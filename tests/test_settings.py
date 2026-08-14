"""Tests for configuration settings management."""

from pathlib import Path
import json
import pytest
from pydantic import ValidationError

from app.core.config.settings import (
    Settings,
    DEFAULTS,
    BildSettings,
    OverlaySettings,
    KameraSettings,
    ZipSettings,
    CopyrightSettings,
    ExcelMapping,
)


def test_load_creates_file_with_defaults(tmp_path):
    cfg = tmp_path / "settings.json"
    settings = Settings.load(cfg)
    assert cfg.exists()
    assert settings.bild.seitenverhaeltnis == (3, 4)
    assert settings.overlay.image is None


def test_save_and_load_roundtrip(tmp_path):
    cfg = tmp_path / "settings.json"
    s = Settings(
        ausgabeBasisPfad=tmp_path,
        missedPath=tmp_path / "missed.xlsx",
        bild=BildSettings(breite=800, hoehe=600, qualitaet=80, seitenverhaeltnis=(4, 3)),
        overlay=OverlaySettings(drittellinien=True, horizonte=False, deckkraft=0.3, image=None),
        kamera=KameraSettings(backend="opencv", liveviewFpsZiel=20, format="JPEG", timeoutMs=5000),
        zip=ZipSettings(maxAnzahl=None, maxGroesseMB=None),
        copyright=CopyrightSettings(artist="", copyright=""),
        excelMapping=ExcelMapping(**DEFAULTS["excelMapping"]),
    )
    s.save(cfg)
    loaded = Settings.load(cfg)
    assert loaded.bild.seitenverhaeltnis == (4, 3)
    assert loaded.ausgabeBasisPfad == tmp_path


def test_kamera_device_index_roundtrip(tmp_path):
    cfg = tmp_path / "settings.json"
    # Default value
    settings = Settings.load(cfg)
    assert settings.kamera.deviceIndex == 1
    # Change, save, reload
    settings.kamera.deviceIndex = 3
    settings.save(cfg)
    reloaded = Settings.load(cfg)
    assert reloaded.kamera.deviceIndex == 3


def test_overlay_path_validation(tmp_path):
    cfg = tmp_path / "settings.json"
    data = DEFAULTS.copy()
    data["overlay"] = data["overlay"].copy()
    data["overlay"]["image"] = str(tmp_path / "missing.png")
    cfg.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings.load(cfg)


def test_anzeige_hints_roundtrip(tmp_path):
    cfg = tmp_path / "settings.json"
    s = Settings.load(cfg)
    s.anzeige.hinweise = ["Erster Hinweis", "Zweiter Hinweis"]
    s.anzeige.hinweisIntervallSekunden = 25
    s.save(cfg)

    reloaded = Settings.load(cfg)
    assert reloaded.anzeige.hinweise == ["Erster Hinweis", "Zweiter Hinweis"]
    assert reloaded.anzeige.hinweisIntervallSekunden == 25


def test_anzeige_defaults_apply_to_an_older_settings_file(tmp_path):
    """Eine settings.json aus einer Version ohne Anzeige-Block muss weiterhin
    laden - sonst startet die App nach einem Update nicht mehr."""
    cfg = tmp_path / "settings.json"
    data = {k: v for k, v in DEFAULTS.items() if k != "anzeige"}
    cfg.write_text(json.dumps(data), encoding="utf-8")

    settings = Settings.load(cfg)
    assert settings.anzeige.port == 8080
    assert settings.anzeige.hinweise  # Standardhinweis vorhanden
