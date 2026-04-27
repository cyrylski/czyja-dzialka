# Panel — data scenarios

Each scenario maps to a branch in `buildCard()` (`index.html`). Branches are evaluated
top-to-bottom; first match wins. XLSX entries (branches 1–2) always beat inferred logic.
Full decision tree with legal basis: `ZARZADCA-LOGIC.md`.

---

## Branch 1 — XLSX: multiple managers

**Condition:** `powList.length > 1`

Parcel has more than one row in `powierzenia-YYYY-MM-DD.xlsx`.
Displayed as a grid of all managers, each with name + signature.

| Field | Example value |
|---|---|
| Numer działki | 01/24/11/2 |
| Właściciel | Miasto Poznań |
| Managers | Zakład Lasów Poznańskich · Usługi Komunalne |
| Sygnatury | GN-XIX.6845.5.48.2025 · GN-XIX.6845.5.49.2025 |

---

## Branch 2 — XLSX: single manager

**Condition:** `powList.length === 1`

Single XLSX row. Manager name as hero, signature below.

| Field | Example value |
|---|---|
| Numer działki | 35/21/53/25 |
| Właściciel | Miasto Poznań |
| Manager | Zarząd Dróg Miejskich - powierzenie |
| Sygnatura | GN-XX.6845.2.65.2013 |
| Rodzaj powierzenia | Wykonywanie zadań zarządcy dróg publicznych |

---

## Branch 3 — Road parcel, city-owned

**Condition:** `isRoads && isCityOwned` (no XLSX entry)

`WLAD` contains `'dróg publicznych'` and owner is Miasto Poznań.
Legal basis: Art. 19 ust. 5 UoDP — ZDM acts on behalf of Prezydent Miasta.

| Field | Example value |
|---|---|
| Numer działki | 20/41/76/8 |
| Właściciel | Miasto Poznań |
| Rodzaj powierzenia | Wykonywanie zadań zarządcy dróg publicznych |
| Shown as | Tą działką zarządza **Zarząd Dróg Miejskich** |

**isRoads trigger:** `WLAD` contains `'dróg publicznych'` **OR** `KLASOUZYTKI_EGIB === 'dr'`.
`KLASOUZYTKI_EGIB` is fetched from `portal.geopoz.poznan.pl/wmsegib` (concurrent with the WFS geometry call).
It is set at the classification level and stays `'dr'` even when `WLAD` is stale.
Test case: parcel 04/13/4/473 (ul. Piotra Tomickiego) — previously routed to WGN, now correctly shows ZDM.

---

## Branch 4 — Road parcel, non-city owner

**Condition:** `isRoads && !isCityOwned` (no XLSX entry)

Same as branch 3 but owner is not Miasto Poznań (e.g. Skarb Państwa).
Zarządca status follows road category, not ownership.

| Field | Example value |
|---|---|
| Właściciel | Skarb Państwa |
| Rodzaj powierzenia | Wykonywanie zadań zarządcy dróg publicznych |
| Shown as | Tą działką zarządza **Zarząd Dróg Miejskich** + "Działka ma innego właściciela..." |

⚠ GDDKiA roads (A2, S5, S11) not handled — would incorrectly show ZDM.

---

## Branch 5 — Religious entity

**Condition:** `isChurch` — `WLASC` contains `'kościoły'` or `'związki wyznaniowe'`

Owner IS the manager. Religious associations manage independently under dedicated laws.
`showWlasc = false` — name in hero zone, not repeated in data grid.

| Field | Example value |
|---|---|
| Właściciel | Kościoły katolickie |
| Shown as | Właścicielem i zarządcą działki jest **Kościoły katolickie** |

---

## Branch 6 — Skarb Państwa + użytkowanie wieczyste

**Condition:** `isSkarb && WLAD contains 'Użytkowanie wieczyste'`

SP land in perpetual usufruct. UW holder acts independently toward third parties.
WGN (Prezydent as Starosta) administers the UW contract on behalf of SP.

| Field | Example value |
|---|---|
| Właściciel | Skarb Państwa |
| Rodzaj powierzenia | Użytkowanie wieczyste |
| Shown as | Działka Skarbu Państwa w użytkowaniu wieczystym |

---

## Branch 7 — Skarb Państwa + Gospodarowanie zasobem

**Condition:** `isSkarb && WLAD contains 'Gospodarowanie zasobem'`

General SP resource pool managed by Prezydent-as-Starosta. WGN is the contact.
Art. 11 + 23 UGN + Art. 92 u.s.p.

| Field | Example value |
|---|---|
| Właściciel | Skarb Państwa |
| Rodzaj powierzenia | Gospodarowanie zasobem nieruchomości SP oraz gminnymi... |
| Shown as | Działką zarządza urząd lub jednostka Skarbu Państwa |

---

## Branch 7b — Skarb Państwa + Trwały zarząd

**Condition:** `isSkarb && WLAD contains 'Trwały zarząd'`

SP land held in trwały zarząd — may be a state unit or a city unit (e.g. school).
Both named since either is possible. WGN supervises.

