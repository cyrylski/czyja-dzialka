# Non-city ownership: copy matrix

Scope: hero_label and contextual_note for all non-city-managed parcel categories,
derived from real WLASC strings found in 500-parcel survey (wlasc_survey_results.md).

Rules applied:
- manager_name: always empty (not applicable for non-city parcels)
- show_wlasc: true — raw EGIB string shown in data grid under "Właściciel" label,
  consistent with Numer działki / Powierzchnia / Rodzaj powierzenia
- No phone numbers in contextual_note; use website or contact page URL instead

---

## 1. osoba fizyczna

**Detection:** WLASC contains `"osoba fizyczna"` AND no `"prawo związane"` AND no `"wspólnota:"`
**Legal basis:** Art. 140 KC — właściciel wykonuje zarząd we własnym zakresie

| Pole             | Treść |
|------------------|-------|
| hero_label       | Ta działka jest własnością prywatną |
| contextual_note  | Właścicielem jest osoba fizyczna lub kilka osób prywatnych. Szczegóły własności znajdziesz w Księdze Wieczystej — numer KW możesz uzyskać w [Geopoz — Wydział Geodezji i Kartografii](https://geopoz.poznan.pl/geo/kontakt/dane-adresowe/1522,Dane-adresowe.html) lub wyszukać na stronie [ekw.ms.gov.pl](https://ekw.ms.gov.pl). |

---

## 2. wspólnota: osoba fizyczna

**Detection:** WLASC starts with `"wspólnota:"`
**Legal basis:** Art. 3 ustawy z 24.06.1994 r. o własności lokali — grunt pod budynkiem stanowi
współwłasność ułamkową właścicieli lokali; zarząd sprawuje wspólnota mieszkaniowa lub
wyznaczony zarządca nieruchomości

| Pole             | Treść |
|------------------|-------|
| hero_label       | Działka stanowi grunt pod budynkiem wielolokalowym |
| contextual_note  | Gruntem zarządza wspólnota mieszkaniowa budynku. W sprawach dotyczących terenu zwróć się do zarządu wspólnoty (dane na tablicy informacyjnej w klatce schodowej) lub do zarządcy nieruchomości. |

---

## 3. prawo związane: osoba fizyczna

**Detection:** WLASC contains `"prawo związane:"`
**Legal basis:** Art. 3 ust. 1 ustawy o własności lokali — prawo do gruntu jest prawem związanym
z własnością lokalu, niezbywalne od niego osobno. Na mocy ustawy z 20.07.2018 r.
o przekształceniu użytkowania wieczystego gruntów mieszkaniowych, dawne prawa użytkowania
wieczystego zostały z mocy prawa przekształcone we własność z dniem 1.01.2019 r.

| Pole             | Treść |
|------------------|-------|
| hero_label       | Działka stanowi grunt pod budynkiem — własność powiązana z lokalami |
| contextual_note  | Każdy właściciel lokalu w tym budynku posiada ułamkowy udział własności tego gruntu, nierozerwalnie związany z prawem do swojego mieszkania (art. 3 ustawy o własności lokali). Sprawami gruntowymi zajmuje się wspólnota mieszkaniowa budynku — zwróć się do jej zarządu lub zarządcy nieruchomości. |

---

## 4. spółka handlowa niebędąca cudzoziemcem

**Detection:** WLASC contains `"spółka handlowa niebędąca cudzoziemcem"`
**Legal basis:** Kodeks spółek handlowych — spółka zarządza nieruchomością przez swoje organy;
brak ograniczeń w nabywaniu nieruchomości przez krajowe podmioty gospodarcze

| Pole             | Treść |
|------------------|-------|
| hero_label       | Ta działka należy do polskiej spółki handlowej |
| contextual_note  | Właścicielem jest spółka prawa handlowego zarejestrowana w Polsce. Dane firmy (adres, reprezentacja) możesz sprawdzić bezpłatnie w Krajowym Rejestrze Sądowym: [ekrs.ms.gov.pl](https://ekrs.ms.gov.pl). Szczegóły własności gruntu — w Księdze Wieczystej: [ekw.ms.gov.pl](https://ekw.ms.gov.pl). |

---

## 5. spółka handlowa będąca cudzoziemcem

**Detection:** WLASC contains `"spółka handlowa będąca cudzoziemcem"`
**Legal basis:** Ustawa z 24.03.1920 r. o nabywaniu nieruchomości przez cudzoziemców —
nabycie nieruchomości przez podmiot zagraniczny wymagało zezwolenia MSWiA;
podmiot zarządza nieruchomością samodzielnie lub przez oddział w Polsce

| Pole             | Treść |
|------------------|-------|
| hero_label       | Ta działka należy do zagranicznego podmiotu prawnego |
| contextual_note  | Właścicielem jest podmiot zarejestrowany za granicą (nabycie nieruchomości przez cudzoziemca wymaga zezwolenia MSWiA). Jeśli podmiot posiada oddział w Polsce, możesz go znaleźć w KRS: [ekrs.ms.gov.pl](https://ekrs.ms.gov.pl). Szczegóły własności gruntu — w Księdze Wieczystej: [ekw.ms.gov.pl](https://ekw.ms.gov.pl). |

---

## 6. powiat

**Detection:** WLASC contains `"powiat"`
**Legal basis:** Art. 48 ustawy z 5.06.1998 r. o samorządzie powiatowym — powiat zarządza
mieniem przez Zarząd Powiatu; obsługę nieruchomości prowadzi Starostwo Powiatowe,
Wydział Geodezji i Gospodarki Nieruchomościami

| Pole             | Treść |
|------------------|-------|
| hero_label       | Ta działka należy do powiatu |
| contextual_note  | Właścicielem jest Powiat Poznański. W sprawach dotyczących tej nieruchomości zwróć się do Starostwa Powiatowego w Poznaniu, Wydział Geodezji i Gospodarki Nieruchomościami: [powiat.poznan.pl/kontakt](https://powiat.poznan.pl/kontakt). |

---

## 7. stowarzyszenie

**Detection:** WLASC contains `"stowarzyszenie"`
**Legal basis:** Ustawa z 7.04.1989 r. Prawo o stowarzyszeniach — stowarzyszenie zarządza
własnym majątkiem przez zarząd; rejestracja i dane publiczne w KRS

| Pole             | Treść |
|------------------|-------|
| hero_label       | Ta działka należy do stowarzyszenia lub organizacji |
| contextual_note  | Właścicielem jest zarejestrowane stowarzyszenie, które zarządza nieruchomością przez swój zarząd. Dane organizacji (adres, skład zarządu) możesz znaleźć bezpłatnie w Krajowym Rejestrze Sądowym: [ekrs.ms.gov.pl](https://ekrs.ms.gov.pl). |

---

## 8. mixed combos + pozostałe prywatne (fallback)

**Detection:** catch-all — żadna z powyższych kategorii nie pasuje; np. `spółka + osoba fizyczna`,
`dwie spółki`, `prawo związane: spółka + osoba fizyczna`
**Legal basis:** Art. 195 KC — współwłasność ułamkowa; każdy współwłaściciel zarządza
w granicach swojego udziału lub przez umowę quoad usum

| Pole             | Treść |
|------------------|-------|
| hero_label       | Ta działka jest własnością prywatną |
| contextual_note  | Działka należy do kilku współwłaścicieli (osoby prywatne lub podmioty gospodarcze). Szczegóły własności znajdziesz w Księdze Wieczystej: [ekw.ms.gov.pl](https://ekw.ms.gov.pl). Numer KW możesz uzyskać w [Geopoz — Wydział Geodezji i Kartografii](https://geopoz.poznan.pl/geo/kontakt/dane-adresowe/1522,Dane-adresowe.html). |

---

## Decyzje projektowe

| Kwestia | Decyzja |
|---------|---------|
| manager_name | puste dla wszystkich kategorii prywatnych |
| show_wlasc | true — surowy ciąg EGIB wyświetlany pod etykietą „Właściciel" (spójnie z Numer działki / Powierzchnia / Rodzaj powierzenia) |
| Numery telefonów | nie używamy |
| Linki | ekw.ms.gov.pl, ekrs.ms.gov.pl, powiat.poznan.pl/kontakt |
| Confidence | inferred (dla wszystkich — brak danych XLSX) |
