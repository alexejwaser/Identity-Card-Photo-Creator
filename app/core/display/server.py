"""Mini-Webserver fuer die Wartezimmer-Anzeige.

Nur Standardbibliothek (``http.server``) - keine neue Abhaengigkeit und nichts,
was der PyInstaller-Workflow zusaetzlich einsammeln muesste.

Threading-Modell nach dem Vorbild von ``app/core/camera/directshow_backend.py``:
ein Daemon-Thread, Stoppen ueber ein ``threading.Event`` bzw. ``shutdown()``, und
ein **begrenzter** ``join`` - ein haengender Thread darf die GUI nie einfrieren.
Der Socket wird noch im aufrufenden Thread gebunden, damit ein belegter Port als
``OSError`` synchron beim Aufrufer landet und nicht unbemerkt im Thread verpufft.
"""
from __future__ import annotations

import json
import logging
import secrets
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

from .page import render_page

logger = logging.getLogger(__name__)

# Wie lange auf das Ende des Server-Threads gewartet wird. Als Modulkonstante,
# damit Tests sie verkleinern koennen (wie _IO_LOCK_TIMEOUT_SECONDS in
# app/core/camera/opencv_backend.py).
_STOP_JOIN_TIMEOUT_SECONDS = 5.0

# Wie oft serve_forever() nach dem Stopp-Signal schaut. Der Default von 0.5 s
# haengt sonst beim Schliessen der App eine halbe Sekunde am GUI-Thread.
_POLL_INTERVAL_SECONDS = 0.1

# Ziel des UDP-Tricks zur Ermittlung der eigenen LAN-Adresse. Es werden keine
# Pakete gesendet - ``connect`` auf einem UDP-Socket waehlt nur die Route.
_ROUTE_PROBE_TARGET = ("203.0.113.1", 9)  # TEST-NET-3, garantiert nicht geroutet

# Eine tote Keep-alive-Verbindung darf ihren Handler-Thread nicht ewig in
# readline() blockieren; nach dieser Frist wird sie abgeraeumt.
_CONNECTION_TIMEOUT_SECONDS = 30.0

# Ab diesem Alter der ausgelieferten Daten wird eine Warnung geloggt. Damit steht
# beim naechsten Einfrieren eine Zeile mit Zeitstempel in logs/app.log, statt dass
# man auf Vermutungen angewiesen ist.
_STALE_WARN_SECONDS = 15.0

_IDLE_SNAPSHOT: Dict[str, Any] = {
    "state": "idle",
    "current": None,
    "upcoming": [],
    "klasse": "",
    "standort": "",
    "done": 0,
    "total": 0,
    "hints": [],
    "hint_interval": 10,
}


