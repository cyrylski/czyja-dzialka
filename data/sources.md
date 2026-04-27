# Data sources

Drop updated files here with today's date in the filename. The app picks up the newest file automatically at startup (sorted by name, descending).

---

## 1. Powierzenia (concessions)

**Filename pattern:** `powierzenia-YYYY-MM-DD.xlsx`  
**Report URL:** https://sipaplikacje.geopoz.poznan.pl/raporty/report?reportId=2000035  
**Required columns:** `OZN_DZ`, `OPIS`, `SYGNATURA`  
**Used for:** Highest-priority lookup — branches XLSX_SINGLE / XLSX_MULTI (overrides all inferred logic)

**To update:** Download the report as XLSX, rename it `powierzenia-YYYY-MM-DD.xlsx`, drop it here. Delete the old file.

---

## 2. Trwały zarząd (permanent management)

**Filename pattern:** `trwaly-zarzad-YYYY-MM-DD.csv`  
**Report URL:** https://sipaplikacje.geopoz.poznan.pl/raporty/report?reportId=2000092  
**Required columns:** `Pełny numer działki`, `Jednostka`  
**Optional columns:** `Data ustanowienia`  
**Used for:** Enriches SKARB_TZ and CITY_TZ branches — shows the specific managing unit instead of a generic note

**To update:** Download the report as CSV, rename it `trwaly-zarzad-YYYY-MM-DD.csv`, drop it here. Delete the old file.

---

## 3. GEOPOZ API (live)

No files needed. Called per request from `geopoz_client.py`.  
Endpoints: WMS GetFeatureInfo, WFS GetFeature, Portal WMS (land use class).

---

## Future: auto-refresh script

Both reports above are publicly accessible without authentication. A `refresh_data.py` script could download them automatically on a schedule (e.g. weekly cron). See ROADMAP.md for details.
