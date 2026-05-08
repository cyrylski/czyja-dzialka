import csv
import glob
import math
import os
import re
import threading
from dataclasses import dataclass, field

import requests

GEOSERVER  = 'https://wms2.geopoz.poznan.pl/geoserver/egib/ows'
PORTAL_WMS = 'https://portal.geopoz.poznan.pl/wmsegib'
MGMT_WMS   = 'https://sipuslugiogc1.geopoz.poznan.pl/gospodarka_nieruchomosciami/Service.svc/get'


@dataclass
class PowierzenieEntry:
    opis: str               # manager display name
    sygnatura: str | None = None  # concession number; None when sourced from live API


@dataclass
class ParcelAttributes:
    ozn_dz: str       # OZN_DZ — parcel identifier
    nrd: str          # NRD — registration district number
    wlasc: str        # WLASC stripped of trailing commas/whitespace
    wlad: str         # WLAD stripped of leading "- " and trailing commas
    pow_ewd: str      # POW_EWD — area in hectares (raw string from EGIB)
    adres: str        # ADRES_DZIALKI
    klasouzytki: str  # KLASOUZYTKI_EGIB from portal.geopoz.poznan.pl; '' if unavailable
    geometry: dict | None  # GeoJSON geometry from WFS, or None if WFS fails
    pow_entries: list = field(default_factory=list)  # list[PowierzenieEntry] from live API
    tz_entries: list  = field(default_factory=list)  # list[TrwalyZarzadEntry] from live API


@dataclass
class PowierzeniesMeta:
    source_date: str | None  # extracted from filename powierzenia-YYYY-MM-DD.xlsx
    total_records: int       # total unique OZN_DZ entries loaded


@dataclass
class TrwalyZarzadEntry:
    jednostka: str           # managing unit name from Jednostka column
    data_ustanowienia: str   # establishment date (may be empty)


@dataclass
class TrwalyZarzadMeta:
    source_date: str | None  # extracted from filename trwaly-zarzad-YYYY-MM-DD.csv
    total_records: int       # total unique parcel entries loaded


def _coords_to_epsg2177(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 → EPSG:2177 (CS2000 zone 6, central meridian 18°E). Pure-Python."""
    a  = 6_378_137.0
    f  = 1 / 298.257_222_101
    b  = a * (1 - f)
    e2 = 1 - (b / a) ** 2
    lon0 = math.radians(18.0)
    k0   = 0.999923
    FE   = 6_500_000.0
    FN   = 0.0

    phi = math.radians(lat)
    lam = math.radians(lon)
    dl  = lam - lon0

    N    = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t    = math.tan(phi)
    eta2 = e2 / (1 - e2) * math.cos(phi) ** 2

    n  = (a - b) / (a + b)
    A0 = 1 + n**2/4 + n**4/64
    A2 = 3/2  * (n - n**3/8)
    A4 = 15/16 * (n**2 - n**4/4)
    A6 = 35/48 * n**3
    A8 = 315/512 * n**4
    M  = a / (1 + n) * (A0*phi - A2*math.sin(2*phi) + A4*math.sin(4*phi)
                        - A6*math.sin(6*phi) + A8*math.sin(8*phi))

    x = (k0 * N * (dl * math.cos(phi)
         + dl**3/6   * math.cos(phi)**3 * (1 - t**2 + eta2)
         + dl**5/120 * math.cos(phi)**5 * (5 - 18*t**2 + t**4 + 14*eta2 - 58*t**2*eta2)))
    y = (k0 * (M + N * math.tan(phi) * (
         dl**2/2 * math.cos(phi)**2
         + dl**4/24 * math.cos(phi)**4 * (5 - t**2 + 9*eta2 + 4*eta2**2)
         + dl**6/720 * math.cos(phi)**6 * (61 - 58*t**2 + t**4))))

    return FE + x, FN + y


def _coords_to_epsg3857(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 → EPSG:3857 (Web Mercator). Used for gospodarka_nieruchomościami WMS queries."""
    x = lon * 20_037_508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) * 20_037_508.34 / math.pi
    return x, y


