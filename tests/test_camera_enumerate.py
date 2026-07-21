"""Tests for camera device enumeration."""

from app.core.camera import enumerate as cam_enum
from app.core.camera.enumerate import list_cameras, CameraDevice


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
