# Sherlock

[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-blue.svg)](LICENSE)

Werkzeug für CarinthiaMesh (MeshCore, Kärnten): Wenn im Netz etwas Komisches vorkommt, liest es die öffentlichen Kartendaten dazu und sagt, **was sich aus den Daten sagen lässt und was nicht**.

**Im Repo:** `sherlock.py` (Auswertung und Kommandozeile), `server.py` und `static/` (Website mit Hilfe-Seite), `Dockerfile` und `docker-compose.yml` (Betrieb). Python 3, keine Abhängigkeiten.

Es nennt keine Personen und keine Wohnorte, nur Zeiten, Zahlen und die Observer und Repeater, die etwas gehört haben. Der Name und der Schlüssel eines Knotens sind frei wählbar. Ein Befund ist kein Urteil.

## Benutzen

Python 3, nur Standardbibliothek, keine Zugangsdaten.

```bash
python3 sherlock.py finden                 # gibt es Stösse neuer Knoten?
python3 sherlock.py auswerten --von 2026-11-20T23:40 --bis 2026-11-21T00:10
python3 sherlock.py auswerten --von … --bis … --name '^AT-LV8-'   # nur Namen, die passen
python3 sherlock.py auswerten --von … --bis … --json
python3 sherlock.py auswerten --von … --bis … --liste schluessel.json
```

Zeiten in **UTC**. `finden` nennt sie mit; die Zeiten in Klammern sind MEZ.

Wer etwas Auffälliges sieht, gibt dem Werkzeug an, **wonach es suchen soll**: Zeitfenster (`--von`, `--bis`) und optional ein Namensmuster (`--name`, regulärer Ausdruck). Alles andere rechnet es selbst.

### Namensmuster bauen

Nicht jeder schreibt gern reguläre Ausdrücke. Mit ein paar Beispielnamen schlägt das Werkzeug eines vor und zeigt, was es in der Karte trifft:

```bash
python3 sherlock.py muster --beispiel "AT-LV8-123456" "AT-LV8-654321"
#   Muster: ^AT\-LV8\-\d{6}$      (sechs Ziffern)
python3 sherlock.py muster --beispiel "AT-LV8-Sensohr" "AT-LV8-Zellinkopf"
#   Muster: ^AT\-LV8\-[^\W\d_]+$  (ein Wort)
python3 sherlock.py muster --muster '^AT-LV8-'    # eigenes Muster nur prüfen
```

Ausgegeben werden die Zahl der Treffer, Beispiele mit Datum der ersten Sichtung und ein Hinweis, wenn das Muster nicht auf die eigenen Beispiele passt. Das Muster immer gegen die Treffer lesen: ein zu weites Muster erfasst auch echte Knoten.

Einfache Muster gehen auch ohne Regex: `#` = eine Ziffer, `?` = ein Zeichen, `*` = beliebig viele (`AT-LV8-######`, `AT-LV8-*`); ohne Platzhalter genügt ein enthaltener Text. Reguläre Ausdrücke bleiben möglich, sind aber begrenzt (höchstens 80 Zeichen, keine Gruppenwiederholungen, Rückbezüge, Lookarounds oder mehr als drei offene Wiederholungen), damit niemand den Server mit einem katastrophalen Muster lahmlegen kann.

## Was herauskommt

- Wie viele neue Knoten, welche Rollen, welche Namen, welche Hash-Größe, wie viele Adverts je Knoten
- Verlauf je Minute und Pausen
- Welche Observer die Adverts gehört haben, mit Signalpegel, Hopzahlen und was direkt (ohne Hop) ankam
- Erster Hop: welche Repeater (Hash, mehrdeutig) vorn stehen
- Sendezeit als Obergrenze (alles von einem Gerät angenommen), gegen die 10 % Duty Cycle gelesen
- Optional die Schlüssel als JSON-Array, z. B. für eine CoreScope-`nodeBlacklist`

## Website

`server.py` bietet dasselbe als Website (Start, Hilfe), im Look von kaernten-funkt.at. Python 3, keine Abhängigkeiten.

```bash
python3 server.py                  # http://127.0.0.1:8080
docker compose up -d --build       # Container, nur auf 127.0.0.1:8080
```

Läuft auf dem Rechner schon etwas auf Port 8080, den Host-Port in `docker-compose.yml` ändern, zum Beispiel auf `127.0.0.1:8081:8080`. `HOST` und `PORT` lassen sich außerdem als Umgebungsvariablen setzen.

Betrieb (z. B. `sherlock.kaernten-funkt.at`): hinter einem Reverse Proxy mit TLS laufen lassen. Die Karte erlaubt keine Abrufe direkt aus dem Browser, deshalb fragt der Server sie ab (höchstens einmal pro Minute, 30 Anfragen pro Minute gesamt). Eingaben werden nicht gespeichert und nicht protokolliert, es gibt keine Cookies. Impressum und Datenschutz verweisen wie bei den anderen Werkzeugen auf kaernten-funkt.at. Der Reverse Proxy kann IP-Adressen protokollieren, das gehört dann in die Datenschutzangaben.