def _normalize_ozn_dz(ozn: str) -> str:
    """Strip leading zeros from each /‑separated segment so GEOPOZ format (03/06/1/7)
    and CSV format (3/06/1/7) resolve to the same key (3/6/1/7)."""
    return '/'.join(str(int(s)) if s.isdigit() else s for s in ozn.split('/'))


def _data_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def _find_powierzenia_file() -> tuple[str | None, str | None]:
    files = glob.glob(os.path.join(_data_dir(), 'powierzenia-*.xlsx'))
    if not files:
        return None, None
    files.sort(reverse=True)
    filepath = files[0]
    m = re.search(r'powierzenia-(\d{4}-\d{2}-\d{2})\.xlsx', os.path.basename(filepath))
    return filepath, m.group(1) if m else None


def _find_trwaly_zarzad_file() -> tuple[str | None, str | None]:
    files = glob.glob(os.path.join(_data_dir(), 'trwaly-zarzad-*.csv'))
    if not files:
        return None, None
    files.sort(reverse=True)
    filepath = files[0]
    m = re.search(r'trwaly-zarzad-(\d{4}-\d{2}-\d{2})\.csv', os.path.basename(filepath))
    return filepath, m.group(1) if m else None


def _load_powierzenia() -> tuple[dict, PowierzeniesMeta]:
    filepath, date_str = _find_powierzenia_file()
    if not filepath:
        print('[POWIERZENIA] Brak pliku powierzenia-*.xlsx')
        return {}, PowierzeniesMeta(source_date=None, total_records=0)
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {}, PowierzeniesMeta(source_date=date_str, total_records=0)
        header = [str(c).strip() if c else '' for c in rows[0]]
        try:
            idx_ozn  = header.index('OZN_DZ')
            idx_opis = header.index('OPIS')
            idx_syg  = header.index('SYGNATURA')
        except ValueError as e:
            print(f'[POWIERZENIA] Brak kolumny: {e}')
            return {}, PowierzeniesMeta(source_date=date_str, total_records=0)
        data: dict = {}
        for row in rows[1:]:
            ozn = str(row[idx_ozn]).strip() if row[idx_ozn] else None
            if not ozn or ozn == 'None':
                continue
            ozn = _normalize_ozn_dz(ozn)
            entry = PowierzenieEntry(
                opis=str(row[idx_opis]).strip() if row[idx_opis] else '',
                sygnatura=str(row[idx_syg]).strip() if row[idx_syg] else '',
            )
            data.setdefault(ozn, []).append(entry)
        print(f'[POWIERZENIA] Wczytano {len(data)} rekordów z {os.path.basename(filepath)}')
        return data, PowierzeniesMeta(source_date=date_str, total_records=len(data))
    except Exception as e:
        print(f'[POWIERZENIA] Blad wczytywania: {e}')
        return {}, PowierzeniesMeta(source_date=date_str, total_records=0)


_POWIERZENIA, _POWIERZENIA_META = _load_powierzenia()


