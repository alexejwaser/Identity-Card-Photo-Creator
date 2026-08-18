"""Die GUI-Haelfte von #46: was das Fenster aus einer Entscheidung macht.

Die Rechnung selbst (``diff_settings``) haengt in tests/test_settings_change.py.
Hier geht es um die Naht dahinter - ``MainWindow._apply_settings_change`` - und
um den zweiten Dialog des Fensters, ``search_class``.

Warum die Tests ``_apply_settings_change`` **direkt** mit einem von Hand
gebauten ``SettingsChange`` aufrufen: der echte Weg fuehrt durch
``SettingsDialog.exec()``, und ``exec()`` auf einem modalen Dialog haengt im
Test fuer immer. Ohne diese Naht war der ganze Block (Kamera-Neustart,
Zuschnitt, Overlay, Anzeige-Neustart, Testmodus) nur ueber einen modalen Dialog
erreichbar und deshalb ungetestet. Genau ein Test geht trotzdem durch
``open_settings()`` - mit einem Dialog-Double statt des echten Dialogs -, weil
die Verdrahtung von Schnappschuss und Anwendung sonst nirgends geprueft waere.

Der Kontrast zu test_settings_change.py ist Absicht: dort steht, *ob* etwas zu
tun ist, hier steht, *wie* es getan wird - und vor allem, in welcher
Reihenfolge.
"""
import pytest
from PySide6 import QtWidgets

import app.ui.main_window as main_window_module
from app.core.config.settings_change import SettingsChange, SettingsSnapshot
from tests.conftest import DummyCamera


# --- Hilfen ----------------------------------------------------------------

def record_notifications(win):
    """Ersetzt das stumme _notify des main_window-Fixtures durch ein
    aufzeichnendes Double.

    Das Fixture patcht ``MainWindow._notify`` klassenweit auf einen No-Op,
    damit keine modale Box die Tests anhaelt. Wer auf Meldungen prueft, braucht
    ein eigenes Double - hier am Objekt, damit es mit dem Fenster vergeht.
    """
    seen = []
    win._notify = lambda title, message, level="info", show=True: seen.append(
        (title, message, level)
    )
    return seen


def spy_preview(win):
    """Zeichnet die Vorschau-Aufrufe auf, ohne das Widget zu ersetzen.

    Das echte LiveViewWidget bleibt stehen (der Timer soll am Ende wirklich
    laufen); nur die drei Setter und timer.start() werden umgehaengt.
    """
    calls = []
    preview = win.preview
    preview.set_camera = lambda cam: calls.append(("set_camera", cam))
    preview.set_crop_aspect = lambda aspect: calls.append(("set_crop_aspect", aspect))
    preview.set_overlay_image = lambda path: calls.append(("set_overlay_image", path))
    real_start = preview.timer.start
    preview.timer.start = lambda *a: (calls.append(("timer.start", a)), real_start(*a))[1]
    return calls


def names(calls):
    return [name for name, _ in calls]


def payload(calls, name):
    """Das Argument des ersten Aufrufs von *name*."""
    for called, arg in calls:
        if called == name:
            return arg
    raise AssertionError(f"{name} wurde nie aufgerufen: {names(calls)}")


def snapshot(win):
    return SettingsSnapshot.capture(win.settings, win.controller.display.endpoint())


@pytest.fixture
def win(main_window):
    """Das gemeinsame Fenster; die Vorschau steht am Anfang still, genau wie
    nach ``open_settings()``s erstem Schritt."""
    main_window.preview.timer.stop()
    return main_window


# --- Kamera-Neustart -------------------------------------------------------

def test_a_camera_restart_replaces_the_preview_camera(win, monkeypatch):
    fresh = DummyCamera()
    monkeypatch.setattr(
        type(win.controller), "restart_camera", lambda self: fresh
    )
    banner = []
    win._update_camera_banner = lambda: banner.append(True)
    calls = spy_preview(win)

    win._apply_settings_change(SettingsChange(camera_restart=True), snapshot(win))

    assert win.camera is fresh
    assert payload(calls, "set_camera") is fresh
    assert banner == [True]


def test_a_failed_camera_restart_leaves_a_running_preview(win, monkeypatch):
    """Der wichtigste Test dieser Datei.

    Faellt ``restart_camera()`` aus, wird die alte Kamera weiterbenutzt - und
    die Vorschau muss trotzdem wieder anlaufen. Ein vorzeitiges ``return`` im
    Fehlerzweig liesse ein dauerhaft totes Livebild zurueck, ohne dass danach
    noch irgendetwas eine Fehlermeldung zeigte: die Nutzerin saehe ein
    eingefrorenes Bild und haette keinen Hinweis, warum.
    """
    def boom(self):
        raise RuntimeError("Gerät belegt")

    monkeypatch.setattr(type(win.controller), "restart_camera", boom)
    seen = record_notifications(win)

    win._apply_settings_change(SettingsChange(camera_restart=True), snapshot(win))

    assert len(seen) == 1
    title, message, level = seen[0]
    assert title == "Kamera"
    assert "Gerät belegt" in message
    assert level == "warning"
    assert win.camera is win.controller.camera
    assert win.preview.timer.isActive() is True


