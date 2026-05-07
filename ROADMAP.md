# Roadmap — Czyja działka?

## Changelog

### 2026-04-20

**Project initialization**
- Initial Flask + Leaflet app created (`server.py`, `index.html`, `render.yaml`, `requirements.txt`). Parcel lookup via GEOPOZ GeoServer WMS GetFeatureInfo. Deployed to Render free tier.
- Prototype copy placed in `geopoz-app/` subdirectory (later superseded by root-level files).

**Early debugging & stabilization**
- Fixed syntax errors in `server.py`.
- Added character escaping in HTML and server responses.
- Added error logging to backend.
- Investigated session-based authentication with GEOPOZ (dynamic `mapServiceIds`, CSRF cookie fetching) — ultimately abandoned in favour of direct GeoServer WMS access.
- Added a `/featureInfo` test endpoint (debug, later removed from active use).
- Fixed WMS service initialization order.

**Refactor: direct GeoServer access**
- Removed all session/cookie/CSRF logic. Backend now hits `wms2.geopoz.poznan.pl/geoserver/egib/ows` directly with WMS `GetFeatureInfo`.
- Fixed BBOX axis order for EPSG:2177 (northing/easting, not easting/northing).

**Features: geolocation & UX**
- Geolocation on page load — map centers on user's position at zoom 16.
- Double-tap zoom (Leaflet default re-enabled), with single-tap/double-tap disambiguation via 250 ms timer to avoid accidental parcel lookups on zoom.

**Features: powierzenia (road concession) lookup**
- Backend reads `powierzenia-YYYY-MM-DD.xlsx` at startup into an in-memory dict keyed by parcel number (`OZN_DZ`).
- Tap result now shows: concession holder name (`OPIS`), concession signature (`SYGNATURA`), and database date + record count.
- Renamed field `Władający` → `Rodzaj zarządzania`.

**Features: parcel outline on map**
- Added GEOPOZ WMS layer (`dzialki_szraw_sql`) as a semi-transparent tile overlay.
- On tap: WFS `GetFeature` query with `INTERSECTS` spatial filter retrieves the clicked parcel's geometry; rendered as a blue polygon with black outline.
- Parcel number label (`OZN_DZ`) displayed as a permanent tooltip over the outline centre.
- Fixed: WFS layer name (`egib:dzialki_ewidencyjne_sql`), CRS axis order, race condition on fast successive taps.
- Outline colour changed to black for better contrast against the blue fill.

**Field display polish**
- Field order reordered: Zarządca, Sygnatura powierzenia, Rodzaj zarządzania, Powierzchnia.
- Special-case display: when `WLAD` is `"Wykonywanie zadań zarządcy dróg publicznych"`, rendered as two lines (main text + "(Zarząd Dróg Miejskich)" sub-label).
- ZDM case in Zarządca field: when concession data is absent but `WLAD` indicates ZDM, show "Prawdopodobnie Zarząd Dróg Miejskich" with a note about missing GEOPOZ data.
- Fixed: `<br>` before secondary `<span>` in Zarządca field was missing in one rendering path.

### 2026-04-24

**Bug fixes**

- Fixed a persistent race condition with the circle marker: introduced a `requestToken` counter in `index.html` so that only the response matching the most recent tap is rendered; stale responses from earlier taps are silently discarded.
- Fixed invisible parcel border on tap — triaged through three successive root causes:
  1. Wrong WFS layer name: `dzialki_szraw_sql` → `egib:dzialki_ewidencyjne_sql`.
  2. CRS axis order mismatch: replaced `EPSG:4326` with `CRS:84` in the WFS `GetFeature` request so longitude/latitude are sent in the correct order.
  3. Switched from a bounding-box filter to a `SRID=4326;POINT(lon lat)` spatial `INTERSECTS` predicate, which correctly identifies the single clicked parcel rather than all parcels in the bbox.

**UI / Visual changes**

- Reduced color fill layer opacity from 0.45 to 0.32 (`index.html`, Leaflet tile layer options).
- Added `egib:dzialki_ewidencyjne_sql` as a dedicated WMS boundary layer at 0.4 opacity so parcel outlines are always visible even before a tap.
- Selected parcel polygon border color changed to blue, weight reduced; both circle marker and selected parcel border now use the unified `#4299e1` / `#2b6cb0` palette so the two visual elements are clearly related.
- `Zarządca` field: added conditional rendering for the ZDM + "brak informacji" case — shows a `<br>` line break before the sub-label so the secondary text renders on its own line in all rendering paths.
- Narrative heading "Tą działką zarządza" (`index.html`, `renderScenario()`) added above the manager name in the result panel.
- App title updated to include `(wersja testowa)` rendered in `#999` grey via an inline `<span>`.
- "Masz pomysł?" feedback line moved below the H1 heading and converted to a `mailto:` anchor link.

