"""Die Browser-Seite der Wartezimmer-Anzeige.

Als Python-String eingebettet - gleiche Konvention wie die base64-Icons in
``app/ui/icons.py``: nichts, was PyInstaller per ``--add-data`` mitnehmen muss,
und keine externen Ressourcen, die im Schul-WLAN nicht erreichbar waeren.

Gestaltet fuer eine Leseentfernung von zwei bis vier Metern im Gang, nicht fuer
einen Schreibtisch. Die Hierarchie ist bewusst umgedreht: draussen wartet niemand
auf die Person, die gerade drin ist - die **naechste** Person ist die Information,
die zaehlt, und darum das groesste Element der Seite.

Bewusste Abweichung vom ueblichen Web-Standard: die Seite nutzt die System-
Schriftfamilie statt einer selbst gehosteten. Ein eingebetteter Webfont muesste
als base64 in diese Datei, was das Modul um Hunderte Kilobyte aufblaeht - und
Segoe UI Variable ist auf dem Zielsystem (Windows) ohnehin die sauberste
verfuegbare Wahl fuer grosse Displaygroessen.
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
    /* Farben. Dunkel gewaehlt nach der Nutzungsszene: ein Bildschirm, der
       stundenlang in einem beleuchteten Gang steht und niemanden blenden soll. */
    --bg: #101216;
    --surface: #171a20;
    --fg: #f4f5f7;
    --dim: #c8ccd3;
    --muted: #8d939c;
    --line: #262a32;
    --accent: #58a9ff;
    --warn: #e8764a;

    /* Typo-Skala. Deckel bei 6rem, damit ein grosser Fernseher die Namen nicht
       ins Absurde zieht; vh-Anteil, damit sie auf jedem Format atmet. */
    --fs-meta:   clamp(11px, 1.45vh, 18px);
    --fs-label:  clamp(12px, 1.6vh, 20px);
    --fs-now:    clamp(18px, 3.4vh, 40px);
    --fs-hint:   clamp(16px, 2.9vh, 34px);
    --fs-next-1: clamp(32px, 8.6vh, 96px);
    --fs-next-2: clamp(25px, 6.2vh, 68px);
    --fs-next-3: clamp(21px, 4.8vh, 52px);
    --fs-next-n: clamp(18px, 3.8vh, 40px);

    /* Abstandsskala: eng innerhalb einer Gruppe, grosszuegig dazwischen. */
    --sp-tight: clamp(4px, 0.8vh, 12px);
    --sp-group: clamp(10px, 1.6vh, 24px);
    --sp-apart: clamp(18px, 3vh, 44px);
    --pad-page: clamp(16px, 3vh, 44px) clamp(18px, 3.5vw, 64px);
  }

  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--fg);
    /* Segoe UI Variable Display ist auf Windows 11 die fuer grosse Grade
       optimierte Schnittvariante und faellt sauber auf Segoe UI zurueck. */
    font-family: "Segoe UI Variable Display", "Segoe UI", system-ui,
                 -apple-system, sans-serif;
    font-synthesis-weight: none;
    display: flex;
    flex-direction: column;
    padding: var(--pad-page);
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
  }

  /* Browser-Oberflaechen, die sonst mit Fremd-Defaults ausgeliefert werden. */
  ::selection { background: var(--accent); color: #06121f; }
  ::-webkit-scrollbar { width: 0; height: 0; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }

  /* Veraltet-Warnung: liegt ueber allem, damit draussen niemand einem alten
     Namen folgt, ohne es zu merken. */
  #stale {
    flex: none;
    display: flex;
    align-items: center;
    gap: 0.6em;
    background: color-mix(in srgb, var(--warn) 16%, var(--bg));
    color: var(--warn);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--warn) 45%, transparent);
    font-weight: 600;
    border-radius: 10px;
    padding: clamp(8px, 1.4vh, 16px) clamp(12px, 1.8vw, 22px);
    margin-bottom: var(--sp-group);
    font-size: clamp(13px, 2vh, 26px);
  }
  #stale::before {
    content: "";
    width: 0.62em;
    height: 0.62em;
    border-radius: 50%;
    background: var(--warn);
    flex: none;
    animation: pulse 1.8s ease-in-out infinite;
  }
  @keyframes pulse { 50% { opacity: 0.25; } }

  #stage {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr;
    gap: clamp(20px, 3vw, 56px);
    align-items: center;
    min-height: 0;
  }
  /* Namen bekommen zwei Drittel, der Hinweis ein Drittel: die Warteschlange ist
     das, wofür die Leute draussen stehen. */
  #stage.has-hints { grid-template-columns: 2fr 1fr; }
  @media (max-width: 900px) {
    #stage.has-hints {
      grid-template-columns: 1fr;
      align-content: center;
      gap: var(--sp-apart);
    }
  }

  /* Aktuelle Person: eine Zeile, kein Label darueber. Sie bleibt lesbar, tritt
     aber zurueck - draussen wartet niemand auf sie. */
  #now-line {
    margin: 0;
    font-size: var(--fs-now);
    line-height: 1.2;
    color: var(--muted);
    display: flex;
    align-items: baseline;
    gap: 0.45em;
    flex-wrap: wrap;
  }
  #now {
    color: var(--accent);
    font-weight: 600;
    letter-spacing: -0.01em;
    word-break: break-word;
  }
  .rule {
    height: 1px;
    background: var(--line);
    /* Mehr Luft ueber der Abschnittsmarke als darunter. */
    margin: var(--sp-apart) 0;
  }
  .section-label {
    font-size: var(--fs-label);
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--muted);
    margin-bottom: var(--sp-group);
  }

  /* Die Nummern bleiben: die Reihenfolge ist hier echte Information, kein Dekor. */
  #upcoming {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--sp-tight);
  }
  #upcoming li {
    /* Feste Spalte fuer die Ziffer, damit alle Namen auf einer Kante stehen.
       Mit em-Breiten waeren sie je nach Schriftgrad unterschiedlich eingerueckt. */
    display: grid;
    grid-template-columns: clamp(30px, 6.2vh, 68px) 1fr;
    column-gap: clamp(6px, 1vw, 18px);
    align-items: baseline;
    line-height: 1.1;
    text-wrap: balance;
    word-break: break-word;
    font-size: var(--fs-next-1);
    font-weight: 600;
    letter-spacing: -0.025em;
  }
  #upcoming li .pos {
    color: var(--muted);
    font-size: 0.32em;
    font-weight: 500;
    letter-spacing: 0;
    font-variant-numeric: tabular-nums;
  }
  #upcoming li.none { grid-template-columns: 1fr; }
  #upcoming li:nth-child(2) {
    font-size: var(--fs-next-2); color: var(--dim);
    letter-spacing: -0.02em; font-weight: 500;
  }
  #upcoming li:nth-child(3) {
    font-size: var(--fs-next-3); color: var(--muted);
    letter-spacing: -0.015em; font-weight: 500;
  }
  #upcoming li:nth-child(n+4) {
    font-size: var(--fs-next-n); color: var(--muted); font-weight: 500;
  }
  #upcoming li:nth-child(n+2) .pos { font-size: 0.38em; }
  #upcoming li.none {
    font-size: var(--fs-next-3);
    font-weight: 500;
    color: var(--muted);
    letter-spacing: 0;
  }

  /* Hinweis-Panel: eigene Flaeche statt Rahmenkasten. */
  #hints {
    background: var(--surface);
    border-radius: 16px;
    padding: clamp(20px, 3.2vh, 44px);
    display: flex;
    flex-direction: column;
    /* Der Text steht mittig in der freien Hoehe, die Punkte sitzen unten -
       so bekommt die volle Spaltenhoehe eine Aufgabe statt Leere zu sein. */
    justify-content: space-between;
    gap: var(--sp-apart);
    min-height: 0;
    align-self: stretch;
  }
  #hint-text { flex: 1; display: flex; align-items: center; }
  @media (max-width: 900px) {
    #hints { align-self: auto; gap: var(--sp-group); }
  }
  #hint-text {
    font-size: var(--fs-hint);
    line-height: 1.4;
    color: var(--dim);
    text-wrap: pretty;
    transition: opacity .45s ease;
  }
  #hint-text.fading { opacity: 0; }
  #dots { display: flex; justify-content: center; align-items: center; gap: 10px; }
  /* Punkt-Indikatoren im Apple-Stil: der aktive wird zur breiteren Pille. */
  #dots span {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: var(--line);
    position: relative;
    overflow: hidden;
    transition: width .35s cubic-bezier(.16,1,.3,1), background-color .35s ease;
  }
  #dots span.active {
    width: 30px;
    background: color-mix(in srgb, var(--muted) 32%, transparent);
  }
  /* Die aktive Pille laeuft im Takt des Hinweis-Wechsels voll - so ist sichtbar,
     dass die Folie von selbst weiterspringt, und wie lange es noch dauert.
     scaleX statt width: kein Layout, und die runden Enden clippt die Pille. */
  #dots span.active::after {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--dim);
    transform: scaleX(0);
    transform-origin: left center;
    animation: dotfill var(--hint-duration, 10s) linear forwards;
  }
  @keyframes dotfill { to { transform: scaleX(1); } }

  #message {
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    text-wrap: balance;
    font-size: clamp(22px, 5.4vh, 64px);
    font-weight: 500;
    letter-spacing: -0.02em;
    color: var(--muted);
    min-height: 30vh;
  }

  /* Fortschrittsbalken der Klasse */
  #progress {
    flex: none;
    height: clamp(7px, 1.1vh, 14px);
    border-radius: 999px;
    background: var(--surface);
    overflow: hidden;
    margin-top: var(--sp-apart);
  }
  #bar {
    height: 100%;
    width: 0%;
    border-radius: 999px;
    background: var(--accent);
    /* Ein gestalteter Moment statt Dauerbewegung: der Balken gleitet, wenn
       tatsaechlich jemand fertig fotografiert ist - sonst steht er still.
       Bewusste Ausnahme zur "keine Layout-Animation"-Regel: die runden Enden
       wuerden unter transform: scaleX verzerren, und der Wert aendert sich
       hoechstens einmal pro Foto - Layout-Kosten spielen hier keine Rolle. */
    transition: width .9s cubic-bezier(.16,1,.3,1), filter .45s ease;
  }
  /* Kurz aufhellen statt Glow: ein farbiger Schein ohne Versatz auf dunklem
     Grund ist Deko, kein Lichtsystem. */
  #bar.bumped { filter: brightness(1.4); }
  /* Kompaktmodus: kleines Display (z.B. 7"). Hinweise weg, Namen deutlich
     groesser, weniger Rand - aus zwei Metern soll nur der Name zaehlen. */
  body.compact {
    --pad-page: clamp(10px, 2.2vh, 30px) clamp(12px, 2.4vw, 36px);
    --fs-meta:   clamp(11px, 2.2vh, 26px);
    --fs-label:  clamp(12px, 2.6vh, 30px);
    --fs-now:    clamp(16px, 5vh, 54px);
    --fs-next-1: clamp(40px, 17vh, 190px);
    --fs-next-2: clamp(28px, 11vh, 124px);
    --fs-next-3: clamp(24px, 8.5vh, 94px);
    --fs-next-n: clamp(20px, 6.5vh, 70px);
    --sp-apart:  clamp(12px, 2.2vh, 30px);
  }
  body.compact #hints { display: none; }
  body.compact #stage,
  body.compact #stage.has-hints { grid-template-columns: 1fr; }
  body.compact #upcoming li {
    grid-template-columns: clamp(26px, 7vh, 76px) 1fr;
  }

  @media (prefers-reduced-motion: reduce) {
    #bar, #hint-text, #dots span { transition: none; }
    #stale::before, #dots span.active::after { animation: none; }
    #dots span.active::after { transform: scaleX(1); }
  }

  footer {
    flex: none;
    padding-top: var(--sp-group);
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1em;
    font-size: var(--fs-meta);
    color: var(--muted);
  }
  #progress-text { font-variant-numeric: tabular-nums; }
  [hidden] { display: none !important; }
</style>
</head>
<body>
  <div id="stale" hidden>Keine Verbindung zur App &ndash; Anzeige eventuell veraltet</div>

  <div id="stage">
    <div id="queue-col">
      <main id="queue" hidden>
        <p id="now-line"><span>Wird gerade fotografiert</span><span id="now"></span></p>
        <div class="rule"></div>
        <div class="section-label">Als N&auml;chstes</div>
        <ol id="upcoming"></ol>
      </main>
      <div id="message">Verbinde&hellip;</div>
    </div>

    <aside id="hints" hidden>
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
  var lastDone = null;
  var instance = null;
  var hintsKey = null;
  var hints = [];
  var hintIndex = 0;
  var hintTimer = null;
  var bumpTimer = null;

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

  function setHints(list, intervalSeconds, compact) {
    // Im Kompaktmodus zaehlen nur die Namen - Hinweise entfallen ganz.
    if (compact) { list = []; }
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
    var seconds = Math.max(intervalSeconds, 2);
    // Speist die Fuell-Animation der aktiven Pille, damit sie exakt im Takt des
    // Wechsels vollaeuft.
    elDots.style.setProperty('--hint-duration', seconds + 's');
    elHints.hidden = false;
    elStage.classList.add('has-hints');
    showHint(0);
    if (hints.length > 1) {
      hintTimer = setInterval(advanceHint, seconds * 1000);
    }
  }

  // --- Zustand ------------------------------------------------------------
  function renderQueue(data) {
    elMessage.hidden = true;
    elQueue.hidden = false;
    elNow.textContent = data.current || '';
    elUpcoming.textContent = '';
    if (data.upcoming.length === 0) {
      var li = document.createElement('li');
      li.className = 'none';
      li.textContent = 'Niemand mehr \\u2013 das war die letzte Person';
      elUpcoming.appendChild(li);
      return;
    }
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

  function renderProgress(data) {
    elWhere.textContent = [data.standort, data.klasse].filter(Boolean).join(' \\u2013 ');
    elProgressText.textContent = data.total ? data.done + ' / ' + data.total : '';
    elBar.style.width = data.total ? (data.done / data.total * 100) + '%' : '0%';

    // Der eine gestaltete Moment: kurz aufleuchten, wenn jemand fertig ist.
    if (lastDone !== null && data.done > lastDone) {
      elBar.classList.add('bumped');
      clearTimeout(bumpTimer);
      bumpTimer = setTimeout(function () { elBar.classList.remove('bumped'); }, 900);
    }
    lastDone = data.done;
  }

  function render(data) {
    if (data.state === 'running') {
      renderQueue(data);
    } else if (data.state === 'done') {
      showMessage('Klasse abgeschlossen');
    } else {
      showMessage('Bitte warten');
    }
    renderProgress(data);
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
        document.body.classList.toggle('compact', !!data.compact);
        setHints(data.hints || [], data.hint_interval || 10, !!data.compact);

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
