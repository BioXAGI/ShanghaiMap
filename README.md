# Shanghai Food Map · 上海食记

A static, browser-local food notebook rebuilt from the available conversation requirements. This is a reconstruction, not the recovered original artifact.

## Features

- Add, edit, delete, and search places; filter by cuisine and visit status.
- Save addresses, dishes, budgets, districts, and notes.
- Paste a screenshot with Ctrl+V / Cmd+V or upload a PNG, JPEG, or WebP. Images are resized locally and attached to a place. Image text is **not** extracted automatically.
- Place and move pins on an OpenStreetMap map; enter coordinates manually if preferred.
- Open an address search in Amap.
- Export and import JSON backups including reference images. Import adds entries and preserves existing ones.

## Run

Serve this directory with any static web server, for example `python -m http.server 8080`, then open `http://localhost:8080`. No build step or API keys are required.

## Publish with GitHub Pages

In this repository, open **Settings → Pages → Build and deployment**. Select **Deploy from a branch**, choose **main** and **/ (root)**, then Save. After GitHub finishes deployment, the expected URL is `https://bioxagi.github.io/ShanghaiMap/`.

## Data and limitations

Entries and images are stored in localStorage on the current browser and site origin; they do not sync to GitHub or another device. Export backups regularly, especially before changing browsers or URLs. Storage limits vary; the app reports failed writes instead of claiming to save them. Imported backups can contain personal notes and images; keep them private as appropriate.

The map needs internet access to Leaflet (unpkg.com) and OpenStreetMap tile servers. Core notebook functions continue when the map library is unavailable. These services receive normal network request information. Address searches are sent to Amap only when you click Find address. Pins use WGS84; coordinates from Chinese map services may need adjustment.

The app begins empty: it contains no invented restaurant recommendations or unverified locations.

