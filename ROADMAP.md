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

---

## Planned features / Ideas

### Private analytics system

Track every parcel lookup with: user IP address, reverse-geocoded geolocation, timestamp, session identifier. Build an owner-only dashboard showing lookup volume over time (heatmaps per day / week / month / quarter / year). Add Poznań proximity detection — flag lookups originating from outside the Poznań metro area, with the option to rate-limit or eventually block remote IPs to prevent scraping by external parties.

### Production deployment

Move the app off Render's free tier (which spins down after 15 minutes of inactivity and has no SLA) onto a proper production environment with persistent uptime, a custom domain, HTTPS, and a caching layer to reduce outbound calls to GEOPOZ and avoid IP-based rate limiting. See `PRODUCTION_PLAN.md` for the full step-by-step plan.
