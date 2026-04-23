from flask import Flask, request, jsonify, send_from_directory
import requests
import os
import glob
import re
import smtplib
import threading
from email.mime.text import MIMEText
from datetime import datetime

app = Flask(__name__, static_folder='.')

GEOSERVER   = 'https://wms2.geopoz.poznan.pl/geoserver/egib/ows'
PORTAL_WMS  = 'https://portal.geopoz.poznan.pl/wmsegib'

# --- Powierzenia ---

def find_powierzenia_file():
    """Znajdź plik powierzenia-*.xlsx w katalogu aplikacji."""
    base = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(os.path.join(base, 'powierzenia-*.xlsx'))
    if not files:
        return None, None
    # Wybierz najnowszy plik
    files.sort(reverse=True)
    filepath = files[0]
    # Wyciągnij datę z nazwy pliku (powierzenia-YYYY-MM-DD.xlsx)
    m = re.search(r'powierzenia-(\d{4}-\d{2}-\d{2})\.xlsx', os.path.basename(filepath))
    date_str = m.group(1) if m else None
    return filepath, date_str


def load_powierzenia():
    """Wczytaj plik XLSX do słownika {OZN_DZ: {opis, sygnatura}}."""
    filepath, date_str = find_powierzenia_file()
    if not filepath:
        print("[POWIERZENIA] Brak pliku powierzenia-*.xlsx")
        return {}, None
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        # Pierwsza kolumna: nagłówki
        if not rows:
            return {}, date_str
        header = [str(c).strip() if c else '' for c in rows[0]]
        try:
            idx_ozn  = header.index('OZN_DZ')
            idx_opis = header.index('OPIS')
            idx_syg  = header.index('SYGNATURA')
        except ValueError as e:
            print(f"[POWIERZENIA] Brak kolumny: {e}")
            return {}, date_str
        data = {}
        for row in rows[1:]:
            ozn = str(row[idx_ozn]).strip() if row[idx_ozn] else None
            if not ozn or ozn == 'None':
                continue
            entry = {
                'opis':      str(row[idx_opis]).strip() if row[idx_opis] else '',
                'sygnatura': str(row[idx_syg]).strip()  if row[idx_syg]  else '',
            }
            if ozn not in data:
                data[ozn] = []
            data[ozn].append(entry)
        print(f"[POWIERZENIA] Wczytano {len(data)} rekordów z {os.path.basename(filepath)}")
        return data, date_str
    except Exception as e:
        print(f"[POWIERZENIA] Blad wczytywania: {e}")
        return {}, date_str


# Wczytaj przy starcie
POWIERZENIA, POWIERZENIA_DATA = load_powierzenia()


# --- Helpers ---

def get_klasouzytki(easting, northing):
    """Query portal.geopoz.poznan.pl/wmsegib for KLASOUZYTKI_EGIB land-use code (e.g. 'dr' for roads)."""
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


def coords_to_epsg2177(lon, lat):
    """WGS84 → EPSG:2177 (CS2000 zone 7, central meridian 21°E).
    Pure-Python Transverse Mercator — no pyproj/PROJ required."""
    import math
    # GRS80 ellipsoid
    a  = 6_378_137.0
    f  = 1 / 298.257_222_101
    b  = a * (1 - f)
    e2 = 1 - (b / a) ** 2
    e  = math.sqrt(e2)
    # EPSG:2177 = ETRF2000-PL / CS2000/18  (zone 6, lon0=18°, k=0.999923, FE=6500000)
    lon0 = math.radians(18.0)
    k0   = 0.999923
    FE   = 6_500_000.0
    FN   = 0.0

    phi = math.radians(lat)
    lam = math.radians(lon)
    dl  = lam - lon0

    N   = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t   = math.tan(phi)
    eta2 = e2 / (1 - e2) * math.cos(phi) ** 2

    # Meridional arc
    n  = (a - b) / (a + b)
    A0 = 1 + n**2/4 + n**4/64
    A2 = 3/2  * (n - n**3/8)
    A4 = 15/16 * (n**2 - n**4/4)
    A6 = 35/48 * n**3
    A8 = 315/512 * n**4
    M  = a / (1 + n) * (A0*phi - A2*math.sin(2*phi) + A4*math.sin(4*phi)
                        - A6*math.sin(6*phi) + A8*math.sin(8*phi))

    # TM series (6th-order Helmert)
    x = (k0 * N * (dl * math.cos(phi)
         + dl**3/6   * math.cos(phi)**3 * (1 - t**2 + eta2)
         + dl**5/120 * math.cos(phi)**5 * (5 - 18*t**2 + t**4 + 14*eta2 - 58*t**2*eta2)))
    y = (k0 * (M + N * math.tan(phi) * (
         dl**2/2 * math.cos(phi)**2
         + dl**4/24 * math.cos(phi)**4 * (5 - t**2 + 9*eta2 + 4*eta2**2)
         + dl**6/720 * math.cos(phi)**6 * (61 - 58*t**2 + t**4))))

    easting  = FE + x
    northing = FN + y
    return easting, northing


_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analytics.log')

_EMAIL_FROM = os.environ.get('LOG_EMAIL_FROM', '')
_EMAIL_PASS = os.environ.get('LOG_EMAIL_PASSWORD', '')
_EMAIL_TO   = os.environ.get('LOG_EMAIL_TO', '')


def _geo_lookup(ip):
    try:
        r = requests.get(
            f'http://ip-api.com/json/{ip}',
            params={'fields': 'city,country'},
            timeout=2,
        )
        if r.status_code == 200:
            d = r.json()
            city, country = d.get('city', ''), d.get('country', '')
            return f"{city}, {country}".strip(', ')
    except Exception:
        pass
    return ''


