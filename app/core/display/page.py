"""Die Browser-Seite der Wartezimmer-Anzeige.

Als Python-String eingebettet - gleiche Konvention wie die base64-Icons in
``app/ui/icons.py``: nichts, was PyInstaller per ``--add-data`` mitnehmen muss,
und keine externen Ressourcen, die im Schul-WLAN nicht erreichbar waeren.

Die Hierarchie ist bewusst umgedreht: draussen wartet niemand auf die Person, die
gerade drin ist - die **naechste** Person ist die Information, die zaehlt, und
darum das groesste Element der Seite.
"""
from __future__ import annotations

# Poll-Intervall der Seite in ms. Bewusst Polling statt SSE: bei ein bis zwei
# Clients kein messbarer Unterschied, aber ein WLAN-Aussetzer oder der Standby
# des Anzeigegeraets heilt sich ohne eigene Reconnect-Logik.
POLL_INTERVAL_MS = 1000

# Frist fuer einen einzelnen Poll. Ohne sie kann ein halb weggebrochenes WLAN das
# fetch-Promise weder erfuellen noch ablehnen - die Seite stuende dann still, ohne
# je "Keine Verbindung" zu melden.
FETCH_TIMEOUT_MS = 4000

# Nach so vielen fehlgeschlagenen Polls in Folge gilt die Verbindung als weg.
OFFLINE_AFTER_FAILURES = 5

# Ab diesem Alter der Serverdaten gilt die Anzeige als veraltet, selbst wenn der
# Server sauber antwortet - dann hat die App aufgehoert zu veroeffentlichen.
STALE_AFTER_SECONDS = 6

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
    --dim: #c3c7cd;
    --accent: #4aa3ff;
    --line: #2c2f36;
    --panel: #1b1e24;
    --warn: #e0714a;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--fg);
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    display: flex;
    flex-direction: column;
    padding: clamp(16px, 3vh, 44px) clamp(16px, 3.5vw, 64px);
    overflow: hidden;
  }

  /* Veraltet-Warnung: liegt ueber allem, damit draussen niemand einem alten
     Namen folgt, ohne es zu merken. */
  #stale {
    background: var(--warn);
    color: #1a1207;
    font-weight: 600;
    text-align: center;
    border-radius: 8px;
    padding: clamp(8px, 1.4vh, 16px);
    margin-bottom: clamp(10px, 1.6vh, 20px);
    font-size: clamp(14px, 2.2vh, 28px);
    flex: none;
  }

  #stage {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr;
    gap: clamp(20px, 3vw, 56px);
    align-items: center;
    min-height: 0;
  }
  #stage.has-hints { grid-template-columns: 1.15fr 1fr; }
  @media (max-width: 900px) {
    #stage.has-hints {
      grid-template-columns: 1fr;
      align-content: center;
      gap: clamp(14px, 2.5vh, 28px);
    }
  }

  .label {
    font-size: clamp(12px, 1.7vh, 22px);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.4em;
  }

  /* Aktuelle Person: bleibt sichtbar, tritt aber bewusst zurueck. */
  #now {
    font-size: clamp(20px, 4vh, 46px);
    font-weight: 600;
    line-height: 1.15;
    color: var(--accent);
    word-break: break-word;
  }
  .divider {
    height: 1px;
    background: var(--line);
    margin: clamp(12px, 2.4vh, 32px) 0;
  }

  #upcoming {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: clamp(6px, 1.2vh, 20px);
  }
  #upcoming li {
    line-height: 1.12;
    word-break: break-word;
    display: flex;
    align-items: baseline;
    gap: 0.45em;
    /* Staffelung: die naechste Person dominiert, danach wird es leiser. */
    font-size: clamp(34px, 9.5vh, 120px);
  }
  #upcoming li .pos {
    color: var(--muted);
    font-size: 0.34em;
    font-variant-numeric: tabular-nums;
    min-width: 1.6em;
  }
  #upcoming li:nth-child(2) { font-size: clamp(26px, 6.7vh, 84px); color: var(--dim); }
  #upcoming li:nth-child(3) { font-size: clamp(22px, 5.3vh, 66px); color: var(--muted); }
  #upcoming li:nth-child(n+4) { font-size: clamp(18px, 4vh, 48px); color: var(--muted); }
  #upcoming li:nth-child(n+2) .pos { font-size: 0.4em; }

  /* Hinweis-Panel */
  #hints {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: clamp(18px, 3vh, 40px);
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: clamp(14px, 2.4vh, 32px);
    min-height: 0;
    /* Füllt die Spaltenhöhe, statt als schmaler Kasten in der Mitte zu schweben. */
    align-self: stretch;
  }
  @media (max-width: 900px) {
    #hints { align-self: auto; }
  }
  #hint-text {
    font-size: clamp(17px, 3.1vh, 40px);
    line-height: 1.35;
    color: var(--dim);
    transition: opacity .45s ease;
  }
  #hint-text.fading { opacity: 0; }
  #dots {
    display: flex;
    justify-content: center;
    gap: 10px;
  }
  /* Punkt-Indikatoren im Apple-Stil: der aktive wird zur breiteren Pille. */
  #dots span {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: transparent;
    border: 2px solid var(--muted);
    transition: width .35s ease, background-color .35s ease, border-color .35s ease;
  }
  #dots span.active {
    width: 26px;
    background: var(--dim);
    border-color: var(--dim);
  }

  #message {
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    font-size: clamp(24px, 6vh, 76px);
    color: var(--muted);
    min-height: 30vh;
  }

  /* Fortschrittsbalken der Klasse */
  #progress {
    flex: none;
    height: clamp(8px, 1.3vh, 16px);
    border-radius: 999px;
    background: #22262d;
    overflow: hidden;
    margin-top: clamp(12px, 2vh, 28px);
  }
  #bar {
    height: 100%;
    width: 0%;
    border-radius: 999px;
    background: linear-gradient(90deg, #2f7fd4, var(--accent));
    transition: width .6s ease;
    position: relative;
    overflow: hidden;
  }
  /* Sehr dezenter Schimmer - lebendig, ohne vom Namen abzulenken. */
  #bar::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg,
      rgba(255,255,255,0) 0%, rgba(255,255,255,.28) 50%, rgba(255,255,255,0) 100%);
    transform: translateX(-100%);
    animation: sheen 2.8s ease-in-out infinite;
  }
  @keyframes sheen { to { transform: translateX(100%); } }
  @media (prefers-reduced-motion: reduce) {
    #bar::after { animation: none; }
    #bar, #hint-text, #dots span { transition: none; }
  }

  footer {
    flex: none;
    padding-top: clamp(8px, 1.2vh, 16px);
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1em;
    font-size: clamp(11px, 1.4vh, 20px);
    color: var(--muted);
  }
  [hidden] { display: none !important; }
