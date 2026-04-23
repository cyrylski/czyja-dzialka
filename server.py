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

GEOSERVER = 'https://wms2.geopoz.poznan.pl/geoserver/egib/ows'

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

def coords_to_epsg2177(lon, lat):
    from pyproj import Transformer
    t = Transformer.from_crs('EPSG:4326', 'EPSG:2177', always_xy=True)
    easting, northing = t.transform(lon, lat)
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

    # WFS — pobierz geometrię działki przez przecięcie z punktem kliknięcia.
    # Używamy SRID=4326;POINT w EWKT, bo CQL_FILTER domyślnie przyjmuje CRS warstwy (EPSG:2177).
    geometry = None
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
            wfs_data = wfs_r.json()
            wfs_features = wfs_data.get('features', [])
            if wfs_features:
                geometry = wfs_features[0].get('geometry')
    except Exception as e:
        print(f"[WFS] exception: {e}")

    result = {
        'ozn_dz':       ozn_dz or '\u2014',
        'nrd':          p.get('NRD', '\u2014'),
        'wlasc':        (p.get('WLASC') or '').strip().rstrip(',') or '\u2014',
        'wlad':         (p.get('WLAD') or '').strip().lstrip('- ').rstrip(',') or '\u2014',
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
