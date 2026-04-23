# Zarządca / Właściciel Logic

This document describes the decision tree used in `buildCard()` (`index.html`) to
determine **who manages a given parcel** and what the user should see. It is
intended for future Claude Code sessions or agents making changes to this logic.

---

## Data sources

Every parcel lookup returns three fields relevant to this logic:

| Field | Source | Example values |
|---|---|---|
| `wlasc` | GEOPOZ (`WLASC`) — cadastre owner string | `"Miasto Poznań"`, `"Skarb Państwa"`, `"Kościoły katolickie"`, `"osoba fizyczna"` |
| `wlad` | GEOPOZ (`WLAD`) — management/tenure type | `"Wykonywanie zadań zarządcy dróg publicznych"`, `"Trwały zarząd"`, `"Użytkowanie wieczyste"`, `"Gospodarowanie zasobem nieruchomości..."` |
| `pow_list` | Local XLSX (`powierzenia-YYYY-MM-DD.xlsx`) | `[{opis: "Zarząd Dróg Miejskich", sygnatura: "GN-XX.6845.2.65.2013"}]` |

`wlasc` and `wlad` are free-text strings from the cadastre — matching is done
with `indexOf()`, not strict equality.

---

## Boolean flags (computed at the top of `buildCard()`)

```javascript
const isMulti       = powList.length > 1;
const hasPow        = powList.length >= 1;
const isRoads       = wlad.indexOf('dróg publicznych') !== -1;
const isCityOwned   = wlasc.indexOf('Miasto Poznań') !== -1;
const isSkarb       = wlasc.indexOf('Skarb Państwa') !== -1;
const isChurch      = wlasc.toLowerCase().indexOf('kościoły') !== -1
                   || wlasc.toLowerCase().indexOf('związki wyznaniowe') !== -1;
const isMixedOwnership = isCityOwned && wlasc.indexOf('osoba fizyczna') !== -1;
```

---

## Decision tree (priority order)

Branches are evaluated top-to-bottom; the first match wins.

### 1 — Multiple managers in XLSX (`isMulti`)
**Display:** grid of all managers, each with name + signature number.  
**Rationale:** explicit data beats inferred logic; XLSX is the authoritative concession register.

### 2 — Single manager in XLSX (`hasPow`)
**Display:** manager name as hero + signature number below.  
**Rationale:** same as above.

### 3 — Road parcel, city-owned (`isRoads && isCityOwned`, no XLSX entry)
**Display:** "Tą działką zarządza **Zarząd Dróg Miejskich**"  
**Note:** "(jednostka odpowiada za utrzymanie pasa drogowego)"  
**Legal basis:** Art. 19 ust. 5 Ustawy o drogach publicznych — within a *miasto
na prawach powiatu* (Poznań qualifies) the Prezydent Miasta is zarządca of all
public roads except expressways/highways; ZDM executes this on his behalf.

### 4 — Road parcel, non-city owner (`isRoads && !isCityOwned`, no XLSX entry)
**Display:** "Tą działką zarządza **Zarząd Dróg Miejskich**"  
**Note:** "Działka ma innego właściciela, ale ZDM odpowiada za utrzymanie pasa
drogowego."  
**Legal basis:** same as branch 3 — zarządca status follows road category, not
parcel ownership. ZDM manages roads on Skarb Państwa land too.  
**⚠ Edge case not handled:** expressways and highways within Poznań city limits
(A2, S5, S11) are managed by **GDDKiA**, not ZDM. These are unlikely to appear
as individually clickable city-cadastre parcels in practice.

### 5 — Religious owner (`isChurch`)
**Display:** "Właścicielem i zarządcą działki jest **{wlasc}**"  
**Note:** "(kościoły i związki wyznaniowe zarządzają własnością samodzielnie)"  
**Legal basis:** Ustawa o gwarancjach wolności sumienia i wyznania +
denomination-specific laws (e.g. Ustawa o stosunku Państwa do Kościoła
Katolickiego). Religious associations own and manage their property fully
independently — they are outside the UGN / Skarb Państwa resource management
framework entirely.  
**Note:** `showWlasc = false` here because the name is already in the hero zone
above; it is not repeated in the data grid.

