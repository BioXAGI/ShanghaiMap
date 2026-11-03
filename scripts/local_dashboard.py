"""Loopback-only discovery and editorial dashboard. No automatic publishing."""
import argparse
import datetime as dt
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request

try:
    from . import discover_youtube as discovery
except ImportError:
    import discover_youtube as discovery

ROOT = Path(__file__).resolve().parents[1]


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def public_candidate(value):
    """Allowlist discovery data before saving it locally or returning it to a browser."""
    vid = str(value.get('id', ''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', vid):
        raise ValueError('Invalid video ID')
    comments = value.get('comments') or {}
    links = [url for url in comments.get('comment_evidence_urls', [])
             if isinstance(url, str) and url.startswith('https://www.youtube.com/watch?')][:3]
    return {'id': vid, 'title': str(value.get('title', ''))[:500],
            'city_candidate': str(value.get('city_candidate', 'Shanghai'))[:80],
            'description_excerpt': str(value.get('description_excerpt', ''))[:400],
            'video_url': 'https://www.youtube.com/watch?v=' + vid,
            'published_at': str(value.get('published_at', ''))[:80],
            'comments': {'relevant_comment_count_sampled': int(comments.get('relevant_comment_count_sampled', 0)),
                         'comment_evidence_urls': links}}


def validate_review(candidate, data):
    decision = data.get('decision', 'draft')
    if decision not in ('draft', 'approved', 'rejected'):
        raise ValueError('Choose draft, approved, or rejected')
    result = {'decision': decision, 'verified': data.get('verified') is True}
    for field, limit in [('name',120), ('address',2000), ('district',2000), ('cuisine',2000), ('notes',1500)]:
        value = data.get(field, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'Invalid {field}')
        result[field] = value.strip()
    for field, bound in [('lat',90), ('lng',180)]:
        value = data.get(field)
        if value in ('', None):
            result[field] = None
        else:
            try:
                number = float(value)
            except (ValueError, TypeError):
                raise ValueError(f'Invalid {field}') from None
            if isinstance(value, bool) or not math.isfinite(number) or abs(number) > bound:
                raise ValueError(f'Invalid {field}')
            result[field] = number
    if decision == 'approved':
        if not result['verified'] or not result['name'] or not result['address'] or any(result[x] is None for x in ('lat','lng')):
            raise ValueError('Approval requires a name, address, both WGS84 coordinates, and verification')
        if candidate.get('synthetic'):
            raise ValueError('Demo candidates cannot be approved for publication')
    return result


def render_catalog(source, additions):
    match = re.search(r'const PUBLISHED_PLACES = (\[.*?\]);', source, re.S)
    if not match:
        raise ValueError('Published catalog not found')
    existing = json.loads(match[1])
    ids = {p['id'] for p in existing}
    # The current website deduplicates by name. Reject collisions instead of
    # preparing records that existing visitors would silently fail to import.
    names = {p['name'].strip().casefold() for p in existing}
    for place in additions:
        if place['id'] in ids or place['name'].strip().casefold() in names:
            raise ValueError('A restaurant with this name or ID already exists; use a distinct branch name')
        ids.add(place['id'])
        names.add(place['name'].strip().casefold())
    catalog = json.dumps(existing + additions, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    updated = source[:match.start(1)] + catalog + source[match.end(1):]
    digest = hashlib.sha256(catalog.encode()).hexdigest()[:12]
    updated, count = re.subn(r"const PUBLISHED_BATCH_KEY='[^']+';", "const PUBLISHED_BATCH_KEY='shanghai-food-map-published-" + digest + "';", updated)
    if count != 1:
        raise ValueError('Published batch marker not found')
    return updated


class Studio:
    def __init__(self, root=ROOT, data_dir=None, oauth_token=None):
        self.root = Path(root)
        self.data_dir = Path(data_dir or self.root / '.local')
        self.oauth_token = Path(oauth_token) if oauth_token else None
        self.lock = threading.Lock()
        self.csrf = secrets.token_urlsafe(32)
        state_file = self.data_dir / 'state.json'
        self.state = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {'candidates': [], 'reviews': {}, 'last_run': None}

    def save(self):
        atomic_json(self.data_dir / 'state.json', self.state)

    def snapshot(self):
        return dict(self.state, csrf=self.csrf, cities=list(discovery.CITIES),
                    auth_available=bool(os.getenv('YOUTUBE_API_KEY') or self.oauth_token and self.oauth_token.is_file()))

    def merge(self, payload, synthetic=False):
        items = {item['id']: item for item in self.state['candidates']}
        for raw in payload['candidates']:
            item = public_candidate(raw)
            item['synthetic'] = synthetic
            if item['id'] in items and items[item['id']].get('synthetic') != synthetic:
                raise ValueError('Demo and live candidate IDs conflict')
            items[item['id']] = item
        self.state['candidates'] = list(items.values())
        self.state['last_run'] = {key: payload.get(key) for key in ('generated_at','searches_run','mode')}
        self.save()

    def live_request(self):
        key = os.getenv('YOUTUBE_API_KEY')
        if key:
            return lambda endpoint, params: discovery.call(endpoint, params, key)
        if not self.oauth_token or not self.oauth_token.is_file():
            raise ValueError('No local YouTube sign-in configured. Start with --oauth-token or YOUTUBE_API_KEY.')
        try:
            import requests
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError:
            raise ValueError('Install requirements-local.txt to use a saved Google sign-in') from None
        try:
            creds = Credentials.from_authorized_user_file(str(self.oauth_token))
            session = requests.Session()
            session.trust_env = False
            if not creds.valid:
                creds.refresh(Request(session=session))
        except Exception:
            raise ValueError('Saved Google sign-in could not be used. Reconnect YouTube in the app that created it.') from None
        def request(endpoint, params):
            try:
                response = session.get('https://www.googleapis.com/youtube/v3/' + endpoint,
                                       params=params, headers={'Authorization': 'Bearer ' + creds.token}, timeout=25)
                if not response.ok:
                    raise discovery.APIError(response.status_code)
                return response.json()
            except discovery.APIError:
                raise
            except Exception:
                raise discovery.APIError() from None
        return request

    def discover(self, data):
        city = data.get('city', 'Shanghai')
        if city not in discovery.CITIES:
            raise ValueError('Choose a supported city')
        demo = data.get('demo') is True
        request = discovery.FixtureAPI(discovery.DEFAULT_FIXTURE) if demo else self.live_request()
        now = dt.datetime.fromisoformat(request.data['now'].replace('Z','+00:00')) if demo else dt.datetime.now(dt.timezone.utc)
        result = discovery.discover([city], 1, 10, request, now)
        result['mode'] = 'dry-run' if demo else 'live'
        self.merge(result, synthetic=demo)
        return {'message': f"Found {len(result['candidates'])} candidates in one {'demo' if demo else 'live'} search."}

    def review(self, data):
        candidate = next((c for c in self.state['candidates'] if c['id'] == data.get('id')), None)
        if not candidate:
            raise ValueError('Candidate not found')
        self.state['reviews'][candidate['id']] = validate_review(candidate, data)
        self.save()
        return {'message':'Review saved on this computer.'}

    def prepared(self):
        additions = []
        for candidate in self.state['candidates']:
            review = self.state['reviews'].get(candidate['id'], {})
            if review.get('decision') != 'approved':
                continue
            review = validate_review(candidate, review)
            place = {k:review[k] for k in ('name','address','district','cuisine','lat','lng')}
            place.update(id='youtube-' + candidate['id'], image='', status='Want to try', budget='',
                         notes=review['notes'], videoUrl=candidate['video_url'], videoTime='')
            additions.append(place)
        if not additions:
            raise ValueError('Approve at least one verified restaurant first')
        source = (self.root / 'index.html').read_text(encoding='utf-8')
        html = render_catalog(source, additions)
        return html, additions

    def prepare(self):
        html, additions = self.prepared()
        target = self.data_dir / 'prepared'
        target.mkdir(parents=True, exist_ok=True)
        (target / 'index.html').write_text(html, encoding='utf-8')
        atomic_json(target / 'approved-places.json', {'format':'shanghai-food-map','version':1,'places':additions})
        return {'message':f'Prepared {len(additions)} verified places. Download the map, review it, then submit a Git update.', 'count':len(additions)}


def handler_for(studio):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body, content_type='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(body)

        def trusted_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.trusted_host():
                return self.respond(403, {'error':'Local access only'})
            path = urllib.parse.urlsplit(self.path).path
            try:
                if path == '/api/state':
                    if not studio.lock.acquire(blocking=False):
                        return self.respond(409, {'error':'Discovery is running. Please wait.'})
                    try:
                        return self.respond(200, studio.snapshot())
                    finally:
                        studio.lock.release()
                if path in ('/preview', '/download/index.html', '/download/approved-places.json'):
                    with studio.lock:
                        html, places = studio.prepared()
                    if path.endswith('.json'):
                        return self.respond(200, {'format':'shanghai-food-map','version':1,'places':places})
                    if path == '/preview':
                        # Preview gets an isolated notebook, refreshed per preview;
                        # ordinary map/local personal data is never overwritten.
                        html = html.replace("KEY='shanghai-food-map-v1'", "KEY='shanghai-food-map-preview-" + secrets.token_hex(8) + "'")
                        html = html.replace("PERSONAL_KEY='shanghai-food-map-personal-v1'", "PERSONAL_KEY='shanghai-food-map-preview-personal'")
                        html = html.replace('shanghai-food-map-published-', 'shanghai-food-map-preview-' + secrets.token_hex(8) + '-')
                    return self.respond(200, html.encode('utf-8'), 'text/html; charset=utf-8')
                files = {'/': ('local-dashboard/index.html','text/html'), '/app.js':('local-dashboard/app.js','text/javascript'),
                         '/style.css':('local-dashboard/style.css','text/css'), '/map':('index.html','text/html')}
                if path not in files:
                    return self.respond(404, {'error':'Not found'})
                file, mime = files[path]
                return self.respond(200, (studio.root / file).read_bytes(), mime + '; charset=utf-8')
            except ValueError as exc:
                self.respond(400, {'error':str(exc)})
            except Exception:
                self.respond(500, {'error':'Unable to load this view'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            allowed = (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}')
            if not self.trusted_host() or origin not in allowed or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''), studio.csrf):
                return self.respond(403, {'error':'Open the local dashboard and retry'})
            if not studio.lock.acquire(blocking=False):
                return self.respond(409, {'error':'Another operation is running'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 20000:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected an object')
                routes = {'/api/discover':studio.discover, '/api/review':studio.review, '/api/prepare':lambda _:studio.prepare()}
                action = routes.get(self.path)
                if not action:
                    return self.respond(404, {'error':'Not found'})
                self.respond(200, action(data))
            except (ValueError, discovery.APIError) as exc:
                self.respond(400, {'error':str(exc)})
            except Exception:
                self.respond(500, {'error':'Operation failed; local credentials were not disclosed'})
            finally:
                studio.lock.release()
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--oauth-token', type=Path, help='Existing authorized-user Google token; never copied or modified')
    parser.add_argument('--import-candidates', type=Path, help='Import a discovery JSON file at startup')
    args = parser.parse_args()
    config_path = ROOT / '.local' / 'config.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    token_path = args.oauth_token or config.get('oauth_token')
    studio = Studio(oauth_token=token_path)
    if args.oauth_token:
        # Save the file location only. Credential contents remain in their owner app.
        atomic_json(config_path, {'oauth_token': str(args.oauth_token.resolve())})
    if args.import_candidates:
        payload = json.loads(args.import_candidates.read_text(encoding='utf-8'))
        studio.merge(payload, synthetic=payload.get('mode') != 'live')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(studio))
    print(f'Local dashboard: http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
