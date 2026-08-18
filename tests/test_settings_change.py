"""Die Vorher/Nachher-Rechnung um den Einstellungsdialog (Issue #46).

Kein Qt, kein qtbot, kein Dialog: ``diff_settings`` ist eine reine Funktion,
also wird sie auch rein geprueft - echte ``Settings`` hinein (das gemeinsame
Fixture aus conftest.py), ein ``SettingsChange`` heraus. Nichts ist
weggemockt; ein Mock waere hier auch nur eine zweite, schlechtere Kopie der
Datenklasse.

Zwei Regeln in diesem Modul sehen aus wie Schlampigkeit und sind es nicht:
Kamera- und Zuschnittsaenderungen zaehlen **auch nach Abbrechen** (der Dialog
kann ueber "Als Standard speichern" mitten drin festschreiben), Overlay und
Testmodus dagegen nur bei Zustimmung. Wer diese Asymmetrie "aufraeumt", soll
hier rot werden.
"""
from pathlib import Path

from app.core.config.settings_change import (
    SettingsChange,
    SettingsSnapshot,
    diff_settings,
)


# --- Hilfen ----------------------------------------------------------------

def snapshot(settings, display=(8080, "netzwerk")):
    """Der Token, den ``open_settings`` vor dem Dialog zieht."""
    return SettingsSnapshot.capture(settings, display)


def real_image(tmp_path, name="overlay.png"):
    """Ein existierender Pfad - ``OverlaySettings.image`` validiert die
    Existenz und weist alles andere zurueck."""
    p = tmp_path / name
    p.write_bytes(b"nicht wirklich ein PNG, aber vorhanden")
    return p


# --- Nichts geaendert ------------------------------------------------------

def test_an_untouched_cancelled_dialog_changes_nothing(settings):
    change = diff_settings(snapshot(settings), settings, accepted=False)
    assert change == SettingsChange()
    assert change.camera_restart is False
    assert change.crop_changed is False
    assert change.overlay_changed is False
    assert change.test_mode is False


def test_an_untouched_accepted_dialog_changes_nothing(settings):
    change = diff_settings(snapshot(settings), settings, accepted=True)
    assert change == SettingsChange()


# --- Kamera ----------------------------------------------------------------

def test_a_changed_backend_requires_a_camera_restart(settings):
    before = snapshot(settings)
    settings.kamera.backend = "simulator"
    assert diff_settings(before, settings, accepted=True).camera_restart is True


def test_a_changed_rotation_requires_a_camera_restart(settings):
    before = snapshot(settings)
    settings.kamera.rotation = settings.kamera.rotation + 90
    assert diff_settings(before, settings, accepted=True).camera_restart is True


def test_a_changed_device_index_requires_a_camera_restart(settings):
    before = snapshot(settings)
    settings.kamera.deviceIndex = settings.kamera.deviceIndex + 1
    assert diff_settings(before, settings, accepted=True).camera_restart is True


def test_a_reconnect_request_alone_requires_a_camera_restart(settings):
    """Der Knopf "Neu verbinden" aendert keinen einzigen Wert - ohne dieses
    Flag bliebe ein haengendes Geraet einfach haengen."""
    change = diff_settings(
        snapshot(settings), settings, accepted=False, reconnect_requested=True
    )
    assert change.camera_restart is True
    assert change.crop_changed is False


def test_saving_as_default_mid_dialog_makes_a_camera_change_count_after_cancel(settings):
    """Der Dialog schreibt ueber "Als Standard speichern" sofort fest.

    Danach ist die Kamera bereits umgestellt, egal ob die Nutzerin den Dialog
    mit Abbrechen verlaesst. Wer das an ``accepted`` haengt, laesst die App mit
    einer Einstellung weiterlaufen, die zur laufenden Kamera nicht mehr passt.
    """
    before = snapshot(settings)
    settings.kamera.deviceIndex = 3
    assert diff_settings(before, settings, accepted=False).camera_restart is True


# --- Zuschnitt -------------------------------------------------------------

def test_a_changed_width_is_a_crop_change(settings):
    before = snapshot(settings)
    settings.bild.breite = settings.bild.breite + 10
    assert diff_settings(before, settings, accepted=True).crop_changed is True


def test_a_changed_height_is_a_crop_change(settings):
    before = snapshot(settings)
    settings.bild.hoehe = settings.bild.hoehe + 10
    assert diff_settings(before, settings, accepted=True).crop_changed is True


