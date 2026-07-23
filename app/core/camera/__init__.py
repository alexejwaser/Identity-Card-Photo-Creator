import sys

from .base import BaseCamera, CameraError
from .simulator import SimulatorCamera
from .gphoto2_backend import GPhoto2Camera
from .opencv_backend import OpenCVCamera
from .enumerate import list_cameras, CameraDevice


def make_webcam_camera(
    camera_id: int = 0,
    rotation: int = 0,
    device_name: str | None = None,
    device_path: str | None = None,
) -> BaseCamera:
    """Build the webcam-mode camera for this platform.

    On Windows, capture goes through DirectShow/pygrabber: OpenCV cannot capture
    the production camera at all here (its MSMF plugin DLL is not shipped in the
    pip wheels, and its DirectShow path returns black for the Canon EOS Webcam
    Utility virtual webcam), whereas pygrabber reads real frames from both that
    virtual webcam and ordinary UVC cameras. Elsewhere, OpenCV is used directly.
    """
    if sys.platform == "win32":
        from .directshow_backend import DirectShowCamera

        return DirectShowCamera(
            camera_id,
            rotation=rotation,
            device_name=device_name,
            device_path=device_path,
        )
    return OpenCVCamera(
        camera_id,
        rotation=rotation,
        device_name=device_name,
        device_path=device_path,
    )


__all__ = [
    'BaseCamera',
    'CameraError',
    'SimulatorCamera',
    'GPhoto2Camera',
    'OpenCVCamera',
    'make_webcam_camera',
    'list_cameras',
    'CameraDevice',
]
