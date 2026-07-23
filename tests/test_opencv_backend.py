"""Tests for OpenCVCamera backend fallback and read-failure auto-recovery."""

import threading

import numpy as np
import pytest

from app.core.camera import opencv_backend as backend_mod
from app.core.camera.base import CameraError
from app.core.camera.opencv_backend import OpenCVCamera


def _black_frame():
    return np.zeros((4, 4, 3), dtype=np.uint8)


def _white_frame():
    return np.full((4, 4, 3), 255, dtype=np.uint8)


class FakeCapture:
    """Stand-in for cv2.VideoCapture with a scriptable sequence of reads."""

    def __init__(self, index, backend, opens: bool = True, reads=None):
        self.index = index
        self.backend = backend
        self._opens = opens
        self._reads = list(reads) if reads is not None else [(True, _white_frame())]
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


def test_good_frames_do_not_trigger_recovery(monkeypatch):
    _patch_backends(monkeypatch, ["ANY"])
    cap = FakeCapture(0, "ANY", reads=[(True, _white_frame())])
    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", lambda index, backend: cap)

    cam = OpenCVCamera(0)
    for _ in range(10):
        cam.get_preview_qimage()

    assert cam._consecutive_bad_frames == 0
    assert not cap.released


def test_dark_frames_are_not_treated_as_errors(monkeypatch):
    """A dark/placeholder frame (e.g. Canon EOS Webcam Utility's "connect
    your camera" graphic before it detects the physical camera) is a valid
    frame, not a failure - it must be displayed like any other frame and
    must never trigger a reopen. Reopening doesn't speed up the driver's
    own detection and can reset/prolong it."""
    _patch_backends(monkeypatch, ["ANY"])
    cap = FakeCapture(0, "ANY", reads=[(True, _black_frame())])
    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", lambda index, backend: cap)

    cam = OpenCVCamera(0)
    for _ in range(10):
        img = cam.get_preview_qimage()
        assert not img.isNull()

    assert cam._consecutive_bad_frames == 0
    assert not cap.released


def test_persistent_read_failures_trigger_reopen(monkeypatch):
    _patch_backends(monkeypatch, ["ANY"])
    caps = []

    def factory(index, backend):
        cap = FakeCapture(index, backend, reads=[(False, None)])
        caps.append(cap)
        return cap

    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", factory)
    monkeypatch.setattr(backend_mod, "_MAX_CONSECUTIVE_BAD_FRAMES", 3)

    cam = OpenCVCamera(0)
    cam.start_liveview()
    first_cap = caps[0]

    for _ in range(3):
        with pytest.raises(CameraError):
            cam.get_preview_qimage()

    # First capture should have been released and a new one opened once the
    # failure streak crossed the threshold.
    assert first_cap.released
    assert len(caps) == 2
    assert cam._consecutive_bad_frames == 0


def test_reopen_reuses_last_working_backend(monkeypatch):
    """Once a backend has worked, reopening (after a failure streak) should
    try it first rather than re-probing ones already known to fail on this
    device (e.g. MSMF on some virtual webcam drivers)."""
    _patch_backends(monkeypatch, ["MSMF", "DSHOW"])
    monkeypatch.setattr(backend_mod, "_MAX_CONSECUTIVE_BAD_FRAMES", 1)
    attempts = []

    def factory(index, backend):
        attempts.append(backend)
        opens = backend == "DSHOW"
        reads = [(False, None)] if opens else [(True, _white_frame())]
        return FakeCapture(index, backend, opens=opens, reads=reads)

    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", factory)

    cam = OpenCVCamera(0)
    cam.start_liveview()
    assert attempts == ["MSMF", "DSHOW"]

    with pytest.raises(CameraError):
        cam.get_preview_qimage()

    # The reopen triggered by the failure streak should have tried DSHOW
    # (the previously-working backend) first, without probing MSMF again.
    assert attempts == ["MSMF", "DSHOW", "DSHOW"]


def test_transient_read_failure_recovers_without_reopen(monkeypatch):
    _patch_backends(monkeypatch, ["ANY"])
    cap = FakeCapture(0, "ANY", reads=[(False, None), (True, _white_frame())])
    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", lambda index, backend: cap)

    cam = OpenCVCamera(0)
    cam.get_preview_qimage()

    assert cam._consecutive_bad_frames == 0
    assert not cap.released


def test_lock_timeout_raises_instead_of_blocking_forever(monkeypatch):
    """If a read is (or looks) stuck holding the camera lock forever, any
    other caller - notably the GUI thread doing a settings-driven reconnect -
    must get a bounded wait and a clear error instead of hanging until the
    whole app has to be force-restarted."""
    _patch_backends(monkeypatch, ["ANY"])
    monkeypatch.setattr(backend_mod, "_IO_LOCK_TIMEOUT_SECONDS", 0.2)
    cap = FakeCapture(0, "ANY", reads=[(True, _white_frame())])
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
