# Changelog

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
