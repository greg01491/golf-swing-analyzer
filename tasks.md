# Tasks: Golf Swing Analyzer — Audio-Triggered Capture & 3D Pose Analysis

**Derived from:** `plan.md`
**Status:** Draft v1 — check items off as completed

## Phase 0 — Project & Repo Setup
- [x] Create GitHub repo (`golf-swing-analyzer`), default branch, `.gitignore` (Python + Node)
- [x] Create folder structure: `backend/`, `frontend/`, `docs/`, `config/`, `data/`
- [x] Set up Python environment + dependency manager (venv or poetry)
- [x] Set up Electron/React app scaffold in `frontend/`
- [x] Add base `config/config.yaml` (or `.json`) with placeholders for all configurable parameters from spec §7
- [x] Add lint/format tooling (e.g. ruff/black for Python, eslint/prettier for JS)
- [x] Add minimal CI (lint + placeholder test run)
- [x] Write `CONTRIBUTING.md`/constitution notes: module boundaries, coding conventions

## Phase 1 — Dual-Camera Capture Pipeline
- [x] Enumerate connected USB cameras; build a simple camera-selection config
- [x] Implement per-camera capture stream (resolution/FPS configurable)
- [x] Implement rolling buffer per camera (size = capture duration + margin, configurable — see spec.md FR6 correction)
- [x] Implement "extract window" function: given trigger time, pre-capture delay, duration → produce clip from buffer
- [x] Implement session folder writer (video files + metadata.json: timestamp, settings, camera IDs)
- [x] Add manual "capture now" trigger (dev/test button or CLI command) — `python -m golf_sim.capture.cli [--synthetic]`
- [x] Verify two-camera timestamp sync approach (e.g. shared clock / sync test using a clap or flash) — shared time.monotonic() clock implemented + validated with synthetic sources; `golf_sim.capture.sync_check` tool built for a real-hardware clap/flash test (**still needs running against actual USB cameras** — no physical rig available in this dev environment)
- [x] Write test: manual trigger produces two correctly-windowed clips

## Phase 2 — Audio Trigger Service
- [x] Implement mic input stream reader — real (sounddevice) + synthetic sources, mirroring the capture module's pattern
- [x] Implement level detection (RMS/dB) over a rolling window
- [x] Add configurable trigger threshold
- [x] Add configurable pre-capture delay (default 1.0s) and capture duration — reused from Phase 1 config; `capture_now()` now accepts an explicit `trigger_time` so the audio-detected instant (not a fresh timestamp) anchors the window
- [x] Add configurable trigger cooldown period (debounce)
- [x] Wire trigger event → Phase 1 "extract window" + save session
- [x] Build simple calibration helper (record ambient + sample impact sounds, suggest threshold) — `golf_sim.audio.calibration`
- [x] Add manual arm/disarm control — `golf_sim.audio.cli listen` (a/d commands)
- [x] Add manual re-trigger fallback (in case auto-detect misses) — `listen`'s `t` command, bypasses threshold/cooldown but still resets the cooldown window
- [ ] Test in real conditions: impact sound vs. talking/ambient noise — tune default threshold/cooldown — **still needs the real golf-sim room + an actual club/impact sound**; no physical rig available in this dev environment
- Found while testing on real hardware: the system-default mic input (`device: null`) can fail outright (PortAudio "no driver installed" over MME) even when the hardware itself is fine — a specific WASAPI device index worked where the default didn't. Added `golf_sim.audio.cli devices` to list candidates; config.yaml's `device` comment now points users at it instead of trusting the OS default blindly.

