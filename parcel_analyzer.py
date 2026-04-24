from dataclasses import dataclass
from enum import Enum

from geopoz_client import ParcelAttributes, PowierzenieEntry, PowierzeniesMeta


class ScenarioType(str, Enum):
    XLSX_MULTI    = 'xlsx_multi'    # branch 1: pow_list.length > 1
    XLSX_SINGLE   = 'xlsx_single'   # branch 2: pow_list.length == 1
    ZDM_CITY      = 'zdm_city'      # branch 3: isRoads && isCityOwned
    ZDM_OTHER     = 'zdm_other'     # branch 4: isRoads && !isCityOwned
    CHURCH        = 'church'        # branch 5: isChurch
    SKARB_UW      = 'skarb_uw'      # branch 6: isSkarb && WLAD contains 'Użytkowanie wieczyste'
    SKARB_ZASOB   = 'skarb_zasob'   # branch 7: isSkarb && WLAD contains 'Gospodarowanie zasobem'
    SKARB_TZ      = 'skarb_tz'      # branch 7b: isSkarb && WLAD contains 'Trwały zarząd'
    SKARB_OTHER   = 'skarb_other'   # branch 8: isSkarb fallback
    GMINNA_ENTITY = 'gminna_entity' # branch 9a: isGminnaEntity
    PRIVATE       = 'private'       # branch 9: !isCityOwned (non-city, non-state, non-church)
    CITY_MIXED    = 'city_mixed'    # branch 10: isMixedOwnership && 'Gospodarowanie zasobem'
    CITY_ZASOB    = 'city_zasob'    # branch 11: isCityOwned && 'Gospodarowanie zasobem'
    CITY_UW       = 'city_uw'       # branch 12: isCityOwned && 'Użytkowanie wieczyste'
    CITY_TZ       = 'city_tz'       # branch 13: isCityOwned && 'Trwały zarząd'
    UNKNOWN       = 'unknown'       # branch 14: unrecognised combination


@dataclass
class ParcelScenario:
    # scenario fields
    type: ScenarioType
    manager_label: str               # heading, e.g. "Tą działką zarządza"
    manager_name: str | None         # e.g. "Zarząd Dróg Miejskich"; None when label says it all
    contextual_note: str | None      # secondary explanation line; None if not needed
    show_wlasc: bool                 # False for CHURCH, PRIVATE, CITY_MIXED
    pow_entries: list[PowierzenieEntry]  # populated for XLSX_MULTI / XLSX_SINGLE; [] otherwise
    confidence: str                  # "confirmed" (XLSX) | "inferred" (WLASC/WLAD strings)
    # pass-through data grid fields
    ozn_dz: str
    wlasc: str
    wlad: str
    pow_ewd: str
    adres: str
    geometry: dict | None
    baza_data: str | None
    baza_liczba: int


# --- Private boolean helpers (mirror JS buildCard flags exactly) ---

def _is_roads(wlad: str, klasouzytki: str) -> bool:
    return 'dróg publicznych' in wlad or klasouzytki == 'dr'

def _is_city_owned(wlasc: str) -> bool:
    return 'Miasto Poznań' in wlasc

def _is_skarb(wlasc: str) -> bool:
    return 'Skarb Państwa' in wlasc

def _is_church(wlasc: str) -> bool:
    w = wlasc.lower()
    return 'kościoły' in w or 'związki wyznaniowe' in w

def _is_mixed_ownership(wlasc: str) -> bool:
    return _is_city_owned(wlasc) and 'osoba fizyczna' in wlasc

def _is_gminna_entity(wlasc: str) -> bool:
    return not _is_city_owned(wlasc) and not _is_skarb(wlasc) and 'gminna' in wlasc.lower()


