import glob
import math
import os
import re
import threading
from dataclasses import dataclass

import requests

GEOSERVER  = 'https://wms2.geopoz.poznan.pl/geoserver/egib/ows'
PORTAL_WMS = 'https://portal.geopoz.poznan.pl/wmsegib'


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


@dataclass
class PowierzenieEntry:
    opis: str      # manager display name from OPIS column
    sygnatura: str  # concession number from SYGNATURA column


@dataclass
class PowierzeniesMeta:
    source_date: str | None  # extracted from filename powierzenia-YYYY-MM-DD.xlsx
    total_records: int       # total unique OZN_DZ entries loaded


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


def _find_powierzenia_file() -> tuple[str | None, str | None]:
    base = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(os.path.join(base, 'powierzenia-*.xlsx'))
    if not files:
        return None, None
    files.sort(reverse=True)
    filepath = files[0]
    m = re.search(r'powierzenia-(\d{4}-\d{2}-\d{2})\.xlsx', os.path.basename(filepath))
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
        except Exception as e:
            print(f'[WFS] exception: {e}')

    def _klas():
        nonlocal klasouzytki
        klasouzytki = _fetch_klasouzytki(easting, northing)

    t_wfs  = threading.Thread(target=_wfs)
    t_klas = threading.Thread(target=_klas)
    t_wfs.start(); t_klas.start()
    t_wfs.join();  t_klas.join()

    attrs = ParcelAttributes(
        ozn_dz=(p.get('OZN_DZ') or ''),
        nrd=(p.get('NRD') or ''),
        wlasc=(p.get('WLASC') or '').strip().rstrip(','),
        wlad=(p.get('WLAD') or '').strip().lstrip('- ').rstrip(','),
        pow_ewd=str(p.get('POW_EWD') or ''),
        adres=(p.get('ADRES_DZIALKI') or ''),
        klasouzytki=klasouzytki,
        geometry=geometry,
    )
    return attrs, None


def get_powierzenia(ozn_dz: str) -> list[PowierzenieEntry]:
    """Looks up ozn_dz in the in-memory POWIERZENIA dict loaded at startup."""
    return _POWIERZENIA.get(ozn_dz, [])


def get_powierzenia_meta() -> PowierzeniesMeta:
    """Returns date and record count for footer display in the UI."""
    return _POWIERZENIA_META
