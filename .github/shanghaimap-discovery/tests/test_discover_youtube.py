import contextlib
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import uuid
import unittest
from unittest.mock import patch
import urllib.error

from scripts import discover_youtube as d

ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def test_directory():
    # Inherit workspace ACLs: Windows restricted tokens may lose access to
    # tempfile's owner-only directories. All contents here are synthetic.
    root = (ROOT / '.test-work').resolve()
    root.mkdir(exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    try:
        yield str(path)
    finally:
        if path.resolve().parent != root:
            raise RuntimeError('Test directory escaped workspace')
        shutil.rmtree(path)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        # Every in-process test fails if it accidentally attempts live I/O.
        self.network = patch.object(d.urllib.request, 'urlopen', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.api = d.FixtureAPI(d.DEFAULT_FIXTURE)
        self.now = dt.datetime(2026, 11, 1, 12, tzinfo=dt.timezone.utc)
        self.calls = []

    def request(self, endpoint, params):
        self.calls.append((endpoint, copy.deepcopy(params)))
        return self.api(endpoint, params)

    def run_discovery(self, **overrides):
        args = dict(cities=['Shanghai', 'Beijing'], max_searches=8, comments_per_video=50,
                    request=self.request, today=self.now)
        args.update(overrides)
        return d.discover(**args)

    def test_city_date_filtering_deduplication_and_missing_metadata(self):
        result = self.run_discovery()
        self.assertEqual([(v['id'], v['city_candidate']) for v in result['candidates']],
                         [('shanghai', 'Shanghai'), ('beijing', 'Beijing')])
        self.assertEqual(result['searches_run'], 8)
        self.assertEqual(len([c for c in self.calls if c[0] == 'commentThreads']), 3)

    def test_search_budget_and_parameters(self):
        result = self.run_discovery(max_searches=1)
        searches = [p for e, p in self.calls if e == 'search']
        self.assertEqual(len(searches), 1)
        self.assertEqual(result['searches_run'], 1)
        self.assertEqual(searches[0]['publishedAfter'], '2026-01-01T00:00:00Z')
        self.assertEqual(searches[0]['publishedBefore'], '2026-11-01T12:00:00Z')
        self.assertEqual(searches[0]['type'], 'video')
        self.assertEqual(searches[0]['q'], '上海 美食探店')

    def test_zero_searches_no_requests(self):
        self.assertEqual(self.run_discovery(max_searches=0)['candidates'], [])
        self.assertEqual(self.calls, [])

    def test_empty_search_no_metadata_request(self):
        self.assertEqual(self.run_discovery(cities=['Chengdu'])['candidates'], [])
        self.assertTrue(all(e == 'search' for e, p in self.calls))

    def test_window_capped_at_2027(self):
        self.run_discovery(today=dt.datetime(2028, 1, 1, tzinfo=dt.timezone.utc), max_searches=1)
        self.assertEqual(self.calls[0][1]['publishedBefore'], '2027-01-01T00:00:00Z')

    def test_window_not_started(self):
        with self.assertRaisesRegex(ValueError, 'not started'):
            self.run_discovery(today=dt.datetime(2025, 12, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(self.calls, [])

    def test_comments_disabled_by_zero(self):
        result = self.run_discovery(comments_per_video=0)
        self.assertTrue(all(v['comments'] == {} for v in result['candidates']))
        self.assertFalse(any(e == 'commentThreads' for e, p in self.calls))

    def test_comment_filtering_pagination_evidence_and_privacy(self):
        result = d.collect_comments('shanghai', self.request, 50)
        self.assertEqual(result['relevant_comment_count_sampled'], 4)
        self.assertEqual(result['comment_evidence_urls'], [
            'https://www.youtube.com/watch?v=shanghai&lc=c1',
            'https://www.youtube.com/watch?v=shanghai&lc=c2',
            'https://www.youtube.com/watch?v=shanghai&lc=c3'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[1][1]['pageToken'], 'page2')
        self.assertEqual(self.calls[1][1]['maxResults'], 45)
        self.assertEqual(set(result), {'relevant_comment_count_sampled', 'comment_evidence_urls'})

    def test_limit_counts_all_comments_including_spam(self):
        result = d.collect_comments('shanghai', self.request, 6)
        self.assertEqual(result['relevant_comment_count_sampled'], 2)
        self.assertEqual([p['maxResults'] for e, p in self.calls], [6, 1])

    def test_defensive_limit_when_response_exceeds_requested_size(self):
        page = self.api.data['comments']['shanghai']['']
        result = d.collect_comments('shanghai', lambda e, p: page, 2)
        self.assertEqual(result['relevant_comment_count_sampled'], 1)

    def test_spam_variants(self):
        for spam in ['HTTPS://example.invalid', 'www.example.invalid', 'wa.me/123', 't.me/test',
                     'WhatsApp', 'TELEGRAM', '加微', '加v', '私信领取', '代购', '返佣', '推广链接']:
            with self.subTest(spam=spam):
                page = {'items': [{'snippet': {'topLevelComment': {'id': 'spam', 'snippet': {'textDisplay': '推荐好吃 ' + spam}}}}]}
                self.assertEqual(d.collect_comments('x', lambda e, p: page, 10)['relevant_comment_count_sampled'], 0)

    def test_unavailable_comments_and_other_errors(self):
        for code in [403, 404, 429, 500]:
            def fail(endpoint, params):
                raise d.APIError(code)
            with self.subTest(code=code):
                if code in (403, 404):
                    self.assertEqual(d.collect_comments('x', fail)['relevant_comment_count_sampled'], 0)
                else:
                    with self.assertRaises(d.APIError):
                        d.collect_comments('x', fail)

    def test_json_schema_unicode_and_no_private_comment_fields(self):
        with test_directory() as tmp, patch.dict(os.environ, {'YOUTUBE_API_KEY': 'SENTINEL-NEVER-USE'}):
            path = Path(tmp) / 'nested/result.json'
            with contextlib.redirect_stdout(io.StringIO()):
                d.main(['--dry-run', '--output', str(path)])
            raw = path.read_text(encoding='utf-8')
            result = json.loads(raw)
            self.assertTrue(raw.endswith('\n'))
            self.assertIn('上海', raw)
            for private in ['SENTINEL-NEVER-USE', 'textDisplay', 'authorDisplayName', 'Synthetic private author', '地址在测试路一号']:
                self.assertNotIn(private, raw)
            self.assertEqual(result['schema_version'], 1)
            self.assertEqual(result['mode'], 'dry-run')
            first, second = result['candidates']
            self.assertEqual(first['title'], '上海 美食 探店')
            self.assertEqual(len(first['description_excerpt']), 400)
            self.assertEqual(first['view_count'], 123)
            self.assertEqual(second['view_count'], 0)
            for row in result['candidates']:
                self.assertIsNone(row['restaurant_name'])
                self.assertIsNone(row['address'])
                self.assertEqual(row['status'], 'needs_human_review')
                self.assertEqual(row['discovered_at'], result['generated_at'])

    def test_cli_validation_before_network(self):
        for argv in [['--cities', 'Unknown'], ['--cities'], ['--max-searches', '-1'],
                     ['--comments-per-video', '-1'], ['--fixture', str(d.DEFAULT_FIXTURE)]]:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    d.main(argv)
                self.assertEqual(error.exception.code, 2)

    def test_live_requires_key(self):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                d.main([])
            self.assertEqual(error.exception.code, 2)

    def test_transport_errors_never_expose_key(self):
        sentinel = 'FAKE-KEY-SECRET'
        errors = [urllib.error.HTTPError('https://example.invalid/?key=' + sentinel, 500, sentinel, {}, None),
                  urllib.error.URLError(sentinel), TimeoutError(sentinel), ValueError(sentinel)]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(d.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(d.APIError) as caught:
                    d.call('search', {}, sentinel)
                self.assertNotIn(sentinel, str(caught.exception))
                self.assertTrue(caught.exception.__suppress_context__)

    def test_live_failure_leaves_output_untouched(self):
        with test_directory() as tmp, patch.dict(os.environ, {'YOUTUBE_API_KEY':'FAKE'}):
            path = Path(tmp) / 'existing.json'
            path.write_text('original', encoding='utf-8')
            with patch.object(d, 'call', side_effect=d.APIError(429)), self.assertRaises(SystemExit):
                d.main(['--output', str(path)])
            self.assertEqual(path.read_text(), 'original')

    def test_dry_run_subprocess_deterministic_without_key(self):
        env = {k:v for k,v in os.environ.items() if k != 'YOUTUBE_API_KEY'}
        # A subprocess guard makes any urllib call fail, even outside the mock above.
        with test_directory() as tmp:
            path = Path(tmp)
            (path / 'sitecustomize.py').write_text("import urllib.request\ndef deny(*a, **k):\n    raise AssertionError('Network forbidden')\nurllib.request.urlopen = deny\n", encoding='utf-8')
            env['PYTHONPATH'] = str(path)
            outputs = []
            for index in range(2):
                output = path / f'{index}.json'
                run = subprocess.run([sys.executable, str(ROOT / 'scripts/discover_youtube.py'), '--dry-run', '--output', str(output)], cwd=tmp, env=env, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn('Saved 2 video candidates from 8 searches', run.stdout)
                outputs.append(output.read_bytes())
            self.assertEqual(*outputs)

    def test_custom_fixture_and_missing_fixture_do_not_fall_back(self):
        with test_directory() as tmp:
            path = Path(tmp) / 'fixture.json'
            data = copy.deepcopy(self.api.data)
            data['searches'] = {}
            path.write_text(json.dumps(data), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                result = d.main(['--dry-run', '--fixture', str(path), '--output', str(Path(tmp) / 'out.json')])
            self.assertEqual(result['candidates'], [])
            with self.assertRaises(FileNotFoundError):
                d.main(['--dry-run', '--fixture', str(Path(tmp) / 'missing.json')])


if __name__ == '__main__':
    unittest.main()