## Phase 3 — 2D Pose Estimation per Camera
- [x] ~~Spike A: shortlist 1-2 open-source pose models~~ — resolved: adopt Pose2Sim (BSD-3-Clause), RTMPose default backend
- [x] Add `pose2sim` as an optional dependency (`backend/pyproject.toml` `pose` extra); install when starting this phase — installed v0.10.49
- [x] Integrate Pose2Sim's 2D pose stage into a per-camera processing step in `backend/pose/` — session→Pose2Sim-project adapter (`pose/project.py`) + `run_pose_estimation` (`pose/estimate.py`) + `python -m golf_sim.pose.cli <session>|--latest`
- [x] Run pose estimation over a saved session's two clips → landmark sequences (per-frame, per-camera) — validated end-to-end on Pose2Sim demo footage (real human motion): 100/100 frames landmarked per camera, HALPE_26 keypoints, mean confidence 0.81
- [x] Store landmark sequences alongside session — kept in Pose2Sim's native layout (`<session>/pose2sim/pose/camera_N_json/`) deliberately, since Phase 4's triangulation stages consume that exact structure
- [x] Build a debug overlay video (landmarks drawn on original frames) for visual QA — free via Pose2Sim's `save_video='to_video'` (config.yaml `pose.save_debug_video`); visually verified skeleton locked on subject mid-motion
- [x] Benchmark processing time; confirm within NFR3 target — 17.1s for 2×100 frames with cached models on this machine (**CPU-only** onnxruntime); extrapolates to ~31s for a real 3s/60fps two-camera swing, inside NFR3's "well under a minute". Optimization headroom if wanted later: swap in `onnxruntime-directml` for AMD-GPU acceleration on Windows, or drop `pose.mode` to `lightweight`
- Note from demo footage: RTMPose detected a *second* person in the background — Pose2Sim's `personAssociation` stage (Phase 4) is what picks the subject; don't skip it even for a single-golfer setup

## Phase 4 — Camera Calibration & 3D Triangulation
- [x] Set up physical rig: down-the-line (behind golfer) + face-on (side) — **done 2026-07-18**: cameras identified by DirectShow name ("PC Camera" = camera_1/down-the-line, "HD USB Camera" = camera_2/face-on)
- [x] Design calibration capture routine — **superseded Pose2Sim's board-based extrinsics** (needs a board far larger than A4 at golf-rig camera distances) **with an in-app guided wizard**: `pose/rig_calibration.py` (per-camera intrinsics via `cv2.calibrateCamera` on close-up board shots) + person-keypoint extrinsics (essential-matrix relative pose from matched 2D pose keypoints across both cameras during a synced capture of someone standing/swinging at the hitting position, scaled to real-world metres via a user-measured camera-to-camera distance). Math validated against synthetic cameras with known ground truth: rotation recovered to <1°, translation to <5cm (`test_rig_calibration.py`)
- [x] Implement calibration computation (relative camera pose/intrinsics) — `pose/wizard.py compute_rig_calibration()`: runs both intrinsics, pose-estimates the extrinsics capture, solves relative pose, writes `Calib_rig.toml` in Pose2Sim's expected format
- [x] Store calibration result (reusable until camera moves) — rig calibration lives in `config/calibration/` (gitignored, machine-specific), auto-installed into each session's project before triangulation
- [x] Implement triangulation via Pose2Sim: personAssociation → triangulation → Butterworth filtering in `pose/reconstruct.py`; output TRC (+c3d) stored with session in `pose2sim/pose-3d/` (FR15). Validated end-to-end on demo footage: 100/100 frames triangulated, 14.5s for the 3D stages
- [x] Build the in-app calibration wizard UI (`frontend/src/components/CalibrationWizard.tsx`) — live per-camera preview (polled JPEG snapshots via new `/api/capture/preview/{camera}`), a 3-second countdown before each capture so the user has time to get in position/pose the board, running board-detection feedback per capture, a "distance between cameras" input, and a compute step with live progress + final reprojection-error/keypoint-match summary. Verified live in-browser against the real rig: countdown fires, capture completes, board-detection feedback updates correctly (0/6 when no board present, as expected)
- [x] Check whether our own Phase 1/2 trigger-timestamp sync is sufficient — **yes, confirmed on real hardware**: manual/wizard captures on the actual rig produce identical, aligned frame counts per camera (see the resample-to-grid fix below)
- [x] Build a simple 3D landmark playback/plot to sanity-check output against real motion — `python -m golf_sim.pose.viewer <trc>` renders a sampled-frame skeleton grid; verified anatomically-coherent motion on demo output (known cosmetic issue: z-axis renders inverted)
- [ ] Real-footage occlusion check (spec.md OQ4): confirm the down-the-line + face-on pair isn't losing key joints (e.g. trail arm) during the swing; revisit rig angle if it is — **still needs a real completed calibration + real swing** to check
- [x] Add a "recalibration needed" check — `calibration_status()`: missing or older than `calibration.max_age_days` (config.yaml) → flagged; `python -m golf_sim.pose.cli status` and `/api/calibration/info`
- Integration gotcha worth remembering: Pose2Sim stages anchor their directory search on the *location of a Config.toml* (falling back to cwd), even when driven by a config dict — so `prepare_pose_project` installs a copy of the packaged default Config.toml into every session project. Removing it breaks personAssociation/triangulation in ways that look like a missing-calibration error.
- **Real-rig bring-up findings (2026-07-18), all fixed and tested:**
  - Mic needed the device's *native* samplerate (48kHz WASAPI), not the hardcoded 44100 — `SounddeviceMicSource` now queries the device default.
  - One camera's driver delivered reads at ~2x real speed (duplicated frames); `capture/resample.py` now snaps every window onto an exact fps grid per camera so both cameras always produce identical, time-aligned frame counts — required because triangulation pairs cameras by frame index.
  - **Windows does not keep DirectShow camera indices stable across processes** — the same physical camera was index 0 in one process and the laptop's webcam in the next, which silently recorded the wrong camera with no error. Cameras are now selected by DirectShow device *name* (`capture/source.py resolve_camera_index`, via `pygrabber`), with the numeric `id` kept only as fallback.
  - After long continuous streaming both USB cameras were observed to stall into delivering solid-black frames while otherwise reporting healthy; `CameraStream` now detects a run of all-black frames and reopens the device automatically.
  - Session folders renamed to readable local time (`2026-07-18_18-29-41_xxxx`) instead of compact UTC, per request; UI shows a friendly time + date instead of the raw id.