def test_without_a_restart_the_existing_liveview_is_resumed(win, monkeypatch):
    """Kein Neustart heisst: dieselbe Kamera wieder anwerfen. Beides zusammen
    oeffnete das Geraet zweimal - deshalb der else-Zweig im Code."""
    restarts = []
    monkeypatch.setattr(
        type(win.controller), "restart_camera", lambda self: restarts.append(True)
    )
    started = []
    win.controller.camera.start_liveview = lambda: started.append(True)

    win._apply_settings_change(SettingsChange(), snapshot(win))

    assert started == [True]
    assert restarts == []


def test_a_restart_does_not_additionally_start_the_liveview(win, monkeypatch):
    """Die andere Haelfte des elif - und die, die stumm bleibt, wenn sie fehlt.

    ``restart_camera()`` wirft das Liveview selbst an. Wuerde aus dem ``elif``
    ein ``if``, liefe zusaetzlich ``start_liveview()`` und das Geraet ginge
    zweimal auf - unter Windows genau der Fall, in dem die EOS-Webcam nicht
    mehr aufgeht. Ohne diesen Test ueberlebt diese Aenderung die ganze Suite:
    der Test darueber prueft nur die Gegenrichtung.
    """
    fresh = DummyCamera()
    started = []
    fresh.start_liveview = lambda: started.append("neu")
    monkeypatch.setattr(type(win.controller), "restart_camera", lambda self: fresh)
    win.controller.camera.start_liveview = lambda: started.append("alt")

    win._apply_settings_change(SettingsChange(camera_restart=True), snapshot(win))

    # restart_camera() ist hier ein Double und startet nichts; entscheidend ist,
    # dass _apply_settings_change von sich aus keine Kamera anwirft.
    assert started == []


# --- Zuschnitt, Overlay, Timer ---------------------------------------------

def test_a_crop_change_reaches_the_preview_with_the_live_values(win):
    calls = spy_preview(win)
    win.settings.bild.breite = 413
    win.settings.bild.hoehe = 531

    win._apply_settings_change(SettingsChange(crop_changed=True), snapshot(win))

    assert payload(calls, "set_crop_aspect") == (413, 531)


def test_an_overlay_change_reaches_the_preview(win, tmp_path):
    calls = spy_preview(win)
    overlay = tmp_path / "rahmen.png"
    win.settings.overlay.image = overlay

    win._apply_settings_change(SettingsChange(overlay_changed=True), snapshot(win))

    assert payload(calls, "set_overlay_image") == overlay


def test_the_preview_timer_runs_again_afterwards(win):
    assert win.preview.timer.isActive() is False
    win._apply_settings_change(SettingsChange(), snapshot(win))
    assert win.preview.timer.isActive() is True


def test_the_preview_timer_starts_before_the_display_restart(win):
    """Nicht nur *dass* der Timer laeuft, sondern *wann*.

    Der Anzeige-Neustart kann synchron 'failed' melden, und das Fenster oeffnet
    darauf eine modale Box. Stuende die Vorschau dann noch still, froere das
    Livebild, solange die Meldung offen ist. Der Test daneben prueft nur den
    Endzustand - die Reihenfolge zu vertauschen ueberlebt ihn unbemerkt.
    """
    order = spy_preview(win)
    win.controller.display.restart_if_endpoint_changed = lambda token: order.append(
        ("display_restart", token)
    )

    win._apply_settings_change(SettingsChange(), snapshot(win))

    assert names(order).index("timer.start") < names(order).index("display_restart")


# --- Anzeige-Endpunkt ------------------------------------------------------

def test_the_display_restart_receives_the_captured_token(win):
    """Der Token muss der *vor* dem Dialog abgenommene sein - ein frisch
    abgefragter Endpunkt wuerde immer gleich aussehen und den Neustart
    verschlucken."""
    seen = []
    win.controller.display.restart_if_endpoint_changed = lambda token: seen.append(
        token
    )
    before = snapshot(win)
    # Nach dem Schnappschuss geaendert: genau der Fall, den der Neustart
    # erwischen soll.
    win.settings.anzeige.port = 9999

    win._apply_settings_change(SettingsChange(), before)

    assert seen == [before.display]


# --- Reihenfolge -----------------------------------------------------------

