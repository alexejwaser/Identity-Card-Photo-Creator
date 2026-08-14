"""Snapshot-Logik der Wartezimmer-Anzeige.

Die Faelle spiegeln die Abloeufe im Hauptfenster: Ueberspringen, Foto verwerfen,
Person hinzufuegen, Sprung zu einer spezifischen Person, Klasse abschliessen.
"""
from app.core.display.state import (
    STATE_DONE,
    STATE_IDLE,
    STATE_RUNNING,
    build_snapshot,
    format_name,
)
from app.core.excel.reader import Learner


def make_learners(*names):
    """*names* sind Vornamen; der Nachname ist 'Nachname<N>'."""
    return [
        Learner('1a', f'Nachname{i}', vorname, str(100 + i))
        for i, vorname in enumerate(names)
    ]


def snap(learners, current, **kw):
    kw.setdefault('klasse', '1a')
    return build_snapshot(learners=learners, current=current, **kw)


# --- Namensformatierung ----------------------------------------------------

def test_abbreviates_by_default():
    assert format_name('Anna', 'Mueller') == 'Anna M.'


def test_full_name_on_request():
    assert format_name('Anna', 'Mueller', full=True) == 'Anna Mueller'


def test_missing_surname_yields_no_stray_dot():
    # Walk-ins koennen ohne Nachnamen angelegt werden.
    assert format_name('Anna', '') == 'Anna'
    assert format_name('Anna', '   ') == 'Anna'


def test_missing_first_name_falls_back_to_surname():
    assert format_name('', 'Mueller') == 'M.'
    assert format_name('', 'Mueller', full=True) == 'Mueller'


# --- Normalbetrieb ---------------------------------------------------------

def test_current_and_next_three():
    learners = make_learners('Anna', 'Beat', 'Clara', 'David', 'Eva')
    result = snap(learners, 0)
    assert result['state'] == STATE_RUNNING
    assert result['current'] == 'Anna N.'
    assert result['upcoming'] == ['Beat N.', 'Clara N.', 'David N.']
    assert (result['done'], result['total']) == (0, 5)


def test_upcoming_shrinks_near_the_end():
    learners = make_learners('Anna', 'Beat')
    assert snap(learners, 0)['upcoming'] == ['Beat N.']
    assert snap(learners, 1)['upcoming'] == []


def test_count_is_configurable():
    learners = make_learners('Anna', 'Beat', 'Clara', 'David', 'Eva')
    assert len(snap(learners, 0, count=1)['upcoming']) == 1


def test_full_names_propagate_to_the_snapshot():
    learners = make_learners('Anna', 'Beat')
    result = snap(learners, 0, full_names=True)
    assert result['current'] == 'Anna Nachname0'
    assert result['upcoming'] == ['Beat Nachname1']


def test_location_and_class_are_carried():
    learners = make_learners('Anna')
    result = snap(learners, 0, standort='Bern')
    assert (result['standort'], result['klasse']) == ('Bern', '1a')


# --- Ablaeufe aus dem Hauptfenster -----------------------------------------

def test_skip_advances_like_a_taken_photo():
    learners = make_learners('Anna', 'Beat', 'Clara')
    # Ueberspringen und Foto-Uebernehmen enden beide in advance().
    assert snap(learners, 1)['current'] == 'Beat N.'


def test_retaking_a_photo_yields_an_identical_snapshot():
    # "Erneut fotografieren" ruft show_next() erneut auf, ohne advance().
    learners = make_learners('Anna', 'Beat', 'Clara')
    assert snap(learners, 0) == snap(learners, 0)


def test_added_person_becomes_current_without_index_change():
    learners = make_learners('Anna', 'Beat')
    learners.insert(1, Learner('1a', '', 'Zoe', '', is_new=True))
    # add_learner fuegt bei *current* ein - der Index bleibt, die Person wechselt.
    result = snap(learners, 1)
    assert result['current'] == 'Zoe'
    assert result['upcoming'] == ['Beat N.']


