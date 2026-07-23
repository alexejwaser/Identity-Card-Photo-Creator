import os
import copy
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore

from app.core.config.settings import Settings, DEFAULTS
from app.core.excel.reader import Learner
from app.ui.main_window import MainWindow
import app.core.controller as controller_module


@pytest.fixture
def settings(tmp_path):
    data = copy.deepcopy(DEFAULTS)
    data['ausgabeBasisPfad'] = tmp_path / 'out'
    data['missedPath'] = tmp_path / 'missed.xlsx'
    return Settings(
        ausgabeBasisPfad=data['ausgabeBasisPfad'],
        missedPath=data['missedPath'],
        bild=data['bild'],
        overlay=data['overlay'],
        kamera=data['kamera'],
        zip=data['zip'],
        copyright=data['copyright'],
        excelMapping=data['excelMapping'],
    )


class DummyCamera:
    def __init__(self):
        self.captured = []

    def start_liveview(self):
        pass

    def stop_liveview(self):
        pass

    def capture(self, path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'data')
        self.captured.append(p)


@pytest.fixture
def dummy_camera():
    return DummyCamera()


@pytest.fixture
def main_window(qtbot, settings, dummy_camera, monkeypatch, tmp_path):
    monkeypatch.setattr(MainWindow, "_init_camera", lambda self: dummy_camera)
    monkeypatch.setattr(controller_module, "class_output_dir", lambda base, loc, klass: tmp_path / f"{loc}_{klass}")
    monkeypatch.setattr(controller_module, "new_learner_dir", lambda base, loc, klass: tmp_path / f"new_{loc}_{klass}")

    def dummy_unique_file_path(directory, name):
        directory.mkdir(parents=True, exist_ok=True)
        return directory / name

    monkeypatch.setattr(controller_module, "unique_file_path", dummy_unique_file_path)
    monkeypatch.setattr(controller_module, "process_image", lambda *a, **kw: None)
    monkeypatch.setattr(MainWindow, "_show_review", lambda self, path: True)
    monkeypatch.setattr(MainWindow, "_excel_running", lambda self: False)
    monkeypatch.setattr(MainWindow, "_notify", lambda *a, **kw: None)
    win = MainWindow(settings)
    qtbot.addWidget(win)
    return win


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

        def learners(self, location, class_name):
            return self._learners

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

        def learners(self, location, class_name):
            return self._learners

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

        def learners(self, location, class_name):
            return [learner1]

    reader = FakeReader()
    win = main_window
    win.reader = reader
    win.cmb_location.addItems(reader.locations())
    win.cmb_location.setCurrentIndex(0)
    assert win.btn_search_class.isEnabled()
