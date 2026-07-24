# CLAUDE.md — project & handoff notes

Guidance for Claude Code working in this repo. The app is in a **stable, shipped
state**: the long-standing EOS Webcam Utility black-screen bug is fixed and the
UI has been modernised (dark theme, iconography, grouped sidebar). Read
**Camera capture on Windows** before touching anything camera-related — it's the
biggest non-obvious gotcha in the codebase.

## What this app is

Desktop app (PySide6/Qt) for taking ID/portrait photos of students/employees,
matched against an Excel roster, with automatic per-class ZIP bundling. Runs on
Windows in production; developed/tested on macOS too (with a Simulator camera).
German UI and log messages.

- Entry point: `app/main.py` → `python -m app.main` (run as a module from repo root).
- Packaged as a Windows `.exe` via GitHub Actions (`.github/workflows/build-exe.yml`,
  PyInstaller `--onedir`, zipped artifact). Triggered by pushing a `v*` tag or
  manual `workflow_dispatch`.
- Version: `app/version.py` (`__version__`), shown in the window title and the
  bottom-left status bar (next to "erstellt von Alexej Waser" and a clickable
  GitHub icon). CI stamps `app/_build_info.py` (git short SHA + run number, git-
  ignored); local runs show `(dev)`.
- App icon: `icon.ico` (repo root, multi-size). PyInstaller embeds it via
  `--icon=icon.ico`; replace the file in place to change it (no workflow edit).

## Dev environment setup

This is a plain `venv` + `pip` project. There is no Python bundled with the repo;
on a fresh machine install CPython **3.12** first (e.g. `winget install
Python.Python.3.12`), then:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# macOS/Linux: source .venv/bin/activate && pip install -r requirements.txt
```

`requirements.txt` pins **`opencv-python-headless==4.11.0.86`** on purpose — cv2
is used only for array ops (colour convert / rotate / resize / imwrite), *not*
capture, and pinning avoids drifting onto OpenCV 5.0 (which dropped the Media
Foundation backend). Windows-only deps: `pygrabber`, `cv2_enumerate_cameras`
(they carry `comtypes`).

## Commands

```bash
# from repo root, using the venv interpreter
.venv/Scripts/python.exe -m app.main          # run from source (fast iteration w/ real camera)
.venv/Scripts/python.exe -m pytest tests/ -q  # tests (cv2 is mocked; no hardware needed)
```

Logs: `logs/` from source, and `%AppData%\LegicCardCreator\...` in the packaged
app. Camera opens / first-frames are logged at INFO (the EOS open line reads
`Backend DirectShow (pygrabber)` + a first-frame `mittlere Helligkeit`).

**Pre-existing test failures (not yours to fix):** ~10 `MainWindow._init_camera`
errors in `tests/test_photo_saving.py` + `tests/test_mainwindow_ui.py` (they
reference an attribute that doesn't exist), plus 4 `tests/test_camera_enumerate.py`
cases that fail on any machine with real cameras (they don't mock the MSMF
enumeration path). Everything else is green — verify with a clean tree if unsure.

**Rendering the UI headless for a visual check:** offscreen renders show text as
boxes (no Segoe UI in the offscreen platform) but layout/icons/colours are
faithful. Disable the modal onboarding first or the construction blocks:
```python
import app.ui.main_window as mw
mw.MainWindow._maybe_show_onboarding = lambda self: None
# QT_QPA_PLATFORM=offscreen; build MainWindow(settings with kamera.backend='simulator'); w.grab().save(...)
```

## Architecture

### Camera
- `app/core/camera/base.py` — `BaseCamera` ABC + `CameraError`.
- `app/core/camera/__init__.py` — exports the backends and
  **`make_webcam_camera(...)`**, the factory the app uses for webcam mode:
  `DirectShowCamera` on Windows, `OpenCVCamera` elsewhere. **Always build the
  webcam through this factory**, never `OpenCVCamera` directly.
- `app/core/camera/directshow_backend.py` — `DirectShowCamera`, the Windows
  capture path (pygrabber/DirectShow). All COM work is confined to one owner
  thread that builds+runs the graph and continuously re-arms the SampleGrabber
  so the newest frame lands in a BGR buffer; reader methods (`get_preview_qimage`
  / `capture`, called from Qt worker threads) just copy that buffer under a lock.
  pygrabber's RGB24 output is physically BGR in memory, so frames are stored
  as-is (no channel swap — swapping turns skin blue). Mirrors `OpenCVCamera`'s
  public API (rotation, downscale, first-frame diagnostics, bounded lock).
- `app/core/camera/opencv_backend.py` — `OpenCVCamera`, the non-Windows / legacy
  path. Streams frames; tries `_LIVEVIEW_BACKENDS`; **deliberately does NOT
  inspect frame content** (black/blank/freeze heuristics were tried and reverted;
  the Canon placeholder is a legitimately dark frame — don't reintroduce them).
- `app/core/camera/enumerate.py` — `list_cameras()` enumerates via Media
  Foundation (`cv2_enumerate_cameras`) on Windows so device names carry a stable
  `path`; falls back to DirectShow probing + pygrabber names. pygrabber's
  DirectShow device order matches, so saved `deviceName` resolves correctly for
  capture.
- `app/core/controller.py` — `MainController._init_camera()` builds the camera
  from settings via `make_webcam_camera`; falls back to Simulator on failure
  without clobbering the chosen device.
- `app/core/config/settings.py` — pydantic `Settings`; `KameraSettings` has
  `backend`, `deviceIndex`, `deviceName`, `devicePath`, `rotation`. `backend
  == "opencv"` means "webcam mode" (routed to DirectShow on Windows).
- `app/__init__.py` — sets `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` before
  cv2 loads (legacy; harmless now that Windows capture bypasses OpenCV).

### UI
- `app/main.py` — creates the QApplication, calls `apply_dark_theme(app)`,
  builds `MainController` + `MainWindow`.
- `app/ui/theme.py` — **forced dark theme** (dark Fusion palette applied app-
  wide, so dialogs/message boxes inherit it and the light-grey icons stay legible
  regardless of the OS setting).
- `app/ui/icons.py` — embedded UI icons as **base64 PNGs decoded with QtGui
  only** (no QtSvg, no asset files → nothing extra to bundle). `icon(name)`
  returns a cached `QIcon` (null for unknown names → graceful degradation);
  `github_icon()` delegates to it. Button glyphs are from lucide.dev, rendered in
  light grey (`#e6e6e6`); text-button icons have a baked transparent right margin
  (`PADDED` / `PADDED_ASPECT`) so the label sits clear of the glyph. To add/re-
  colour icons, re-render from SVG to base64 PNG (see git history for the
  generator) and update the dict — do NOT hand-wrap base64.
