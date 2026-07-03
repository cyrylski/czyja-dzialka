# Decision Log — Czyja to działka?

Chronological record of significant architectural, product, and infrastructure decisions. Each entry documents what was decided, why, and what alternatives were considered or rejected.

---

## 2026-04-20 11:41 — Initial architecture: Flask + Leaflet, single-file frontend

**Decision:** Build as a minimal Flask backend serving a single `index.html` with Leaflet.js loaded from unpkg CDN. Deploy to Render.com free tier via `gunicorn` and `render.yaml`.

**Rationale:** The only server-side work is coordinate conversion (EPSG:4326 → EPSG:2177) and proxying two HTTP calls to GEOPOZ GeoServer. Flask is the lowest-friction choice for this workload in Python. A single HTML file avoids a build step entirely; Leaflet from CDN avoids bundling. Render free tier gives instant deployment with no infra to manage.

**Alternatives not taken:**
- Node/Express: no reason to leave Python given pyproj is needed.
- Full SPA framework (React/Vue): no interactivity beyond a map click + a card render; overkill.
- Serverless (Vercel/Lambda): coordinate conversion and outbound HTTP calls work fine in a persistent process; no benefit to serverless here.

---

## 2026-04-20 11:41–12:41 — Initial approach: SIPMAPY session scraping (then abandoned)

**Decision (initial):** Prototype (`geopoz-app/`) queried `sipmapy.geopoz.poznan.pl/sipportal/api/stateful/featureInfo` by fabricating a fake browser session: generated a UUID-based `__wc_user_name` cookie, initiated an ASP.NET session, sent JSON POSTs with spoofed `Referer` and `User-Agent` headers, and parsed HTML responses.

**Abandoned because:** This API is internal to GEOPOZ's own portal and is not documented for third-party use. Fabricating session cookies and spoofing headers is a concrete ToS violation and potentially a violation of Polish computer misuse law. When it was discovered that the same data is available from a publicly accessible OGC GeoServer endpoint at `wms2.geopoz.poznan.pl`, the session-scraping approach was dropped entirely.

**Decision (replacement):** Call the public GeoServer endpoint directly using standard OGC WMS `GetFeatureInfo` and WFS `GetFeature` requests. No cookies, no auth, no spoofed headers.

**Note:** The `geopoz-app/` prototype directory was left in the repo but must be purged from git history (via `git filter-repo`) before the repo is made public. See `TECHNICAL_AUDIT.md §5.8` and `PRODUCTION_PLAN.md §5`.

---

## 2026-04-20 12:45 — BBOX axis order for EPSG:2177: northing first, then easting

**Decision:** In WMS 1.3.0 requests against GEOPOZ GeoServer with `CRS=EPSG:2177`, the bounding box must be expressed as `northing_min,easting_min,northing_max,easting_max` — not easting/northing.

**Rationale:** WMS 1.3.0 respects the axis order defined in the CRS specification. EPSG:2177 (Polish national grid, zone 7) defines axes as northing (Y) first, easting (X) second. This is opposite to WGS84 (EPSG:4326) where longitude/easting comes first. Getting this wrong produces a bounding box that is geographically nonsensical, returning no features or features from the wrong location. Fixed after observing empty GetFeatureInfo responses despite correct coordinates.

---

## 2026-04-20 12:53 — Geolocation on load + 250 ms debounce for tap/double-tap disambiguation

**Decision:** On page load, request the browser's geolocation and center the map at zoom 16 on the user's position. Use a 250 ms timer on map click events: if a second click fires within 250 ms, the first click is treated as part of a double-click (zoom gesture) and no parcel lookup is triggered.

**Rationale:** Without centering on the user, the map opens on a default view that may not be relevant to them. Poznań is a specific city; a user who is physically there should see their surroundings immediately. The 250 ms debounce is necessary because Leaflet fires a `click` event for every click, including the first click of a double-click — without this guard, double-tapping to zoom in would also trigger a parcel lookup.

---

## 2026-04-20 13:43 — Powierzenia (road concession) data: in-memory dict loaded from XLSX at startup

**Decision:** At Flask startup, read `powierzenia-YYYY-MM-DD.xlsx` from the repo root into a Python dict keyed by parcel number (`OZN_DZ`). Hold in memory for the process lifetime. No database, no hot-reload.

