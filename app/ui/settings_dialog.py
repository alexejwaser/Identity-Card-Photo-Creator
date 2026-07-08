# app/ui/settings_dialog.py
from PySide6 import QtWidgets
from pathlib import Path
from pydantic import ValidationError
import logging
from ..core.config.settings import Settings, ExcelMapping


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

        form = QtWidgets.QFormLayout(self)

        # Camera backend
        self.cmb_camera = QtWidgets.QComboBox()
        self.cmb_camera.addItems(['Webcam (OpenCV)', 'GPhoto2 (DSLR)', 'Simulator'])
        backend = self.settings.kamera.backend
        mapping = {'opencv': 0, 'gphoto2': 1, 'simulator': 2}
        self.cmb_camera.setCurrentIndex(mapping.get(backend, 0))
        form.addRow('Kamera', self.cmb_camera)

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
        form.addRow('Kamera-Drehung', self.cmb_rotation)

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

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        form.addRow(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

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

    def choose_missed(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Datei wählen', self.missed_path, filter='Excel (*.xlsx)')
        if path:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            self.missed_path = path
            self.lbl_missed.setText(Path(path).as_posix())

    def accept(self):
        backend_idx = self.cmb_camera.currentIndex()
        backend = ['opencv', 'gphoto2', 'simulator'][backend_idx]
        self.settings.kamera.backend = backend
        self.settings.kamera.rotation = [0, 90, 180, 270][self.cmb_rotation.currentIndex()]

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
        self.settings.missedPath = Path(self.missed_path)
        try:
            self.settings.save()
        except ValidationError as e:
            self._notify('Einstellungen', str(e), level='error')
            return
        super().accept()
