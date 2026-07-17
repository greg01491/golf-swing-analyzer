# Spec: Golf Swing Analyzer — Audio-Triggered Dual-Camera Capture & 3D Pose Analysis

**Status:** Draft v1
**Feature ID:** 001-audio-triggered-capture-and-analysis
**Owner:** Greg

## 1. Overview

A desktop application (Windows/PC laptop) for a home golf simulator setup that:

1. Listens continuously to the laptop microphone for the impact sound of a golf shot.
2. On detecting a sufficiently loud sound, waits a configurable delay, then records synchronized video from two USB cameras for a fixed, configurable duration.
3. Extracts 2D body pose from each camera feed and triangulates it into a 3D skeleton over time.
4. Computes swing biomechanics metrics from the 3D skeleton sequence.
5. Generates plain-English swing tips from those metrics.
6. Presents the captured swing, 3D skeleton playback, metrics, and tips to the user.

This builds on the existing architecture decisions: dual USB cameras, GPU-accelerated open-source AI models, Python backend, React/Electron frontend.

## 2. Goals

- G1: Hands-free capture — no button press needed to start recording a swing.
- G2: Capture reliably brackets the actual swing (not just noise-to-noise) via a configurable pre-trigger delay.
- G3: Produce a 3D pose (skeleton/landmark) representation of the swing, not just flat 2D video.
- G4: Turn pose data into a small number of concrete, actionable tips per swing.
- G5: Everything runs locally on the user's PC/laptop — no required cloud dependency.
- G6: Every key parameter (trigger sensitivity, delay, capture duration, camera settings) is user-configurable without code changes.

## 3. Non-Goals (Out of Scope for v1)

- NG1: Full 3D body **mesh** reconstruction (e.g. SMPL avatar). v1 uses skeleton/pose landmarks only.
- NG2: Club tracking or ball-flight/launch-monitor data (club path, ball speed, spin).
- NG3: Multi-user / cloud sync / mobile companion app.
- NG4: Real-time in-swing feedback (analysis happens post-capture, not live during the swing).
- NG5: Automatic camera calibration hardware (a manual/guided calibration step is in-scope; specialized calibration rigs are not).

## 4. Functional Requirements

Written in EARS-style ("When/If <trigger>, the system shall <response>") where useful.

### 4.1 Audio-Triggered Capture
- FR1: While in "armed" mode, the system shall continuously monitor the selected microphone input.
- FR2: When the input sound level exceeds a configurable threshold (dB or RMS-based), the system shall treat this as a "trigger event."
- FR3: The system shall provide a configurable **trigger sensitivity** setting, with a sensible default calibrated for a typical golf strike/impact sound.
- FR4: The system shall support a configurable **pre-capture delay** (default: 1.0 second) between the trigger event and the start of the recording window that is saved. (Rationale: the swing/backswing happens *before* the impact sound, so the saved clip must include time before the trigger, not after.)
- FR5: The system shall support a configurable **capture duration** (default: e.g. 3 seconds), fixed-length, counted from the effective start of the recording window (i.e. trigger time minus pre-capture delay).
- FR6: Because audio detection can't be truly "predictive," the system shall continuously buffer video from both cameras in a rolling in-memory/disk buffer of at least (pre-capture delay + margin) so that footage *before* the trigger can still be saved once the trigger fires.
- FR7: The system shall debounce/ignore additional trigger events for a configurable cooldown period after a capture starts, to avoid re-triggering on follow-through or crowd/room noise.
- FR8: The system shall let the user manually arm/disarm listening, and manually trigger a capture as a fallback.

### 4.2 Dual-Camera Video Capture
- FR9: The system shall capture synchronized video from two USB cameras simultaneously.
- FR10: The system shall allow the user to select which two connected USB cameras to use and configure resolution/frame rate per camera.
- FR11: The system shall save each captured swing as a discrete "session" containing both camera clips plus metadata (timestamp, settings used, camera IDs).