**Rationale:** The data is small (hundreds of rows), read-only at runtime, and changes infrequently. Loading into a dict gives O(1) lookup with zero network dependency at query time. Using openpyxl keeps the dependency count low.

**Known limitations accepted:**
- Updating the data requires a full redeployment.
- No hot-reload endpoint.
- Stale data persists indefinitely until a new file is deployed.

**Future migration path:** Replace with a PostgreSQL table with an admin update endpoint. See `PRODUCTION_PLAN.md §4` and `ANALYTICS_PLAN.md §2`.

---

## 2026-04-20 13:49 — WMS background tile layer: `dzialki_szraw_sql`

**Decision:** Add GEOPOZ's `dzialki_szraw_sql` WMS layer as a semi-transparent Leaflet tile overlay on top of the OpenStreetMap base layer. This shows cadastral parcel outlines as a persistent background.

**Rationale:** Users need to see parcel boundaries before tapping, to know what they are tapping on. The WMS tile layer provides this context without any extra backend calls — tiles are fetched directly by the browser from GEOPOZ. The `szraw` layer is GEOPOZ's standard cadastral display layer.

---

## 2026-04-20 14:05–14:47 — Parcel outline on tap: WFS GetFeature with INTERSECTS spatial filter

**Decision:** On parcel tap, the backend makes a second call — WFS `GetFeature` against `egib:dzialki_ewidencyjne_sql` — using a `CQL_FILTER=INTERSECTS(SHAPE, SRID=4326;POINT(lon lat))` query to retrieve the clicked parcel's boundary geometry. The GeoJSON polygon is returned to the browser and rendered as a Leaflet overlay with a permanent tooltip showing `OZN_DZ`.

**Key details:**
- WMS layer (`dzialki_szraw_sql`) and WFS layer (`dzialki_ewidencyjne_sql`) are separate feature types in the same GeoServer workspace. The WMS layer carries attribute data; the WFS layer provides geometry. Both are needed.
- WFS request uses `SRSNAME=CRS:84` and the filter uses `SRID=4326` — GeoServer expects this even though the WMS uses EPSG:2177.
- Race condition handled via a `requestToken` integer: each click increments the token; a response whose token doesn't match the current value is discarded.

**Rationale for WFS vs. WMS:** WMS `GetFeatureInfo` returns attribute data in the GetFeatureInfo response but does not return the polygon geometry in a usable form for rendering. WFS `GetFeature` with a spatial filter is the correct OGC mechanism to retrieve geometries.

---

## 2026-04-20 15:08–15:16 — ZDM special-case rendering in Zarządca and Rodzaj zarządzania fields

**Decision:** Two special cases for the `WLAD` field value `"Wykonywanie zadań zarządcy dróg publicznych"`:

1. **Rodzaj zarządzania field:** Render as two lines: the full phrase on the first line, then `"(Zarząd Dróg Miejskich)"` as a sub-label.
2. **Zarządca field (fallback):** If no powierzenia XLSX match is found for the parcel, but `WLAD` is the ZDM indicator, show `"Prawdopodobnie Zarząd Dróg Miejskich"` with a parenthetical note `"(brak informacji w danych GEOPOZu)"` instead of the generic `"brak informacji"`.

**Rationale:** In Poznań's cadastral data, the value `"Wykonywanie zadań zarządcy dróg publicznych"` unambiguously means Zarząd Dróg Miejskich (ZDM) manages the road. However, ZDM is not consistently present in the powierzenia XLSX — the XLSX originates from a different system and has coverage gaps. Inferring the manager from the GEOPOZ `WLAD` field provides useful information for users even when the XLSX lookup fails, while the `"Prawdopodobnie"` qualifier and the source note prevent the inference from being mistaken for confirmed data.

---

## 2026-04-20 19:01 — Request logging added to `/dzialka` endpoint

**Decision:** Log every `/dzialka` request to stdout: timestamp, IP, lat/lon, `OZN_DZ` result. Later (commit `9b1b3d8`, 2026-04-21) extended to include IP geolocation via ip-api.com.

**Rationale:** No observability had existed until this point. Even basic `print()`-based logging to Render's log viewer is far better than nothing. Geolocation was added to flag lookups originating outside Poznań (potential scrapers or users forwarding the link to people elsewhere).

**Note:** This is a precursor to the full analytics system described in `ANALYTICS_PLAN.md`. The current implementation is stdout-only; data is lost on restart.

