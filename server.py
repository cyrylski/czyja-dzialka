import os
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText

import requests
from flask import Flask, jsonify, request, send_from_directory

import geopoz_client

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

    attrs, error = geopoz_client.get_parcel_info(lat, lon)
    if error:
        return jsonify({'error': error}), 502
    if attrs is None:
        return jsonify({'error': 'Nie znaleziono dzialki w tym miejscu'})

    _log_dzialka(attrs.ozn_dz)

    pow_entries = geopoz_client.get_powierzenia(attrs.ozn_dz)
    meta        = geopoz_client.get_powierzenia_meta()

    result = {
        'ozn_dz':      attrs.ozn_dz or '\u2014',
        'nrd':         attrs.nrd or '\u2014',
        'wlasc':       attrs.wlasc or '\u2014',
        'wlad':        attrs.wlad or '\u2014',
        'klasouzytki': attrs.klasouzytki,
        'pow_ewd':     attrs.pow_ewd or '\u2014',
        'adres':       attrs.adres or '\u2014',
        'pow_list':    [{'opis': e.opis, 'sygnatura': e.sygnatura} for e in pow_entries],
        'baza_data':   meta.source_date or '',
        'baza_liczba': meta.total_records,
    }
    if attrs.geometry:
        result['geometry'] = attrs.geometry

    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