def _send_log_email(ozn_dz, ip, ua, ts):
    if not all([_EMAIL_FROM, _EMAIL_PASS, _EMAIL_TO]):
        return
    location = _geo_lookup(ip)
    loc_str = f'  ({location})' if location else ''
    body = (
        f"Czas:      {ts}\n"
        f"Działka:   {ozn_dz}\n"
        f"IP:        {ip}{loc_str}\n"
        f"Urządzenie: {ua}\n"
    )
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f'[działka] {ozn_dz}'
    msg['From'] = _EMAIL_FROM
    msg['To'] = _EMAIL_TO
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.starttls()
            s.login(_EMAIL_FROM, _EMAIL_PASS)
            s.sendmail(_EMAIL_FROM, _EMAIL_TO, msg.as_string())
    except Exception as e:
        print(f'[EMAIL] Błąd wysyłki: {e}')


def _log_dzialka(ozn_dz):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    forwarded = request.headers.get('X-Forwarded-For', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.remote_addr
    ua = request.headers.get('User-Agent', '')
    with open(_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f'| {ts} | {ozn_dz} | {ip} | {ua} |\n')
    threading.Thread(target=_send_log_email, args=(ozn_dz, ip, ua, ts), daemon=True).start()


# --- Routes ---

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/dzialka')
def dzialka():
    try:
        lat = float(request.args['lat'])
        lon = float(request.args['lon'])
    except (KeyError, ValueError):
        return jsonify({'error': 'Podaj lat i lon'}), 400

    easting, northing = coords_to_epsg2177(lon, lat)

    delta = 100
    east_min = easting - delta
    east_max = easting + delta
    north_min = northing - delta
    north_max = northing + delta
    width, height = 800, 800
    i = int((easting - east_min) / (east_max - east_min) * width)
    j = int((north_max - northing) / (north_max - north_min) * height)

    params = {
        'SERVICE': 'WMS',
        'VERSION': '1.3.0',
        'REQUEST': 'GetFeatureInfo',
        'LAYERS': 'dzialki_szraw_sql',
        'QUERY_LAYERS': 'dzialki_szraw_sql',
        'STYLES': '',
        'INFO_FORMAT': 'application/json',
        'FEATURE_COUNT': '5',
        'CRS': 'EPSG:2177',
        'BBOX': f'{north_min},{east_min},{north_max},{east_max}',
        'WIDTH': width,
        'HEIGHT': height,
        'I': i,
        'J': j,
    }

    try:
        r = requests.get(GEOSERVER, params=params, timeout=15)
    except Exception as e:
        print(f"[WMS] exception: {e}")
        return jsonify({'error': 'Serwer GEOPOZ chwilowo niedostępny. Spróbuj ponownie za chwilę.'}), 502

    if r.status_code != 200:
        return jsonify({'error': f'GeoServer zwrocil {r.status_code}'}), 502

    try:
        data = r.json()
    except Exception:
        return jsonify({'error': 'Nieprawidlowa odpowiedz GeoServer'}), 502

    features = data.get('features', [])
    if not features:
        return jsonify({'error': 'Nie znaleziono dzialki w tym miejscu'})

    p = features[0]['properties']
    ozn_dz = p.get('OZN_DZ', '')

    _log_dzialka(ozn_dz)

    pow_list = POWIERZENIA.get(ozn_dz, [])

    # WFS (geometry) and portal KLASOUZYTKI_EGIB lookup run concurrently.
    geometry     = None
    klasouzytki  = ''

    def _fetch_wfs():
        nonlocal geometry
        try:
            wfs_params = {
                'SERVICE':      'WFS',
                'VERSION':      '2.0.0',
                'REQUEST':      'GetFeature',
                'TYPENAMES':    'egib:dzialki_ewidencyjne_sql',
                'OUTPUTFORMAT': 'application/json',
                'SRSNAME':      'CRS:84',
                'CQL_FILTER':   f'INTERSECTS(SHAPE,SRID=4326;POINT({lon} {lat}))',
                'COUNT':        '1',
            }
            wfs_r = requests.get(GEOSERVER, params=wfs_params, timeout=15)
            if wfs_r.status_code == 200:
                wfs_features = wfs_r.json().get('features', [])
                if wfs_features:
                    geometry = wfs_features[0].get('geometry')
        except Exception as e:
            print(f'[WFS] exception: {e}')

    def _fetch_klasouzytki():
        nonlocal klasouzytki
        klasouzytki = get_klasouzytki(easting, northing)

    t_wfs  = threading.Thread(target=_fetch_wfs)
    t_klas = threading.Thread(target=_fetch_klasouzytki)
    t_wfs.start(); t_klas.start()
    t_wfs.join();  t_klas.join()

    result = {
        'ozn_dz':       ozn_dz or '\u2014',
        'nrd':          p.get('NRD', '\u2014'),
        'wlasc':        (p.get('WLASC') or '').strip().rstrip(',') or '\u2014',
        'wlad':         (p.get('WLAD') or '').strip().lstrip('- ').rstrip(',') or '\u2014',
        'klasouzytki':  klasouzytki,
        'pow_ewd':      str(p.get('POW_EWD', '\u2014')),
        'adres':        p.get('ADRES_DZIALKI', '\u2014'),
        'pow_list':     pow_list,
        'baza_data':    POWIERZENIA_DATA or '',
        'baza_liczba':  len(POWIERZENIA),
    }
    if geometry:
        result['geometry'] = geometry
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
