# app/core/camera/opencv_backend.py
import sys
import time
import logging
import threading
from contextlib import contextmanager
from pathlib import Path
import cv2
from PySide6 import QtGui
from .base import BaseCamera, CameraError

logger = logging.getLogger(__name__)

# DirectShow is Windows-only; other platforms fall back to OpenCV's auto-detection.
# Kept as the enumeration backend (enumerate.py pairs it with pygrabber's
# DirectShow-ordered device names) even though live capture now prefers MSMF.
_CAPTURE_BACKEND = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY

# Backends attempted (in order) when opening a camera for live capture. Media
# Foundation (MSMF) is what most modern Windows apps (Teams, Camera app) use
# and negotiates pixel formats more reliably with some UVC/virtual webcams
# (e.g. Canon EOS Webcam Utility) than DirectShow does. DirectShow is kept as
# a fallback for devices/drivers that only work through it.
if sys.platform == "win32":
    _LIVEVIEW_BACKENDS = [cv2.CAP_MSMF, cv2.CAP_DSHOW]
else:
    _LIVEVIEW_BACKENDS = [cv2.CAP_ANY]

# Number of consecutive blank/failed frames tolerated before the capture
# device is fully reopened (mirrors what a PC restart does, but scoped to
# just this VideoCapture instance).
_MAX_CONSECUTIVE_BAD_FRAMES = 5
# Minimum time between reopen attempts. Some virtual webcam drivers (e.g.
# Canon EOS Webcam Utility) take up to ~30s after launch before delivering
# real frames; without a cooldown the bad-frame threshold above would be hit
# every ~0.25s during that window, tearing down and rebuilding the capture
# graph dozens of times a second for no benefit and adding needless CPU load.
_REOPEN_COOLDOWN_SECONDS = 5.0
# A frame whose mean pixel value falls below this is treated as black.
_BLANK_FRAME_MEAN_THRESHOLD = 2.0
# Cap on how long any caller (GUI thread or background task) waits for the
# camera lock. A live-preview read can legitimately take a few seconds when
# the driver is having a bad moment, but if cv2 ever truly wedges inside a
# blocking call, waiting forever for the lock would freeze whichever thread
# asked for it - including the GUI thread when the operator opens Settings
# or hits reconnect - and the whole app would appear hung and need a forced
# restart. A bounded wait turns that into a clear, recoverable error instead.
_IO_LOCK_TIMEOUT_SECONDS = 10.0
# Live preview frames are only ever displayed scaled down into a small
# widget, so downscale before the (comparatively expensive) rotate/color
# conversion/QImage copy steps rather than doing that work at full sensor
# resolution every tick. Does not affect capture()/capture_preview(), which
# keep the full-resolution frame for the saved photo.
_PREVIEW_MAX_DIM = 960

# Map clockwise-rotation degrees to the corresponding cv2 constant.
# 270° CW = 90° CCW, which is the correct setting for a Canon EOS M50
# connected in webcam mode (sensor outputs landscape, portrait needed).
_CV2_ROTATION = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def _is_blank(ret: bool, frame) -> bool:
    """True if the read failed, returned nothing, or the frame is (near-)black.

    Canon EOS Webcam Utility has been observed to intermittently deliver an
    all-black feed while still reporting a successful read, so a plain
    ``ret`` check is not enough.
    """
    if not ret or frame is None:
        return True
    return bool(frame.mean() < _BLANK_FRAME_MEAN_THRESHOLD)


def _downscale_for_preview(frame):
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= _PREVIEW_MAX_DIM:
        return frame
    scale = _PREVIEW_MAX_DIM / longest
    return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


