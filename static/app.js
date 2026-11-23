(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var letzte = null;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function zeigeFehler(ziel, t) { $(ziel).innerHTML = '<p class="fehler">' + esc(t) + '</p>'; }
  function lade(url, ziel, ok) {
    $(ziel).innerHTML = '<p class="klein">Einen Moment …</p>';
    fetch(url).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (x) { if (!x.ok) zeigeFehler(ziel, x.d.fehler || 'Fehler'); else ok(x.d); })
      .catch(function () { zeigeFehler(ziel, 'Keine Verbindung zum Server.'); });
  }
  function tab(kopf, zeilen) {
    return '<table><tr>' + kopf.map(function (k) { return '<th>' + esc(k) + '</th>'; }).join('') + '</tr>' +
      zeilen.map(function (z) { return '<tr>' + z.map(function (c) { return '<td>' + c + '</td>'; }).join('') + '</tr>'; }).join('') + '</table>';
  }

  $('finden').addEventListener('click', function () {
    var q = 'schwelle=' + encodeURIComponent($('schwelle').value) + '&luecke=' + encodeURIComponent($('luecke').value);
    lade('/api/finden?' + q, 'finden-out', function (d) {
      if (!d.stoesse.length) { $('finden-out').innerHTML = '<p>Kein Stoß gefunden: nie ' + d.schwelle + ' oder mehr neue Schlüssel mit Abständen unter ' + d.luecke_min + ' Minuten.</p>'; return; }
      $('finden-out').innerHTML = tab(['UTC', 'MEZ', 'Neue Schlüssel', ''], d.stoesse.map(function (s) {
        return [esc(s.von_utc) + ' bis ' + esc(s.bis_utc.slice(11)), esc(s.von_mez) + ' bis ' + esc(s.bis_mez), s.knoten,
          '<button class="btn sek" data-von="' + esc(s.von_utc) + '" data-bis="' + esc(s.bis_utc) + '">übernehmen</button>'];
      }));
      Array.prototype.forEach.call($('finden-out').querySelectorAll('button[data-von]'), function (b) {
        b.addEventListener('click', function () {
          $('von').value = b.getAttribute('data-von'); $('bis').value = b.getAttribute('data-bis');
          $('auswerten').scrollIntoView({ behavior: 'smooth' });
        });
      });
    });
  });

  $('mustern').addEventListener('click', function () {
    var bsp = $('beispiele').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
    var q = bsp.map(function (b) { return 'beispiel=' + encodeURIComponent(b); }).join('&');
    if (!bsp.length) q = 'muster=' + encodeURIComponent($('muster').value);
    lade('/api/muster?' + q, 'muster-out', function (d) {
      var h = '<p>' + (d.aus_beispielen ? 'Vorschlag: ' : 'Muster: ') + '<code>' + esc(d.muster) + '</code> ' +
        '<button class="btn sek" id="uebernehmen">ins Auswerten übernehmen</button></p>' +
        '<p><strong>Trifft ' + d.treffer + ' von ' + d.gesamt + ' Knoten</strong> in der Karte.</p>';
      if (d.fehlt_bei.length) h += '<p class="fehler">Passt nicht auf die eigenen Beispiele: ' + esc(d.fehlt_bei.join(', ')) + '</p>';
      if (d.beispiele.length) h += tab(['Erste Sichtung (UTC)', 'Rolle', 'Name'], d.beispiele.map(function (b) { return [esc(b.erste_sichtung), esc(b.rolle), esc(b.name)]; }));
      if (d.treffer > d.beispiele.length) h += '<p class="klein">… und ' + (d.treffer - d.beispiele.length) + ' weitere</p>';
      h += '<p class="klein">Das Muster gegen die Treffer lesen: Ein zu weites Muster erfasst auch echte Knoten.</p>';
      $('muster-out').innerHTML = h;
      $('uebernehmen').addEventListener('click', function () { $('name').value = d.muster; $('auswerten').scrollIntoView({ behavior: 'smooth' }); });
    });
  });

  $('auswerten').addEventListener('click', function () {
    var q = 'von=' + encodeURIComponent($('von').value) + '&bis=' + encodeURIComponent($('bis').value) +
      '&name=' + encodeURIComponent($('name').value) + '&schluessel=1';
    $('schluessel').hidden = true;
    lade('/api/auswerten?' + q, 'auswerten-out', function (o) {
      letzte = o.schluessel || null;
      var f = o.fenster;
      var h = '<h3>' + o.knoten + ' neue Knoten, ' + esc(f.erster_mez.slice(11)) + ' bis ' + esc(f.letzter_mez.slice(11)) + ' MEZ (' + f.dauer_s + ' s)</h3>';
      h += '<p>Rollen: ' + esc(JSON.stringify(o.rollen)) + '<br>Hash-Größe: ' + esc(JSON.stringify(o.hash_groesse)) +
        ' · Adverts je Knoten: ' + esc(JSON.stringify(o.adverts_je_knoten)) + '</p>';
      var max = Math.max.apply(null, Object.keys(o.je_minute_mez).map(function (k) { return o.je_minute_mez[k]; }));
      h += '<h3>Je Minute (MEZ)</h3>' + tab(['Minute', 'Knoten', ''], Object.keys(o.je_minute_mez).map(function (k) {
        var n = o.je_minute_mez[k];
        return [esc(k), n, '<span class="balken" style="width:' + Math.round(200 * n / max) + 'px"></span>'];
      }));
      if (o.pausen_ueber_30s.length) h += '<p class="klein">Pausen über 30 s: ' + o.pausen_ueber_30s.map(function (p) { return esc(p[0]) + ' (' + p[1] + ' s)'; }).join(', ') + '</p>';
      h += '<h3>Observer (' + o.advert_pakete + ' Advert-Pakete)</h3>';
      if (o.hinweis) h += '<p class="fehler">' + esc(o.hinweis) + '</p>';
      if (o.observer.length) h += tab(['Observer', 'Pakete', 'SNR', 'RSSI häufigster (Anteil)', 'ohne Hop', 'Hops'], o.observer.map(function (b) {
        return [esc(b.observer), b.pakete, b.snr_mittel, b.rssi_haeufigster + ' (' + Math.round(100 * b.rssi_haeufigster_anteil) + ' %)', b.ohne_hop, esc(b.hops_min_max.join(' bis '))];
      }));
      var d0 = Object.keys(o.direkt_gehoert_von);
      if (d0.length) h += '<p>Direkt gehört (ohne Hop): ' + d0.map(function (k) { return esc(k) + ' ' + o.direkt_gehoert_von[k] + '×'; }).join(', ') + '</p>';
      var eh = Object.keys(o.erster_hop);
      if (eh.length) h += '<h3>Erster Hop (1-Byte-Hash, mehrdeutig)</h3>' + tab(['Hash', 'Anzahl', 'passt auf'], eh.map(function (k) {
        var e = o.erster_hop[k];
        return [esc(k), e.anzahl, esc(e.passende_repeater.join(', ') || '–') + (e.weitere ? ' (+' + e.weitere + ')' : '')];
      }));
      if (o.sendezeit) h += '<h3>Sendezeit</h3><p>' + o.sendezeit.summe_s + ' s Summe, ' + o.sendezeit.anteil_im_fenster_prozent + ' % im Fenster, ' +
        o.sendezeit.anteil_je_stunde_prozent + ' % je Stunde.<br><span class="klein">Annahme: alle Adverts von einem Gerät, Obergrenze. Der Duty Cycle liegt bei 10 %.</span></p>';
      h += '<div class="grenze">Name und Schlüssel sind frei wählbar. Der erste Hop zeigt das beste Netz, nicht den Sender. Pfade können gefälscht sein. Kein Urteil über Personen.</div>';
      $('auswerten-out').innerHTML = h;
      $('schluessel').hidden = !letzte;
    });
  });

  $('schluessel').addEventListener('click', function () {
    if (!letzte) return;
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(letzte, null, 1)], { type: 'application/json' }));
    a.download = 'schluessel.json';
    a.click();
  });
})();
