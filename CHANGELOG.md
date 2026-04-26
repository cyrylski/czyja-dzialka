# Changelog

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
