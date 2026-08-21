"""Der Name auf dem Bildschirm und die ID auf der Datei muessen dieselbe Person meinen.

Das ist der eine Fehler, den im Betrieb **nichts** sichtbar macht. Zeigt die App
"Anna Abt" und legt das Foto unter Beats ID ab, gibt es keine Meldung, keinen
Absturz und keine Luecke: der Fototag laeuft unauffaellig durch, jede Datei traegt
eine gueltige ID, und ``tools/check_output.py`` meldet "keine Auffaelligkeiten" -
es prueft die Buchhaltung (gehoert jede Datei genau einer Zeile?), nicht die
Zuordnung Gesicht -> Name. Auffallen wuerde es erst Wochen spaeter auf einem
Ausweis. Genau deshalb steht das hier und nicht im Kopf der Fotografin.

Bestehende Tests decken die beiden Haelften getrennt ab: ``test_mainwindow_ui.py``
prueft die Labels, ``test_photo_saving.py`` die Dateinamen. Hier wird die
**Kopplung** festgehalten - was beim Ausloesen auf dem Bildschirm stand, muss zu
der Datei passen, die dabei entstanden ist.

Zwei Entscheidungen, die diesen Test erst wirksam machen:

* Namen und IDs im Roster laufen bewusst **nicht** parallel (die IDs sind
  gewuerfelt und haben keinen Bezug zur Zeilennummer). In Fixtures wie
  ``John Doe = "1", Jane Roe = "2"`` wuerde ein Versatz um eine Position zwar
  eine falsche Datei erzeugen, aber die Erwartung waere genauso verschoben.
* Es wird gegen eine echte Excel-Datei gearbeitet, nicht gegen ein Reader-Double
  - dieselbe Begruendung wie in ``test_id_conflicts_end_to_end.py``: die Typen,
  die openpyxl aus einer Zelle liefert, sind Teil des Problems.

Geprueft werden alle Wege, die den Index verschieben koennen: Reihenfolge,
Ueberspringen, Sprung zu einer Person, Person hinzufuegen und Foto verwerfen.
"""
import openpyxl
import pytest
from PySide6 import QtCore

from app.core.display.state import format_name
from app.core.excel.reader import ExcelReader
from app.ui.main_window import MainWindow


STANDORT = "Sursee"
KLASSE = "INF23a"

MAPPING = {
    "klasse": "A",
    "nachname": "B",
    "vorname": "C",
    "schuelerId": "D",
    "fotografiert": "E",
    "aufnahmedatum": "F",
    "grund": "G",
}

# (Nachname, Vorname, SchuelerID). Die IDs stehen absichtlich in keinem
# Zusammenhang zur Position: weder aufsteigend noch aus der Zeile ableitbar.
# Ein Versatz um eine Position liefert damit garantiert eine ID, die einer
# anderen Person gehoert - und faellt auf.
ROSTER = [
    ("Abt", "Anna", "7413"),
    ("Brun", "Beat", "2856"),
    ("Curti", "Chiara", "9021"),
    ("Dubois", "Dario", "4390"),
    ("Egli", "Elif", "6175"),
]

ID_BY_NAME = {f"{vorname} {nachname}": sid for nachname, vorname, sid in ROSTER}
NAMES = list(ID_BY_NAME)


# --- Aufbau -----------------------------------------------------------------

@pytest.fixture
def win(main_window, tmp_path):
    """MainWindow mit einer echten Excel-Liste, geladen ueber den GUI-Weg."""
    path = tmp_path / "roster.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = STANDORT
    ws.append(["Klasse", "Nachname", "Vorname", "ID", "Fotografiert", "Datum", "Grund"])
    for nachname, vorname, sid in ROSTER:
        ws.append([KLASSE, nachname, vorname, sid, None, None, None])
    wb.save(path)

    main_window.reader = ExcelReader(path, MAPPING)
    main_window.cmb_location.addItems(main_window.reader.locations())
    main_window.cmb_location.setCurrentIndex(0)
    main_window.cmb_class.setCurrentIndex(0)
    return main_window


