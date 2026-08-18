"""Lebenszyklus des Anzeige-Controllers (Server + Timer + Signale).

Gegen echte Sockets auf Port 0 - wie tests/test_display_server.py. Es wird
nichts weggemockt: der Controller startet einen echten DisplayServer auf
Loopback, und der veroeffentlichte Zustand wird ueber die oeffentliche
HTTP-Oberflaeche (/api/state) zurueckgelesen. Das ist bewusst der Weg mit dem
geringsten Zugriff auf Interna - der Controller selbst legt den Snapshot nicht
oeffentlich offen, der Server tut es ueber HTTP.

Der Anzeige-Port 8080 wird hier nie gebunden: settings.anzeige.port = 0 laesst
das Betriebssystem einen freien Port waehlen.
"""
import json
import socket
import urllib.request

import pytest
from PySide6 import QtCore

from app.core.display.controller import DisplayController, DisplayContext
from app.core.display.server import DisplayServer
from app.core.excel.reader import Learner

TIMEOUT = 5


# --- Hilfen ----------------------------------------------------------------

@pytest.fixture
def settings(settings):
    """Die gemeinsamen Settings aus conftest.py, auf die Anzeige zugeschnitten.

    Gleicher Name wie das Fixture in conftest.py: pytest reicht das aeussere
    als Argument herein (dokumentiertes Override-Muster), sodass hier nur die
    beiden Felder stehen, die diese Datei wirklich anders braucht.
    """
    settings.anzeige.port = 0          # niemals 8080 in Tests
    settings.anzeige.modus = "lokal"   # Standard hier: alles auf Loopback
    return settings


@pytest.fixture
def controller(qtbot, settings):
    """qtbot liefert die QApplication; der Teardown stoppt den Server immer,
    damit zwischen den Tests kein Thread und kein Port haengen bleibt."""
    ctrl = DisplayController(settings)
    try:
        yield ctrl
    finally:
        ctrl.stop()


def make_learners(*names):
    """*names* sind Vornamen; der Nachname ist 'Nachname<N>'."""
    return [
        Learner("1a", f"Nachname{i}", vorname, str(100 + i))
        for i, vorname in enumerate(names)
    ]


def context(**kw):
    kw.setdefault("learners", make_learners("Anna", "Beat"))
    kw.setdefault("klasse", "1a")
    kw.setdefault("has_roster", True)
    return DisplayContext(**kw)


def record(signal):
    """Sammelt die Signal-Nutzlast in einer Liste - die Signale feuern
    synchron in start()/stop(), also ist das deterministisch."""
    seen = []
    signal.connect(lambda *args: seen.append(args))
    return seen


