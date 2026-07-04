import atexit
import dataclasses
import hmac
import logging
import os
import smtplib
import threading
import time
from collections import deque
from datetime import datetime, timezone
from email.mime.text import MIMEText

from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

import geopoz_client
import parcel_analyzer

APP_VERSION = 'v1.6.5'
APP_UPDATE_DATE = '2026-07-05'

app = Flask(__name__, static_folder='.')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
_analytics = logging.getLogger('analytics')

def _client_ip():
    # Fly routes every request through two proxy hops (regional edge node →
    # worker), so the last X-Forwarded-For entry — what ProxyFix x_for=1
    # yields as remote_addr — is Fly's shared edge node, not the visitor.
    # Fly-Client-IP is set authoritatively by fly-proxy and cannot be spoofed
    # through it; absent only in local dev, where remote_addr is correct.
    return request.headers.get('Fly-Client-IP') or get_remote_address()


limiter = Limiter(
    app=app,
    key_func=_client_ip,
    default_limits=['200/minute', '5000/day'],
    headers_enabled=True,
)

_EMAIL_FROM = os.environ.get('LOG_EMAIL_FROM', '')
_EMAIL_PASS = os.environ.get('LOG_EMAIL_PASSWORD', '')
_EMAIL_TO   = os.environ.get('LOG_EMAIL_TO', '')
_STATUS_TOKEN = os.environ.get('LOG_STATUS_TOKEN', '')

try:
    _FLUSH_INTERVAL_SEC = max(60, int(os.environ.get('LOG_EMAIL_INTERVAL_MIN', '15')) * 60)
except ValueError:
    _FLUSH_INTERVAL_SEC = 15 * 60
_FLUSH_SIZE_TRIGGER = 800  # flush before the deque maxlen starts dropping events

_BUFFER_MAX = 1000
_buffer: deque = deque(maxlen=_BUFFER_MAX)
_buffer_lock = threading.Lock()
_last_flush_mono = time.monotonic()
_last_flush_result = None


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
    ip = _mask_ip(_client_ip() or '')
    ua = request.headers.get('User-Agent', '')[:200]
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    _analytics.info('lookup ozn=%s source=%s ip=%s ua=%r', ozn_dz, source, ip, ua)
    with _buffer_lock:
        _buffer.append({'ts': ts, 'ozn': ozn_dz, 'source': source, 'ip': ip, 'ua': ua})


def _email_configured():
    return all([_EMAIL_FROM, _EMAIL_PASS, _EMAIL_TO])


def _flush_events(reason):
    """Drains the in-memory event buffer into a single SMTP digest message.
    Returns (sent_count, error_string_or_None). On send failure the drained
    events are put back at the front of the buffer so the next flush retries
    them. Called periodically from the flush thread, manually via
    POST /api/log_status, and one last time at process exit (atexit)."""
    global _last_flush_mono, _last_flush_result
    _last_flush_mono = time.monotonic()
    if not _email_configured():
        return 0, 'email not configured'
    with _buffer_lock:
        events = list(_buffer)
        _buffer.clear()
    if not events:
        return 0, None
    lines = [
        f"| {e['ts']} | {e['source']}-{e['ozn']} | {e['ip']} | {e['ua']} |"
        for e in events
    ]
    body = (
        f"Zdarzenia z aplikacji ({len(events)} wpisów, powód: {reason}):\n\n"
        + '\n'.join(lines)
        + '\n'
    )
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f'[działka] digest x{len(events)} ({reason})'
    msg['From'] = _EMAIL_FROM
    msg['To'] = _EMAIL_TO
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as s:
            s.starttls()
            s.login(_EMAIL_FROM, _EMAIL_PASS)
            s.sendmail(_EMAIL_FROM, _EMAIL_TO, msg.as_string())
        _analytics.info('flushed %d events via email (%s)', len(events), reason)
        _last_flush_result = {'ts': ts, 'reason': reason, 'sent': len(events), 'error': None}
        return len(events), None
    except Exception as e:
        with _buffer_lock:
            _buffer.extendleft(reversed(events))
        err = f'{type(e).__name__}: {e}'
        _analytics.warning('flush email failed (%s): %s', reason, err)
        _last_flush_result = {'ts': ts, 'reason': reason, 'sent': 0, 'error': err}
        return 0, err


def _flush_at_exit():
    _flush_events('shutdown')


def _periodic_flush_loop():
    """Flushes the buffer at most every _FLUSH_INTERVAL_SEC while events are
    pending, or immediately when the buffer nears capacity — so the digest no
    longer depends on the machine shutting down gracefully."""
    while True:
        time.sleep(30)
        with _buffer_lock:
            size = len(_buffer)
        if size == 0:
            continue
        if size >= _FLUSH_SIZE_TRIGGER or time.monotonic() - _last_flush_mono >= _FLUSH_INTERVAL_SEC:
            _flush_events('periodic')


_missing_email_vars = [
    name for name, value in [
        ('LOG_EMAIL_FROM', _EMAIL_FROM),
        ('LOG_EMAIL_PASSWORD', _EMAIL_PASS),
        ('LOG_EMAIL_TO', _EMAIL_TO),
    ] if not value
]
if _missing_email_vars:
    _analytics.warning(
        'email digest DISABLED — missing env vars: %s', ', '.join(_missing_email_vars))
else:
    _analytics.info(
        'email digest armed -> %s (every %d min while events pending, or at %d events)',
        _EMAIL_TO, _FLUSH_INTERVAL_SEC // 60, _FLUSH_SIZE_TRIGGER)
    threading.Thread(target=_periodic_flush_loop, daemon=True, name='log-flush').start()

atexit.register(_flush_at_exit)


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


@app.route('/api/log_status', methods=['GET', 'POST'])
@limiter.limit('10/minute')
def log_status():
    """Owner-only diagnostics for the email digest pipeline. Requires the
    LOG_STATUS_TOKEN env var to be set and matched (X-Log-Token header or
    ?token=). GET reports config/buffer/last-flush state; POST forces a flush
    (injecting a synthetic test event when the buffer is empty) so delivery
    can be verified end-to-end without waiting for traffic or spindown."""
    token = request.headers.get('X-Log-Token', '') or (request.args.get('token') or '')
    if not _STATUS_TOKEN or not hmac.compare_digest(token, _STATUS_TOKEN):
        return jsonify({'error': 'not found'}), 404
    if request.method == 'POST':
        with _buffer_lock:
            if not _buffer:
                ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                _buffer.append({'ts': ts, 'ozn': '-', 'source': 'test',
                                'ip': '', 'ua': 'manual flush test'})
        sent, err = _flush_events('manual')
        return jsonify({'sent': sent, 'error': err}), 200 if err is None else 502
    with _buffer_lock:
        pending = len(_buffer)
    return jsonify({
        'version': APP_VERSION,
        'email_configured': _email_configured(),
        'missing_env_vars': _missing_email_vars,
        'email_to': _EMAIL_TO or None,
        'pending_events': pending,
        'flush_interval_min': _FLUSH_INTERVAL_SEC // 60,
        'last_flush': _last_flush_result,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
