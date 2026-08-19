"""Die Einmal-Entscheidung hinter der Kurzanleitung (Issue #46).

Zwei Haelften. Die reine Haelfte prueft ``app/core/util/onboarding.py`` ohne
Qt - der Marker ist eine leere Datei, mehr steckt nicht dahinter. Die
Fenster-Haelfte prueft die Stelle, die vorher niemand gedeckt hat: das
``main_window``-Fixture patcht ``_maybe_show_onboarding`` fuer alle GUI-Tests
weg, weil der modale Dialog sonst die Fensterkonstruktion blockiert - also
lief der Onboarding-Pfad im gesamten Testlauf kein einziges Mal. Dafuer gibt
es ``main_window_factory(onboarding=True)``.

Zwei Dinge sind in der Fenster-Haelfte nicht verhandelbar:

* ``app.ui.main_window.CONFIG_DIR`` wird in **jedem** Fenstertest auf
  *tmp_path* gebogen. Ohne das schriebe der erste Test seinen ``.onboarded``
  in das sitzungsweite Konfigurationsverzeichnis aus conftest.py, und jeder
  spaetere Test wuerde je nach Reihenfolge gruen werden, ohne etwas zu pruefen.
* ``MainWindow.show_onboarding`` wird durch einen Zaehler ersetzt. Der echte
  Dialog ruft ``exec()`` - ein modaler Aufruf ohne Nutzerin haengt fuer immer.
"""
import os

import pytest

from app.core.util.onboarding import MARKER_NAME, mark_shown, marker_path, should_show
from app.ui.main_window import MainWindow


# --- Der reine Marker ------------------------------------------------------

def test_a_fresh_config_dir_shows_the_guide(tmp_path):
    assert should_show(tmp_path) is True


def test_the_guide_is_gone_after_it_was_marked(tmp_path):
    assert mark_shown(tmp_path) is True
    assert should_show(tmp_path) is False


def test_the_marker_is_the_file_the_installed_base_already_has(tmp_path):
    """Der Name ist tragend, nicht kosmetisch: auf jedem Rechner, auf dem die
    App schon lief, liegt genau diese Datei. Wer sie umbenennt, zeigt allen
    Bestandsnutzerinnen die Kurzanleitung noch einmal."""
    assert MARKER_NAME == '.onboarded'
    mark_shown(tmp_path)
    assert (tmp_path / '.onboarded').exists()
    assert marker_path(tmp_path) == tmp_path / '.onboarded'


def test_marking_twice_is_idempotent(tmp_path):
    assert mark_shown(tmp_path) is True
    assert mark_shown(tmp_path) is True
    assert should_show(tmp_path) is False


def test_the_marker_is_empty(tmp_path):
    # touch() und nichts weiter - der Inhalt darf nie Bedeutung bekommen.
    mark_shown(tmp_path)
    assert marker_path(tmp_path).read_bytes() == b''


@pytest.mark.skipif(os.name == 'nt', reason='chmod steuert unter Windows keinen Schreibschutz')
def test_an_unwritable_config_dir_is_reported_not_raised(tmp_path):
    """Portabler Betrieb von einem schreibgeschuetzten Netzlaufwerk: die
    Kurzanleitung kommt beim naechsten Start halt wieder - das ist deutlich
    harmloser als ein Absturz direkt nach dem Willkommensdialog."""
    readonly = tmp_path / 'readonly'
    readonly.mkdir()
    readonly.chmod(0o500)
    try:
        assert mark_shown(readonly) is False
        assert should_show(readonly) is True
    finally:
        readonly.chmod(0o700)      # sonst raeumt pytest tmp_path nicht ab


# --- Das Fenster -----------------------------------------------------------

@pytest.fixture
def onboarding_calls(monkeypatch, tmp_path):
    """Zaehlt die Dialogaufrufe und legt den Marker in *tmp_path*.

    Beides gehoert zusammen und darf in keinem Fenstertest fehlen (siehe
    Modul-Docstring), deshalb steht es hier als ein einziges Fixture statt als
    zwei Zeilen, die man einzeln vergessen kann. Bleibt lokal: kein anderes
    Testmodul baut ein Fenster mit Onboarding.
    """
    monkeypatch.setattr('app.ui.main_window.CONFIG_DIR', tmp_path)
    calls = []
    monkeypatch.setattr(MainWindow, 'show_onboarding', lambda self: calls.append(1))
    return calls


def test_the_first_start_shows_the_guide_and_writes_the_marker(
    main_window_factory, onboarding_calls, tmp_path
):
    main_window_factory(onboarding=True)
    assert len(onboarding_calls) == 1
    assert (tmp_path / MARKER_NAME).exists()


def test_an_existing_marker_skips_the_guide(
    main_window_factory, onboarding_calls, tmp_path
):
    mark_shown(tmp_path)
    main_window_factory(onboarding=True)
    assert onboarding_calls == []


def test_a_second_window_does_not_show_the_guide_again(
    main_window_factory, onboarding_calls
):
    """Der eigentliche Sinn des Markers - einmal, nicht bei jedem Start."""
    main_window_factory(onboarding=True)
    main_window_factory(onboarding=True)
    assert len(onboarding_calls) == 1


def test_an_unwritable_config_dir_still_lets_the_window_come_up(
    main_window_factory, monkeypatch, onboarding_calls
):
    """Der Fehlerfall aus mark_shown() darf die Konstruktion nicht abbrechen -
    ein Absturz direkt nach dem Willkommensdialog waere das Schlimmste, was an
    dieser Stelle passieren kann."""
    # Das Fenster importiert die Funktion unter eigenem Namen; der Patch muss
    # deshalb dort sitzen und nicht im Ursprungsmodul.
    monkeypatch.setattr('app.ui.main_window.mark_onboarding_shown', lambda config_dir: False)
    win = main_window_factory(onboarding=True)
    assert len(onboarding_calls) == 1
    assert win.isEnabled() is True