---

## 2026-04-21 11:17 — Full UI redesign: full-screen map with floating card; rename

**Decision:** Redesign the layout so the map fills the entire viewport and the info card floats over it. Rename the app from its working title to `"Czyja to działka?"` (whose parcel is this?).

**Rationale:** The previous layout split the screen between map and card, wasting map real estate on mobile. A floating card over a full-screen map is the standard mobile map app pattern (Maps, Google Maps). The rename makes the purpose of the app immediately clear to a new user.

---

## 2026-04-21 12:01–12:44 — Figma-based redesign: typography, layout, footer inside card

**Decision:** Implement a detailed visual redesign derived from a Figma prototype. Key structural changes: H1 heading and footer both live inside the card (previously outside); `Powierzchnia` moved to row 1 of the data grid; card has defined max-height with internal scroll.

**Rationale:** Having the title and data feedback in the same visual container makes the card self-contained and visually coherent — the heading and source attribution are properties of the card, not the page. Powierzchnia was moved to row 1 because it is the most spatially intuitive field and gives users a quick sense of parcel size before reading ownership data.

---

## 2026-04-21 14:23 — UX polish: spinner, selection circle, location pin, card height transition

**Decision:** Add a loading spinner shown while a parcel lookup is in flight; replace the plain click point with an animated selection circle (pulsing ring); add a location pin marker; animate the card height between collapsed and expanded states via CSS transitions.

**Rationale:** Without feedback, users cannot distinguish "the app is loading" from "nothing happened". The selection circle communicates that a tap was registered. The card height animation prevents a jarring layout jump when data arrives. These are the minimum affordances for a responsive, app-like feel on mobile.

---

## 2026-04-21 14:39–14:46 — Selection circle visual treatment: blue border weight 3, color-matched fill

**Decision (iterative):** After several attempts, the selected parcel polygon outline was settled at: blue stroke (`#3399CC`), weight 3, with fill color and opacity matching the selection circle marker. The background WMS tile layer opacity was reduced to make the selected polygon stand out.

**Rationale:** Earlier iterations used a black outline (too harsh, competed with the OSM basemap) and an unmatched fill (confusing visual disconnect between the tap circle and the polygon). Matching the circle and polygon colors creates a visual continuity — the polygon is clearly "the same thing" as the circle. Blue (`#3399CC`) is Leaflet's default selection color and is universally recognized as a selection indicator on maps.

---

## 2026-04-21 15:01 — Circle-to-polygon transition: CSS fade animation (not flubber morphing)

**Decision:** Animate the selection circle transitioning to the parcel polygon using CSS opacity fades (circle fades out, polygon fades in) rather than SVG path morphing via flubber.js.

**Rationale:** Flubber.js SVG morphing requires converting Leaflet's `circleMarker` (rendered as `<circle>`) to a `<path>`, projecting GeoJSON coordinates to screen space, and hooking into the WFS response to cancel in-flight animations. This is non-trivial with Leaflet's internal SVG renderer and estimated at ~1 day of work. A CSS fade achieves the same perceptual result — the user sees a smooth transition from "selection point" to "parcel outline" — with a few lines of code. The more complex flubber approach was documented in `ROADMAP.md` as a future enhancement.

---

## 2026-04-21 15:03 — Add `"(wersja testowa)"` subtitle

**Decision:** Display `"(wersja testowa)"` below the main H1 heading.

**Rationale:** The app uses live GEOPOZ data and is deployed publicly, but the data pipeline has known gaps (multi-entrust parcels silently drop entries, ZDM inference is probabilistic). The subtitle sets user expectations and protects against the tool being cited as authoritative during the testing phase.

---

## 2026-04-21 19:51 — Minimize button on card

**Decision:** Add a chevron-style minimize button to the card header that collapses the card body while keeping the header visible.

**Rationale:** On mobile, the card can obscure a significant portion of the map after a parcel lookup. Users who want to browse the map after seeing the data need a way to reduce the card without losing their place. Collapsing to the header (rather than fully hiding the card) keeps the parcel context visible.

---

## 2026-04-23 14:00 — Panel redesign: manager-first information hierarchy, scenario-aware layouts

**Commit:** `e6766a4` — "feat: add panel redesign mockup and scenario documentation"

**Files added:** `scenarios-preview.html`, `panel-scenarios.md`, `Scenario A.svg`, `Scenario C1.svg`, `Scenario C2.svg`, `Scenario D.svg`

