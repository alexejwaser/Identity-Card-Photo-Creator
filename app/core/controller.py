from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import psutil
from PySide6 import QtCore

from .config.settings import Settings
from .camera import SimulatorCamera, GPhoto2Camera, OpenCVCamera, list_cameras
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
        device_index = getattr(self.settings.kamera, "deviceIndex", 1)
        device_name = getattr(self.settings.kamera, "deviceName", "") or None
        device_path = getattr(self.settings.kamera, "devicePath", "") or None
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
                cam = OpenCVCamera(
                    device_index,
                    rotation=rotation,
                    device_name=device_name,
                    device_path=device_path,
                )
                cam.start_liveview()
            except Exception as e:
                cam = None
                # Only auto-switch to a different camera if the configured
                # index genuinely doesn't exist on this machine (e.g. a
                # laptop's built-in webcam sits at index 0, but the stored
                # setting still points at index 1 from a previous device/OS).
                # A flaky driver (observed with Canon EOS Webcam Utility,
                # which can intermittently fail to open for a stretch before
                # recovering on its own) is a different situation: silently
                # switching to - and persisting - some other camera on every
                # transient hiccup would fight the operator's actual choice
                # and adds a slow device re-enumeration on top of an already
                # slow startup, so leave the configured index alone and fall
                # back to the simulator for this attempt instead.
                detected = self._safe_list_cameras()
                configured_exists = self._device_present(
                    detected, device_index, device_name, device_path
                )
                fallback = (
                    None if configured_exists else next(iter(detected), None)
                )
                if fallback is not None:
                    try:
                        cam = OpenCVCamera(
                            fallback.index,
                            rotation=rotation,
                            device_name=fallback.name,
                            device_path=getattr(fallback, "path", None),
                        )
                        cam.start_liveview()
                        self.settings.kamera.deviceIndex = fallback.index
                        self.settings.kamera.deviceName = fallback.name or ""
                        self.settings.kamera.devicePath = getattr(fallback, "path", None) or ""
                        try:
                            self.settings.save()
                        except Exception:
                            pass
                    except Exception as e2:
                        cam = None
                        e = e2
                if cam is None:
                    self.camera_fallback = True
                    self.camera_fallback_reason = str(e)
        if cam is None:
            cam = SimulatorCamera()
        return cam

    @staticmethod
    def _safe_list_cameras():
        try:
            return list_cameras()
        except Exception:
            return []

    @staticmethod
    def _device_present(detected, device_index, device_name, device_path) -> bool:
        """Whether the configured device is among *detected*. Prefers the stable
        path/name (so a transient index shift is not mistaken for a missing
        device); falls back to the index when no name/path was saved."""
        if device_path and any(getattr(d, "path", None) == device_path for d in detected):
            return True
        if device_name and any(d.name == device_name for d in detected):
            return True
        if device_path or device_name:
            # A name/path was configured but not found among detected devices.
            return False
        return any(d.index == device_index for d in detected)

    def restart_camera(self):
        if hasattr(self.camera, "stop_liveview"):
            self.camera.stop_liveview()
        self.camera = self._init_camera()
        if hasattr(self.camera, "start_liveview"):
            self.camera.start_liveview()
        return self.camera

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
