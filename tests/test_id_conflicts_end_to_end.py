"""Von der Excel-Zelle bis zur blockierten Aufnahme.

tests/test_identity.py prueft die Erkennung fuer sich allein. Hier geht es um
die Kette drumherum, denn dort sassen die beiden eigentlichen Fehler:

1. Die Pruefung lief gegen die **rohen** IDs, die Kollision entsteht aber erst
   im Dateinamen - '12.345' und '12345' kamen sauber durch und ergaben beide
   '12345.jpg'.
2. Die Pruefung lief gegen die **gefilterte** Arbeitsliste. Wer schon
   fotografiert war, fiel bei skip_photographed heraus - seine Datei liegt aber
   im Ausgabeordner und kollidiert weiterhin.

Deshalb wird hier mit einer echten Excel-Datei gearbeitet statt mit einem
Reader-Double: die Typen, die openpyxl aus einer Zelle zurueckgibt, sind Teil
des Problems und ein Double wuerde sie wegdefinieren.
"""
import openpyxl
import pytest

from app.core.controller import MainController
from app.core.excel.reader import ExcelReader
from app.core.identity import storage_key


MAPPING = {
    "klasse": "A",
    "nachname": "B",
    "vorname": "C",
    "schuelerId": "D",
    "fotografiert": "E",
    "aufnahmedatum": "F",
    "grund": "G",
}


# --- Hilfen ----------------------------------------------------------------

def roster(tmp_path, *zeilen, standort="Bern"):
    """*zeilen* sind (nachname, id) oder (nachname, id, 'Ja') fuer bereits
    fotografiert."""
    path = tmp_path / "roster.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = standort
    ws.append(["Klasse", "Nachname", "Vorname", "ID", "Fotografiert", "Datum", "Grund"])
    for zeile in zeilen:
        nachname, sid = zeile[0], zeile[1]
        fotografiert = zeile[2] if len(zeile) > 2 else None
        ws.append(["1a", nachname, "Vorname", sid, fotografiert, None, None])
    wb.save(path)
    return path


def controller_for(settings, path):
    ctrl = MainController.__new__(MainController)   # ohne Kamera-Aufbau
    ctrl.settings = settings
    ctrl.reader = ExcelReader(path, MAPPING)
    ctrl.learners = []
    ctrl.current = 0
    ctrl.id_conflicts = []
    return ctrl


def keys(conflicts):
    return sorted(c.key for c in conflicts)


# --- Excel-Zelle -> ID ------------------------------------------------------

def test_a_whole_number_cell_does_not_grow_a_decimal_tail(settings, tmp_path):
    """openpyxl liefert fuer 12345.0 ein int, nicht ein float.

    Waere es ein float, ergaebe str() '12345.0' und der Dateiname waere
    '123450' - eine ID, die es gar nicht gibt. Der Fall haelt hier fest, dass
    das *nicht* passiert; wer die Lesekette anfasst, sieht es sofort.
    """
    path = roster(tmp_path, ("Muster", 12345.0))
    lernende = ExcelReader(path, MAPPING).learners("Bern", "1a")
    assert lernende[0].schueler_id == "12345"
    assert storage_key(lernende[0].schueler_id) == "12345"


# --- Die Kollision, die frueher durchrutschte ------------------------------

def test_ids_differing_only_in_punctuation_are_caught(settings, tmp_path):
    """Der Fall aus der Praxis: ein Tausenderpunkt in einer von Hand
    gepflegten Liste. Beide ergeben '12345.jpg'."""
    path = roster(tmp_path, ("Alpha", "12.345"), ("Beta", "12345"))
    ctrl = controller_for(settings, path)
    ctrl.learners_for_class("Bern", "1a")
    assert keys(ctrl.id_conflicts) == ["12345"]


def test_ids_differing_only_in_whitespace_are_caught(settings, tmp_path):
    path = roster(tmp_path, ("Alpha", "12345 "), ("Beta", "12345"))
    ctrl = controller_for(settings, path)
    ctrl.learners_for_class("Bern", "1a")
    assert keys(ctrl.id_conflicts) == ["12345"]