### 6 — State parcel, użytkowanie wieczyste (`isSkarb && wlad contains 'Użytkowanie wieczyste'`)
**Display:** "Działka Skarbu Państwa w użytkowaniu wieczystym"  
**Note:** "Grunt oddany miastu lub podmiotowi prywatnemu. Szczegóły: Wydział
Gospodarki Nieruchomościami UMP."  
**Legal basis:** Art. 232 KC — once SP land is in UW, only the UW holder acts
toward third parties for day-to-day management. However WGN (acting as Starosta
= Prezydent) administers the UW contracts on behalf of SP, so it is the right
administrative contact.

### 7 — State parcel, asset management (`isSkarb && wlad contains 'Gospodarowanie zasobem'`)
**Display:** "Działką zarządza urząd lub jednostka Skarbu Państwa"  
**Note:** "Brak szczegółowych danych — w razie pytań zwróć się do Wydziału
Gospodarki Nieruchomościami UMP."  
**Legal basis:** Art. 11 + Art. 23 Ustawy o gospodarce nieruchomościami + Art.
92 Ustawy o samorządzie powiatowym. The Prezydent Poznania simultaneously acts
as Starosta; WGN's BIP page explicitly lists SP property tasks alongside Miasto
tasks. "Gospodarowanie zasobem SP" ≠ ZDM (a previous incorrect assumption) —
it means the land is in the general SP resource managed by the Prezydent-as-Starosta.  
**Note:** `showWlasc = true` so the user can see "Skarb Państwa" in the data
grid alongside the contextual note.

### 7b — State parcel, trwały zarząd (`isSkarb && wlad contains 'Trwały zarząd'`)
**Display:** "Działka w trwałym zarządzie jednostki państwowej lub miejskiej"  
**Note:** "W razie pytań zwróć się do Wydziału Gospodarki Nieruchomościami UMP."  
**Rationale:** SP land in trwały zarząd may be held by a state unit (jednostka
państwowa) or a city unit (e.g. a school or public institution) — hence both
are named. WGN (acting as Starosta) is the supervisory contact for SP parcels
in trwały zarząd.  
**Contrast with branch 13:** City-owned parcels in trwały zarząd use "jednostki
miejskiej" only, since Miasto Poznań cannot grant trwały zarząd to state units.

### 8 — State parcel, other / fallback (`isSkarb`)
**Display:** "Działka należy do Skarbu Państwa"  
**Note:** "Brak danych o zarządcy — w razie pytań zwróć się do Wydziału
Gospodarki Nieruchomościami UMP."  
**Covers:** SP + Trwały zarząd, SP + any other WLAD not matched above, SP with
no WLAD. WGN (Prezydent as Starosta) is still the correct contact for all of
these.

### 9 — Non-city, non-state, non-church private owner (`!isCityOwned`)
**Display:** "Tą działką zarządza **{wlasc}** (orange)"  
**Note:** "Miasto nie jest jej właścicielem. W sprawach dotyczących tej działki
możesz zwrócić się do Wydziału Gospodarki Nieruchomościami..."  
**Covers:** osoba fizyczna, spółka prywatna, cooperative, etc.  
**Note:** `showWlasc = false` because the name is in the hero zone.

### 10 — City + private co-ownership, asset management (`isMixedOwnership && wlad contains 'Gospodarowanie zasobem'`)
**Display:** "Działka ze współwłasnością Miasta i osób prywatnych"  
**Note:** "To prawdopodobnie grunt pod budynkiem wielolokalowym (wspólnota
mieszkaniowa)"  
**Note:** `isMixedOwnership = isCityOwned && wlasc contains 'osoba fizyczna'`.
This branch is reachable because `isCityOwned` is true, so branch 9 does not
fire.

