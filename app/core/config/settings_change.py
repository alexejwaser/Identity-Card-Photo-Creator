"""Was sich am Einstellungsdialog geaendert hat - als reine Rechnung.

Warum es dieses Modul gibt (Issue #46): ``MainWindow.open_settings()`` hat sieben
Einstellungswerte vor dem Dialog abgehaengt und danach fuenf Entscheidungen
gefaellt (Kamera-Neustart, Zuschnitt, Overlay, Anzeige-Endpunkt, Testmodus).
Diese Vergleichslogik steckte in einer Qt-Widget-Klasse, die sich ohne
QApplication nicht bauen laesst - entsprechend deckte sie kein Test ab.

Das Muster ist das von ``DisplayController.restart_if_endpoint_changed`` aus #43:
das Fenster holt vor dem Dialog einen Token und reicht ihn danach zurueck. Die
Form ist bewusst die von ``app/core/display/state.py`` - eine **reine Funktion**,
kein ``QObject`` mit Signalen. Ein Vorher/Nachher-Vergleich ist eine Rechnung und
kein Lebenszyklus: es gibt genau einen Aufrufer, der synchron auf die Antwort
wartet. Als Funktion haengt die Korrektheit an keiner Verbindungsreihenfolge, es
kommt kein Qt in diesen Teil des Kerns, und ein Test prueft die Entscheidung
direkt, statt "ein Signal ist geflogen".

Alle Entscheidungen werden **vor** der ersten Nebenwirkung berechnet. Das ist
kein Stil, sondern noetig: ``MainController.restart_camera()`` kann ueber den
Fallback in ``_init_camera`` den ``deviceIndex`` in die Einstellungen
zurueckschreiben, und der Testmodus biegt die Ausgabepfade um. Wer waehrend des
Anwendens erneut vergleicht, vergleicht gegen bereits veraenderte Werte.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class SettingsSnapshot:
    """Die Werte, die *vor* dem Dialog galten.

    Bewusst kopierte Einzelwerte und kein Verweis auf ``settings.kamera``: der
    Dialog veraendert dasselbe ``Settings``-Objekt an Ort und Stelle (es wird per
    Referenz geteilt, genau wie bei der Anzeige). Haette der Schnappschuss das
    Untermodell festgehalten, verglichen wir es am Ende mit sich selbst und ein
    Kamerawechsel bliebe fuer immer unbemerkt.
    """

    backend: str = ""
    rotation: int = 0
    device_index: int = 0
    breite: int = 0
    hoehe: int = 0
    overlay_image: Optional[Path] = None
    #: Undurchsichtig; gehoert dem DisplayController. Hier reist er nur mit,
    #: damit das Fenster einen einzigen Token traegt.
    display: Tuple[int, str] = (0, "")

    @classmethod
    def capture(cls, settings, display_endpoint: Tuple[int, str]) -> "SettingsSnapshot":
        return cls(
            backend=settings.kamera.backend,
            rotation=settings.kamera.rotation,
            device_index=settings.kamera.deviceIndex,
            breite=settings.bild.breite,
            hoehe=settings.bild.hoehe,
            overlay_image=settings.overlay.image,
            display=display_endpoint,
        )


@dataclass(frozen=True)
class SettingsChange:
    """Was daraufhin zu tun ist. Das *Wie* steht im ``MainWindow``."""

    camera_restart: bool = False
    crop_changed: bool = False
    overlay_changed: bool = False
    test_mode: bool = False


def diff_settings(
    before: SettingsSnapshot,
    settings,
    *,
    accepted: bool,
    reconnect_requested: bool = False,
    test_mode_requested: bool = False,
) -> SettingsChange:
    """Vergleicht *settings* mit *before*. Veraendert nichts.

    Zur Rolle von *accepted*: Kamera und Zuschnitt zaehlen **auch nach
    Abbrechen**. Das ist kein Versehen und keine offene Baustelle, sondern
    bestehendes Verhalten: der Dialog kann ueber "Als Standard speichern"
    Einstellungen mitten im Dialog festschreiben, sie sind dann bereits
    geaendert, egal wie die Nutzerin ihn verlaesst. Overlay und Testmodus
    dagegen gelten nur bei Zustimmung. Diese Asymmetrie bitte nicht
    "aufraeumen".
    """
    camera_restart = (
        settings.kamera.backend != before.backend
        or settings.kamera.rotation != before.rotation
        or settings.kamera.deviceIndex != before.device_index
        or reconnect_requested
    )
    crop_changed = (
        settings.bild.breite != before.breite or settings.bild.hoehe != before.hoehe
    )
    overlay_changed = accepted and settings.overlay.image != before.overlay_image
    return SettingsChange(
        camera_restart=camera_restart,
        crop_changed=crop_changed,
        overlay_changed=overlay_changed,
        test_mode=accepted and test_mode_requested,
    )