class OpenCVCamera(BaseCamera):
    def __init__(self, camera_id: int = 0, rotation: int = 0):
        self.camera_id = camera_id
        self.cap = None
        self.rotation = rotation  # degrees clockwise (0, 90, 180, 270)
        self.backend_used = None
        self._consecutive_bad_frames = 0
        self._last_reopen_time = 0.0
        # Guards every access to self.cap: the live preview (background task)
        # and an actual photo capture (also a background task) can otherwise
        # land on cap.read()/cap.release() at the same time, which is not
        # safe with a single cv2.VideoCapture handle. Reentrant because
        # _reopen() calls stop_liveview()/start_liveview() while already
        # holding the lock from _read_frame().
        self._io_lock = threading.RLock()

    @contextmanager
    def _locked(self):
        if not self._io_lock.acquire(timeout=_IO_LOCK_TIMEOUT_SECONDS):
            raise CameraError("Kamera ist gerade beschaeftigt, bitte kurz warten")
        try:
            yield
        finally:
            self._io_lock.release()

    def _rotate(self, frame):
        """Rotate *frame* by the configured amount; no-op if rotation is 0."""
        code = _CV2_ROTATION.get(self.rotation)
        if code is not None:
            return cv2.rotate(frame, code)
        return frame

    def start_liveview(self):
        with self._locked():
            if self.cap is not None:
                return
            # Once we know which backend actually works for this device, try
            # it first on subsequent (re)opens. Some backends (e.g. MSMF on
            # certain virtual webcam drivers) can take a noticeable moment to
            # fail before falling back, and that cost is pure waste on every
            # reconnect once we already know DSHOW (or whichever) is the one
            # that works.
            backends = _LIVEVIEW_BACKENDS
            if self.backend_used is not None and self.backend_used in backends:
                backends = [self.backend_used] + [b for b in backends if b != self.backend_used]
            for backend in backends:
                cap = cv2.VideoCapture(self.camera_id, backend)
                if cap.isOpened():
                    # Reduces internal frame buffering (where supported), which
                    # otherwise shows up as visible lag between the live scene
                    # and what the preview displays.
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap = cap
                    self.backend_used = backend
                    self._consecutive_bad_frames = 0
                    logger.info(
                        "Kamera %s geoeffnet (Backend %s)", self.camera_id, backend
                    )
                    return
                cap.release()
            self.backend_used = None
            raise CameraError(f"Kamera {self.camera_id} kann nicht geoeffnet werden")

    def stop_liveview(self):
        with self._locked():
            if self.cap is not None:
                self.cap.release()
                self.cap = None

    def _ensure_open(self):
        if self.cap is None:
            self.start_liveview()

    def _reopen(self):
        logger.warning(
            "Kamera %s liefert wiederholt Schwarzbilder, versuche Neuverbindung",
            self.camera_id,
        )
        self.stop_liveview()
        try:
            self.start_liveview()
        except CameraError:
            logger.warning("Neuverbindung zu Kamera %s fehlgeschlagen", self.camera_id)
            raise
        else:
            logger.info("Neuverbindung zu Kamera %s erfolgreich", self.camera_id)
        self._consecutive_bad_frames = 0

    def _read_frame(self):
        """Read a frame, retrying transient blank reads and auto-reopening the
        capture device if blank frames persist. Raises CameraError if no
        usable frame could be obtained."""
        self._ensure_open()
        ret, frame = self.cap.read()
        if _is_blank(ret, frame):
            # Transient blanks (e.g. right after opening) often clear up on
            # an immediate retry, so try a couple more times before counting
            # this as part of a persistent streak.
            for _ in range(2):
                ret, frame = self.cap.read()
                if not _is_blank(ret, frame):
                    break

        if not _is_blank(ret, frame):
            self._consecutive_bad_frames = 0
            return frame

        self._consecutive_bad_frames += 1
        if self._consecutive_bad_frames == 1:
            logger.warning("Schwarzbild von Kamera %s erhalten", self.camera_id)
        now = time.monotonic()
        if (
            self._consecutive_bad_frames >= _MAX_CONSECUTIVE_BAD_FRAMES
            and now - self._last_reopen_time >= _REOPEN_COOLDOWN_SECONDS
        ):
            self._last_reopen_time = now
            self._reopen()
            ret, frame = self.cap.read()
            if not _is_blank(ret, frame):
                self._consecutive_bad_frames = 0
                return frame

        raise CameraError("Kein Bild von Kamera erhalten")

    def capture(self, dest: Path) -> None:
        with self._locked():
            frame = self._read_frame()
            frame = self._rotate(frame)
            cv2.imwrite(str(dest), frame)

    def capture_preview(self, dest: Path) -> None:
        self.capture(dest)

    def get_preview_qimage(self) -> QtGui.QImage:
        with self._locked():
            frame = self._read_frame()
            frame = _downscale_for_preview(frame)
            frame = self._rotate(frame)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            img = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            return img.copy()
