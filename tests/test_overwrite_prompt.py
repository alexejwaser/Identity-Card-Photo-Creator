"""Die Rueckfrage, wenn schon eine Datei unter diesem Namen liegt.

Zwei verschiedene Lagen landen in derselben Frage:

* **Dieselbe Person nochmal.** Kommt jemand zurueck, weil das erste Bild nichts
  taugte, ersetzt "Ueberschreiben" nur das eigene aeltere Foto. Frueher entstand
  hier stillschweigend ``12345_1.jpg`` und niemand wusste, welche der beiden
  Dateien die gueltige ist.
* **Zwei verschiedene IDs auf demselben Dateinamen.** Dann gehoert die
  vorhandene Datei moeglicherweise jemand anderem, und Ueberschreiben loescht
  deren Foto - waehrend die Person in Excel als fotografiert gilt. Genau das
  muss im Text stehen, sonst ist die Entscheidung keine.

Der Dialog wird nie wirklich geoeffnet (``exec()`` auf einer modalen Box haengt
im Test): geprueft wird einerseits der Text, den ``_ask_overwrite`` baut,
andererseits was ``capture_photo`` aus den drei moeglichen Antworten macht.
"""
import openpyxl
import pytest

import app.core.controller as controller_module
from app.core.excel.reader import ExcelReader, Learner
from app.core.util.paths import target_file_path, unique_file_path
from app.ui.main_window import MainWindow

# Beim Import festgehalten, *bevor* das main_window-Fixture die Methode
# klassenweit durch eine feste Antwort ersetzt. Die Textpruefungen unten wollen
# den echten Dialogaufbau sehen, nicht die Vorgabe aus conftest.py.
ECHTES_ASK = MainWindow.__dict__["_ask_overwrite"]


MAPPING = {
    "klasse": "A", "nachname": "B", "vorname": "C", "schuelerId": "D",
    "fotografiert": "E", "aufnahmedatum": "F", "grund": "G",
}


# --- Hilfen ----------------------------------------------------------------

def roster(tmp_path, *zeilen):
    path = tmp_path / "roster.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bern"
    ws.append(["Klasse", "Nachname", "Vorname", "ID", "Fotografiert", "Datum", "Grund"])
    for nachname, sid in zeilen:
        ws.append(["1a", nachname, "Vorname", sid, None, None, None])
    wb.save(path)
    return path


def vorbereiten(win, tmp_path, *zeilen):
    win.reader = ExcelReader(roster(tmp_path, *zeilen), MAPPING)
    win.cmb_location.clear()
    win.cmb_location.addItem("Bern")
    win.controller.learners_for_class("Bern", "1a")
    win.controller.current = 0
    return win.controller.learners


def antwort(win, wert):
    """Ersetzt die modale Frage durch eine feste Antwort."""
    win._ask_overwrite = lambda learner, location: wert


# --- Der Text der Frage ----------------------------------------------------

def test_the_question_names_the_file_and_the_person(main_window, tmp_path, monkeypatch):
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12345"))
    gebaut = {}
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.exec", lambda self: gebaut.update(text=self.text())
    )
    ECHTES_ASK(main_window, lernende[0], "Bern")
    assert "12345.jpg" in gebaut["text"]
    assert "Alpha" in gebaut["text"]


def test_a_collision_with_another_id_is_spelled_out(main_window, tmp_path, monkeypatch):
    """Die Zusage aus der Entscheidung: die Operatorin darf ueberschreiben,
    aber nicht ahnungslos."""
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12.345"), ("Beta", "12345"))
    gebaut = {}
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.exec", lambda self: gebaut.update(text=self.text())
    )
    beta = [l for l in lernende if l.nachname == "Beta"][0]
    ECHTES_ASK(main_window, beta, "Bern")

    assert "12.345" in gebaut["text"]              # die fremde ID wird genannt
    assert "verloren" in gebaut["text"]            # und die Folge benannt


def test_the_same_id_alone_gets_no_foreign_id_warning(main_window, tmp_path, monkeypatch):
    """Ohne Kollision darf die Warnung nicht erscheinen - sonst stumpft sie ab."""
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12345"))
    gebaut = {}
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.exec", lambda self: gebaut.update(text=self.text())
    )
    ECHTES_ASK(main_window, lernende[0], "Bern")
    assert "ACHTUNG" not in gebaut["text"]


