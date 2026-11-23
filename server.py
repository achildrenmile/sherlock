#!/usr/bin/env python3
"""Sherlock als Website: kleine Standardbibliothek-Anwendung ohne Abhaengigkeiten.

    python3 server.py                  # http://127.0.0.1:8080
    PORT=9000 python3 server.py

Die Seite ruft die oeffentliche Karten-API von hier aus ab (die Karte erlaubt
keine Abrufe direkt aus dem Browser). Eingaben werden nicht gespeichert und
nicht protokolliert. Hinter einem Reverse Proxy laufen lassen.
"""
import json
import os
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sherlock

HIER = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HIER, 'static')
TYPEN = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.js': 'text/javascript; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml'}
SEITEN = {'/': 'index.html', '/hilfe': 'hilfe.html'}

try:
    VERSION = open(os.path.join(HIER, 'VERSION'), encoding='utf-8').read().strip()
except OSError:
    VERSION = 'dev'

_cache = {'t': 0.0, 'daten': None}
_lock = threading.Lock()
_anfragen = []     # Zeitstempel der letzten Minute, grob gegen Missbrauch
GRENZE = 30


def knoten_gecacht():
    """Knotenliste hoechstens einmal pro 60 s von der Karte holen."""
    with _lock:
        if _cache['daten'] is None or time.time() - _cache['t'] > 60:
            _cache['daten'] = sherlock.knoten()
            _cache['t'] = time.time()
        return _cache['daten']


def erlaubt():
    jetzt = time.time()
    with _lock:
        _anfragen[:] = [t for t in _anfragen if jetzt - t < 60]
        if len(_anfragen) >= GRENZE:
            return False
        _anfragen.append(jetzt)
        return True


def api_finden(q):
    schwelle = int(q.get('schwelle', ['30'])[0])
    luecke = float(q.get('luecke', ['10'])[0])
    if not (2 <= schwelle <= 1000 and 1 <= luecke <= 120):
        raise ValueError('schwelle 2 bis 1000, luecke 1 bis 120 Minuten.')
    out = []
    for a, b, n in sherlock.stoesse(knoten_gecacht(), luecke, schwelle):
        out.append({'von_utc': a.strftime('%Y-%m-%dT%H:%M'), 'bis_utc': b.strftime('%Y-%m-%dT%H:%M'),
                    'von_mez': (a + sherlock.MEZ).strftime('%d.%m. %H:%M'),
                    'bis_mez': (b + sherlock.MEZ).strftime('%H:%M'), 'knoten': n})
    return {'stoesse': out, 'schwelle': schwelle, 'luecke_min': luecke}


def api_muster(q):
    alle = knoten_gecacht()
    bsp = [b.strip() for b in q.get('beispiel', [])[:40] if b.strip()][:12]
    muster = (q.get('muster', [''])[0]).strip()
    if bsp:
        if any(len(b) > 64 for b in bsp):
            raise ValueError('Ein Beispielname ist zu lang.')
        muster = sherlock.muster_aus_beispielen(bsp)
    if not muster:
        raise ValueError('Beispielnamen oder ein Muster angeben.')
    treffer = sherlock.muster_treffer(muster, alle)
    treffer.sort(key=lambda n: n.get('first_seen') or '')
    return {'muster': muster, 'aus_beispielen': bool(bsp), 'treffer': len(treffer), 'gesamt': len(alle),
            'beispiele': [{'erste_sichtung': (n.get('first_seen') or '')[:16], 'rolle': n['role'],
                           'name': n['name']} for n in treffer[:12]],
            'fehlt_bei': [b for b in bsp if not sherlock.muster_kompilieren(muster).search(b)],
            'erklaerung': sherlock.erklaere(sherlock.einfach_zu_regex(muster))}


def api_auswerten(q):
    von = (q.get('von', [''])[0]).strip()
    bis = (q.get('bis', [''])[0]).strip()
    name = (q.get('name', [''])[0]).strip() or None
    out = sherlock.rechne(von, bis, name, None, knoten_gecacht())
    if not q.get('schluessel'):
        out.pop('schluessel', None)
    return out


API = {'/api/finden': api_finden, '/api/muster': api_muster, '/api/auswerten': api_auswerten}


ERLAUBT = {f for f in os.listdir(STATIC) if os.path.isfile(os.path.join(STATIC, f)) and not f.startswith('.')}
GLEICHZEITIG = threading.BoundedSemaphore(48)
MAX_URL = 1500


class H(BaseHTTPRequestHandler):
    server_version = 'sherlock'
    sys_version = ''
    timeout = 10                        # langsame oder haengende Verbindungen kappen
    protocol_version = 'HTTP/1.0'

    def log_message(self, *a):          # nichts protokollieren
        pass

    def senden(self, code, typ, daten, cache='no-store'):
        self.send_response(code)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(len(daten)))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                         "base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'")
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
        self.end_headers()
        self.wfile.write(daten)

    def do_GET(self):
        if not GLEICHZEITIG.acquire(blocking=False):
            return self.senden(503, 'text/plain; charset=utf-8', b'ausgelastet')
        try:
            self.bearbeite()
        finally:
            GLEICHZEITIG.release()

    def methode_nicht_erlaubt(self):
        self.send_response(405)
        self.send_header('Allow', 'GET')
        self.send_header('Content-Length', '0')
        self.end_headers()

    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = methode_nicht_erlaubt

    def bearbeite(self):
        if len(self.path) > MAX_URL:
            return self.senden(414, 'text/plain; charset=utf-8', b'URL zu lang')
        u = urllib.parse.urlparse(self.path)
        if u.path in API:
            if not erlaubt():
                return self.antwort_json(429, {'fehler': 'Zu viele Anfragen, bitte kurz warten.'})
            try:
                return self.antwort_json(200, API[u.path](urllib.parse.parse_qs(u.query)))
            except ValueError as e:
                return self.antwort_json(400, {'fehler': str(e)})
            except Exception:
                return self.antwort_json(502, {'fehler': 'Die Karte antwortet gerade nicht.'})
        datei = SEITEN.get(u.path)
        if not datei and u.path.startswith('/static/'):
            datei = u.path[len('/static/'):]
        if not datei or datei not in ERLAUBT and datei not in SEITEN.values():
            return self.senden(404, 'text/plain; charset=utf-8', b'nicht gefunden')
        pfad = os.path.join(STATIC, datei)
        try:
            daten = open(pfad, 'rb').read()
        except OSError:
            return self.senden(404, 'text/plain; charset=utf-8', b'nicht gefunden')
        if datei.endswith('.html'):
            daten = daten.replace(b'@@VERSION@@', VERSION.encode())
        self.senden(200, TYPEN.get(os.path.splitext(pfad)[1], 'application/octet-stream'), daten,
                    'public, max-age=300')

    def antwort_json(self, code, obj):
        self.senden(code, 'application/json; charset=utf-8', json.dumps(obj, ensure_ascii=False).encode())


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    host = os.environ.get('HOST', '127.0.0.1')
    print('Sherlock auf http://%s:%d' % (host, port))
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer.request_queue_size = 64
    ThreadingHTTPServer((host, port), H).serve_forever()
