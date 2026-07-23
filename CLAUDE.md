# CLAUDE.md — project & handoff notes

Guidance for Claude Code working in this repo. Read the **Current focus** section
first — it's an active debugging effort being continued on the Windows PC that
has the Canon EOS R100.

## What this app is

Desktop app (PySide6/Qt) for taking ID/portrait photos of students/employees,
matched against an Excel roster, with automatic per-class ZIP bundling. Runs on
Windows in production; developed/tested on macOS too (with a Simulator camera).
German UI and log messages.

- Entry point: `app/main.py` → `python -m app.main` (run as a module from repo root).
- Packaged as a Windows `.exe` via GitHub Actions (`.github/workflows/build-exe.yml`,
  PyInstaller `--onedir`). Triggered by pushing a `v*` tag or manual
  `workflow_dispatch`.
- Version: `app/version.py` (`__version__`), shown in the window title and
  bottom-left status bar. CI stamps `app/_build_info.py` (git short SHA + run
  number); local runs show `(dev)`.

### Architecture (camera-relevant)
- `app/core/camera/base.py` — `BaseCamera` ABC + `CameraError`.
- `app/core/camera/opencv_backend.py` — `OpenCVCamera`: opens a device via
  OpenCV, streams frames. Tries backends in `_LIVEVIEW_BACKENDS`
  (`[CAP_MSMF, CAP_DSHOW]` on Windows), re-resolving the correct per-backend
  index from the saved device name/path (`resolve_backend_index`). Logs each
  open attempt/failure + first-frame diagnostics (resolution, mean brightness).
  **Deliberately does NOT inspect frame content** (no black/blank/freeze
  heuristics — those were tried and reverted; the Canon placeholder is a
  legitimately dark frame).
- `app/core/camera/enumerate.py` — `list_cameras()` enumerates via Media
  Foundation using the `cv2_enumerate_cameras` package on Windows (so indices
  match the capture backend and each device has a stable `path`); falls back to
  DirectShow probing + pygrabber names. `resolve_backend_index(backend, name,
  path, fallback_index)` maps a saved device to the right index for a backend.
- `app/core/controller.py` — `MainController._init_camera()` builds the camera
  from settings (`backend`, `deviceIndex`, `deviceName`, `devicePath`,
  `rotation`); falls back to Simulator on failure without clobbering the chosen
  device.
- `app/ui/widgets/live_view_widget.py` — `QTimer`-driven preview; fetches frames
  on a `QtConcurrent` worker thread with an in-flight guard. Shows "Kamera wird
  geladen…" on read errors; black label background.
- `app/ui/settings_dialog.py` — camera picker + live preview; persists
  `deviceName`/`devicePath`; rotation changes apply in place (no device reopen).
- `app/core/config/settings.py` — pydantic `Settings`; `KameraSettings` has
  `backend`, `deviceIndex`, `deviceName`, `devicePath`, `rotation`.
- `app/__init__.py` — sets `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` before
  cv2 loads.

## Commands

