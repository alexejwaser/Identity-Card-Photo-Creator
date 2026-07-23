"""Tests for camera device enumeration."""

from app.core.camera import enumerate as cam_enum
from app.core.camera.enumerate import list_cameras, CameraDevice, resolve_backend_index


class FakeCapture:
    """Minimal stand-in for cv2.VideoCapture that reports 'opened' only for a
    fixed set of indices."""

    opened_indices = {0, 2}

    def __init__(self, index, backend=None):
        self.index = index

    def isOpened(self):
        return self.index in self.opened_indices

    def release(self):
        pass


def test_list_cameras_generic_labels(monkeypatch):
    monkeypatch.setattr(cam_enum.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(cam_enum, "_windows_device_names", lambda: None)

    devices = list_cameras(max_index=5)

    assert [d.index for d in devices] == [0, 2]
    assert all(isinstance(d, CameraDevice) for d in devices)
    assert devices[0].name == "Kamera 0"
    assert devices[1].name == "Kamera 2"


def test_list_cameras_windows_names(monkeypatch):
    monkeypatch.setattr(cam_enum.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(
        cam_enum,
        "_windows_device_names",
        lambda: ["Integrated Webcam", "Virtual Cam", "Canon EOS Webcam"],
    )

    devices = list_cameras(max_index=5)

    assert [d.index for d in devices] == [0, 2]
    assert devices[0].name == "Integrated Webcam"
    assert devices[1].name == "Canon EOS Webcam"


def test_list_cameras_names_shorter_than_index(monkeypatch):
    """Falls back to a generic label if the pygrabber name list is shorter than
    the probed index (avoids IndexError)."""
    monkeypatch.setattr(cam_enum.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(cam_enum, "_windows_device_names", lambda: ["Only One"])

    devices = list_cameras(max_index=5)

    assert devices[0].name == "Only One"
    assert devices[1].name == "Kamera 2"


def test_list_cameras_empty(monkeypatch):
    class NoneOpen(FakeCapture):
        opened_indices = set()

    monkeypatch.setattr(cam_enum.cv2, "VideoCapture", NoneOpen)
    monkeypatch.setattr(cam_enum, "_windows_device_names", lambda: None)

    assert list_cameras(max_index=5) == []


# --- resolve_backend_index -------------------------------------------------

def _fake_backend_devices(monkeypatch, devices):
    monkeypatch.setattr(cam_enum, "_enumerate_via_cv2ec", lambda backend: devices)


def test_resolve_returns_fallback_without_name_or_path(monkeypatch):
    _fake_backend_devices(monkeypatch, [CameraDevice(0, "Cam", "path0")])
    assert resolve_backend_index(700, fallback_index=5) == 5


def test_resolve_prefers_path_over_name(monkeypatch):
    _fake_backend_devices(
        monkeypatch,
        [CameraDevice(3, "EOS Webcam Utility", "usb#vid_04a9"),
         CameraDevice(7, "Other", "usb#vid_ffff")],
    )
    # Name would match index 3, but path points at index 7.
    assert resolve_backend_index(
        700, name="EOS Webcam Utility", path="usb#vid_ffff"
    ) == 7


def test_resolve_matches_name_exact_then_substring(monkeypatch):
    _fake_backend_devices(
        monkeypatch,
        [CameraDevice(0, "Integrated Webcam"), CameraDevice(2, "EOS Webcam Utility #2")],
    )
    # Substring match: saved "EOS Webcam Utility" vs enumerated "... #2".
    assert resolve_backend_index(1400, name="EOS Webcam Utility") == 2


def test_resolve_falls_back_when_no_match(monkeypatch):
    _fake_backend_devices(monkeypatch, [CameraDevice(0, "Integrated Webcam")])
    assert resolve_backend_index(700, name="Nonexistent", fallback_index=1) == 1


def test_resolve_falls_back_when_library_unavailable(monkeypatch):
    monkeypatch.setattr(cam_enum, "_enumerate_via_cv2ec", lambda backend: None)
    assert resolve_backend_index(700, name="EOS", fallback_index=4) == 4