**Decision:** Redesign the info panel around a new information hierarchy: the managing unit (Zarządca) is promoted to a large hero element at the top of the card under the label "To działką zarządza", replacing the previous flat table-of-fields layout. Each of the five data scenarios (A, B, C1, C2, D) gets a distinct card treatment rather than a single generic template.

**Key design decisions within this redesign:**

1. **Manager name as visual anchor** — The unit name (e.g. "Zarząd Dróg Miejskich") is rendered at 22px bold in brand blue. This is the single most important piece of information for the app's primary users (city officials determining who to contact about a parcel); it should be readable in one glance without scanning a table.

2. **"Numer powierzenia" directly under the hero name** — The concession signature appears immediately below the unit name, before the horizontal divider that separates the hero zone from the data grid. Previous layout buried it among four equal-weight fields.

3. **Scenario C2 (non-city owner): orange hero + contextual routing note** — When the owner is not Miasto Poznań (e.g. Skarb Państwa), the hero name renders in amber/orange instead of blue, and a contextual note reads: "Miasto nie jest jej właścicielem. W sprawach dotyczących tej działki możesz zwrócić się do Wydziału Gospodarki Nieruchomościami Urzędu Miasta Poznania." The color change provides an immediate visual signal that this parcel is outside the city's direct responsibility; the note routes the user to the correct contact point.

4. **Scenario D (multi-entrust): `units-grid` replaces single entry** — Previously a known silent data-loss bug: when multiple powierzenia rows exist for one `OZN_DZ`, only the last loaded row was displayed. The redesign replaces the single-hero zone with a wrapping flex grid (`units-grid`) where each managing unit gets its own name + "Numer powierzenia" entry. This is the first concrete design resolution of the Scenario D bug documented in `panel-scenarios.md`.

5. **Contextual note for Scenario C1** — When ZDM is inferred from the `WLAD` field (not from the XLSX), a clarifying sentence appears: "Działka ma innego właściciela, ale ZDM odpowiada za utrzymanie pasa drogowego." This replaces the previous "(brak informacji w danych GEOPOZu)" parenthetical, which was technically accurate but unhelpful to a non-technical user.

6. **Field renaming:** "Sygnatura powierzenia" → "Numer powierzenia"; "Rodzaj zarządzania" → "Rodzaj powierzenia". The new terms are more consistent with the vocabulary used in actual powierzenia documents.

7. **Footer outside the card body** — Attribution footer (`Wszystkie dane pochodzą z GEOPOZu · Zaktualizowano · Autor`) is rendered below the card with flat corners and a light grey background, visually separate from the card content. This keeps the card body focused on data and treats attribution as structural chrome rather than content.

8. **Data grid** — Numer działki, Właściciel, and Powierzchnia are displayed in a single horizontal row with 10px micro-labels. Właściciel is omitted from the Scenario C2 grid (it would be redundant with the hero name). This compresses the secondary data to free vertical space for the hero zone.

**Status of this redesign:** HTML/SVG mockup only — `scenarios-preview.html` is a static design artefact, not connected to the Flask backend. The next step is implementing this layout in `index.html` and updating the backend response schema to return a list of managers (for Scenario D support) rather than a single `pow_opis`/`pow_syg` pair.

---

## Planned decisions (not yet implemented)

### Infrastructure: Hetzner CX22 VPS (vs. Render paid tier)

**Status:** Chosen in `PRODUCTION_PLAN.md`, not yet implemented.

**Decision:** Move production deployment from Render free tier to a Hetzner CX22 VPS (~€4/month).

**Key reason:** A dedicated IP address. All backend requests to GEOPOZ GeoServer originate from a single IP. On Render's shared infrastructure, that IP is shared with other tenants; unusual traffic from any of them could trigger a GEOPOZ ban that affects this app. A VPS gives a dedicated egress IP, meaning any IP-level relationship with GEOPOZ is entirely under this app's control. The VPS also enables persistent disk (Redis for caching, PostgreSQL for analytics) without add-on costs.

**Alternatives considered:** Render Starter ($7/mo) — eliminates cold starts and is zero-ops, but shared IP pool remains a concern, and Redis + Postgres add-ons bring total cost to ~$24/mo.

### Analytics: Supabase (PostgreSQL) as event store

