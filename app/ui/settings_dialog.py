# app/ui/settings_dialog.py
from PySide6 import QtWidgets, QtGui, QtCore
from pathlib import Path
from pydantic import ValidationError
import logging
from ..core.config.settings import Settings, ExcelMapping, CONFIG_PATH
from ..core.camera import list_cameras, OpenCVCamera
from .widgets.live_view_widget import LiveViewWidget


class SettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        settings: Settings,
        parent=None,
        logger: logging.Logger | None = None,
        reader=None,
    ):
        super().__init__(parent)
        self.logger = logger or logging.getLogger(type(self).__name__)
        self.settings = settings
        self.setWindowTitle('Einstellungen')
        self._headers = {}
        if reader is not None:
            try:
                self._headers = reader.headers()
            except Exception as e:
                self._notify('Excel-Spalten', str(e), level='warning')

        self._preview_camera = None
        # index -> CameraDevice for the currently listed devices, so name/path
        # (the stable identifiers persisted and used to re-resolve the device
        # per backend) can be looked up from the combo's index selection.
        self._devices_by_index = {}

        outer = QtWidgets.QVBoxLayout(self)

        # ---- Camera settings group -----------------------------------
        cam_group = QtWidgets.QGroupBox('Kamera-Einstellungen')
        cam_form = QtWidgets.QFormLayout(cam_group)
        outer.addWidget(cam_group)

        # Camera backend
        self.cmb_camera = QtWidgets.QComboBox()
        self.cmb_camera.addItems(['Webcam (OpenCV)', 'GPhoto2 (DSLR)', 'Simulator'])
        backend = self.settings.kamera.backend
        mapping = {'opencv': 0, 'gphoto2': 1, 'simulator': 2}
        self.cmb_camera.setCurrentIndex(mapping.get(backend, 0))
        cam_form.addRow('Kamera', self.cmb_camera)

        # Webcam device selection
        self.cmb_device = QtWidgets.QComboBox()
        self.btn_refresh_devices = QtWidgets.QPushButton('Aktualisieren')
        h_device = QtWidgets.QHBoxLayout()
        h_device.addWidget(self.cmb_device, stretch=1)
        h_device.addWidget(self.btn_refresh_devices)
        cam_form.addRow('Webcam-Auswahl', h_device)
        self.btn_refresh_devices.clicked.connect(self._populate_devices)

        # Camera rotation (relevant for USB webcam mode)
        self.cmb_rotation = QtWidgets.QComboBox()
        self.cmb_rotation.addItems(['0° (keine Drehung)', '90° im Uhrzeigersinn', '180°', '270° (Canon EOS M50)'])
        _rotation_idx = {0: 0, 90: 1, 180: 2, 270: 3}
        self.cmb_rotation.setCurrentIndex(
            _rotation_idx.get(getattr(self.settings.kamera, 'rotation', 270), 3)
        )
        self.cmb_rotation.setToolTip(
            'Drehung des Kamerabildes im Uhrzeigersinn.\n'
            'Canon EOS M50 im Webcam-Modus → 270°'
        )
        cam_form.addRow('Kamera-Drehung', self.cmb_rotation)

        # Resolution / format
        self.spin_width = QtWidgets.QSpinBox()
        self.spin_width.setRange(100, 8000)
        self.spin_width.setValue(int(self.settings.bild.breite))
        self.spin_height = QtWidgets.QSpinBox()
        self.spin_height.setRange(100, 8000)
        self.spin_height.setValue(int(self.settings.bild.hoehe))
        h_res = QtWidgets.QHBoxLayout()
        h_res.addWidget(QtWidgets.QLabel('Breite'))
        h_res.addWidget(self.spin_width)
        h_res.addWidget(QtWidgets.QLabel('Höhe'))
        h_res.addWidget(self.spin_height)
        h_res.addStretch()
        cam_form.addRow('Auflösung & Format', h_res)

        # Live preview
        self.preview_widget = LiveViewWidget(None, fps=self.settings.kamera.liveviewFpsZiel)
        self.preview_widget.setFixedHeight(200)
        cam_form.addRow('Vorschau', self.preview_widget)

        # Manual override for when the live preview goes black (observed
        # with some virtual webcam drivers, e.g. Canon EOS Webcam Utility)
        # and the automatic recovery hasn't kicked in yet. Reopens this
        # dialog's own preview camera immediately for feedback; closing the
        # dialog afterwards (OK or Cancel) also forces the main window's
        # camera to fully reconnect, via reconnect_requested below.
        self.reconnect_requested = False
        self.btn_reconnect = QtWidgets.QPushButton('Kamera neu verbinden')
        self.btn_reconnect.setToolTip(
            'Kamera trennen und neu initialisieren (z.B. bei schwarzem Live-Bild)'
        )
        self.btn_reconnect.clicked.connect(self._reconnect_camera)
        cam_form.addRow('', self.btn_reconnect)

        # Persist camera/resolution settings immediately, without closing
        # the dialog, so an operator can confirm the preview looks right
        # first and the choice survives an app restart right away.
        self.btn_save_camera_defaults = QtWidgets.QPushButton('Als Standard speichern')
        self.btn_save_camera_defaults.setToolTip(
            'Speichert Kamera, Webcam-Auswahl, Drehung und Auflösung sofort,\n'
            'ohne den Dialog zu schließen.'
        )
        cam_form.addRow('', self.btn_save_camera_defaults)
        self.btn_save_camera_defaults.clicked.connect(self._save_camera_defaults)

        self.cmb_camera.currentIndexChanged.connect(self._restart_preview)
        # Rotation is applied in software on each frame, so it must NOT reopen
        # the device - reopening churns fragile virtual webcam drivers (e.g.
        # EOS Webcam Utility) and can wedge them into delivering black.
        self.cmb_rotation.currentIndexChanged.connect(self._apply_rotation)
        self.cmb_device.currentIndexChanged.connect(self._restart_preview)
        self.spin_width.valueChanged.connect(self._update_crop_guide)
        self.spin_height.valueChanged.connect(self._update_crop_guide)
        # finished() fires on accept, reject and close alike, so the preview
        # camera handle is always released regardless of how the dialog ends
        # (QDialog.accept/reject hide() rather than close(), so closeEvent
        # alone would not cover the OK/Cancel buttons).
        self.finished.connect(lambda _=0: self._stop_preview())
        self._populate_devices()
        self._update_crop_guide()

        # ---- Remaining settings (flat form) --------------------------
        form = QtWidgets.QFormLayout()
        outer.addLayout(form)

        # output directory
        self.output_dir = str(self.settings.ausgabeBasisPfad)
        self.lbl_output = QtWidgets.QLabel(self.output_dir)
        self.lbl_output.setWordWrap(True)
        self.btn_output = QtWidgets.QPushButton('Ordner wählen...')
        h_out = QtWidgets.QHBoxLayout()
        h_out.addWidget(self.lbl_output, stretch=1)
        h_out.addWidget(self.btn_output)
        form.addRow('Ausgabeordner', h_out)
        self.btn_output.clicked.connect(self.choose_output)

        # base folder for walk-in students not on the roster ("Neue Lernende")
        self.new_learner_dir = str(self.settings.neueLernendeBasisPfad)
        self.lbl_new_learner = QtWidgets.QLabel(self.new_learner_dir)
        self.lbl_new_learner.setWordWrap(True)
        self.btn_new_learner = QtWidgets.QPushButton('Ordner wählen...')
        h_new = QtWidgets.QHBoxLayout()
        h_new.addWidget(self.lbl_new_learner, stretch=1)
        h_new.addWidget(self.btn_new_learner)
        form.addRow('Ordner für neue Lernende', h_new)
        self.btn_new_learner.clicked.connect(self.choose_new_learner_dir)

        # settings.json location (read-only; see LEGICCARD_CONFIG_DIR / portable
        # "config" folder next to the .exe to relocate it)
        self.lbl_config_path = QtWidgets.QLabel(str(CONFIG_PATH))
        self.lbl_config_path.setWordWrap(True)
        self.lbl_config_path.setToolTip(
            'Um diesen Speicherort zu ändern: einen Ordner namens "config" neben\n'
            'die LegicCardCreator.exe legen (Portable-Modus), oder die\n'
            'Umgebungsvariable LEGICCARD_CONFIG_DIR setzen.'
        )
        btn_open_config = QtWidgets.QPushButton('Ordner öffnen')
        btn_open_config.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(CONFIG_PATH.parent)))
        )
        h_config = QtWidgets.QHBoxLayout()
        h_config.addWidget(self.lbl_config_path, stretch=1)
        h_config.addWidget(btn_open_config)
        form.addRow('Konfigurationsdatei', h_config)

        # missed file path
        self.missed_path = str(self.settings.missedPath)
        self.lbl_missed = QtWidgets.QLabel(Path(self.missed_path).as_posix())
        self.lbl_missed.setWordWrap(True)
        self.btn_missed = QtWidgets.QPushButton('Datei wählen...')
        h_miss = QtWidgets.QHBoxLayout()
        h_miss.addWidget(self.lbl_missed, stretch=1)
        h_miss.addWidget(self.btn_missed)
        form.addRow('Verpasste Termine', h_miss)
        self.btn_missed.clicked.connect(self.choose_missed)

        self.overlay_path = str(self.settings.overlay.image) if self.settings.overlay.image else ''
        self.lbl_overlay = QtWidgets.QLabel(Path(self.overlay_path).name if self.overlay_path else 'Kein Overlay')
        self.btn_overlay = QtWidgets.QPushButton('Overlay wählen...')
        h_overlay = QtWidgets.QHBoxLayout()
        h_overlay.addWidget(self.lbl_overlay, stretch=1)
        h_overlay.addWidget(self.btn_overlay)
        form.addRow('Overlay-Bild', h_overlay)
        self.btn_overlay.clicked.connect(self.choose_overlay)

        # Excel column mapping. If a workbook is currently loaded, offer a
        # friendly dropdown of its actual header names instead of requiring
        # the operator to know raw Excel column letters.
        emap = self.settings.excelMapping
        mapping_fields = [
            ('klasse', 'Spalte Klasse', emap.klasse),
            ('nachname', 'Spalte Nachname', emap.nachname),
            ('vorname', 'Spalte Vorname', emap.vorname),
            ('schuelerId', 'Spalte SchülerID', emap.schuelerId),
            ('fotografiert', 'Spalte Fotografiert', emap.fotografiert),
            ('aufnahmedatum', 'Spalte Aufnahmedatum', emap.aufnahmedatum),
            ('grund', 'Spalte Grund', emap.grund),
        ]
        self._mapping_widgets = {}
        # letter -> header text, for pre-selecting the combo to the current mapping
        letter_to_header = {v: k for k, v in self._headers.items()}
        for key, label, current_letter in mapping_fields:
            if self._headers:
                combo = QtWidgets.QComboBox()
                combo.addItems(list(self._headers.keys()))
                current_header = letter_to_header.get(current_letter)
                if current_header:
                    combo.setCurrentText(current_header)
                combo.setToolTip('Spalte aus der geladenen Excel-Datei auswählen')
                self._mapping_widgets[key] = combo
                form.addRow(label, combo)
            else:
                ed = QtWidgets.QLineEdit(current_letter)
                ed.setMaximumWidth(60)
                ed.setToolTip('Spaltenbuchstabe der Excel-Datei, z.B. "A", "B" … (keine Excel-Datei geladen)')
                self._mapping_widgets[key] = ed
                form.addRow(label, ed)

        # ---- Test mode group -----------------------------------------
        test_group = QtWidgets.QGroupBox('Testmodus')
        test_form = QtWidgets.QFormLayout(test_group)
        outer.addWidget(test_group)
        self._test_mode_requested = False
        self.btn_test_mode = QtWidgets.QPushButton('Testdaten generieren && laden')
        self.btn_test_mode.setToolTip(
            'Erstellt eine zufällige Test-Excel-Datei mit Platzhalter-Standorten, Klassen\n'
            'und Lernenden und lädt sie sofort. Fotos landen für diese Sitzung in einem\n'
            'separaten Testordner – echte Daten werden nicht verändert.'
        )
        self.btn_test_mode.clicked.connect(self._request_test_mode)
        test_form.addRow(self.btn_test_mode)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        form.addRow(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    # ------------------------------------------------------------------
    def _populate_devices(self):
        self.cmb_device.blockSignals(True)
        self.cmb_device.clear()
        try:
            devices = list_cameras()
        except Exception as e:
            self._notify('Kameras', str(e), level='warning', show=False)
            devices = []
        self._devices_by_index = {d.index: d for d in devices}
        for d in devices:
            self.cmb_device.addItem(d.name, d.index)
        # Prefer re-selecting the saved device by its stable path/name, so the
        # right entry is highlighted even if the index shifted between sessions;
        # fall back to the saved index.
        idx = self._find_saved_device_row(devices)
        self.cmb_device.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_device.blockSignals(False)
        self._restart_preview()

    def _find_saved_device_row(self, devices) -> int:
        saved_path = getattr(self.settings.kamera, 'devicePath', '') or ''
        saved_name = getattr(self.settings.kamera, 'deviceName', '') or ''
        if saved_path:
            for row, d in enumerate(devices):
                if d.path and d.path == saved_path:
                    return row
        if saved_name:
            for row, d in enumerate(devices):
                if d.name == saved_name:
                    return row
        return self.cmb_device.findData(getattr(self.settings.kamera, 'deviceIndex', 1))

    def _selected_device(self):
        data = self.cmb_device.currentData()
        return self._devices_by_index.get(data)

    def _reconnect_camera(self):
        self.reconnect_requested = True
        self._restart_preview()

    def _restart_preview(self):
        self._stop_preview()
        backend = ['opencv', 'gphoto2', 'simulator'][self.cmb_camera.currentIndex()]
        if backend != 'opencv' or self.cmb_device.currentData() is None:
            self.preview_widget.set_camera(None)
            return
        device = self._selected_device()
        try:
            cam = OpenCVCamera(
                self.cmb_device.currentData(),
                rotation=[0, 90, 180, 270][self.cmb_rotation.currentIndex()],
                device_name=device.name if device else None,
                device_path=device.path if device else None,
            )
            cam.start_liveview()
            self._preview_camera = cam
            self.preview_widget.set_camera(cam)
        except Exception:
            self.preview_widget.set_camera(None)

    def _apply_rotation(self):
        """Update the preview rotation in place without reopening the device."""
        if self._preview_camera is not None:
            self._preview_camera.rotation = [0, 90, 180, 270][self.cmb_rotation.currentIndex()]

    def _stop_preview(self):
        if self._preview_camera is not None:
            self.preview_widget.set_camera(None)
            try:
                self._preview_camera.stop_liveview()
            except Exception:
                pass
            self._preview_camera = None

    def closeEvent(self, event):
        self._stop_preview()
        super().closeEvent(event)

    def _update_crop_guide(self):
        self.preview_widget.set_crop_aspect(
            (self.spin_width.value(), self.spin_height.value())
        )

    def _write_camera_settings(self):
        backend_idx = self.cmb_camera.currentIndex()
        backend = ['opencv', 'gphoto2', 'simulator'][backend_idx]
        self.settings.kamera.backend = backend
        self.settings.kamera.rotation = [0, 90, 180, 270][self.cmb_rotation.currentIndex()]
        device_idx = self.cmb_device.currentData()
        self.settings.kamera.deviceIndex = device_idx if device_idx is not None else 1
        device = self._selected_device()
        self.settings.kamera.deviceName = device.name if device else ''
        self.settings.kamera.devicePath = (device.path or '') if device else ''
        self.settings.bild.breite = self.spin_width.value()
        self.settings.bild.hoehe = self.spin_height.value()

    def _save_camera_defaults(self):
        self._write_camera_settings()
        try:
            self.settings.save()
        except ValidationError as e:
            self._notify('Einstellungen', str(e), level='error')
            return
        self._notify(
            'Kamera-Einstellungen', 'Als Standard gespeichert.', level='info'
        )

    # ------------------------------------------------------------------
    def _notify(
        self,
        title: str,
        message: str,
        level: str = "info",
        show: bool = True,
    ) -> None:
        """Log *message* with *level* and optionally show a QMessageBox."""
        log_fn = getattr(self.logger, level, self.logger.info)
        log_fn(f"{title}: {message}")
        if not show:
            return
        mapping = {
            "error": QtWidgets.QMessageBox.critical,
            "warning": QtWidgets.QMessageBox.warning,
            "info": QtWidgets.QMessageBox.information,
        }
        msg_fn = mapping.get(level, QtWidgets.QMessageBox.information)
        msg_fn(self, title, message)

    def choose_overlay(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'PNG wählen', filter='PNG (*.png)')
        if path:
            self.overlay_path = path
            self.lbl_overlay.setText(Path(path).name)

    def choose_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Ordner wählen', self.output_dir)
        if path:
            self.output_dir = path
            self.lbl_output.setText(path)

    def choose_new_learner_dir(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Ordner wählen', self.new_learner_dir)
        if path:
            self.new_learner_dir = path
            self.lbl_new_learner.setText(path)

    def choose_missed(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Datei wählen', self.missed_path, filter='Excel (*.xlsx)')
        if path:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            self.missed_path = path
            self.lbl_missed.setText(Path(path).as_posix())

    def _request_test_mode(self):
        """Signal MainWindow to activate one-shot test mode, then close via the
        normal accept() path (persisting any other pending settings)."""
        self._test_mode_requested = True
        self.accept()

    def accept(self):
        self._write_camera_settings()

        def _column_letter(key: str, default: str) -> str:
            widget = self._mapping_widgets[key]
            if isinstance(widget, QtWidgets.QComboBox):
                header = widget.currentText()
                return self._headers.get(header, default).upper()
            return widget.text().upper() or default

        self.settings.excelMapping = ExcelMapping(
            klasse=_column_letter('klasse', 'A'),
            nachname=_column_letter('nachname', 'B'),
            vorname=_column_letter('vorname', 'C'),
            schuelerId=_column_letter('schuelerId', 'D'),
            fotografiert=_column_letter('fotografiert', 'E'),
            aufnahmedatum=_column_letter('aufnahmedatum', 'F'),
            grund=_column_letter('grund', 'G'),
        )
        self.settings.overlay.image = Path(self.overlay_path) if self.overlay_path else None
        self.settings.ausgabeBasisPfad = Path(self.output_dir)
        self.settings.neueLernendeBasisPfad = Path(self.new_learner_dir)
        self.settings.missedPath = Path(self.missed_path)
        try:
            self.settings.save()
        except ValidationError as e:
            self._notify('Einstellungen', str(e), level='error')
            return
        super().accept()
