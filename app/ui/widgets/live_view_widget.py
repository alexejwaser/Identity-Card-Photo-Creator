# app/ui/widgets/live_view_widget.py
import logging
from pathlib import Path
from PySide6 import QtWidgets, QtGui, QtCore
from .overlay import Overlay

logger = logging.getLogger(__name__)

class LiveViewWidget(QtWidgets.QWidget):
    """Widget zur Anzeige des Live-Streams mit einblendbarem Overlay."""

    def __init__(self, camera, fps: int = 20, parent=None):
        super().__init__(parent)
        self.camera = camera
        self.crop_aspect: tuple[int, int] | None = None
        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("background-color: black;")
        self.label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.frame_ratio = 3 / 4
        self.overlay = Overlay()
        layout = QtWidgets.QStackedLayout(self)
        layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        layout.addWidget(self.label)
        layout.addWidget(self.overlay)
        # Sicherstellen, dass das Overlay ueber dem Bild liegt
        self.overlay.raise_()
        self.overlay.show()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(max(30, int(1000 / max(1, fps))))

    def _update_label_geometry(self):
        if self.frame_ratio <= 0:
            return
        w, h = self.width(), self.height()
        if w / h > self.frame_ratio:
            new_w = int(h * self.frame_ratio)
            new_h = h
        else:
            new_w = w
            new_h = int(w / self.frame_ratio)
        x = (w - new_w) // 2
        y = (h - new_h) // 2
        self.label.setGeometry(x, y, new_w, new_h)
        self.overlay.setGeometry(self.label.geometry())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_label_geometry()

    def sizeHint(self):
        if self.frame_ratio >= 1:
            return QtCore.QSize(480, int(480 / self.frame_ratio))
        else:
            return QtCore.QSize(int(640 * self.frame_ratio), 640)

    def set_camera(self, camera):
        self.camera = camera

    def set_overlay_image(self, path: str | Path | None):
        self.overlay.set_image(path)

    def set_crop_aspect(self, aspect: tuple[int, int] | None):
        """Crop every displayed frame to a centered *width:height* region,
        or show the full frame when *aspect* is ``None``. Shows the operator
        exactly what part of the live feed ends up in the final saved photo,
        instead of the full (often wider) sensor field of view."""
        self.crop_aspect = aspect if aspect and aspect[0] > 0 and aspect[1] > 0 else None

    def _crop_to_aspect(self, img: QtGui.QImage) -> QtGui.QImage:
        if not self.crop_aspect:
            return img
        w, h = img.width(), img.height()
        target_w = w
        target_h = int(w * self.crop_aspect[1] / self.crop_aspect[0])
        if target_h > h:
            target_h = h
            target_w = int(h * self.crop_aspect[0] / self.crop_aspect[1])
        x = (w - target_w) // 2
        y = (h - target_h) // 2
        return img.copy(x, y, target_w, target_h)

    def update_frame(self):
        if self.camera is None:
            return
        try:
            if hasattr(self.camera, 'get_preview_qimage'):
                img = self.camera.get_preview_qimage()
            else:
                from tempfile import NamedTemporaryFile
                with NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    path = Path(tmp.name)
                try:
                    self.camera.capture_preview(path)
                    img = QtGui.QImage(str(path))
                finally:
                    path.unlink(missing_ok=True)
            if not img.isNull():
                img = self._crop_to_aspect(img)
                self.frame_ratio = img.width() / img.height()
                self._update_label_geometry()
                pix = QtGui.QPixmap.fromImage(img).scaled(
                    self.label.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
                self.label.setPixmap(pix)
        except Exception as e:
            # Some virtual webcam drivers (e.g. Canon EOS Webcam Utility)
            # take a while to start delivering real frames after launch, so
            # a friendly "still loading" message reads better than a raw
            # exception during that window; the actual error still goes to
            # the log for diagnostics.
            logger.debug('Live-Vorschau: kein Bild erhalten: %s', e)
            self.label.setText('Kamera wird geladen, bitte warten …')
