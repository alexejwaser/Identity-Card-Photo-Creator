# app/core/camera/directshow_backend.py
"""DirectShow capture backend (Windows) built on pygrabber.

Why this exists
---------------
On the production Windows machine OpenCV cannot capture the camera at all:

* OpenCV's Media Foundation (MSMF) backend is a *plugin* DLL
  (``opencv_videoio_msmf*.dll``) that the ``opencv-python``/``-headless`` pip
  wheels do not ship, so every MSMF open fails ("backend is not available").
* OpenCV's DirectShow backend opens the device but, for the Canon EOS Webcam
  Utility virtual webcam, negotiates a media type it cannot decode and delivers
  pure-black frames.

pygrabber builds a DirectShow graph with a SampleGrabber that explicitly asks
for ``RGB24`` output, which makes DirectShow insert a colour converter. That is
exactly what lets it read real frames from EOS Webcam Utility (and from ordinary
UVC webcams) where OpenCV's DirectShow path returns black. pygrabber is already
a dependency (used for device enumeration), so this adds no new package.

Threading / COM
---------------
All COM/DirectShow work is confined to a single owner thread created per open:
it initialises COM, builds and runs the graph, then loops re-arming the grabber
so the newest frame is continuously copied into ``self._latest``. ``grab_frame``
itself only sets a Python flag; the frame is delivered on DirectShow's own
streaming thread via ``BufferCB``. Reader methods (``capture`` /
``get_preview_qimage``, called from Qt worker threads) never touch COM - they
just copy the buffered numpy frame under a lock - so there is no cross-apartment
call and no message-pump requirement.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import cv2
from PySide6 import QtGui

from .base import BaseCamera, CameraError
from .enumerate import _normalize
# Reuse the exact preview scaling / rotation behaviour of the OpenCV backend so
# both paths look and behave identically to the rest of the app.
from .opencv_backend import _CV2_ROTATION, _downscale_for_preview

logger = logging.getLogger(__name__)

# How long a reader waits for the first frame to arrive after opening. EOS
# Webcam Utility can take a moment to start delivering; the live preview shows
# "Kamera wird geladen…" until then instead of erroring hard.
_FIRST_FRAME_TIMEOUT_SECONDS = 5.0
# Bounded wait for the capture lock, mirroring OpenCVCamera: a wedged read must
# never freeze the GUI thread forever.
_IO_LOCK_TIMEOUT_SECONDS = 10.0
# How long stop_liveview waits for the owner thread to tear the graph down.
_STOP_JOIN_TIMEOUT_SECONDS = 5.0
# Owner-thread poll interval between re-arming the grabber (~33 fps). The device
# frame rate, not this value, ultimately paces delivery.
_GRAB_INTERVAL_SECONDS = 0.03


def _resolve_pygrabber_index(devices: list[str], name, path, fallback_index):
    """Return the pygrabber (DirectShow-ordered) device index for the saved
    device, matched by *name*. ``devices`` is ``FilterGraph.get_input_devices()``.

    pygrabber exposes only device names (no stable path), so the saved
    ``deviceName`` is the reliable key here; the DirectShow-ordered index is used
    as a last resort. Path is accepted for signature symmetry but unused."""
    target = _normalize(name)
    if target:
        for i, dev_name in enumerate(devices):
            if _normalize(dev_name) == target:
                return i
        for i, dev_name in enumerate(devices):
            nd = _normalize(dev_name)
            if target in nd or nd in target:
                return i
    if fallback_index is not None and 0 <= fallback_index < len(devices):
        return fallback_index
    return 0 if devices else None


class DirectShowCamera(BaseCamera):
    """Streams frames from a DirectShow webcam via pygrabber. Delivers whatever
    the device currently provides - e.g. EOS Webcam Utility's own placeholder
    while it detects the physical camera, then the live feed once it does - the
    same way any other webcam viewer would. Frame content is never inspected."""

    def __init__(
        self,
        camera_id: int = 0,
        rotation: int = 0,
        device_name: str | None = None,
        device_path: str | None = None,
    ):
        self.camera_id = camera_id
        self.rotation = rotation  # degrees clockwise (0, 90, 180, 270)
        self.device_name = device_name
        self.device_path = device_path

        # Latest frame, stored in BGR (matching OpenCVCamera) so all downstream
        # rotate / imwrite / QImage logic is identical to the OpenCV path.
        self._latest = None
        self._frame_lock = threading.Lock()
        self._have_frame = threading.Event()

        # Owner-thread lifecycle.
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._started = threading.Event()
        self._start_error: Exception | None = None
        self._resolution: tuple[int, int] | None = None

        # Serialises capture() vs. get_preview_qimage(), like OpenCVCamera's lock.
        self._io_lock = threading.RLock()
        self._open_diagnostics_logged = False

    # -- owner thread --------------------------------------------------------
    def _on_frame(self, frame) -> None:
        """SampleGrabber callback (runs on DirectShow's streaming thread).

        The grabber is configured for ``RGB24``, which on Windows is physically
        stored **BGR** in memory; pygrabber reshapes that buffer without
        reordering channels (it only flips vertically), so the array it hands us
        is already BGR - i.e. OpenCV's native convention. Store it as-is; a
        colour conversion here would swap red and blue (skin tones turn blue)."""
        if frame is None:
            return
        with self._frame_lock:
            self._latest = frame
        self._have_frame.set()

    def _run(self) -> None:
        import comtypes

        com_ready = False
        graph = None
        try:
            # Multithreaded apartment: no message pump needed for a background
            # capture thread, and the SampleGrabber callback is delivered freely.
            try:
                comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
                com_ready = True
            except OSError:
                # COM already initialised on this thread with another mode; the
                # graph still works, just skip our matching CoUninitialize.
                pass

            from pygrabber.dshow_graph import FilterGraph

            graph = FilterGraph()
            devices = graph.get_input_devices()
            index = _resolve_pygrabber_index(
                devices, self.device_name, self.device_path, self.camera_id
            )
            if index is None:
                raise CameraError(f"Kamera {self.camera_id} kann nicht geoeffnet werden")

            graph.add_video_input_device(index)
            graph.add_sample_grabber(self._on_frame)
            graph.add_null_render()
            graph.prepare_preview_graph()
            self._resolution = graph.get_input_device().get_current_format()
            graph.run()

            logger.info(
                "Kamera '%s' geoeffnet: Index %s, Backend DirectShow (pygrabber)",
                self.device_name or self.camera_id,
                index,
            )
            self._started.set()

            # Continuously re-arm the grabber so _latest tracks the live feed.
            while not self._stop.is_set():
                graph.grab_frame()
                self._stop.wait(_GRAB_INTERVAL_SECONDS)
        except Exception as e:  # includes CameraError and any COM error
            self._start_error = e
            self._started.set()
        finally:
            if graph is not None:
                try:
                    graph.stop()
                except Exception:
                    pass
            if com_ready:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

    # -- lifecycle -----------------------------------------------------------
    def start_liveview(self):
        with self._locked():
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._started.clear()
            self._have_frame.clear()
            self._start_error = None
            with self._frame_lock:
                self._latest = None
            self._open_diagnostics_logged = False
            self._thread = threading.Thread(
                target=self._run, name="DirectShowCamera", daemon=True
            )
            self._thread.start()
            # Wait until the graph is running (or failed) before returning, so a
            # bad device surfaces as an exception here just like OpenCVCamera.
            if not self._started.wait(timeout=_IO_LOCK_TIMEOUT_SECONDS):
                self._stop.set()
                raise CameraError(
                    f"Kamera {self.camera_id} reagiert nicht beim Oeffnen"
                )
            if self._start_error is not None:
                err = self._start_error
                self._join_thread()
                if isinstance(err, CameraError):
                    raise err
                raise CameraError(
                    f"Kamera {self.camera_id} kann nicht geoeffnet werden: {err}"
                )

    def stop_liveview(self):
        with self._locked():
            self._stop.set()
            self._join_thread()
            with self._frame_lock:
                self._latest = None
            self._have_frame.clear()

    def _join_thread(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=_STOP_JOIN_TIMEOUT_SECONDS)

    # -- reading -------------------------------------------------------------
    def _ensure_open(self):
        if self._thread is None or not self._thread.is_alive():
            self.start_liveview()

    def _read_frame(self):
        """Return the most recent frame (BGR). Waits briefly for the first frame
        after opening; raises CameraError if none arrives, so the live preview
        shows its "loading" message and simply retries next tick."""
        self._ensure_open()
        if not self._have_frame.wait(timeout=_FIRST_FRAME_TIMEOUT_SECONDS):
            raise CameraError("Kein Bild von Kamera erhalten")
        with self._frame_lock:
            frame = None if self._latest is None else self._latest.copy()
        if frame is None:
            raise CameraError("Kein Bild von Kamera erhalten")
        if not self._open_diagnostics_logged:
            self._log_first_frame(frame)
        return frame

    def _log_first_frame(self, frame) -> None:
        self._open_diagnostics_logged = True
        try:
            h, w = frame.shape[:2]
            logger.info(
                "Kamera '%s' erstes Bild: %sx%s, mittlere Helligkeit %.1f "
                "(Backend DirectShow (pygrabber))",
                self.device_name or self.camera_id,
                w,
                h,
                float(frame.mean()),
            )
        except Exception:
            pass

    def _rotate(self, frame):
        code = _CV2_ROTATION.get(self.rotation)
        if code is not None:
            return cv2.rotate(frame, code)
        return frame

    # -- BaseCamera API ------------------------------------------------------
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

    # -- helpers -------------------------------------------------------------
    def _locked(self):
        return _LockCtx(self._io_lock)


class _LockCtx:
    """Bounded-acquire context manager for the capture lock (mirrors
    OpenCVCamera): a wedged read must not freeze the GUI thread forever."""

    def __init__(self, lock: threading.RLock):
        self._lock = lock

    def __enter__(self):
        if not self._lock.acquire(timeout=_IO_LOCK_TIMEOUT_SECONDS):
            raise CameraError("Kamera ist gerade beschaeftigt, bitte kurz warten")
        return self

    def __exit__(self, *exc):
        self._lock.release()
        return False
