"""Tests for OpenCVCamera: backend fallback and basic frame reads.

The camera just streams whatever frame the device provides - it does not
inspect frame content or attempt automatic recovery based on it. Drivers
like Canon EOS Webcam Utility are responsible for their own hand-off from
a placeholder graphic to live video; this class only cares whether a read
succeeded or failed.
"""

import threading

import numpy as np
import pytest

from app.core.camera import opencv_backend as backend_mod
from app.core.camera.base import CameraError
from app.core.camera.opencv_backend import OpenCVCamera


def _frame():
    return np.zeros((4, 4, 3), dtype=np.uint8)


class FakeCapture:
    """Stand-in for cv2.VideoCapture with a scriptable sequence of reads."""

    def __init__(self, index, backend, opens: bool = True, reads=None):
        self.index = index
        self.backend = backend
        self._opens = opens
        self._reads = list(reads) if reads is not None else [(True, _frame())]
        self.released = False

    def isOpened(self):
        return self._opens

    def set(self, prop, value):
        return True

    def read(self):
        if len(self._reads) > 1:
            return self._reads.pop(0)
        return self._reads[0]

    def release(self):
        self.released = True


def _patch_backends(monkeypatch, backends):
    monkeypatch.setattr(backend_mod, "_LIVEVIEW_BACKENDS", backends)


def test_start_liveview_uses_first_working_backend(monkeypatch):
    _patch_backends(monkeypatch, ["MSMF", "DSHOW"])

    def factory(index, backend):
        return FakeCapture(index, backend, opens=(backend == "MSMF"))

    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", factory)

    cam = OpenCVCamera(0)
    cam.start_liveview()

    assert cam.backend_used == "MSMF"


def test_start_liveview_falls_back_when_first_backend_fails(monkeypatch):
    _patch_backends(monkeypatch, ["MSMF", "DSHOW"])

    def factory(index, backend):
        return FakeCapture(index, backend, opens=(backend == "DSHOW"))

    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", factory)

    cam = OpenCVCamera(0)
    cam.start_liveview()

    assert cam.backend_used == "DSHOW"


def test_start_liveview_raises_when_all_backends_fail(monkeypatch):
    _patch_backends(monkeypatch, ["MSMF", "DSHOW"])
    monkeypatch.setattr(
        backend_mod.cv2, "VideoCapture", lambda index, backend: FakeCapture(index, backend, opens=False)
    )

    cam = OpenCVCamera(0)
    with pytest.raises(CameraError):
        cam.start_liveview()


def test_reopen_reuses_last_working_backend(monkeypatch):
    """Once a backend has worked, a later reopen (e.g. via the manual
    reconnect action) should try it first rather than re-probing ones
    already known to fail on this device (e.g. MSMF on some virtual
    webcam drivers)."""
    _patch_backends(monkeypatch, ["MSMF", "DSHOW"])
    attempts = []

    def factory(index, backend):
        attempts.append(backend)
        return FakeCapture(index, backend, opens=(backend == "DSHOW"))

    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", factory)

    cam = OpenCVCamera(0)
    cam.start_liveview()
    assert attempts == ["MSMF", "DSHOW"]

    cam.stop_liveview()
    cam.start_liveview()

    assert attempts == ["MSMF", "DSHOW", "DSHOW"]


def test_start_liveview_opens_resolved_index_per_backend(monkeypatch):
    """When a device name/path is saved, the index is re-resolved for the
    backend actually opening the camera - so the DirectShow-vs-MediaFoundation
    index mismatch cannot open the wrong device."""
    _patch_backends(monkeypatch, ["MSMF", "DSHOW"])
    opened = []

    def factory(index, backend):
        opened.append((index, backend))
        return FakeCapture(index, backend, opens=(backend == "MSMF"))

    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", factory)
    # Saved index is a stale DirectShow index (1); resolution returns the real
    # MSMF index (4) for this device.
    monkeypatch.setattr(
        backend_mod, "resolve_backend_index",
        lambda backend, name, path, fallback_index: 4 if backend == "MSMF" else fallback_index,
    )

    cam = OpenCVCamera(1, device_name="EOS Webcam Utility", device_path="usb#eos")
    cam.start_liveview()

    assert opened[0] == (4, "MSMF")
    assert cam.backend_used == "MSMF"


def test_get_preview_qimage_returns_whatever_frame_is_read(monkeypatch):
    """A dark/placeholder frame (e.g. Canon EOS Webcam Utility's "connect
    your camera" graphic before it detects the physical camera) is just
    displayed like any other frame - the driver owns the hand-off to live
    video, not this class."""
    _patch_backends(monkeypatch, ["ANY"])
    cap = FakeCapture(0, "ANY", reads=[(True, _frame())])
    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", lambda index, backend: cap)

    cam = OpenCVCamera(0)
    for _ in range(10):
        img = cam.get_preview_qimage()
        assert not img.isNull()

    assert not cap.released


def test_read_failure_raises_but_does_not_reopen(monkeypatch):
    """A failed read surfaces as an error for that tick only; the same
    connection is tried again next time, with no automatic teardown."""
    _patch_backends(monkeypatch, ["ANY"])
    cap = FakeCapture(0, "ANY", reads=[(False, None)])
    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", lambda index, backend: cap)

    cam = OpenCVCamera(0)
    with pytest.raises(CameraError):
        cam.get_preview_qimage()

    assert not cap.released


def test_lock_timeout_raises_instead_of_blocking_forever(monkeypatch):
    """If a read is (or looks) stuck holding the camera lock forever, any
    other caller - notably the GUI thread doing a settings-driven reconnect -
    must get a bounded wait and a clear error instead of hanging until the
    whole app has to be force-restarted."""
    _patch_backends(monkeypatch, ["ANY"])
    monkeypatch.setattr(backend_mod, "_IO_LOCK_TIMEOUT_SECONDS", 0.2)
    cap = FakeCapture(0, "ANY", reads=[(True, _frame())])
    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", lambda index, backend: cap)

    cam = OpenCVCamera(0)
    cam.start_liveview()

    # Simulate another thread wedged inside a camera call, holding the lock.
    cam._io_lock.acquire()
    try:
        start = threading.Event()
        error = {}

        def blocked_call():
            start.set()
            try:
                cam.stop_liveview()
            except CameraError as e:
                error["e"] = e

        t = threading.Thread(target=blocked_call)
        t.start()
        start.wait()
        t.join(timeout=2)
        assert not t.is_alive()
        assert "e" in error
    finally:
        cam._io_lock.release()