def gezeigter_name(win):
    """Der Name im Label, ohne den Zaehler ``(3/5)``."""
    return win.label_current.text().rsplit(" (", 1)[0]


def fotografieren(win, qtbot):
    """Loest aus und liefert das Paar (gezeigter Name, geschriebene Datei).

    Der Name wird **vor** dem Klick gelesen - danach ist die Anzeige laengst
    eine Person weiter, und der Test pruefte sich selbst gegen den falschen
    Stand.
    """
    name = gezeigter_name(win)
    vorher = len(win.camera.captured)
    qtbot.mouseClick(win.btn_capture, QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: not getattr(win, "busy", False))
    assert len(win.camera.captured) == vorher + 1, f"keine Aufnahme fuer {name}"
    return name, win.camera.captured[-1].name


def pruefe_paare(paare):
    """Jedes Paar muss auf dieselbe Person zeigen."""
    for name, datei in paare:
        assert name in ID_BY_NAME, f"unbekannter Name auf dem Bildschirm: {name!r}"
        erwartet = f"{ID_BY_NAME[name]}.jpg"
        assert datei == erwartet, (
            f"Auf dem Bildschirm stand {name!r}, gespeichert wurde aber {datei!r} "
            f"statt {erwartet!r} - das Foto haengt an einer fremden SchuelerID."
        )


# --- Die Gegenprobe zuerst --------------------------------------------------

def test_the_check_would_actually_fail_on_a_swapped_pair():
    """Damit die Zusicherung unten nicht leer laeuft.

    Ohne diesen Fall koennte ``pruefe_paare`` versehentlich nichts pruefen und
    alle folgenden Tests waeren gruen, ohne etwas auszusagen.
    """
    pruefe_paare([("Anna Abt", "7413.jpg")])          # richtig gepaart
    with pytest.raises(AssertionError):
        pruefe_paare([("Anna Abt", "2856.jpg")])      # Beats ID unter Annas Namen


def test_the_roster_can_expose_an_off_by_one():
    """Die IDs duerfen nicht der Reihenfolge folgen - sonst waere ein Versatz
    um eine Position nicht von einem korrekten Lauf zu unterscheiden."""
    ids = [sid for _, _, sid in ROSTER]
    assert len(set(ids)) == len(ids)
    assert all(a != b for a, b in zip(ids, ids[1:]))
    assert ids != sorted(ids)


# --- Der normale Durchlauf --------------------------------------------------

def test_every_photo_of_a_full_class_carries_the_id_of_the_shown_person(win, qtbot):
    paare = [fotografieren(win, qtbot) for _ in ROSTER]

    pruefe_paare(paare)
    # Und jede Person genau einmal - kein Doppel, keine Auslassung.
    assert [name for name, _ in paare] == NAMES
    assert sorted(datei for _, datei in paare) == sorted(
        f"{sid}.jpg" for _, _, sid in ROSTER
    )


def test_the_class_is_done_after_the_last_person(win, qtbot):
    for _ in ROSTER:
        fotografieren(win, qtbot)
    assert win.label_current.text() == "Klasse abgeschlossen"
    assert not win.btn_capture.isEnabled()


# --- Wege, die den Index verschieben ----------------------------------------

def test_skipping_does_not_shift_the_id_by_one(win, qtbot, monkeypatch):
    """Ueberspringen ruecken alle Nachfolgenden vor - der haeufigste Ablauf
    ueberhaupt und die naheliegendste Stelle fuer einen Versatz."""
    monkeypatch.setattr(MainWindow, "_ask_skip_reason", lambda self: ("Krank", True))

    erste = fotografieren(win, qtbot)                 # Anna

    uebersprungen = gezeigter_name(win)               # Beat
    qtbot.mouseClick(win.btn_skip, QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: not getattr(win, "busy", False))

    rest = [fotografieren(win, qtbot) for _ in range(3)]

    pruefe_paare([erste] + rest)
    assert uebersprungen == "Beat Brun"
    # Wer uebersprungen wurde, hat keine Datei - und niemand sonst hat seine.
    assert all(datei != "2856.jpg" for _, datei in [erste] + rest)


