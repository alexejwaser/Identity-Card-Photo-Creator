"""Die Einmal-Entscheidung hinter der Kurzanleitung.

Warum es dieses Modul gibt (Issue #46): ob das Onboarding erscheint, hing an
einer Methode des ``MainWindow`` und war damit faktisch ungetestet - das
``main_window``-Fixture patcht sie fuer alle GUI-Tests weg, weil der modale
Dialog sonst die Fensterkonstruktion blockiert. Uebrig bleibt hier nur der
Marker: eine leere Datei im Konfigurationsverzeichnis, deren blosse Existenz
"schon gesehen" bedeutet.

Bewusst ohne Qt und ohne Dialogwissen. Der Dialog selbst bleibt in der GUI -
hier steht nur, *ob* er drankommt.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

#: Leere Markierungsdatei neben settings.json. Der Name beginnt mit einem Punkt,
#: damit sie im Konfigurationsordner nicht als Nutzerdatei missverstanden wird.
MARKER_NAME = ".onboarded"


def marker_path(config_dir: Path) -> Path:
    return Path(config_dir) / MARKER_NAME


def should_show(config_dir: Path) -> bool:
    """Ob die Kurzanleitung beim Start erscheinen soll (einmal, fuer immer)."""
    return not marker_path(config_dir).exists()


def mark_shown(config_dir: Path) -> bool:
    """Setzt den Marker; liefert False, wenn das nicht ging.

    Der Rueckgabewert ist die einzige Neuerung gegenueber dem alten Code im
    Fenster - er macht den Fehlerfall pruefbar, ohne ihn zu veraendern. Ein
    ``OSError`` (z.B. schreibgeschuetztes Konfigurationsverzeichnis im
    portablen Betrieb) wird weiterhin geschluckt: die Kurzanleitung erscheint
    dann beim naechsten Start erneut, was deutlich harmloser ist als ein
    Absturz direkt nach dem Willkommensdialog.
    """
    try:
        marker_path(config_dir).touch()
    except OSError as exc:
        logger.warning("Onboarding-Marker konnte nicht gesetzt werden: %s", exc)
        return False
    return True
