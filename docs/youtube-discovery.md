# YouTube 2026 discovery (experimental)

The existing Shanghai map remains unchanged. This separate job discovers **video candidates**, not geocoded restaurants. Output is a GitHub Actions artifact for review, never automatically published as pins.

## Setup
1. Enable YouTube Data API v3 in Google Cloud.
2. Add the API key in GitHub repository **Settings > Secrets and variables > Actions > New repository secret**, name `YOUTUBE_API_KEY`.
3. Open Actions > **Discover 2026 China food videos** > Run workflow.
4. Download the resulting `youtube-candidates-2026` artifact from that run, and manually review videos and restaurant location evidence.

The default job uses 8 searches across the configured cities (currently starting with Shanghai and Beijing; raise `--max-searches` or rotate city batches for broader coverage). All 16 cities are configured. `search.list` has high quota cost; monitor the Google Cloud quota. Search results are not exhaustive and may include sponsored content. Search terms use Chinese and English variants.

The job reads public top-level comments via the official API, drops likely promotions/links, and stores **only aggregate counts and comment URLs**, not raw text or commenter details. Comment links can expire or become unavailable; disabled comments are skipped. Do not treat comment agreement as a verification signal.

Video title, date, channel, metadata and a description excerpt are stored in the transient artifact; no full video, image or comment is scraped. Review access, attribution, caching/retention, and YouTube API policies before deploying beyond this experiment. The weekly run retains output for 7 days. Avoid persisting stale YouTube metadata.

All restaurant names, branches, addresses and coordinates require human verification before adding to the public catalog. Coordinates for Leaflet must be WGS84 (not unconverted GCJ-02). The website does not read your API key.
