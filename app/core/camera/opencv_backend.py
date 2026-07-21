# app/core/camera/opencv_backend.py
import sys
from pathlib import Path
import cv2
from PySide6 import QtGui
from .base import BaseCamera, CameraError

# DirectShow is Windows-only; other platforms fall back to OpenCV's auto-detection.
_CAPTURE_BACKEND = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY

# Map clockwise-rotation degrees to the corresponding cv2 constant.
# 270° CW = 90° CCW, which is the correct setting for a Canon EOS M50
# connected in webcam mode (sensor outputs landscape, portrait needed).
_CV2_ROTATION = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


class OpenCVCamera(BaseCamera):
    def __init__(self, camera_id: int = 0, rotation: int = 0):
        self.camera_id = camera_id
        self.cap = None
        self.rotation = rotation  # degrees clockwise (0, 90, 180, 270)

    def _rotate(self, frame):
        """Rotate *frame* by the configured amount; no-op if rotation is 0."""
        code = _CV2_ROTATION.get(self.rotation)
        if code is not None:
            return cv2.rotate(frame, code)
        return frame

    def start_liveview(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.camera_id, _CAPTURE_BACKEND)
        if not self.cap.isOpened():
            raise CameraError(f"Kamera {self.camera_id} kann nicht geoeffnet werden")

    def stop_liveview(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def _ensure_open(self):
        if self.cap is None:
            self.start_liveview()

    def capture(self, dest: Path) -> None:
        self._ensure_open()
        ret, frame = self.cap.read()
        if not ret:
            raise CameraError("Kein Bild von Kamera erhalten")
        frame = self._rotate(frame)
        cv2.imwrite(str(dest), frame)

    def capture_preview(self, dest: Path) -> None:
        self.capture(dest)

    def get_preview_qimage(self) -> QtGui.QImage:
        self._ensure_open()
        ret, frame = self.cap.read()
        if not ret:
            raise CameraError("Kein Bild von Kamera erhalten")
        frame = self._rotate(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        img = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        return img.copy()
