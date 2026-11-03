# Local discovery and review dashboard

Run the backend on your computer; publish only approved restaurant data to GitHub Pages. It never pushes, merges, uploads videos, or changes the online map automatically.

## Start on Windows

From the ShanghaiMap checkout (Python 3.11+):

```powershell
python -m pip install -r requirements-local.txt
python scripts/local_dashboard.py --oauth-token "$env:USERPROFILE\MP4MTV\work\youtube-token.json"
```

Open **http://127.0.0.1:8081/**. The existing static map may stay on port 8080. The dashboard serves its own current map at `/map`.

The OAuth option points to an existing Google authorized-user token file, not an OAuth client-secret file. Connect YouTube in MP4MTV first if needed. The dashboard refreshes authorization in memory, only sends read requests to YouTube, and never changes or copies MP4MTV's token file. Only the token file location is remembered in ignored `.local/config.json`. You can instead supply `YOUTUBE_API_KEY` in the process environment; it takes precedence. No credentials reach the browser or prepared map.

After first setup, start with either:

```powershell
python scripts/local_dashboard.py
# Or:
.\start-local.ps1
```

If PowerShell script execution is restricted, use the Python command; no execution-policy change is needed. Stop with Ctrl+C. Use `--port 8082` if 8081 is occupied. Without credentials, the offline demo and review/preparation still work; OAuth dependencies are only needed for Google sign-in.

To load a prior discovery result once:

```powershell
python scripts/local_dashboard.py --import-candidates "C:\path\to\youtube_candidates.live.json"
```

Imports merge by video ID and preserve saved reviews. Files marked `mode: live` are live candidates; all other imported runs are treated as synthetic and cannot be approved. Only import files you trust. The import allowlists fields and drops raw comments and arbitrary credential fields.

## Discover → review → prepare

1. Choose a city and click **Discover on YouTube**. Confirm one search, up to 15 candidates, and at most 10 sampled comments per candidate. A repeated search may return the same videos; it updates metadata without duplicating candidates. **Try demo** uses fixtures and no network.
2. Select a candidate. Open its source video and comment links. Enter the verified restaurant/branch name, address, optional cuisine/district, WGS84 coordinates, and public source notes. This version supports one restaurant per video; multi-restaurant videos require choosing one for this update.
3. **Save draft**, **Reject candidate**, or check the verification box and **Approve restaurant**. The backend requires a name, address, valid coordinates, and verification. Demo candidates cannot be approved. No video is automatically converted into a verified restaurant.
4. **Preview map** shows approved additions with the existing public catalog in a separate preview notebook. Preview edits do not update the saved review: make final corrections in the dashboard and reopen the preview.
5. **Prepare online update** writes `.local/prepared/index.html` and `.local/prepared/approved-places.json`. Download links regenerate the current approved selection. Drafts, rejected entries, raw comments, credentials, and personal notebook data are excluded. The updated HTML changes the published batch marker so existing visitors can receive new entries without losing local edits.

Reviews and candidates persist in `.local/state.json`; keep a private backup if needed. This folder is ignored by Git and is not exposed by the backend. Live metadata does not expire automatically; remove obsolete data when no longer needed. Run only one dashboard process per checkout so file writes remain serialized.

## Explicit online update

Preparation does **not** modify tracked `index.html`. Inspect the prepared map and source evidence first. For this open PR, keep work on `feature/youtube-2026-discovery`; do not merge until separately approved.

When you explicitly decide to submit the prepared catalog, stop editing reviews, check that your checkout is current and that `index.html` has no unrelated local changes, and prepare again. Then, from the repository folder:

```powershell
Copy-Item -LiteralPath .local/prepared/index.html -Destination index.html
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
git diff --check
git diff --stat
git diff -- index.html
# After reviewing the changes:
git add index.html
git commit -m "Add reviewed Shanghai restaurants"
git push origin feature/youtube-2026-discovery
```

This updates the existing PR. Publication requires a separate reviewed merge into the branch configured for GitHub Pages. There is no automatic live discovery schedule.

This version adds new published entries. Duplicate restaurant names or IDs are rejected because the existing map imports additions without overwriting local edits. Use a distinct branch name for genuinely different locations; editing or deleting an already published restaurant requires a separate catalog change and migration decision.

## Checks and local access

```powershell
python -m unittest discover -s tests -v
```

The suite covers discovery, filtering, JSON/privacy, persisted review state, approval validation, demo exclusion, duplicate entries, safe HTML serialization, prepared files, and HTTP access controls. It uses synthetic data and does not consume YouTube quota. The server binds only to loopback, allows only known public files/routes, validates Host and Origin, and requires a per-process anti-forgery token for writes. Do not expose this development backend on your LAN or the public internet.