def _load_trwaly_zarzad() -> tuple[dict, TrwalyZarzadMeta]:
    filepath, date_str = _find_trwaly_zarzad_file()
    if not filepath:
        print('[TRWALY_ZARZAD] Brak pliku trwaly-zarzad-*.csv')
        return {}, TrwalyZarzadMeta(source_date=None, total_records=0)
    try:
        data: dict = {}
        with open(filepath, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ozn = (row.get('Pełny numer działki') or '').strip()
                if not ozn:
                    continue
                ozn = _normalize_ozn_dz(ozn)
                entry = TrwalyZarzadEntry(
                    jednostka=(row.get('Jednostka') or '').strip(),
                    data_ustanowienia=(row.get('Data ustanowienia') or '').strip(),
                )
                data.setdefault(ozn, []).append(entry)
        print(f'[TRWALY_ZARZAD] Wczytano {len(data)} rekordów z {os.path.basename(filepath)}')
        return data, TrwalyZarzadMeta(source_date=date_str, total_records=len(data))
    except Exception as e:
        print(f'[TRWALY_ZARZAD] Blad wczytywania: {e}')
        return {}, TrwalyZarzadMeta(source_date=date_str, total_records=0)


_TRWALY_ZARZAD, _TRWALY_ZARZAD_META = _load_trwaly_zarzad()


def _bbox_epsg3857_from_geometry(geometry: dict) -> tuple[float, float, float, float] | None:
    """Returns (minx, miny, maxx, maxy) in EPSG:3857 from a WGS84 GeoJSON geometry."""
    if not geometry:
        return None
    gtype = geometry.get('type')
    coords = geometry.get('coordinates', [])
    if gtype == 'Polygon':
        rings = coords
    elif gtype == 'MultiPolygon':
        rings = [ring for poly in coords for ring in poly]
    else:
        return None
    all_xy = []
    for ring in rings:
        for pt in ring:
            all_xy.append(_coords_to_epsg3857(pt[0], pt[1]))
    if not all_xy:
        return None
    return (min(p[0] for p in all_xy), min(p[1] for p in all_xy),
            max(p[0] for p in all_xy), max(p[1] for p in all_xy))


def _sample_points_for_bbox(bbox_3857: tuple) -> list[tuple[float, float]]:
    """Returns 5 (x, y) EPSG:3857 points: bbox centre + 4 quadrant centres.
    Quadrant offsets are 25 % of the bbox dimensions (min 10 m) so even tiny
    parcels get spread coverage."""
    minx, miny, maxx, maxy = bbox_3857
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    ox = max((maxx - minx) * 0.25, 10.0)
    oy = max((maxy - miny) * 0.25, 10.0)
    return [
        (cx,       cy      ),
        (cx - ox,  cy + oy ),
        (cx + ox,  cy + oy ),
        (cx - ox,  cy - oy ),
        (cx + ox,  cy - oy ),
    ]


def _mgmt_query_point(layer: str, px: float, py: float,
                      normalized_ozn: str, entry_factory) -> list:
    """Single GetFeatureInfo call at EPSG:3857 point (px, py). Returns matching entries."""
    margin = 200
    params = {
        'SERVICE': 'WMS', 'VERSION': '1.3.0', 'REQUEST': 'GetFeatureInfo',
        'LAYERS': layer, 'QUERY_LAYERS': layer,
        'STYLES': '', 'INFO_FORMAT': 'application/geo+json', 'FEATURE_COUNT': '5',
        'CRS': 'EPSG:3857',
        'BBOX': f'{px - margin},{py - margin},{px + margin},{py + margin}',
        'WIDTH': 101, 'HEIGHT': 101, 'I': 50, 'J': 50,
    }
    r = requests.get(MGMT_WMS, params=params, timeout=6)
    if r.status_code != 200:
        return []
    results = []
    for feature in r.json().get('features', []):
        props = feature.get('properties', {})
        if _normalize_ozn_dz(props.get('Numer działki', '')) == normalized_ozn:
            entry = entry_factory(props)
            if entry is not None:
                results.append(entry)
    return results


def _fetch_trwaly_zarzad(lat: float, lon: float, ozn_dz: str,
                         bbox_3857: tuple | None = None) -> list:
    """Multi-point GetFeatureInfo against the Trwały_zarząd layer.
    Samples 5 points across the parcel bbox (if available) to detect all TZ zones.
    Returns [] on any error."""
    try:
        normalized = _normalize_ozn_dz(ozn_dz)
        cx, cy = _coords_to_epsg3857(lon, lat)
        points = _sample_points_for_bbox(bbox_3857) if bbox_3857 else [(cx, cy)]

        def factory(props):
            return TrwalyZarzadEntry(jednostka=props.get('Zarządca', ''),
                                     data_ustanowienia='')

        results: list = [None] * len(points)

        def _q(idx, px, py):
            try:
                results[idx] = _mgmt_query_point('Trwały_zarząd', px, py, normalized, factory)
            except Exception as e:
                print(f'[MGMT TZ pt{idx}] {e}')
                results[idx] = []

        threads = [threading.Thread(target=_q, args=(i, px, py))
                   for i, (px, py) in enumerate(points)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        seen: set = set()
        unique: list = []
        for batch in results:
            for entry in (batch or []):
                key = entry.jednostka.strip()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(entry)
        return unique
    except Exception as e:
        print(f'[MGMT TZ] exception: {e}')
        return []


def _fetch_powierzenia_live(lat: float, lon: float, ozn_dz: str,
                            bbox_3857: tuple | None = None) -> list:
    """Multi-point GetFeatureInfo against the Powierzenia layer.
    Samples 5 points across the parcel bbox (if available) to detect all management zones.
    Returns [] on any error."""
    try:
        normalized = _normalize_ozn_dz(ozn_dz)
        cx, cy = _coords_to_epsg3857(lon, lat)
        points = _sample_points_for_bbox(bbox_3857) if bbox_3857 else [(cx, cy)]

        def factory(props):
            return PowierzenieEntry(opis=props.get('Powierzono', ''), sygnatura=None)

        results: list = [None] * len(points)

        def _q(idx, px, py):
            try:
                results[idx] = _mgmt_query_point('Powierzenia', px, py, normalized, factory)
            except Exception as e:
                print(f'[MGMT POW pt{idx}] {e}')
                results[idx] = []

        threads = [threading.Thread(target=_q, args=(i, px, py))
                   for i, (px, py) in enumerate(points)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        seen: set = set()
        unique: list = []
        for batch in results:
            for entry in (batch or []):
                key = entry.opis.strip()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(entry)
        return unique
    except Exception as e:
        print(f'[MGMT POW] exception: {e}')
        return []


def _overlay_xlsx_sygnatura(api_entries: list, ozn_dz: str) -> list:
    """If the XLSX file is present and has an entry for this parcel, copy the
    sygnatura onto matching API entries. Falls back gracefully when XLSX is absent."""
    xlsx = _POWIERZENIA.get(_normalize_ozn_dz(ozn_dz), [])
    if not xlsx:
        return api_entries
    syg_map = {e.opis: e.sygnatura for e in xlsx if e.sygnatura}
    for entry in api_entries:
        if entry.sygnatura is None and entry.opis in syg_map:
            entry.sygnatura = syg_map[entry.opis]
    return api_entries


def _fetch_klasouzytki(easting: float, northing: float) -> str:
    try:
        delta = 100
        east_min, east_max = easting - delta, easting + delta
        north_min, north_max = northing - delta, northing + delta
        width = height = 800
        i = int((easting - east_min) / (east_max - east_min) * width)
        j = int((north_max - northing) / (north_max - north_min) * height)
        params = {
            'SERVICE': 'WMS', 'VERSION': '1.3.0', 'REQUEST': 'GetFeatureInfo',
            'LAYERS': 'dzialki', 'QUERY_LAYERS': 'dzialki',
            'STYLES': '', 'INFO_FORMAT': 'text/html', 'FEATURE_COUNT': '1',
            'CRS': 'EPSG:2177',
            'BBOX': f'{north_min},{east_min},{north_max},{east_max}',
            'WIDTH': width, 'HEIGHT': height, 'I': i, 'J': j,
        }
        r = requests.get(PORTAL_WMS, params=params, timeout=5)
        if r.status_code == 200:
            headers = re.findall(r'<th>([^<]+)</th>', r.text)
            values  = re.findall(r'<td>([^<]*)</td>', r.text)
            if 'KLASOUZYTKI_EGIB' in headers and values:
                idx = headers.index('KLASOUZYTKI_EGIB')
                if idx < len(values):
                    return values[idx].strip()
    except Exception as e:
        print(f'[PORTAL WMS] exception: {e}')
    return ''


def get_parcel_info(lat: float, lon: float) -> tuple[ParcelAttributes | None, str | None]:
    """
    Runs WMS GetFeatureInfo, WFS GetFeature, and portal WMS concurrently.
    Returns (ParcelAttributes, None) on success.
    Returns (None, None) when no parcel is found at that location.
    Returns (None, polish_error_message) on network/server failure.
    Field normalization (strip, rstrip(','), lstrip('- ')) happens here.
    """
    easting, northing = _coords_to_epsg2177(lon, lat)

    delta = 100
    east_min = easting - delta
    east_max = easting + delta
    north_min = northing - delta
    north_max = northing + delta
    width, height = 800, 800
    i = int((easting - east_min) / (east_max - east_min) * width)
    j = int((north_max - northing) / (north_max - north_min) * height)

    params = {
        'SERVICE': 'WMS', 'VERSION': '1.3.0', 'REQUEST': 'GetFeatureInfo',
        'LAYERS': 'dzialki_szraw_sql', 'QUERY_LAYERS': 'dzialki_szraw_sql',
        'STYLES': '', 'INFO_FORMAT': 'application/json', 'FEATURE_COUNT': '5',
        'CRS': 'EPSG:2177',
        'BBOX': f'{north_min},{east_min},{north_max},{east_max}',
        'WIDTH': width, 'HEIGHT': height, 'I': i, 'J': j,
    }

    try:
        r = requests.get(GEOSERVER, params=params, timeout=15)
    except Exception as e:
        print(f'[WMS] exception: {e}')
        return None, 'Serwer GEOPOZ chwilowo niedostępny. Spróbuj ponownie za chwilę.'

    if r.status_code != 200:
        return None, f'GeoServer zwrocil {r.status_code}'

    try:
        data = r.json()
    except Exception:
        return None, 'Nieprawidlowa odpowiedz GeoServer'

    features = data.get('features', [])
    if not features:
        return None, None  # not found — caller returns 200 with error JSON

    p = features[0]['properties']

    geometry: dict | None = None
    klasouzytki: str = ''
    pow_entries: list = []
    tz_entries: list = []
    ozn_dz_raw: str = (p.get('OZN_DZ') or '')

    # Management fetchers wait for the WFS geometry so they can sample the full parcel bbox.
    _geo_ready = threading.Event()
    _bbox_holder: list = [None]  # [tuple | None]

    def _wfs():
        nonlocal geometry
        try:
            wfs_params = {
                'SERVICE': 'WFS', 'VERSION': '2.0.0', 'REQUEST': 'GetFeature',
                'TYPENAMES': 'egib:dzialki_ewidencyjne_sql',
                'OUTPUTFORMAT': 'application/json', 'SRSNAME': 'CRS:84',
                'CQL_FILTER': f'INTERSECTS(SHAPE,SRID=4326;POINT({lon} {lat}))',
                'COUNT': '1',
            }
            wfs_r = requests.get(GEOSERVER, params=wfs_params, timeout=15)
            if wfs_r.status_code == 200:
                wfs_features = wfs_r.json().get('features', [])
                if wfs_features:
                    geometry = wfs_features[0].get('geometry')
                    _bbox_holder[0] = _bbox_epsg3857_from_geometry(geometry)
        except Exception as e:
            print(f'[WFS] exception: {e}')
        finally:
            _geo_ready.set()

    def _klas():
        nonlocal klasouzytki
        klasouzytki = _fetch_klasouzytki(easting, northing)

    def _tz():
        nonlocal tz_entries
        _geo_ready.wait(timeout=10)
        tz_entries = _fetch_trwaly_zarzad(lat, lon, ozn_dz_raw, _bbox_holder[0])

    def _pow():
        nonlocal pow_entries
        _geo_ready.wait(timeout=10)
        entries = _fetch_powierzenia_live(lat, lon, ozn_dz_raw, _bbox_holder[0])
        pow_entries = _overlay_xlsx_sygnatura(entries, ozn_dz_raw)

    threads = [
        threading.Thread(target=_wfs),
        threading.Thread(target=_klas),
        threading.Thread(target=_tz),
        threading.Thread(target=_pow),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    attrs = ParcelAttributes(
        ozn_dz=ozn_dz_raw,
        nrd=(p.get('NRD') or ''),
        wlasc=(p.get('WLASC') or '').strip().rstrip(','),
        wlad=(p.get('WLAD') or '').strip().lstrip('- ').rstrip(','),
        pow_ewd=str(p.get('POW_EWD') or ''),
        adres=(p.get('ADRES_DZIALKI') or ''),
        klasouzytki=klasouzytki,
        geometry=geometry,
        pow_entries=pow_entries,
        tz_entries=tz_entries,
    )
    return attrs, None


def _polygon_sample_point(geometry: dict) -> tuple[float, float] | None:
    """Returns a (lon, lat) point near the centre of a Polygon/MultiPolygon
    suitable for klasouzytki sampling. Falls back to first vertex on degenerate input."""
    if not geometry:
        return None
    coords = geometry.get('coordinates') or []
    if geometry.get('type') == 'MultiPolygon':
        if not coords or not coords[0] or not coords[0][0]:
            return None
        ring = coords[0][0]
    elif geometry.get('type') == 'Polygon':
        if not coords or not coords[0]:
            return None
        ring = coords[0]
    else:
        return None
    if not ring:
        return None
    sx = sum(p[0] for p in ring) / len(ring)
    sy = sum(p[1] for p in ring) / len(ring)
    return sx, sy


def _ozn_cql_variants(ozn_dz: str) -> list[str]:
    """GEOPOZ stores OZN_DZ with inconsistent leading-zero padding (e.g. '03/06/1/7').
    The slug arriving from the URL is normalised. Generate all 2^n combinations of
    segments padded to width 2 vs as-is, so the CQL filter matches whichever form
    the layer actually holds."""
    parts = ozn_dz.split('/')
    variants: set[str] = set()
    for mask in range(1 << len(parts)):
        out = []
        for i, p in enumerate(parts):
            if (mask >> i) & 1 and p.isdigit() and len(p) < 2:
                out.append(p.zfill(2))
            else:
                out.append(p)
        variants.add('/'.join(out))
    return sorted(variants)


def get_parcel_info_by_ozn(ozn_dz: str) -> tuple[ParcelAttributes | None, str | None]:
    """Resolves a parcel identifier (e.g. '3/6/1/7' or '03/06/1/7') to full
    ParcelAttributes. WFS exposes only egib:dzialki_ewidencyjne_sql (geometry +
    OZN_DZIALKI), so we fetch the parcel's polygon by OZN_DZIALKI, take a point
    inside it, and delegate to get_parcel_info(lat, lon) — the same path used
    for map clicks, which yields ownership data via WMS GetFeatureInfo."""
    ozn_dz = (ozn_dz or '').strip()
    if not ozn_dz:
        return None, None
    variants = _ozn_cql_variants(_normalize_ozn_dz(ozn_dz))
    cql = ' OR '.join(f"OZN_DZIALKI='{v}'" for v in variants)

    wfs_params = {
        'SERVICE': 'WFS', 'VERSION': '2.0.0', 'REQUEST': 'GetFeature',
        'TYPENAMES': 'egib:dzialki_ewidencyjne_sql',
        'OUTPUTFORMAT': 'application/json', 'SRSNAME': 'CRS:84',
        'CQL_FILTER': cql,
        'COUNT': '1',
    }
    try:
        r = requests.get(GEOSERVER, params=wfs_params, timeout=15)
    except Exception as e:
        print(f'[WFS by-ozn] exception: {e}')
        return None, 'Serwer GEOPOZ chwilowo niedostępny. Spróbuj ponownie za chwilę.'

    if r.status_code != 200:
        return None, f'GeoServer zwrocil {r.status_code}'

    try:
        data = r.json()
    except Exception:
        return None, 'Nieprawidlowa odpowiedz GeoServer'

    features = data.get('features', [])
    if not features:
        return None, None

    geometry = features[0].get('geometry')
    sample = _polygon_sample_point(geometry) if geometry else None
    if sample is None:
        return None, None

    lon, lat = sample
    return get_parcel_info(lat, lon)


def get_powierzenia_meta() -> PowierzeniesMeta:
    """Returns XLSX file date and record count for footer display; None values when file absent."""
    return _POWIERZENIA_META


def get_trwaly_zarzad_meta() -> TrwalyZarzadMeta:
    """Returns CSV file date and record count; None values when file absent."""
    return _TRWALY_ZARZAD_META
