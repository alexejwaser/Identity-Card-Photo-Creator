# Identity Card Photo Creator

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)

Desktop-App zur schnellen Erstellung von Portraitfotos für Klassen und Gruppen, inklusive Excel-Abgleich und automatischer ZIP-Erstellung.

## Features
- Excel-Roster als Datenquelle (Standort/Klasse/Lernende), automatischer Abgleich beim Fotografieren
- Live-Vorschau mit konfigurierbarem Overlay und Kamera-Rotation
- Automatische ZIP-Bündelung der Fotos pro Klasse
- Unterstützung für USB-Webcam (OpenCV), DSLR via `gphoto2`, oder Simulator-Modus (kein Kamera-Hardware nötig)

## Installation

Voraussetzung: Python 3.10+.

**Windows (PowerShell):**
```powershell
git clone https://github.com/alexejwaser/Identity-Card-Photo-Creator.git
cd Identity-Card-Photo-Creator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
git clone https://github.com/alexejwaser/Identity-Card-Photo-Creator.git
cd Identity-Card-Photo-Creator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Die virtuelle Umgebung landet in `.venv/` im Projektordner (via `.gitignore` ausgeschlossen). Bei jedem neuen Terminal muss sie vor dem Start erneut aktiviert werden (`.venv\Scripts\activate` bzw. `source .venv/bin/activate`).

> Kamera-Hinweis: Auf macOS gibt es i. d. R. keine kompatible USB-Webcam wie am Windows-Zielsystem. Zum Testen ohne Kamera in den Einstellungen (⚙️) den Kamera-Modus auf **Simulator** stellen – dann werden Platzhalterbilder statt echter Fotos gespeichert.

## Nutzung
```bash
python -m app.main
```
Beim Abschluss einer Klasse werden alle Fotos automatisch zu einem ZIP-Archiv zusammengefasst und der Zielordner geöffnet.

## Tastenkürzel
| Taste | Aktion |
|---|---|
| ␠ Leertaste | Foto aufnehmen / im Review-Dialog übernehmen |
| ⎋ Esc | Aufnahme verwerfen, erneut fotografieren |
| S | Lernende(n) überspringen |
| A | Person hinzufügen |
| F | Klasse abschließen |
| C | Kamera wechseln |

## Tests
```bash
pytest
```

## Windows-EXE bauen (GitHub Actions)
Der Workflow **Build Windows release** (`.github/workflows/build-exe.yml`) baut automatisch eine Windows-Exe.

Auslöser:
- **Versions-Tag pushen**, z. B.:
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```
- oder **manuell**: Tab **Actions** → **Build Windows release** → **Run workflow**.

Nach Abschluss unter **Artifacts** das Archiv **LegicCardCreator-windows** herunterladen; darin liegt der fertige `LegicCardCreator`-Ordner mit der `.exe`.

## Lizenz
[MIT](LICENSE)
