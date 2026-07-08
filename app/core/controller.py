from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import psutil
from PySide6 import QtCore

from .config.settings import Settings
from .camera import SimulatorCamera, GPhoto2Camera, OpenCVCamera
from .excel.reader import ExcelReader, Learner
from .excel.missed_writer import MissedWriter, MissedEntry
from .imaging.processor import process_image
from .util.paths import class_output_dir, new_learner_dir, unique_file_path


class MainController:
    """Service layer containing business logic for the application."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.camera_fallback: bool = False
        self.camera_fallback_reason: str = ""
        self.camera = self._init_camera()
        self.reader: Optional[ExcelReader] = None
        self.learners: List[Learner] = []
        self.current: int = 0
        self.current_classes: List[str] = []

    # camera -----------------------------------------------------------------
    def _init_camera(self):
        backend = getattr(self.settings.kamera, "backend", "opencv")
        rotation = getattr(self.settings.kamera, "rotation", 270)
        self.camera_fallback = False
        self.camera_fallback_reason = ""
        cam = None
        if backend == "gphoto2" and QtCore.QStandardPaths.findExecutable("gphoto2"):
            cam = GPhoto2Camera()
        elif backend == "simulator":
            cam = SimulatorCamera()
        else:
            # Default: OpenCV (Webcam-Modus, z.B. Canon EOS M50 per USB)
            try:
                cam = OpenCVCamera(1, rotation=rotation)
                cam.start_liveview()
                self.current_cam_id = 1
            except Exception as e:
                cam = None
                self.camera_fallback = True
                self.camera_fallback_reason = str(e)
        if cam is None:
            cam = SimulatorCamera()
        return cam

    def restart_camera(self):
        if hasattr(self.camera, "stop_liveview"):
            self.camera.stop_liveview()
        self.camera = self._init_camera()
        if hasattr(self.camera, "start_liveview"):
            self.camera.start_liveview()
        return self.camera

    def switch_camera(self):
        if hasattr(self.camera, "switch_camera"):
            self.current_cam_id = getattr(self, "current_cam_id", 0) + 1
            self.camera.switch_camera(self.current_cam_id)

    # excel handling ---------------------------------------------------------
    def load_excel(self, path: Path) -> List[str]:
        self.reader = ExcelReader(path, self.settings.excelMapping.model_dump())
        locations = self.reader.locations()
        return locations

    def classes_for_location(self, location: str) -> List[str]:
        if not self.reader or not location:
            return []
        classes = self.reader.classes_for_location(location)
        self.current_classes = classes
        return classes

    def learners_for_class(
        self,
        location: str,
        class_name: str,
        skip_photographed: bool = False,
    ) -> List[Learner]:
        if not self.reader or not class_name:
            return []
        self.learners = self.reader.learners(
            location, class_name, skip_photographed=skip_photographed
        )
        self.current = 0
        return self.learners

    # learner helpers --------------------------------------------------------
    def current_learner(self) -> Optional[Learner]:
        if self.current < len(self.learners):
            return self.learners[self.current]
        return None

    def next_learner(self) -> Optional[Learner]:
        if self.current + 1 < len(self.learners):
            return self.learners[self.current + 1]
        return None

    def advance(self):
        self.current += 1

    # actions ----------------------------------------------------------------
    def excel_running(self) -> bool:
        # Note: on non-Windows platforms EXCEL.EXE is never running, so this
        # check is effectively a no-op outside Windows.
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info["name"] or ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if "excel" in name.lower():
                return True
        return False

    def capture(self, learner: Learner, location: str) -> Path:
        if learner.is_new:
            out_dir = new_learner_dir(self.settings.neueLernendeBasisPfad, location, learner.klasse)
            raw_path = unique_file_path(out_dir, f"{learner.vorname}_{learner.nachname}.jpg")
        else:
            out_dir = class_output_dir(self.settings.ausgabeBasisPfad, location, learner.klasse)
            raw_path = unique_file_path(out_dir, f"{learner.schueler_id}.jpg")
        self.camera.capture(raw_path)
        aspect = getattr(self.settings.bild, "seitenverhaeltnis", (3, 4))
        process_image(
            raw_path,
            raw_path,
            self.settings.bild.breite,
            self.settings.bild.hoehe,
            self.settings.bild.qualitaet,
            aspect,
        )
        return raw_path

    def mark_photographed(self, learner: Learner, location: str):
        if learner.is_new:
            return
        date_str = datetime.now().strftime("%d.%m.%Y")
        self.reader.mark_photographed(location, learner.row, True, date_str)

    def skip(self, learner: Learner, location: str, reason: str):
        missed = MissedWriter(self.settings.missedPath)
        entry = MissedEntry(
            location,
            learner.klasse,
            learner.nachname,
            learner.vorname,
            learner.schueler_id,
            datetime.now().isoformat(),
            reason,
        )
        missed.append(entry)
        if not learner.is_new:
            self.reader.mark_photographed(location, learner.row, False, reason=reason)

    def finish(self, location: str, klasse: str):
        out_dir = class_output_dir(self.settings.ausgabeBasisPfad, location, klasse)
        files = sorted(out_dir.glob("*.jpg"))
        if files:
            from .archiver.chunk_zip import chunk_by_count
            zip_base = out_dir / f"{klasse}.zip"
            max_count = getattr(self.settings.zip, "maxAnzahl", None) or len(files)
            zip_paths = chunk_by_count(files, zip_base, max_count)
        else:
            zip_paths = []
        return zip_paths, out_dir

    def add_learner(self, klasse: str, vorname: str, nachname: str) -> Learner:
        learner = Learner(klasse, nachname, vorname, "", is_new=True)
        self.learners.insert(self.current, learner)
        return learner
