"""Der Testmodus und seine eine harte Zusage (Issue #46).

Kein Qt: ``activate_test_mode`` ist seit #46 eine gewoehnliche Funktion, also
laeuft hier weder ein Fenster noch ein Dialog. Auch nichts weggemockt - das
Roster wird wirklich geschrieben und mit dem echten ``ExcelReader``
zurueckgelesen, denn genau die Kette "Datei erzeugen -> laden koennen" ist der
Zweck des Moduls.

Die *eine* Zusage, wegen der es das Modul ueberhaupt gibt: die Umleitung gilt
nur fuer diese Sitzung. Waere sie je gespeichert, blieben die echten
Ausgabepfade der Nutzerin ueberschrieben, nur weil jemand kurz den Testmodus
ausprobiert hat - siehe ``test_settings_are_never_saved``.

``config_dir`` ist immer *tmp_path*, niemals das echte CONFIG_DIR: der Modus
legt Ordner an und schreibt Dateien.
"""
from app.core.config.settings import Settings
from app.core.excel.reader import ExcelReader
from app.core.test_mode import TEST_DATA_DIRNAME, TEST_ROSTER_NAME, activate_test_mode


# --- Hilfen ----------------------------------------------------------------

# Kein 'test'-Praefix: pytest sammelt per Vorgabe alles ein, was mit 'test'
# beginnt - auch ohne Unterstrich.
def daten_dir(tmp_path):
    return tmp_path / TEST_DATA_DIRNAME


# --- Roster ----------------------------------------------------------------

def test_the_roster_is_written_below_the_config_dir(settings, tmp_path):
    path = activate_test_mode(settings, tmp_path)
    assert path == daten_dir(tmp_path) / TEST_ROSTER_NAME
    assert path.exists()


def test_the_generated_roster_can_be_loaded(settings, tmp_path):
    """Nur *eine* Zusicherung: dass die Datei fuer den ExcelReader ueberhaupt
    ein Roster ist. Die Form des Rosters (Klassen, IDs, Eindeutigkeit) deckt
    tests/test_excel_test_data.py ab - hier waere sie eine zweite Kopie
    derselben Deckung."""
    path = activate_test_mode(settings, tmp_path)
    reader = ExcelReader(path, settings.excelMapping.model_dump())
    assert reader.locations()


def test_the_roster_uses_the_configured_column_mapping(settings, tmp_path):
    # Der Testmodus reicht das excelMapping durch; mit einem abweichenden
    # Mapping muss der Reader dieselbe Datei genauso lesen koennen.
    settings.excelMapping.klasse = 'B'
    settings.excelMapping.nachname = 'C'
    settings.excelMapping.vorname = 'D'
    settings.excelMapping.schuelerId = 'E'
    path = activate_test_mode(settings, tmp_path)
    reader = ExcelReader(path, settings.excelMapping.model_dump())
    assert reader.locations()


# --- Umgelenkte Ausgabe ----------------------------------------------------

def test_the_output_path_is_redirected_below_testdaten(settings, tmp_path):
    activate_test_mode(settings, tmp_path)
    assert settings.ausgabeBasisPfad.parent == daten_dir(tmp_path)


def test_the_new_learner_path_is_redirected_below_testdaten(settings, tmp_path):
    activate_test_mode(settings, tmp_path)
    assert settings.neueLernendeBasisPfad.parent == daten_dir(tmp_path)


def test_the_two_output_paths_stay_distinct(settings, tmp_path):
    activate_test_mode(settings, tmp_path)
    assert settings.ausgabeBasisPfad != settings.neueLernendeBasisPfad


# --- Nur fuer diese Sitzung ------------------------------------------------

def test_settings_are_never_saved(settings, tmp_path, monkeypatch):
    """Der Kern des Moduls: die Umleitung darf nicht in settings.json landen.

    Ein Aufruf von ``Settings.save`` bringt den Test hier sofort zum Scheitern,
    statt ihn nur "vermutlich nicht" zu erwarten. Wer den Testmodus erweitert
    und dabei speichert, ueberschreibt die echten Ausgabepfade der Nutzerin -
    genau dieser Fall soll rot werden.
    """
    def explode(self, *args, **kwargs):
        raise AssertionError('activate_test_mode darf settings.save() nie rufen')

    monkeypatch.setattr(Settings, 'save', explode)
    activate_test_mode(settings, tmp_path)


def test_unrelated_settings_are_left_alone(settings, tmp_path):
    missed_before = settings.missedPath
    bild_before = settings.bild.model_dump()
    activate_test_mode(settings, tmp_path)
    assert settings.missedPath == missed_before
    assert settings.bild.model_dump() == bild_before


# --- Wiederholung ----------------------------------------------------------

def test_a_second_activation_does_not_raise(settings, tmp_path):
    """Der Knopf ist mehrfach erreichbar; das zweite Mal trifft auf einen
    bestehenden Ordner und ein bestehendes Roster."""
    first = activate_test_mode(settings, tmp_path)
    second = activate_test_mode(settings, tmp_path)
    assert second == first
    assert second.exists()


def test_a_second_activation_keeps_the_redirected_paths(settings, tmp_path):
    activate_test_mode(settings, tmp_path)
    redirected = settings.ausgabeBasisPfad
    activate_test_mode(settings, tmp_path)
    assert settings.ausgabeBasisPfad == redirected
