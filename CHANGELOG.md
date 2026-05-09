# Changelog

## v1.6.1 — 2026-05-09

### Added
- Fixed beta-notice bar at the bottom of the panel: blue accent background, white text, two lines (bold disclaimer + mailto contact link in a lighter tint). Replaces the inline footer contact line.

### Changed
- `.panel-footer` trimmed: removed duplicate "Widzisz błąd?" contact row and the now-redundant `·` separator.
- Introduced `--color-accent` and `--color-accent-light` CSS custom properties in `index.html` as the start of a proper variable system.

---

## v1.6.0 — 2026-05-08

### Added
- Multi-point management zone sampling: `_fetch_powierzenia_live()` and `_fetch_trwaly_zarzad()` now sample **9 points in a 3×3 grid** (inset 10 % from each bbox edge) rather than a single centroid pixel. Near-corner points catch edge-confined zones (e.g. the ZDM road strip in the SE corner of `04/16/93/11`) that centroid-only queries miss entirely. Parcels with multiple management zones now return all managers in `pow_entries`/`tz_entries`.
- `_bbox_epsg3857_from_geometry()` — converts the WFS GeoJSON polygon to an EPSG:3857 bounding box used for sample point placement.
- `_sample_points_for_bbox()` — generates the 9-point 3×3 grid from the bbox (rows from top-left to bottom-right, ys reversed so row 0 = north).
- `_mgmt_query_point()` — single-point GetFeatureInfo helper shared by both fetchers.
- Management zone WMS overlay in the Leaflet map: when a parcel with `pow_entries` or `tz_entries` is selected, a semi-transparent `Powierzenia`/`Trwały_zarząd` WMS layer (opacity 0.55) is added to the map, showing colour-coded management zones. The overlay is removed when the selection changes or is cleared.

### Changed
- `_fetch_trwaly_zarzad()` and `_fetch_powierzenia_live()` accept an optional `bbox_3857` parameter; fall back to single-centroid query when absent.
- In `get_parcel_info()`, `_tz` and `_pow` threads now wait on a `threading.Event` set by `_wfs` after the geometry is fetched, so management fetchers can use the parcel bbox. All 4 threads still start concurrently; management fetchers block only until WFS resolves (typically < 400 ms).
- BBOX margin per sample point reduced from 500 m to 200 m (tighter, matching the ~100 m scale of management zone features).

### Known limitation
- Parcels with a city-owned interior not covered by any Powierzenia or Trwały zarząd record (e.g. the uncoloured interior zone of `04/16/93/11`) are de facto managed by **WGN (Wydział Gospodarowania Nieruchomościami)** — the city's residual direct manager for unentrusted properties. This is user-reported and cannot be confirmed via any current API; no Powierzenia/TZ entry exists for such areas by design. If a WGN data export becomes available it can be integrated via the existing `_overlay_xlsx_sygnatura` pattern.

### Research
- Confirmed via GEOPOZ SIP portal browser inspection that management zone vector geometries are **not available via any API** — the WMS renders colored polygons server-side as PNG tiles; GetFeatureInfo returns attributes only. See `POZNAN-API-RESEARCH.md` for the full investigation notes.

---

## v1.5.0 — 2026-05-08

### Changed
- Management data (`trwały zarząd`, `powierzenia`) now sourced from the live GEOPOZ `gospodarka_nieruchomościami` WMS API instead of static XLSX/CSV files. Both management queries run concurrently with the existing WFS geometry and klasouzytki fetches — no added latency.
- `PowierzenieEntry.sygnatura` is now `Optional[str]` (defaults to `None` when sourced from the API). The XLSX file, if present in `data/`, is used only to overlay sygnatura onto matching API entries.
- `ParcelAttributes` now carries `pow_entries` and `tz_entries` directly; `server.py` no longer performs separate dict lookups after the parcel fetch.

### Added
- `_fetch_trwaly_zarzad(lat, lon, ozn_dz)` — live `GetFeatureInfo` against the `Trwały_zarząd` WMS layer; matches by `Numer działki`, maps `Zarządca` → `TrwalyZarzadEntry.jednostka`
- `_fetch_powierzenia_live(lat, lon, ozn_dz)` — live `GetFeatureInfo` against the `Powierzenia` layer; maps `Powierzono` → `PowierzenieEntry.opis`
- `_overlay_xlsx_sygnatura()` — enriches API `pow_entries` with sygnatura values from XLSX when names match; no-op if XLSX is absent
- `_coords_to_epsg3857()` — WGS84 → Web Mercator helper for the management WMS BBOX

### Removed
- Public `get_powierzenia(ozn_dz)` and `get_trwaly_zarzad(ozn_dz)` dict-lookup functions (no longer called; XLSX/CSV used only for sygnatura overlay and footer metadata)

### Infrastructure
- `data/powierzenia-*.xlsx` and `data/trwaly-zarzad-*.csv` are now optional. App works fully without them; XLSX presence adds sygnatura values; CSV metadata (date, count) still shown in footer if file exists.

---

## v1.4.0 — 2026-05-08

### Changed
- Split `ZDM_OTHER` into two scenarios: `ZDM_SKARB` (Skarb Państwa road parcels — "probably ZDM") and `ZDM_PRIVATE` (private owner road parcels — "uncertain, confirm with WGN")
- Fixed `_is_roads()` to handle multi-value `KLASOUZYTKI_EGIB` strings (e.g. `'N,RIVb,RV,dr'`) — previously only exact `'dr'` matched; city-owned road parcels with mixed land-use classifications fell through to UNKNOWN

