# CLAUDE.md — project & handoff notes

Guidance for Claude Code working in this repo. The long-running EOS Webcam
Utility black-screen bug is **resolved** — see the **RESOLVED** section below for
the root cause and the DirectShow/pygrabber fix (relevant when touching camera
capture on Windows).

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
- `app/core/camera/__init__.py` — exports the backends and
  `make_webcam_camera(...)`, the factory the app uses for webcam mode:
  **`DirectShowCamera` on Windows**, `OpenCVCamera` elsewhere. Use this, not
  `OpenCVCamera` directly, for the webcam path.
- `app/core/camera/directshow_backend.py` — `DirectShowCamera`: the Windows
  capture path (pygrabber/DirectShow). See the **RESOLVED** section for why
  OpenCV can't capture here. COM confined to one owner thread; frames buffered
  as BGR; readers just copy the buffer.
- `app/core/camera/opencv_backend.py` — `OpenCVCamera`: non-Windows / legacy
  path. Opens a device via OpenCV, streams frames. Tries backends in
  `_LIVEVIEW_BACKENDS`
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

## RESOLVED — EOS Webcam Utility black-screen (fixed via DirectShow/pygrabber)

### Symptom (history)
With a **Canon EOS R100** via **EOS Webcam Utility** on Windows, the live preview
was **black** instead of the R100 feed or the Canon placeholder, while MS Teams
showed it fine and the built-in "Integrated Camera" worked in the app.

### Root cause (confirmed on-hardware, from source, this session)
OpenCV simply **cannot capture on this machine** — both of its Windows backends
are dead ends here:
1. **MSMF is a plugin DLL that the pip wheels do not ship.** With
   `OPENCV_VIDEOIO_DEBUG=1` the log is explicit:
   `load ...\cv2\opencv_videoio_msmf4110_64.dll => FAILED` →
   `VIDEOIO(MSMF): backend is not available`. The `cv2/` folder ships only
   `opencv_videoio_ffmpeg*.dll`; no MSMF plugin in **either** `opencv-python`
   **or** `-headless`, on 4.11 **or** 5.0. (headless-vs-full differ only in GUI,
   not video I/O — so "switch to full opencv-python" does NOT help.) OpenCV 5.0
   additionally has no `Media Foundation` line in `getBuildInformation()` at all.
2. **OpenCV's DirectShow returns pure-black buffers for EOS Webcam Utility**
   (all-zero frames; forcing `CAP_PROP_FOURCC` to YUY2/I420/NV12 does not help —
   verified visually), even though the same DSHOW path reads the built-in camera
   fine (~150 brightness).

**pygrabber** builds a DirectShow graph whose SampleGrabber explicitly requests
**RGB24**, which makes DirectShow insert a colour converter — and that reads real
frames from EOS Webcam Utility (placeholder *and* live R100 video, correct
colours) as well as from the built-in camera. pygrabber was already a dependency
(device enumeration), so this added no new package.

### The fix (implemented, verified from source with the R100)
- **`app/core/camera/directshow_backend.py`** — new `DirectShowCamera`
  (pygrabber). All COM/DirectShow work is confined to one owner thread that
  builds+runs the graph and continuously re-arms the grabber so the newest frame
  is copied into a BGR buffer; reader methods (`get_preview_qimage` / `capture`,
  called from Qt worker threads) just copy that buffer under a lock — no
  cross-thread COM. Public API mirrors `OpenCVCamera` (rotation, downscale,
  first-frame diagnostics, bounded capture lock).
- **`app/core/camera/__init__.py`** — `make_webcam_camera(...)` factory:
  `DirectShowCamera` on win32, `OpenCVCamera` elsewhere (macOS dev, etc.).
- **`controller.py`** and **`settings_dialog.py`** now build the webcam via
  `make_webcam_camera` instead of `OpenCVCamera` directly.
- **`requirements.txt`** pins `opencv-python-headless==4.11.0.86` (cv2 is now used
  only for array ops — colour convert / rotate / resize / imwrite — not capture).
- `OpenCVCamera` is unchanged and still used off-Windows; `enumerate.py`
  (MSMF-based `list_cameras`) is unchanged — its names match pygrabber's order.

Verified: `DirectShowCamera` opened from the main thread, `get_preview_qimage`
read from a worker thread (valid non-black QImages), full-res `capture()` from a
third thread (real R100 photo saved), and the live feed rendered through the real
`LiveViewWidget` path — all with correct colours. `pytest tests/` green except the
same pre-existing failures (10 `MainWindow._init_camera` errors; plus 4
`test_camera_enumerate.py` cases that fail on any machine with real cameras
because they don't mock the MSMF enumeration path — confirmed on a clean tree).

### If it regresses / for future work
- Run from source (`python -m app.main`) and read `logs/`; the EOS open line now
  logs `Backend DirectShow (pygrabber)` and a first-frame `mittlere Helligkeit`.
- Do **not** reintroduce brightness/black-frame/freeze heuristics (rejected
  earlier — the placeholder is a legitimately dark frame).
- The PyInstaller build already bundled pygrabber/comtypes (used for
  enumeration), so no build-spec change was needed; if a packaged build ever
  can't find comtypes-generated modules, add them as PyInstaller hidden imports.

### Key files for this issue
`app/core/camera/directshow_backend.py`, `app/core/camera/__init__.py`,
`app/core/camera/opencv_backend.py`, `app/core/camera/enumerate.py`,
`app/core/controller.py`, `app/ui/settings_dialog.py`, `requirements.txt`.
