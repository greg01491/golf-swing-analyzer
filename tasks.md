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
- [ ] Enumerate connected USB cameras; build a simple camera-selection config
- [ ] Implement per-camera capture stream (resolution/FPS configurable)
- [ ] Implement rolling buffer per camera (size = pre-capture delay + margin, configurable)
- [ ] Implement "extract window" function: given trigger time, pre-capture delay, duration → produce clip from buffer
- [ ] Implement session folder writer (video files + metadata.json: timestamp, settings, camera IDs)
- [ ] Add manual "capture now" trigger (dev/test button or CLI command)
- [ ] Verify two-camera timestamp sync approach (e.g. shared clock / sync test using a clap or flash)
- [ ] Write test: manual trigger produces two correctly-windowed clips

## Phase 2 — Audio Trigger Service
- [ ] Implement mic input stream reader
- [ ] Implement level detection (RMS/dB) over a rolling window
- [ ] Add configurable trigger threshold
- [ ] Add configurable pre-capture delay (default 1.0s) and capture duration
- [ ] Add configurable trigger cooldown period (debounce)
- [ ] Wire trigger event → Phase 1 "extract window" + save session
- [ ] Build simple calibration helper (record ambient + sample impact sounds, suggest threshold)
- [ ] Add manual arm/disarm control
- [ ] Add manual re-trigger fallback (in case auto-detect misses)
- [ ] Test in real conditions: impact sound vs. talking/ambient noise — tune default threshold/cooldown

## Phase 3 — 2D Pose Estimation per Camera
- [x] ~~Spike A: shortlist 1-2 open-source pose models~~ — resolved: adopt Pose2Sim (BSD-3-Clause), RTMPose default backend
- [ ] Add `pose2sim` as an optional dependency (`backend/pyproject.toml` `pose` extra); install when starting this phase
- [ ] Integrate Pose2Sim's 2D pose stage into a per-camera processing step in `backend/pose/`
- [ ] Run pose estimation over a saved session's two clips → landmark sequences (per-frame, per-camera)
- [ ] Store landmark sequences alongside session (e.g. `landmarks_cam1.json`, `landmarks_cam2.json`)
- [ ] Build a debug overlay video (landmarks drawn on original frames) for visual QA
- [ ] Benchmark processing time on target laptop GPU; confirm within NFR3 target

## Phase 4 — Camera Calibration & 3D Triangulation
- [ ] Set up physical rig: down-the-line (behind golfer) + face-on (side), ~90° apart (spec.md FR11a)
- [ ] Design calibration capture routine using Pose2Sim's checkerboard/charuco calibration (shown to both cameras)
- [ ] Implement calibration computation (relative camera pose/intrinsics) via Pose2Sim
- [ ] Store calibration result (reusable until camera moves)
- [ ] Implement triangulation via Pose2Sim: paired 2D landmarks (per camera, per frame) → 3D landmark per frame
- [ ] Check whether our own Phase 1/2 trigger-timestamp sync is sufficient, or whether Pose2Sim's sync stage (keypoint-correlation or clap/flash) is still needed
- [ ] Build a simple 3D landmark playback/plot (even a basic viewer) to sanity-check output against real motion
- [ ] Real-footage occlusion check (spec.md OQ4): confirm the down-the-line + face-on pair isn't losing key joints (e.g. trail arm) during the swing; revisit rig angle if it is
- [ ] Add a "recalibration needed" check (e.g. flag if calibration file missing/stale)

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