## Grenzen

- **Sieben Tage.** Die Karte führt nur, was in den letzten sieben Tagen gehört wurde. Eine ältere Welle ist weg.
- **Ein Byte ist mehrdeutig.** Pfade mit 1-Byte-Hash passen auf mehrere Repeater, und Pfade können gefälscht sein. Der erste Hop zeigt das bestvernetzte Gerät, nicht den Sender.
- **Sendezeit je Gerät** lässt sich nicht aus der Zahl der Adverts ablesen. Die Rechnung ist eine Obergrenze.
- **Das Paketfenster** der Karte reicht nur einige Tage zurück.

## Verwendung

Sherlock ist für die Frage gedacht, **was im Netz passiert ist**, nicht **wer** es war. Es nennt keine Personen und keine Wohnorte, und eine Zahl wie „der erste Hop“ ist kein Beleg gegen jemanden. Wer einen Verdacht hat, belegt ihn nicht mit diesem Werkzeug.

## Betrieb

Jeder Push auf `main` rollt automatisch aus, ohne manuellen Schritt:

1. GitHub schickt einen Push-Webhook (signiert) an den Build-Dienst des Betreibers (Tekton).
2. Die Pipeline prüft den Code mit einem Smoke-Test: `py_compile`, Server starten, dann `GET /`, `GET /hilfe`, `GET /api/finden` und `GET /api/muster?muster=^AT-`. Schlägt etwas fehl, wird nichts gebaut und nichts ausgerollt.
3. Kaniko baut das `Dockerfile` und legt das Image als `ghcr.io/achildrenmile/sherlock:<voller Commit-SHA>` ab. Der Tag ist immer der Commit, es gibt kein `latest`.
4. Die Pipeline trägt den neuen Tag im GitOps-Repo des Betreibers (`dcsetup`, `k8s/apps/mesh/sherlock/kustomization.yaml`, Feld `newTag`) ein und committet das.
5. ArgoCD erkennt die Änderung und rollt das Deployment aus (Rolling Update, Healthcheck `GET /hilfe`).

Dauer vom Push bis live: wenige Minuten. Den Status zeigt der Commit-Status auf GitHub (pending, success, failure).

**Rollback (ein Schritt):** im GitOps-Repo `newTag` in `k8s/apps/mesh/sherlock/kustomization.yaml` auf den SHA eines früheren, guten Commits setzen (oder den Bump-Commit zurücknehmen). Das alte Image liegt noch in GHCR. Der nächste Push auf `main` baut wieder vorwärts, also zuerst den fehlerhaften Commit hier mit `git revert` korrigieren.

**Für Agenten und Mitwirkende:**
- Im Normalfall nur auf `main` pushen (oder PR mergen), alles Weitere läuft von selbst. Nicht im GitOps-Repo am Tag drehen, außer für einen Rollback.
- Keine Geheimnisse und keine internen Hostnamen in dieses Repo. Der Server braucht keine Konfiguration, er hat keine Zugangsdaten.
- Der Server setzt eine strenge Content-Security-Policy (`default-src 'self'`): keine Inline-Styles, keine Inline-Skripte, keine externen Schriften oder Bilder.
- Härtung: nur GET, nur freigegebene statische Dateien, URL-Länge und gleichzeitige Anfragen begrenzt, Timeout für träge Verbindungen, strenge CSP mit `frame-ancestors 'none'`, keine Server-Versionsangabe. Ein Limit pro Client gibt es nicht (dafür wären IP-Adressen nötig); der Schutz vor Überlast ist global.
- Datenschutz: der Server speichert und protokolliert keine Eingaben und keine IP-Adressen. Die Infrastruktur davor (z. B. Cloudflare) sieht Verbindungsdaten, das steht in der Datenschutzangabe auf der Hilfe-Seite.
- Ein Fehlschlag der Pipeline ist am roten Commit-Status zu sehen. Dann den Fehler beheben und erneut pushen.

## Geplant

- Weitere Prüfungen für „komisch“: gleiche Namen mit vielen Schlüsseln, Positionssprünge (Knoten plötzlich weit weg), auffällige Umbenennungen, Uhr-Sprünge

## Mitmachen

Fehler und Vorschläge gern als Issue. Änderungen als Pull Request, bitte mit einem Satz, was sich aus den Daten ändert und was nicht.

Die Version steht in der Datei `VERSION` und erscheint im Footer der Website. Bei sichtbaren Änderungen bitte hochzählen.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Das Logo gehört KÄRNTEN FUNKT und steht nicht unter dieser Lizenz.
