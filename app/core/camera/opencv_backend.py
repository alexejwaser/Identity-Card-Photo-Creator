# app/core/camera/opencv_backend.py
import sys
import logging
import threading
from contextlib import contextmanager
from pathlib import Path
import cv2
from PySide6 import QtGui
from .base import BaseCamera, CameraError
from .enumerate import resolve_backend_index

logger = logging.getLogger(__name__)

# Human-readable backend labels for the diagnostic log. Values not in the map
# (e.g. a monkeypatched string in tests) are logged verbatim.
_BACKEND_NAMES = {
    getattr(cv2, "CAP_MSMF", -101): "MSMF",
    getattr(cv2, "CAP_DSHOW", -102): "DSHOW",
    getattr(cv2, "CAP_ANY", 0): "ANY",
}


def _backend_label(backend) -> str:
    return _BACKEND_NAMES.get(backend, str(backend))

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


def _downscale_for_preview(frame):
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= _PREVIEW_MAX_DIM:
        return frame
    scale = _PREVIEW_MAX_DIM / longest
    return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


class OpenCVCamera(BaseCamera):
    """Reads frames from an OpenCV/DirectShow camera index, including
    virtual webcam drivers such as Canon EOS Webcam Utility. Once opened,
    this just streams whatever frame the device currently provides - e.g.
    EOS Webcam Utility's own "connect your camera" placeholder while it
    detects the physical camera, then its live feed once it does - the
    same way any other webcam viewer would. The driver is responsible for
    that hand-off; this class does not inspect frame content or guess
    about it."""

    def __init__(
        self,
        camera_id: int = 0,
        rotation: int = 0,
        device_name: str | None = None,
        device_path: str | None = None,
    ):
        self.camera_id = camera_id
        self.rotation = rotation  # degrees clockwise (0, 90, 180, 270)
        # Stable identifiers for the chosen device. When set, the correct index
        # is re-resolved for whichever backend actually opens the camera, so the
        # DirectShow-vs-MediaFoundation index mismatch cannot open the wrong
        # device (or nothing). camera_id is used as the fallback/hint.
        self.device_name = device_name
        self.device_path = device_path
        self.cap = None
        self.backend_used = None
        # Log the negotiated resolution / frame brightness only once per open,
        # so a real session log confirms the right device delivers real frames
        # without spamming a line every tick.
        self._open_diagnostics_logged = False
        # Guards every access to self.cap: the live preview (background task)
        # and an actual photo capture (also a background task) can otherwise
        # land on cap.read()/cap.release() at the same time, which is not
        # safe with a single cv2.VideoCapture handle.
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
                # Re-resolve the index for this specific backend so the saved
                # device opens on MSMF and DSHOW alike; falls back to the stored
                # camera_id when no name/path is set or resolution is unavailable.
                index = resolve_backend_index(
                    backend,
                    name=self.device_name,
                    path=self.device_path,
                    fallback_index=self.camera_id,
                )
                if index is None:
                    index = self.camera_id
                cap = cv2.VideoCapture(index, backend)
                if cap.isOpened():
                    # Reduces internal frame buffering (where supported), which
                    # otherwise shows up as visible lag between the live scene
                    # and what the preview displays.
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap = cap
                    self.backend_used = backend
                    self._open_diagnostics_logged = False
                    logger.info(
                        "Kamera '%s' geoeffnet: Index %s, Backend %s",
                        self.device_name or self.camera_id,
                        index,
                        _backend_label(backend),
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

    def _read_frame(self):
        """Read a single frame. Raises CameraError only if the read itself
        fails - the next tick simply tries again on the same connection,
        exactly like any other webcam viewer. Frame content (e.g. a driver's
        own placeholder graphic while it detects the physical camera) is
        never inspected or second-guessed."""
        self._ensure_open()
        ret, frame = self.cap.read()
        if not ret or frame is None:
            raise CameraError("Kein Bild von Kamera erhalten")
        if not self._open_diagnostics_logged:
            self._log_first_frame(frame)
        return frame

    def _log_first_frame(self, frame) -> None:
        """Log the negotiated resolution and this device's mean frame
        brightness once per open. A near-zero mean here (with a virtual webcam
        like EOS Webcam Utility) means the driver is delivering black rather
        than its placeholder/live feed, which is exactly the signal needed to
        tell a wrong-device open apart from a genuinely dark scene."""
        self._open_diagnostics_logged = True
        try:
            h, w = frame.shape[:2]
            logger.info(
                "Kamera '%s' erstes Bild: %sx%s, mittlere Helligkeit %.1f "
                "(Backend %s)",
                self.device_name or self.camera_id,
                w,
                h,
                float(frame.mean()),
                _backend_label(self.backend_used),
            )
        except Exception:
            pass

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