def test_a_crop_change_counts_after_cancel(settings):
    # Gleiche Begruendung wie bei der Kamera: das Seitenverhaeltnis der
    # Vorschau muss zu den tatsaechlich gespeicherten Werten passen.
    before = snapshot(settings)
    settings.bild.breite = settings.bild.breite + 10
    assert diff_settings(before, settings, accepted=False).crop_changed is True


# --- Overlay ---------------------------------------------------------------

def test_a_new_overlay_image_counts_when_accepted(settings, tmp_path):
    before = snapshot(settings)
    settings.overlay.image = real_image(tmp_path)
    assert diff_settings(before, settings, accepted=True).overlay_changed is True


def test_a_new_overlay_image_is_ignored_after_cancel(settings, tmp_path):
    """Anders als Kamera und Zuschnitt: das Overlay wird erst beim OK
    uebernommen, ein Abbrechen verwirft die Auswahl."""
    before = snapshot(settings)
    settings.overlay.image = real_image(tmp_path)
    assert diff_settings(before, settings, accepted=False).overlay_changed is False


def test_a_removed_overlay_image_counts_when_accepted(settings, tmp_path):
    settings.overlay.image = real_image(tmp_path)
    before = snapshot(settings)
    settings.overlay.image = None
    assert diff_settings(before, settings, accepted=True).overlay_changed is True


# --- Testmodus -------------------------------------------------------------

def test_test_mode_needs_both_acceptance_and_request(settings):
    before = snapshot(settings)
    assert diff_settings(
        before, settings, accepted=True, test_mode_requested=True
    ).test_mode is True


def test_a_requested_test_mode_is_dropped_after_cancel(settings):
    before = snapshot(settings)
    assert diff_settings(
        before, settings, accepted=False, test_mode_requested=True
    ).test_mode is False


def test_acceptance_alone_does_not_start_test_mode(settings):
    before = snapshot(settings)
    assert diff_settings(before, settings, accepted=True).test_mode is False


# --- Der Schnappschuss haengt nicht am Modell ------------------------------

def test_the_snapshot_copies_values_instead_of_referencing_the_submodel(settings):
    """Der einzige Test, der ein aliasing im Schnappschuss faengt.

    ``settings`` wird per Referenz geteilt, der Dialog aendert dasselbe Objekt.
    Haelte ``capture()`` ``settings.kamera`` fest statt der Einzelwerte,
    verglichen wir am Ende das Untermodell mit sich selbst - jeder Vergleich
    waere gleich und kein Kamerawechsel wuerde je bemerkt. Die drei
    Kamera-Tests oben faenden das ebenfalls, aber nur als Symptom; dieser hier
    benennt die Ursache und haelt den Schnappschuss selbst fest, statt nur sein
    Ergebnis.
    """
    settings.kamera.rotation = 0
    before = snapshot(settings)
    settings.kamera.rotation = 180
    assert before.rotation == 0
    assert diff_settings(before, settings, accepted=True).camera_restart is True


def test_the_display_token_rides_through_the_snapshot_unchanged(settings):
    """Der Endpunkt ist fuer dieses Modul undurchsichtig - er gehoert dem
    DisplayController und wird nur weitergereicht."""
    token = (9999, "lokal")
    before = SettingsSnapshot.capture(settings, token)
    assert before.display == token
    settings.anzeige.port = 1234          # aendert den Token nicht nachtraeglich
    assert before.display == token


def test_diff_settings_does_not_touch_the_settings(settings, tmp_path):
    """Alle Entscheidungen fallen *vor* der ersten Nebenwirkung; die Rechnung
    selbst darf keine haben."""
    settings.overlay.image = real_image(tmp_path)
    before = snapshot(settings)
    settings.kamera.rotation = 90
    settings.bild.breite = settings.bild.breite + 5
    dumped = settings.model_dump()
    diff_settings(
        before,
        settings,
        accepted=True,
        reconnect_requested=True,
        test_mode_requested=True,
    )
    assert settings.model_dump() == dumped


def test_an_empty_snapshot_has_no_overlay_image():
    # Die Vorgaben der Datenklasse; ``open_settings`` baut sie nie so, aber ein
    # Standardwert, der plotzlich ein Pfad waere, ergaebe stille Falschtreffer.
    empty = SettingsSnapshot()
    assert empty.overlay_image is None
    assert isinstance(empty.display, tuple)
    assert empty.backend == ""


def test_the_snapshot_keeps_the_overlay_path_as_a_path(settings, tmp_path):
    image = real_image(tmp_path)
    settings.overlay.image = image
    before = snapshot(settings)
    assert isinstance(before.overlay_image, Path)
    assert diff_settings(before, settings, accepted=True).overlay_changed is False