</style>
</head>
<body>
  <div id="stale" hidden>Keine Verbindung zur App &ndash; Anzeige eventuell veraltet</div>

  <div id="stage">
    <div id="queue-col">
      <main id="queue" hidden>
        <div class="label">Jetzt</div>
        <div id="now"></div>
        <div class="divider"></div>
        <div class="label">Als N&auml;chstes</div>
        <ol id="upcoming"></ol>
      </main>
      <div id="message">Verbinde&hellip;</div>
    </div>

    <aside id="hints" hidden>
      <div class="label">Hinweis</div>
      <div id="hint-text"></div>
      <div id="dots"></div>
    </aside>
  </div>

  <div id="progress"><div id="bar"></div></div>

  <footer>
    <span id="where"></span>
    <span id="progress-text"></span>
  </footer>

<script>
(function () {
  var POLL_MS = __POLL_MS__;
  var FETCH_TIMEOUT_MS = __FETCH_TIMEOUT_MS__;
  var OFFLINE_AFTER = __OFFLINE_AFTER__;
  var STALE_AFTER = __STALE_AFTER__;

  var failures = 0;
  var lastRev = null;
  var instance = null;
  var hintsKey = null;
  var hints = [];
  var hintIndex = 0;
  var hintTimer = null;

  var elStale = document.getElementById('stale');
  var elStage = document.getElementById('stage');
  var elQueue = document.getElementById('queue');
  var elNow = document.getElementById('now');
  var elUpcoming = document.getElementById('upcoming');
  var elMessage = document.getElementById('message');
  var elHints = document.getElementById('hints');
  var elHintText = document.getElementById('hint-text');
  var elDots = document.getElementById('dots');
  var elBar = document.getElementById('bar');
  var elWhere = document.getElementById('where');
  var elProgressText = document.getElementById('progress-text');

  function showMessage(text) {
    elQueue.hidden = true;
    elMessage.hidden = false;
    elMessage.textContent = text;
  }

  // --- Hinweis-Slideshow --------------------------------------------------
  function renderDots() {
    elDots.textContent = '';
    if (hints.length < 2) { return; }
    hints.forEach(function (_, i) {
      var dot = document.createElement('span');
      if (i === hintIndex) { dot.className = 'active'; }
      elDots.appendChild(dot);
    });
  }

  function showHint(index) {
    hintIndex = index;
    elHintText.textContent = hints[index] || '';
    renderDots();
  }

  function advanceHint() {
    if (hints.length < 2) { return; }
    elHintText.classList.add('fading');
    setTimeout(function () {
      showHint((hintIndex + 1) % hints.length);
      elHintText.classList.remove('fading');
    }, 450);
  }

  function setHints(list, intervalSeconds) {
    // Nur bei echter Aenderung neu starten - sonst spraenge die Slideshow bei
    // jedem Namenswechsel zurueck auf den ersten Hinweis.
    var key = JSON.stringify(list) + '|' + intervalSeconds;
    if (key === hintsKey) { return; }
    hintsKey = key;
    hints = list;
    if (hintTimer) { clearInterval(hintTimer); hintTimer = null; }
    if (hints.length === 0) {
      elHints.hidden = true;
      elStage.classList.remove('has-hints');
      return;
    }
    elHints.hidden = false;
    elStage.classList.add('has-hints');
    showHint(0);
    if (hints.length > 1) {
      hintTimer = setInterval(advanceHint, Math.max(intervalSeconds, 2) * 1000);
    }
  }

  // --- Zustand ------------------------------------------------------------
  function render(data) {
    if (data.state === 'running') {
      elMessage.hidden = true;
      elQueue.hidden = false;
      elNow.textContent = data.current || '';
      elUpcoming.textContent = '';
      if (data.upcoming.length === 0) {
        var li = document.createElement('li');
        li.style.color = 'var(--muted)';
        li.style.fontSize = 'clamp(20px, 4.5vh, 54px)';
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
    elProgressText.textContent = data.total ? data.done + ' / ' + data.total : '';
    elBar.style.width = data.total ? (data.done / data.total * 100) + '%' : '0%';
  }

  function markStale(isStale) {
    elStale.hidden = !isStale;
  }

  function poll() {
    // AbortController: ohne Frist kann ein halb weggebrochenes WLAN das Promise
    // weder erfuellen noch ablehnen - die Seite stuende still, ohne es zu melden.
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, FETCH_TIMEOUT_MS);

    fetch('api/state', { cache: 'no-store', signal: controller.signal })
      .then(function (r) {
        clearTimeout(timer);
        if (!r.ok) { throw new Error('HTTP ' + r.status); }
        return r.json();
      })
      .then(function (data) {
        failures = 0;

        // Neuer Serverstart -> Seite neu laden, damit sie nicht am alten Stand haengt.
        if (instance === null) {
          instance = data.instance;
        } else if (data.instance && data.instance !== instance) {
          window.location.reload();
          return;
        }

        markStale(data.age_seconds >= STALE_AFTER);
        setHints(data.hints || [], data.hint_interval || 10);

        // Nur bei echter Aenderung neu rendern - sonst flackert die Anzeige
        // z.B. waehrend eines wiederholten Fotos im Sekundentakt.
        if (data.rev !== lastRev) {
          lastRev = data.rev;
          render(data);
        }
      })
      .catch(function () {
        clearTimeout(timer);
        failures += 1;
        if (failures >= OFFLINE_AFTER) { markStale(true); }
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
        .replace("__FETCH_TIMEOUT_MS__", str(FETCH_TIMEOUT_MS))
        .replace("__OFFLINE_AFTER__", str(OFFLINE_AFTER_FAILURES))
        .replace("__STALE_AFTER__", str(STALE_AFTER_SECONDS))
    )
    return html.encode("utf-8")
