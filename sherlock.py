#!/usr/bin/env python3
"""Sherlock -- wenn im Netz etwas Komisches vorkommt, die Daten dazu lesen.

Nur aus der oeffentlichen Karten-API. Heute: Wellen neuer Knoten.

Wenn auf einmal Dutzende neuer Knoten erscheinen (Namen wie AT-LV8-123456,
je ein Advert), beantwortet dieses Werkzeug in fuenf Schritten, was sich aus
den Daten sagen laesst und was nicht:

    python3 sherlock.py finden
        Zeigt Stosszeiten: viele neue Schluessel in kurzer Zeit.
    python3 sherlock.py auswerten --von 2026-11-20T23:40 --bis 2026-11-21T00:10
        Zeiten in UTC. Wann, wie viele, welche Observer, direkt gehoert,
        erster Hop, Signalpegel, Sendezeit.
    python3 sherlock.py auswerten ... --json
        dieselben Zahlen als JSON.
    python3 sherlock.py auswerten ... --liste schluessel.json
        schreibt die Schluessel als JSON-Array (fuer eine nodeBlacklist).

Was herauskommt, ist ein Befund, kein Urteil. Der Name ist frei waehlbar, der
Schluessel auch. Das Werkzeug nennt keine Personen und keine Orte, nur
Observer und Repeater, die etwas gehoert haben. Dazu drei Grenzen:

  * Das Fenster der Karte ist sieben Tage. Eine aeltere Welle ist weg.
  * Pfade mit 1-Byte-Hash sind mehrdeutig, und Pfade koennen gefaelscht sein.
    Der "erste Hop" sagt, welcher Repeater am oefftesten vorn steht, nicht wo
    der Sender sitzt -- ein gut vernetzter Repeater steht bei fast allem vorn.
  * Aus der Zahl der Adverts folgt keine Sendezeit je Geraet. Die Rechnung
    unten nimmt an, alles kam von einem Geraet (Obergrenze).

Keine Zugangsdaten noetig, nur die Standardbibliothek.
"""
import argparse
import collections
import datetime as dt
import json
import math
import re
import sys
import urllib.parse
import urllib.request

KARTE = 'https://map.carinthiamesh.com'
SF, BW, CR = 8, 62500.0, 8      # AT-weit: 869.618 MHz, 62,5 kHz, SF8, CR8
MEZ = dt.timedelta(hours=1)


def hole(pfad):
    req = urllib.request.Request(KARTE + pfad, headers={'User-Agent': 'carinthiamesh-welle/1.0'})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
    return d


def knoten():
    d = hole('/api/nodes?limit=2000')
    return d.get('nodes', d)


def zeit(s):
    return dt.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')


def sendezeit(bytes_):
    """Sendezeit eines Pakets in Sekunden (LoRa, explizit, CRC an)."""
    tsym = (2 ** SF) / BW
    de = 1 if tsym > 0.016 else 0
    npayload = 8 + max(math.ceil((8 * bytes_ - 4 * SF + 28 + 16) / (4 * (SF - 2 * de))) * (CR), 0)
    return (8 + 4.25 + npayload) * tsym


def stoesse(alle, fenster_min, schwelle):
    """Zeitfenster mit mindestens `schwelle` neuen Schluesseln."""
    t = sorted(zeit(n['first_seen']) for n in alle if n.get('first_seen'))
    ergebnis, i = [], 0
    while i < len(t):
        j = i
        while j + 1 < len(t) and (t[j + 1] - t[j]).total_seconds() <= fenster_min * 60:
            j += 1
        if j - i + 1 >= schwelle:
            ergebnis.append((t[i], t[j], j - i + 1))
        i = j + 1
    return ergebnis


def teile(name):
    """Name in Ziffern, Buchstaben und Rest zerlegen."""
    return re.findall(r'\d+|[^\W\d_]+|[^\w]|_', name)