def test_jump_computes_upcoming_from_the_return_position():
    learners = make_learners('Anna', 'Beat', 'Clara', 'David')
    # Von Position 0 zu David (Index 3) vorgezogen: als Naechstes sind wieder
    # Anna, Beat und Clara dran - nicht die Leute hinter David.
    result = snap(learners, 3, jump_return=0)
    assert result['current'] == 'David N.'
    assert result['upcoming'] == ['Anna N.', 'Beat N.', 'Clara N.']


def test_without_jump_upcoming_starts_after_current():
    learners = make_learners('Anna', 'Beat', 'Clara')
    assert snap(learners, 1)['upcoming'] == ['Clara N.']


# --- Rand- und Leerzustaende -----------------------------------------------

def test_idle_without_roster():
    result = build_snapshot(learners=[], current=0, klasse='', has_roster=False)
    assert result['state'] == STATE_IDLE
    assert result['current'] is None


def test_idle_when_no_class_is_selected():
    # Standortwechsel und Excel-Neuladen leeren die Klassen-Combo.
    learners = make_learners('Anna')
    assert snap(learners, 0, klasse='')['state'] == STATE_IDLE


def test_done_after_the_last_person():
    learners = make_learners('Anna', 'Beat')
    result = snap(learners, 2)
    assert result['state'] == STATE_DONE
    assert (result['done'], result['total']) == (2, 2)


def test_done_when_class_was_finished_early():
    # "Fertig" laesst den Roster im Controller stehen - ohne das Flag wuerde
    # die Anzeige draussen weiter Anna aufrufen.
    learners = make_learners('Anna', 'Beat')
    assert snap(learners, 0, class_finished=True)['state'] == STATE_DONE


def test_no_student_ids_leak_into_the_payload():
    learners = make_learners('Anna', 'Beat')
    assert '100' not in repr(snap(learners, 0))


# --- Hinweise --------------------------------------------------------------

def test_hints_travel_with_the_snapshot():
    learners = make_learners('Anna')
    result = snap(learners, 0, hints=['Erster Hinweis', 'Zweiter Hinweis'])
    assert result['hints'] == ['Erster Hinweis', 'Zweiter Hinweis']


def test_hints_are_independent_of_the_state():
    # Draussen soll der Hinweis auch beim Warten und nach Klassenschluss lesbar
    # bleiben - er haengt bewusst nicht am Fotografier-Zustand.
    hints = ['Bitte einzeln eintreten']
    idle = build_snapshot(learners=[], current=0, klasse='', has_roster=False, hints=hints)
    done = snap(make_learners('Anna'), 0, class_finished=True, hints=hints)
    assert idle['hints'] == hints
    assert done['hints'] == hints


def test_blank_hint_lines_are_dropped():
    # Das Textfeld in den Einstellungen produziert leicht Leerzeilen.
    result = snap(make_learners('Anna'), 0, hints=['  Echt  ', '', '   '])
    assert result['hints'] == ['Echt']


def test_no_hints_yields_an_empty_list():
    assert snap(make_learners('Anna'), 0)['hints'] == []


def test_hint_interval_is_carried_and_floored():
    assert snap(make_learners('Anna'), 0, hint_interval=25)['hint_interval'] == 25
    assert snap(make_learners('Anna'), 0, hint_interval=0)['hint_interval'] == 1


# --- Kompaktmodus ----------------------------------------------------------

def test_compact_flag_travels_with_the_snapshot():
    assert snap(make_learners('Anna'), 0, compact=True)['compact'] is True
    assert snap(make_learners('Anna'), 0)['compact'] is False


def test_compact_does_not_strip_hints_at_the_source():
    # Ausgeblendet wird erst auf der Seite - so wirkt ein Umschalten sofort,
    # ohne dass draussen jemand neu laden muss.
    result = snap(make_learners('Anna'), 0, compact=True, hints=['Ein Hinweis'])
    assert result['hints'] == ['Ein Hinweis']