- `app/ui/widgets/control_panel.ui` + `control_panel.py` — the left sidebar,
  loaded from the `.ui`. Buttons are grouped into titled `QGroupBox` categories:
  **Datenbank** (Excel + Standort/Klasse + search), **Fotografieren** (Foto
  aufnehmen), **Einzelfälle** (Überspringen, Person hinzufügen, "Zu spezifischer
  Person springen"). `btn_finish` sits below a stretch; the loaded widget is set
  vertical-Expanding so Fertig is pushed to the bottom.
- `app/ui/main_window.py` — wires the panel: assigns icons, left-aligns the
  action buttons (scoped `#controlPanel QGroupBox` QSS + `QGroupBox` card
  styling), constrains the sidebar to a fixed width, moves the settings button
  into a compact bottom row beside the help "?" button, and adds the status-bar
  version/author/GitHub widgets. The photo review dialog (`_show_review`) keeps
  the photo on Space **and Enter** (autoDefault disabled so Enter doesn't hit the
  focused "Erneut fotografieren" button); Esc retakes.
- `app/ui/widgets/live_view_widget.py` — `QTimer`-driven preview; fetches frames
  on a `QtConcurrent` worker thread with an in-flight guard; shows "Kamera wird
  geladen…" on read errors.
- `app/ui/settings_dialog.py` — camera picker + live preview (builds its preview
  camera via `make_webcam_camera`); persists `deviceName`/`devicePath`; rotation
  changes apply in place (no device reopen). `load_excel` confirms before
  swapping the active roster.

## Camera capture on Windows — the big gotcha

**OpenCV cannot capture the production camera at all on the target machine.**
Both of its Windows backends are dead ends, so the app captures via pygrabber's
DirectShow SampleGrabber instead:

1. **MSMF is a plugin DLL the pip wheels don't ship.** With `OPENCV_VIDEOIO_DEBUG=1`
   the log is explicit: `load ...opencv_videoio_msmf*.dll => FAILED` →
   `VIDEOIO(MSMF): backend is not available`. The bundled `cv2/` folder ships only
   the FFMPEG plugin — no MSMF in **either** `opencv-python` or `-headless`, on
   4.11 or 5.0 (headless-vs-full differ only in GUI, not video I/O).
2. **OpenCV's DirectShow returns pure-black buffers for EOS Webcam Utility**
   (all-zero frames; forcing `CAP_PROP_FOURCC` doesn't help), though it reads the
   built-in webcam fine.

pygrabber's SampleGrabber requests **RGB24**, which makes DirectShow insert a
colour converter, and *that* reads real frames (placeholder + live R100, correct
colours) from the virtual webcam and from ordinary UVC cams. pygrabber was
already a dependency, so no new package was added.

Debugging tips: run from source and read `logs/`; the open line names the backend
and the first-frame mean brightness. EOS Webcam Utility emits its dark
"connect your camera" placeholder when the R100 is off/asleep — that's expected,
not a bug. Don't add frame-content heuristics.

## Packaging / GitHub Actions

`.github/workflows/build-exe.yml` (PyInstaller `--onedir`, zipped) must include,
because Windows capture now depends on pygrabber + comtypes at runtime:
- a **"Pre-generate comtypes wrappers"** step (`python -c "import
  pygrabber.dshow_graph"`) so comtypes generates its `comtypes.gen` COM wrappers
  in the build venv before PyInstaller runs — a fresh runner has none;
- `--collect-submodules pygrabber` and `--collect-all comtypes` so those wrappers
  are bundled. Without these the packaged app opens no camera.

Icons and theme need nothing special (pure-Python / embedded base64). To trigger
a build without `gh` installed, POST `workflow_dispatch` to the Actions API with
a stored git token (see session history), or push a `v*` tag.

## Conventions

- Default branch is **`main`**; branch off it for new work. The
  `camera-config-rewamp` branch (camera fix + UI overhaul) is merged into `main`.
- Commit/push only when asked. Commit messages end with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`; PR bodies end with
  the Claude Code footer.
