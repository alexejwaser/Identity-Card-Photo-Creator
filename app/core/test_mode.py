"""Testmodus: Platzhalter-Roster laden und die Ausgabe umlenken.

Warum es dieses Modul gibt (Issue #46): der Teil lag als ``_activate_test_mode``
im ``MainWindow``. Die eigentliche Zusage - die Umleitung gilt **nur fuer diese
Sitzung** und darf niemals in settings.json landen - war damit an eine
Qt-Widget-Klasse gebunden und ungetestet. Hier ist sie eine gewoehnliche
Funktion, und ``tests/test_test_mode.py`` wacht darueber.

Liegt bewusst in ``core/`` und nicht in ``core/config/``: ``config`` ist heute
ein Blatt, das alle importieren duerfen: eine Abhaengigkeit von ``core.excel``
wuerde das umdrehen. Der Import von ``generate_test_roster`` bleibt aus demselben
Grund wie bisher lokal in der Funktion (openpyxl kostet Startzeit).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

#: Alles, was der Testmodus anfasst, liegt unter diesem Ordner im Config-Verzeichnis.
TEST_DATA_DIRNAME = "Testdaten"
TEST_ROSTER_NAME = "Testroster.xlsx"


def activate_test_mode(settings, config_dir: Path) -> Path:
    """Erzeugt ein frisches Zufalls-Roster und liefert seinen Pfad.

    Die Ausgabepfade von *settings* zeigen danach unter ``Testdaten``. Es wird
    dabei **kein** ``settings.save()`` gerufen: Testaufnahmen sollen unter keinen
    Umstaenden im echten Ausgabeordner landen koennen, und ebenso wenig sollen
    die echten Pfade der Nutzerin ueberschrieben werden, nur weil jemand kurz den
    Testmodus ausprobiert hat. Wer hier etwas ergaenzt, darf das nicht brechen.
    """
    from .excel.test_data import generate_test_roster

    base = Path(config_dir) / TEST_DATA_DIRNAME
    roster_path = base / TEST_ROSTER_NAME
    generate_test_roster(roster_path, settings.excelMapping.model_dump())
    settings.ausgabeBasisPfad = base / "Ausgabe"
    settings.neueLernendeBasisPfad = base / "Neue Lernende"
    logger.info("Testmodus aktiviert, Ausgabe -> %s", settings.ausgabeBasisPfad)
    return roster_path
