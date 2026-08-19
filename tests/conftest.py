# tests/conftest.py
# Point settings.CONFIG_DIR at a throwaway directory for the whole test
# session, before any test module can import app.core.config.settings (which
# resolves CONFIG_DIR at import time). This prevents tests from ever writing
# to the real user config path (e.g. ~/LegicCardCreator/settings.json) if a
# test forgets to monkeypatch Settings.save().
import copy
import os
import tempfile
from pathlib import Path

os.environ.setdefault("LEGICCARD_CONFIG_DIR", tempfile.mkdtemp(prefix="legiccard_test_config_"))
# Muss ebenfalls vor dem ersten Qt-Import stehen: die GUI-Tests bauen echte
# Fenster, aber es gibt hier keinen Bildschirm.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.core.config.settings import Settings, DEFAULTS
from app.ui.main_window import MainWindow
import app.core.controller as controller_module


# --- gemeinsame Doubles und Fixtures ---------------------------------------
# Diese lagen bis #44 in test_mainwindow_ui.py und test_photo_saving.py doppelt
# (und `settings` sogar dreifach). Zwei Kopien desselben Doubles driften
# irgendwann auseinander: passt jemand DummyCamera an eine geaenderte
# BaseCamera an, bleibt die zweite Kopie stehen und ihre Testdatei laeuft
# weiter gruen gegen ein veraltetes Double - Deckung, die es nicht gibt.


@pytest.fixture
def settings(tmp_path):
    """Vollstaendige Settings auf tmp_path, ohne die echte settings.json.

    `anzeige` wird bewusst nicht uebergeben, damit die Defaults aus
    AnzeigeSettings gelten (Port 8080, modus='netzwerk'). Tests, die die
    Anzeige wirklich starten, ueberschreiben das - siehe
    test_display_controller.py.
    """
    data = copy.deepcopy(DEFAULTS)
    data["ausgabeBasisPfad"] = tmp_path / "out"
    data["missedPath"] = tmp_path / "missed.xlsx"
    return Settings(
        ausgabeBasisPfad=data["ausgabeBasisPfad"],
        missedPath=data["missedPath"],
        bild=data["bild"],
        overlay=data["overlay"],
        kamera=data["kamera"],
        zip=data["zip"],
        copyright=data["copyright"],
        excelMapping=data["excelMapping"],
    )


class DummyCamera:
    """Kamera-Double, das statt echter Hardware eine Datei schreibt."""

    def __init__(self):
        self.captured = []

    def start_liveview(self):
        pass

    def stop_liveview(self):
        pass

    def capture(self, path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"data")
        self.captured.append(p)


@pytest.fixture
def dummy_camera():
    return DummyCamera()


@pytest.fixture
def main_window_factory(qtbot, settings, dummy_camera, monkeypatch, tmp_path):
    """Baut ein MainWindow; `onboarding=True` laesst den Onboarding-Pfad laufen.

    Fabrik statt zweiter Fixture, weil sonst saemtliche Doubles doppelt
    stuenden - genau das, was #44 aufgeraeumt hat. Das Onboarding ist der
    einzige Unterschied und deshalb der einzige Schalter: der modale Dialog
    blockiert sonst die Fensterkonstruktion, weshalb er hier normalerweise
    weggepatcht wird. Wer ihn wirklich testen will (test_onboarding.py), muss
    zusaetzlich `MainWindow.show_onboarding` ersetzen - `exec()` auf einem
    modalen Dialog haengt im Test fuer immer.
    """
    # _init_camera gehoert MainController, nicht MainWindow: das Fenster
    # uebernimmt die Kamera, die der Controller gebaut hat.
    monkeypatch.setattr(
        controller_module.MainController, "_init_camera", lambda self: dummy_camera
    )
    monkeypatch.setattr(
        controller_module, "class_output_dir", lambda base, loc, klass: tmp_path / f"{loc}_{klass}"
    )
    monkeypatch.setattr(
        controller_module, "new_learner_dir", lambda base, loc, klass: tmp_path / f"new_{loc}_{klass}"
    )

    def dummy_unique_file_path(directory, name):
        directory.mkdir(parents=True, exist_ok=True)
        return directory / name

    monkeypatch.setattr(controller_module, "unique_file_path", dummy_unique_file_path)
    monkeypatch.setattr(controller_module, "process_image", lambda *a, **kw: None)
    # Der Code fragt controller.excel_running(); MainWindow._excel_running
    # ist toter Code. Ohne diesen Patch schlagen die Tests auf jedem
    # Rechner fehl, auf dem gerade Excel offen ist.
    monkeypatch.setattr(
        controller_module.MainController, "excel_running", lambda self: False
    )
    monkeypatch.setattr(MainWindow, "_notify", lambda *a, **kw: None)
    # Der Review-Dialog wird automatisch bestaetigt, solange ein Test nichts
    # anderes sagt.
    monkeypatch.setattr(MainWindow, "_show_review", lambda self, path: True)
    # Existiert die Zieldatei schon, fragt capture_photo modal nach
    # ueberschreiben/behalten. Vorgabe hier: "beide behalten" - das ist das
    # Verhalten von frueher, sodass bestehende Tests unveraendert gelten. Wer
    # den Dialog selbst pruefen will, ersetzt ihn im Test (siehe
    # test_overwrite_prompt.py).
    monkeypatch.setattr(MainWindow, "_ask_overwrite", lambda self, learner, location: False)

    def build(*, onboarding=False):
        if not onboarding:
            monkeypatch.setattr(MainWindow, "_maybe_show_onboarding", lambda self: None)
        win = MainWindow(settings)
        qtbot.addWidget(win)
        return win

    return build


@pytest.fixture
def main_window(main_window_factory):
    return main_window_factory()
