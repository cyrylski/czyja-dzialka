import atexit
import dataclasses
import logging
import os
import smtplib
import threading
from collections import deque
from datetime import datetime, timezone
from email.mime.text import MIMEText

from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

import geopoz_client
import parcel_analyzer

APP_VERSION = 'v1.6.2'
APP_UPDATE_DATE = '2026-05-10'

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

_EMAIL_FROM = os.environ.get('LOG_EMAIL_FROM', '')
_EMAIL_PASS = os.environ.get('LOG_EMAIL_PASSWORD', '')
_EMAIL_TO   = os.environ.get('LOG_EMAIL_TO', '')

_BUFFER_MAX = 1000
_buffer: deque = deque(maxlen=_BUFFER_MAX)
_buffer_lock = threading.Lock()
_flushed = False


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
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    _analytics.info('lookup ozn=%s source=%s ip=%s ua=%r', ozn_dz, source, ip, ua)
    with _buffer_lock:
        _buffer.append({'ts': ts, 'ozn': ozn_dz, 'source': source, 'ip': ip, 'ua': ua})


def _flush_buffer_email():
    """Drains the in-memory event buffer into a single SMTP message. Intended
    to fire on graceful machine shutdown (atexit) — Fly.io's idle-stop sends
    SIGTERM, gunicorn lets the worker exit cleanly, and atexit then runs."""
    global _flushed
    if _flushed:
        return
    _flushed = True
    if not all([_EMAIL_FROM, _EMAIL_PASS, _EMAIL_TO]):
        return
    with _buffer_lock:
        events = list(_buffer)
        _buffer.clear()
    if not events:
        return
    lines = [
        f"| {e['ts']} | {e['source']}-{e['ozn']} | {e['ip']} | {e['ua']} |"
        for e in events
    ]
    body = (
        f"Bufor zdarzeń przed wyłączeniem maszyny ({len(events)} wpisów):\n\n"
        + '\n'.join(lines)
        + '\n'
    )
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f'[działka] digest x{len(events)}'
    msg['From'] = _EMAIL_FROM
    msg['To'] = _EMAIL_TO
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as s:
            s.starttls()
            s.login(_EMAIL_FROM, _EMAIL_PASS)
            s.sendmail(_EMAIL_FROM, _EMAIL_TO, msg.as_string())
        _analytics.info('flushed %d events via email', len(events))
    except Exception as e:
        _analytics.warning('flush email failed: %s', e)


atexit.register(_flush_buffer_email)


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

    scenario = parcel_analyzer.analyze_parcel(
        attrs, attrs.pow_entries, geopoz_client.get_powierzenia_meta(),
        attrs.tz_entries, geopoz_client.get_trwaly_zarzad_meta(),
    )

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

    scenario = parcel_analyzer.analyze_parcel(
        attrs, attrs.pow_entries, geopoz_client.get_powierzenia_meta(),
        attrs.tz_entries, geopoz_client.get_trwaly_zarzad_meta(),
    )

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
