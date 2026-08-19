"""Gleicht die abgelegten Fotos gegen die Excel-Liste ab. Aendert nichts.

Warum das trotz gruener Tests noch gebraucht wird: der Fehler, um den es hier
geht, ist unsichtbar. Landet ein Foto unter der ID einer anderen Person, gibt es
keine Meldung und keinen Absturz - ein Fototag laeuft voellig unauffaellig ab und
faellt erst auf, wenn Wochen spaeter ein falsches Gesicht auf einem Ausweis
klebt. "Hat gut funktioniert" ist deshalb kein Nachweis; ein Abgleich schon.

Geprueft wird genau das, was die App zusagt:

* Zu jeder in Excel als fotografiert markierten Person gibt es eine Datei.
* Jede Datei laesst sich genau einer Person zuordnen.
* Es gibt keine ``_1``-Dateien mehr, ausser jemand hat sie bewusst gewaehlt.
* Es liegt nichts im Ordner, das zu niemandem gehoert.

Aufruf (Windows, aus dem Projektordner):

    .venv\\Scripts\\python.exe tools\\check_output.py "C:\\Pfad\\roster.xlsx" "C:\\Pfad\\Ausgabe"

Der zweite Pfad ist ``ausgabeBasisPfad`` aus settings.json. Rueckgabe 0 = sauber,
1 = es gibt etwas anzusehen.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config.settings import Settings, CONFIG_PATH  # noqa: E402
from app.core.excel.reader import ExcelReader  # noqa: E402
from app.core.identity import storage_key  # noqa: E402
from app.core.util.paths import sanitize_name  # noqa: E402


def mapping() -> dict:
    """Die Spaltenzuordnung aus der echten settings.json, nicht geraten."""
    if CONFIG_PATH.exists():
        return Settings.load().excelMapping.model_dump()
    return {
        "klasse": "A", "nachname": "B", "vorname": "C", "schuelerId": "D",
        "fotografiert": "E", "aufnahmedatum": "F", "grund": "G",
    }


def pruefe(roster: Path, ausgabe: Path) -> int:
    reader = ExcelReader(roster, mapping())
    befunde: list[str] = []
    geprueft = 0

    for standort in reader.locations():
        for klasse in reader.classes_for_location(standort):
            ordner = ausgabe / sanitize_name(standort) / sanitize_name(klasse)
            if not ordner.is_dir():
                continue
            lernende = reader.learners(standort, klasse)
            dateien = {p.name: p for p in ordner.glob("*.jpg")}

            # Erwartete Datei je Person, ueber denselben Schluessel wie die App.
            nach_schluessel: dict[str, list] = {}
            for lernende_r in lernende:
                nach_schluessel.setdefault(storage_key(lernende_r.schueler_id), []).append(lernende_r)

            for schluessel, gruppe in nach_schluessel.items():
                geprueft += 1
                name = f"{schluessel}.jpg"
                fotografiert = [l for l in gruppe if l.photographed]
                if not schluessel:
                    befunde.append(
                        f"[{standort}/{klasse}] ID {gruppe[0].schueler_id!r} ergibt keinen "
                        f"Dateinamen - das Foto waere nicht ablegbar."
                    )
                    continue
                if len(gruppe) > 1:
                    ids = ", ".join(sorted({str(l.schueler_id) for l in gruppe}))
                    befunde.append(
                        f"[{standort}/{klasse}] {name} ist fuer mehrere Personen "
                        f"zustaendig (IDs {ids}) - die Zuordnung ist nicht eindeutig."
                    )
                if fotografiert and name not in dateien:
                    wer = ", ".join(f"{l.vorname} {l.nachname}" for l in fotografiert)
                    befunde.append(
                        f"[{standort}/{klasse}] {wer} ist in Excel als fotografiert "
                        f"markiert, aber {name} fehlt."
                    )
                if not fotografiert and name in dateien:
                    befunde.append(
                        f"[{standort}/{klasse}] {name} liegt im Ordner, in Excel ist "
                        f"aber niemand mit dieser ID als fotografiert markiert."
                    )

            erwartet = {f"{s}.jpg" for s in nach_schluessel if s}
            for dateiname in sorted(dateien):
                if dateiname in erwartet:
                    continue
                stamm = Path(dateiname).stem
                if "_" in stamm and f"{stamm.rsplit('_', 1)[0]}.jpg" in erwartet:
                    befunde.append(
                        f"[{standort}/{klasse}] {dateiname} ist eine Zweitdatei - der Name "
                        f"ist keine SchuelerID und laesst sich niemandem zuordnen. "
                        f"Bewusst so gewaehlt?"
                    )
                else:
                    befunde.append(
                        f"[{standort}/{klasse}] {dateiname} gehoert zu niemandem in dieser Klasse."
                    )

    print(f"{geprueft} Personen gegen {ausgabe} geprueft.")
    if not befunde:
        print("Keine Auffaelligkeiten: jede Datei gehoert genau einer Person.")
        return 0
    print(f"\n{len(befunde)} Punkt(e) zum Ansehen:\n")
    for zeile in befunde:
        print(f"  - {zeile}")
    return 1


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    roster, ausgabe = Path(sys.argv[1]), Path(sys.argv[2])
    if not roster.is_file():
        print(f"Excel-Datei nicht gefunden: {roster}")
        return 2
    if not ausgabe.is_dir():
        print(f"Ausgabeordner nicht gefunden: {ausgabe}")
        return 2
    return pruefe(roster, ausgabe)


if __name__ == "__main__":
    raise SystemExit(main())
