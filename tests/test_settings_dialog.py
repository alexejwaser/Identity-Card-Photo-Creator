import os
import copy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtGui, QtWidgets

from app.core.config.settings import Settings, DEFAULTS
from app.core.camera.enumerate import CameraDevice
import app.ui.settings_dialog as settings_dialog_module
from app.ui.settings_dialog import SettingsDialog


class FakePreviewCamera:
    """Stand-in for OpenCVCamera used by the dialog preview - touches no
    real hardware."""

    def __init__(self, camera_id=0, rotation=0, device_name=None, device_path=None):
        self.camera_id = camera_id
        self.rotation = rotation
        self.device_name = device_name
        self.device_path = device_path
        self.started = False

    def start_liveview(self):
        self.started = True

    def stop_liveview(self):
        self.started = False

    def get_preview_qimage(self):
        return QtGui.QImage(4, 4, QtGui.QImage.Format_RGB888)


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


@pytest.fixture
def patched_camera(monkeypatch):
    devices = [CameraDevice(0, "Kamera 0"), CameraDevice(1, "Kamera 1")]
    monkeypatch.setattr(settings_dialog_module, "list_cameras", lambda *a, **kw: devices)
    monkeypatch.setattr(settings_dialog_module, "OpenCVCamera", FakePreviewCamera)
    return devices


def test_resolution_spinboxes_reflect_settings(qtbot, settings, patched_camera):
    settings.bild.breite = 1234
    settings.bild.hoehe = 4321
    dlg = SettingsDialog(settings)
    qtbot.addWidget(dlg)
    assert dlg.spin_width.value() == 1234
    assert dlg.spin_height.value() == 4321
    dlg._stop_preview()


def test_device_preselected_from_settings(qtbot, settings, patched_camera):
    settings.kamera.deviceIndex = 1
    dlg = SettingsDialog(settings)
    qtbot.addWidget(dlg)
    assert dlg.cmb_device.currentData() == 1
    dlg._stop_preview()


def test_accept_writes_back_device_and_resolution(qtbot, settings, patched_camera, monkeypatch):
    # Avoid writing to the real user config path during the test.
    monkeypatch.setattr(type(settings), "save", lambda self, *a, **kw: None)
    dlg = SettingsDialog(settings)
    qtbot.addWidget(dlg)
    idx = dlg.cmb_device.findData(0)
    dlg.cmb_device.setCurrentIndex(idx)
    dlg.spin_width.setValue(2000)
    dlg.spin_height.setValue(2500)
    dlg.accept()
    assert settings.kamera.deviceIndex == 0
    assert settings.bild.breite == 2000
    assert settings.bild.hoehe == 2500


def test_request_test_mode_sets_flag_and_accepts(qtbot, settings, patched_camera, monkeypatch):
    # accept() persists settings; avoid touching the real user config path.
    monkeypatch.setattr(type(settings), "save", lambda self, *a, **kw: None)
    dlg = SettingsDialog(settings)
    qtbot.addWidget(dlg)
    assert dlg._test_mode_requested is False
    dlg.btn_test_mode.click()
    assert dlg._test_mode_requested is True
    assert dlg.result() == QtWidgets.QDialog.Accepted


def test_stop_preview_releases_camera(qtbot, settings, patched_camera):
    dlg = SettingsDialog(settings)
    qtbot.addWidget(dlg)
    cam = dlg._preview_camera
    assert isinstance(cam, FakePreviewCamera)
    assert cam.started
    dlg._stop_preview()
    assert dlg._preview_camera is None
    assert not cam.started
