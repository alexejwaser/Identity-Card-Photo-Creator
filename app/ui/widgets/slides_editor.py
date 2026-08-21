# app/ui/widgets/slides_editor.py
"""Editor für die Folien der Wartezimmer-Anzeige.

Vorher war das ein einzelnes ``QPlainTextEdit``, in dem **eine Zeile = eine
Folie** war. Damit liess sich genau das nicht ausdrücken, was auf der Anzeige
stehen soll: ein Übertitel mit einer Aufzählung darunter.

Deshalb ein eigenes Widget statt eines weiteren Textfelds mit ausgedachter
Syntax: eine Folie ist hier ein Objekt mit drei Feldern, und die Reihenfolge ist
eine Liste, die man verschiebt — nichts hängt mehr an Zeilenumbrüchen.

Bewusst frei von pydantic: der Zustand sind schlichte dicts mit den Schlüsseln
``titel`` / ``text`` / ``punkte``. Die Umwandlung nach ``HinweisFolie`` macht der
Einstellungsdialog, und das Widget lässt sich ohne Settings-Objekt testen.
"""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6 import QtCore, QtWidgets


def _blank_slide() -> Dict[str, Any]:
    return {'titel': '', 'text': '', 'punkte': []}


class SlidesEditor(QtWidgets.QWidget):
    """Liste der Folien links, die Felder der gewählten Folie rechts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Quelle der Wahrheit. Die Eingabefelder zeigen immer nur den Eintrag,
        # der gerade ausgewählt ist; geschrieben wird beim Auswahlwechsel.
        self._slides: List[Dict[str, Any]] = []
        self._current = -1
        # Sperrt das Zurückschreiben, während die Felder programmatisch befüllt
        # werden - sonst schriebe das textChanged der frisch geladenen Folie
        # sofort wieder in die alte.
        self._loading = False

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ---- linke Spalte: Reihenfolge ----------------------------------
        left = QtWidgets.QVBoxLayout()
        layout.addLayout(left, 2)
        self.list = QtWidgets.QListWidget()
        # Lange Titel kuerzen statt waagrecht scrollen: die Leiste frisst sonst
        # eine Zeile der ohnehin knappen Liste.
        self.list.setTextElideMode(QtCore.Qt.ElideRight)
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self._on_row_changed)
        left.addWidget(self.list)

        buttons = QtWidgets.QHBoxLayout()
        left.addLayout(buttons)
        self.btn_add = QtWidgets.QPushButton('+')
        self.btn_add.setToolTip('Folie hinzufügen')
        self.btn_remove = QtWidgets.QPushButton('−')
        self.btn_remove.setToolTip('Folie entfernen')
        self.btn_up = QtWidgets.QPushButton('↑')
        self.btn_up.setToolTip('Folie nach oben')
        self.btn_down = QtWidgets.QPushButton('↓')
        self.btn_down.setToolTip('Folie nach unten')
        for btn in (self.btn_add, self.btn_remove, self.btn_up, self.btn_down):
            btn.setFixedWidth(34)
            buttons.addWidget(btn)
        buttons.addStretch()
        self.btn_add.clicked.connect(self.add_slide)
        self.btn_remove.clicked.connect(self.remove_current)
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down.clicked.connect(lambda: self._move(1))

        # ---- rechte Spalte: Inhalt der gewählten Folie --------------------
        self.fields = QtWidgets.QWidget()
        layout.addWidget(self.fields, 3)
        form = QtWidgets.QFormLayout(self.fields)
        form.setContentsMargins(0, 0, 0, 0)
        self.txt_titel = QtWidgets.QLineEdit()
        self.txt_titel.setPlaceholderText('z.B. Foto-Regeln')
        self.txt_titel.textChanged.connect(self._flush)
        form.addRow('Titel', self.txt_titel)
        self.txt_text = QtWidgets.QPlainTextEdit()
        self.txt_text.setFixedHeight(52)
        self.txt_text.setPlaceholderText('Optionaler Einleitungssatz')
        self.txt_text.textChanged.connect(self._flush)
        form.addRow('Fliesstext', self.txt_text)
        self.txt_punkte = QtWidgets.QPlainTextEdit()
        self.txt_punkte.setFixedHeight(112)
        self.txt_punkte.setPlaceholderText('Ein Aufzählungspunkt pro Zeile')
        self.txt_punkte.textChanged.connect(self._flush)
        form.addRow('Punkte', self.txt_punkte)

        self._sync_enabled()

    # -- öffentliche API ---------------------------------------------------
    def set_slides(self, slides) -> None:
        """Übernimmt *slides* (Liste von dicts) und wählt die erste Folie."""
        self._slides = [
            {
                'titel': str(s.get('titel', '') or ''),
                'text': str(s.get('text', '') or ''),
                'punkte': [str(p) for p in (s.get('punkte') or [])],
            }
            for s in (slides or [])
        ]
        self._current = -1
        self._refill_list()
        if self._slides:
            self.list.setCurrentRow(0)
        else:
            self._sync_enabled()

    def slides(self) -> List[Dict[str, Any]]:
        """Die Folien in der angezeigten Reihenfolge, ohne die leeren.

        Eine Folie ohne Titel, Text und Punkte fällt weg: ein Klick auf "+" ohne
        Eingabe soll keine leere Folie in der Slideshow hinterlassen.
        """
        self._flush()
        result = []
        for slide in self._slides:
            titel = slide['titel'].strip()
            text = slide['text'].strip()
            punkte = [p.strip() for p in slide['punkte'] if p.strip()]
            if not titel and not text and not punkte:
                continue
            result.append({'titel': titel, 'text': text, 'punkte': punkte})
        return result

    def add_slide(self) -> None:
        self._flush()
        self._slides.append(_blank_slide())
        self._refill_list()
        self.list.setCurrentRow(len(self._slides) - 1)
        self.txt_titel.setFocus()

    def remove_current(self) -> None:
        row = self.list.currentRow()
        if not 0 <= row < len(self._slides):
            return
        # Erst die Auswahl auflösen, damit _on_row_changed nicht auf den gerade
        # entfernten Index zurückschreibt.
        self._current = -1
        del self._slides[row]
        self._refill_list()
        if self._slides:
            self.list.setCurrentRow(min(row, len(self._slides) - 1))
        else:
            self._load(-1)

    # -- intern ------------------------------------------------------------
    def _label(self, index: int) -> str:
        slide = self._slides[index]
        for candidate in (slide['titel'], slide['text']):
            first = candidate.strip().splitlines()[0].strip() if candidate.strip() else ''
            if first:
                return first
        for punkt in slide['punkte']:
            if punkt.strip():
                return punkt.strip()
        return f'Folie {index + 1}'

    def _refill_list(self) -> None:
        blocked = self.list.blockSignals(True)
        self.list.clear()
        for i in range(len(self._slides)):
            self.list.addItem(self._label(i))
        self.list.blockSignals(blocked)

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        target = row + delta
        if not (0 <= row < len(self._slides) and 0 <= target < len(self._slides)):
            return
        self._flush()
        self._slides[row], self._slides[target] = self._slides[target], self._slides[row]
        self._current = -1
        self._refill_list()
        self.list.setCurrentRow(target)

    def _on_row_changed(self, row: int) -> None:
        self._flush()
        self._load(row)

    def _flush(self) -> None:
        """Schreibt die Eingabefelder in die zuletzt geladene Folie zurück."""
        if self._loading or not 0 <= self._current < len(self._slides):
            return
        slide = self._slides[self._current]
        slide['titel'] = self.txt_titel.text()
        slide['text'] = self.txt_text.toPlainText()
        slide['punkte'] = [
            line.strip()
            for line in self.txt_punkte.toPlainText().splitlines()
            if line.strip()
        ]
        # Das Listenlabel folgt der Eingabe sofort - sonst stünde dort weiter
        # "Folie 3", während rechts längst ein Titel steht.
        item = self.list.item(self._current)
        if item is not None:
            item.setText(self._label(self._current))

    def _load(self, row: int) -> None:
        self._loading = True
        try:
            if 0 <= row < len(self._slides):
                slide = self._slides[row]
                self.txt_titel.setText(slide['titel'])
                self.txt_text.setPlainText(slide['text'])
                self.txt_punkte.setPlainText('\n'.join(slide['punkte']))
            else:
                self.txt_titel.clear()
                self.txt_text.clear()
                self.txt_punkte.clear()
        finally:
            self._loading = False
        self._current = row if 0 <= row < len(self._slides) else -1
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        has_selection = 0 <= self._current < len(self._slides)
        self.fields.setEnabled(has_selection)
        self.btn_remove.setEnabled(has_selection)
        self.btn_up.setEnabled(has_selection and self._current > 0)
        self.btn_down.setEnabled(
            has_selection and self._current < len(self._slides) - 1
        )
