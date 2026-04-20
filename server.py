from flask import Flask, request, jsonify, send_from_directory
import requests
import uuid
import os

app = Flask(__name__, static_folder='.')

# Stan sesji
SESSION = {'cookies': {}}

HEADERS = {
    'content-type': 'application/json',
    'referer': 'https://sipmapy.geopoz.poznan.pl/sipportal/',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'origin': 'https://sipmapy.geopoz.poznan.pl',
}

# ID serwisów są stałe — wbudowane w JS strony sipportal
SERVICE_BASE = '75946dc1-b0ce-4264-b26a-02db99542ac4'   # dzialki (podstawowe dane)
SERVICE_EGIB = '447df96f-b25e-41e4-a7dc-b440526e92fa'   # dzialki_szraw_sql (WLASC/WLAD)


def init_session():
    """Inicjuje sesję GEOPOZ — pobiera ASP.NET_SessionId i csrfCookie."""
    uid = str(uuid.uuid4())
    cookies = {
        '__wc_user_name': uid,
        'GPZ_cookie': '{"GPZ_cookie_consent":"yes","lang":"pl"}'
    }
    # Krok 1: checkSession — dostajemy ASP.NET_SessionId
    r = requests.get(
        'https://sipmapy.geopoz.poznan.pl/sipportal/SessionManager.WebClient.ashx',
        params={'action': 'checkSession', 'mapStateId': 'map'},
        cookies=cookies,
        headers={'user-agent': HEADERS['user-agent']},
        timeout=10
    )
    for k, v in r.cookies.items():
        cookies[k] = v
    print(f"[SESSION] po checkSession: {list(cookies.keys())}")
    # Krok 2: pobierz stronę główną — ustawia __wc_csrfCookie
    r2 = requests.get(
        'https://sipmapy.geopoz.poznan.pl/sipportal/',
        cookies=cookies,
        headers={'user-agent': HEADERS['user-agent']},
        timeout=10,
        allow_redirects=True
    )
    for k, v in r2.cookies.items():
        cookies[k] = v
    print(f"[SESSION] po stronie glownej: {list(cookies.keys())}")
    SESSION['cookies'] = cookies
    return cookies


def get_session():
    if not SESSION['cookies']:
        init_session()
    return SESSION['cookies']


def coords_to_epsg2177(lon, lat):
    from pyproj import Transformer
    t = Transformer.from_crs('EPSG:4326', 'EPSG:2177', always_xy=True)
    easting, northing = t.transform(lon, lat)
    return easting, northing


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/debug-session')
def debug_session():
    cookies = get_session()
    return jsonify({
        'cookie_keys': list(cookies.keys()),
        'service_base': SERVICE_BASE,
        'service_egib': SERVICE_EGIB,
    })


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
    bbox = [north_min, east_min, north_max, east_max]

    cookies = get_session()

    payload = {
        "items": [
            {
                "mapServiceId": SERVICE_BASE,
                "itemDefinitionIds": ["dzialki"],
                "additionalData": {"imageFormat": "image/png", "forceInfoFormat": False, "vspm": "{}"}
            },
            {
                "mapServiceId": SERVICE_EGIB,
                "itemDefinitionIds": ["dzialki_szraw_sql"],
                "additionalData": {"imageFormat": "image/png", "forceInfoFormat": False, "vspm": "{}"}
            }
        ],
        "i": i,
        "j": j,
        "crsId": "EPSG:2177",
        "format": "text/html",
        "count": 10,
        "bbox": bbox,
        "width": width,
        "height": height
    }

    r = requests.post(
        'https://sipmapy.geopoz.poznan.pl/sipportal/api/stateful/featureInfo',
        json=payload,
        cookies=cookies,
        headers=HEADERS,
        timeout=15
    )

    if r.status_code != 200:
        print(f"[ERROR] featureInfo status: {r.status_code}, body: {r.text[:500]}")
        # Spróbuj odświeżyć sesję i ponów
        SESSION['cookies'] = {}  # reset sesji przy następnym zapytaniu
        return jsonify({'error': f'Blad GEOPOZ ({r.status_code}). Odswież stronę i spróbuj ponownie.'}), 502

    try:
        data = r.json()
    except Exception as e:
        print(f"[ERROR] JSON parse: {e}, raw: {r.text[:500]}")
        return jsonify({'error': 'Nieprawidłowa odpowiedź serwera'}), 502

    result = parse_feature_info(data)
    return jsonify(result)


def parse_feature_info(items):
    from html.parser import HTMLParser

    class TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.headers = []
            self.rows = []
            self.in_th = False
            self.in_td = False
            self.current_row = []
            self.current_data = ''

        def handle_starttag(self, tag, attrs):
            if tag == 'th': self.in_th = True; self.current_data = ''
            if tag == 'td': self.in_td = True; self.current_data = ''
            if tag == 'tr' and self.current_row:
                if self.headers and len(self.current_row) == len(self.headers):
                    self.rows.append(dict(zip(self.headers, self.current_row)))
                self.current_row = []

        def handle_endtag(self, tag):
            if tag == 'th':
                self.headers.append(self.current_data.strip())
                self.in_th = False
            if tag == 'td':
                self.current_row.append(self.current_data.strip())
                self.in_td = False

        def handle_data(self, data):
            if self.in_th or self.in_td:
                self.current_data += data

    flat = {}
    for item in items:
        html = item.get('html', '')
        p = TableParser()
        p.feed(html)
        if p.current_row and len(p.current_row) == len(p.headers):
            p.rows.append(dict(zip(p.headers, p.current_row)))
        for row in p.rows:
            flat.update(row)

    if not flat:
        return {'error': 'Nie znaleziono działki w tym miejscu'}

    return {
        'ozn_dz':  flat.get('OZN_DZ', '\u2014'),
        'nrd':     flat.get('NRD', flat.get('NUMER_DZIALKI', '\u2014')),
        'wlasc':   flat.get('WLASC', '\u2014'),
        'wlad':    flat.get('WLAD', '\u2014'),
        'pow_ewd': flat.get('POW_EWD', flat.get('POLE_EWIDENCYJNE', '\u2014')),
        'obreby':  flat.get('NAZWA_OBREBU', '\u2014'),
        'kw':      flat.get('KW', '\u2014'),
        'klasa':   flat.get('KLASOUZYTKI_EGIB', '\u2014'),
        'adres':   flat.get('ADRES_DZIALKI', '\u2014'),
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
