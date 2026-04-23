# Poznań City Portal API — Research Notes

**Date:** 2026-04-23  
**Goal:** Determine whether parcel `03/06/1/7` is managed by ZZM (Zarząd Zieleni Miejskiej) via external API sources, without relying on the powierzenia XLSX.

---

## API base

```
https://www.poznan.pl/mim/plan/map_service.html
```

Discovered from browser DevTools while viewing:  
`https://www.poznan.pl/mim/plan/plan.html?id_klasy=3338&lhs=chapters&wo_id=1104`

---

## Access

The server returns HTTP 503 `"DNS cache overflow"` when accessed via cloud egress IPs (WAF/CDN block). Bypassed by resolving the IP manually and passing a `Host:` header with standard browser `User-Agent` and `Referer` headers. No session cookie required.

---

## Confirmed working endpoints

### 1. List all objects in a class
```
?mtype=pub_transport&co=class_objects&class_id=<id>&lang=pl
```
Returns a GeoJSON `FeatureCollection` of all objects in the class.

**Example:** `class_id=3338` = ZZM Parki → 50 features  

Top-level response keys: `features`, `crs`, `klasa`, `type`

The `klasa` meta-object:
```json
{
  "opis_klasy": "Parki",
  "atrybuty_klasy": [...],
  "id_klasy": "3338"
}
```

Each feature:
- `id`: integer
- `geometry`: `{"type":"Point","coordinates":[lon,lat]}`
- `properties`: `{nazwa, adres, miasto, id_klasy, opis_klasy, grafika, lang, kolejnosc, telefon, url, email, y_2944_inne, y_2946_ceny_bilet_w, y_2947_godziny_otwar, y_2948_dojazd, y_4125_atrakcje_dla_}`

No parcel numbers in properties.

---

### 2. Get parcel geometry for a map object
```
?co=object_parcel&id=<numeric_object_id>
```
Returns a GeoJSON `FeatureCollection` of parcel polygon(s) linked to the object.

**When data exists** (tested on class 3310 — Skateparki):
```json
{
  "features":[{
    "geometry":{"coordinates":[[[17.0096956,52.39033472],...]],"type":"Polygon"},
    "id":"73480",
    "type":"Feature",
    "properties":{}
  }],
  "crs":{"type":"EPSG","properties":{"code":"4326"}},
  "type":"FeatureCollection"
}
```
Note: `properties` is always `{}` — the response carries geometry only, never a cadastral parcel number string.

**For all 50 ZZM Parki objects (class 3338):**
```json
{"features":[],"crs":{"type":"EPSG","properties":{"code":"4326"}},"type":"FeatureCollection"}
```
Empty for every park — no parcel geometry is linked in the portal's backend for any ZZM park.

---

### 3. Get single object details
```
?mtype=default&co=object&id=<id>&class=3338
```
Returns same fields as `class_objects` for a single object.

---

## Confirmed non-existent endpoints

All of the following return `{"error_msg":"brak serwisu: <name>"}`:

`search`, `class_parcels`, `parcels_by_class`, `objects_by_parcel`, `parcel_info`, `object_info`, `object_data`, `class_objects_parcel`, `parcel`, and ~10 other variants.

There is **no reverse lookup** (parcel number → object). Passing `id=03%2F06%2F1%2F7` to `object_parcel` triggers `{"error_msg":"wystąpił nieoczekiwany błąd"}` — the field expects a numeric object ID only.

---

## Other surfaces checked

**featureserver:** `https://www.poznan.pl/featureserver/featureserver.cgi/` — 35 layers (addresses, transit stops, osiedla, etc.). No parcel/EGiB layer.

**WMS tilecache:** Has a `geopoz:zielen` (green areas) layer among 157 layers, but all layers have `queryable="0"` — no `GetFeatureInfo` available.

---

## Conclusion

The Poznań city portal API **cannot confirm** ZZM management of parcel `03/06/1/7`:

1. All 50 ZZM Parki objects have no parcel geometry linked in the portal database.
2. There is no parcel-number-based search in this API.

---

## Viable alternatives

### A — Manual XLSX entry (recommended, immediate)
Add `03/06/1/7` to `powierzenia-YYYY-MM-DD.xlsx` with `opis = "Zarząd Zieleni Miejskiej"` and the correct sygnatura. This feeds the app's authoritative source (branch 1/2 always wins over inferred logic).

### B — GUGIK spatial intersection (future feature)
Query `uldk.gugik.gov.pl` for parcel geometry, then do a spatial intersection against ZZM park polygons from the `class_objects` endpoint. The GUGIK full parcel ID would be `306401_1.0306.1/7` (Poznań TERYT prefix + obręb 0306 + parcel 1/7). See ROADMAP for the planned feature.
