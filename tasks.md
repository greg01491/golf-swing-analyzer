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
- [ ] Set up physical rig: down-the-line (behind golfer) + face-on (side), ~90° apart (spec.md FR11a) — **needs your hardware**
- [x] Design calibration capture routine using Pose2Sim's checkerboard calibration — `pose/calibrate.py` `run_checkerboard_calibration()` + `python -m golf_sim.pose.cli calibrate`; expects checkerboard footage in `config/calibration/{intrinsics,extrinsics}/` per its docstring layout. **Running it against real footage needs the physical rig + a printed checkerboard**
- [x] Implement calibration computation (relative camera pose/intrinsics) via Pose2Sim — validated using the demo's Qualisys calibration converted to Calib.toml
- [x] Store calibration result (reusable until camera moves) — rig calibration lives in `config/calibration/` (gitignored, machine-specific), auto-installed into each session's project before triangulation
- [x] Implement triangulation via Pose2Sim: personAssociation → triangulation → Butterworth filtering in `pose/reconstruct.py`; output TRC (+c3d) stored with session in `pose2sim/pose-3d/` (FR15). Validated end-to-end on demo footage: 100/100 frames triangulated, 14.5s for the 3D stages
- [ ] Check whether our own Phase 1/2 trigger-timestamp sync is sufficient, or whether Pose2Sim's sync stage is still needed — **needs real dual-camera captures**; demo footage is pre-synced so this couldn't be exercised
- [x] Build a simple 3D landmark playback/plot to sanity-check output against real motion — `python -m golf_sim.pose.viewer <trc>` renders a sampled-frame skeleton grid; verified anatomically-coherent motion on demo output (known cosmetic issue: z-axis renders inverted)
- [ ] Real-footage occlusion check (spec.md OQ4): confirm the down-the-line + face-on pair isn't losing key joints (e.g. trail arm) during the swing; revisit rig angle if it is — **needs real swing footage from your rig**
- [x] Add a "recalibration needed" check — `calibration_status()`: missing or older than `calibration.max_age_days` (config.yaml) → flagged; `python -m golf_sim.pose.cli status`
- Integration gotcha worth remembering: Pose2Sim stages anchor their directory search on the *location of a Config.toml* (falling back to cwd), even when driven by a config dict — so `prepare_pose_project` installs a copy of the packaged default Config.toml into every session project. Removing it breaks personAssociation/triangulation in ways that look like a missing-calibration error.

## Phase 5 — Swing Metrics Engine
- [ ] Finalize metric list (e.g. shoulder turn angle, hip turn angle, spine tilt, X-factor, tempo ratio, weight transfer proxy)
- [ ] Implement each metric's computation from the 3D landmark sequence
- [ ] Add configurable reference ranges per metric (defaults + user-editable)
- [ ] Implement "flag out-of-range" logic
- [ ] Output a structured metrics report (JSON) per session
- [ ] Write tests against a few known/sample swings (sanity values)

## Phase 6 — Tips Engine
- [ ] Define rule set mapping flagged metrics → candidate tip text
- [ ] Implement tip selection/prioritization (e.g. top 3 most significant deviations)
- [ ] Output ranked tips list per session
- [ ] Review tip wording for clarity/usefulness (manual pass)

## Phase 7 — Review UI
- [ ] Session browser screen (list past sessions, thumbnails/timestamps)
- [ ] Playback screen: video player synced with 3D skeleton animation
- [ ] Metrics panel (numbers + flagged/OK indicators)
- [ ] Tips panel (ranked list)
- [ ] Settings screen: trigger threshold, pre-capture delay, capture duration, cooldown, camera settings
- [ ] Settings screen: metric reference ranges (editable)
- [ ] Arm/disarm control + live mic level indicator (so user can see it's listening)
- [ ] Wire frontend to backend via local API/WebSocket
- [ ] End-to-end manual test: swing → capture → processing → browse → playback with tips

## Phase 8 — Hardening & Packaging
- [ ] Run extended real-world test sessions (multiple rooms/noise levels); log false triggers/misses
- [ ] Tune default threshold/delay/duration/cooldown based on test data
- [ ] Add error handling/recovery for: camera disconnect, mic disconnect, failed pose estimation, corrupt session
- [ ] Write setup/calibration/troubleshooting docs
- [ ] Build Windows installer/package
- [ ] Final pass: confirm every parameter in spec §7 is genuinely configurable, not hardcoded

## Backlog / Deferred (not scheduled — see spec Non-Goals)
- [ ] Full 3D mesh (SMPL-style) reconstruction option
- [ ] Club tracking / ball flight data integration
- [ ] Cloud sync / multi-device support
- [ ] Live in-swing feedback
- [ ] macOS support