### 11 — City parcel, użytkowanie wieczyste (`wlad contains 'Użytkowanie wieczyste'`)
**Display:** "Działka w użytkowaniu wieczystym"  
**Note:** "Grunt miejski oddany w użytkowanie wieczyste — najprawdopodobniej
wspólnocie, firmie lub osobie prywatnej."  
**Legal basis:** Art. 232 KC. UW ≠ dzierżawa — it is a distinct legal form
(perpetual usufruct, up to 99 years). The UW holder has quasi-ownership and
acts independently toward third parties.

### 12 — City parcel, asset management (`wlad contains 'Gospodarowanie zasobem'`)
**Display:** "Tą działką zarządza **Wydział Gospodarki Nieruchomościami**"  
**Covers:** City-owned parcels in the general municipal asset stock with no
specific concession recorded.

### 13 — City parcel, trwały zarząd (`isCityOwned && wlad contains 'Trwały zarząd'`)
**Display:** "Działka w trwałym zarządzie jednostki miejskiej"  
**Note:** "W razie pytań zwróć się do Wydziału Gospodarki Nieruchomościami UMP."  
**Legal basis:** Art. 43 UGN — trwały zarząd is a legal form of land holding
by a *jednostka organizacyjna* (public organisational unit). Only public units
can hold it. WGN is the supervisory organ for trwały zarząd on both MP and SP
parcels in Poznań. If the specific holding unit is in the XLSX, branch 1 or 2
will have fired before this branch is reached.

### 14 — Default
**Display:** "Tą działką zarządza **brak informacji**"

---

## XLSX powierzenie data

The file `powierzenia-YYYY-MM-DD.xlsx` (loaded at startup by `server.py:load_powierzenia()`)
is the **primary source** and overrides all inferred logic (branches 1–2 always
win). It maps `OZN_DZ` → `[{opis, sygnatura}]`.

- Multiple rows for the same parcel → `isMulti = true` → branch 1 (grid view).
- One row → branch 2 (single manager).
- The date in the filename is shown in the UI as "Zaktualizowano: YYYY-MM-DD".
- When the file is missing a parcel that GEOPOZ marks as a road, the app falls
  through to branch 3 or 4 and infers ZDM (correct per Art. 19 ust. 5 UoDP).

---

## Legal sources verified

| Article | Law | Relevance |
|---|---|---|
| Art. 19 ust. 5 | Ustawa o drogach publicznych (1985) | ZDM scope in miasto na prawach powiatu |
| Art. 11, 23 | Ustawa o gospodarce nieruchomościami (1997) | Starosta = organ for SP parcels |
| Art. 43 | Ustawa o gospodarce nieruchomościami (1997) | Trwały zarząd definition |
| Art. 92 | Ustawa o samorządzie powiatowym | Prezydent = Starosta in Poznań |
| Art. 232 | Kodeks cywilny | Użytkowanie wieczyste definition |
| Art. 693 | Kodeks cywilny | Dzierżawa — distinct from UW |
| — | Ustawa o gwarancjach wolności sumienia i wyznania | Religious association property independence |

---

## Known limitations and edge cases

1. **GDDKiA roads not handled:** Expressways and highways within Poznań city
   limits (A2, S5, S11) are managed by GDDKiA, not ZDM. The app has no branch
   for this. In practice these parcels are unlikely to appear as individually
   clickable cadastre parcels.

2. **XLSX is not auto-synced:** The powierzenie file requires a manual export
   from the municipal system. It may lag behind reality. The date in the
   filename is the only freshness indicator shown to the user.

4. **wlasc / wlad are free-text:** GEOPOZ does not enforce a controlled
   vocabulary. New values may appear that don't match any `indexOf()` check and
   fall through to the default (branch 14). Monitor for unexpected fallbacks in
   production.

---

## Files to modify

| What to change | File | Lines |
|---|---|---|
| Decision tree (all branches) | `index.html` | 427–496 |
| Boolean flag definitions | `index.html` | 427–433 |
| XLSX loading | `server.py` | 32–70 |
| API response fields | `server.py` | 234–244 |
| Scenario documentation | `panel-scenarios.md` | entire file |