def test_a_clean_roster_reports_nothing(settings, tmp_path):
    path = roster(tmp_path, ("Alpha", "111"), ("Beta", "222"))
    ctrl = controller_for(settings, path)
    ctrl.learners_for_class("Bern", "1a")
    assert ctrl.id_conflicts == []


# --- Die gefilterte Arbeitsliste -------------------------------------------

def test_an_already_photographed_learner_still_counts(settings, tmp_path):
    """Der zweite Fehler.

    Alpha ist fotografiert und faellt aus der Arbeitsliste - ihre Datei
    '12345.jpg' liegt aber im Ausgabeordner. Beta wuerde jetzt darauf
    kollidieren. Wer nur die Arbeitsliste prueft, sieht genau einen Lernenden
    und meldet nichts.
    """
    path = roster(tmp_path, ("Alpha", "12.345", "Ja"), ("Beta", "12345"))
    ctrl = controller_for(settings, path)
    arbeitsliste = ctrl.learners_for_class("Bern", "1a", skip_photographed=True)

    assert [l.nachname for l in arbeitsliste] == ["Beta"]   # Alpha ist raus
    assert keys(ctrl.id_conflicts) == ["12345"]             # trotzdem erkannt
    assert ctrl.id_conflict_for(arbeitsliste[0]) is not None


def test_reloading_a_clean_class_clears_earlier_conflicts(settings, tmp_path):
    """Die Konflikte gehoeren zur geladenen Klasse, nicht zur Sitzung."""
    path = roster(tmp_path, ("Alpha", "12.345"), ("Beta", "12345"))
    ctrl = controller_for(settings, path)
    ctrl.learners_for_class("Bern", "1a")
    assert ctrl.id_conflicts != []

    # Dieselbe Datei neu schreiben, diesmal ohne Kollision.
    ctrl.reader = ExcelReader(roster(tmp_path, ("Gamma", "777")), MAPPING)
    ctrl.learners_for_class("Bern", "1a")
    assert ctrl.id_conflicts == []


# --- Die blockierte Aufnahme -----------------------------------------------

def test_a_conflicted_learner_is_blocked_and_the_camera_never_fires(
    main_window, settings, tmp_path, monkeypatch
):
    """Die Zusage aus der Entscheidung: lieber laut stehenbleiben als ein Foto
    ablegen, das spaeter der falschen Person zugeordnet wird."""
    path = roster(tmp_path, ("Alpha", "12.345"), ("Beta", "12345"))
    main_window.reader = ExcelReader(path, MAPPING)
    main_window.cmb_location.clear()
    main_window.cmb_location.addItem("Bern")
    main_window.controller.learners_for_class("Bern", "1a")
    main_window.controller.current = 0

    gemeldet = []
    main_window._notify = lambda titel, text, level="info", show=True: gemeldet.append(
        (titel, text, level)
    )

    main_window.capture_photo()

    assert main_window.controller.camera.captured == []      # nichts ausgeloest
    assert len(gemeldet) == 1
    titel, text, level = gemeldet[0]
    assert "blockiert" in titel.lower()
    assert level == "error"
    assert "12.345" in text and "12345" in text              # beide IDs genannt
    assert main_window.controller.current == 0               # niemand uebersprungen


def test_an_unconflicted_learner_is_photographed_normally(
    main_window, settings, tmp_path
):
    """Die Gegenprobe - der Riegel darf nicht alles blockieren."""
    path = roster(tmp_path, ("Alpha", "111"), ("Beta", "222"))
    main_window.reader = ExcelReader(path, MAPPING)
    main_window.cmb_location.clear()
    main_window.cmb_location.addItem("Bern")
    main_window.controller.learners_for_class("Bern", "1a")
    main_window.controller.current = 0

    main_window.capture_photo()

    assert len(main_window.controller.camera.captured) == 1