### Added
- `ZDM_SKARB` scenario: contextual note names GDDKiA/ZDW as possible alternative managers for state-owned road parcels within city limits
- `ZDM_PRIVATE` scenario: honest "uncertain" messaging directing users to WGN for private road parcels

---

## v1.3.0 — 2026-05-07

### Security (pre-public-release P0)
- Wired up Flask-Limiter (already in requirements but never imported): 30/min;600/day on `/dzialka` and `/api/dzialka_by_ozn`, 10/min;200/day on `/api/log_share`, app-wide default 200/min;5000/day. Static and SPA routes exempt.
- Added same-origin guard on `POST /api/log_share` so third-party pages can no longer drive victim browsers into spamming the endpoint (returns 403 on missing or foreign `Origin`/`Referer`).
- Removed per-lookup Gmail SMTP send and the synchronous `ip-api.com` GET that ran on every parcel tap — both would have been exhausted within minutes of public traffic.
- Added `ProxyFix` so Flask sees the real client IP and scheme behind Fly.io's TLS terminator (also keys Flask-Limiter correctly).
- Mask IPv4 last octet / IPv6 lower 64 bits before logging — partial GDPR fix.

### Server
- Replaced file-based `analytics.log` writes (lossy on Fly.io's ephemeral disk with `min_machines=0`) with structured stdout logging via the `analytics` logger; Fly.io captures it and `flyctl logs` streams it.
- Added in-memory event buffer (deque, capped at 1000) and graceful-shutdown email digest: on machine spindown gunicorn lets the worker exit cleanly, `atexit` fires, and a single SMTP message is sent containing all events accumulated during the session. Reuses existing `LOG_EMAIL_FROM`/`LOG_EMAIL_PASSWORD`/`LOG_EMAIL_TO` env vars; no-op if any is missing or the buffer is empty.

### Docs
- Added "Pre-public-release security review" section to `ROADMAP.md` documenting the full P0/P1/P2 risk register, with file:line references, fix outlines, and scope notes (e.g. that `data/*.xlsx`/`*.csv` are public Poznań cadastre exports and safe to ship).

---

## v1.2.0 — 2026-05-07

### Added
- Share button above the panel (always visible) — uses Web Share API on mobile, copies the link to clipboard with a toast confirmation on desktop
- Shareable parcel URLs in the form `/dzialka/<obreb>-<dz>-<podz1>-<podz2>` (e.g. `/dzialka/3-6-1-7`); slug is the canonical OZN_DZ identifier with `/` replaced by `-`
- Direct entry from a shared link: app reads the slug, fetches parcel data via the new `/api/dzialka_by_ozn` endpoint, zooms to the parcel and opens the panel — same UX as a manual map click
- Toast notification "Użyty adres działki jest niepoprawny" when the slug doesn't resolve to a real parcel; map recentres on Poznań
- `pushState` on every map click so the browser URL stays in sync with the selected parcel and the back button steps through history

### Changed
- `_log_dzialka` now takes a `source` parameter (`'map'` or `'share'`) and prefixes both the analytics log entry and the email subject (`[działka] map- 3/6/1/7` vs `[działka] share- 3/6/1/7`)
- Frontend deduplicates share-button events per session: clicking "Udostępnij" again for the same parcel skips the backend log/email round-trip
- Geolocation prompt is suppressed when the app loads with a `/dzialka/<slug>` URL so the deeplinked parcel stays in view

### Server
- `/dzialka/<slug>` route serves `index.html` so SPA deeplinks survive a hard reload on Fly.dev
- New endpoints: `/api/dzialka_by_ozn?ozn=<id>` (lookup by identifier) and `POST /api/log_share` (share-button telemetry)
- New `geopoz_client.get_parcel_info_by_ozn()` — WFS GetFeature on `dzialki_szraw_sql` with a CQL filter that tolerates GEOPOZ's leading-zero formatting variants

---

## v1.1.2 — 2026-04-26

### Added
- Base map layer toggle: switch between OSM contour map and Esri satellite imagery

---

## v1.1.1 — 2026-04-26

### Fixed
- Removed misleading references to ekw.ms.gov.pl and ekrs.ms.gov.pl from all private ownership scenarios — neither can be searched by parcel number; company names are not exposed in EGIB (confirmed via UODO/GDPR ruling); KW numbers are not publicly searchable by parcel identifier
- Updated contextual notes for osoba fizyczna, spółka krajowa, spółka zagraniczna, and co-owner branches to honestly state data is not available in public registries

---

## v1.1.0 — 2026-04-26

### Added
- Expanded private ownership scenarios: 8 sub-branches covering wspólnoty mieszkaniowe, prawo związane z lokalem, współwłasność, spółki zagraniczne, spółki krajowe, powiaty, stowarzyszenia, osoby fizyczne
- Polish contextual notes with legal basis and actionable links for each private scenario
- Fly.io deployment with GitHub Actions auto-deploy on push to main
- App version displayed in panel footer

### Changed
- Refactored ownership logic into dedicated `parcel_analyzer.py`
- Refactored GEOPOZ API calls into dedicated `geopoz_client.py`
- Updated copy strings across all scenarios (removed parentheses, added BIP links)

---

## v1.0.0 — 2026-04-20

### Added
- Interactive map of Poznań parcels (Leaflet + GEOPOZ WMS)
- Tap-to-lookup: identifies parcel owner/manager from EGIB register
- City entity branches: ZDM, ZZM, ZUK, ZGiKM Geopoz, Zarząd Dróg, schools, churches, county, district administration
- XLSX powierzenia lookup for city-managed parcels
- Panel with hero zone, data grid, collapsible UI
- Analytics logging with email notifications
- Geolocation on app start
