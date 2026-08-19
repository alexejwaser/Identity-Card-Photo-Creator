# Graph Report - .  (2026-08-19)

## Corpus Check
- 27 files · ~38,518 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 996 nodes · 1906 edges · 64 communities (57 shown, 7 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 49 edges (avg confidence: 0.67)
- Token cost: 0 input · 70,057 output

## Community Hubs (Navigation)
- MainWindow Capture Flow
- Settings Diff & Test Doubles
- OpenCV Camera Backend
- Settings Schema
- Onboarding Gate
- Controller Photo Paths
- Settings Snapshot & Diff
- Display Snapshot State
- Sidebar & Live View Widgets
- Camera Enumeration
- SchuelerID Conflict Detection
- Display Controller Tests
- Settings Dialog
- Packaging & Build Workflow
- Display Controller Lifecycle
- Display Server Tests
- Test Mode & Roster Redirect
- Camera Base & DirectShow
- Display Server Surface
- ID Conflict End-to-End Tests
- DirectShow Capture Backend
- Excel Reader Core
- MainController Service Layer
- Class Search Dialog
- Learner Loading & UI Tests
- Settings Dialog Tests
- Display HTTP Server Internals
- Image Processing
- Display Context Boundary
- Display Page & Handler
- Camera Fallback Tests
- Display Snapshot Tests
- Storage Key Characterization
- Photo Saving & Jump Tests
- GPhoto2 Backend
- README Feature Overview
- Simulator Camera
- Embedded Icons
- Missed-Entry Writer
- Output Audit Tool
- ZIP Chunking
- Capture Lock Context
- Filename Identity Rules
- Display Timer Tests
- Display Test Fixtures
- Preview Capture Interface
- Display URL Resolution
- Shared Test Fixture Policy
- Display Port Restart Tests
- Camera Probing Fixture
- Unusable ID Guard
- App Package Init
- Logger Reference
- QFutureWatcher Reference
- Pytest Fixture Marker
- Pytest Fixture Marker (2)

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 58 edges
2. `Learner` - 34 edges
3. `MainController` - 32 edges
4. `OpenCVCamera` - 30 edges
5. `ExcelReader` - 30 edges
6. `DisplayServer` - 29 edges
7. `diff_settings()` - 29 edges
8. `DisplayController` - 28 edges
9. `DirectShowCamera` - 26 edges
10. `CameraError` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Single COM owner thread + locked frame buffer` --semantically_similar_to--> `DisplayServer`  [INFERRED] [semantically similar]
  CLAUDE.md → app/core/display/server.py
- `find_id_conflicts()` --semantically_similar_to--> `ExcelReader.duplicate_ids() (removed — compared raw IDs)`  [INFERRED] [semantically similar]
  app/core/identity.py → CLAUDE.md
- `Single COM owner thread + locked frame buffer` --rationale_for--> `DirectShowCamera`  [EXTRACTED]
  CLAUDE.md → app/core/camera/directshow_backend.py
- `Pre-generate comtypes wrappers packaging step` --conceptually_related_to--> `DirectShowCamera`  [EXTRACTED]
  CLAUDE.md → app/core/camera/directshow_backend.py
- `pygrabber SampleGrabber RGB24 capture path` --rationale_for--> `DirectShowCamera`  [EXTRACTED]
  CLAUDE.md → app/core/camera/directshow_backend.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Camera backend family behind make_webcam_camera** — app_core_camera_base_basecamera, app_core_camera_directshow_backend_directshowcamera, app_core_camera_opencv_backend_opencvcamera, app_core_camera___init___make_webcam_camera, app_core_camera_enumerate_list_cameras, app_core_controller_maincontroller_init_camera [EXTRACTED 1.00]
- **SchülerID → filename safety flow** — app_core_identity_sanitize_name, app_core_identity_storage_key, app_core_identity_find_id_conflicts, app_core_identity_planned_photo_path, app_core_identity_target_file_path, app_core_identity_unique_file_path, claude_capture_photo_ask_overwrite [EXTRACTED 1.00]
- **Anti-stale-data mechanism of the Wartezimmer-Anzeige** — app_core_display_controller_displaycontroller, app_core_display_server_displayserver, app_core_display_page_page, app_core_display_state_build_snapshot, claude_never_show_stale_names, claude_1hz_republish_timer, claude_allow_reuse_address_off_windows [EXTRACTED 1.00]
- **Windows packaging steps bundling camera-capture dependencies** — github_workflows_build_exe_pregenerate_comtypes_wrappers, github_workflows_build_exe_build_application_directory, pkg_pygrabber, pkg_comtypes, pkg_cv2_enumerate_cameras, concept_windows_camera_capture_pipeline [EXTRACTED 1.00]

## Communities (64 total, 7 thin omitted)

### Community 0 - "MainWindow Capture Flow"
Cohesion: 0.07
Nodes (18): MainWindow, Path, Settings, Das *Wie* zu den Entscheidungen aus diff_settings().          Nur hier stehen Wi, Main GUI window for the application., Log *message* with *level* and optionally show a QMessageBox., Point self.reader at *path* and populate the location dropdown.         Returns, Generate a fresh randomized placeholder roster, load it as the active         ro (+10 more)

### Community 1 - "Settings Diff & Test Doubles"
Cohesion: 0.06
Nodes (46): Was sich am Einstellungsdialog geaendert hat - als reine Rechnung.  Warum es die, Was daraufhin zu tun ist. Das *Wie* steht im ``MainWindow``., SettingsChange, DummyCamera, Kamera-Double, das statt echter Hardware eine Datei schreibt., fill_classes(), names(), payload() (+38 more)

### Community 2 - "OpenCV Camera Backend"
Cohesion: 0.08
Nodes (30): _backend_label(), OpenCVCamera, Path, QImage, Rotate *frame* by the configured amount; no-op if rotation is 0., Read a single frame. Raises CameraError only if the read itself         fails -, Log the negotiated resolution and this device's mean frame         brightness on, Reads frames from an OpenCV/DirectShow camera index, including     virtual webca (+22 more)

### Community 3 - "Settings Schema"
Cohesion: 0.09
Nodes (37): AnzeigeSettings, _app_base_dir(), BildSettings, CopyrightSettings, _default_new_learner_path(), _default_output_path(), ExcelMapping, KameraSettings (+29 more)

### Community 4 - "Onboarding Gate"
Cohesion: 0.07
Nodes (39): mark_shown(), marker_path(), Path, Die Einmal-Entscheidung hinter der Kurzanleitung.  Warum es dieses Modul gibt (I, Ob die Kurzanleitung beim Start erscheinen soll (einmal, fuer immer)., Setzt den Marker; liefert False, wenn das nicht ging.      Der Rueckgabewert ist, should_show(), Main application window. (+31 more)

### Community 5 - "Controller Photo Paths"
Cohesion: 0.09
Nodes (37): Path, Wohin das Foto ginge, wenn nichts im Weg stuende.          Getrennt von ``captur, class_output_dir(), new_learner_dir(), Path, Return the directory for a class, creating it if necessary., Return folder for additional (walk-in) learners under *base*.      *base* is exp, Return the sanitized path for *filename* – *without* any unique suffix.      Thi (+29 more)

### Community 6 - "Settings Snapshot & Diff"
Cohesion: 0.11
Nodes (39): diff_settings(), Die Werte, die *vor* dem Dialog galten.      Bewusst kopierte Einzelwerte und ke, Vergleicht *settings* mit *before*. Veraendert nichts.      Zur Rolle von *accep, SettingsSnapshot, MainWindow._apply_settings_change, MainWindow.open_settings, Load-bearing ordering in _apply_settings_change, Die Vorher/Nachher-Rechnung um den Einstellungsdialog (Issue #46).  Kein Qt, kei (+31 more)

### Community 7 - "Display Snapshot State"
Cohesion: 0.12
Nodes (38): build_snapshot(), format_name(), Any, Snapshot-Aufbau fuer die Wartezimmer-Anzeige.  Bewusst frei von Qt und Netzwerk:, Anna Mueller' -> 'Anna M.' (bzw. voll, wenn *full*).      Neu hinzugefuegte Pers, Baut den Zustand, den die Anzeige zeigt.      *jump_return* ist gesetzt, solange, Student IDs never enter the display payload, Abgekürzte Namen weil die Anzeige öffentlich hängt (+30 more)

### Community 8 - "Sidebar & Live View Widgets"
Cohesion: 0.09
Nodes (13): ControlPanel, Left side control panel loaded from a Qt Designer .ui file., LiveViewWidget, Exception, Path, QFutureWatcher, QImage, Widget zur Anzeige des Live-Streams mit einblendbarem Overlay. (+5 more)

### Community 9 - "Camera Enumeration"
Cohesion: 0.13
Nodes (26): CameraDevice, _enumerate_via_cv2ec(), list_cameras(), _list_cameras_by_probing(), _probe_indices(), List available cameras, indexed for the live-capture backend.      On Windows, e, Return the ``cv2.VideoCapture`` index for *backend* that identifies the     devi, Enumerate cameras for a specific cv2 *backend* via cv2_enumerate_cameras.      R (+18 more)

### Community 10 - "SchuelerID Conflict Detection"
Cohesion: 0.14
Nodes (27): Der Dateinamen-Konflikt dieser Lernenden - oder None., conflict_for(), find_id_conflicts(), IdConflict, Wie aus einer SchuelerID ein Dateiname wird - und wann das schiefgeht.  Warum es, Ein Dateiname, den sich mehrere Lernende teilen wuerden., Alle Dateinamen-Kollisionen im Roster.      *learners* sollte die **vollstaendig, Der Konflikt, der *learner* betrifft - oder None, wenn alles sauber ist. (+19 more)

### Community 11 - "Display Controller Tests"
Cohesion: 0.09
Nodes (18): Lebenszyklus des Anzeige-Controllers (Server + Timer + Signale).  Gegen echte So, lokal' -> nur 127.0.0.1; die LAN-Adressen fuehren dort ins Leere., netzwerk' -> 0.0.0.0, damit das zweite Geraet im WLAN drankommt., Der OSError aus DisplayServer.start() darf nicht durchschlagen - die     GUI bek, publish() laeuft in einem Qt-Timer-Slot - eine Ausnahme dort reisst im     Zweif, Der Neustart auf einen belegten Port: erst 'stopped', dann 'failed' -     und *k, Sammelt die Signal-Nutzlast in einer Liste - die Signale feuern     synchron in, record() (+10 more)

### Community 12 - "Settings Dialog"
Cohesion: 0.13
Nodes (7): make_webcam_camera, Logger, Update the preview rotation in place without reopening the device., Log *message* with *level* and optionally show a QMessageBox., Signal MainWindow to activate one-shot test mode, then close via the         nor, SettingsDialog, make_webcam_camera factory rule

### Community 13 - "Packaging & Build Workflow"
Cohesion: 0.10
Nodes (25): app._build_info module (git-ignored, CI-stamped), app/main.py (entry point), app/ui/widgets/control_panel.ui, app.version.__version__, OpenCV 4.x pin rationale (5.0 dropped Media Foundation backend; cv2 used only for array ops), Windows camera capture packaging requirement (pygrabber+comtypes bundling), Build Windows release workflow, Build application directory step (PyInstaller --onedir) (+17 more)

### Community 14 - "Display Controller Lifecycle"
Cohesion: 0.11
Nodes (14): DisplayController, Haelt Timer und Server an - bedingungslos.          ``stopped`` wird auch dann g, Schiebt den aktuellen Zustand an die Anzeige.          Laeuft immer auf dem GUI-, Die Einstellungen, die den Socket bestimmen (Port und Modus)., Startet neu, falls sich Port oder Modus seit *before* geaendert haben., Besitzt ``DisplayServer`` und den Veroeffentlichungs-Timer., Schaltet um und liefert den Zustand *danach* (True = laeuft)., Startet Server und Timer; liefert False bei belegtem Port. (+6 more)

### Community 15 - "Display Server Tests"
Cohesion: 0.16
Nodes (19): get(), Lebenszyklus und HTTP-Oberflaeche des Anzeige-Servers.  Gegen einen echten Socke, Die Kernzusage: rev bleibt gleich (kein Flackern), der Zeitstempel wird     trot, snapshot(), test_age_is_reported_and_grows(), test_changed_snapshot_bumps_the_revision(), test_instance_is_stable_within_a_run_and_changes_between_runs(), test_local_mode_still_serves_the_page() (+11 more)

### Community 16 - "Test Mode & Roster Redirect"
Cohesion: 0.16
Nodes (19): activate_test_mode(), Path, Testmodus: Platzhalter-Roster laden und die Ausgabe umlenken.  Warum es dieses M, Erzeugt ein frisches Zufalls-Roster und liefert seinen Pfad.      Die Ausgabepfa, daten_dir(), Der Testmodus und seine eine harte Zusage (Issue #46).  Kein Qt: ``activate_test, Der Knopf ist mehrfach erreichbar; das zweite Mal trifft auf einen     bestehend, Nur *eine* Zusicherung: dass die Datei fuer den ExcelReader ueberhaupt     ein R (+11 more)

### Community 17 - "Camera Base & DirectShow"
Cohesion: 0.21
Nodes (10): ABC, BaseCamera, CameraError, Exception, Return the pygrabber (DirectShow-ordered) device index for the saved     device,, _resolve_pygrabber_index(), _normalize(), make_webcam_camera() (+2 more)

### Community 18 - "Display Server Surface"
Cohesion: 0.10
Nodes (16): DisplayServer, Steuert Lebenszyklus und Inhalt der Wartezimmer-Anzeige., Der tatsaechlich gebundene Port (wichtig bei Port 0 im Test)., True, wenn der Server nur auf dem eigenen Rechner erreichbar ist., allow_reuse_address off on Windows, Single COM owner thread + locked frame buffer, fixture, Unter Windows darf sich kein zweiter Prozess still danebenbinden - sonst     lie (+8 more)

### Community 19 - "ID Conflict End-to-End Tests"
Cohesion: 0.18
Nodes (19): controller_for(), keys(), Von der Excel-Zelle bis zur blockierten Aufnahme.  tests/test_identity.py prueft, Der zweite Fehler.      Alpha ist fotografiert und faellt aus der Arbeitsliste -, Die Konflikte gehoeren zur geladenen Klasse, nicht zur Sitzung., Die Vorwarnung beim Laden nennt beide IDs und den Dateinamen., Der eigentliche Ablauf: die erste Aufnahme laeuft durch, erst die     zweite tri, Die Gegenprobe - ohne Kollision wird nicht gefragt. (+11 more)

### Community 20 - "DirectShow Capture Backend"
Cohesion: 0.19
Nodes (7): DirectShowCamera, Path, QImage, SampleGrabber callback (runs on DirectShow's streaming thread).          The gra, Return the most recent frame (BGR). Waits briefly for the first frame         af, Streams frames from a DirectShow webcam via pygrabber. Delivers whatever     the, BGR-in-RGB24 buffer, no channel swap

### Community 21 - "Excel Reader Core"
Cohesion: 0.15
Nodes (11): ExcelReader, Path, Read row 1 of the first sheet and return {header_text: column_letter}., generate_test_roster(), Path, Write a randomized placeholder roster to *path*.      *mapping* is a dict with k, create_sample(), Path (+3 more)

### Community 22 - "MainController Service Layer"
Cohesion: 0.14
Nodes (4): MainController, Settings, Whether the configured device is among *detected*. Prefers the stable         pa, Service layer containing business logic for the application.

### Community 23 - "Class Search Dialog"
Cohesion: 0.12
Nodes (5): ClassSearchDialog, Logger, dialog(), fixture, Die Aufloesung der Klassensuche - der einzige Ort, an dem getippter Text zu eine

### Community 24 - "Learner Loading & UI Tests"
Cohesion: 0.16
Nodes (14): Learner, Return all learners for *class_name* in *location*.          If *skip_photograph, Die Anzeige oeffnet einen Port (und unter Windows die Firewall-Frage) -     sie, Ein Klick startet, der naechste stoppt - und der Knopf zeigt es an., Der belegte Port darf nicht als 'laeuft' durchgehen - sonst glaubt die     Fotog, Der Controller ueberlebt das Fenster (er gehoert MainController) - nach     dem, test_busy_port_leaves_the_button_unchecked(), test_capture_flow() (+6 more)

### Community 25 - "Settings Dialog Tests"
Cohesion: 0.15
Nodes (4): FakePreviewCamera, patched_camera(), fixture, Stand-in for OpenCVCamera used by the dialog preview - touches no     real hardw

### Community 26 - "Display HTTP Server Internals"
Cohesion: 0.17
Nodes (6): Any, Logger, Uebernimmt *snapshot*; zaehlt ``rev`` nur bei inhaltlicher Aenderung hoch., Startet den Server und liefert den gebundenen Port.          Wirft ``OSError``,, _Server, ThreadingHTTPServer

### Community 27 - "Image Processing"
Cohesion: 0.24
Nodes (11): crop_center(), _parse_ratio(), process_image(), Path, Return a tuple ratio from a ``"w:h"`` string or tuple., Image, Tests for image processing helpers., Ensure the internal ratio parser handles various inputs. (+3 more)

### Community 28 - "Display Context Boundary"
Cohesion: 0.20
Nodes (7): DisplayContext, Lebenszyklus der Wartezimmer-Anzeige - Server + 1-Hz-Takt an einem Ort.  Warum e, Der Teil des GUI-Zustands, den die Momentaufnahme braucht.      Bewusst ein pass, Hinterlegt die Funktion, die den aktuellen GUI-Zustand liefert., Wartezimmer-Anzeige: Mini-Webserver, der den aktuellen Fotografier-Fortschritt a, Der GUI-Zustand, aus dem der Controller seine Momentaufnahme baut.          Klas, test_default_context_is_idle()

### Community 29 - "Display Page & Handler"
Cohesion: 0.24
Nodes (6): Die Browser-Seite der Wartezimmer-Anzeige.  Als Python-String eingebettet - glei, Die fertige Seite als UTF-8-Bytes., render_page(), _Handler, Mini-Webserver fuer die Wartezimmer-Anzeige.  Nur Standardbibliothek (``http.ser, BaseHTTPRequestHandler

### Community 30 - "Camera Fallback Tests"
Cohesion: 0.24
Nodes (8): FlakyOpenCVCamera, Tests for MainController's camera init/fallback logic., Stand-in for OpenCVCamera: configured index always fails to open,     even thoug, If the configured device index IS among the detected cameras but just     failed, If the configured index doesn't exist on this machine at all (e.g. a     laptop, _settings(), test_missing_device_falls_back_to_detected_camera(), test_transient_open_failure_does_not_switch_or_persist_device()

### Community 31 - "Display Snapshot Tests"
Cohesion: 0.25
Nodes (11): context(), make_learners(), Beim Aufblenden der URL muss die Seite schon Inhalt haben - es wird     einmal s, *names* sind Vornamen; der Nachname ist 'Nachname<N>'., state_of(), test_context_without_roster_is_idle(), test_finished_class_is_reported_as_done(), test_provider_can_be_replaced_after_start() (+3 more)

### Community 32 - "Storage Key Characterization"
Cohesion: 0.20
Nodes (10): Der Dateiname-Stamm, unter dem ein Foto zu dieser ID wirklich landet.      Bewus, storage_key(), parametrize, openpyxl liefert fuer 12345.0 ein int, nicht ein float.      Waere es ein float,, test_a_whole_number_cell_does_not_grow_a_decimal_tail(), Der Kern des Problems, in einer Zeile.      Das ist kein konstruierter Extremfal, Beweist, dass die Kollision nicht theoretisch ist.      ``unique_file_path`` ueb, test_five_different_ids_map_to_the_same_file_name() (+2 more)

### Community 33 - "Photo Saving & Jump Tests"
Cohesion: 0.51
Nodes (9): prepare(), test_add_person_file_naming(), test_jump_to_person_file_names(), test_jump_to_person_retake_preserves_selection(), test_jump_to_person_returns_to_first_unphotographed(), test_normal_photo_saved_with_student_id(), test_retake_photo_preserves_student_id(), test_skip_then_next_photo_has_correct_id() (+1 more)

### Community 34 - "GPhoto2 Backend"
Cohesion: 0.31
Nodes (3): GPhoto2Camera, Path, QImage

### Community 35 - "README Feature Overview"
Cohesion: 0.22
Nodes (8): Test mode (roster generation + session-only output redirect), Build Windows release workflow (PyInstaller --onedir), Pre-generate comtypes wrappers packaging step, Identity Card Photo Creator (PySide6 desktop app), Excel-Roster als Datenquelle (Standort/Klasse/Lernende), Feature list (Excel roster, live preview, test mode, ZIP bundling), Simulator-Modus (kein Kamera-Hardware nötig), Automatische ZIP-Bündelung pro Klasse

### Community 36 - "Simulator Camera"
Cohesion: 0.32
Nodes (3): Path, QImage, SimulatorCamera

### Community 37 - "Embedded Icons"
Cohesion: 0.32
Nodes (7): Display browser page (embedded HTML constant), github_icon(), icon(), Return the named icon as a QIcon (cached). Unknown names yield a null     QIcon, Return the GitHub mark as a QIcon., No external resources / embed everything in Python, QIcon

### Community 38 - "Missed-Entry Writer"
Cohesion: 0.46
Nodes (4): MissedEntry, MissedWriter, Path, test_missed_reason()

### Community 39 - "Output Audit Tool"
Cohesion: 0.36
Nodes (6): main(), mapping(), pruefe(), Path, Gleicht die abgelegten Fotos gegen die Excel-Liste ab. Aendert nichts.  Warum da, Die Spaltenzuordnung aus der echten settings.json, nicht geraten.

### Community 40 - "ZIP Chunking"
Cohesion: 0.43
Nodes (5): chunk_by_count(), Path, Archive *files* into one or more ZIPs with at most *max_count* entries., test_chunk(), test_single_chunk()

### Community 41 - "Capture Lock Context"
Cohesion: 0.29
Nodes (3): _LockCtx, Bounded-acquire context manager for the capture lock (mirrors     OpenCVCamera):, RLock

### Community 42 - "Filename Identity Rules"
Cohesion: 0.29
Nodes (7): planned_photo_path, sanitize_name, target_file_path, unique_file_path, Ask before overwrite (Abbrechen as default button), The filename IS the identity, sanitize_name is not injective

### Community 43 - "Display Timer Tests"
Cohesion: 0.33
Nodes (6): Die Anzeige darf sich niemals von selbst starten., Der Timer gehoert dem Controller; er wird ueber die Qt-Objekthierarchie     gesu, test_timer_exists_but_is_idle_before_start(), test_timer_runs_while_started_and_stops_again(), test_timer_stays_inactive_after_a_failed_start(), timer_of()

### Community 44 - "Display Test Fixtures"
Cohesion: 0.40
Nodes (5): controller(), fixture, Die gemeinsamen Settings aus conftest.py, auf die Anzeige zugeschnitten.      Gl, qtbot liefert die QApplication; der Teardown stoppt den Server immer,     damit, settings()

### Community 46 - "Display URL Resolution"
Cohesion: 0.50
Nodes (3): local_addresses(), Alle brauchbaren URLs zum Oeffnen der Anzeige.          Im lokalen Modus ist das, Vermutliche LAN-IPv4-Adressen dieses Rechners, beste zuerst.      Der Rueckgabew

### Community 47 - "Shared Test Fixture Policy"
Cohesion: 0.50
Nodes (4): Onboarding .onboarded marker decision, Pass config_dir as argument, not via import, One shared test double, never a second copy, Shared test fixtures (settings, DummyCamera, main_window_factory)

### Community 48 - "Display Port Restart Tests"
Cohesion: 0.50
Nodes (4): free_port(), Nach einer Aenderung in den Einstellungen muss der laufende Server den     Socke, Ein garantiert freier Port auf Loopback (Socket wird sofort geschlossen)., test_restart_on_a_changed_endpoint()

### Community 49 - "Camera Probing Fixture"
Cohesion: 0.67
Nodes (3): probing_path(), fixture, Force list_cameras() down the DirectShow-probing fallback.      On Windows list_

## Knowledge Gaps
- **15 isolated node(s):** `app.version.__version__`, `app/main.py (entry point)`, `app/ui/widgets/control_panel.ui`, `icon.ico (app icon)`, `PyInstaller (--onedir packager)` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DisplayController` connect `Display Controller Lifecycle` to `MainWindow Capture Flow`, `Controller Photo Paths`, `Settings Snapshot & Diff`, `Display Snapshot State`, `Display Controller Tests`, `Display Test Fixtures`, `Display Server Surface`, `MainController Service Layer`, `Display Context Boundary`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow Capture Flow` to `Settings Diff & Test Doubles`, `Photo Saving & Jump Tests`, `Settings Schema`, `Onboarding Gate`, `Embedded Icons`, `Controller Photo Paths`, `Sidebar & Live View Widgets`, `Display Controller Lifecycle`, `Shared Test Fixture Policy`, `Display Context Boundary`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Why does `Learner` connect `Learner Loading & UI Tests` to `MainWindow Capture Flow`, `Photo Saving & Jump Tests`, `README Feature Overview`, `Onboarding Gate`, `Controller Photo Paths`, `Output Audit Tool`, `Display Snapshot State`, `SchuelerID Conflict Detection`, `Display Controller Tests`, `MainController Service Layer`, `Display Snapshot Tests`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `MainWindow` (e.g. with `Tastenkürzel (Space / Esc / S / A / F)` and `DummyCamera`) actually correct?**
  _`MainWindow` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `MainController` (e.g. with `IdConflict` and `FlakyOpenCVCamera`) actually correct?**
  _`MainController` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `OpenCVCamera` (e.g. with `DirectShowCamera` and `BaseCamera`) actually correct?**
  _`OpenCVCamera` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `app.version.__version__`, `app/main.py (entry point)`, `app/ui/widgets/control_panel.ui` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._

---

<!-- HANDGESCHRIEBEN. Alles darüber erzeugt graphify neu; dieser Abschnitt wird
     beim nächsten `--update` überschrieben. Die dauerhafte Fassung steht in
     CLAUDE.md unter "Was die Zentralität von DisplayController bedeutet". -->

## Nachgetragen: warum `DisplayController` so zentral ist (2026-08-19)

Der Bericht listet `DisplayController` mit der höchsten Betweenness des Graphen
(0.135, knapp vor `MainWindow` mit 0.134) und fragt oben, warum. Nachgetragen,
weil die Antwort das Gegenteil der üblichen Lesart ist.

**Es ist keine Reichweite, sondern Unersetzlichkeit.** `DisplayController` hat
28 Kanten, `MainWindow` hat 58 — also weniger als die Hälfte. Nur 12 dieser 28
verlassen die eigene Community, und sie landen genau dort, wo die Naht aus #43
gezogen wurde:

- `references DisplayServer` (der Server darunter)
- `calls build_snapshot()` (die reine Funktion daneben)
- `references MainController` / `calls __init__` (der Besitzer darüber)
- `shares_data_with MainWindow` + `set_context_provider()` (der Rückkanal zur GUI)

Sonst nichts. Eine schmale Schnittstelle, die zufällig zwischen vier Subsystemen
sitzt, die sonst nie miteinander sprechen.

**Der Test dazu.** Entfernt man den Knoten aus der Hauptkomponente (943 Knoten),
fallen 18 Knoten heraus — bei `MainWindow` nur 11. Halber Grad, mehr
struktureller Schaden. Die 18 sind ausnahmslos die eigenen Methoden des
Controllers: `publish()`, `stop()`, `restart_if_endpoint_changed()`,
`endpoint()`, `urls()`, `running()`, `port()`, `local_only()`. Nichts sonst
erreicht sie. `MainWindow` ruft die Klasse, und die Klasse allein erreicht ihr
Innenleben.

**Wie das zu lesen ist.** Hohe Zentralität heisst hier *nicht*, dass ein neuer
Gott-Knoten entstanden ist. Vor #43 lag dieser Lebenszyklus als lose Methoden im
`MainWindow`: von überall erreichbar und von nirgends testbar. Jetzt ist es eine
Tür mit genau einem Türsteher — deshalb isoliert das Entfernen des Türstehers den
Raum, und deshalb ist die Betweenness trotz bescheidenem Grad hoch.
`MainWindow`s 58 Kanten sind der umgekehrte Fall: viel Grad, redundante Pfade,
wenig strukturelle Notwendigkeit pro Kante.

**Messhinweis für den nächsten, der das nachrechnet:** der Graph zerfällt schon
ohne jeden Eingriff in 17 Komponenten (grösste: 943 Knoten). Wer `remove_node`
auf dem *ganzen* Graphen rechnet, zählt diese vorbestehenden Inseln als Schaden
mit und bekommt viel zu grosse Zahlen heraus. Immer gegen die Hauptkomponente
messen.