```powershell
# From repo root, in the venv (.venv\Scripts\activate)
python -m app.main                       # run from source (fast iteration w/ real camera)
python -m pytest tests/ -q               # tests (cv2 is mocked; no hardware needed)
```
Note: 10 tests in `tests/test_photo_saving.py` + `tests/test_mainwindow_ui.py`
were already failing before this work (they reference a `MainWindow._init_camera`
attribute that doesn't exist) — **pre-existing, unrelated**. Everything else is green.

Logs are written under `logs/` (and in the packaged app, under
`%AppData%\LegicCardCreator\...`). Camera opens/first-frames are logged at INFO.

Git: work happens on branch **`camera-config-rewamp`**. Commit messages end with
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit/push only when
asked. Build with `gh workflow run build-exe.yml --ref camera-config-rewamp`.

---

## CURRENT FOCUS — EOS Webcam Utility black-screen (unresolved)

### Symptom
Using the app with a **Canon EOS R100** via **EOS Webcam Utility** (a virtual
webcam) on Windows: the live preview is **black** instead of showing the camera
feed or the Canon "connect your camera" placeholder. In **MS Teams and other
apps the placeholder/feed always shows** (even with the camera off), so the
device itself is fine. The **built-in laptop webcam ("Integrated Camera") works
perfectly** in this app. This regressed sometime this year (last summer's build
was fine).

### Root cause established (from three on-hardware session logs)
1. Original bug: enumeration used DirectShow while capture preferred Media
   Foundation, so the picked index was fed to the wrong backend → wrong/no
   device. **Fixed**: now enumerate + resolve by stable name/path per backend.
2. **The remaining blocker:** on the target Windows machine, **OpenCV's Media
   Foundation (MSMF) backend cannot open ANY camera** — the log shows
   `Backend MSMF konnte Index N nicht oeffnen` for the EOS (index 0), the
   built-in camera (index 1), and startup — even with
   `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` set. It always falls back to
   **DirectShow**, and **DirectShow streams pure black for EOS Webcam Utility**
   (`erstes Bild ... mittlere Helligkeit 0.0`), while the built-in camera via
   DirectShow reads normally (~160 brightness).

So: MSMF (the path Teams uses, which shows the placeholder) is unavailable in
this OpenCV build, and DirectShow — the only working backend here — delivers
black for this particular virtual webcam.

### What's already been tried (don't redo)
- ✅ Name/path-based device resolution per backend (`resolve_backend_index`).
- ✅ MSMF preferred in `_LIVEVIEW_BACKENDS`; `cv2_enumerate_cameras` for MSMF
  enumeration. → MSMF still won't open on the target machine.
- ✅ `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` in `app/__init__.py`. → no effect.
- ✅ Per-attempt + first-frame diagnostic logging (keep it — it's how we confirm).
- ✅ Rotation-only changes no longer reopen the device (churn reduction).
- ❌ Reintroducing brightness/black-frame/freeze heuristics — explicitly rejected
  earlier; do NOT bring these back.

### Next steps to try — ON THE WINDOWS PC, from source, with the R100
Run from source for fast iteration (`python -m app.main`) and read `logs/`.
Prioritized hypotheses:

1. **Confirm whether MSMF exists in this OpenCV build at all.**
   ```powershell
   python -c "import cv2; print(cv2.getBuildInformation())" | Select-String -Pattern "Media Foundation|MSMF|DSHOW|DirectShow"
   $env:OPENCV_VIDEOIO_DEBUG=1; python -m app.main   # prints backend load attempts
   ```
   If "Media Foundation" is NO / the plugin DLL fails to load, MSMF is a dead end
   in this wheel → go to step 2.

2. **Switch the dependency from `opencv-python-headless` to full `opencv-python`.**
   `requirements.txt` currently pins `opencv-python-headless`. The full wheel may
   ship a working MSMF plugin. Swap it, `pip install -r requirements.txt`, retest.
   (If it fixes MSMF, also update the PyInstaller build.)

3. **Make DirectShow deliver real frames for EOS Webcam Utility (leading fix if
   MSMF stays dead).** EOS Webcam Utility commonly needs an explicit format on
   the DSHOW path or it yields black. In `OpenCVCamera.start_liveview`, after a
   successful DSHOW open, try forcing MJPG and/or the native resolution:
   ```python
   cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
   cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
   cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
   ```
   Experiment with FOURCC (`MJPG`, `YUY2`, `NV12`) and resolutions the EOS
   Webcam Utility advertises. Watch the logged `mittlere Helligkeit` — nonzero
   means real content. Note EOS Webcam Utility only outputs the *placeholder*
   when the camera is off; with the R100 powered on it should output live video.

4. **If OpenCV can't be made to work, capture via Media Foundation directly**
   (bypass OpenCV for the EOS path) — e.g. a small MF/DirectShow frame-grabber
   (`pygrabber` can grab DSHOW frames with a chosen format; or a `windows-capture`/
   MF-based reader). Bigger change; only if 2–3 fail.

### How to verify a fix
- App bottom-left shows the build version (confirm you're testing the new build).
- EOS Webcam Utility selected → preview shows live R100 video (camera on) or the
  Canon placeholder (camera off), not black, promptly (no ~10s black warm-up).
- Log: EOS open line reports a working backend and `mittlere Helligkeit` > ~5.
- Built-in "Integrated Camera" still works; switching between them recovers cleanly.
- `python -m pytest tests/ -q` still green (minus the 10 pre-existing failures).

### Key files for this issue
`app/core/camera/opencv_backend.py`, `app/core/camera/enumerate.py`,
`app/__init__.py`, `requirements.txt`, `.github/workflows/build-exe.yml`.
