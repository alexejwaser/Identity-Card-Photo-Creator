from PySide6 import QtWidgets, QtCore
import logging

class ClassSearchDialog(QtWidgets.QDialog):
    def __init__(self, classes, parent=None, logger: logging.Logger | None = None):
        super().__init__(parent)
        self.logger = logger or logging.getLogger(type(self).__name__)
        self.setWindowTitle('Klasse suchen')
        self.classes = list(classes)
        self._selected = None
        layout = QtWidgets.QVBoxLayout(self)
        self.edit = QtWidgets.QLineEdit()
        self.edit.setPlaceholderText('Klasse eingeben...')
        completer = QtWidgets.QCompleter(self.classes, self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.edit.setCompleter(completer)
        layout.addWidget(self.edit)
        self.lbl_error = QtWidgets.QLabel('')
        self.lbl_error.setStyleSheet('color:#d32f2f;')
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)

    def _try_accept(self):
        text = self.edit.text().strip()
        match = self._resolve(text)
        if match is None:
            self.lbl_error.setText(
                f'Keine eindeutige Klasse gefunden für "{text}". Bitte aus der Liste auswählen.'
            )
            self.lbl_error.setVisible(True)
            return
        self._selected = match
        self.accept()

    def _resolve(self, text: str):
        if not text:
            return None
        for c in self.classes:
            if c.lower() == text.lower():
                return c
        contains = [c for c in self.classes if text.lower() in c.lower()]
        if len(contains) == 1:
            return contains[0]
        return None

    def selected_class(self):
        return self._selected
