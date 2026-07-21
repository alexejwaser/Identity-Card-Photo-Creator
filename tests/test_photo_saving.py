import os
import copy
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtWidgets

from app.core.config.settings import Settings, DEFAULTS
from app.core.excel.reader import Learner
from app.ui.main_window import MainWindow
import app.core.controller as controller_module


@pytest.fixture
def settings(tmp_path):
    data = copy.deepcopy(DEFAULTS)
    data["ausgabeBasisPfad"] = tmp_path / "out"
    data["missedPath"] = tmp_path / "missed.xlsx"
    return Settings(
        ausgabeBasisPfad=data["ausgabeBasisPfad"],
        missedPath=data["missedPath"],
        bild=data["bild"],
        overlay=data["overlay"],
        kamera=data["kamera"],
        zip=data["zip"],
        copyright=data["copyright"],
        excelMapping=data["excelMapping"],
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
        p.write_bytes(b"data")
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
    monkeypatch.setattr(MainWindow, "_excel_running", lambda self: False)
    monkeypatch.setattr(MainWindow, "_notify", lambda *a, **kw: None)
    # Automatically accept the review dialog unless a test overrides
    # this behaviour.
    monkeypatch.setattr(MainWindow, "_show_review", lambda self, p: True)
    win = MainWindow(settings)
    qtbot.addWidget(win)
    return win


def prepare(win, learners):
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

    reader = FakeReader(learners)
    win.reader = reader
    win.cmb_location.addItems(reader.locations())
    win.cmb_location.setCurrentIndex(0)
    win.cmb_class.setCurrentIndex(0)
    return reader


def wait_idle(qtbot, win):
    qtbot.waitUntil(lambda: not getattr(win, "busy", False))


def test_normal_photo_saved_with_student_id(main_window, qtbot, tmp_path):
    l1 = Learner("Class1", "Doe", "John", "1", row=1)
    reader = prepare(main_window, [l1])
    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert main_window.camera.captured[0].name == "1.jpg"
    assert (tmp_path / "Loc1_Class1" / "1.jpg").exists()
    assert reader.marked[0][1] == 1


def test_retake_photo_preserves_student_id(main_window, qtbot, monkeypatch, tmp_path):
    l1 = Learner("Class1", "Doe", "John", "1", row=1)
    prepare(main_window, [l1])
    seq = iter([False, True])
    monkeypatch.setattr(MainWindow, "_show_review", lambda self, p: next(seq))

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert not (tmp_path / "Loc1_Class1" / "1.jpg").exists()

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert (tmp_path / "Loc1_Class1" / "1.jpg").exists()
    assert main_window.camera.captured[-1].name == "1.jpg"


def test_skip_then_next_photo_has_correct_id(main_window, qtbot, tmp_path, monkeypatch):
    l1 = Learner("Class1", "Doe", "John", "1", row=1)
    l2 = Learner("Class1", "Roe", "Jane", "2", row=2)
    prepare(main_window, [l1, l2])

    monkeypatch.setattr(
        QtWidgets.QInputDialog, "getItem", lambda *args, **kwargs: ("Krank", True)
    )
    monkeypatch.setattr(
        QtWidgets.QInputDialog, "getText", lambda *args, **kwargs: ("", True)
    )

    qtbot.mouseClick(main_window.btn_skip, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert len(main_window.camera.captured) == 0

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert main_window.camera.captured[0].name == "2.jpg"
    assert (tmp_path / "Loc1_Class1" / "2.jpg").exists()


def test_add_person_file_naming(main_window, qtbot, tmp_path):
    l1 = Learner("Class1", "Doe", "John", "1", row=1)
    prepare(main_window, [l1])
    main_window.controller.add_learner("Class1", "New", "Person")
    main_window.show_next()

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert main_window.camera.captured[0].name == "New_Person.jpg"
    assert (tmp_path / "new_Loc1_Class1" / "New_Person.jpg").exists()

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert main_window.camera.captured[1].name == "1.jpg"
    assert (tmp_path / "Loc1_Class1" / "1.jpg").exists()


def test_jump_to_person_file_names(main_window, qtbot, tmp_path):
    l1 = Learner("Class1", "A", "Alice", "1", row=1)
    l2 = Learner("Class1", "B", "Bob", "2", row=2)
    l3 = Learner("Class1", "C", "Carl", "3", row=3)
    prepare(main_window, [l1, l2, l3])

    main_window.jump_to(2)
    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert main_window.camera.captured[0].name == "3.jpg"
    assert (tmp_path / "Loc1_Class1" / "3.jpg").exists()

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert main_window.camera.captured[1].name == "1.jpg"
    assert (tmp_path / "Loc1_Class1" / "1.jpg").exists()


def test_jump_to_person_retake_preserves_selection(main_window, qtbot, monkeypatch, tmp_path):
    l1 = Learner("Class1", "A", "Alice", "1", row=1)
    l2 = Learner("Class1", "B", "Bob", "2", row=2)
    prepare(main_window, [l1, l2])

    main_window.jump_to(1)
    seq = iter([False, True, True])
    monkeypatch.setattr(MainWindow, "_show_review", lambda self, p: next(seq))

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    # No file saved yet and still on the selected learner
    assert not (tmp_path / "Loc1_Class1" / "2.jpg").exists()
    assert main_window.controller.current == 1

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert (tmp_path / "Loc1_Class1" / "2.jpg").exists()

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)
    assert (tmp_path / "Loc1_Class1" / "1.jpg").exists()


def test_jump_to_person_returns_to_first_unphotographed(main_window, qtbot, tmp_path):
    l1 = Learner("Class1", "A", "Alice", "1", row=1)
    l2 = Learner("Class1", "B", "Bob", "2", row=2)
    l3 = Learner("Class1", "C", "Carl", "3", row=3)
    prepare(main_window, [l1, l2, l3])

    # Jump to the last learner out of order
    main_window.jump_to(2)

    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)

    # After capturing the out-of-order learner, we should be back at the first
    # unphotographed learner (index 0)
    assert main_window.controller.current == 0
    assert main_window.camera.captured[0].name == "3.jpg"

    # Capture the first learner and ensure sequential order continues
    qtbot.mouseClick(main_window.btn_capture, QtCore.Qt.LeftButton)
    wait_idle(qtbot, main_window)

    assert main_window.camera.captured[1].name == "1.jpg"
    assert main_window.controller.current == 1

