"""Snapshot-Aufbau fuer die Wartezimmer-Anzeige.

Bewusst frei von Qt und Netzwerk: eine reine Funktion ueber (learners, current),
damit sich jeder Ablauf - Ueberspringen, Foto verwerfen, Person hinzufuegen,
Sprung zu einer spezifischen Person - direkt testen laesst.

Der Snapshot enthaelt **keine SchuelerIDs**: die Seite haengt oeffentlich im Gang.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

# Zustaende, die die Browser-Seite kennt.
STATE_IDLE = "idle"      # keine Klasse geladen -> neutrale Wartemeldung
STATE_RUNNING = "running"
STATE_DONE = "done"      # Klasse abgeschlossen


def format_name(vorname: str, nachname: str, full: bool = False) -> str:
    """'Anna Mueller' -> 'Anna M.' (bzw. voll, wenn *full*).

    Neu hinzugefuegte Personen koennen einen leeren Nachnamen haben; dann bleibt
    nur der Vorname stehen (kein einzelner Punkt)."""
    vorname = (vorname or "").strip()
    nachname = (nachname or "").strip()
    if not nachname:
        return vorname
    if not vorname:
        return nachname if full else f"{nachname[0]}."
    if full:
        return f"{vorname} {nachname}"
    return f"{vorname} {nachname[0]}."


def build_snapshot(
    *,
    learners: Sequence[Any],
    current: int,
    jump_return: Optional[int] = None,
    klasse: str = "",
    standort: str = "",
    has_roster: bool = True,
    class_finished: bool = False,
    count: int = 3,
    full_names: bool = False,
    hints: Optional[Sequence[str]] = None,
    hint_interval: int = 10,
    compact: bool = False,
) -> Dict[str, Any]:
    """Baut den Zustand, den die Anzeige zeigt.

    *jump_return* ist gesetzt, solange man per "Zu spezifischer Person springen"
    ausserhalb der Reihenfolge fotografiert. Die "als Naechstes"-Liste wird dann
    ab der Rueckkehrposition berechnet statt ab *current* - sonst wuerden die
    Leute draussen aufgerufen, die nach der vorgezogenen Person stehen, statt
    derer, die tatsaechlich als Naechstes dran sind.

    *hints* laufen rechts als Slideshow durch und haengen bewusst **nicht** am
    Zustand: sie sollen auch beim Warten und nach Klassenschluss lesbar bleiben.
    """
    total = len(learners)
    klasse = (klasse or "").strip()
    standort = (standort or "").strip()
    clean_hints = [h.strip() for h in (hints or []) if h and h.strip()]

    base: Dict[str, Any] = {
        "state": STATE_IDLE,
        "current": None,
        "upcoming": [],
        "klasse": klasse,
        "standort": standort,
        "done": 0,
        "total": total,
        "hints": clean_hints,
        "hint_interval": max(int(hint_interval), 1),
        "compact": bool(compact),
    }

    if not has_roster or not klasse or total == 0:
        return base

    current_learner = learners[current] if 0 <= current < total else None

    if class_finished or current_learner is None:
        base["state"] = STATE_DONE
        base["done"] = total
        return base

    start = jump_return if jump_return is not None else current
    upcoming: List[str] = []
    for i in range(max(start, 0), total):
        if i == current:
            continue
        upcoming.append(format_name(learners[i].vorname, learners[i].nachname, full_names))
        if len(upcoming) >= max(count, 0):
            break

    base["state"] = STATE_RUNNING
    base["current"] = format_name(
        current_learner.vorname, current_learner.nachname, full_names
    )
    base["upcoming"] = upcoming
    base["done"] = current
    return base
