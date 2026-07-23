# app/ui/widgets/live_view_widget.py
from __future__ import annotations

import logging
from pathlib import Path
from PySide6 import QtWidgets, QtGui, QtCore, QtConcurrent
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
        self._inflight = False
        self._watcher: QtCore.QFutureWatcher | None = None
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

    @staticmethod
    def _fetch_frame(camera) -> QtGui.QImage:
        if hasattr(camera, 'get_preview_qimage'):
            return camera.get_preview_qimage()
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            path = Path(tmp.name)
        try:
            camera.capture_preview(path)
            return QtGui.QImage(str(path))
        finally:
            path.unlink(missing_ok=True)

    def update_frame(self):
        # Some camera drivers can block for seconds inside a single read
        # (observed with Canon EOS Webcam Utility during startup/reconnect
        # hiccups). Fetching frames on a worker thread keeps the rest of the
        # UI (buttons, dialogs, ...) responsive even when that happens; the
        # in-flight guard makes sure at most one read per camera is ever
        # outstanding, so a slow read just means the next tick is skipped
        # rather than reads piling up.
        if self.camera is None or self._inflight:
            return
        camera = self.camera
        self._inflight = True

        def task():
            return self._fetch_frame(camera)

        if hasattr(QtConcurrent, 'run'):
            future = QtConcurrent.run(task)
            watcher = QtCore.QFutureWatcher()
            watcher.setFuture(future)
            watcher.finished.connect(lambda: self._on_frame_ready(watcher, camera))
            self._watcher = watcher
        else:
            try:
                img = task()
            except Exception as e:
                self._inflight = False
                self._show_frame_error(e)
                return
            self._inflight = False
            if camera is self.camera:
                self._display_frame(img)

    def _on_frame_ready(self, watcher: QtCore.QFutureWatcher, camera):
        self._inflight = False
        try:
            img = watcher.result()
        except Exception as e:
            self._show_frame_error(e)
            return
        # The camera may have been swapped out (e.g. settings dialog closed,
        # reconnect) while this read was in flight; drop stale results.
        if camera is self.camera:
            self._display_frame(img)

    def _display_frame(self, img: QtGui.QImage):
        if img is None or img.isNull():
            return
        img = self._crop_to_aspect(img)
        self.frame_ratio = img.width() / img.height()
        self._update_label_geometry()
        pix = QtGui.QPixmap.fromImage(img).scaled(
            self.label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.label.setPixmap(pix)

    def _show_frame_error(self, e: Exception):
        # Some virtual webcam drivers (e.g. Canon EOS Webcam Utility) take a
        # while to start delivering real frames after launch, so a friendly
        # "still loading" message reads better than a raw exception during
        # that window; the actual error still goes to the log for diagnostics.
        logger.debug('Live-Vorschau: kein Bild erhalten: %s', e)
        self.label.setText('Kamera wird geladen, bitte warten …')
