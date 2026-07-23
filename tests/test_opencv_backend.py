"""Tests for OpenCVCamera backend fallback and black-frame auto-recovery."""

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


def test_persistent_black_frames_trigger_reopen(monkeypatch):
    _patch_backends(monkeypatch, ["ANY"])
    caps = []

    def factory(index, backend):
        cap = FakeCapture(index, backend, reads=[(True, _black_frame())])
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
    # bad-frame streak crossed the threshold.
    assert first_cap.released
    assert len(caps) == 2
    assert cam._consecutive_bad_frames == 0


def test_transient_blank_recovers_without_reopen(monkeypatch):
    _patch_backends(monkeypatch, ["ANY"])
    cap = FakeCapture(0, "ANY", reads=[(True, _black_frame()), (True, _white_frame())])
    monkeypatch.setattr(backend_mod.cv2, "VideoCapture", lambda index, backend: cap)

    cam = OpenCVCamera(0)
    cam.get_preview_qimage()

    assert cam._consecutive_bad_frames == 0
    assert not cap.released