def test_the_question_explains_what_keeping_both_costs(main_window, tmp_path, monkeypatch):
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12345"))
    gebaut = {}
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.exec", lambda self: gebaut.update(text=self.text())
    )
    ECHTES_ASK(main_window, lernende[0], "Bern")
    assert "12345_1.jpg" in gebaut["text"]
    assert "keine SchülerID mehr" in gebaut["text"]


# --- Was aus der Antwort folgt ---------------------------------------------

def test_overwrite_replaces_the_existing_file(main_window, tmp_path, monkeypatch):
    # Ohne das echte unique_file_path ist dieser Test blind: das Fixture-Double
    # vergibt gar kein Suffix, also schriebe auch ein ignoriertes overwrite=True
    # brav nach 12345.jpg und der Test bliebe gruen.
    monkeypatch.setattr(controller_module, "unique_file_path", unique_file_path)
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12345"))
    ziel = main_window.controller.planned_photo_path(lernende[0], "Bern")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"alt")

    antwort(main_window, True)
    main_window.capture_photo()

    assert main_window.controller.camera.captured == [ziel]
    assert ziel.read_bytes() != b"alt"                     # wirklich ersetzt
    assert not (ziel.parent / "12345_1.jpg").exists()      # keine zweite Datei


def test_keeping_both_writes_the_suffixed_file(main_window, tmp_path, monkeypatch):
    # Das main_window-Fixture ersetzt unique_file_path durch eine Variante ohne
    # Suffix, damit Pfade in den uebrigen Tests vorhersagbar sind. Genau das
    # Suffix ist hier aber der Prueffall, also gilt wieder das Echte.
    monkeypatch.setattr(controller_module, "unique_file_path", unique_file_path)
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12345"))
    ziel = main_window.controller.planned_photo_path(lernende[0], "Bern")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"alt")

    antwort(main_window, False)
    main_window.capture_photo()

    assert ziel.read_bytes() == b"alt"                     # das alte bleibt
    assert (ziel.parent / "12345_1.jpg").exists()


def test_cancelling_writes_nothing_and_never_fires_the_camera(main_window, tmp_path):
    """Abbrechen ist auch die Vorgabetaste des Dialogs: wer die Meldung
    reflexhaft wegdrueckt, soll nichts zerstoeren und nichts Unzuordenbares
    anlegen."""
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12345"))
    ziel = main_window.controller.planned_photo_path(lernende[0], "Bern")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"alt")

    antwort(main_window, None)
    main_window.capture_photo()

    assert main_window.controller.camera.captured == []
    assert ziel.read_bytes() == b"alt"
    assert not (ziel.parent / "12345_1.jpg").exists()
    assert main_window.controller.current == 0             # niemand uebersprungen
    assert main_window.busy is False                       # Knoepfe wieder frei


def test_no_question_when_the_name_is_free(main_window, tmp_path):
    lernende = vorbereiten(main_window, tmp_path, ("Alpha", "12345"))

    gefragt = []
    main_window._ask_overwrite = lambda learner, location: gefragt.append(1) or False
    main_window.capture_photo()

    assert gefragt == []
    assert len(main_window.controller.camera.captured) == 1


# --- Die Pfad-Aufteilung dahinter ------------------------------------------

def test_target_file_path_does_not_uniquify_or_create_anything(tmp_path):
    """target_file_path beantwortet 'welche Datei meine ich?', nicht 'ist der
    Name frei?'. Ohne diese Trennung koennte capture_photo gar nicht pruefen,
    ob schon etwas da ist - unique_file_path haette laengst umbenannt."""
    ziel = target_file_path(tmp_path / "neu", "12345.jpg")
    assert ziel.name == "12345.jpg"
    assert not ziel.parent.exists()                        # nichts angelegt

    (tmp_path / "neu").mkdir()
    ziel.write_bytes(b"x")
    assert target_file_path(tmp_path / "neu", "12345.jpg") == ziel     # unveraendert
    assert unique_file_path(tmp_path / "neu", "12345.jpg").name == "12345_1.jpg"


def test_target_file_path_sanitises_like_unique_file_path(tmp_path):
    """Beide muessen denselben Namen bilden - sonst prueft die App auf eine
    andere Datei, als sie danach schreibt."""
    assert (
        target_file_path(tmp_path, "12.345.jpg").name
        == unique_file_path(tmp_path, "12.345.jpg").name
    )
