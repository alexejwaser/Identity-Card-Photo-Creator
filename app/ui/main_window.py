"""Main application window."""

from __future__ import annotations

from PySide6 import QtWidgets, QtGui, QtCore, QtConcurrent
from pathlib import Path
from datetime import datetime
import logging
import os
import psutil

from ..core.config.settings import Settings, CONFIG_DIR
from ..core.controller import MainController
from ..version import get_version
from ..core.excel.reader import ExcelReader, Learner
from ..core.excel.missed_writer import MissedWriter, MissedEntry
from ..core.imaging.processor import process_image
from .settings_dialog import SettingsDialog
from .class_search_dialog import ClassSearchDialog
from .onboarding_dialog import OnboardingDialog
from .icons import github_icon, icon, PADDED_ASPECT
from .widgets import ControlPanel


class MainWindow(QtWidgets.QMainWindow):
    """Main GUI window for the application."""

    _GITHUB_URL = 'https://github.com/alexejwaser/Identity-Card-Photo-Creator'

    def __init__(
        self,
        settings: Settings,
        controller: MainController | None = None,
        logger: logging.Logger | None = None,
    ):
        super().__init__()
        self.logger = logger or logging.getLogger(type(self).__name__)
        self.settings = settings
        self.controller = controller or MainController(settings)
        # Use the camera that the controller already created – no duplication.
        self.camera = self.controller.camera
        self._reader = None
        self.busy = False
        self._jump_return = None
        # Automatic camera recovery (see _auto_recover_camera): a re-entrancy
        # guard and a bounded retry budget so a genuinely absent camera does
        # not restart in an endless loop.
        self._camera_recovering = False
        self._auto_recover_attempts = 0
        self._setup_ui()
        if hasattr(self.camera, "start_liveview"):
            self.camera.start_liveview()
        self._update_camera_banner()
        self._maybe_show_onboarding()

    @property
    def reader(self):
        return self._reader

    @reader.setter
    def reader(self, value):
        self._reader = value
        if self.controller is not None:
            self.controller.reader = value

    def _setup_ui(self):
        self._version = get_version()
        self.setWindowTitle(f'LegicCard-Creator v{self._version}')
        self.setMinimumSize(900, 620)
        # Version in the bottom-left status bar, so the running build is always
        # identifiable at a glance (matches the version tagged on GitHub).
        version_label = QtWidgets.QLabel(f'v{self._version}')
        version_label.setStyleSheet('color: gray; font-size:11px;')
        self.statusBar().addWidget(version_label)
        # Author credit + a clickable GitHub mark that opens the project repo.
        author_label = QtWidgets.QLabel('erstellt von Alexej Waser')
        author_label.setStyleSheet('color: gray; font-size:11px;')
        self.statusBar().addWidget(author_label)
        self.btn_github = QtWidgets.QToolButton()
        self.btn_github.setIcon(github_icon())
        self.btn_github.setIconSize(QtCore.QSize(14, 14))
        self.btn_github.setAutoRaise(True)  # flat, blends into the status bar
        self.btn_github.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_github.setToolTip('GitHub-Repository öffnen')
        self.btn_github.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._GITHUB_URL))
        )
        self.statusBar().addWidget(self.btn_github)
        self.statusBar().setSizeGripEnabled(False)
        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        self.setCentralWidget(central)

        # left controls
        self.controls = ControlPanel(self)
        self.cmb_location = self.controls.cmb_location
        self.cmb_class = self.controls.cmb_class
        self.btn_search_class = self.controls.btn_search_class
        self.btn_excel = self.controls.btn_excel
        self.btn_capture = self.controls.btn_capture
        self.btn_skip = self.controls.btn_skip
        self.btn_add_person = self.controls.btn_add_person
        self.btn_finish = self.controls.btn_finish
        self.btn_settings = self.controls.btn_settings
        self.btn_jump_to = self.controls.btn_jump_to
        self.controls.setObjectName('controlPanel')  # scopes the left-align QSS
        self.cmb_location.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.cmb_class.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.cmb_class.setMaxVisibleItems(25)
        # No class is preselected when a roster loads; the operator picks one
        # actively. With currentIndex == -1 this placeholder shows and
        # currentText() returns '' (so the existing "no class" guards hold).
        self.cmb_class.setPlaceholderText('Wähle die Klasse')
        # Consistent lucide.dev iconography on the major buttons. Text buttons
        # get a wider (padded) icon so the label sits clear of the glyph, and are
        # left-aligned via the #controlPanel stylesheet below; icon-only buttons
        # (search, settings) use a square icon and keep their tooltips.
        h = 16
        padded_size = QtCore.QSize(round(h * PADDED_ASPECT), h)
        square_size = QtCore.QSize(h, h)
        for btn, name in (
            (self.btn_excel, 'file-spreadsheet'),
            (self.btn_capture, 'camera'),
            (self.btn_skip, 'skip-forward'),
            (self.btn_add_person, 'user-plus'),
            (self.btn_finish, 'check'),
        ):
            btn.setIcon(icon(name))
            btn.setIconSize(padded_size)
        self.btn_search_class.setIcon(icon('search'))
        self.btn_search_class.setIconSize(square_size)
        self.btn_search_class.setToolTip('Klasse suchen')
        self.btn_settings.setIcon(icon('settings'))
        self.btn_settings.setIconSize(square_size)
        self.btn_settings.setToolTip('Einstellungen')
        # QToolButton carries a label, so show the icon beside the text and let
        # it stretch to the group width like the neighbouring push buttons.
        self.btn_jump_to.setIcon(icon('users'))
        self.btn_jump_to.setIconSize(padded_size)
        self.btn_jump_to.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_jump_to.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )

        # Help + settings share a compact row at the bottom of the left column.
        # The settings button is detached from the control stack and moved here,
        # to the right of the help button.
        self.btn_help = QtWidgets.QPushButton('?')
        self.btn_help.setObjectName('btn_help')
        self.btn_help.setFixedWidth(32)
        self.btn_help.setToolTip('Kurzanleitung anzeigen')
        self.btn_help.clicked.connect(self.show_onboarding)
        self.btn_settings.setParent(None)
        self.btn_settings.setFixedWidth(40)
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.addWidget(self.btn_help)
        bottom_row.addWidget(self.btn_settings)
        bottom_row.addStretch()
        self.controls.layout().addLayout(bottom_row)

        # Tooltips for keyboard shortcuts (cleaner than baking them into labels)
        self.btn_capture.setToolTip('Leertaste')
        self.btn_skip.setToolTip('S')
        self.btn_add_person.setToolTip('A')
        self.btn_finish.setToolTip('F')

        # Keep the control column a tidy fixed-width sidebar; the preview takes
        # the remaining space.
        self.controls.setMaximumWidth(320)
        self.controls.setMinimumWidth(260)
        layout.addWidget(self.controls)

        # right preview
        from .widgets.live_view_widget import LiveViewWidget
        fps = self.settings.kamera.liveviewFpsZiel
        self.preview = LiveViewWidget(self.camera, fps)
        self.preview.recovery_requested.connect(self._auto_recover_camera)
        self.preview.recovered.connect(self._on_camera_recovered)
        self.preview.set_overlay_image(self.settings.overlay.image)
        self.preview.set_crop_aspect((self.settings.bild.breite, self.settings.bild.hoehe))
        preview_layout = QtWidgets.QVBoxLayout()
        preview_layout.setSpacing(8)

        # Persistent warning shown whenever the real camera failed to open and
        # the app silently fell back to the simulator (placeholder images).
        self.label_camera_banner = QtWidgets.QLabel('')
        self.label_camera_banner.setWordWrap(True)
        self.label_camera_banner.setStyleSheet(
            'background:#d32f2f; color:white; padding:6px; border-radius:4px; font-weight:bold;'
        )
        self.label_camera_banner.setVisible(False)
        preview_layout.addWidget(self.label_camera_banner)

        # Current / next learner labels
        name_layout = QtWidgets.QHBoxLayout()
        self.label_current = QtWidgets.QLabel('')
        self.label_current.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.label_current.setStyleSheet('font-size:16px;')
        self.label_upcoming = QtWidgets.QLabel('')
        self.label_upcoming.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.label_upcoming.setStyleSheet('font-size:12px; color: gray;')
        name_layout.addWidget(self.label_current)
        name_layout.addStretch()
        name_layout.addWidget(self.label_upcoming)
        preview_layout.addLayout(name_layout)

        # Shown only while the operator has jumped ahead to a specific
        # person out of order, so it's obvious the queue will snap back.
        self.label_jump_status = QtWidgets.QLabel('')
        self.label_jump_status.setStyleSheet('color:#0078d4; font-size:12px;')
        self.label_jump_status.setVisible(False)
        preview_layout.addWidget(self.label_jump_status)

        # Progress bar showing photographed / total for the current class
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #aaa; border-radius: 3px; }"
            "QProgressBar::chunk { background: #0078d4; border-radius: 2px; }"
        )
        preview_layout.addWidget(self.progress_bar)

        preview_layout.addWidget(self.preview)

        # Always-visible shortcut legend so a new operator never has to
        # discover keyboard shortcuts via hover tooltips.
        self.label_shortcuts = QtWidgets.QLabel(
            '[Leertaste] Foto aufnehmen    [S] Überspringen    '
            '[A] Neue Person    [F] Fertig'
        )
        self.label_shortcuts.setStyleSheet('color: gray; font-size:11px;')
        self.label_shortcuts.setAlignment(QtCore.Qt.AlignCenter)
        preview_layout.addWidget(self.label_shortcuts)

        layout.addLayout(preview_layout, stretch=1)

        self.setStyleSheet(
            "* {font-family: 'Segoe UI';}"
            " QPushButton {padding:6px 12px;}"
            # Left-align the main action buttons (group buttons + Fertig) so the
            # icon sits at the left edge and the label reads left-to-right. The
            # small help/settings buttons and dialog buttons are unaffected.
            " #controlPanel QGroupBox QPushButton,"
            " #controlPanel QGroupBox QToolButton,"
            " QPushButton#btn_finish {text-align:left; padding:7px 12px;}"
            # Keep the compact icon buttons small (they are icon-only / tiny).
            " QToolButton#btn_search_class, QPushButton#btn_help,"
            " QPushButton#btn_settings {text-align:center; padding:4px;}"
            # Group the sidebar controls into labelled category cards.
            " QGroupBox {border:1px solid #45474d; border-radius:6px;"
            " margin-top:12px; padding:8px 8px 4px 8px; font-weight:600;}"
            " QGroupBox::title {subcontrol-origin:margin; left:10px;"
            " padding:0 4px; color:#9aa0a6;}"
            " QLabel{font-size:14px;}"
        )

        self.btn_excel.clicked.connect(self.load_excel)
        self.cmb_location.currentTextChanged.connect(self.update_classes)
        self.cmb_class.currentTextChanged.connect(self.load_learners)
        self.btn_capture.clicked.connect(self.capture_photo)
        self.btn_skip.clicked.connect(self.skip_learner)
        self.btn_add_person.clicked.connect(self.add_person)
        self.btn_finish.clicked.connect(self.finish_class)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_search_class.clicked.connect(self.search_class)
        self.btn_jump_to.setEnabled(False)

        self._update_buttons()

        # Keyboard shortcuts
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Space), self, self.capture_photo)
        QtGui.QShortcut(QtGui.QKeySequence('S'), self, self.skip_learner)
        QtGui.QShortcut(QtGui.QKeySequence('F'), self, self.finish_class)
        QtGui.QShortcut(QtGui.QKeySequence('A'), self, self.add_person)

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

    def load_excel(self):
        # Start the dialog in the folder of the last opened Excel file (remembered
        # across restarts) instead of the app's install/working directory.
        start_dir = self.settings.lastExcelDir if os.path.isdir(self.settings.lastExcelDir) else ''
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Excel auswählen', start_dir, filter='Excel (*.xlsx)'
        )
        if not path:
            return
        # Confirm before opening, so an accidental pick in the file dialog does
        # not silently swap the active roster.
        reply = QtWidgets.QMessageBox.question(
            self,
            'Datei öffnen',
            f'Bist du sicher dass du diese Datei öffnen willst:\n{Path(path).name}',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        if self._load_excel_from_path(Path(path)):
            # Remember the folder for next time (persist so it survives restarts).
            self.settings.lastExcelDir = str(Path(path).resolve().parent)
            try:
                self.settings.save()
            except Exception as e:
                self.logger.warning('Konnte lastExcelDir nicht speichern: %s', e)

    def _load_excel_from_path(self, path: Path) -> bool:
        """Point self.reader at *path* and populate the location dropdown.
        Returns True on success. Shared by the file-picker flow (load_excel) and
        the test-mode flow (_activate_test_mode)."""
        try:
            self.reader = ExcelReader(path, self.settings.excelMapping.model_dump())
            locations = self.reader.locations()
        except Exception as e:
            self._notify('Excel', str(e), level='error')
            return False
        self.controls.cmb_location.clear()
        self.controls.cmb_location.addItems(locations)
        self._update_buttons()
        return True

    def _activate_test_mode(self):
        """Generate a fresh randomized placeholder roster, load it as the active
        roster, and redirect photo/zip output to a dedicated Testdaten folder
        for the rest of the session (session-only, not saved to settings.json)."""
        from ..core.excel.test_data import generate_test_roster
        test_dir = CONFIG_DIR / 'Testdaten'
        roster_path = test_dir / 'Testroster.xlsx'
        generate_test_roster(roster_path, self.settings.excelMapping.model_dump())
        # Session-only redirect (not persisted) so test captures can never land
        # in or overwrite the real output folder.
        self.settings.ausgabeBasisPfad = test_dir / 'Ausgabe'
        self.settings.neueLernendeBasisPfad = test_dir / 'Neue Lernende'
        self._load_excel_from_path(roster_path)
        self._notify(
            'Testmodus',
            f'Testdaten geladen: {roster_path}\n'
            f'Fotos werden für diese Sitzung in {self.settings.ausgabeBasisPfad} gespeichert.\n'
            'Lade eine echte Excel-Datei oder starte die App neu, um zu echten Daten zurückzukehren.',
            level='info',
        )

    def update_classes(self, location: str):
        classes = self.controller.classes_for_location(location)
        combo = self.controls.cmb_class
        # Populate without auto-selecting the first class: block signals so
        # addItems() doesn't fire load_learners for item 0, then clear the
        # selection so the "Wähle die Klasse" placeholder shows instead.
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(classes)
        combo.setCurrentIndex(-1)
        combo.blockSignals(False)
        self._update_buttons()

    def search_class(self):
        classes = getattr(self.controller, "current_classes", [])
        if not classes:
            self._notify("Klassen", "Keine Klassen geladen", level="warning", show=True)
            return
        dlg = ClassSearchDialog(
            classes, self, logger=self.logger.getChild("ClassSearchDialog")
        )
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            selected = dlg.selected_class()
            if selected:
                idx = self.controls.cmb_class.findText(selected, QtCore.Qt.MatchExactly)
                if idx >= 0:
                    self.controls.cmb_class.setCurrentIndex(idx)

    def load_learners(self, class_name: str):
        location = self.controls.cmb_location.currentText()
        if not self.reader or not class_name:
            self._update_buttons()
            return

        # Check how many students are already photographed and offer to skip them.
        all_learners = self.reader.learners(location, class_name)
        already_done = sum(1 for l in all_learners if l.photographed)

        skip_photographed = False
        if already_done > 0:
            box = QtWidgets.QMessageBox(self)
            box.setWindowTitle('Bereits fotografiert')
            box.setText(
                f'{already_done} von {len(all_learners)} Lernenden wurden bereits fotografiert.\n'
                'Sollen diese übersprungen werden?'
            )
            skip_btn = box.addButton('Ja, überspringen', QtWidgets.QMessageBox.YesRole)
            box.addButton('Nein, alle anzeigen', QtWidgets.QMessageBox.NoRole)
            box.exec()
            skip_photographed = (box.clickedButton() is skip_btn)

        self.controller.learners_for_class(location, class_name, skip_photographed=skip_photographed)

        # Warn about duplicate student IDs – they would cause silent file collisions.
        dupes = self.reader.duplicate_ids(location, class_name)
        if dupes:
            self._notify(
                'Doppelte SchülerIDs',
                f'Achtung: Diese IDs kommen mehrfach vor: {", ".join(dupes)}\n'
                'Bitte die Excel-Datei prüfen.',
                level='warning',
            )

        self.show_next()
        self._update_buttons()

    def show_next(self):
        learner = self.controller.current_learner()
        total = len(self.controller.learners)
        done = self.controller.current

        if learner is None:
            self.label_current.setText('Klasse abgeschlossen')
            self.label_current.setStyleSheet('font-size:16px; color: green;')
            self.label_upcoming.setText('')
            if total > 0:
                self.progress_bar.setVisible(True)
                self.progress_bar.setMaximum(total)
                self.progress_bar.setValue(total)
                self.progress_bar.setFormat(f'{total}/{total}')
            self._populate_jump_menu()
            self._update_buttons()
            return

        name_text = f"{learner.vorname} {learner.nachname} ({done + 1}/{total})"
        self.label_current.setText(name_text)

        if learner.is_new:
            # Visual distinction: blue label + tooltip explaining the save location.
            self.label_current.setStyleSheet('font-size:16px; color: #0078d4;')
            self.label_current.setToolTip(
                f'Neue Person – wird gespeichert in: {self.settings.neueLernendeBasisPfad}'
            )
        else:
            self.label_current.setStyleSheet('font-size:16px;')
            self.label_current.setToolTip('')

        next_l = self.controller.next_learner()
        if next_l:
            self.label_upcoming.setText(f"{next_l.vorname} {next_l.nachname}")
        else:
            self.label_upcoming.setText('')

        # Update progress bar
        self.progress_bar.setVisible(total > 0)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        self.progress_bar.setFormat(f'{done}/{total}')

        self._populate_jump_menu()
        self._update_buttons()

    def _populate_jump_menu(self):
        menu = self.btn_jump_to.menu()
        if menu is None:
            menu = QtWidgets.QMenu(self.btn_jump_to)
            self.btn_jump_to.setMenu(menu)
        menu.clear()
        # Only one jump can be active at a time (self._jump_return holds a
        # single return position, not a stack) - block further jumps until
        # the operator has finished with the person they jumped to.
        if self._jump_return is None:
            for idx, learner in enumerate(self.controller.learners[self.controller.current:], start=self.controller.current):
                action = menu.addAction(f"{learner.vorname} {learner.nachname}")
                action.triggered.connect(lambda _, i=idx: self.jump_to(i))
        self.btn_jump_to.setEnabled(
            bool(menu.actions()) and not getattr(self, 'busy', False) and self._jump_return is None
        )

    def jump_to(self, index: int):
        if self._jump_return is not None or index <= self.controller.current or index >= len(self.controller.learners):
            return
        # Remember current position so we can resume after processing the
        # selected learner.
        return_learner = self.controller.learners[self.controller.current]
        self._jump_return = self.controller.current
        self.controller.current = index
        self.label_jump_status.setText(
            f'↩ Zurück zu {return_learner.vorname} {return_learner.nachname} nach dieser Aufnahme'
        )
        self.label_jump_status.setVisible(True)
        self.show_next()

    def show_onboarding(self):
        OnboardingDialog(self).exec()

    def _maybe_show_onboarding(self):
        marker = CONFIG_DIR / '.onboarded'
        if marker.exists():
            return
        self.show_onboarding()
        try:
            marker.touch()
        except OSError:
            pass

    def _update_camera_banner(self):
        """Show a persistent warning if a real camera failed to open and the
        app is running on the simulator (placeholder photos) as a fallback."""
        fallback = getattr(self.controller, 'camera_fallback', False)
        if fallback:
            reason = getattr(self.controller, 'camera_fallback_reason', '')
            self.label_camera_banner.setText(
                '⚠ Keine Kamera erkannt — es werden Platzhalterbilder gespeichert!'
                + (f' ({reason})' if reason else '')
            )
        self.label_camera_banner.setVisible(fallback)

    # Stop auto-recovering after this many consecutive attempts without frames,
    # so a genuinely missing camera does not restart forever.
    _MAX_AUTO_RECOVER_ATTEMPTS = 6

    def _auto_recover_camera(self):
        """Restart the camera when the live preview has been stuck on
        "Kamera wird geladen …" for a few seconds.

        This happens when the camera device is still held by a just-closed
        instance of the app (a quick close+reopen, or a second instance running
        at once): the stream never starts. Restarting the camera — exactly what
        closing the settings dialog does — reliably unblocks it once the device
        is free again. Retries are bounded so a genuinely absent camera does not
        loop forever; the budget is reset once frames resume
        (``_on_camera_recovered``)."""
        if self._camera_recovering:
            return
        if getattr(self.settings.kamera, 'backend', 'opencv') == 'simulator':
            return  # simulator always delivers frames; nothing to recover
        if self._auto_recover_attempts >= self._MAX_AUTO_RECOVER_ATTEMPTS:
            return
        self._camera_recovering = True
        self._auto_recover_attempts += 1
        self.logger.info(
            'Kamera-Vorschau haengt — automatischer Neustart der Kamera '
            '(Versuch %s/%s)',
            self._auto_recover_attempts,
            self._MAX_AUTO_RECOVER_ATTEMPTS,
        )
        # Pause the preview reads while the camera is torn down and rebuilt, the
        # same way the settings dialog does around a restart.
        self.preview.timer.stop()
        try:
            self.camera = self.controller.restart_camera()
        except Exception as e:
            self.logger.warning('Automatischer Kamera-Neustart fehlgeschlagen: %s', e)
            self.camera = self.controller.camera
        self.preview.set_camera(self.camera)
        self._update_camera_banner()
        self.preview.timer.start()
        self._camera_recovering = False

    def _on_camera_recovered(self):
        """Frames are flowing again — reset the retry budget so a future stall
        gets the full set of automatic attempts."""
        self._auto_recover_attempts = 0

    def _excel_running(self) -> bool:
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name'] or ''
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if 'excel' in name.lower():
                return True
        return False

    def _set_busy(self, busy: bool):
        self.busy = busy
        for btn in [self.btn_excel, self.btn_settings]:
            btn.setEnabled(not busy)
        self._update_buttons()

    def capture_photo(self):
        if self.controller.current >= len(self.controller.learners):
            return
        if self.controller.excel_running():
            self._notify(
                'Excel geöffnet',
                'Schliesse Excel um die App zu benutzen!',
                level='warning',
            )
            return
        self._set_busy(True)
        learner = self.controller.learners[self.controller.current]
        location = self.cmb_location.currentText()

        # Pause the live-preview reads while the background task grabs the
        # actual capture frame: the same cv2.VideoCapture handle isn't safe
        # to read from two threads at once, and contention here was a source
        # of UI stutter during capture.
        self.preview.timer.stop()

        def task():
            return self.controller.capture(learner, location)

        if hasattr(QtConcurrent, 'run'):
            future = QtConcurrent.run(task)
            watcher = QtCore.QFutureWatcher()
            watcher.setFuture(future)
            watcher.finished.connect(
                lambda: self._capture_finished(watcher, learner, location, None)
            )
            self._capture_watcher = watcher
        else:
            raw_path = task()
            self._capture_finished(None, learner, location, raw_path)

    def _capture_finished(self, watcher: QtCore.QFutureWatcher | None, learner: Learner, location: str, raw_path: Path | None):
        # The capture task (which reads from the camera) has finished by the
        # time this runs (either synchronously above, or via watcher.result()
        # below), so it's safe to resume the live preview now.
        self.preview.timer.start()
        try:
            if watcher is not None:
                raw_path = watcher.result()
        except Exception as e:
            self._notify('Aufnahme fehlgeschlagen', str(e), level='error')
            if raw_path is not None:
                raw_path.unlink(missing_ok=True)
            self._set_busy(False)
            return
        if raw_path is None:
            self._set_busy(False)
            return
        if self._show_review(raw_path):
            if not learner.is_new:
                date_str = datetime.now().strftime('%d.%m.%Y')

                def excel_task():
                    self.reader.mark_photographed(location, learner.row, True, date_str)

                if hasattr(QtConcurrent, 'run'):
                    future = QtConcurrent.run(excel_task)
                    watcher2 = QtCore.QFutureWatcher()
                    watcher2.setFuture(future)
                    watcher2.finished.connect(lambda: self._mark_finished(watcher2))
                    self._excel_watcher = watcher2
                else:
                    excel_task()
                    self._mark_finished(None)
            else:
                self._after_learner_done()
        else:
            raw_path.unlink(missing_ok=True)
            self.show_next()
            self._set_busy(False)

    def _mark_finished(self, watcher: QtCore.QFutureWatcher | None):
        try:
            if watcher is not None:
                watcher.result()
        except Exception as e:
            self._notify('Excel', str(e), level='warning')
        self._after_learner_done()

    def _after_learner_done(self):
        if getattr(self, '_jump_return', None) is not None:
            del self.controller.learners[self.controller.current]
            self.controller.current = self._jump_return
            self._jump_return = None
            self.label_jump_status.setVisible(False)
        else:
            self.controller.advance()
        self.show_next()
        self._set_busy(False)

    def _ask_skip_reason(self) -> tuple[str, bool]:
        """Single-step reason picker: a combo box plus a free-text field that
        only matters when 'Anderer Grund...' is selected. Replaces the old
        two-sequential-dialogs flow, which lost the whole skip if the
        operator accidentally cancelled the second dialog."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Grund')
        form = QtWidgets.QFormLayout(dlg)
        combo = QtWidgets.QComboBox()
        combo.addItems(['Krank', 'Verweigert', 'Anderer Grund...'])
        form.addRow('Grund für das Überspringen', combo)
        other_edit = QtWidgets.QLineEdit()
        other_edit.setPlaceholderText('Grund eingeben...')
        other_edit.setEnabled(False)
        form.addRow(other_edit)

        def _on_change(text):
            other_edit.setEnabled(text == 'Anderer Grund...')

        combo.currentTextChanged.connect(_on_change)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return '', False
        reason = combo.currentText()
        if reason == 'Anderer Grund...':
            reason = other_edit.text().strip()
            if not reason:
                return '', False
        return reason, True

    def skip_learner(self):
        if self.controller.current >= len(self.controller.learners):
            return
        if self.controller.excel_running():
            self._notify(
                'Excel geöffnet',
                'Schliesse Excel um die App zu benutzen!',
                level='warning',
            )
            return
        reason, ok = self._ask_skip_reason()
        if not ok:
            return
        learner = self.controller.learners[self.controller.current]
        missed = MissedWriter(self.settings.missedPath)
        entry = MissedEntry(
            self.cmb_location.currentText(),
            learner.klasse,
            learner.nachname,
            learner.vorname,
            learner.schueler_id,
            datetime.now().isoformat(),
            reason,
        )
        self._set_busy(True)

        def task():
            errors = []
            try:
                missed.append(entry)
            except Exception as e:
                errors.append(str(e))
            if not learner.is_new:
                try:
                    self.reader.mark_photographed(
                        self.cmb_location.currentText(),
                        learner.row,
                        False,
                        reason=reason,
                    )
                except Exception as e:
                    errors.append(str(e))
            return errors

        if hasattr(QtConcurrent, 'run'):
            future = QtConcurrent.run(task)
            watcher = QtCore.QFutureWatcher()
            watcher.setFuture(future)
            watcher.finished.connect(lambda: self._skip_finished(watcher))
            self._skip_watcher = watcher
        else:
            errors = task()
            for err in errors:
                self._notify('Excel', err, level='warning')
            self._after_learner_done()

    def _skip_finished(self, watcher: QtCore.QFutureWatcher):
        errors = watcher.result()
        for err in errors:
            self._notify('Excel', err, level='warning')
        self._after_learner_done()

    def finish_class(self):
        remaining = len(self.controller.learners) - self.controller.current
        if remaining > 0:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Noch nicht fertig',
                f'{remaining} Lernende(r) wurden noch nicht fotografiert.\n'
                'Klasse trotzdem abschliessen?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
        location = self.controls.cmb_location.currentText()
        klasse = self.controls.cmb_class.currentText()
        zip_paths, out_dir = self.controller.finish(location, klasse)
        if zip_paths:
            text = f'ZIP-Archiv {zip_paths[0].name} wurde erstellt.'
        else:
            text = 'Klasse abgeschlossen'
        self.logger.info(text)

        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle('Klasse abgeschlossen')
        msg.setText(text)
        open_btn = None
        if zip_paths:
            open_btn = msg.addButton('Ordner öffnen', QtWidgets.QMessageBox.ActionRole)
        msg.addButton('OK', QtWidgets.QMessageBox.AcceptRole)
        msg.exec()
        if open_btn and msg.clickedButton() == open_btn:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(out_dir)))
        self._update_buttons()

    def add_person(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Neue Person')
        form = QtWidgets.QFormLayout(dlg)
        first = QtWidgets.QLineEdit()
        last = QtWidgets.QLineEdit()
        form.addRow('Vorname', first)
        form.addRow('Nachname', last)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            vor = first.text().strip()
            nach = last.text().strip()
            if vor and nach:
                self.controller.add_learner(self.controls.cmb_class.currentText(), vor, nach)
                self.show_next()
                self._update_buttons()

    def _show_review(self, path: Path) -> bool:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Aufnahme ansehen')
        vbox = QtWidgets.QVBoxLayout(dlg)
        lbl = QtWidgets.QLabel()
        pix = QtGui.QPixmap(str(path))
        lbl.setPixmap(pix.scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio))
        vbox.addWidget(lbl)
        h = QtWidgets.QHBoxLayout()
        retry = QtWidgets.QPushButton('Erneut fotografieren  [Esc]')
        ok_btn = QtWidgets.QPushButton('OK  [Leertaste / Enter]')
        # Enter previously discarded the photo because the "Erneut fotografieren"
        # button held focus and got triggered. Disable autoDefault on both so no
        # button auto-fires on Enter; the explicit shortcuts below decide, making
        # Enter keep the photo just like the spacebar.
        for b in (retry, ok_btn):
            b.setAutoDefault(False)
            b.setDefault(False)
        retry.setToolTip('Foto verwerfen und neu aufnehmen (Esc)')
        ok_btn.setToolTip('Foto behalten (Leertaste oder Enter)')
        h.addWidget(retry)
        h.addWidget(ok_btn)
        vbox.addLayout(h)
        result = {'ok': True}
        retry.clicked.connect(lambda: (result.update(ok=False), dlg.accept()))
        ok_btn.clicked.connect(dlg.accept)
        for key in (QtCore.Qt.Key_Space, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            QtGui.QShortcut(QtGui.QKeySequence(key), dlg, ok_btn.click)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), dlg, retry.click)
        dlg.exec()
        return result['ok']

    def closeEvent(self, event):
        self.controller.camera.stop_liveview()
        super().closeEvent(event)

    def open_settings(self):
        # Only one process/handle can hold a webcam at a time, so pause the
        # main live view before the Settings dialog (which opens its own
        # preview camera) and resume/restart it afterwards.
        self.preview.timer.stop()
        if hasattr(self.controller.camera, 'stop_liveview'):
            self.controller.camera.stop_liveview()
        dlg = SettingsDialog(
            self.settings, self, logger=self.logger.getChild('SettingsDialog'), reader=self.reader
        )
        before_backend = self.settings.kamera.backend
        before_rotation = self.settings.kamera.rotation
        before_device = self.settings.kamera.deviceIndex
        before_breite = self.settings.bild.breite
        before_hoehe = self.settings.bild.hoehe
        before_overlay = self.settings.overlay.image
        accepted = dlg.exec() == QtWidgets.QDialog.Accepted
        # Checked regardless of accept/reject: the dialog's "Als Standard
        # speichern" button can persist camera settings mid-dialog, so
        # self.settings may already reflect a change even if the operator
        # ultimately cancels out of the rest of the form.
        changed = (
            self.settings.kamera.backend != before_backend
            or self.settings.kamera.rotation != before_rotation
            or self.settings.kamera.deviceIndex != before_device
            or getattr(dlg, 'reconnect_requested', False)
        )
        if changed:
            # Delegate full camera restart to the controller so there is
            # a single source of truth for camera initialisation.
            try:
                self.camera = self.controller.restart_camera()
            except Exception as e:
                self._notify('Kamera', str(e), level='warning')
                self.camera = self.controller.camera
            self.preview.set_camera(self.camera)
            self._update_camera_banner()
        elif hasattr(self.controller.camera, 'start_liveview'):
            self.controller.camera.start_liveview()
        if self.settings.bild.breite != before_breite or self.settings.bild.hoehe != before_hoehe:
            self.preview.set_crop_aspect((self.settings.bild.breite, self.settings.bild.hoehe))
        if accepted and self.settings.overlay.image != before_overlay:
            self.preview.set_overlay_image(self.settings.overlay.image)
        self.preview.timer.start()
        self._update_buttons()
        if accepted and getattr(dlg, '_test_mode_requested', False):
            self._activate_test_mode()

    def _update_buttons(self):
        ready = bool(self.reader) and bool(self.cmb_class.currentText())
        more = ready and self.controller.current < len(self.controller.learners)
        busy = getattr(self, 'busy', False)
        self.btn_capture.setEnabled(more and not busy)
        self.btn_skip.setEnabled(more and not busy)
        self.btn_add_person.setEnabled(ready and not busy)
        self.btn_finish.setEnabled(ready and not busy)
        self.btn_search_class.setEnabled(
            bool(getattr(self.controller, 'current_classes', [])) and not busy
        )
        self.btn_jump_to.setEnabled(more and not busy and bool(self.btn_jump_to.menu() and self.btn_jump_to.menu().actions()))
