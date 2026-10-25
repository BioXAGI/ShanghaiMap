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

The site includes two published restaurant entries with pins, source links, and a storefront reference image. New browsers receive this published collection automatically. Existing matching entries are preserved without duplication. Each published batch is imported once, so local edits and deletions survive reloads. Personal additions and edits are stored in localStorage on the current browser and site origin; they do not automatically sync to GitHub or another device. Export backups regularly, especially before changing browsers or URLs. Storage limits vary; the app reports failed writes instead of claiming to save them. Imported backups can contain personal notes and images; keep them private as appropriate.

The map needs internet access to Leaflet (unpkg.com) and OpenStreetMap tile servers. Core notebook functions continue when the map library is unavailable. These services receive normal network request information. Address searches are sent to Amap only when you click Find address. Pins use WGS84; coordinates from Chinese map services may need adjustment.

Published places: 冯爸面馆（陕西南路31号） and 谈灵农家柴爿菜饭（浦东新区川沙新镇水闸南路7号）. Location provenance and uncertainty are recorded in each entry; the 冯爸 pin is approximate. GitHub Pages is enabled at https://bioxagi.github.io/ShanghaiMap/.


## Compact cards and personal notebook

Each card shows a short description, up to three sourced food highlights, and Locate, Video, Save, and Details actions. Click a card or use Details in its map popup for the address, reference photo, sources, and My notes.

My notes, rating, saved state, and visit status use a separate browser-local notebook keyed by stable restaurant IDs. They are never included in Export places or the published catalog. Back up my notes exports them explicitly; Restore notes merges missing personal entries and preserves existing notes. This is local storage, not a password-protected account: people using the same browser profile can access it. There is no cross-device synchronization.

Manage places reveals local catalog editing, importing, and exporting. This is a convenience view, not an administrator login. Website publication still requires a GitHub commit. Place imports preserve IDs so a corresponding personal backup can reconnect to those places. Existing legacy place/source notes are not automatically classified as private. Use My notes for personal text.

Verified: JavaScript syntax; compact card and details rendering; saving and reloading personal note, rating, status; saved-place filtering; management controls; personal export includes personal text while place export and website source exclude it.

