# app/core/util/paths.py
from pathlib import Path
from typing import Union
import unicodedata


def sanitize_name(name: str) -> str:
    """Return *name* restricted to ASCII letters, numbers, ``-`` and ``_``.

    Characters with accents or other diacritics are normalised to their ASCII
    representation and anything that cannot be expressed in ASCII is removed.
    The German sharp s ("ß") is explicitly converted to ``ss`` to retain a
    readable representation. This avoids crashes on filesystems or libraries
    that cannot handle non‑ASCII paths (e.g. when class names contain umlauts
    like ``Bü25x``).
    """
    name = name.replace("ß", "ss")
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in ascii_name if c.isalnum() or c in ("-", "_")).strip()

def class_output_dir(base: Union[str, Path], location: str, class_name: str) -> Path:
    """Return the directory for a class, creating it if necessary."""
    base_path = Path(base)
    safe_loc = sanitize_name(location)
    safe_class = sanitize_name(class_name)
    path = base_path / safe_loc / safe_class
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_learner_dir(base: Union[str, Path], location: str, class_name: str) -> Path:
    """Return folder for additional (walk-in) learners under *base*.

    *base* is expected to already be the dedicated "new learners" base path
    (``Settings.neueLernendeBasisPfad``), separate from the main class-photo
    output path so it can be configured independently.
    """
    return class_output_dir(base, location, class_name)


def target_file_path(directory: Union[str, Path], filename: str) -> Path:
    """Return the sanitized path for *filename* – *without* any unique suffix.

    This is where a file would land if nothing were in the way. Split out from
    ``unique_file_path`` so that "which file do I mean?" and "is that name
    already taken?" are two separate questions: the app has to be able to ask
    the first one (to check for an existing photo, and to overwrite it on
    request) without the second one silently renaming the target.

    Creates no directory – it is pure path arithmetic and safe to call for a
    file that may never be written.
    """
    directory = Path(directory)
    stem = sanitize_name(Path(filename).stem)
    return directory / f"{stem}{Path(filename).suffix}"


def unique_file_path(directory: Union[str, Path], filename: str) -> Path:
    """Return a unique, sanitized file path inside *directory*.

    If *filename* already exists it will be suffixed with ``_1``, ``_2`` …
    Note what that means for photos: the suffixed name is no longer a student
    ID, so it cannot be matched back to a person by name alone. Callers that
    care (see ``MainWindow.capture_photo``) ask the operator first.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    candidate = target_file_path(directory, filename)
    stem, suffix = candidate.stem, candidate.suffix
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{index}{suffix}"
        index += 1
    return candidate
