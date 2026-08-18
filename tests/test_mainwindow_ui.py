import socket

from PySide6 import QtCore

from app.core.excel.reader import Learner


def test_capture_flow(main_window, qtbot):
    learner1 = Learner("Class1", "Doe", "John", "1", row=1)
    learner2 = Learner("Class1", "Roe", "Jane", "2", row=2)

    class FakeReader:
        def __init__(self, learners):
            self._learners = learners
            self.marked = []

        def locations(self):
            return ["Loc1"]

        def classes_for_location(self, location):
            return ["Class1"]

        def learners(self, location, class_name, skip_photographed=False):
            return self._learners

        def duplicate_ids(self, location, class_name):
            return []

        def mark_photographed(self, location, row, photographed, date):
            self.marked.append((location, row, photographed, date))

    reader = FakeReader([learner1, learner2])
    win = main_window
    win.reader = reader

    win.cmb_location.addItems(reader.locations())
    win.cmb_location.setCurrentIndex(0)
    win.cmb_class.setCurrentIndex(0)

    assert win.label_current.text() == "John Doe (1/2)"
    assert win.label_upcoming.text() == "Jane Roe"
    assert win.btn_capture.isEnabled()
    assert win.btn_skip.isEnabled()

    qtbot.mouseClick(win.btn_capture, QtCore.Qt.LeftButton)

    assert win.label_current.text() == "Jane Roe (2/2)"
    assert win.label_upcoming.text() == ""
    assert len(win.camera.captured) == 1
    assert len(reader.marked) == 1
    assert win.btn_capture.isEnabled()

    qtbot.mouseClick(win.btn_capture, QtCore.Qt.LeftButton)

    assert win.label_current.text() == "Klasse abgeschlossen"
    assert win.label_upcoming.text() == ""
    assert not win.btn_capture.isEnabled()
    assert not win.btn_skip.isEnabled()
    assert len(win.camera.captured) == 2
    assert len(reader.marked) == 2


def test_jump_to_person(main_window, qtbot):
    learner1 = Learner("Class1", "Doe", "John", "1", row=1)
    learner2 = Learner("Class1", "Roe", "Jane", "2", row=2)

    class FakeReader:
        def __init__(self, learners):
            self._learners = learners

        def locations(self):
            return ["Loc1"]

        def classes_for_location(self, location):
            return ["Class1"]

        def learners(self, location, class_name, skip_photographed=False):
            return self._learners

        def duplicate_ids(self, location, class_name):
            return []

        def mark_photographed(self, location, row, photographed, date):
            pass

    reader = FakeReader([learner1, learner2])
    win = main_window
    win.reader = reader
    win.cmb_location.addItems(reader.locations())
    win.cmb_location.setCurrentIndex(0)
    win.cmb_class.setCurrentIndex(0)

    win.jump_to(1)
    assert win.label_current.text().startswith("Jane Roe")
    qtbot.mouseClick(win.btn_capture, QtCore.Qt.LeftButton)
    assert win.label_current.text().startswith("John Doe")


def test_search_button_enabled_after_loading_classes(main_window, qtbot):
    learner1 = Learner("Class1", "Doe", "John", "1", row=1)

    class FakeReader:
        def locations(self):
            return ["Loc1"]

        def classes_for_location(self, location):
            return ["Class1"]

        def learners(self, location, class_name, skip_photographed=False):
            return [learner1]

        def duplicate_ids(self, location, class_name):
            return []

    reader = FakeReader()
    win = main_window
    win.reader = reader
    win.cmb_location.addItems(reader.locations())
    win.cmb_location.setCurrentIndex(0)
    assert win.btn_search_class.isEnabled()


# --- Wartezimmer-Anzeige: die GUI-Haelfte von #43 ---------------------------
# Der Lebenszyklus selbst haengt in tests/test_display_controller.py. Hier geht
# es nur um die Naht: liefert das Fenster den richtigen Kontext, und uebersetzt
# es die Signale des Controllers korrekt in Knopf- und Label-Zustand?

def test_display_does_not_start_by_itself(main_window):
    """Die Anzeige oeffnet einen Port (und unter Windows die Firewall-Frage) -
    sie darf ausschliesslich per Knopfdruck angehen."""
    assert main_window.controller.display.running is False
    assert main_window.btn_display.isChecked() is False
    assert main_window.lbl_display_url.isVisible() is False


def test_display_context_reads_the_live_gui_state(main_window):
    learner = Learner("Class1", "Doe", "John", "1", row=1)
    win = main_window
    win.controller.learners = [learner]
    win.controller.current = 0

    class StubReader:
        def classes_for_location(self, location):
            return ["Class1"]

    win.controller.reader = StubReader()
    win.cmb_location.addItem("Loc1")
    win.cmb_location.setCurrentIndex(0)
    win.cmb_class.setCurrentText("Class1")
    win.controller.learners = [learner]
    win.controller.current = 0
    win._class_finished = False

    ctx = win._display_context()
    assert ctx.klasse == "Class1"
    assert ctx.standort == "Loc1"
    assert ctx.has_roster is True
    assert ctx.class_finished is False
    assert list(ctx.learners) == [learner]

    # _class_finished ist Ablaufzustand des Fensters und muss durchschlagen,
    # sonst ruft die Anzeige nach "Fertig" weiter die letzte Person auf.
    win._class_finished = True
    assert win._display_context().class_finished is True


def test_toggle_button_starts_and_stops_the_display(main_window):
    """Ein Klick startet, der naechste stoppt - und der Knopf zeigt es an."""
    win = main_window
    win.settings.anzeige.port = 0        # nie 8080 im Test
    win.settings.anzeige.modus = 'lokal'  # kein 0.0.0.0, keine Firewall-Frage
    try:
        win.btn_display.click()
        assert win.controller.display.running is True
        assert win.btn_display.isChecked() is True
        # Das Label kommt aus _on_display_started -> _update_display_url.
        assert win.lbl_display_url.text().startswith('Anzeige (lokal): http://localhost:')
    finally:
        win.btn_display.click()
    assert win.controller.display.running is False
    assert win.btn_display.isChecked() is False


def test_busy_port_leaves_the_button_unchecked(main_window):
    """Der belegte Port darf nicht als 'laeuft' durchgehen - sonst glaubt die
    Fotografin, draussen haenge eine Anzeige."""
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    win = main_window
    win.settings.anzeige.port = blocker.getsockname()[1]
    win.settings.anzeige.modus = 'lokal'
    try:
        win.btn_display.click()
        assert win.controller.display.running is False
        assert win.btn_display.isChecked() is False
        assert win.lbl_display_url.isVisible() is False
    finally:
        blocker.close()


def test_close_cuts_the_context_provider(main_window):
    """Der Controller ueberlebt das Fenster (er gehoert MainController) - nach
    dem Schliessen darf sein Takt nicht mehr in abgebaute Widgets greifen."""
    win = main_window
    win.settings.anzeige.port = 0
    win.settings.anzeige.modus = 'lokal'
    win.btn_display.click()
    assert win.controller.display.running is True
    win.close()
    assert win.controller.display.running is False
    # Ein Tick nach dem Schliessen muss folgenlos bleiben.
    win.controller.display.publish()