def analyze_parcel(
    attrs: ParcelAttributes,
    pow_entries: list[PowierzenieEntry],
    baza_meta: PowierzeniesMeta,
) -> ParcelScenario:
    """
    Pure function. No IO. Evaluates the 14-branch decision tree and returns a ParcelScenario.
    Branch order matches buildCard()'s if/else order exactly, preserving existing priority rules.
    """
    wlasc = attrs.wlasc
    wlad  = attrs.wlad
    klas  = attrs.klasouzytki

    is_multi  = len(pow_entries) > 1
    has_pow   = len(pow_entries) >= 1
    is_roads  = _is_roads(wlad, klas)
    is_city   = _is_city_owned(wlasc)
    is_skarb  = _is_skarb(wlasc)
    is_church = _is_church(wlasc)
    is_mixed  = _is_mixed_ownership(wlasc)
    is_gminna = _is_gminna_entity(wlasc)

    def _base(type_, label, name, note, show_wlasc, entries, confidence):
        return ParcelScenario(
            type=type_,
            manager_label=label,
            manager_name=name,
            contextual_note=note,
            show_wlasc=show_wlasc,
            pow_entries=entries,
            confidence=confidence,
            ozn_dz=attrs.ozn_dz or '\u2014',
            wlasc=wlasc or '\u2014',
            wlad=wlad or '\u2014',
            pow_ewd=attrs.pow_ewd or '\u2014',
            adres=attrs.adres or '\u2014',
            geometry=attrs.geometry,
            baza_data=baza_meta.source_date,
            baza_liczba=baza_meta.total_records,
        )

    # 1 — XLSX: multiple managers
    if is_multi:
        return _base(
            ScenarioType.XLSX_MULTI,
            'Tą działką zarządza kilka jednostek:',
            None, None, True, pow_entries, 'confirmed',
        )

    # 2 — XLSX: single manager
    if has_pow:
        return _base(
            ScenarioType.XLSX_SINGLE,
            'Tą działką zarządza',
            pow_entries[0].opis or 'brak informacji',
            None, True, pow_entries, 'confirmed',
        )

    # 3 — Road parcel, city-owned → ZDM (Art. 19 ust. 5 UoDP)
    if is_roads and is_city:
        return _base(
            ScenarioType.ZDM_CITY,
            'Tą działką zarządza',
            'Zarząd Dróg Miejskich',
            '(jednostka odpowiada za utrzymanie pasa drogowego)',
            True, [], 'inferred',
        )

    # 4 — Road parcel, non-city owner → ZDM (zarządca follows road category, not ownership)
    if is_roads and not is_city:
        return _base(
            ScenarioType.ZDM_OTHER,
            'Tą działką zarządza',
            'Zarząd Dróg Miejskich',
            'Działka ma innego właściciela, ale ZDM odpowiada za utrzymanie pasa drogowego.',
            True, [], 'inferred',
        )

    # 5 — Religious entity: owner IS the manager (Ustawa o gwarancjach wolności sumienia)
    if is_church:
        return _base(
            ScenarioType.CHURCH,
            'Właścicielem i zarządcą działki jest',
            wlasc or 'instytucja kościelna',
            '(kościoły i związki wyznaniowe zarządzają własnością samodzielnie)',
            False, [], 'inferred',
        )

    # 6 — SP + użytkowanie wieczyste (Art. 232 KC — UW holder acts independently)
    if is_skarb and 'Użytkowanie wieczyste' in wlad:
        return _base(
            ScenarioType.SKARB_UW,
            'Działka Skarbu Państwa w użytkowaniu wieczystym',
            None,
            'Grunt oddany miastu lub podmiotowi prywatnemu. Szczegóły: Wydział Gospodarki Nieruchomościami UMP.',
            True, [], 'inferred',
        )

    # 7 — SP + Gospodarowanie zasobem (Art. 11+23 UGN + Art. 92 u.s.p.)
    if is_skarb and 'Gospodarowanie zasobem' in wlad:
        return _base(
            ScenarioType.SKARB_ZASOB,
            'Działką zarządza urząd lub jednostka Skarbu Państwa',
            None,
            'Brak szczegółowych danych \u2014 w razie pytań zwróć się do Wydziału Gospodarki Nieruchomościami UMP.',
            True, [], 'inferred',
        )

    # 7b — SP + Trwały zarząd (may be state or city unit, e.g. school)
    if is_skarb and 'Trwały zarząd' in wlad:
        return _base(
            ScenarioType.SKARB_TZ,
            'Działka w trwałym zarządzie jednostki państwowej lub miejskiej',
            None,
            'W razie pytań zwróć się do Wydziału Gospodarki Nieruchomościami UMP.',
            True, [], 'inferred',
        )

    # 8 — SP fallback: catches SP + any WLAD not matched above, or SP with no WLAD
    if is_skarb:
        return _base(
            ScenarioType.SKARB_OTHER,
            'Działka należy do Skarbu Państwa',
            None,
            'Brak danych o zarządcy \u2014 w razie pytań zwróć się do Wydziału Gospodarki Nieruchomościami UMP.',
            True, [], 'inferred',
        )

    # 9a — Gminna legal entity: city-owned company not matching 'Miasto Poznań' literally
    if is_gminna:
        return _base(
            ScenarioType.GMINNA_ENTITY,
            'Działka należy do miejskiej spółki lub jednostki gminnej',
            None,
            'Właścicielem jest podmiot powiązany z Miastem Poznań. W sprawach dotyczących tej działki zwróć się do Wydziału Gospodarki Nieruchomościami UMP.',
            True, [], 'inferred',
        )

    # 9 — Private / other non-city non-state non-church owner
    if not is_city:
        return _base(
            ScenarioType.PRIVATE,
            'Tą działką zarządza',
            wlasc or 'nieznany',
            '<strong>Miasto nie jest jej właścicielem.</strong> W sprawach dotyczących tej działki możesz zwrócić się do Wydziału Gospodarki Nieruchomościami Urzędu Miasta Poznania.',
            False, [], 'inferred',
        )

    # 10 — City + private co-ownership + Gospodarowanie zasobem (typically wspólnota plot)
    if is_mixed and 'Gospodarowanie zasobem' in wlad:
        return _base(
            ScenarioType.CITY_MIXED,
            'Działka ze współwłasnością Miasta i osób prywatnych',
            None,
            'To prawdopodobnie grunt pod budynkiem wielolokalowym (wspólnota mieszkaniowa)',
            False, [], 'inferred',
        )

    # 11 — City parcel + Gospodarowanie zasobem: general city asset pool, WGN manages
    if 'Gospodarowanie zasobem' in wlad:
        return _base(
            ScenarioType.CITY_ZASOB,
            'Tą działką zarządza',
            'Wydział Gospodarki Nieruchomościami',
            None, True, [], 'inferred',
        )

    # 12 — City parcel + użytkowanie wieczyste (Art. 232 KC — UW holder quasi-owns)
    if 'Użytkowanie wieczyste' in wlad:
        return _base(
            ScenarioType.CITY_UW,
            'Działka w użytkowaniu wieczystym',
            None,
            'Grunt miejski oddany w użytkowanie wieczyste \u2014 najprawdopodobniej wspólnocie, firmie lub osobie prywatnej.',
            True, [], 'inferred',
        )

    # 13 — City parcel + Trwały zarząd (Art. 43 UGN — TZ held by public units only)
    if is_city and 'Trwały zarząd' in wlad:
        return _base(
            ScenarioType.CITY_TZ,
            'Działka w trwałym zarządzie jednostki miejskiej',
            None,
            'W razie pytań zwróć się do Wydziału Gospodarki Nieruchomościami UMP.',
            True, [], 'inferred',
        )

    # 14 — Default: unrecognised WLASC/WLAD combination
    import logging
    logging.warning('[UNKNOWN] ozn_dz=%s wlasc=%r wlad=%r klas=%r', attrs.ozn_dz, wlasc, wlad, klas)
    return _base(
        ScenarioType.UNKNOWN,
        'Tą działką zarządza',
        'brak informacji',
        None, True, [], 'inferred',
    )
