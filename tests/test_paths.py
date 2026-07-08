from pathlib import Path
from app.core.util.paths import (
    class_output_dir,
    new_learner_dir,
    unique_file_path,
    sanitize_name,
)

def test_class_output_dir(tmp_path):
    path = class_output_dir(str(tmp_path), 'Standort', 'Klasse')
    assert path.exists()
    assert path == tmp_path / 'Standort' / 'Klasse'

def test_new_learner_dir(tmp_path):
    # new_learner_dir takes the dedicated "Neue Lernende" base path directly
    # (Settings.neueLernendeBasisPfad), so no extra subfolder is appended here.
    path = new_learner_dir(str(tmp_path), 'Standort', 'Klasse')
    assert path.exists()
    assert path == tmp_path / 'Standort' / 'Klasse'


def test_unique_file_path(tmp_path):
    p1 = unique_file_path(tmp_path, 'name.jpg')
    p1.write_text('x')
    p2 = unique_file_path(tmp_path, 'name.jpg')
    assert p2.name == 'name_1.jpg'


def test_sanitize_name_umlauts():
    assert sanitize_name('Bü25x') == 'Bu25x'
    assert sanitize_name('ÄÖ Üßé') == 'AOUsse'
