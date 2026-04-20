from flask import Flask, request, jsonify, send_from_directory
import requests
import os

app = Flask(__name__, static_folder='.')

GEOSERVER = 'https://wms2.geopoz.poznan.pl/geoserver/egib/ows'


def coords_to_epsg2177(lon, lat):
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
        return jsonify({'error': f'Blad polaczenia: {e}'}), 502

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
    return jsonify({
        'ozn_dz':  p.get('OZN_DZ', '\u2014'),
        'nrd':     p.get('NRD', '\u2014'),
        'wlasc':   (p.get('WLASC') or '').strip().rstrip(',') or '\u2014',
        'wlad':    (p.get('WLAD') or '').strip().lstrip('- ').rstrip(',') or '\u2014',
        'pow_ewd': str(p.get('POW_EWD', '\u2014')),
        'adres':   p.get('ADRES_DZIALKI', '\u2014'),
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