def test_test_mode_runs_after_the_buttons_and_the_running_preview(win):
    """Der Testmodus laedt einen neuen Roster nach und stoesst dabei
    _update_buttons() erneut an - er will eine eingerichtete Kamera und eine
    laufende Vorschau vorfinden, nicht andersherum."""
    order = spy_preview(win)
    win._update_buttons = lambda: order.append(("_update_buttons", None))
    win._activate_test_mode = lambda: order.append(("_activate_test_mode", None))

    win._apply_settings_change(SettingsChange(test_mode=True), snapshot(win))

    steps = names(order)
    assert "_activate_test_mode" in steps
    assert steps.index("_activate_test_mode") > steps.index("_update_buttons")
    assert steps.index("_activate_test_mode") > steps.index("timer.start")


# --- Einmal ganz durch open_settings() -------------------------------------

class StubSettingsDialog:
    """Ein Dialog-Double mit der Signatur des echten SettingsDialog.

    ``exec()`` veraendert dasselbe Settings-Objekt an Ort und Stelle - genau
    wie der echte Dialog, und genau deshalb faellt hier ein Schnappschuss auf,
    der nur eine Referenz auf ``settings.kamera`` festhaelt: der Vergleich
    liefe dann gegen sich selbst und der Kamerawechsel bliebe unbemerkt.
    """

    def __init__(self, settings, parent=None, logger=None, reader=None):
        self.settings = settings

    def exec(self):
        self.settings.kamera.rotation = (self.settings.kamera.rotation + 90) % 360
        return QtWidgets.QDialog.Accepted


def test_open_settings_restarts_the_camera_after_a_rotation_change(win, monkeypatch):
    monkeypatch.setattr(main_window_module, "SettingsDialog", StubSettingsDialog)
    fresh = DummyCamera()
    restarts = []

    def restart(self):
        restarts.append(True)
        return fresh

    monkeypatch.setattr(type(win.controller), "restart_camera", restart)

    win.open_settings()

    assert restarts == [True]
    assert win.camera is fresh
    assert win.preview.timer.isActive() is True


# --- search_class ----------------------------------------------------------

class StubClassSearchDialog:
    """Steht anstelle von ClassSearchDialog im Namensraum des Fensters.

    ``exec()`` wird hier nie am echten Dialog aufgerufen: ein modaler Dialog
    haengt im Test fuer immer. Das Ergebnis wird stattdessen ueber
    Klassenattribute vorgegeben.
    """

    result = QtWidgets.QDialog.Accepted
    selection = "1a"
    constructed = 0

    def __init__(self, classes, parent=None, logger=None):
        type(self).constructed += 1
        self.classes = classes

    def exec(self):
        return type(self).result

    def selected_class(self):
        return type(self).selection


@pytest.fixture
def search_dialog(monkeypatch):
    """Frische Zaehler pro Test - `constructed` ist ein Klassenattribut."""
    StubClassSearchDialog.constructed = 0
    StubClassSearchDialog.result = QtWidgets.QDialog.Accepted
    StubClassSearchDialog.selection = "1a"
    monkeypatch.setattr(main_window_module, "ClassSearchDialog", StubClassSearchDialog)
    return StubClassSearchDialog


def fill_classes(win, *classes):
    combo = win.cmb_class
    combo.blockSignals(True)   # load_learners geht hier niemanden etwas an
    combo.clear()
    combo.addItems(classes)
    combo.setCurrentIndex(-1)
    combo.blockSignals(False)
    win.controller.current_classes = list(classes)
    return combo


def test_search_class_without_classes_warns_and_opens_no_dialog(win, search_dialog):
    win.controller.current_classes = []
    seen = record_notifications(win)

    win.search_class()

    assert [(t, lvl) for t, _, lvl in seen] == [("Klassen", "warning")]
    assert search_dialog.constructed == 0


def test_an_accepted_dialog_selects_the_class_in_the_combo(win, search_dialog):
    combo = fill_classes(win, "1a", "2b")
    search_dialog.selection = "2b"

    win.search_class()

    assert search_dialog.constructed == 1
    assert combo.currentText() == "2b"


def test_a_cancelled_dialog_leaves_the_combo_alone(win, search_dialog):
    combo = fill_classes(win, "1a", "2b")
    search_dialog.result = QtWidgets.QDialog.Rejected
    search_dialog.selection = "2b"

    win.search_class()

    assert combo.currentIndex() == -1


def test_a_class_missing_from_the_combo_leaves_it_alone(win, search_dialog):
    """findText() liefert -1, etwa wenn die Klassenliste des Controllers und
    die Combobox auseinanderlaufen (anderer Standort gewaehlt). Dann darf
    keinesfalls irgendein Eintrag gesetzt werden."""
    combo = fill_classes(win, "1a", "2b")
    search_dialog.selection = "9z"

    win.search_class()

    assert combo.currentIndex() == -1
