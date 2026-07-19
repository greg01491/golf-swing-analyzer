# Spec: Golf Swing Analyzer — Audio-Triggered Dual-Camera Capture & 3D Pose Analysis

**Status:** Draft v2 — updated 2026-07-19 to reflect the implemented system (calibration approach, playback pipeline, P-positions, system checks)
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
- FR6: Because audio detection can't be truly "predictive," the system shall continuously buffer video from both cameras in a rolling in-memory/disk buffer of at least (capture duration + margin) so that footage *before* the trigger can still be saved once the trigger fires. (Buffer sizing is driven by capture duration, not just pre-capture delay, because the same buffer keeps accumulating post-trigger frames while extraction is still waiting for the window to complete — sizing it to pre-capture delay alone evicts the start of the window before extraction finishes.)
- FR7: The system shall debounce/ignore additional trigger events for a configurable cooldown period after a capture starts, to avoid re-triggering on follow-through or crowd/room noise.
- FR8: The system shall let the user manually arm/disarm listening, and manually trigger a capture as a fallback.

### 4.2 Dual-Camera Video Capture
- FR9: The system shall capture synchronized video from two USB cameras simultaneously.
- FR10: The system shall allow the user to select which two connected USB cameras to use and configure resolution/frame rate per camera. (Cameras are selected by DirectShow device *name*, not index — Windows does not keep camera indices stable across processes.)
- FR10a: The system shall support a per-camera **rotation correction** (0/90/180/270°) for physically sideways/upside-down mounted cameras, applied to every frame at capture time — not just the preview — because a rotated person degrades pose-model accuracy (models are trained on upright people). Configurable from the settings UI with a live preview per camera.
- FR11: The system shall save each captured swing as a discrete "session" containing both camera clips plus metadata (timestamp, settings used, camera IDs).
- FR11b: Saved clips shall be encoded in a format the review UI can actually decode (H.264/yuv420p). Rationale: OpenCV writes MPEG-4 Part 2, which Chromium/Electron cannot decode at all — clips are transcoded via a bundled ffmpeg immediately after capture; on transcode failure the original is kept (an unplayable clip beats a lost capture).
- FR11a: The reference camera rig is **down-the-line** (behind the golfer, looking along the target line) + **face-on** (to the side, perpendicular to the target line), roughly a 90° pair. This gives real triangulated depth (not a single-view estimate) at the cost of some self-occlusion risk during the swing, which Phase 4 testing must validate against actual footage.