def muster_aus_beispielen(beispiele):
    """Regex aus Beispielnamen. Gleich aufgebaute Namen werden verallgemeinert:
    gleiche Teile bleiben woertlich, Ziffernfolgen werden \\d{n}, abweichende
    Woerter [^\\W\\d_]+. Bei verschiedenem Aufbau: gemeinsamer Anfang plus .*"""
    zerlegt = [teile(b) for b in beispiele]
    if len(set(len(z) for z in zerlegt)) == 1:
        teile_re = []
        for spalte in zip(*zerlegt):
            if len(set(spalte)) == 1:
                teile_re.append(re.escape(spalte[0]))
            elif all(t.isdigit() for t in spalte):
                laengen = {len(t) for t in spalte}
                teile_re.append(r'\d{%d}' % laengen.pop() if len(laengen) == 1 else r'\d+')
            elif all(t.isalpha() for t in spalte):
                teile_re.append(r'[^\W\d_]+')
            else:
                teile_re.append(r'.+')
        return '^' + ''.join(teile_re) + '$'
    anfang = beispiele[0]
    for b in beispiele[1:]:
        i = 0
        while i < min(len(anfang), len(b)) and anfang[i] == b[i]:
            i += 1
        anfang = anfang[:i]
    return '^' + re.escape(anfang) + '.*' if anfang else '.*'


def pruefe_muster(muster, alle, beispiele=()):
    """Zeigt, was ein Muster in der Karte trifft."""
    try:
        r = re.compile(muster)
    except re.error as e:
        sys.exit('Das Muster ist kein gueltiger regulaerer Ausdruck: %s' % e)
    treffer = [n for n in alle if r.search(n['name'])]
    print('Muster: %s' % muster)
    print('Trifft %d von %d Knoten in der Karte.' % (len(treffer), len(alle)))
    for n in sorted(treffer, key=lambda n: n.get('first_seen') or '')[:8]:
        print('  %s  %-10s %s' % ((n.get('first_seen') or '')[:16], n['role'], n['name']))
    if len(treffer) > 8:
        print('  ... und %d weitere' % (len(treffer) - 8))
    fehlt = [b for b in beispiele if not r.search(b)]
    if fehlt:
        print('ACHTUNG: passt nicht auf die eigenen Beispiele: %s' % fehlt)
    if treffer:
        t = sorted((n.get('first_seen') or '')[:10] for n in treffer)
        print('Zeitraum der Treffer (erste Sichtung): %s bis %s' % (t[0], t[-1]))
    return treffer


def cmd_muster(args):
    alle = knoten()
    if args.beispiel:
        m = muster_aus_beispielen(args.beispiel)
        print('Vorschlag aus %d Beispielen. Pruefen, ggf. anpassen:\n' % len(args.beispiel))
        pruefe_muster(m, alle, args.beispiel)
        print('\nweiter mit:  auswerten --von <UTC> --bis <UTC> --name \'%s\'' % m)
    else:
        pruefe_muster(args.muster, alle)


def cmd_finden(args):
    alle = knoten()
    s = stoesse(alle, args.luecke, args.schwelle)
    if not s:
        print('Keine Stoesse: nie %d oder mehr neue Schluessel mit Abstaenden unter %d Minuten.'
              % (args.schwelle, args.luecke))
        return
    print('Stoesse in der Karte (Zeiten UTC, Klammer MEZ):')
    for a, b, n in s:
        print('  %s bis %s  (%s bis %s MEZ)  %d neue Schluessel'
              % (a.strftime('%d.%m. %H:%M'), b.strftime('%H:%M'),
                 (a + MEZ).strftime('%H:%M'), (b + MEZ).strftime('%H:%M'), n))
    print('\nweiter mit:  auswerten --von <UTC> --bis <UTC>')


