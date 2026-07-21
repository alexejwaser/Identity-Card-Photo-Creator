# app/core/config/settings.py
"""Configuration management using Pydantic models."""

from pathlib import Path
import json
import os
import sys
from typing import Tuple, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ---------------------------------------------------------------------------
# Storage locations
# ---------------------------------------------------------------------------

def _app_base_dir() -> Path:
    """Directory containing the running .exe (frozen build), or this file's
    project root when running from source."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]


def _resolve_config_dir() -> Path:
    """Resolve where settings.json (and related config files) live.

    Priority:
    1. LEGICCARD_CONFIG_DIR environment variable, if set.
    2. Portable mode: a 'config' folder placed next to the .exe by the
       operator (e.g. on a shared/USB drive so settings travel with the app).
    3. Default: %APPDATA%\\LegicCardCreator (falls back to the home
       directory on non-Windows platforms).
    """
    env_override = os.getenv("LEGICCARD_CONFIG_DIR")
    if env_override:
        return Path(env_override)
    if getattr(sys, 'frozen', False):
        portable_dir = _app_base_dir() / "config"
        if portable_dir.is_dir():
            return portable_dir
    return Path(os.getenv("APPDATA", str(Path.home()))) / "LegicCardCreator"


CONFIG_DIR = _resolve_config_dir()
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "settings.json"


def _default_output_path() -> Path:
    """Return an absolute default output path anchored to the user's Pictures folder."""
    return Path(os.getenv("USERPROFILE", str(Path.home()))) / "Pictures" / "LegicCardCreator"


def _default_new_learner_path() -> Path:
    """Return the default folder for walk-in students not on the roster."""
    return _default_output_path() / "Neue Lernende"


# ---------------------------------------------------------------------------
# First-run defaults (used when settings.json does not yet exist)
# ---------------------------------------------------------------------------

DEFAULTS = {
    'ausgabeBasisPfad': str(_default_output_path()),
    'neueLernendeBasisPfad': str(_default_new_learner_path()),
    'missedPath': str(CONFIG_DIR / 'Verpasste_Termine.xlsx'),
    'bild': {
        'breite': 1200,
        'hoehe': 1600,
        'qualitaet': 90,
        'seitenverhaeltnis': '3:4',
    },
    'overlay': {
        'drittellinien': True,
        'horizonte': False,
        'deckkraft': 0.3,
        'image': '',
    },
    'kamera': {
        'backend': 'opencv',
        'liveviewFpsZiel': 20,
        'format': 'JPEG',
        'timeoutMs': 5000,
        'rotation': 270,
        'deviceIndex': 1,
    },
    'zip': {'maxAnzahl': None, 'maxGroesseMB': None},
    'copyright': {'artist': '', 'copyright': ''},
    'excelMapping': {
        'klasse': 'A',
        'nachname': 'B',
        'vorname': 'C',
        'schuelerId': 'D',
        'fotografiert': 'E',
        'aufnahmedatum': 'F',
        'grund': 'G',
    },
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BildSettings(BaseModel):
    breite: int
    hoehe: int
    qualitaet: int
    seitenverhaeltnis: Tuple[int, int] = (3, 4)

    @field_validator('seitenverhaeltnis', mode='before')
    @classmethod
    def parse_ratio(cls, v):
        if isinstance(v, str) and ':' in v:
            a, b = v.split(':', 1)
            if a.isdigit() and b.isdigit():
                return int(a), int(b)
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return int(v[0]), int(v[1])
        raise ValueError('Invalid ratio format')


class OverlaySettings(BaseModel):
    drittellinien: bool = True
    horizonte: bool = False
    deckkraft: float = 0.3
    image: Optional[Path] = Field(default=None)

    @field_validator('image', mode='before')
    @classmethod
    def check_image(cls, v):
        if not v:
            return None
        p = Path(v)
        if not p.exists():
            raise ValueError(f'Overlay image not found: {v}')
        return p


class KameraSettings(BaseModel):
    backend: str = 'opencv'
    liveviewFpsZiel: int = 20
    format: str = 'JPEG'
    timeoutMs: int = 5000
    # Drehung in Grad im Uhrzeigersinn. 270 (= 90° CCW) ist der richtige
    # Wert für die Canon EOS M50 im Webcam-Modus, da der Sensor im
    # Querformat ausgibt aber ein Hochformat benötigt wird.
    rotation: int = 270
    # Index des Kamera-Geräts (cv2.VideoCapture). Standard 1, da Index 0
    # meist die eingebaute Laptop-Webcam ist, nicht die gewünschte externe.
    deviceIndex: int = 1


class ZipSettings(BaseModel):
    maxAnzahl: Optional[int] = None
    # maxGroesseMB: reserviert für zukünftige grössenbasierte ZIP-Aufteilung
    maxGroesseMB: Optional[int] = None


class CopyrightSettings(BaseModel):
    # Hinweis: Diese Felder werden aktuell nicht in EXIF-Metadaten geschrieben.
    # Implementierung ausstehend.
    artist: str = ''
    copyright: str = ''


class ExcelMapping(BaseModel):
    klasse: str = 'A'
    nachname: str = 'B'
    vorname: str = 'C'
    schuelerId: str = 'D'
    fotografiert: str = 'E'
    aufnahmedatum: str = 'F'
    grund: str = 'G'


class Settings(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    ausgabeBasisPfad: Path = Field(default_factory=_default_output_path)
    neueLernendeBasisPfad: Path = Field(default_factory=_default_new_learner_path)
    missedPath: Path = Field(default_factory=lambda: CONFIG_DIR / 'Verpasste_Termine.xlsx')
    bild: BildSettings = Field(default_factory=BildSettings)
    overlay: OverlaySettings = Field(default_factory=OverlaySettings)
    kamera: KameraSettings = Field(default_factory=KameraSettings)
    zip: ZipSettings = Field(default_factory=ZipSettings)
    copyright: CopyrightSettings = Field(default_factory=CopyrightSettings)
    excelMapping: ExcelMapping = Field(default_factory=ExcelMapping)

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> 'Settings':
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
        else:
            data = DEFAULTS
            path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        return cls.model_validate(data)

    def save(self, path: Path = CONFIG_PATH) -> None:
        data = self.model_dump()
        data['ausgabeBasisPfad'] = str(data['ausgabeBasisPfad'])
        data['neueLernendeBasisPfad'] = str(data['neueLernendeBasisPfad'])
        data['missedPath'] = str(data['missedPath'])
        ratio = data['bild']['seitenverhaeltnis']
        data['bild']['seitenverhaeltnis'] = f"{ratio[0]}:{ratio[1]}"
        img = data['overlay'].get('image')
        data['overlay']['image'] = str(img) if img else ''
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')
