"""Die Kette ID -> Dateiname, und wo sie mehrdeutig wird.

Diese Datei haelt den einen Fehler fest, der in dieser App am teuersten ist und
am leisesten passiert: ein Foto landet unter der ID einer anderen Person. Es
gibt dafuer keine Fehlermeldung und keinen Absturz - nur ein falsches Gesicht
auf einem Ausweis, Wochen spaeter.

Die erste Haelfte ist bewusst *charakterisierend*: sie schreibt fest, was
``sanitize_name`` heute tut. Diese Umwandlung wird hier **nicht** repariert -
sie muss Umlaute und Sonderzeichen entschaerfen, damit Windows-Pfade nicht
zerbrechen, und genau dabei wirft sie zwangslaeufig Information weg. Repariert
wird stattdessen die Pruefung: sie sucht die Kollision jetzt dort, wo sie
entsteht.
"""
import pytest

from app.core.identity import (
    IdConflict,
    conflict_for,
    find_id_conflicts,
    storage_key,
)
from app.core.excel.reader import Learner
from app.core.util.paths import unique_file_path


# --- Hilfen ----------------------------------------------------------------

def learner(sid, nachname="Muster", vorname="Anna", is_new=False):
    return Learner("1a", nachname, vorname, str(sid), is_new=is_new)


def keys(conflicts):
    return sorted(c.key for c in conflicts)


# --- Charakterisierung: was sanitize_name aus einer ID macht ----------------
# Nicht der Sollzustand, sondern der Istzustand. Aendert jemand die
# Umwandlung, sollen diese Faelle bewusst rot werden.

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("12345", "12345"),      # der Normalfall
        ("12345 ", "12345"),     # Leerzeichen aus der Excel-Pflege
        (" 12345", "12345"),
        ("12.345", "12345"),     # der Punkt faellt weg
        ("12/345", "12345"),
        ("12-345", "12-345"),    # Bindestrich bleibt - keine Kollision
        ("A123", "A123"),
        ("MÜ123", "MU123"),      # Umlaut wird zerlegt
        ("...", ""),             # nichts Verwertbares uebrig
        ("", ""),
    ],
)
def test_the_storage_key_is_what_sanitize_name_makes_of_the_id(raw, expected):
    assert storage_key(raw) == expected


def test_five_different_ids_map_to_the_same_file_name():
    """Der Kern des Problems, in einer Zeile.

    Das ist kein konstruierter Extremfall: ein nachgetragenes Leerzeichen und
    ein Tausenderpunkt sind genau das, was in einer von Hand gepflegten
    Excel-Liste passiert.
    """
    kollidierend = ["12345", "12345 ", " 12345", "12.345", "12/345"]
    assert {storage_key(sid) for sid in kollidierend} == {"12345"}


def test_the_collision_really_reaches_the_disk(tmp_path):
    """Beweist, dass die Kollision nicht theoretisch ist.

    ``unique_file_path`` ueberschreibt nichts - es haengt _1/_2 an. Genau das
    ist die Falle: es sieht nach Sicherheit aus, aber der Dateiname ist danach
    keine ID mehr, und wer ihn spaeter als ID liest, liegt falsch.
    """
    namen = []
    for sid in ["12345", "12345 ", "12.345"]:
        p = unique_file_path(tmp_path, f"{storage_key(sid)}.jpg")
        p.write_bytes(b"x")
        namen.append(p.name)
    assert namen == ["12345.jpg", "12345_1.jpg", "12345_2.jpg"]


# --- Die Pruefung: Kollisionen finden --------------------------------------

def test_a_clean_roster_has_no_conflicts():
    assert find_id_conflicts([learner(1), learner(2), learner(3)]) == []


def test_the_same_id_twice_is_a_conflict():
    """Der Fall, den auch die alte Pruefung schon fand."""
    conflicts = find_id_conflicts([learner("12345", "A"), learner("12345", "B")])
    assert keys(conflicts) == ["12345"]
    assert conflicts[0].count == 2
    assert conflicts[0].ids == ["12345"]     # eine Roh-ID, zwei Lernende


def test_ids_that_only_collide_after_sanitising_are_a_conflict():
    """Der Fall, den die alte Pruefung uebersah - und der eigentliche Grund
    fuer dieses Modul. Die Roh-IDs sind verschieden, die Dateinamen nicht."""
    conflicts = find_id_conflicts([learner("12.345", "A"), learner("12345", "B")])
    assert keys(conflicts) == ["12345"]
    assert conflicts[0].ids == ["12.345", "12345"]
    assert conflicts[0].count == 2


def test_an_id_that_sanitises_to_nothing_is_a_conflict_on_its_own():
    """Ohne Stamm hiesse die Datei '.jpg'. Auch ohne zweite Person ist das
    keine ablegbare Aufnahme, deshalb zaehlt sie allein schon als Konflikt."""
    conflicts = find_id_conflicts([learner("..."), learner("12345")])
    assert keys(conflicts) == [""]
    assert conflicts[0].unusable is True
    assert conflicts[0].count == 1


def test_new_learners_are_outside_the_id_domain():
    """Neue Lernende werden nach Namen abgelegt, nicht nach ID - eine leere ID
    ist bei ihnen der Normalfall und kein Konflikt."""
    conflicts = find_id_conflicts([learner("", is_new=True), learner("", is_new=True)])
    assert conflicts == []


def test_conflicts_are_reported_per_colliding_file_name():
    conflicts = find_id_conflicts(
        [learner("12.345", "A"), learner("12345", "B"), learner("999", "C"), learner("99.9", "D")]
    )
    assert keys(conflicts) == ["12345", "999"]


def test_the_reported_ids_keep_the_roster_order_and_drop_repeats():
    conflicts = find_id_conflicts(
        [learner("12.345", "A"), learner("12345", "B"), learner("12.345", "C")]
    )
    assert conflicts[0].ids == ["12.345", "12345"]
    assert conflicts[0].count == 3


# --- Zuordnung zu einer einzelnen Lernenden --------------------------------

def test_conflict_for_finds_the_affected_learner():
    roster = [learner("12.345", "A"), learner("12345", "B"), learner("777", "C")]
    conflicts = find_id_conflicts(roster)
    assert conflict_for(roster[0], conflicts) is not None
    assert conflict_for(roster[1], conflicts) is not None
    assert conflict_for(roster[2], conflicts) is None


def test_conflict_for_matches_on_the_file_name_not_the_raw_id():
    """Die entscheidende Zeile: gesucht wird ueber den Dateinamen. Ein
    Vergleich der Roh-IDs faende '12.345' nie in einem Konflikt namens
    '12345'."""
    roster = [learner("12.345", "A"), learner("12345", "B")]
    found = conflict_for(roster[0], find_id_conflicts(roster))
    assert found is not None
    assert found.key == "12345"


def test_a_new_learner_is_never_blocked():
    roster = [learner("", is_new=True)]
    assert conflict_for(roster[0], [IdConflict(key="", ids=[""], count=1)]) is None
