import dataclasses
import logging
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

import geopoz_client
import parcel_analyzer

APP_VERSION = 'v1.2.0'
APP_UPDATE_DATE = '2026-05-07'

app = Flask(__name__, static_folder='.')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
_analytics = logging.getLogger('analytics')

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=['200/minute', '5000/day'],
    headers_enabled=True,
)


def _mask_ip(ip):
    if not ip:
        return ''
    if ':' in ip:
        parts = ip.split(':')
        return ':'.join(parts[:4]) + '::'
    parts = ip.split('.')
    if len(parts) == 4:
        return '.'.join(parts[:3]) + '.0'
    return ip


def _is_same_origin():
    expected_host = request.host
    origin = request.headers.get('Origin', '')
    if origin:
        return origin.split('://', 1)[-1].split('/', 1)[0] == expected_host
    referer = request.headers.get('Referer', '')
    if referer:
        return referer.split('://', 1)[-1].split('/', 1)[0] == expected_host
    return False


def _log_dzialka(ozn_dz, source='map'):
    ip = _mask_ip(request.remote_addr or '')
    ua = request.headers.get('User-Agent', '')[:200]
    _analytics.info('lookup ozn=%s source=%s ip=%s ua=%r', ozn_dz, source, ip, ua)


@app.route('/api/version')
@limiter.exempt
def version():
    return jsonify({'version': APP_VERSION, 'app_update_date': APP_UPDATE_DATE})


@app.route('/')
@limiter.exempt
def index():
    return send_from_directory('.', 'index.html')


@app.route('/dzialka/<slug>')
@limiter.exempt
def dzialka_spa(slug):
    return send_from_directory('.', 'index.html')


@app.route('/dzialka')
@limiter.limit('30/minute;600/day')
def dzialka():
    try:
        lat = float(request.args['lat'])
        lon = float(request.args['lon'])
    except (KeyError, ValueError):
        return jsonify({'error': 'Podaj lat i lon'}), 400

    attrs, error = geopoz_client.get_parcel_info(lat, lon)
    if error:
        return jsonify({'error': error}), 502
    if attrs is None:
        return jsonify({'error': 'Nie znaleziono dzialki w tym miejscu'})

    pow_entries = geopoz_client.get_powierzenia(attrs.ozn_dz)
    meta        = geopoz_client.get_powierzenia_meta()
    tz_entries  = geopoz_client.get_trwaly_zarzad(attrs.ozn_dz)
    tz_meta     = geopoz_client.get_trwaly_zarzad_meta()
    scenario    = parcel_analyzer.analyze_parcel(attrs, pow_entries, meta, tz_entries, tz_meta)

    _log_dzialka(scenario.ozn_dz, source='map')

    return jsonify(dataclasses.asdict(scenario))


@app.route('/api/dzialka_by_ozn')
@limiter.limit('30/minute;600/day')
def dzialka_by_ozn():
    ozn = (request.args.get('ozn') or '').strip()
    if not ozn:
        return jsonify({'error': 'Brak parametru ozn'}), 400

    attrs, error = geopoz_client.get_parcel_info_by_ozn(ozn)
    if error:
        return jsonify({'error': error}), 502
    if attrs is None:
        return jsonify({'error': 'Użyty adres działki jest niepoprawny'}), 404

    pow_entries = geopoz_client.get_powierzenia(attrs.ozn_dz)
    meta        = geopoz_client.get_powierzenia_meta()
    tz_entries  = geopoz_client.get_trwaly_zarzad(attrs.ozn_dz)
    tz_meta     = geopoz_client.get_trwaly_zarzad_meta()
    scenario    = parcel_analyzer.analyze_parcel(attrs, pow_entries, meta, tz_entries, tz_meta)

    _log_dzialka(scenario.ozn_dz, source='share')

    return jsonify(dataclasses.asdict(scenario))


@app.route('/api/log_share', methods=['POST'])
@limiter.limit('10/minute;200/day')
def log_share():
    if not _is_same_origin():
        return jsonify({'error': 'forbidden'}), 403
    payload = request.get_json(silent=True) or {}
    ozn = (payload.get('ozn') or '').strip()
    if not ozn:
        return jsonify({'error': 'Brak ozn'}), 400
    _log_dzialka(ozn, source='share')
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