**Status:** Chosen in `ANALYTICS_PLAN.md`, not yet implemented.

**Decision:** Use Supabase free tier (managed PostgreSQL) as the analytics event store.

**Key reason:** Render's free tier has an ephemeral filesystem — SQLite on disk is lost on every deploy or restart. Supabase provides persistent storage with a free-tier SQL dashboard for ad-hoc queries, using a standard `psycopg2` interface. A single `events` table covers all analytics needs at current scale.

**Alternatives considered:** SQLite on disk (data loss on restart — only viable for debugging); Turso (libsql, less mature Python SDK); Neon (serverless Postgres, cold starts on first query after idle).

### Multi-entrust parcels: design resolved, backend not yet updated

**Status:** UI design resolved in the 2026-04-23 panel redesign mockup (`scenarios-preview.html`). Backend fix not yet implemented.

**Problem:** The powierzenia XLSX can have multiple rows for the same `OZN_DZ` (multiple concession holders). The current dict keyed on `OZN_DZ` silently overwrites earlier entries with later ones, losing all but the last concession record.

**Design resolution (2026-04-23):** The `units-grid` layout in the redesigned card stacks all managing units, each with their own name and signature. See the 2026-04-23 entry above.

**Remaining backend work:** Change the XLSX loading to store a list of matches per `OZN_DZ` instead of a single record. Update the `/dzialka` JSON response to return an array of `{opis, sygnatura}` objects instead of scalar `pow_opis`/`pow_syg` fields.

---

## 2026-05-08 — Replace static management files with live gospodarka_nieruchomościami API

**Decision:** Remove static `powierzenia-*.xlsx` / `trwaly-zarzad-*.csv` as the primary source for `trwały zarząd` and `powierzenia` data. Replace with live per-request queries to the GEOPOZ `gospodarka_nieruchomościami` WMS (`GetFeatureInfo` on the `Trwały_zarząd` and `Powierzenia` layers).

**Rationale:** The static files required manual downloads after every municipal registry update. Discovery that `https://sipuslugiogc1.geopoz.poznan.pl/gospodarka_nieruchomosciami/Service.svc/get` exposes both layers as queryable WMS with `GetFeatureInfo` support (confirmed via `GetCapabilities` and live tests) makes the manual workflow unnecessary. The live API returns exactly the fields needed (`Zarządca`, `Powierzono`, `Numer działki`).

**Trade-off accepted — sygnatura loss:** The `Powierzenia` WMS layer does not return the concession reference number (`SYGNATURA`). The XLSX report does. Resolution: XLSX file is kept as an optional sygnatura enrichment source — if present in `data/`, `_overlay_xlsx_sygnatura()` copies matching sygnatura values onto API entries; if absent, the app works fully with `sygnatura=None`.

**Alternatives not taken:**
- Keep XLSX/CSV as primary, API as fallback: would require maintaining the manual refresh workflow indefinitely.
- Fetch management data as a separate server endpoint: no UX benefit; adds round-trip latency from the frontend.
- Cache management responses in Redis/memcached: out of scope at current scale; management zones change rarely.

**Key technical findings (from POZNAN-API-RESEARCH.md):**
- `CQL_FILTER` on the `WFS_SIP_EWIDENCJA` endpoint is silently ignored — OGC XML `FILTER` is required for EGiB parcel lookups.
- `text/plain` as `INFO_FORMAT` is rejected; use `application/geo+json`.
- EPSG:3857 bbox coordinate origin confirmed: service extent starts at Y≈6,849,028, not the expected ~6,837,000 — off-by-12km was causing empty responses during testing.
- `OID` field is shared between the management WMS and the EGiB WFS for the same parcel.

---

## 2026-05-10 — XLSX fallback when live Powierzenia WMS returns nothing (v1.6.2)

**Decision:** When the live `Powierzenia` WMS GetFeatureInfo returns zero entries for a parcel, fall back to entries from `powierzenia-*.xlsx` (authored by WGN) for that parcel. The XLSX retains its sygnatura-overlay role when the live API does return entries.

**Problem:** The 2026-05-08 migration (v1.5.0) assumed the live `Powierzenia` layer covers every parcel the XLSX has. It doesn't — the layer is sparser. Parcels like `04/13/4/436` and `04/13/4/438` (and many other ZKZL-managed plots in the same registry block) are absent from the live layer; the XLSX records them with `OPIS = "Zarząd Komunalnych Zasobów Lokalowych"` and a concrete sygnatura. With the old logic, these parcels had `pow_entries: []` and fell through to branch `CITY_ZASOB` → WGN, despite the XLSX having authoritative data. User confirmed they are 100 % managed by ZKZL.