## Phase 5 — Swing Metrics Engine
- [x] Finalize metric list: shoulder_turn_deg, hip_turn_deg, x_factor_deg, spine_tilt_deg (at address), tempo_ratio, hip_sway_top_pct + hip_sway_impact_pct (weight-transfer proxy, % of stance width). All angles reported as magnitudes → handedness-neutral
- [x] Implement each metric's computation from the 3D landmark sequence — `analysis/metrics.py`, built on a body-anchored reference frame (`analysis/frame_of_reference.py`) that infers the vertical axis from ankle→head separation, so nothing assumes which calibrated world axis is up or where the target line is
- [x] Swing phase detection (address/top/impact) from the hand-midpoint trajectory — `analysis/phases.py`; relative-quantity heuristics only (fractions of peak speed, per-clip extrema) so it's invariant to units/frame rate/position
- [x] Add configurable reference ranges per metric — config.yaml `metrics.reference_ranges`; metrics without a range are computed but never flagged
- [x] Implement "flag out-of-range" logic
- [x] Output a structured metrics report (JSON) per session — `python -m golf_sim.analysis.cli <session>|--latest` → `<session>/metrics.json`
- [x] Write tests against known swings — synthetic swing generator with controlled ground truth (90° shoulder turn, 45° hip turn, 3:1 tempo, known spine tilt); computed metrics match within tolerance. Chain also smoke-tested on the demo session's real 3D data: runs end-to-end, and correctly flags everything out-of-range since the demo subject isn't swinging a golf club
- Real-swing validation of phase-detection heuristics + reference-range defaults still needs actual swing captures from your rig (same dependency as the Phase 4 hardware items)

