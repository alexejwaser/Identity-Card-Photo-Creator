# app/core/camera/enumerate.py
"""Camera device enumeration.

Isolates device probing and the Windows-only naming dependency (pygrabber)
from opencv_backend.py so nothing imports pygrabber eagerly on non-Windows.
"""
from __future__ import annotations
import sys
from dataclasses import dataclass
import cv2


@dataclass
class CameraDevice:
    index: int
    name: str


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


def list_cameras(max_index: int = 10) -> list[CameraDevice]:
    indices = _probe_indices(max_index)
    names = _windows_device_names()
    devices = []
    for idx in indices:
        name = names[idx] if names and idx < len(names) else f"Kamera {idx}"
        devices.append(CameraDevice(idx, name))
    return devices
