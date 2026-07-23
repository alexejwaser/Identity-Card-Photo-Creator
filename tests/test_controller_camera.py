"""Tests for MainController's camera init/fallback logic."""

from app.core.config.settings import Settings
from app.core.camera.base import CameraError
from app.core.camera.enumerate import CameraDevice
from app.core import controller as controller_mod
from app.core.controller import MainController


def _settings(tmp_path, device_index=1):
    s = Settings.load(tmp_path / "settings.json")
    s.kamera.backend = "opencv"
    s.kamera.deviceIndex = device_index
    return s


class FlakyOpenCVCamera:
    """Stand-in for OpenCVCamera: configured index always fails to open,
    even though it's a real, currently-detected device (simulates a
    transient driver hiccup, not a missing device)."""

    def __init__(self, camera_id, rotation=0, device_name=None, device_path=None):
        self.camera_id = camera_id

    def start_liveview(self):
        raise CameraError(f"Kamera {self.camera_id} kann nicht geoeffnet werden")


def test_transient_open_failure_does_not_switch_or_persist_device(tmp_path, monkeypatch):
    """If the configured device index IS among the detected cameras but just
    failed to open this once, the controller should not silently switch to
    a different camera and overwrite the user's chosen device index."""
    settings = _settings(tmp_path, device_index=1)
    monkeypatch.setattr(controller_mod, "OpenCVCamera", FlakyOpenCVCamera)
    monkeypatch.setattr(
        controller_mod,
        "list_cameras",
        lambda: [CameraDevice(0, "Built-in"), CameraDevice(1, "Canon EOS Webcam")],
    )

    ctrl = MainController(settings)

    assert ctrl.camera_fallback is True
    assert settings.kamera.deviceIndex == 1  # unchanged
    assert ctrl.camera.__class__.__name__ == "SimulatorCamera"


def test_missing_device_falls_back_to_detected_camera(tmp_path, monkeypatch):
    """If the configured index doesn't exist on this machine at all (e.g. a
    laptop with only a built-in webcam at index 0, but the setting still
    points at index 1 from another machine/OS), fall back to whatever is
    actually available and persist it."""
    settings = _settings(tmp_path, device_index=1)
    opened = {}

    class WorkingOpenCVCamera:
        def __init__(self, camera_id, rotation=0, device_name=None, device_path=None):
            self.camera_id = camera_id

        def start_liveview(self):
            if self.camera_id == 1:
                raise CameraError("Kamera 1 kann nicht geoeffnet werden")
            opened["index"] = self.camera_id

    monkeypatch.setattr(controller_mod, "OpenCVCamera", WorkingOpenCVCamera)
    monkeypatch.setattr(
        controller_mod, "list_cameras", lambda: [CameraDevice(0, "Built-in")]
    )

    ctrl = MainController(settings)

    assert ctrl.camera_fallback is False
    assert opened["index"] == 0
    assert settings.kamera.deviceIndex == 0
    assert ctrl.camera.camera_id == 0
