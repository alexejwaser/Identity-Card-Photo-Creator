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


def _field(folie: Any, name: str, default: Any) -> Any:
    """Liest *name* aus einem Modell **oder** einem dict."""
    if isinstance(folie, dict):
        return folie.get(name, default)
    return getattr(folie, name, default)


def normalize_slide(folie: Any) -> Optional[Dict[str, Any]]:
    """Eine Folie in die Form, die die Seite erwartet - oder ``None``.

    Nimmt ein ``HinweisFolie``-Modell, ein dict oder (aus dem alten,
    zeilenbasierten Format) einen blossen String. Alles wird getrimmt, leere
    Aufzaehlungspunkte fallen weg, und eine Folie ohne jeden Inhalt liefert
    ``None`` - das ist der Nachfolger der frueheren "Leerzeilen fliegen raus"-
    Regel, die es beim Tippen im Einstellungsdialog braucht.
    """
    if isinstance(folie, str):
        folie = {"text": folie}
    titel = str(_field(folie, "titel", "") or "").strip()
    text = str(_field(folie, "text", "") or "").strip()
    punkte = [
        str(p or "").strip()
        for p in (_field(folie, "punkte", ()) or ())
        if str(p or "").strip()
    ]
    if not titel and not text and not punkte:
        return None
    return {"titel": titel, "text": text, "punkte": punkte}


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
    hints: Optional[Sequence[Any]] = None,
    hint_interval: int = 10,
    compact: bool = False,
) -> Dict[str, Any]:
    """Baut den Zustand, den die Anzeige zeigt.

    *jump_return* ist gesetzt, solange man per "Zu spezifischer Person springen"
    ausserhalb der Reihenfolge fotografiert. Die "als Naechstes"-Liste wird dann
    ab der Rueckkehrposition berechnet statt ab *current* - sonst wuerden die
    Leute draussen aufgerufen, die nach der vorgezogenen Person stehen, statt
    derer, die tatsaechlich als Naechstes dran sind.

    *hints* sind Folien (Titel / Fliesstext / Aufzaehlung, siehe
    ``normalize_slide``), die rechts als Slideshow durchlaufen. Sie haengen
    bewusst **nicht** am Zustand: sie sollen auch beim Warten und nach
    Klassenschluss lesbar bleiben.
    """
    total = len(learners)
    klasse = (klasse or "").strip()
    standort = (standort or "").strip()
    clean_hints = [
        slide for slide in (normalize_slide(h) for h in (hints or [])) if slide
    ]

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
