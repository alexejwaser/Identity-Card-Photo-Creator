"""Lebenszyklus der Wartezimmer-Anzeige - Server + 1-Hz-Takt an einem Ort.

Warum es diese Klasse gibt (Issue #43): Start, Stopp, Neustart bei geaenderter
Adresse und das periodische Veroeffentlichen lagen bisher als lose Methoden im
``MainWindow``. Damit hing die Korrektheit der Anzeige an einer Qt-Widget-Klasse,
die sich ohne QApplication weder bauen noch testen laesst. Hier steckt nur noch
der Zustandsautomat: ein ``QObject`` mit Signalen, dem das ``MainWindow`` zuhoert
und der *keine* Widgets kennt. Saemtliche Texte fuer die Nutzerin bleiben drueben
in der GUI - hier wird nur geloggt.

Der 1-Hz-Timer ist kein Komfort, sondern das Sicherheitsnetz aus CLAUDE.md:
er veroeffentlicht den Zustand unabhaengig davon, welcher Codepfad ihn geaendert
hat. Ein neu hinzugekommener Mutationspfad ist damit gratis abgedeckt - sonst
haengt draussen im Gang irgendwann still ein falscher Name.

Der Controller startet **nie** von selbst: die Anzeige geht ausschliesslich per
Knopfdruck an, weil sie einen Port oeffnet (und unter Windows die Firewall
fragt). Wer ``MainController`` baut, bekommt also ein schlafendes Objekt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

from PySide6 import QtCore

from .server import DisplayServer
from .state import build_snapshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisplayContext:
    """Der Teil des GUI-Zustands, den die Momentaufnahme braucht.

    Bewusst ein passiver Wertetyp und kein Verweis auf das Fenster: der
    Controller soll nichts ueber Widgets wissen. Das ``MainWindow`` baut ihn bei
    jedem Tick frisch - Klasse und Standort stehen dort in Comboboxen, die
    niemand sonst zuverlaessig ablesen kann.
    """

    learners: Sequence[Any] = ()
    current: int = 0
    jump_return: Optional[int] = None
    klasse: str = ""
    standort: str = ""
    has_roster: bool = False
    class_finished: bool = False


class DisplayController(QtCore.QObject):
    """Besitzt ``DisplayServer`` und den Veroeffentlichungs-Timer."""

    #: (local_mode, urls) - erst nach dem ersten erfolgreichen Publish.
    started = QtCore.Signal(bool, list)
    #: Immer nach ``stop()``, auch wenn gar nichts lief.
    stopped = QtCore.Signal()
    #: (port, str(exc)) - Port belegt; die GUI formuliert die Meldung.
    failed = QtCore.Signal(int, str)

    PUBLISH_INTERVAL_MS = 1000

    def __init__(self, settings, logger=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        # Der Parametername verdeckt den Modul-Logger, daher hier neu geholt.
        self.logger = logger or logging.getLogger(__name__)
        # Fester Kindname statt eines vom uebergebenen Logger abgeleiteten:
        # in logs/app.log soll die Server-Zeile weiter unter "DisplayServer"
        # stehen, egal wer den Controller gebaut hat.
        self._server = DisplayServer(self.logger.getChild("DisplayServer"))
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.PUBLISH_INTERVAL_MS)
        self._timer.timeout.connect(self.publish)
        self._context_provider: Optional[Callable[[], DisplayContext]] = None

    # context ----------------------------------------------------------------
    def set_context_provider(self, provider: Callable[[], DisplayContext]) -> None:
        """Hinterlegt die Funktion, die den aktuellen GUI-Zustand liefert."""
        self._context_provider = provider

    # lifecycle --------------------------------------------------------------
    def toggle(self) -> bool:
        """Schaltet um und liefert den Zustand *danach* (True = laeuft)."""
        if self.running:
            self.stop()
            return False
        return self.start()

    def start(self) -> bool:
        """Startet Server und Timer; liefert False bei belegtem Port."""
        if self._server.running:
            return True
        port = self.settings.anzeige.port
        local = self.settings.anzeige.modus == "lokal"
        host = DisplayServer.LOCAL_HOST if local else DisplayServer.NETWORK_HOST
        try:
            self._server.start(port, host=host)
        except OSError as exc:
            self.failed.emit(port, str(exc))
            return False
        # Reihenfolge ist wichtig: erst den Zustand hineinschieben, dann den
        # Takt anwerfen, und erst danach melden. Wer auf ``started`` reagiert,
        # oeffnet den Browser - der darf keine leere Seite vorfinden.
        self.publish()
        self._timer.start()
        self.started.emit(local, self.urls())
        return True

    def stop(self) -> None:
        """Haelt Timer und Server an - bedingungslos.

        ``stopped`` wird auch dann gemeldet, wenn nichts lief: die GUI setzt
        daran ihre Knopf- und Label-Zustaende zurueck, und ``DisplayServer.stop()``
        ist im Ruhezustand ohnehin ein No-op.
        """
        self._timer.stop()
        self._server.stop()
        self.stopped.emit()

    # content ----------------------------------------------------------------
    def publish(self) -> None:
        """Schiebt den aktuellen Zustand an die Anzeige.

        Laeuft immer auf dem GUI-Thread (aus der GUI oder dem 1-Hz-Timer); der
        Server serialisiert intern gegen seine Handler-Threads.

        Fehler werden hier geloggt statt im Qt-Slot zu verpuffen - auch die des
        Providers, der ja im Fenster lebt und stolpern kann: bliebe eine Ausnahme
        unsichtbar, stuende die Anzeige draussen still, ohne dass irgendwo eine
        Spur davon landet.
        """
        if not self._server.running:
            return
        if self._context_provider is None:
            return
        anzeige = self.settings.anzeige
        try:
            ctx = self._context_provider()
            self._server.publish(
                build_snapshot(
                    learners=ctx.learners,
                    current=ctx.current,
                    jump_return=ctx.jump_return,
                    klasse=ctx.klasse,
                    standort=ctx.standort,
                    has_roster=ctx.has_roster,
                    class_finished=ctx.class_finished,
                    count=anzeige.anzahlNaechste,
                    full_names=anzeige.vollstaendigeNamen,
                    hints=anzeige.hinweise,
                    hint_interval=anzeige.hinweisIntervallSekunden,
                    compact=anzeige.kompakt,
                )
            )
        except Exception:
            self.logger.exception("Anzeige-Zustand konnte nicht veröffentlicht werden")

    # settings ---------------------------------------------------------------
    def endpoint(self) -> Tuple[int, str]:
        """Die Einstellungen, die den Socket bestimmen (Port und Modus)."""
        return (self.settings.anzeige.port, self.settings.anzeige.modus)

    def restart_if_endpoint_changed(self, before: Tuple[int, str]) -> None:
        """Startet neu, falls sich Port oder Modus seit *before* geaendert haben.

        Beides greift nur ueber einen neuen Socket; Namensform, Anzahl und
        Hinweise holt der 1-Hz-Timer von selbst nach.
        """
        if self.running and self.endpoint() != before:
            self.stop()
            self.start()

    # server delegation ------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._server.running

    @property
    def port(self) -> int:
        return self._server.port

    @property
    def local_only(self) -> bool:
        return self._server.local_only

    def urls(self) -> List[str]:
        return self._server.urls()
