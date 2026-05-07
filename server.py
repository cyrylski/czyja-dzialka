import dataclasses
import os
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText

import requests
from flask import Flask, jsonify, request, send_from_directory

import geopoz_client
import parcel_analyzer

APP_VERSION = 'v1.2.0'
APP_UPDATE_DATE = '2026-05-07'

app = Flask(__name__, static_folder='.')

_LOG_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analytics.log')
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


def _send_log_email(prefixed, ip, ua, ts):
    if not all([_EMAIL_FROM, _EMAIL_PASS, _EMAIL_TO]):
        return
    location = _geo_lookup(ip)
    loc_str = f'  ({location})' if location else ''
    body = (
        f"Czas:      {ts}\n"
        f"Działka:   {prefixed}\n"
        f"IP:        {ip}{loc_str}\n"
        f"Urządzenie: {ua}\n"
    )
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f'[działka] {prefixed}'
    msg['From'] = _EMAIL_FROM
    msg['To'] = _EMAIL_TO
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.starttls()
            s.login(_EMAIL_FROM, _EMAIL_PASS)
            s.sendmail(_EMAIL_FROM, _EMAIL_TO, msg.as_string())
    except Exception as e:
        print(f'[EMAIL] Błąd wysyłki: {e}')


def _log_dzialka(ozn_dz, source='map'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    forwarded = request.headers.get('X-Forwarded-For', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.remote_addr
    ua = request.headers.get('User-Agent', '')
    prefixed = f'{source}-{ozn_dz}'
    with open(_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f'| {ts} | {prefixed} | {ip} | {ua} |\n')
    threading.Thread(target=_send_log_email, args=(prefixed, ip, ua, ts), daemon=True).start()


@app.route('/api/version')
def version():
    return jsonify({'version': APP_VERSION, 'app_update_date': APP_UPDATE_DATE})


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/dzialka/<slug>')
def dzialka_spa(slug):
    return send_from_directory('.', 'index.html')


@app.route('/dzialka')
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
def log_share():
    payload = request.get_json(silent=True) or {}
    ozn = (payload.get('ozn') or '').strip()
    if not ozn:
        return jsonify({'error': 'Brak ozn'}), 400
    _log_dzialka(ozn, source='share')
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