def cmd_auswerten(args):
    alle = knoten()
    nach = {n['public_key'].lower(): n for n in alle}
    von, bis = args.von, args.bis
    muster = None
    if args.name:
        try:
            muster = re.compile(args.name)
        except re.error as e:
            sys.exit('--name ist kein gueltiger regulaerer Ausdruck: %s\n'
                     'Hilfe beim Bauen:  muster --beispiel "AT-LV8-123456" "AT-LV8-654321"' % e)
    neu = [n for n in alle if von <= (n.get('first_seen') or '')[:16] <= bis
           and (not muster or muster.search(n['name']))]
    if not neu:
        sys.exit('Keine neuen Knoten im Fenster%s. Zeiten in UTC, Format 2026-11-21T00:10.%s'
                 % (' mit diesem Namensmuster' if muster else '',
                    '\nMuster pruefen:  muster %s' % json.dumps(args.name) if muster else ''))
    ks = {n['public_key'].lower() for n in neu}
    t = sorted(((zeit(n['first_seen']) + MEZ, n) for n in neu), key=lambda x: x[0])
    out = collections.OrderedDict()
    out['fenster'] = {'erster_mez': str(t[0][0]), 'letzter_mez': str(t[-1][0]),
                      'dauer_s': int((t[-1][0] - t[0][0]).total_seconds())}
    out['knoten'] = len(neu)
    out['rollen'] = dict(collections.Counter(n['role'] for n in neu))
    out['namen_haeufigste'] = collections.Counter(n['name'] for n in neu).most_common(3)
    out['hash_groesse'] = dict(collections.Counter(n.get('hash_size') for n in neu))
    out['adverts_je_knoten'] = dict(collections.Counter(n.get('advert_count') for n in neu))
    pro_min = collections.Counter(x[0].strftime('%H:%M') for x in t)
    out['je_minute_mez'] = dict(sorted(pro_min.items()))
    pausen = [(str(t[i][0].time()), int((t[i + 1][0] - t[i][0]).total_seconds()))
              for i in range(len(t) - 1) if (t[i + 1][0] - t[i][0]).total_seconds() > 30]
    out['pausen_ueber_30s'] = pausen

    ende = (zeit(bis + ':00') + dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    P = hole('/api/packets?limit=10000&until=' + urllib.parse.quote(ende))
    P = P.get('packets', P)
    adv = []
    for p in P:
        if p['payload_type'] != 4:
            continue
        try:
            d = json.loads(p['decoded_json'])
        except Exception:
            continue
        k = (d.get('pubKey') or d.get('publicKey') or '').lower()
        if k in ks:
            adv.append(p)
    out['advert_pakete'] = len(adv)
    if len(adv) == 0:
        out['hinweis'] = ('Keine Advert-Pakete gefunden: Das Paketfenster der Karte reicht nicht so weit '
                          'zurueck oder die Welle liegt ausserhalb.')
    obs = collections.defaultdict(list)
    for p in adv:
        obs[p['observer_name']].append(p)
    beob = []
    for name, ps in sorted(obs.items(), key=lambda x: -len(x[1])):
        rs = collections.Counter(p['rssi'] for p in ps)
        ss = [p['snr'] for p in ps if p.get('snr') is not None]
        hops = [len(p.get('_parsedPath') or []) for p in ps]
        beob.append({'observer': name, 'pakete': len(ps),
                     'snr_mittel': round(sum(ss) / len(ss), 1) if ss else None,
                     'rssi_haeufigster': rs.most_common(1)[0][0],
                     'rssi_haeufigster_anteil': round(rs.most_common(1)[0][1] / len(ps), 2),
                     'ohne_hop': sum(1 for h in hops if h == 0),
                     'hops_min_max': [min(hops), max(hops)]})
    out['observer'] = beob
    out['direkt_gehoert_von'] = {b['observer']: b['ohne_hop'] for b in beob if b['ohne_hop']}
    hopz = collections.Counter(len(p.get('_parsedPath') or []) for p in adv)
    out['hopzahlen'] = dict(sorted(hopz.items()))
    erste = collections.Counter()
    for p in adv:
        pf = p.get('_parsedPath') or []
        if pf:
            erste[pf[0]] += 1
    kandidaten = {}
    for h, n_ in erste.most_common(6):
        c = [n['name'] for k, n in nach.items()
             if k.startswith(h.lower()) and n['role'] in ('repeater', 'room')]
        kandidaten[h] = {'anzahl': n_, 'passende_repeater': c[:6], 'weitere': max(0, len(c) - 6)}
    out['erster_hop'] = kandidaten
    # Sendezeit: Obergrenze, alles von einem Geraet
    laengen = [len(p['raw_hex']) // 2 for p in adv if p.get('raw_hex')]
    if laengen:
        mittel = sum(laengen) / len(laengen)
        s1 = sendezeit(mittel)
        n_send = len(neu)       # ein Advert je Knoten, ein Sendevorgang
        dauer = max(out['fenster']['dauer_s'], 1)
        out['sendezeit'] = {'bytes_mittel': round(mittel), 'je_advert_s': round(s1, 2),
                            'summe_s': round(n_send * s1, 1),
                            'anteil_im_fenster_prozent': round(100 * n_send * s1 / dauer, 1),
                            'anteil_je_stunde_prozent': round(100 * n_send * s1 / 3600, 1),
                            'annahme': 'alle Adverts von einem Geraet, Obergrenze'}
    if args.liste:
        json.dump(sorted(ks), open(args.liste, 'w'), indent=1)
        out['schluessel_datei'] = args.liste
    if args.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return
    drucke(out)


def drucke(o):
    f = o['fenster']
    print('WELLE  %d neue Knoten, %s bis %s MEZ (%d s)' % (o['knoten'], f['erster_mez'][11:], f['letzter_mez'][11:], f['dauer_s']))
    print('Rollen: %s' % o['rollen'])
    print('Haeufigste Namen: %s' % o['namen_haeufigste'])
    print('Hash-Groesse: %s   Adverts je Knoten: %s' % (o['hash_groesse'], o['adverts_je_knoten']))
    print('\nJe Minute (MEZ):')
    for m, n in o['je_minute_mez'].items():
        print('  %s %3d %s' % (m, n, '#' * n))
    if o['pausen_ueber_30s']:
        print('Pausen ueber 30 s: %s' % o['pausen_ueber_30s'])
    print('\nAdvert-Pakete gefunden: %d' % o['advert_pakete'])
    if o.get('hinweis'):
        print(o['hinweis'])
    for b in o.get('observer', []):
        print('  %-26s %4d Pakete  SNR %5s  RSSI %s (%d %%)  ohne Hop %d  Hops %s'
              % (b['observer'], b['pakete'], b['snr_mittel'], b['rssi_haeufigster'],
                 100 * b['rssi_haeufigster_anteil'], b['ohne_hop'], b['hops_min_max']))
    if o.get('direkt_gehoert_von'):
        print('Direkt gehoert (ohne Hop): %s' % o['direkt_gehoert_von'])
    print('Hopzahlen: %s' % o.get('hopzahlen'))
    print('\nErster Hop (1-Byte-Hash, mehrdeutig):')
    for h, d in o.get('erster_hop', {}).items():
        print('  %s %4d  passt auf: %s%s' % (h, d['anzahl'], ', '.join(d['passende_repeater']) or '-',
                                           ' (+%d)' % d['weitere'] if d['weitere'] else ''))
    if o.get('sendezeit'):
        s = o['sendezeit']
        print('\nSendezeit (%s): %.1f s Summe, %.1f %% im Fenster, %.1f %% je Stunde'
              % (s['annahme'], s['summe_s'], s['anteil_im_fenster_prozent'], s['anteil_je_stunde_prozent']))
    print('\nGrenzen: Name und Schluessel sind frei waehlbar. Der erste Hop zeigt das beste '
          'Netz, nicht den Sender. Pfade koennen gefaelscht sein. Kein Urteil ueber Personen.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('finden', help='Stoesse neuer Knoten suchen')
    f.add_argument('--schwelle', type=int, default=30, help='mindestens so viele neue Schluessel')
    f.add_argument('--luecke', type=float, default=10, help='groesster Abstand in Minuten')
    f.set_defaults(fn=cmd_finden)
    m = sub.add_parser('muster', help='Namensmuster (regulaerer Ausdruck) bauen und pruefen')
    m.add_argument('--beispiel', nargs='+', help='ein paar Namen, die erfasst werden sollen')
    m.add_argument('--muster', help='ein fertiges Muster nur pruefen')
    m.set_defaults(fn=cmd_muster)
    a = sub.add_parser('auswerten', help='eine Welle auswerten')
    a.add_argument('--von', required=True, help='UTC, z. B. 2026-11-20T23:40')
    a.add_argument('--bis', required=True, help='UTC, z. B. 2026-11-21T00:10')
    a.add_argument('--name', help='Regex auf den Namen, z. B. ^AT-LV8-')
    a.add_argument('--json', action='store_true')
    a.add_argument('--liste', help='Schluessel als JSON-Array in diese Datei schreiben')
    a.set_defaults(fn=cmd_auswerten)
    args = ap.parse_args()
    if args.cmd == 'muster' and not (args.beispiel or args.muster):
        ap.error('muster: --beispiel NAME ... oder --muster REGEX angeben')
    args.fn(args)


if __name__ == '__main__':
    main()