def test_a_jump_photographs_the_person_that_is_shown(win, qtbot):
    """Der Sprung ist der einzige Weg, der die Reihenfolge wirklich verlaesst."""
    win.jump_to(3)                                    # Dario, vorgezogen
    vorgezogen = fotografieren(win, qtbot)
    assert vorgezogen[0] == "Dario Dubois"

    # Danach geht es an der urspruenglichen Stelle weiter.
    zurueck = fotografieren(win, qtbot)
    assert zurueck[0] == "Anna Abt"

    pruefe_paare([vorgezogen, zurueck])


def test_a_jump_to_the_last_person_and_back(win, qtbot):
    win.jump_to(len(ROSTER) - 1)
    paare = [fotografieren(win, qtbot)]
    paare += [fotografieren(win, qtbot) for _ in range(len(ROSTER) - 1)]

    pruefe_paare(paare)
    assert sorted(name for name, _ in paare) == sorted(NAMES)


def test_a_discarded_photo_keeps_the_pair_together(win, qtbot, monkeypatch):
    """Verwerfen und neu ausloesen darf nicht weiterruecken."""
    seq = iter([False, True])
    monkeypatch.setattr(MainWindow, "_show_review", lambda self, p: next(seq))

    verworfen = gezeigter_name(win)
    qtbot.mouseClick(win.btn_capture, QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: not getattr(win, "busy", False))
    assert gezeigter_name(win) == verworfen           # immer noch dieselbe Person

    pruefe_paare([fotografieren(win, qtbot)])


def test_an_added_person_does_not_take_over_a_roster_id(win, qtbot):
    """Eine hinzugefuegte Person hat keine ID; ihr Foto darf unter keinen
    Umstaenden unter der ID der Person landen, an deren Stelle sie einsteigt."""
    win.controller.add_learner(KLASSE, "Fabio", "Ferrari")
    win.show_next()

    name, datei = fotografieren(win, qtbot)
    assert name == "Fabio Ferrari"
    assert datei == "Fabio_Ferrari.jpg"
    assert datei not in {f"{sid}.jpg" for _, _, sid in ROSTER}

    # Und die verdraengte Person kommt danach mit ihrer eigenen ID dran.
    pruefe_paare([fotografieren(win, qtbot)])


# --- Die Anzeige im Gang ----------------------------------------------------

def display_snapshot(win):
    """Die Momentaufnahme, die draussen im Gang haengt - ueber den echten Weg."""
    win.settings.anzeige.port = 0          # nie 8080 im Test
    win.settings.anzeige.modus = "lokal"   # kein 0.0.0.0, keine Firewall-Frage
    display = win.controller.display
    if not display.running:
        assert display.start() is True
    display.publish()
    return display._server.snapshot()


def test_the_hallway_display_names_the_same_person_as_the_screen(win, qtbot):
    """Die Anzeige ruft die Leute herein. Nennt sie jemand anderen als der
    Bildschirm drinnen, posiert die falsche Person vor der Kamera - und deren
    Foto laeuft dann korrekt unter der ID der aufgerufenen."""
    try:
        for _ in range(len(ROSTER) - 1):
            snapshot = display_snapshot(win)
            assert snapshot["current"] == format_name(
                *gezeigter_name(win).split(" ", 1)
            )
            fotografieren(win, qtbot)
    finally:
        win.controller.display.stop()


def test_the_display_queue_follows_a_jump(win, qtbot):
    """Nach einem Sprung muss draussen weiter die Person stehen, die
    tatsaechlich als Naechstes drankommt - nicht die hinter der vorgezogenen."""
    try:
        win.jump_to(3)                                # Dario vorgezogen
        snapshot = display_snapshot(win)
        assert snapshot["current"] == "Dario D."
        assert snapshot["upcoming"][0] == "Anna A."   # nicht "Elif E."
    finally:
        win.controller.display.stop()
