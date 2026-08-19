"""Wie aus einer SchuelerID ein Dateiname wird - und wann das schiefgeht.

Warum es dieses Modul gibt: das Foto einer Lernenden wird unter ihrer ID
abgelegt (``12345.jpg``), und genau dieser Dateiname ist spaeter die einzige
Verbindung zwischen Bild und Person. Der Name entsteht aber nicht aus der ID
selbst, sondern aus ``sanitize_name(id)`` - und diese Abbildung ist **nicht
eindeutig**:

    '12345'   -> '12345'
    '12345 '  -> '12345'      (Leerzeichen aus der Excel-Pflege)
    '12.345'  -> '12345'      (Punkt faellt weg)
    '12/345'  -> '12345'
    'ΑΒΓ'     -> ''           (nichts Verwertbares uebrig)

Fuenf verschiedene IDs, ein Dateiname. ``unique_file_path`` haengt dann
``_1``/``_2`` an, sodass nichts ueberschrieben wird - aber wer die ZIP-Datei
spaeter auspackt und den Dateinamen als ID liest, ordnet ``12345_1.jpg``
entweder niemandem oder der falschen Person zu. Das faellt niemandem auf: es
gibt keine Fehlermeldung, nur ein Gesicht auf dem falschen Ausweis.

Die bisherige Warnung suchte doppelte IDs im **Rohwert** und uebersah deshalb
genau die Faelle, in denen erst die Umwandlung die Kollision erzeugt. Hier wird
sie stattdessen in der Domaene gesucht, in der die Kollision wirklich
stattfindet: beim Dateinamen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from .util.paths import sanitize_name


def storage_key(schueler_id) -> str:
    """Der Dateiname-Stamm, unter dem ein Foto zu dieser ID wirklich landet.

    Bewusst dieselbe Umwandlung wie in ``unique_file_path`` - waeren es zwei
    getrennte Implementierungen, koennten sie auseinanderdriften und die
    Pruefung wuerde etwas anderes pruefen als das, was gespeichert wird.
    """
    return sanitize_name(str(schueler_id if schueler_id is not None else ""))


@dataclass(frozen=True)
class IdConflict:
    """Ein Dateiname, den sich mehrere Lernende teilen wuerden."""

    #: Der gemeinsame Dateiname-Stamm; leer = aus der ID bleibt nichts uebrig.
    key: str
    #: Die beteiligten Roh-IDs, in Roster-Reihenfolge, ohne Wiederholungen.
    ids: List[str]
    #: Wie viele Lernende betroffen sind (kann groesser als len(ids) sein,
    #: wenn dieselbe ID mehrfach im Roster steht).
    count: int

    @property
    def unusable(self) -> bool:
        """Aus der ID bleibt kein Dateiname uebrig (die Datei hiesse '.jpg')."""
        return not self.key


def find_id_conflicts(learners: Iterable) -> List[IdConflict]:
    """Alle Dateinamen-Kollisionen im Roster.

    *learners* sollte die **vollstaendige** Klasse sein, nicht die gefilterte
    Arbeitsliste: wer bereits fotografiert ist, taucht in der Arbeitsliste nicht
    mehr auf, seine Datei liegt aber laengst im Ausgabeordner und kollidiert
    trotzdem.

    Neue Lernende ("walk-in") bleiben aussen vor - sie werden nach Vor- und
    Nachname abgelegt, nicht nach ID, und spielen in dieser Domaene nicht mit.
    """
    groups: dict[str, List] = {}
    for learner in learners:
        if getattr(learner, "is_new", False):
            continue
        groups.setdefault(storage_key(learner.schueler_id), []).append(learner)

    conflicts = []
    for key, group in groups.items():
        if len(group) > 1 or not key:
            seen, ids = set(), []
            for learner in group:
                raw = str(learner.schueler_id)
                if raw not in seen:
                    seen.add(raw)
                    ids.append(raw)
            conflicts.append(IdConflict(key=key, ids=ids, count=len(group)))
    return conflicts


def conflict_for(learner, conflicts: Sequence[IdConflict]) -> Optional[IdConflict]:
    """Der Konflikt, der *learner* betrifft - oder None, wenn alles sauber ist."""
    if getattr(learner, "is_new", False):
        return None
    key = storage_key(learner.schueler_id)
    for conflict in conflicts:
        if conflict.key == key:
            return conflict
    return None
