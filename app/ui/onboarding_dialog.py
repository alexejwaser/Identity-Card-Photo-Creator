# app/ui/onboarding_dialog.py
from PySide6 import QtWidgets, QtCore

_STEPS_TEXT = (
    "<h3>Kurzanleitung</h3>"
    "<ol>"
    "<li><b>Excel laden</b> – Roster-Datei über 'Excel verbinden...' öffnen.</li>"
    "<li><b>Standort &amp; Klasse wählen</b> – die Liste der Lernenden erscheint automatisch.</li>"
    "<li><b>Foto aufnehmen</b> – Leertaste drücken, Ergebnis prüfen, dann OK oder erneut fotografieren.</li>"
    "<li><b>Überspringen / Neue Person</b> – falls jemand fehlt oder nicht auf der Liste steht.</li>"
    "<li><b>Fertig klicken</b> – sobald alle Lernenden fotografiert wurden, um die Klasse abzuschliessen.</li>"
    "</ol>"
)


class OnboardingDialog(QtWidgets.QDialog):
    """Simple one-time (or on-demand) quick-start guide for new operators."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Willkommen')
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(_STEPS_TEXT)
        label.setWordWrap(True)
        label.setTextFormat(QtCore.Qt.RichText)
        layout.addWidget(label)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
