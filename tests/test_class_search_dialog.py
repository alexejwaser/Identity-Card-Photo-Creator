"""Die Aufloesung der Klassensuche - der einzige Ort, an dem getippter Text zu
einer Klasse wird.

Bisher ungetestet, und ausgerechnet hier faellt eine Regression nicht auf: der
Dialog nimmt jede Eingabe entgegen und liefert am Ende *irgendeine* Klasse. Ein
zu grosszuegiges Matching (etwa: erster Treffer statt eindeutiger Treffer)
schiebe die Fotografin stillschweigend in die falsche Klasse - die Fotos landen
im falschen Ordner, und niemand merkt es am selben Tag.

``exec()`` wird hier nie aufgerufen: ein modaler Dialog blockiert im Test fuer
immer. ``_try_accept`` ist der Slot hinter dem OK-Knopf und laesst sich direkt
anstossen; ``accept()`` auf einem nie gezeigten Dialog setzt nur das Ergebnis.
"""
import pytest

from app.ui.class_search_dialog import ClassSearchDialog


CLASSES = ["1a", "1b", "2a", "Informatik 3", "Elektro 3"]


@pytest.fixture
def dialog(qtbot):
    dlg = ClassSearchDialog(CLASSES)
    qtbot.addWidget(dlg)
    return dlg


# --- _resolve: Text -> Klasse ----------------------------------------------

def test_an_exact_match_wins_over_substring_matches(dialog):
    # "1a" steckt auch in keiner anderen Klasse, aber der exakte Vergleich
    # laeuft bewusst zuerst - sonst entschiede die Reihenfolge der Liste.
    assert dialog._resolve("1a") == "1a"


def test_matching_is_case_insensitive(dialog):
    assert dialog._resolve("informatik 3") == "Informatik 3"
    assert dialog._resolve("INFORMATIK 3") == "Informatik 3"


def test_a_single_substring_match_resolves(dialog):
    assert dialog._resolve("Elektro") == "Elektro 3"
    assert dialog._resolve("2") == "2a"


def test_an_ambiguous_substring_returns_none(dialog):
    # "1" steckt in 1a und 1b, " 3" in beiden Fachklassen: raten waere hier
    # schlimmer als nichts zu tun.
    assert dialog._resolve("1") is None
    assert dialog._resolve(" 3") is None


def test_empty_text_returns_none(dialog):
    assert dialog._resolve("") is None


# --- _try_accept: der OK-Knopf ---------------------------------------------

def test_try_accept_without_a_match_shows_the_error_and_selects_nothing(dialog):
    dialog.edit.setText("1")
    dialog._try_accept()

    assert dialog.selected_class() is None
    # isVisibleTo statt isVisible: der Dialog selbst wird nie gezeigt, damit
    # kein modales exec() den Test anhaelt - isVisible() waere deshalb immer
    # False, egal was setVisible() gesagt hat.
    assert dialog.lbl_error.isVisibleTo(dialog) is True
    assert "1" in dialog.lbl_error.text()
    assert dialog.result() != int(ClassSearchDialog.Accepted)


def test_try_accept_with_a_match_selects_and_accepts(dialog):
    dialog.edit.setText("  elektro  ")   # Leerraum wird abgeschnitten
    dialog._try_accept()

    assert dialog.selected_class() == "Elektro 3"
    assert dialog.result() == int(ClassSearchDialog.Accepted)
