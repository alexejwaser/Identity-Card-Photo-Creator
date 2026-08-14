"""Lebenszyklus und HTTP-Oberflaeche des Anzeige-Servers.

Gegen einen echten Socket auf Port 0 - so wie tests/test_opencv_backend.py den
Lock mit einem echten Thread prueft, statt Threading wegzumocken.
"""
import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from app.core.display.server import DisplayServer

TIMEOUT = 5


@pytest.fixture
def server():
    srv = DisplayServer()
    srv.start(0, host="127.0.0.1")
    yield srv
    srv.stop()


def get(server, path):
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}{path}", timeout=TIMEOUT
    ) as response:
        return response.status, response.read(), response.headers


def snapshot(**kw):
    base = {
        "state": "running",
        "current": "Anna M.",
        "upcoming": ["Beat S."],
        "klasse": "1a",
        "standort": "Bern",
        "done": 0,
        "total": 2,
    }
    base.update(kw)
    return base


# --- HTTP ------------------------------------------------------------------

def test_root_serves_the_page(server):
    status, body, headers = get(server, "/")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert b"Als N" in body  # "Als N&auml;chstes"


def test_state_endpoint_returns_the_published_snapshot(server):
    server.publish(snapshot())
    status, body, headers = get(server, "/api/state")
    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    data = json.loads(body)
    assert data["current"] == "Anna M."
    assert data["upcoming"] == ["Beat S."]
    assert data["rev"] == 1


def test_state_is_not_cached(server):
    _, _, headers = get(server, "/api/state")
    assert headers["Cache-Control"] == "no-store"


def test_unknown_path_is_404(server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(server, "/gibtsnicht")
    assert exc.value.code == 404


def test_state_is_idle_before_anything_is_published(server):
    _, body, _ = get(server, "/api/state")
    assert json.loads(body)["state"] == "idle"


# --- Revisionszaehler ------------------------------------------------------

def test_unchanged_snapshot_does_not_bump_the_revision(server):
    # Das ist der Foto-verwerfen-Fall: show_next() laeuft erneut, der Zustand
    # ist derselbe - die Seite draussen darf nicht neu rendern.
    assert server.publish(snapshot()) is True
    assert server.publish(snapshot()) is False
    assert server.snapshot()["rev"] == 1


def test_changed_snapshot_bumps_the_revision(server):
    server.publish(snapshot())
    assert server.publish(snapshot(current="Beat S.")) is True
    assert server.snapshot()["rev"] == 2


def test_publish_is_ignored_while_stopped():
    srv = DisplayServer()
    assert srv.publish(snapshot()) is False
    assert srv.snapshot()["state"] == "idle"


# --- Lebenszyklus ----------------------------------------------------------

def test_start_reports_the_bound_port(server):
    assert server.running
    assert server.port > 0


def test_start_is_idempotent(server):
    assert server.start(0, host="127.0.0.1") == server.port


def test_stop_ends_the_thread_and_frees_the_port():
    srv = DisplayServer()
    port = srv.start(0, host="127.0.0.1")
    threads = [t for t in threading.enumerate() if t.name == "DisplayServer"]
    assert threads, "Server-Thread wurde nicht gestartet"

    srv.stop()

    assert not srv.running
    assert not threads[0].is_alive()
    # Der Port ist wieder frei - sonst scheitert ein Neustart der App.
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
    finally:
        probe.close()


def test_stop_is_safe_without_a_start():
    DisplayServer().stop()  # darf nicht werfen


def test_busy_port_raises_synchronously():
    # Der Fehler muss beim Aufrufer landen, damit die GUI ihn melden kann.
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    srv = DisplayServer()
    try:
        with pytest.raises(OSError):
            srv.start(port, host="127.0.0.1")
        assert not srv.running
    finally:
        srv.stop()
        blocker.close()


def test_urls_are_empty_while_stopped():
    assert DisplayServer().urls() == []