### 4.3 Pose Estimation & 3D Reconstruction
- FR12: The system shall run 2D pose estimation (body landmarks) independently on each camera's captured clip.
- FR13: The system shall triangulate the two cameras' 2D landmark sequences into a single 3D skeleton/landmark sequence over the capture window, using a one-time camera calibration (relative position/orientation of the two cameras).
- FR14: The system shall provide a guided calibration workflow so the user can calibrate the two-camera rig (e.g. checkerboard or known-object calibration).
- FR15: The system shall store the resulting 3D landmark sequence per session for reuse (re-analysis without re-running pose estimation).

### 4.4 Swing Analysis
- FR16: From the 3D landmark sequence, the system shall compute a defined set of swing metrics (e.g. shoulder turn angle, hip turn angle, spine tilt, X-factor (shoulder-hip separation), swing tempo/ratio, weight transfer indicators — exact metric list to be finalized in design).
- FR17: The system shall compare computed metrics against reference ranges (configurable/editable) to flag metrics outside typical/good ranges.
- FR18: The system shall generate a short list (e.g. top 3) of plain-English swing tips derived from the flagged metrics.

### 4.5 Review UI
- FR19: The system shall let the user browse past swing sessions.
- FR20: The system shall play back a session showing: original video (at least one camera view) synchronized with the 3D skeleton animation.
- FR21: The system shall display computed metrics and generated tips alongside playback.
- FR22: The system shall let the user adjust configuration (trigger sensitivity, delay, duration, camera settings, metric reference ranges) from within the UI.

## 5. Non-Functional Requirements

- NFR1: **Local-first** — video, pose data, and analysis stay on the local machine by default; no required network calls for core functionality.
- NFR2: **Platform** — runs on a Windows PC/laptop (primary target); cross-platform (macOS) is a stretch goal, not a hard requirement for v1.
- NFR3: **Performance** — pose estimation + triangulation for a single swing capture should complete in well under a minute on a GPU-equipped laptop, so the user isn't waiting long between shots.
- NFR4: **Configurability** — all thresholds/delays/durations in §4.1 must be exposed as user-editable settings (config file and/or UI), not hardcoded.
- NFR5: **Reliability** — a missed or false trigger should not corrupt or block the next capture; the system should recover gracefully (e.g. auto re-arm).
- NFR6: **Extensibility** — architecture should allow swapping in a full 3D mesh model or club-tracking later without a full rewrite (out of scope now, but don't architect it out).

## 6. High-Level Architecture

- **Audio Trigger Service** (Python) — mic input stream → level detection → trigger event.
- **Capture Service** (Python) — manages dual USB camera rolling buffers + synchronized recording, writes session video files.
- **Pose Pipeline** (Python, GPU-accelerated, open-source model e.g. MediaPipe Pose or similar) — 2D landmarks per camera → 3D triangulation using calibration data.
- **Analysis Engine** (Python) — metrics computation + rule-based tip generation.
- **Session Store** — local storage (filesystem + a lightweight local DB, e.g. SQLite) for sessions, video, pose data, metrics.
- **Frontend** (React/Electron) — arm/disarm control, live config, session browser, playback + skeleton overlay, metrics/tips display.
- **IPC/API layer** — connects Electron frontend to the Python backend (e.g. local REST/WebSocket service).

## 7. Key Configuration Parameters (must be user-editable)

| Parameter | Default | Notes |
|---|---|---|
| Mic trigger threshold | TBD via calibration | dB or RMS level |
| Pre-capture delay | 1.0 s | time before trigger to include in saved clip |
| Capture duration | ~3 s (TBD) | fixed length from effective start |
| Trigger cooldown | ~5 s (TBD) | ignore re-triggers during this window |
| Camera resolution/FPS | per-camera | |
| Metric reference ranges | per-metric defaults | user-editable |

## 8. Open Questions / Assumptions

- OQ1: Exact capture duration default and pre-capture buffer size — needs real-world testing with actual impact sounds.
- OQ2: Which open-source pose model to standardize on (e.g. MediaPipe Pose vs. a GPU-heavier alternative) — to be confirmed in `plan.md` / design spike.
- OQ3: Camera calibration UX — how much do we ask the user to do manually vs. automate.
- Assumption: Both cameras are fixed in position once calibrated (recalibration needed if a camera moves).
- Assumption: v1 targets a single golfer, single-camera-rig setup (not multi-station).
