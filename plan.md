# Plan: Golf Swing Analyzer — Audio-Triggered Capture & 3D Pose Analysis

**Derived from:** `spec.md` (001-audio-triggered-capture-and-analysis)
**Status:** Draft v1

## 1. Goal Summary

Deliver a working local pipeline: mic-triggered dual-camera capture → 3D pose reconstruction → swing metrics → tips → review UI. Built incrementally so each phase produces something demonstrable/testable before moving on.

## 2. Guiding Principles

- Get one **vertical slice** working end-to-end early (even with rough thresholds and no calibration UI), then improve each stage.
- Keep the audio-trigger, capture, pose, and analysis stages as independent services/modules with clear data contracts between them, so any one can be swapped later (e.g. mesh model instead of skeleton) without touching the others.
- Everything configurable per FR/NFR in the spec goes into a single config file from day one, not scattered constants.

## 3. Phases

### Phase 0 — Project & Repo Setup
- Initialize GitHub repo, base folder structure (`backend/`, `frontend/`, `docs/`, `config/`, `data/`).
- Set up Python environment (venv/poetry), base dependencies (audio I/O, camera capture, pose model, GPU stack).
- Set up Electron/React scaffold.
- Add `constitution`/contribution notes (coding conventions, module boundaries) so future spec/plan/tasks cycles stay consistent.
- **Exit criteria:** repo runs a "hello world" for both backend and frontend; CI lint/test stub in place.

### Phase 1 — Dual-Camera Capture Pipeline
- Enumerate and select two USB cameras; configurable resolution/FPS.
- Implement synchronized rolling buffer (in-memory or ring-buffer to disk) sized to cover pre-capture delay + margin.
- Implement "save capture" — given a trigger time, delay, and duration, extract the correct window from both camera buffers into a session folder.
- **Exit criteria:** manual "capture now" button saves two synced video clips to a session folder.

### Phase 2 — Audio Trigger Service
- Mic input stream + level (dB/RMS) monitoring.
- Configurable threshold, pre-capture delay, capture duration, cooldown.
- Wire trigger event into the Phase 1 capture pipeline (replacing/augmenting the manual button).
- Basic calibration helper (e.g. "make some impact sounds, we'll suggest a threshold").
- **Exit criteria:** a loud noise (e.g. clap, club strike) reliably produces a correctly-bracketed saved clip; false triggers from ambient noise are rare at default settings.

