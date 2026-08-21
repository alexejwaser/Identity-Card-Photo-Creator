"""Der Folien-Editor der Wartezimmer-Anzeige.

Der heikle Teil ist nicht das Layout, sondern das Zurueckschreiben: die
Eingabefelder zeigen immer nur *eine* Folie, der Zustand liegt daneben in einer
Liste. Wer die Auswahl wechselt, verschiebt oder loescht, kann leicht die
falsche Folie ueberschreiben - und das faellt in der GUI erst auf, wenn die
Hinweise draussen im Gang vertauscht haengen.
"""
import pytest

from app.ui.widgets.slides_editor import SlidesEditor


DREI = [
    {'titel': 'Foto & Verwendung', 'text': '', 'punkte': ['Foto für LegicCard']},
    {'titel': 'Foto-Regeln', 'text': '', 'punkte': ['Keine Kopfbedeckungen']},
    {'titel': 'LegicCard', 'text': 'Einleitung', 'punkte': []},
]


@pytest.fixture
def editor(qtbot):
    ed = SlidesEditor()
    qtbot.addWidget(ed)
    ed.set_slides(DREI)
    return ed


def titles(editor):
    return [s['titel'] for s in editor.slides()]


# --- Roundtrip --------------------------------------------------------------

def test_slides_survive_a_roundtrip_unchanged(editor):
    assert editor.slides() == DREI


def test_the_first_slide_is_selected_and_shown(editor):
    assert editor.list.currentRow() == 0
    assert editor.txt_titel.text() == 'Foto & Verwendung'
    assert editor.txt_punkte.toPlainText() == 'Foto für LegicCard'


def test_an_empty_editor_disables_the_fields(qtbot):
    ed = SlidesEditor()
    qtbot.addWidget(ed)
    ed.set_slides([])
    assert ed.slides() == []
    assert not ed.fields.isEnabled()


# --- Bearbeiten -------------------------------------------------------------

def test_edits_land_in_the_selected_slide(editor):
    editor.txt_titel.setText('Neuer Titel')
    editor.txt_punkte.setPlainText('Erster Punkt\nZweiter Punkt')
    result = editor.slides()
    assert result[0]['titel'] == 'Neuer Titel'
    assert result[0]['punkte'] == ['Erster Punkt', 'Zweiter Punkt']
    assert result[1] == DREI[1]  # die uebrigen bleiben unangetastet


def test_switching_selection_keeps_the_previous_edit(editor):
    # Der Kernfall: tippen, wegklicken, zurueckklicken.
    editor.txt_titel.setText('Geaendert')
    editor.list.setCurrentRow(2)
    assert editor.txt_titel.text() == 'LegicCard'
    editor.list.setCurrentRow(0)
    assert editor.txt_titel.text() == 'Geaendert'
    assert titles(editor)[0] == 'Geaendert'


def test_loading_a_slide_does_not_overwrite_the_next_one(editor):
    # Beim Befuellen der Felder feuert textChanged; ohne die Sperre schriebe das
    # den Inhalt der neuen Folie in die alte zurueck.
    editor.list.setCurrentRow(1)
    assert titles(editor) == ['Foto & Verwendung', 'Foto-Regeln', 'LegicCard']


def test_blank_lines_between_bullets_are_dropped(editor):
    editor.txt_punkte.setPlainText('Eins\n\n   \nZwei')
    assert editor.slides()[0]['punkte'] == ['Eins', 'Zwei']


def test_the_list_label_follows_the_title(editor):
    editor.txt_titel.setText('Frisch benannt')
    assert editor.list.item(0).text() == 'Frisch benannt'


def test_a_slide_without_a_title_is_labelled_by_its_content(qtbot):
    ed = SlidesEditor()
    qtbot.addWidget(ed)
    ed.set_slides([{'titel': '', 'text': 'Ein Satz', 'punkte': []}])
    assert ed.list.item(0).text() == 'Ein Satz'


# --- Hinzufuegen, Entfernen, Verschieben ------------------------------------

def test_adding_appends_an_empty_slide_and_selects_it(editor):
    editor.add_slide()
    assert editor.list.count() == 4
    assert editor.list.currentRow() == 3
    assert editor.txt_titel.text() == ''
    # Solange nichts eingegeben ist, taucht sie nicht in der Slideshow auf.
    assert len(editor.slides()) == 3


def test_an_added_slide_appears_once_it_has_content(editor):
    editor.add_slide()
    editor.txt_titel.setText('Vierte Folie')
    assert titles(editor)[-1] == 'Vierte Folie'


def test_removing_drops_the_selected_slide(editor):
    editor.list.setCurrentRow(1)
    editor.remove_current()
    assert titles(editor) == ['Foto & Verwendung', 'LegicCard']
    # Die Auswahl rutscht auf die Folie, die nun an dieser Stelle steht.
    assert editor.txt_titel.text() == 'LegicCard'


def test_removing_the_last_slide_clears_the_fields(qtbot):
    ed = SlidesEditor()
    qtbot.addWidget(ed)
    ed.set_slides([{'titel': 'Allein', 'text': '', 'punkte': []}])
    ed.remove_current()
    assert ed.slides() == []
    assert ed.txt_titel.text() == ''
    assert not ed.fields.isEnabled()


def test_moving_down_reorders_and_follows_the_selection(editor):
    editor.list.setCurrentRow(0)
    editor._move(1)
    assert titles(editor) == ['Foto-Regeln', 'Foto & Verwendung', 'LegicCard']
    assert editor.list.currentRow() == 1
    assert editor.txt_titel.text() == 'Foto & Verwendung'


def test_moving_up_reorders(editor):
    editor.list.setCurrentRow(2)
    editor._move(-1)
    assert titles(editor) == ['Foto & Verwendung', 'LegicCard', 'Foto-Regeln']


def test_moving_past_the_edges_does_nothing(editor):
    editor.list.setCurrentRow(0)
    editor._move(-1)
    editor.list.setCurrentRow(2)
    editor._move(1)
    assert titles(editor) == ['Foto & Verwendung', 'Foto-Regeln', 'LegicCard']


def test_moving_carries_an_unsaved_edit_along(editor):
    editor.list.setCurrentRow(0)
    editor.txt_titel.setText('Wandert mit')
    editor._move(1)
    assert titles(editor) == ['Foto-Regeln', 'Wandert mit', 'LegicCard']