### 4.3 Pose Estimation & 3D Reconstruction
- FR12: The system shall run 2D pose estimation (body landmarks) independently on each camera's captured clip.
- FR13: The system shall triangulate the two cameras' 2D landmark sequences into a single 3D skeleton/landmark sequence over the capture window, using a one-time camera calibration (relative position/orientation of the two cameras).
- FR14: The system shall provide a fully in-app guided calibration wizard covering: printing the checkerboard (generated in-app so it always matches the configured corner count), entering the *measured* printed square size (printers rarely reproduce exact scale), entering the measured camera-to-camera lens distance, per-camera lens (intrinsics) captures with auto-repeating countdown capture and per-step progress feedback visible from across a room, an extrinsics capture, computation with a quality summary (reprojection error, estimated body extent sanity check), and a way to clear all captures and start over (stale pre-rig-change captures otherwise silently pollute later computations).
- FR14a (calibration method): per-camera lens intrinsics come from checkerboard captures (`cv2.calibrateCamera`); the cameras' **relative pose (extrinsics) comes from matched body-pose keypoints** across both views during a synced capture of the golfer at the hitting position (essential-matrix), scaled to metres by the user-measured camera distance. This **supersedes Pose2Sim's board-based extrinsics**, which would need a board far larger than A4 at golf-rig camera distances. Output is written in Pose2Sim's Calib.toml format so its triangulation stage consumes it unchanged.
- FR15: The system shall store the resulting 3D landmark sequence per session for reuse (re-analysis without re-running pose estimation).
- FR12/FR13/FR15 are implemented on top of [Pose2Sim](https://github.com/perfanalytics/pose2sim) (BSD-3-Clause) rather than hand-rolled: it supplies the 2D pose backend (RTMPose default) and personAssociation → DLT triangulation → filtering for exactly the 2-camera case. Calibration (FR14/FR14a) is our own module that feeds Pose2Sim its expected file format. See plan.md Phase 3/4 and OQ2 below.

### 4.4 Swing Analysis
- FR16: From the 3D landmark sequence, the system shall compute a defined set of swing metrics — implemented set: shoulder_turn_deg, hip_turn_deg, x_factor_deg (shoulder-hip separation), spine_tilt_deg (at address), tempo_ratio, hip sway at top and impact (% of stance width, as a weight-transfer proxy). All angles are reported as magnitudes so they're handedness-neutral.
- FR16a: The system shall detect the P1–P10 swing checkpoint positions (P-system: address, takeaway, top, impact, finish, etc.) as frame indices within the capture, so the UI can jump playback to each. Checkpoints are defined relative to the golfer's **lead arm**, so golfer handedness is a required configuration input (pose tracking alone cannot infer it).
- FR16b: For each checkpoint, the system shall generate an "ideal" reference pose built from the golfer's **own measured body proportions** posed into target angles (fractions of the configured metric reference ranges) — only rotation and lead-arm carriage are idealized; posture/stance/legs are copied from the real frame — so the UI can ghost "where you should be" over "where you were."
- FR17: The system shall compare computed metrics against reference ranges (configurable/editable) to flag metrics outside typical/good ranges.
- FR18: The system shall generate a short list (top 3 by severity) of plain-English swing tips derived from the flagged metrics.
- FR18a: The system shall optionally auto-run the full analysis pipeline (2D pose → 3D → metrics → tips) on every capture in the background (one session at a time; capture keeps working while processing runs), so results are waiting without a manual "process" step. Configurable off for batch-processing later.

### 4.5 Review UI
- FR19: The system shall let the user browse past swing sessions.
- FR20: The system shall play back a session showing: original video (per-camera tabs) synchronized with the 3D skeleton animation.
- FR20a: When processing has produced a pose-overlay video (skeleton drawn directly on the golfer's body), the player shall offer it as the default view with a toggle back to the raw clip.
- FR20b: The playback view shall include the P1–P10 checkpoint strip (seek-and-freeze per position) with a toggle for the ideal-pose ghost overlay (FR16b) on the 3D skeleton.
- FR20c: The 3D view is a real WebGL (Three.js) scene — a lit, orbit-controllable capsule humanoid (cylindrical limb segments + joint spheres + head) standing on a ground plane — with a "body" vs "skeleton" toggle. Render fidelity is independent of reconstruction quality: a poorly-triangulated swing still renders, just as a distorted figure (flagged by FR20d).
- FR20d: When reconstruction quality is low (a large share of frames gap-filled, or physically-impossible coordinate ranges), the session view shall show a prominent warning that metrics and positions are unreliable, rather than presenting them as fact. (Backend `analysis/quality.py`; the 2-camera 90° rig's self-occlusion, OQ4, makes this a real and common case.)
- FR21: The system shall display computed metrics and generated tips alongside playback.
- FR22: The system shall let the user adjust configuration (trigger sensitivity, delay, duration, camera settings incl. rotation, metric reference ranges) from within the UI. Config saves must preserve the config file's comments.

### 4.6 System Readiness Check
- FR23: The system shall provide an on-demand PC spec check (CPU cores, RAM, free disk space) against configurable minimum/recommended thresholds, plus a *live* CPU/RAM load reading with a "close other applications" warning when load is high — so an under-specced or overloaded machine is flagged before a session, not discovered via dropped frames mid-session.
- FR24: The system shall provide an on-demand camera capability check that opens each configured camera and measures what it **actually delivers** (resolution and a real timed frame rate — driver-reported FPS is unreliable), compared against configurable minimums. The check must tolerate auto-exposure warm-up (discard frames before timing) and must never hang on a stalled camera driver (bounded watchdog timeout with an actionable error instead).

## 5. Non-Functional Requirements

- NFR1: **Local-first** — video, pose data, and analysis stay on the local machine by default; no required network calls for core functionality.
- NFR2: **Platform** — runs on a Windows PC/laptop (primary target); cross-platform (macOS) is a stretch goal, not a hard requirement for v1.
- NFR3: **Performance** — pose estimation + triangulation for a single swing capture should complete in well under a minute on a GPU-equipped laptop, so the user isn't waiting long between shots.
- NFR4: **Configurability** — all thresholds/delays/durations in §4.1 must be exposed as user-editable settings (config file and/or UI), not hardcoded.
- NFR5: **Reliability** — a missed or false trigger should not corrupt or block the next capture; the system should recover gracefully (e.g. auto re-arm).
- NFR6: **Extensibility** — architecture should allow swapping in a full 3D mesh model or club-tracking later without a full rewrite (out of scope now, but don't architect it out).

## 6. High-Level Architecture

- **Audio Trigger Service** (Python) — mic input stream → level detection → trigger event.
- **Capture Service** (Python) — manages dual USB camera rolling buffers (with per-camera rotation correction at the source) + synchronized recording; writes session video files and transcodes them to H.264 for playback (FR11b).
- **Pose Pipeline** (Python, GPU-accelerated) — built on [Pose2Sim](https://github.com/perfanalytics/pose2sim) (BSD-3-Clause): 2D landmarks per camera (RTMPose default) → DLT triangulation into a 3D landmark sequence. Rig calibration is our own module (FR14a) writing Pose2Sim's expected format. Used as a library dependency called from `backend/pose/`, not forked/vendored — our own capture, storage, analysis, and UI layers stay independent per NFR6. (Runs headless: matplotlib is forced to the Agg backend before Pose2Sim loads, since its filtering stage otherwise opens a GUI figure that deadlocks the whole process when run from a background thread on Windows.)
- **Analysis Engine** (Python) — metrics computation + P1–P10 checkpoint detection + ideal-pose generation + rule-based tip generation.
- **Diagnostics** (Python) — PC spec / live-load check and camera capability probe (§4.6).
- **Session Store** — local storage (filesystem + a lightweight local DB, e.g. SQLite) for sessions, video, pose data, metrics.
- **Frontend** (React/Electron) — arm/disarm control, live config, session browser, playback (raw / skeleton-on-body overlay) + 3D skeleton with ideal-pose ghost, P-position strip, metrics/tips display, calibration wizard, system check.
- **IPC/API layer** — connects Electron frontend to the Python backend (local REST service, FastAPI on 127.0.0.1).

## 7. Key Configuration Parameters (must be user-editable)

| Parameter | Default | Notes |
|---|---|---|
| Mic trigger threshold | TBD via calibration | dB or RMS level |
| Mic device | explicit index | system default proved unreliable on Windows; WASAPI devices preferred |
| Pre-capture delay | 1.0 s | time before trigger to include in saved clip |
| Capture duration | ~3 s (TBD) | fixed length from effective start |
| Trigger cooldown | ~5 s (TBD) | ignore re-triggers during this window |
| Camera resolution/FPS | per-camera | |
| Camera rotation | 0° per camera | 0/90/180/270 correction for physically rotated mounts (FR10a) |
| Checkerboard corners + measured square size | 4×7, measured mm | calibration board geometry; square size is the user's ruler measurement of the actual print |
| Calibration max age | 60 days | "recalibration recommended" staleness flag |
| Golfer handedness | right | needed to interpret P-system checkpoints (FR16a) |
| Auto-process captures | on | FR18a |
| Metric reference ranges | per-metric defaults | user-editable; also drive ideal-pose target angles (FR16b) |
| System requirements thresholds | min/recommended CPU, RAM, disk, camera res/fps, load-warning levels | §4.6 checks; all editable |

## 8. Open Questions / Assumptions

- OQ1: Exact capture duration default and pre-capture buffer size — needs real-world testing with actual impact sounds.
- ~~OQ2: Which open-source pose model to standardize on~~ — **Resolved:** adopt Pose2Sim (BSD-3-Clause), RTMPose as its default 2D backend. See §4.3 and §6.
- ~~OQ3: Camera calibration UX — how much do we ask the user to do manually vs. automate~~ — **Resolved:** fully in-app guided wizard (FR14), with Pose2Sim's board-based extrinsics replaced by person-keypoint extrinsics (FR14a) because an A4 board is too small at golf-rig camera distances. The user's only manual inputs are printing/measuring the board and measuring the camera-to-camera distance.
- OQ4: Down-the-line + face-on (~90°) is an "acceptable" but not Pose2Sim's "optimal" (45°) camera-angle configuration per its own docs — the tradeoff is a real self-occlusion risk (e.g. trail arm hidden behind the torso from one view mid-swing). Phase 4 exit criteria must include a real-footage check that occlusion isn't degrading key joints before locking in the rig as final. **Still open — needs a good calibration + real swing on the rig.**
- Assumption: Both cameras are fixed in position once calibrated (recalibration needed if a camera moves).
- Assumption: v1 targets a single golfer, single-camera-rig setup (not multi-station).