**Architecture refactor**

- Extracted `geopoz_client.py`: a dedicated data-access layer that wraps all outbound calls to GEOPOZ GeoServer (WMS `GetFeatureInfo`, WFS `GetFeature`) and the WMSEGIB portal (`KLASOUZYTKI_EGIB` lookup). `server.py` no longer contains any HTTP calls to external APIs.
- Extracted `parcel_analyzer.py`: a 16-branch scenario engine. Introduced `ScenarioType` enum (one variant per panel scenario) and `ParcelScenario` dataclass (holds `scenario_type`, `manager`, `secondary_label`, `rodzaj`, `sygnatura`, `powierzchnia`). The `analyze()` function maps raw GEOPOZ attributes to a `ParcelScenario`; `server.py` calls `analyze()` and serialises the result to JSON.
- `server.py` `/dzialka` route slimmed to: fetch raw data via `geopoz_client`, call `parcel_analyzer.analyze()`, return the resulting dataclass as JSON. All branching logic removed from the route handler.
- `buildCard()` in `index.html` replaced with `renderScenario()`, which reads the `scenario_type` field from the API response and delegates to a per-scenario render function instead of containing inline conditional chains.

**Analytics**

- Added `_log_dzialka()` in `server.py`: logs every `/dzialka` request to `analytics.log` with ISO timestamp, parcel ID, client IP (read from `X-Forwarded-For` header, falling back to `request.remote_addr`), and user-agent string.
- `analytics.log` added to `.gitignore` so production log data is never committed.

**Performance**

- Replaced `pyproj` with a pure-Python EPSG:2177 → WGS 84 coordinate transform (`geopoz_client.py`) to eliminate the compiled `pyproj` / `PROJ` dependency. Render build time dropped from ~3 min to under 30 s.

**Documentation**

- `ROADMAP.md` created with Changelog and Planned features sections.
- `.gitignore` updated: added `analytics.log` and sensitive planning docs (`PRODUCTION_PLAN.md`, `POZNAN-API-RESEARCH.md`, `ZARZADCA-LOGIC.md`).

### 2026-04-27

**v1.1.5 — Fix: OZN_DZ leading-zero normalization**

- GEOPOZ returns parcel numbers with leading zeros per segment (e.g. `03/06/1/7`), while the TZ CSV stores them without (e.g. `3/06/1/7`). This caused silent lookup misses — including the confirmed ZZM parcel `03/06/1/7` (Park Sołacki).
- Added `_normalize_ozn_dz()` in `geopoz_client.py`: strips leading zeros from each `/`-separated segment. Applied at load time in both loaders and at lookup time in both getters.

**v1.1.4 — Fix: TZ CSV checked before GEOPOZ inference (same session)**

- TZ CSV (trwały zarząd) is now checked as **branch 3** in the decision tree — immediately after the two XLSX powierzenia branches and before all GEOPOZ-inferred logic.
- Previously, TZ data was only consulted deep inside `SKARB_TZ`/`CITY_TZ` branches, meaning it was silently ignored whenever GEOPOZ returned `Zarządzanie zasobem`, `Gospodarowanie zasobem`, an empty WLAD, or anything other than the literal string `Trwały zarząd`. Users got "brak informacji" or wrong manager names for ~2500 parcels.
- Now: if a parcel's `OZN_DZ` matches the TZ CSV, the confirmed unit name is shown regardless of what GEOPOZ sends back for WLAD.

**v1.1.3 — Data sources: trwały zarząd + reorganization**

- Added second static data source: `data/trwaly-zarzad-YYYY-MM-DD.csv` (report `reportId=2000092` from sipaplikacje.geopoz.poznan.pl) — 2616 parcels in permanent management (trwały zarząd), keyed by `Pełny numer działki`.
- Moved `powierzenia-*.xlsx` from project root into new `data/` subdirectory alongside the new CSV.
- Added `data/sources.md` — one-stop reference describing each file, required columns, report URL, and update instructions.
- Updated `geopoz_client.py`: `_load_trwaly_zarzad()` reads the CSV at startup into an in-memory dict; `get_trwaly_zarzad(ozn_dz)` and `get_trwaly_zarzad_meta()` added.
- Enriched `SKARB_TZ` and `CITY_TZ` scenario branches: when TZ data is available for the clicked parcel, the specific managing unit name is now shown with `confidence='confirmed'` instead of the generic "W razie pytań zwróć się do WGN" note.
- Bumped version to v1.1.3.