## Phase 6 — Tips Engine
- [x] Define rule set mapping flagged metrics → candidate tip text — `analysis/tips.py`: per-metric too-low/too-high wording; low hip-sway deliberately has no tip (it isn't a fault)
- [x] Implement tip selection/prioritization — severity = deviation normalized by reference-range width, ranked, top-3 (configurable via `max_tips` arg)
- [x] Output ranked tips list per session — included in `metrics.json` (`tips` array) and the analysis CLI printout
- [ ] Review tip wording for clarity/usefulness (manual pass) — **your call, Greg**: read the tip texts in `backend/src/golf_sim/analysis/tips.py` and edit any wording that doesn't sound like advice you'd actually want

## Phase 7 — Review UI
- [x] Session browser screen (list past sessions, timestamps + 3D/metrics badges)
- [x] Playback screen: video player (camera tabs) + canvas 3D skeleton animation synced to video time, with azimuth rotation slider
- [x] Metrics panel (numbers + flagged/OK indicators + reference ranges)
- [x] Tips panel (ranked list)
- [x] Settings screen: trigger threshold, pre-capture delay, capture duration, cooldown, camera settings
- [x] Settings screen: metric reference ranges (editable)
- [x] Arm/disarm control + live mic level meter + manual capture button in the header
- [x] Wire frontend to backend via local API — FastAPI (`python -m golf_sim.api.server`, port from config.yaml) + Vite dev proxy; endpoints for sessions/video/landmarks/process/config/capture-control. Config saves go through ruamel.yaml round-trip so config.yaml's comments survive UI edits (plain yaml.safe_dump destroyed them — caught during browser verification)
- [x] "Process swing" button runs pose → 3D → metrics in a background thread with status polling, for sessions captured before processing
- [x] Browser-verified against the demo session: session list, camera tabs, metrics table with flags, ranked tips, settings round-trip (value saved to disk, comments intact), and graceful missing-camera error surfaced in UI
- [ ] End-to-end manual test: swing → capture → processing → browse → playback with tips — **needs your rig**; every stage is verified individually but nobody has hit a real ball yet
- Dev workflow: `python -m golf_sim.api.server` in one terminal, `npm run dev` (browser) or `npm run electron:dev` (desktop shell) in another

## Phase 8 — Hardening & Packaging
- [ ] Run extended real-world test sessions (multiple rooms/noise levels); log false triggers/misses — **needs your rig**
- [ ] Tune default threshold/delay/duration/cooldown based on test data — **needs your rig**
- [x] Add error handling/recovery for: camera disconnect (stream survives + backs off + reports unhealthy, surfaced as "camera_N not responding" in the UI header), mic disconnect (listener thread survives, retries at 1Hz, error surfaced in UI), failed pose estimation (process endpoint reports `error: ...`), corrupt session metadata (skipped gracefully, listing keeps working). All covered by tests (`test_hardening.py`)
- [x] Write setup/calibration/troubleshooting docs — [docs/setup.md](docs/setup.md): install, rig placement, device selection (incl. the WASAPI mic finding), threshold + checkerboard calibration walkthroughs, first-time sync/occlusion validation, troubleshooting table
- [x] Windows installer config — electron-builder NSIS target (`npm run electron:build` → `frontend/release/`). **Honest caveat:** the installer packages the UI only; the Python backend still runs from its venv (`python -m golf_sim.api.server`). Bundling the backend (PyInstaller + auto-spawn from Electron) is deferred — worth doing only once the rig workflow has settled
- [x] Final pass: confirm every parameter in spec §7 is genuinely configurable — audited: threshold/delay/duration/cooldown/camera-res-fps/metric-ranges all flow from config.yaml with no hardcoded copies (grep-verified); also fixed packaged-app networking (file:// origin → absolute API base + CORS on the localhost server)

## Backlog / Deferred (not scheduled — see spec Non-Goals)
- [ ] Full 3D mesh (SMPL-style) reconstruction option
- [ ] Club tracking / ball flight data integration
- [ ] Cloud sync / multi-device support
- [ ] Live in-swing feedback
- [ ] macOS support
