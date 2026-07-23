# app/core/camera/enumerate.py
"""Camera device enumeration.

Isolates device probing and the Windows naming/backend dependencies from
opencv_backend.py so nothing imports platform-specific libraries eagerly on
non-Windows.

Enumeration and live capture must agree on the *same* backend, otherwise the
index the operator picks is meaningless: OpenCV's Media Foundation (MSMF) and
DirectShow (DSHOW) backends enumerate devices in a different order and count,
so a DirectShow index handed to MSMF can open a different device (or nothing).
Live capture prefers MSMF (what Teams/Windows Camera use, which negotiates
reliably with virtual webcams such as Canon EOS Webcam Utility), so we enumerate
through MSMF too and remember each device's stable OS path so the exact same
physical device can be re-resolved for whichever backend actually opens it.
"""
from __future__ import annotations
import logging
import sys
from dataclasses import dataclass
import cv2

logger = logging.getLogger(__name__)


@dataclass
class CameraDevice:
    index: int
    name: str
    # Stable OS device path (e.g. the symbolic link / device instance path).
    # Survives backend differences and reordering, so it is the preferred key
    # for re-resolving a saved device. None when the enumeration source cannot
    # provide it (generic probing / pygrabber fallback).
    path: str | None = None


def _enumerate_via_cv2ec(backend: int) -> list[CameraDevice] | None:
    """Enumerate cameras for a specific cv2 *backend* via cv2_enumerate_cameras.

    Returns a list whose ``index`` is the correct value to pass to
    ``cv2.VideoCapture(index, backend)`` for that same backend, plus the
    device's name and stable path. Returns None when the library is missing or
    enumeration is unavailable, so callers can fall back to generic probing.
    """
    try:
        from cv2_enumerate_cameras import enumerate_cameras
    except ImportError:
        return None
    try:
        infos = enumerate_cameras(backend)
    except Exception:
        return None
    devices = []
    for info in infos:
        path = getattr(info, "path", None)
        devices.append(CameraDevice(int(info.index), info.name, path or None))
    return devices


def _probe_indices(max_index: int = 10, backend: int | None = None) -> list[int]:
    from .opencv_backend import _CAPTURE_BACKEND
    backend = backend if backend is not None else _CAPTURE_BACKEND
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, backend)
        try:
            if cap.isOpened():
                found.append(i)
        finally:
            cap.release()
    return found


def _windows_device_names() -> list[str] | None:
    """Ordered DirectShow device names via pygrabber, matching cv2.CAP_DSHOW's
    index order. None if unavailable (non-Windows or pygrabber not installed)."""
    if sys.platform != "win32":
        return None
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return None
    try:
        return FilterGraph().get_input_devices()
    except Exception:
        return None


def _list_cameras_by_probing(max_index: int) -> list[CameraDevice]:
    """Self-consistent DirectShow fallback: probe DSHOW indices and label them
    with DirectShow-ordered names (pygrabber). Matches the historically-working
    behavior when cv2_enumerate_cameras/MSMF is unavailable."""
    indices = _probe_indices(max_index)
    names = _windows_device_names()
    devices = []
    for idx in indices:
        name = names[idx] if names and idx < len(names) else f"Kamera {idx}"
        devices.append(CameraDevice(idx, name))
    return devices


def list_cameras(max_index: int = 10) -> list[CameraDevice]:
    """List available cameras, indexed for the live-capture backend.

    On Windows, enumerate through Media Foundation (matching live capture's
    preferred backend) so the returned index is directly usable and each device
    carries a stable path. Falls back to generic DirectShow probing when the
    Media Foundation enumeration is unavailable.
    """
    if sys.platform == "win32":
        devices = _enumerate_via_cv2ec(cv2.CAP_MSMF)
        if devices:
            return devices
    return _list_cameras_by_probing(max_index)


def _normalize(text: str | None) -> str:
    return (text or "").strip().casefold()


def resolve_backend_index(
    backend: int,
    name: str | None = None,
    path: str | None = None,
    fallback_index: int | None = None,
) -> int | None:
    """Return the ``cv2.VideoCapture`` index for *backend* that identifies the
    device described by *path* (preferred) or *name*.

    This is what makes a saved device open the *same physical camera* no matter
    which backend ends up serving it: the index is re-resolved per backend
    rather than reused blindly. Returns *fallback_index* when resolution is
    unavailable (library missing, non-matching backend) or no device matches.
    """
    if not name and not path:
        return fallback_index
    devices = _enumerate_via_cv2ec(backend)
    if not devices:
        return fallback_index

    if path:
        for d in devices:
            if d.path and d.path == path:
                return d.index

    if name:
        target = _normalize(name)
        # Exact name match first, then a lenient substring match (driver names
        # can pick up suffixes like "#2" across reboots/backends).
        for d in devices:
            if _normalize(d.name) == target:
                return d.index
        for d in devices:
            nd = _normalize(d.name)
            if target and (target in nd or nd in target):
                return d.index

    return fallback_index
