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
import socket
import threading
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

_IDLE_SNAPSHOT: Dict[str, Any] = {
    "state": "idle",
    "current": None,
    "upcoming": [],
    "klasse": "",
    "standort": "",
    "done": 0,
    "total": 0,
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
    server: "_Server"  # type: ignore[assignment]

    def do_GET(self):  # noqa: N802 - von BaseHTTPRequestHandler vorgegeben
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            self._respond(200, "text/html; charset=utf-8", render_page())
        elif path == "/api/state":
            body = json.dumps(self.server.snapshot(), ensure_ascii=False).encode("utf-8")
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
    allow_reuse_address = True

    def __init__(self, address):
        super().__init__(address, _Handler)
        self._lock = threading.Lock()
        self._snapshot: Dict[str, Any] = dict(_IDLE_SNAPSHOT, rev=0)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def publish(self, snapshot: Dict[str, Any]) -> bool:
        """Uebernimmt *snapshot*; zaehlt ``rev`` nur bei inhaltlicher Aenderung hoch.

        Das ist der Grund, weshalb ein verworfenes und neu aufgenommenes Foto die
        Anzeige nicht flackern laesst: der Zustand ist danach derselbe, also
        bleibt ``rev`` gleich und die Seite rendert nicht neu.
        """
        with self._lock:
            previous = {k: v for k, v in self._snapshot.items() if k != "rev"}
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
            return dict(_IDLE_SNAPSHOT, rev=0)
        return self._server.snapshot()

    # display helpers --------------------------------------------------------
    def urls(self) -> List[str]:
        """Alle brauchbaren URLs zum Eintippen auf dem Anzeigegeraet."""
        if self._server is None:
            return []
        return [f"http://{addr}:{self.port}" for addr in local_addresses()]
