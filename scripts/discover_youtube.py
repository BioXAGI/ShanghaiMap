#!/usr/bin/env python3
"""Discover review-only video candidates; --dry-run uses synthetic offline fixtures."""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

CITIES = {"Shanghai": "上海", "Beijing": "北京", "Guangzhou": "广州", "Shenzhen": "深圳",
          "Chengdu": "成都", "Chongqing": "重庆", "Hangzhou": "杭州", "Suzhou": "苏州",
          "Nanjing": "南京", "Xian": "西安", "Wuhan": "武汉", "Xiamen": "厦门",
          "Changsha": "长沙", "Qingdao": "青岛", "Kunming": "昆明", "Tianjin": "天津"}
KEYWORDS = ["美食探店", "苍蝇馆子", "本地美食", "food tour"]
SPAM = re.compile(r"(https?://|www\.|wa\.me/|t\.me/|whatsapp|telegram|加微|加V|私信领取|代购|返佣|推广链接)", re.I)
CLUES = re.compile(r"(店名|地址|在哪|在哪里|几号|路|街|巷|推荐|好吃|人均|元|面馆|饭店|餐厅|小吃|烧烤|火锅|粉店|馄饨|生煎|老店)")
DEFAULT_FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/youtube.json"


class APIError(Exception):
    """A safe error that never retains the request URL or API key."""
    def __init__(self, status=None):
        self.status = status
        super().__init__(f"YouTube API request failed (HTTP {status})" if status else
                         "YouTube API request failed (network or invalid response)")


def call(endpoint, params, key):
    url = "https://www.googleapis.com/youtube/v3/" + endpoint + "?" + urllib.parse.urlencode(dict(params, key=key))
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ShanghaiMapDiscovery/0.1"})
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise APIError(exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise APIError() from None


class FixtureAPI:
    """Serve synthetic API-shaped responses without any network fallback."""
    def __init__(self, path):
        self.data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    def __call__(self, endpoint, params):
        if endpoint == "search":
            return self.data["searches"].get(params["q"], {"items": []})
        if endpoint == "videos":
            ids = params["id"].split(",")
            return {"items": [v for v in self.data["videos"] if v["id"] in ids]}
        if endpoint == "commentThreads":
            page = self.data["comments"].get(params["videoId"], {}).get(params.get("pageToken", ""), {"items": []})
            if "error_status" in page:
                raise APIError(page["error_status"])
            return dict(page, items=page.get("items", [])[:params["maxResults"]])
        raise ValueError("Unsupported fixture endpoint")


def normalize(value):
    return re.sub(r"\s+", " ", value or "").strip()


def collect_comments(video_id, request, limit=100):
    """Sample at most limit top-level comments over at most two pages."""
    sampled = found = pages = 0
    examples = []
    token = None
    while sampled < limit and pages < 2:
        params = {"part": "snippet", "videoId": video_id, "maxResults": min(100, limit - sampled),
                  "textFormat": "plainText", "order": "relevance"}
        if token:
            params["pageToken"] = token
        try:
            payload = request("commentThreads", params)
        except APIError as exc:
            if exc.status in (403, 404):
                break
            raise
        for item in payload.get("items", [])[:limit - sampled]:
            sampled += 1
            top = item.get("snippet", {}).get("topLevelComment", {})
            txt = normalize(top.get("snippet", {}).get("textDisplay", ""))
            if not txt or SPAM.search(txt) or len(txt) > 600:
                continue
            if CLUES.search(txt):
                found += 1
                comment_id = top.get("id")
                if comment_id and len(examples) < 3:
                    examples.append("https://www.youtube.com/watch?" + urllib.parse.urlencode({"v": video_id, "lc": comment_id}))
        token = payload.get("nextPageToken")
        pages += 1
        if not token:
            break
    return {"relevant_comment_count_sampled": found, "comment_evidence_urls": examples}


def discover(cities, max_searches, comments_per_video, request, today):
    stop = min(today, dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc))
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    if stop <= start:
        raise ValueError("2026 discovery window has not started")
    out, seen = [], set()
    searches = 0
    for city in cities:
        for keyword in KEYWORDS:
            if searches >= max_searches:
                break
            params = {"part": "snippet", "type": "video", "q": CITIES[city] + " " + keyword,
                      "maxResults": 15, "publishedAfter": "2026-01-01T00:00:00Z",
                      "publishedBefore": stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "order": "relevance", "regionCode": "HK"}
            payload = request("search", params)
            searches += 1
            ids = list(dict.fromkeys(v["id"]["videoId"] for v in payload.get("items", []) if v.get("id", {}).get("videoId")))
            if not ids:
                continue
            meta = request("videos", {"part": "snippet,statistics", "id": ",".join(ids)})
            for video in meta.get("items", []):
                vid = video["id"]
                if vid in seen:
                    continue
                sn = video["snippet"]
                published = sn.get("publishedAt", "")
                try:
                    published_time = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if not start <= published_time < stop:
                        continue
                except (ValueError, TypeError):
                    continue
                title = normalize(sn.get("title", ""))
                descr = normalize(sn.get("description", ""))
                text = title + " " + descr
                if CITIES[city] not in text and city.lower() not in text.lower():
                    continue
                seen.add(vid)
                comments = collect_comments(vid, request, comments_per_video) if comments_per_video else {}
                out.append({"id": vid, "city_candidate": city, "title": title, "description_excerpt": descr[:400],
                            "published_at": published, "channel_title": sn.get("channelTitle", ""),
                            "video_url": "https://www.youtube.com/watch?v=" + vid,
                            "view_count": int(video.get("statistics", {}).get("viewCount", 0)),
                            "comments": comments, "restaurant_name": None, "address": None,
                            "status": "needs_human_review", "discovered_at": today.isoformat()})
        if searches >= max_searches:
            break
    return {"schema_version": 1, "generated_at": today.isoformat(),
            "note": "Video candidates, NOT verified restaurant pins; no raw comments saved",
            "cities": list(cities), "searches_run": searches, "candidates": out}


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", nargs="+", choices=list(CITIES), default=list(CITIES))
    parser.add_argument("--max-searches", type=nonnegative, default=8)
    parser.add_argument("--comments-per-video", type=nonnegative, default=50)
    parser.add_argument("--output", help="Default: data/youtube_candidates[.dry-run].json")
    parser.add_argument("--dry-run", action="store_true", help="Use synthetic fixtures; no key or network")
    parser.add_argument("--fixture", type=pathlib.Path, help="Custom fixture JSON (requires --dry-run)")
    args = parser.parse_args(argv)
    if args.fixture and not args.dry_run:
        parser.error("--fixture requires --dry-run")
    try:
        if args.dry_run:
            request = FixtureAPI(args.fixture or DEFAULT_FIXTURE)
            today = dt.datetime.fromisoformat(request.data["now"].replace("Z", "+00:00"))
        else:
            key = os.getenv("YOUTUBE_API_KEY")
            if not key:
                parser.error("YOUTUBE_API_KEY environment variable is required for live mode")
            request = lambda endpoint, params: call(endpoint, params, key)
            today = dt.datetime.now(dt.timezone.utc)
        result = discover(args.cities, args.max_searches, args.comments_per_video, request, today)
        result["mode"] = "dry-run" if args.dry_run else "live"
        path = pathlib.Path(args.output or ("data/youtube_candidates.dry-run.json" if args.dry_run else "data/youtube_candidates.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except APIError as exc:
        raise SystemExit(str(exc)) from None
    print(f"Saved {len(result['candidates'])} video candidates from {result['searches_run']} searches to {path} ({result['mode']})")
    return result


if __name__ == "__main__":
    main()
