from pathlib import Path
from PySide6 import QtWidgets, QtUiTools, QtCore


class ControlPanel(QtWidgets.QWidget):
    """Left side control panel loaded from a Qt Designer .ui file."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        ui_path = Path(__file__).with_suffix('.ui')
        if ui_path.exists():
            loader = QtUiTools.QUiLoader()
            ui_file = QtCore.QFile(str(ui_path))
            ui_file.open(QtCore.QFile.ReadOnly)
            loaded = loader.load(ui_file, self)
            ui_file.close()
            # Fill the column vertically so the internal spacer can push the
            # "Fertig" button to the bottom and leave room for the help/settings
            # row that MainWindow adds beneath this widget.
            loaded.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding
            )
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(loaded)
            self.btn_excel = loaded.findChild(QtWidgets.QPushButton, 'btn_excel')
            self.cmb_location = loaded.findChild(QtWidgets.QComboBox, 'cmb_location')
            self.cmb_class = loaded.findChild(QtWidgets.QComboBox, 'cmb_class')
            self.btn_search_class = loaded.findChild(QtWidgets.QToolButton, 'btn_search_class')
            self.btn_capture = loaded.findChild(QtWidgets.QPushButton, 'btn_capture')
            self.btn_skip = loaded.findChild(QtWidgets.QPushButton, 'btn_skip')
            self.btn_add_person = loaded.findChild(QtWidgets.QPushButton, 'btn_add_person')
            self.btn_finish = loaded.findChild(QtWidgets.QPushButton, 'btn_finish')
            self.btn_settings = loaded.findChild(QtWidgets.QPushButton, 'btn_settings')
            self.btn_jump_to = loaded.findChild(QtWidgets.QToolButton, 'btn_jump_to')
        else:
            # Fallback layout (shouldn't happen in normal usage)
            layout = QtWidgets.QVBoxLayout(self)
            self.btn_excel = QtWidgets.QPushButton('Excel verbinden...')
            self.cmb_location = QtWidgets.QComboBox()
            self.cmb_class = QtWidgets.QComboBox()
            self.btn_search_class = QtWidgets.QToolButton()
            self.btn_capture = QtWidgets.QPushButton('Foto aufnehmen')
            self.btn_skip = QtWidgets.QPushButton('Überspringen')
            self.btn_add_person = QtWidgets.QPushButton('Person hinzufügen')
            self.btn_finish = QtWidgets.QPushButton('Fertig')
            self.btn_settings = QtWidgets.QPushButton('')
            self.btn_jump_to = QtWidgets.QToolButton()
            self.btn_jump_to.setText('Zu spezifischer Person springen')
            self.btn_jump_to.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            for w in [
                self.btn_excel,
                self.cmb_location,
                self.cmb_class,
                self.btn_search_class,
                self.btn_capture,
                self.btn_skip,
                self.btn_add_person,
                self.btn_finish,
                self.btn_settings,
                self.btn_jump_to,
            ]:
                layout.addWidget(w)
            layout.addStretch()