**Rationale:** The "Alternatives not taken: Keep XLSX/CSV as primary" line in the 2026-05-08 entry rejected the manual-refresh burden, but did not anticipate silent data loss from the live layer's gaps. A conservative one-way fallback (XLSX only when API returns 0 entries) restores the missing data without overriding any live API result. Stale-XLSX risk is bounded: if the live layer ever starts reporting a different manager for a parcel that's also in the XLSX, the live answer wins.

**Code:** `_xlsx_powierzenia_fallback()` in `geopoz_client.py`. Used in the `_pow` thread inside `get_parcel_info`.

**Trade-off accepted:** XLSX entries are still as stale as the file date. The "Zaktualizowano" line in the panel footer continues to reflect that date, so users can judge.

---

## 2026-07-03 — Periodic email digest replaces shutdown-only flush (v1.6.4)

**Decision:** Flush the in-memory analytics buffer to email on a timer (every 15 min while events are pending, immediately at 800 events) from a daemon thread, keeping the `atexit` flush only as a shutdown backstop. Make configuration state loud at startup, surface SMTP errors through a token-gated `/api/log_status` diagnostics endpoint, and set `kill_signal = 'SIGTERM'` / `kill_timeout = '30s'` in `fly.toml`.

**Problem:** No digest email ever arrived, so there was zero visibility into app usage. The v1.3.0 design assumed Fly.io idle-stop gives the process a clean, unhurried exit ("gunicorn lets the worker exit cleanly, `atexit` fires"). In reality, with no `kill_signal`/`kill_timeout` in `fly.toml`, Fly sends **SIGINT** (which gunicorn treats as *quick* shutdown, not graceful) and **SIGKILLs the VM after 5 s** — while the flush's own SMTP timeout is 10 s and the full Gmail handshake (DNS + TCP + STARTTLS + AUTH + DATA) must also fit in that window on a 256 MB shared-CPU machine. The flush lost that race on every spindown. Compounding it, every failure was invisible: missing `LOG_EMAIL_*` secrets (the app migrated Render → Fly on 2026-04-27; secrets do not migrate) silently no-op the flush, and SMTP exceptions were logged at WARNING to a machine already dying. A crash or OOM (SIGKILL) also loses the entire buffer with shutdown-only flushing, by design.

**Rationale:** Delivery must not depend on the single most fragile moment of the machine lifecycle. A periodic flush bounds data-at-risk to one interval, works regardless of how the machine dies, and — throttled to at most 4 sends/hour, only when events exist — stays far below Gmail's ~500/day limit that motivated removing per-lookup sends in v1.3.0. Failed sends re-queue the events at the front of the buffer for the next cycle. The diagnostics endpoint exists because the pipeline had **no observable state at all**: `GET /api/log_status` (with `LOG_STATUS_TOKEN`) reports config/pending/last-error, `POST` forces a flush with a synthetic test event so end-to-end delivery is verifiable in seconds instead of waiting for organic traffic and spindown.

**Alternatives not taken:**
- External store (Supabase per `ANALYTICS_PLAN.md`): still the right long-term answer, but a bigger dependency; the email digest is the current contract and can be made reliable cheaply.
- Fly.io metrics / log shipper (`fly logs` → external sink): observability of stdout already exists via `flyctl logs`; the requirement here is push notification of usage without running extra infrastructure.
- Per-event send: rejected in v1.3.0 for quota/DoS reasons; unchanged.
- Only fixing `fly.toml` (SIGTERM + 30 s): necessary but not sufficient — still loses the buffer on crash/OOM and still silent when misconfigured.

**Operational note:** if no email arrives after deploy, `flyctl logs` now shows either `email digest armed -> …` or `email digest DISABLED — missing env vars: …` at boot; `fly secrets list` should show `LOG_EMAIL_FROM`, `LOG_EMAIL_PASSWORD` (a Gmail **app password** — regular passwords are rejected by Gmail SMTP), `LOG_EMAIL_TO`, and optionally `LOG_STATUS_TOKEN`. `POST /api/log_status` with the token returns the exact SMTP error if sending fails.
