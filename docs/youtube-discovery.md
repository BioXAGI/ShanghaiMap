# YouTube 2026 discovery (experimental)

Start with the offline tests and dry run below. Discovery produces **video candidates**, not verified restaurants or map pins. The website does not load this JSON. The discovery workflow is **manual only**; there is no weekly schedule.

## Windows PowerShell: offline first

Install Python 3.11 or newer and Git. No third-party Python packages, API key, Google Cloud setup, or virtual-environment activation are needed for these tests.

```powershell
git clone --branch feature/youtube-2026-discovery https://github.com/BioXAGI/ShanghaiMap.git
Set-Location ShanghaiMap
py -3 --version
py -3 -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed' }

py -3 scripts/discover_youtube.py --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Dry run failed' }
$result = Get-Content -Raw -Encoding UTF8 data/youtube_candidates.dry-run.json | ConvertFrom-Json
$result | Select-Object schema_version, mode, searches_run
$result.candidates | Select-Object id, city_candidate, status
```

If already cloned, enter that checkout and use `git switch feature/youtube-2026-discovery` then `git pull --ff-only` before testing. If the `py` launcher is unavailable, use `python` in place of `py -3`, after confirming its version.

Expected: **30 tests pass**, followed by `Saved 2 video candidates from 8 searches ... (dry-run)`. The JSON has `schema_version: 1`, `mode: dry-run`, and synthetic `shanghai` / `beijing` candidates, both `needs_human_review`. This is a fixture result, not evidence of real restaurants. Tests block network calls and exercise the CLI in a subprocess without a key. Temporary synthetic test files use an ignored `.test-work` directory with inherited Windows permissions and are removed after each test.

The dry run never reads the API key and never calls YouTube. It uses `tests/fixtures/youtube.json`, a synthetic dataset with a fixed clock (`2026-11-01T12:00:00Z`), so repeated runs produce identical JSON. Its default output is separate from live output. The fixture covers duplicate and unrelated videos, other years, future/invalid timestamps, unavailable metadata, spam, pagination, and disabled comments.

For a smaller offline run or your own synthetic fixture:

```powershell
py -3 scripts/discover_youtube.py --dry-run --cities Shanghai --max-searches 1 --comments-per-video 6
py -3 scripts/discover_youtube.py --dry-run --fixture tests/fixtures/youtube.json --output data/youtube_candidates.custom.json
```

The fixture contains `now`, `searches` (exact query to API-shaped search response), `videos` (metadata list), and `comments` (video ID to page token to API-shaped response). The first page token is an empty string. A comment page can use `error_status` to simulate an HTTP failure. Unknown searches/comments return empty results; missing or invalid fixture files fail without falling back to the network. `--fixture` requires `--dry-run`.

## Optional bounded live run, after offline review

This uses real YouTube quota and is separate from the offline checks. Enable YouTube Data API v3 in Google Cloud first. Enter the key at a hidden prompt, rather than pasting it into a command, source file, chat, or shell history. The script reads only `YOUTUBE_API_KEY` from the process environment; it does not read `.env` files.

```powershell
$secureKey = Read-Host 'YouTube API key' -AsSecureString
try {
    $env:YOUTUBE_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
    py -3 scripts/discover_youtube.py --cities Shanghai --max-searches 1 --comments-per-video 10
    if ($LASTEXITCODE -ne 0) { throw 'Live discovery failed; check API access and quota' }
    $live = Get-Content -Raw -Encoding UTF8 data/youtube_candidates.json | ConvertFrom-Json
    $live.candidates | Select-Object title, video_url, status
}
finally {
    Remove-Item Env:YOUTUBE_API_KEY -ErrorAction SilentlyContinue
    $secureKey.Dispose()
    Remove-Variable secureKey -ErrorAction SilentlyContinue
}
```

Do not print the environment variable. Errors report only HTTP status or a generic transport failure, never the request URL/key. A failed API request leaves any existing output untouched. Generated discovery JSON, `.env` files, and Python caches are ignored by Git; avoid custom output names outside the ignored pattern or committing live metadata.

`--max-searches` bounds search requests (15 results per request). Defaults are eight searches, starting with Shanghai and Beijing; all 16 cities are configured and each city has four query variants. `search.list` has a high quota cost. Each nonempty search also requests video metadata, and each accepted unique candidate may request up to two comment pages. `--comments-per-video` limits **all sampled comments**, including spam and irrelevant comments, rather than only matched clues; each page requests at most 100. Zero skips comment requests. Zero searches writes an empty result. Negative limits and unknown cities are rejected before network access.

403/404 responses on comments are skipped (this can mean disabled/unavailable comments or forbidden access, not proof that comments are disabled). Other API failures stop the run. Search/metadata failures also stop the run. Search results and heuristic comment clues are incomplete and may include sponsored content; they are not verification signals.

## Manual GitHub Actions (optional later)

The workflow has only `workflow_dispatch`. After local validation and a separate decision to run live, add the key to repository **Settings > Secrets and variables > Actions** as `YOUTUBE_API_KEY`, then use **Discover 2026 China food videos > Run workflow** on the desired branch. It runs the offline tests before querying YouTube and uploads review-only JSON with seven-day artifact retention. Nothing schedules or publishes map pins automatically.

## Output and review

The UTF-8 JSON includes schema version, run mode, timestamp, requested cities, search count, and candidate metadata. Titles/descriptions are whitespace-normalized; description excerpts are capped at 400 characters. Deduplication happens after city/date validation. Dates must fall within the elapsed part of 2026, capped at 2027-01-01. The default discovery output is `data/youtube_candidates.json` for live runs and `data/youtube_candidates.dry-run.json` for fixtures.

Only aggregate relevant-comment counts and up to three top-level comment links are retained. Comment bodies and commenter details are not saved. Likely promotional links/messages and comments over 600 characters are filtered heuristically. Comment links can expire. Video title, date, channel, view count, and description excerpt are transient metadata; no full video or image is downloaded. Local files do not expire automatically: delete stale live output yourself and review YouTube API access, attribution, and retention policies before broader use.

Every candidate has `restaurant_name: null`, `address: null`, and `status: needs_human_review`. Verify names, branches, addresses, and coordinates manually before adding entries to the public catalog. Leaflet coordinates must be WGS84 (not unconverted GCJ-02). The website never receives the API key.

For a local browser dashboard with saved Google sign-in, candidate review, and map preparation, see [Local dashboard](local-dashboard.md).
