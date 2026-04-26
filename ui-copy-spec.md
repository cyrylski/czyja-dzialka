# UI Copy Spec — all scenario branches

Single source of truth for panel copy. Covers all 14 scenario types + Branch 9 expanded
into 8 sub-branches for non-city ownership categories.

Sources: `panel-scenarios.md`, `new-data-values.md`, `parcel_analyzer.py`

**Legal basis column:** ⚠ every entry pending manual verification before display in UI.

Per-branch tables use three explicit UI element rows:
- **UI · hero-label** — always displayed; sets context
- **UI · hero-name** — displayed only when a named entity can be stated; *(nie wyświetlane)* otherwise
- **UI · contextual-note** — displayed when actionable detail is available; *(nie wyświetlane)* otherwise

---

## Quick reference

| Branch | Scenario type | show_wlasc | Confidence |
|--------|--------------|-----------|------------|
| 1 | `xlsx_multi` | ✓ | confirmed |
| 2 | `xlsx_single` | ✓ | confirmed |
| 3 | `zdm_city` | ✓ | inferred |
| 4 | `zdm_other` | ✓ | inferred |
| 5 | `church` | ✗ | inferred |
| 6 | `skarb_uw` | ✓ | inferred |
| 7 | `skarb_zasob` | ✓ | inferred |
| 7b | `skarb_tz` | ✓ | inferred |
| 8 | `skarb_other` | ✓ | inferred |
| 9a | `gminna_entity` | ✓ | inferred |
| 9-A | `private` / osoba fizyczna | ✓ | inferred |
| 9-B | `private` / wspólnota | ✓ | inferred |
| 9-C | `private` / prawo związane | ✓ | inferred |
| 9-D | `private` / spółka krajowa | ✓ | inferred |
| 9-E | `private` / spółka zagraniczna | ✓ | inferred |
| 9-F | `private` / powiat | ✓ | inferred |
| 9-G | `private` / stowarzyszenie | ✓ | inferred |
| 9-Z | `private` / fallback | ✓ | inferred |
| 10 | `city_mixed` | ✗ | inferred |
| 11 | `city_zasob` | ✓ | inferred |
| 12 | `city_uw` | ✓ | inferred |
| 13 | `city_tz` | ✓ | inferred |
| 14 | `unknown` | ✓ | inferred |

---

## Branch 1 — XLSX: kilka zarządców

**Detection:** `pow_entries.length > 1`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Tą działką zarządza kilka jednostek: |
| **UI · hero-name** | *(nie wyświetlane — lista jednostek z XLSX wyświetlana poniżej nagłówka)* |
| **UI · contextual-note** | *(nie wyświetlane)* |
| **Legal basis ⚠** | Dane potwierdzone z rejestru powierzeń (XLSX) |
| show_wlasc | ✓ |
| Confidence | confirmed |

---

## Branch 2 — XLSX: jeden zarządca

**Detection:** `pow_entries.length === 1`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Tą działką zarządza |
| **UI · hero-name** | **[nazwa jednostki z XLSX]** |
| **UI · contextual-note** | *(nie wyświetlane)* |
| **Legal basis ⚠** | Dane potwierdzone z rejestru powierzeń (XLSX) |
| show_wlasc | ✓ |
| Confidence | confirmed |

---

## Branch 3 — Droga, właściciel: Miasto Poznań → ZDM

**Detection:** `isRoads && isCityOwned` (brak wpisu XLSX)
`isRoads`: WLAD zawiera `'dróg publicznych'` LUB `KLASOUZYTKI === 'dr'`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Tą działką zarządza |
| **UI · hero-name** | **Zarząd Dróg Miejskich** |
| **UI · contextual-note** | Jednostka odpowiada za utrzymanie pasa drogowego. |
| **Legal basis ⚠** | Art. 19 ust. 5 ustawy o drogach publicznych |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 4 — Droga, właściciel inny niż Miasto → ZDM