def free_port():
    """Ein garantiert freier Port auf Loopback (Socket wird sofort geschlossen)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def state_of(controller):
    with urllib.request.urlopen(
        f"http://127.0.0.1:{controller.port}/api/state", timeout=TIMEOUT
    ) as response:
        return json.loads(response.read())


def timer_of(controller):
    """Der Timer gehoert dem Controller; er wird ueber die Qt-Objekthierarchie
    gesucht, statt ein privates Attribut anzunehmen."""
    timer = controller.findChild(QtCore.QTimer)
    if timer is None:
        timer = getattr(controller, "_timer", None)
    assert timer is not None, "Kein QTimer im Controller gefunden"
    return timer


# --- Start, Modus, Adressen ------------------------------------------------

def test_local_mode_binds_loopback_only(controller, settings):
    """'lokal' -> nur 127.0.0.1; die LAN-Adressen fuehren dort ins Leere."""
    settings.anzeige.modus = "lokal"
    assert controller.start() is True
    assert controller.running is True
    assert controller.local_only is True
    assert controller.urls() == [f"http://localhost:{controller.port}"]


def test_network_mode_is_not_marked_local(controller, settings):
    """'netzwerk' -> 0.0.0.0, damit das zweite Geraet im WLAN drankommt."""
    settings.anzeige.modus = "netzwerk"
    assert controller.start() is True
    assert controller.local_only is False
    assert not any("localhost" in u for u in controller.urls())


def test_unknown_mode_falls_back_to_network(controller, settings):
    # Alles ausser 'lokal' ist Netzwerkbetrieb - eine kaputte settings.json
    # darf die Anzeige nicht heimlich auf Loopback einsperren.
    settings.anzeige.modus = "quatsch"
    controller.start()
    assert controller.local_only is False


def test_started_signal_carries_mode_and_urls(controller, settings):
    settings.anzeige.modus = "lokal"
    seen = record(controller.started)
    controller.start()
    assert len(seen) == 1
    local_mode, urls = seen[0]
    assert local_mode is True
    assert urls == controller.urls()


def test_started_signal_reports_network_mode(controller, settings):
    settings.anzeige.modus = "netzwerk"
    seen = record(controller.started)
    controller.start()
    assert len(seen) == 1
    assert seen[0][0] is False


def test_start_publishes_before_signalling(controller, settings):
    """Beim Aufblenden der URL muss die Seite schon Inhalt haben - es wird
    einmal sofort veroeffentlicht, erst danach kommt 'started'."""
    controller.set_context_provider(lambda: context(current=0))
    published = []
    controller.started.connect(lambda *_: published.append(state_of(controller)))
    controller.start()
    assert published[0]["klasse"] == "1a"


# --- Belegter Port ---------------------------------------------------------

def test_busy_port_reports_failure_without_raising(controller, settings):
    """Der OSError aus DisplayServer.start() darf nicht durchschlagen - die
    GUI bekommt stattdessen 'failed'."""
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    settings.anzeige.port = port
    settings.anzeige.modus = "lokal"   # gleiches Interface wie der Blocker
    failures = record(controller.failed)
    started = record(controller.started)
    try:
        assert controller.start() is False
        assert controller.running is False
        assert len(failures) == 1
        assert failures[0][0] == port
        assert isinstance(failures[0][1], str) and failures[0][1]
        assert started == []
    finally:
        blocker.close()


def test_timer_stays_inactive_after_a_failed_start(controller, settings):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    settings.anzeige.port = blocker.getsockname()[1]
    settings.anzeige.modus = "lokal"
    try:
        controller.start()
        assert timer_of(controller).isActive() is False
    finally:
        blocker.close()


# --- Toggle, Doppelstart, Stopp --------------------------------------------

def test_toggle_starts_then_stops(controller):
    stops = record(controller.stopped)
    assert controller.toggle() is True
    assert controller.running is True
    assert controller.toggle() is False
    assert controller.running is False
    assert len(stops) == 1


def test_second_start_while_running_is_a_no_op(controller):
    seen = record(controller.started)
    assert controller.start() is True
    port = controller.port
    assert controller.start() is True     # frueher Ausstieg
    assert controller.port == port        # kein zweiter Server
    assert len(seen) == 1                 # 'started' nicht erneut gefeuert


def test_stop_without_start_is_safe_and_still_signals(controller):
    stops = record(controller.stopped)
    controller.stop()                     # darf nicht werfen
    assert controller.running is False
    assert len(stops) == 1


def test_stop_frees_the_port(controller):
    controller.start()
    port = controller.port
    controller.stop()
    assert controller.running is False
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
    finally:
        probe.close()


# --- Timer -----------------------------------------------------------------

def test_publish_interval_is_one_second():
    assert DisplayController.PUBLISH_INTERVAL_MS == 1000


def test_timer_exists_but_is_idle_before_start(controller):
    """Die Anzeige darf sich niemals von selbst starten."""
    assert timer_of(controller).isActive() is False
    assert controller.running is False


def test_timer_runs_while_started_and_stops_again(controller):
    controller.start()
    timer = timer_of(controller)
    assert timer.isActive() is True
    assert timer.interval() == DisplayController.PUBLISH_INTERVAL_MS
    controller.stop()
    assert timer.isActive() is False


# --- publish() und der Kontext-Lieferant -----------------------------------

def test_publish_while_stopped_does_not_touch_the_provider(controller):
    calls = []

    def provider():
        calls.append(1)
        raise AssertionError("darf im gestoppten Zustand nicht laufen")

    controller.set_context_provider(provider)
    controller.publish()
    assert calls == []


def test_publish_without_provider_is_a_no_op(controller):
    controller.start()
    controller.publish()      # darf nicht werfen
    assert state_of(controller)["state"] == "idle"


def test_a_raising_provider_is_swallowed(controller):
    """publish() laeuft in einem Qt-Timer-Slot - eine Ausnahme dort reisst im
    Zweifel die Anwendung mit, also wird sie geschluckt und geloggt."""
    controller.set_context_provider(lambda: (_ for _ in ()).throw(RuntimeError("kaputt")))
    controller.start()
    controller.publish()      # darf nicht durchschlagen
    assert controller.running is True


def test_provider_can_be_replaced_after_start(controller):
    controller.set_context_provider(lambda: context(current=0))
    controller.start()
    controller.set_context_provider(lambda: context(current=1))
    controller.publish()
    assert state_of(controller)["current"] == "Beat N."


# --- Veroeffentlichter Zustand ---------------------------------------------
# Nur Klasse und state werden geprueft; die Snapshot-Form gehoert
# tests/test_display_state.py.

def test_published_snapshot_reflects_the_context(controller):
    controller.set_context_provider(
        lambda: context(learners=make_learners("Anna", "Beat"), current=0,
                        klasse="2b", standort="Bern")
    )
    controller.start()
    data = state_of(controller)
    assert data["klasse"] == "2b"
    assert data["state"] == "running"


def test_context_without_roster_is_idle(controller):
    controller.set_context_provider(
        lambda: DisplayContext(learners=(), current=0, klasse="", has_roster=False)
    )
    controller.start()
    assert state_of(controller)["state"] == "idle"


def test_finished_class_is_reported_as_done(controller):
    controller.set_context_provider(
        lambda: context(current=0, class_finished=True)
    )
    controller.start()
    assert state_of(controller)["state"] == "done"


def test_default_context_is_idle():
    assert DisplayContext().has_roster is False
    assert DisplayContext().current == 0
    assert DisplayContext().jump_return is None


# --- Endpunkt und Neustart -------------------------------------------------

def test_endpoint_reflects_the_settings(controller, settings):
    settings.anzeige.port = 0
    settings.anzeige.modus = "lokal"
    assert controller.endpoint() == (0, "lokal")
    settings.anzeige.modus = "netzwerk"
    assert controller.endpoint() == (0, "netzwerk")


def test_restart_on_a_changed_endpoint(controller, settings):
    """Nach einer Aenderung in den Einstellungen muss der laufende Server den
    Socket neu aufziehen."""
    controller.start()
    before = controller.endpoint()
    port = controller.port
    # Bewusst nur der Port und nicht der Modus: ein Wechsel auf 'netzwerk'
    # wuerde 0.0.0.0 binden und unter macOS/Windows die Firewall fragen. Dass
    # der Modus in die Host-Wahl eingeht, deckt test_network_mode_* ab.
    settings.anzeige.port = free_port()
    controller.restart_if_endpoint_changed(before)
    assert controller.running is True
    assert controller.port != port
    assert controller.local_only is True


def test_failed_restart_reports_stopped_then_failed(controller, settings):
    """Der Neustart auf einen belegten Port: erst 'stopped', dann 'failed' -
    und *kein* zweites 'stopped'. Das Fenster haengt seinen Knopf- und
    Label-Zustand genau an diese Reihenfolge, deshalb steht sie hier fest.
    """
    controller.start()
    before = controller.endpoint()
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    busy = blocker.getsockname()[1]
    settings.anzeige.port = busy
    events = []
    controller.stopped.connect(lambda: events.append("stopped"))
    controller.failed.connect(lambda p, m: events.append(("failed", p)))
    controller.started.connect(lambda *a: events.append("started"))
    try:
        controller.restart_if_endpoint_changed(before)
        assert events == ["stopped", ("failed", busy)]
        assert controller.running is False
    finally:
        blocker.close()


def test_toggle_reports_false_after_a_failed_start(controller, settings):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    settings.anzeige.port = blocker.getsockname()[1]
    try:
        assert controller.toggle() is False
        assert controller.running is False
    finally:
        blocker.close()


def test_unchanged_endpoint_leaves_the_server_alone(controller):
    controller.start()
    before = controller.endpoint()
    port = controller.port
    controller.restart_if_endpoint_changed(before)
    # Ein Neustart auf Port 0 zoege einen neuen Port - der gleiche Port
    # beweist, dass nichts angefasst wurde.
    assert controller.port == port
    assert controller.running is True


def test_no_restart_while_the_server_is_stopped(controller, settings):
    settings.anzeige.modus = "netzwerk"
    controller.restart_if_endpoint_changed((8080, "lokal"))
    assert controller.running is False


# --- Konstanten der Host-Wahl ----------------------------------------------

def test_host_constants_are_taken_from_the_server(controller, settings):
    # Der Controller waehlt zwischen genau diesen beiden Hosts.
    assert DisplayServer.LOCAL_HOST == "127.0.0.1"
    assert DisplayServer.NETWORK_HOST == "0.0.0.0"