### Phase 3 — 2D Pose Estimation per Camera
- **Decided (was Spike A):** use [Pose2Sim](https://github.com/perfanalytics/pose2sim) (BSD-3-Clause) as the pose backend rather than integrating a raw model ourselves — it wraps RTMPose (default) with MediaPipe/OpenPose as swappable alternates, and already outputs the per-camera 2D landmark format its own calibration/triangulation stages expect.
- Wire it into a per-camera processing step in `backend/pose/`: run Pose2Sim's 2D pose stage over each saved session's two clips.
- Store landmark sequences alongside each session.
- **Exit criteria:** given a saved session, produce a 2D landmark overlay video per camera for visual sanity-checking.

### Phase 4 — Camera Calibration & 3D Triangulation
- Camera rig: **down-the-line** (behind golfer, along target line) + **face-on** (side, perpendicular) — a ~90° pair. This is Pose2Sim's documented "acceptable" 2-camera configuration (their "optimal" is 45°); the tradeoff is higher self-occlusion risk for some joints during the swing, not degraded triangulation math.
- Build calibration workflow using Pose2Sim's checkerboard/charuco calibration (compute relative camera pose/intrinsics) rather than hand-rolling OpenCV calibration.
- Use Pose2Sim's synchronization + DLT triangulation of synced 2D landmark pairs into 3D landmark sequences. Our own capture pipeline already tags both camera streams with a shared trigger timestamp (Phase 1/2), so Pose2Sim's audio/keypoint-correlation sync step may be redundant — confirm during implementation and only fall back to it if our own timestamp sync proves insufficient.
- **Exit criteria:** a captured swing produces a 3D landmark sequence that visibly matches the recorded motion when plotted/played back, **and** a real-footage check confirms the down-the-line + face-on pair isn't losing key joints to self-occlusion during the swing (OQ4) — if it is, revisit rig angle before locking it in.

### Phase 5 — Swing Metrics Engine
- Define the finalized metric list (e.g. shoulder turn, hip turn, spine tilt, X-factor, tempo ratio, weight transfer proxy) and how each is computed from the 3D landmark sequence.
- Implement metric computation over the swing window.
- Add configurable "reference ranges" per metric.
- **Exit criteria:** given a 3D landmark sequence, output a metrics report (numbers + in/out-of-range flags).

### Phase 6 — Tips Engine
- Rule-based mapping from flagged metrics → plain-English tips (start simple/rule-based; leave room for a smarter model later).
- Select/prioritize top N tips per swing.
- **Exit criteria:** given a metrics report, output a ranked list of tips.

### Phase 7 — Review UI
- Session browser (list of past swings).
- Playback view: video + 3D skeleton animation, synced.
- Metrics + tips panel.
- Settings screens for all configurable parameters (§7 of spec).
- **Exit criteria:** user can record a real swing, wait for processing, then browse to it and see video, skeleton, metrics, and tips together.

### Phase 8 — Hardening & Packaging
- End-to-end testing with a range of real swings/environments (different rooms, ambient noise levels).
- Tune defaults (threshold, delay, duration, cooldown) based on real test data.
- Packaging (installer) for the Windows PC/laptop target.
- Basic docs (setup, calibration, troubleshooting).

## 4. Dependencies Between Phases

Phase 0 → 1 → 2 (capture works before triggering it automatically) → 3 → 4 (pose before 3D) → 5 → 6 (metrics before tips) → 7 (UI needs all data available) → 8.
Phases 3 and the UI shell (basic Phase 7 scaffolding) can happen in parallel with Phase 2 if useful, since they don't depend on the audio trigger specifically — only on having *some* captured session to work with (Phase 1 output).

## 5. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| ~~Pose model choice needs a spike~~ — resolved: Pose2Sim | — | Adopted Pose2Sim (BSD-3-Clause) for 2D pose + calibration + triangulation instead of a hand-rolled spike |
| Down-the-line + face-on (~90°) risks self-occlusion of key joints mid-swing (OQ4) | Gaps/noise in 3D landmark sequence for some joints | Validate against real footage in Phase 4 exit criteria; fall back to a shallower angle (e.g. closer to Pose2Sim's 45° "optimal") if occlusion proves significant |
| Camera sync drift (two independent USB cameras) | Bad triangulation | Establish a sync method early (e.g. shared capture timestamp, or a clap/flash sync test) in Phase 1; Pose2Sim's own sync stage is a fallback if our timestamp approach isn't tight enough |
| False triggers (mic picks up talking, other noises) | Missed/junk captures | Cooldown + threshold tuning in Phase 2; manual re-trigger fallback (FR8) |
| Calibration drift if camera moves | Bad 3D data silently | Add a simple "recalibration needed" check/reminder in Phase 4/8 |
| GPU/compute requirements too high for target laptop | Slow processing | Benchmark early in Phase 3; keep model choice swappable per NFR6 |

## 6. Design Spikes Needed Before/During Implementation

- ~~Spike A (Phase 3): candidate pose model shortlist~~ — resolved: Pose2Sim (see Phase 3/4, OQ2 in spec.md).
- Spike B (Phase 1/2): USB camera + mic capture library choice (e.g. OpenCV vs. platform-specific APIs) and confirm reliable synchronized timestamps.

## 7. What's Explicitly Deferred (matches spec Non-Goals)

- Full 3D mesh reconstruction.
- Club/ball tracking.
- Cloud sync / multi-device.
- Live in-swing feedback.