---

## Planned features / Ideas

### Private analytics system

Track every parcel lookup with: user IP address, reverse-geocoded geolocation, timestamp, session identifier. Build an owner-only dashboard showing lookup volume over time (heatmaps per day / week / month / quarter / year). Add Poznań proximity detection — flag lookups originating from outside the Poznań metro area, with the option to rate-limit or eventually block remote IPs to prevent scraping by external parties.

### Production deployment

Move the app off Render's free tier (which spins down after 15 minutes of inactivity and has no SLA) onto a proper production environment with persistent uptime, a custom domain, HTTPS, and a caching layer to reduce outbound calls to GEOPOZ and avoid IP-based rate limiting. See `PRODUCTION_PLAN.md` for the full step-by-step plan.

### ZZM / green areas auto-detection via spatial intersection

Automatically detect when a clicked parcel falls within a ZZM-managed park or green area, even when the parcel is absent from `powierzenia-YYYY-MM-DD.xlsx`.

**Approach:**
1. Fetch all ZZM park polygons from the Poznań city portal `class_objects` endpoint (`class_id=3338`) at app startup — stores 50 GeoJSON Point features (geometry only, no cadastral data currently linked in portal DB).
2. Alternatively, query GUGIK (`uldk.gugik.gov.pl`) for the clicked parcel's geometry, then do a spatial intersection against the ZZM park polygon set.
3. If the parcel centroid or outline intersects a ZZM park polygon → infer ZZM as manager (display with a note that this is inferred from spatial overlap, not a formal powierzenie record).

**Status of research (2026-04-23):**  
The Poznań city portal `object_parcel` endpoint returns empty features for all 50 ZZM parks — no cadastral linkage exists in the portal backend. The `class_objects` endpoint does return the park Point geometries. Full parcel polygon intersection would require GUGIK. See `POZNAN-API-RESEARCH.md` for complete API findings.

**Trigger case:** Parcel `03/06/1/7` — confirmed ZZM park, not in powierzenia XLSX. GUGIK ID: `306401_1.0306.1/7`.

**Estimated complexity:** medium-high. Requires GUGIK integration + polygon math (Turf.js or backend shapely).

---

### Auto-refresh data sources on a schedule

Both static data sources (`powierzenia` and `trwaly-zarzad`) are public reports available without authentication at `sipaplikacje.geopoz.poznan.pl/raporty/`. A `refresh_data.py` script could download the latest exports automatically and save them to `data/` with today's date, letting the app pick them up on the next restart.

**Approach:**
1. Use `requests` to GET each report URL with `?format=csv` / `?format=xlsx` query params (verify exact export params against the portal).
2. Save to `data/powierzenia-YYYY-MM-DD.xlsx` and `data/trwaly-zarzad-YYYY-MM-DD.csv`, deleting the previous file.
3. Optionally reload the in-memory dicts at runtime without a full server restart (hot-reload via a `/_reload` internal endpoint or a SIGUSR1 handler).
4. Run the script on a weekly cron (e.g. Render cron job, GitHub Actions scheduled workflow, or a simple `crontab` entry on a VPS).

**Status:** Not started. `data/sources.md` documents the report URLs so this can be wired up when needed.

**Estimated complexity:** low (script itself) to medium (hot-reload without restart).

---

### Circle-to-parcel border morphing animation

On parcel tap, animate the selection circle smoothly transitioning into the parcel's actual boundary outline. Uses flubber.js for SVG path interpolation between the circle marker and the GeoJSON polygon shape. Requires converting Leaflet's circleMarker from a `<circle>` SVG element to a `<path>`, projecting the GeoJSON polygon to screen coordinates, and cancelling the animation cleanly if the user taps another parcel mid-animation (hooks into the existing request token logic). Estimated complexity: medium (~1 day). Result would be a polished, app-like selection experience.

---

### Shareable parcel URLs — open question

Rozważam ukrywanie przycisku zamiast disabled dla działek bez zarządcy — odkładam decyzję na później.
