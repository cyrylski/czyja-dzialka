from flask import Flask, request, jsonify, send_from_directory
import requests
import uuid
import os

app = Flask(__name__, static_folder='.')

SESSION_COOKIES = {}

def get_session():
    """Inicjuje sesję GEOPOZ jeśli nie istnieje."""
    global SESSION_COOKIES
    if not SESSION_COOKIES:
        uid = str(uuid.uuid4())
        SESSION_COOKIES = {
            '__wc_user_name': uid,
            'GPZ_cookie': '{"GPZ_cookie_consent":"yes","lang":"pl"}'
        }
        # Inicjuj sesję ASP.NET
        r = requests.get(
            'https://sipmapy.geopoz.poznan.pl/sipportal/SessionManager.WebClient.ashx',
            params={'action': 'checkSession', 'mapStateId': 'map'},
            cookies=SESSION_COOKIES,
            timeout=10
        )
        for k, v in r.cookies.items():
            SESSION_COOKIES[k] = v
    return SESSION_COOKIES


def coords_to_epsg2177(lon, lat):
    """Konwertuje WGS84 (lon, lat) -> EPSG:2177 (easting, northing)."""
    from pyproj import Transformer
    t = Transformer.from_crs('EPSG:4326', 'EPSG:2177', always_xy=True)
    easting, northing = t.transform(lon, lat)
    return easting, northing


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

    # Buduj bbox 200x200m wokół punktu
    delta_e = 100
    delta_n = 100
    east_min = easting - delta_e
    east_max = easting + delta_e
    north_min = northing - delta_n
    north_max = northing + delta_n

    width, height = 800, 800
    # i = kolumna kliknięcia, j = wiersz kliknięcia (od góry)
    i = int((easting - east_min) / (east_max - east_min) * width)
    j = int((north_max - northing) / (north_max - north_min) * height)

    bbox = [north_min, east_min, north_max, east_max]

    payload = {
        "items": [
            {
                "mapServiceId": "75946dc1-b0ce-4264-b26a-02db99542ac4",
                "itemDefinitionIds": ["dzialki"],
                "additionalData": {"imageFormat": "image/png", "forceInfoFormat": False, "vspm": "{}"}
            },
            {
                "mapServiceId": "447df96f-b25e-41e4-a7dc-b440526e92fa",
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

    cookies = get_session()
    headers = {
        'content-type': 'application/json',
        'referer': 'https://sipmapy.geopoz.poznan.pl/sipportal/',
        'user-agent': 'Mozilla/5.0'
    }

    r = requests.post(
        'https://sipmapy.geopoz.poznan.pl/sipportal/api/stateful/featureInfo',
        json=payload,
        cookies=cookies,
        headers=headers,
        timeout=15
    )

    if r.status_code \!= 200:
        return jsonify({'error': f'GEOPOZ zwrócił {r.status_code}'}), 502

    items = r.json()
    result = parse_feature_info(items)
    return jsonify(result)


def parse_feature_info(items):
    """Parsuje HTML z featureInfo i zwraca słownik z danymi działki."""
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

    result = {}
    for item in items:
        title = item.get('title', '')
        html = item.get('html', '')
        p = TableParser()
        p.feed(html)
        if p.current_row and len(p.current_row) == len(p.headers):
            p.rows.append(dict(zip(p.headers, p.current_row)))
        if p.rows:
            result[title] = p.rows

    # Spłaszcz do jednego słownika priorytetyzując szraw (ma WLASC/WLAD)
    flat = {}
    for title, rows in result.items():
        for row in rows:
            flat.update(row)

    if not flat:
        return {'error': 'Nie znaleziono działki w tym miejscu'}

    # Zwróć tylko kluczowe pola
    return {
        'ozn_dz':     flat.get('OZN_DZ', '—'),
        'nrd':        flat.get('NRD', flat.get('NUMER_DZIALKI', '—')),
        'wlasc':      flat.get('WLASC', '—'),
        'wlad':       flat.get('WLAD', '—'),
        'pow_ewd':    flat.get('POW_EWD', flat.get('POLE_EWIDENCYJNE', '—')),
        'obreby':     flat.get('NAZWA_OBREBU', '—'),
        'kw':         flat.get('KW', '—'),
        'klasa':      flat.get('KLASOUZYTKI_EGIB', '—'),
        'adres':      flat.get('ADRES_DZIALKI', '—'),
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