def local_addresses() -> List[str]:
    """Vermutliche LAN-IPv4-Adressen dieses Rechners, beste zuerst.

    Der Rueckgabewert ist reine Anzeigeinformation fuer den Nutzer ("das hier im
    Browser eintippen"); der Server selbst lauscht immer auf allen Interfaces.
    """
    found: List[str] = []

    def add(addr: Optional[str]) -> None:
        if addr and not addr.startswith("127.") and addr not in found:
            found.append(addr)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(_ROUTE_PROBE_TARGET)
        add(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()

    try:
        add(socket.gethostbyname(socket.gethostname()))
        for addr in socket.gethostbyname_ex(socket.gethostname())[2]:
            add(addr)
    except OSError:
        pass

    return found


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Greift auf die Verbindung: ein halb weggebrochener Browser haelt sonst
    # seinen Handler-Thread unbegrenzt fest.
    timeout = _CONNECTION_TIMEOUT_SECONDS
    server: "_Server"  # type: ignore[assignment]

    def do_GET(self):  # noqa: N802 - von BaseHTTPRequestHandler vorgegeben
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            self._respond(200, "text/html; charset=utf-8", render_page())
        elif path == "/api/state":
            snapshot = self.server.snapshot()
            age = snapshot.get("age_seconds", 0)
            if age >= _STALE_WARN_SECONDS:
                logger.warning(
                    "Anzeige-Server liefert Daten, die %.0f s alt sind - die App "
                    "veroeffentlicht nichts mehr",
                    age,
                )
            body = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
            self._respond(200, "application/json; charset=utf-8", body)
        else:
            self._respond(404, "text/plain; charset=utf-8", b"Nicht gefunden")

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Der Default schreibt auf stderr - unter PyInstaller --windowed gibt es
        # keine Konsole, und pro Poll eine Zeile waere ohnehin zu viel.
        logger.debug("Anzeige-Server: " + fmt, *args)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # Unter Windows erlaubt SO_REUSEADDR - anders als unter Linux - dass sich ein
    # *zweiter* Prozess auf denselben Port bindet; wer die Verbindungen bekommt,
    # ist undefiniert. Eine uebriggebliebene aeltere Instanz kann so eine
    # eingefrorene Momentaufnahme ausliefern, waehrend die neue App munter
    # weiterpubliziert. Deshalb dort aus: ein belegter Port soll laut scheitern.
    allow_reuse_address = sys.platform != "win32"

    # Felder, die der Server selbst beisteuert; sie duerfen den Inhaltsvergleich
    # in publish() nicht beeinflussen, sonst aendert sich rev bei jedem Tick.
    _META_KEYS = ("rev", "instance", "age_seconds")

    def __init__(self, address):
        super().__init__(address, _Handler)
        self._lock = threading.Lock()
        self._snapshot: Dict[str, Any] = dict(_IDLE_SNAPSHOT, rev=0)
        # Wechselt bei jedem Serverstart. Sieht die Seite eine neue Kennung, laedt
        # sie sich selbst neu - das heilt "App neu gestartet, Browser haengt noch
        # am alten Stand" ohne Handgriff am Geraet draussen.
        self.instance = secrets.token_hex(4)
        self._published_at = time.monotonic()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(self._snapshot)
            age = time.monotonic() - self._published_at
        data["instance"] = self.instance
        data["age_seconds"] = round(age, 1)
        return data

    def publish(self, snapshot: Dict[str, Any]) -> bool:
        """Uebernimmt *snapshot*; zaehlt ``rev`` nur bei inhaltlicher Aenderung hoch.

        Das ist der Grund, weshalb ein verworfenes und neu aufgenommenes Foto die
        Anzeige nicht flackern laesst: der Zustand ist danach derselbe, also
        bleibt ``rev`` gleich und die Seite rendert nicht neu.

        Der Zeitstempel wird dagegen **immer** aufgefrischt - er ist der Herzschlag,
        an dem die Seite erkennt, ob die App noch veroeffentlicht. Ohne ihn koennte
        eine eingefrorene Anzeige draussen stumm falsche Namen aufrufen.
        """
        now = time.monotonic()
        with self._lock:
            self._published_at = now
            previous = {
                k: v for k, v in self._snapshot.items() if k not in self._META_KEYS
            }
            if previous == snapshot:
                return False
            self._snapshot = dict(snapshot, rev=self._snapshot["rev"] + 1)
            return True


class DisplayServer:
    """Steuert Lebenszyklus und Inhalt der Wartezimmer-Anzeige."""

    def __init__(self, logger_: Optional[logging.Logger] = None):
        self.logger = logger_ or logger
        self._server: Optional[_Server] = None
        self._thread: Optional[threading.Thread] = None

    # lifecycle --------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def port(self) -> int:
        """Der tatsaechlich gebundene Port (wichtig bei Port 0 im Test)."""
        return self._server.server_address[1] if self._server else 0

    def start(self, port: int, host: str = "0.0.0.0") -> int:
        """Startet den Server und liefert den gebundenen Port.

        Wirft ``OSError``, wenn der Port belegt ist - bewusst synchron, damit die
        GUI eine Fehlermeldung zeigen kann statt stumm nicht zu funktionieren.
        """
        if self._server is not None:
            return self.port
        server = _Server((host, port))
        thread = threading.Thread(
            target=server.serve_forever,
            args=(_POLL_INTERVAL_SECONDS,),
            name="DisplayServer",
            daemon=True,
        )
        thread.start()
        self._server = server
        self._thread = thread
        self.logger.info("Anzeige-Server gestartet auf %s:%s", host, self.port)
        return self.port

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server, self._thread = None, None
        if server is None:
            return
        try:
            server.shutdown()
        except Exception:
            self.logger.debug("Anzeige-Server: shutdown() fehlgeschlagen", exc_info=True)
        try:
            server.server_close()
        except Exception:
            self.logger.debug("Anzeige-Server: server_close() fehlgeschlagen", exc_info=True)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=_STOP_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                self.logger.warning("Anzeige-Server-Thread reagiert nicht auf Stopp")
        self.logger.info("Anzeige-Server gestoppt")

    # content ----------------------------------------------------------------
    def publish(self, snapshot: Dict[str, Any]) -> bool:
        if self._server is None:
            return False
        return self._server.publish(snapshot)

    def snapshot(self) -> Dict[str, Any]:
        if self._server is None:
            return dict(_IDLE_SNAPSHOT, rev=0, instance="", age_seconds=0.0)
        return self._server.snapshot()

    # display helpers --------------------------------------------------------
    def urls(self) -> List[str]:
        """Alle brauchbaren URLs zum Eintippen auf dem Anzeigegeraet."""
        if self._server is None:
            return []
        return [f"http://{addr}:{self.port}" for addr in local_addresses()]
