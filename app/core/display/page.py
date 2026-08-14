"""Die Browser-Seite der Wartezimmer-Anzeige.

Als Python-String eingebettet - gleiche Konvention wie die base64-Icons in
``app/ui/icons.py``: nichts, was PyInstaller per ``--add-data`` mitnehmen muss,
und keine externen Ressourcen, die im Schul-WLAN nicht erreichbar waeren.
"""
from __future__ import annotations

# Poll-Intervall der Seite in ms. Bewusst Polling statt SSE: bei ein bis zwei
# Clients kein messbarer Unterschied, aber ein WLAN-Aussetzer oder der Standby
# des Anzeigegeraets heilt sich ohne eigene Reconnect-Logik.
POLL_INTERVAL_MS = 1000

# Nach so vielen fehlgeschlagenen Polls in Folge wird "Keine Verbindung" gezeigt.
OFFLINE_AFTER_FAILURES = 5

_PAGE_HTML = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fotoshooting</title>
<style>
  :root {
    --bg: #14161a;
    --fg: #f2f3f5;
    --muted: #8b9199;
    --accent: #4aa3ff;
    --line: #2c2f36;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--fg);
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    display: flex;
    flex-direction: column;
    padding: clamp(16px, 3vh, 48px) clamp(16px, 4vw, 72px);
    overflow: hidden;
  }
  /* Füllt die Höhe und zentriert den Block, damit die Anzeige auf einem
     16:9-Bildschirm nicht in der oberen Ecke klebt. */
  #stage {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 0;
  }
  .label {
    font-size: clamp(13px, 1.8vh, 24px);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.4em;
  }
  #now {
    font-size: clamp(34px, 10vh, 130px);
    font-weight: 600;
    line-height: 1.1;
    color: var(--accent);
    word-break: break-word;
  }
  .divider {
    height: 1px;
    background: var(--line);
    margin: clamp(14px, 3vh, 40px) 0;
    flex: none;
  }
  #upcoming {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: clamp(8px, 1.8vh, 26px);
  }
  #upcoming li {
    font-size: clamp(24px, 6.5vh, 84px);
    line-height: 1.15;
    word-break: break-word;
    display: flex;
    align-items: baseline;
    gap: 0.5em;
  }
  #upcoming li .pos {
    color: var(--muted);
    font-size: 0.5em;
    font-variant-numeric: tabular-nums;
    min-width: 1.4em;
  }
  #upcoming li:nth-child(n+2) { color: #c3c7cd; }
  #upcoming li:nth-child(n+3) { color: var(--muted); }
  #message {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    font-size: clamp(24px, 6vh, 76px);
    color: var(--muted);
  }
  footer {
    flex: none;
    padding-top: clamp(10px, 2vh, 24px);
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1em;
    font-size: clamp(12px, 1.5vh, 20px);
    color: var(--muted);
  }
  #offline { color: #e0714a; }
  [hidden] { display: none !important; }
</style>
</head>
<body>
  <div id="stage">
    <main id="queue" hidden>
      <div class="label">Jetzt</div>
      <div id="now"></div>
      <div class="divider"></div>
      <div class="label">Als N&auml;chstes</div>
      <ol id="upcoming"></ol>
    </main>

    <div id="message">Verbinde&hellip;</div>
  </div>

  <footer>
    <span id="where"></span>
    <span id="progress"></span>
    <span id="offline" hidden>Keine Verbindung</span>
  </footer>

<script>
(function () {
  var POLL_MS = __POLL_MS__;
  var OFFLINE_AFTER = __OFFLINE_AFTER__;
  var failures = 0;
  var lastRev = null;

  var elQueue = document.getElementById('queue');
  var elNow = document.getElementById('now');
  var elUpcoming = document.getElementById('upcoming');
  var elMessage = document.getElementById('message');
  var elWhere = document.getElementById('where');
  var elProgress = document.getElementById('progress');
  var elOffline = document.getElementById('offline');

  function showMessage(text) {
    elQueue.hidden = true;
    elMessage.hidden = false;
    elMessage.textContent = text;
  }

  function render(data) {
    if (data.state === 'running') {
      elMessage.hidden = true;
      elQueue.hidden = false;
      elNow.textContent = data.current || '';
      elUpcoming.textContent = '';
      if (data.upcoming.length === 0) {
        var li = document.createElement('li');
        li.style.color = 'var(--muted)';
        li.textContent = 'Niemand mehr \\u2013 das war die letzte Person';
        elUpcoming.appendChild(li);
      } else {
        data.upcoming.forEach(function (name, i) {
          var li = document.createElement('li');
          var pos = document.createElement('span');
          pos.className = 'pos';
          pos.textContent = (i + 1) + '.';
          var who = document.createElement('span');
          who.textContent = name;
          li.appendChild(pos);
          li.appendChild(who);
          elUpcoming.appendChild(li);
        });
      }
    } else if (data.state === 'done') {
      showMessage('Klasse abgeschlossen');
    } else {
      showMessage('Bitte warten');
    }

    var where = [data.standort, data.klasse].filter(Boolean).join(' \\u2013 ');
    elWhere.textContent = where;
    elProgress.textContent = data.total ? data.done + ' / ' + data.total : '';
  }

  function poll() {
    fetch('api/state', { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) { throw new Error('HTTP ' + r.status); }
        return r.json();
      })
      .then(function (data) {
        failures = 0;
        elOffline.hidden = true;
        // Nur bei echter Aenderung neu rendern - sonst flackert die Anzeige
        // z.B. waehrend eines wiederholten Fotos im Sekundentakt.
        if (data.rev !== lastRev) {
          lastRev = data.rev;
          render(data);
        }
      })
      .catch(function () {
        failures += 1;
        if (failures >= OFFLINE_AFTER) {
          elOffline.hidden = false;
        }
      });
  }

  poll();
  setInterval(poll, POLL_MS);
})();
</script>
</body>
</html>
"""


def render_page() -> bytes:
    """Die fertige Seite als UTF-8-Bytes."""
    html = (
        _PAGE_HTML
        .replace("__POLL_MS__", str(POLL_INTERVAL_MS))
        .replace("__OFFLINE_AFTER__", str(OFFLINE_AFTER_FAILURES))
    )
    return html.encode("utf-8")