**Detection:** `isRoads && !isCityOwned`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Tą działką zarządza |
| **UI · hero-name** | **Zarząd Dróg Miejskich** |
| **UI · contextual-note** | Działka ma innego właściciela, ale ZDM odpowiada za utrzymanie pasa drogowego. |
| **Legal basis ⚠** | Art. 19 ust. 5 ustawy o drogach publicznych |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 5 — Kościół / związek wyznaniowy

**Detection:** WLASC zawiera `'kościoły'` LUB `'związki wyznaniowe'` (case-insensitive)

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Właścicielem i zarządcą działki jest |
| **UI · hero-name** | **[WLASC]** |
| **UI · contextual-note** | Kościoły i związki wyznaniowe zarządzają własnością samodzielnie. |
| **Legal basis ⚠** | Ustawa z 17.05.1989 r. o gwarancjach wolności sumienia i wyznania |
| show_wlasc | ✗ (nazwa już w hero-name) |
| Confidence | inferred |

---

## Branch 6 — Skarb Państwa + użytkowanie wieczyste

**Detection:** `isSkarb && 'Użytkowanie wieczyste' in WLAD`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka Skarbu Państwa w użytkowaniu wieczystym |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Grunt powierzony miastu lub podmiotowi prywatnemu. Szczegóły: [Wydział Gospodarki Nieruchomościami](https://bip.poznan.pl/bip/wydzial-gospodarki-nieruchomosciami,24/). |
| **Legal basis ⚠** | Art. 232 KC; Prezydent Miasta jako Starosta wykonuje prawa właścicielskie SP |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 7 — Skarb Państwa + Gospodarowanie zasobem

**Detection:** `isSkarb && 'Gospodarowanie zasobem' in WLAD`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działką zarządza urząd lub jednostka Skarbu Państwa |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Brak szczegółowych danych. W razie pytań zwróć się do [Wydziału Gospodarki Nieruchomościami](https://bip.poznan.pl/bip/wydzial-gospodarki-nieruchomosciami,24/). |
| **Legal basis ⚠** | Art. 11 + 23 UGN; Art. 92 ustawy o samorządzie powiatowym |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 7b — Skarb Państwa + Trwały zarząd

**Detection:** `isSkarb && 'Trwały zarząd' in WLAD`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka w trwałym zarządzie jednostki państwowej lub miejskiej |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | W razie pytań zwróć się do [Wydziału Gospodarki Nieruchomościami](https://bip.poznan.pl/bip/wydzial-gospodarki-nieruchomosciami,24/). |
| **Legal basis ⚠** | Art. 43 + 44 UGN |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 8 — Skarb Państwa (fallback)

**Detection:** `isSkarb` (żaden z powyższych WLAD nie pasuje)

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka należy do Skarbu Państwa |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Brak danych o zarządcy. W razie pytań zwróć się do [Wydziału Gospodarki Nieruchomościami](https://bip.poznan.pl/bip/wydzial-gospodarki-nieruchomosciami,24/). |
| **Legal basis ⚠** | UGN — mienie SP niezagospodarowane podlega Prezydentowi jako Staroście |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9a — Gminna osoba prawna

**Detection:** WLASC zawiera `'gminna'` (case-insensitive); nie `isCityOwned`; nie `isSkarb`
Przykłady: `"Gminna osoba prawna"`, `"jednoosobowa spółka gminy"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka należy do miejskiej spółki lub jednostki gminnej |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Właścicielem jest podmiot powiązany z Miastem Poznań. W sprawach dotyczących tej działki zwróć się do [Wydziału Gospodarki Nieruchomościami](https://bip.poznan.pl/bip/wydzial-gospodarki-nieruchomosciami,24/). |
| **Legal basis ⚠** | Ustawa o samorządzie gminnym — mienie gminy zarządzane przez jej jednostki i spółki |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-A — Własność prywatna: osoba fizyczna

**Detection:** WLASC zawiera `"osoba fizyczna"` AND nie zawiera `"prawo związane"` AND nie zaczyna się od `"wspólnota:"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Ta działka jest własnością prywatną |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Właścicielem jest osoba fizyczna lub kilka osób prywatnych. Szczegóły własności znajdziesz w Księdze Wieczystej — numer KW możesz uzyskać w [Geopoz — Wydział Geodezji i Kartografii](https://geopoz.poznan.pl/geo/kontakt/dane-adresowe/1522,Dane-adresowe.html) lub wyszukać na stronie [ekw.ms.gov.pl](https://ekw.ms.gov.pl). |
| **Legal basis ⚠** | Art. 140 KC — właściciel wykonuje zarząd we własnym zakresie |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-B — Własność prywatna: wspólnota mieszkaniowa

**Detection:** WLASC zaczyna się od `"wspólnota:"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka stanowi grunt pod budynkiem wielolokalowym |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Gruntem zarządza wspólnota mieszkaniowa budynku. W sprawach dotyczących terenu zwróć się do zarządu wspólnoty (dane na tablicy informacyjnej w klatce schodowej) lub do zarządcy nieruchomości. |
| **Legal basis ⚠** | Art. 3 ustawy z 24.06.1994 r. o własności lokali |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-C — Własność prywatna: prawo związane z lokalem

**Detection:** WLASC zawiera `"prawo związane:"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka stanowi grunt pod budynkiem — własność powiązana z lokalami |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Każdy właściciel lokalu w tym budynku posiada ułamkowy udział własności tego gruntu, nierozerwalnie związany z prawem do swojego mieszkania (art. 3 ustawy o własności lokali). Sprawami gruntowymi zajmuje się wspólnota mieszkaniowa budynku — zwróć się do jej zarządu lub zarządcy nieruchomości. |
| **Legal basis ⚠** | Art. 3 ust. 1 ustawy o własności lokali; ustawa z 20.07.2018 r. o przekształceniu użytkowania wieczystego gruntów mieszkaniowych |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-D — Własność prywatna: polska spółka handlowa

**Detection:** WLASC zawiera `"spółka handlowa niebędąca cudzoziemcem"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Ta działka należy do polskiej spółki handlowej |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Właścicielem jest spółka prawa handlowego zarejestrowana w Polsce. Dane firmy (adres, reprezentacja) możesz sprawdzić bezpłatnie w Krajowym Rejestrze Sądowym: [ekrs.ms.gov.pl](https://ekrs.ms.gov.pl). Szczegóły własności gruntu — w Księdze Wieczystej: [ekw.ms.gov.pl](https://ekw.ms.gov.pl). |
| **Legal basis ⚠** | Kodeks spółek handlowych — spółka zarządza nieruchomością przez swoje organy |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-E — Własność prywatna: zagraniczny podmiot prawny

**Detection:** WLASC zawiera `"spółka handlowa będąca cudzoziemcem"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Ta działka należy do zagranicznego podmiotu prawnego |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Właścicielem jest podmiot zarejestrowany za granicą (nabycie nieruchomości przez cudzoziemca wymaga zezwolenia MSWiA). Jeśli podmiot posiada oddział w Polsce, możesz go znaleźć w KRS: [ekrs.ms.gov.pl](https://ekrs.ms.gov.pl). Szczegóły własności gruntu — w Księdze Wieczystej: [ekw.ms.gov.pl](https://ekw.ms.gov.pl). |
| **Legal basis ⚠** | Ustawa z 24.03.1920 r. o nabywaniu nieruchomości przez cudzoziemców |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-F — Własność prywatna: powiat

**Detection:** WLASC zawiera `"powiat"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Ta działka należy do powiatu |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Właścicielem jest Powiat Poznański. W sprawach dotyczących tej nieruchomości zwróć się do Starostwa Powiatowego w Poznaniu, Wydział Geodezji i Gospodarki Nieruchomościami: [powiat.poznan.pl/kontakt](https://powiat.poznan.pl/kontakt). |
| **Legal basis ⚠** | Art. 48 ustawy z 5.06.1998 r. o samorządzie powiatowym |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-G — Własność prywatna: stowarzyszenie

**Detection:** WLASC zawiera `"stowarzyszenie"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Ta działka należy do stowarzyszenia lub organizacji |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Właścicielem jest zarejestrowane stowarzyszenie, które zarządza nieruchomością przez swój zarząd. Dane organizacji (adres, skład zarządu) możesz znaleźć bezpłatnie w Krajowym Rejestrze Sądowym: [ekrs.ms.gov.pl](https://ekrs.ms.gov.pl). |
| **Legal basis ⚠** | Ustawa z 7.04.1989 r. Prawo o stowarzyszeniach |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 9-Z — Własność prywatna: fallback (kilku współwłaścicieli / inne)

**Detection:** catch-all — żadna z powyższych gałęzi prywatnych nie pasuje
Przykłady WLASC: `"spółka handlowa niebędąca cudzoziemcem, osoba fizyczna"`, `"prawo związane: spółka handlowa niebędąca cudzoziemcem, prawo związane: osoba fizyczna"`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Ta działka jest własnością prywatną |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Działka należy do kilku współwłaścicieli (osoby prywatne lub podmioty gospodarcze). Szczegóły własności znajdziesz w Księdze Wieczystej: [ekw.ms.gov.pl](https://ekw.ms.gov.pl). Numer KW możesz uzyskać w [Geopoz — Wydział Geodezji i Kartografii](https://geopoz.poznan.pl/geo/kontakt/dane-adresowe/1522,Dane-adresowe.html). |
| **Legal basis ⚠** | Art. 195 KC — współwłasność ułamkowa |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 10 — Współwłasność: Miasto + osoby prywatne

**Detection:** `isMixedOwnership && 'Gospodarowanie zasobem' in WLAD`
`isMixedOwnership`: WLASC zawiera `'Miasto Poznań'` AND `'osoba fizyczna'`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka ze współwłasnością Miasta i osób prywatnych |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | To prawdopodobnie grunt pod budynkiem wielolokalowym (wspólnota mieszkaniowa) |
| **Legal basis ⚠** | Art. 3 ustawy o własności lokali; mienie komunalne w zarządzie WGN |
| show_wlasc | ✗ (mieszany ciąg byłby mylący) |
| Confidence | inferred |

---

## Branch 11 — Miasto: Gospodarowanie zasobem → WGN

**Detection:** `'Gospodarowanie zasobem' in WLAD` (isCityOwned domniemane; przypadek mieszany obsłużony przez Branch 10)

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Tą działką zarządza |
| **UI · hero-name** | **[Wydział Gospodarki Nieruchomościami](https://bip.poznan.pl/bip/wydzial-gospodarki-nieruchomosciami,24/)** |
| **UI · contextual-note** | *(nie wyświetlane)* |
| **Legal basis ⚠** | Ustawa o gospodarce nieruchomościami — gminny zasób nieruchomości |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 12 — Miasto: użytkowanie wieczyste

**Detection:** `'Użytkowanie wieczyste' in WLAD`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka w użytkowaniu wieczystym |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | Grunt miejski oddany w użytkowanie wieczyste — najprawdopodobniej wspólnocie mieszkaniowej, spółdzielni, firmie lub osobie prywatnej. |
| **Legal basis ⚠** | Art. 232 KC |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 13 — Miasto: Trwały zarząd jednostki miejskiej

**Detection:** `isCityOwned && 'Trwały zarząd' in WLAD`

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Działka w trwałym zarządzie jednostki miejskiej |
| **UI · hero-name** | *(nie wyświetlane)* |
| **UI · contextual-note** | W razie pytań zwróć się do [Wydziału Gospodarki Nieruchomościami](https://bip.poznan.pl/bip/wydzial-gospodarki-nieruchomosciami,24/). |
| **Legal basis ⚠** | Art. 43 UGN — trwały zarząd przysługuje wyłącznie jednostkom organizacyjnym nieposiadającym osobowości prawnej |
| show_wlasc | ✓ |
| Confidence | inferred |

---

## Branch 14 — Nieznana kombinacja (fallback)

**Detection:** żadna z powyższych gałęzi nie pasuje

| Pole | Wartość |
|------|---------|
| **UI · hero-label** | Tą działką zarządza |
| **UI · hero-name** | **brak informacji** |
| **UI · contextual-note** | *(nie wyświetlane)* |
| **Legal basis ⚠** | — |
| show_wlasc | ✓ |
| Confidence | inferred |