| Field | Example value |
|---|---|
| Właściciel | Skarb Państwa |
| Rodzaj powierzenia | Trwały zarząd |
| Shown as | Działka w trwałym zarządzie jednostki państwowej lub miejskiej |

---

## Branch 8 — Skarb Państwa fallback

**Condition:** `isSkarb` (no WLAD matched above)

SP parcel with unrecognised or missing WLAD. WGN still the correct contact.

| Field | Example value |
|---|---|
| Właściciel | Skarb Państwa |
| Rodzaj powierzenia | — (empty or unknown) |
| Shown as | Działka należy do Skarbu Państwa |

---

## Branch 9a — Gminna legal entity

**Condition:** `isGminnaEntity` — `WLASC` contains `'gminna'`, not isCityOwned, not isSkarb

Municipal company or unit (`gminna osoba prawna`, `jednoosobowa spółka gminy`).
`isCityOwned` only matches `'Miasto Poznań'` literally — without this branch these
entities fall to branch 9 with the incorrect "Miasto nie jest właścicielem" copy.
`showWlasc = true` — entity name visible in data grid.

| Field | Example value |
|---|---|
| Właściciel | Gminna osoba prawna |
| Shown as | Działka należy do miejskiej spółki lub jednostki gminnej |

---

## Branch 9 — Private / other owner

**Condition:** `!isCityOwned` (catch-all for non-city, non-state, non-church, non-gminna)

Osoba fizyczna, private spółka, cooperative, etc.
Owner name shown in orange. `showWlasc = false` — name already in hero zone.

| Field | Example value |
|---|---|
| Właściciel | osoba fizyczna |
| Shown as | Tą działką zarządza **[owner name]** (orange) + "Miasto nie jest jej właścicielem..." |

---

## Branch 10 — City + private co-ownership + Gospodarowanie zasobem

**Condition:** `isMixedOwnership && WLAD contains 'Gospodarowanie zasobem'`

`isMixedOwnership = isCityOwned && wlasc contains 'osoba fizyczna'`.
Typically a building plot with a housing community. Reachable because `isCityOwned=true`
prevents branch 9 from firing. `showWlasc = false` — mixed string would confuse users.

| Field | Example value |
|---|---|
| Właściciel | Miasto Poznań, osoba fizyczna |
| Rodzaj powierzenia | Gospodarowanie zasobem... |
| Shown as | Działka ze współwłasnością Miasta i osób prywatnych |

---

## Branch 11 — City parcel + Gospodarowanie zasobem

**Condition:** `WLAD contains 'Gospodarowanie zasobem'` (isCityOwned implied; mixed case handled above)

General city asset pool, no specific concession. WGN manages.
This branch also incorrectly catches road parcels with stale EGIB records — see branch 3 note.

| Field | Example value |
|---|---|
| Właściciel | Miasto Poznań |
| Rodzaj powierzenia | Gospodarowanie zasobem nieruchomości SP oraz gminnymi... |
| Shown as | Tą działką zarządza **Wydział Gospodarki Nieruchomościami** |

---

## Branch 12 — City parcel + użytkowanie wieczyste

**Condition:** `WLAD contains 'Użytkowanie wieczyste'`

City-owned ground in perpetual usufruct. UW holder (typically wspólnota, firma, or
osoba prywatna) has quasi-ownership and acts independently. Art. 232 KC.

| Field | Example value |
|---|---|
| Właściciel | Miasto Poznań |
| Rodzaj powierzenia | Użytkowanie wieczyste |
| Shown as | Działka w użytkowaniu wieczystym |

---

## Branch 13 — City parcel + Trwały zarząd

**Condition:** `isCityOwned && WLAD contains 'Trwały zarząd'`

City-owned parcel held in trwały zarząd by a municipal unit. Art. 43 UGN.
"Jednostki miejskiej" only — Miasto cannot grant TZ to state units (contrast: branch 7b).
If the specific unit is in XLSX, branch 1 or 2 fires first.

| Field | Example value |
|---|---|
| Właściciel | Miasto Poznań |
| Rodzaj powierzenia | Trwały zarząd |
| Shown as | Działka w trwałym zarządzie jednostki miejskiej |

---

## Branch 14 — Default

**Condition:** no branch above matched

Unrecognised WLASC/WLAD combination. Monitor for unexpected fallbacks — EGIB vocabulary
may change over time.

| Shown as | Tą działką zarządza **brak informacji** |

---

## Known gaps requiring manual XLSX entries

| Situation | Why it fails | Fix |
|---|---|---|
| Road parcel with `WLAD='Gospodarowanie zasobem...'` | Stale EGIB record, isRoads=false | Add to XLSX with `opis='Zarząd Dróg Miejskich'` |
| ZZM park parcel not in XLSX | No API can confirm ZZM from parcel number alone | Add to XLSX with `opis='Zarząd Zieleni Miejskiej'` |
| NRD field | Contains parcel-number suffix (`4/473` from `04/13/4/473`), not a road registry indicator | Not usable as road signal |
