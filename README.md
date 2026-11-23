# Sherlock

Werkzeug für CarinthiaMesh (MeshCore, Kärnten): Wenn im Netz etwas Komisches vorkommt, liest es die öffentlichen Kartendaten dazu und sagt, **was sich aus den Daten sagen lässt und was nicht**.

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

## Was herauskommt

- Wie viele neue Knoten, welche Rollen, welche Namen, welche Hash-Größe, wie viele Adverts je Knoten
- Verlauf je Minute und Pausen
- Welche Observer die Adverts gehört haben, mit Signalpegel, Hopzahlen und was direkt (ohne Hop) ankam
- Erster Hop: welche Repeater (Hash, mehrdeutig) vorn stehen
- Sendezeit als Obergrenze (alles von einem Gerät angenommen), gegen die 10 % Duty Cycle gelesen
- Optional die Schlüssel als JSON-Array, z. B. für eine CoreScope-`nodeBlacklist`

## Grenzen

- **Sieben Tage.** Die Karte führt nur, was in den letzten sieben Tagen gehört wurde. Eine ältere Welle ist weg.
- **Ein Byte ist mehrdeutig.** Pfade mit 1-Byte-Hash passen auf mehrere Repeater, und Pfade können gefälscht sein. Der erste Hop zeigt das bestvernetzte Gerät, nicht den Sender.
- **Sendezeit je Gerät** lässt sich nicht aus der Zahl der Adverts ablesen. Die Rechnung ist eine Obergrenze.
- **Das Paketfenster** der Karte reicht nur einige Tage zurück.

## Geplant

Weitere Prüfungen für „komisch“: gleiche Namen mit vielen Schlüsseln, Positionssprünge (Knoten plötzlich weit weg), auffällige Umbenennungen, Uhr-Sprünge.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
