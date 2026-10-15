# Setup, Calibration & Troubleshooting

## 1. Install

Prerequisites: Python 3.11+, Node 20+, two USB cameras, a microphone.

```bash
git clone https://github.com/greg01491/golf-swing-analyzer
cd golf-swing-analyzer

# Backend
cd backend
python -m venv .venv
./.venv/Scripts/activate          # Windows
pip install -e ".[dev,pose]"      # pose extra pulls the ML stack (~1GB with models)

# Frontend
cd ../frontend
npm install
```

## 2. Physical rig

Two cameras, both with a full view of the golfer (head to feet, plus club-length margin):

- **camera_1 — down-the-line:** behind the golfer, looking along the target line, hip height.
- **camera_2 — face-on:** directly to the side (in front of the golfer's chest), perpendicular
  to the target line, hip height.

This ~90° pair gives true triangulated depth (spec.md FR11a). Mount both cameras rigidly —
**any camera movement after calibration invalidates the calibration.**

If a camera is physically mounted sideways or upside down, set its rotation in the
**settings** tab (or `rotation_deg` in config.yaml: 0/90/180/270). This corrects the actual
captured footage, not just the preview — the pose model expects upright people, so a
sideways camera silently wrecks tracking accuracy. Check the live preview per camera in
settings to confirm the orientation looks right, and save + disarm/arm to apply.

Laptop/mic near the hitting area; the impact sound is the trigger.

Before a first real session, run the **system check** tab: it verifies the PC's specs
(CPU/RAM/disk, plus current load — close other apps if it warns) and probes each camera for
the resolution and *measured* frame rate it actually delivers (disarm capture first; the
probe needs exclusive camera access).

## 3. Pick devices

```bash
# Cameras: probe indices, note which index is which physical camera
python -m golf_sim.capture.enumerate

# Microphones
python -m golf_sim.audio.cli devices
```

Set the mic index under `audio_trigger.device`, and each camera's `name` (the exact string
from `enumerate`'s output — e.g. `"HD USB Camera"`) under `cameras.devices` in
[config/config.yaml](../config/config.yaml). **Use `name`, not `id`:** Windows does not keep
DirectShow camera indices stable across process restarts — the same physical camera can be
index 0 one run and index 2 the next, silently recording from the wrong camera with no error.
`id` is only a fallback for when no name is set.

> **Windows mic gotcha:** `device: null` (system default) can fail outright with a PortAudio
> "no driver installed" error even when the mic works fine. Prefer an explicit device index —
> WASAPI-backed entries are the most reliable. WDM-KS entries don't support the blocking reads
> this app uses; skip them.

## 4. Calibrate the trigger threshold

```bash
python -m golf_sim.audio.cli calibrate
```

Stay quiet for the ambient sample, then make ~3 impact sounds (hit a ball, or clap loudly at
the hitting position). Put the suggested value in `audio_trigger.threshold_db`.

## 5. Calibrate the camera rig

Done entirely in-app via the **calibrate** tab — the wizard walks through every step,
including printing the board.

1. **Step 0a:** the wizard shows a printable checkerboard (generated to match the configured
   corner count). Print it at **100% scale — not "fit to page"**, tape it to something rigid,
   measure one square with a ruler (across several squares and divide, for accuracy), and
   enter the measured size in the wizard. The printed size rarely matches the nominal one
   exactly, and a wrong size silently scales all 3D output.
2. **Step 0b:** measure the straight-line distance between the two cameras' **lenses** (same
   reference point on each) in metres and enter it — this anchors real-world scale.
3. **Step 1 / Step 2** (one per camera): pick a countdown length, hold the board about arm's
   length from that camera in view of the live preview, and hit **start capturing**. The
   wizard then repeats countdown → capture on its own — move/tilt the board to a new position
   during each countdown (a big on-preview countdown and an "X / 8 captures" badge are
   readable from across the room). It stops itself at the target count, or hit **stop
   capturing** any time.
4. **Step 3:** stand at your normal hitting position, fully visible to *both* camera
   previews at once, start capturing, and do a slow practice swing (no club needed) during
   the recording so your body sweeps through the shared view volume.
5. Click **compute calibration**. Watch for the reprojection error in the result (well under
   5px is good) and the estimated-height sanity figure (should be roughly your real height) —
   if either looks wrong, recapture Step 3 with more of your body visible in both views and
   try again.

Starting over (e.g. after moving a camera): use **clear all captures and start over** in the
wizard first — old captures are pooled into the computation and would silently pollute a
fresh attempt.

Recalibrate whenever a camera moves. The app flags calibration older than
`calibration.max_age_days` (shown at the top of the calibrate tab and via
`python -m golf_sim.pose.cli status`).

## 6. Run

### Independent calibration and measured references

Camera candidates now reserve independent lens captures and temporal camera-position
observations before fitting. Review held-out per-camera errors and body-region coverage,
not only the historical fit-inlier error. Failed or cancelled candidates leave the last
accepted camera bundle unchanged. Legacy files remain readable as unverified geometry.

Use matching camera identity, dimensions, rotation, frame mode and fixed/read-back lens
settings for the rig. Unknown historical metadata is not filled from current settings.
Accepted bundles are immutable; camera-geometry acceptance and ground readiness are separate.

After accepting compatible cameras, capture two level measured-board placements with a
marked row pointing toward the target. Identify the marked origin in each camera preview
and confirm which side contains the golfer. Independent geometric checks, not confirmations
alone, decide acceptance. The resulting measured reference is transferred automatically
into the selected filtered TRC's coordinates with source fingerprints.

Saved-3D reanalysis updates metrics only. **Reconstruct with active calibration** is a
separate explicit action: it requires compatible recorded evidence and archives previous
outputs before rebuilding. It cannot certify an old capture whose settings are unknown.
See [calibration-validation.md](calibration-validation.md) for the independent rig protocol
and physical-accuracy limits. No new personal calibration or recording was installed as
part of software testing.

### Installed desktop app

The Windows installer contains Electron, the Python backend, Pose2Sim, OpenSim,
OpenVINO, and ffmpeg support. Opening **Golf Swing Analyzer** starts and monitors
the backend automatically; no terminal or separately installed Python is
required. Sessions, settings, logs, and the one-time camera calibration are
stored under the user's application-data folder so upgrades do not remove them.
Calibration and Settings start both camera previews automatically and keep the
shared camera service running while the app is open. The calibration wizard
pre-fills the current rig's measured camera distance of `3.115 m`.

Backend, processing, and calibration failures are recorded in
`%APPDATA%\golf-swing-analyzer\logs\backend.log`; renderer, API-client, and
window failures are recorded alongside it in `renderer.log`.

On a fresh installation, capture remains disabled until the startup readiness
banner confirms that the pose engine and microphone are available and the
two-camera calibration workflow has been completed.

Pose inference defaults to one worker to limit peak memory while the high-frame-rate
cameras continue buffering. Systems with sufficient memory may set
`pose.parallel_workers_pose` to `2`. Slow-motion playback pauses at `0%`; nonzero rates
are clamped to Chromium's supported minimum (`6.25%`).

### Development

Use Node.js 24 for frontend development and `npm test`; the confidence/history tests
use its native TypeScript stripping rather than adding another test framework. The
frontend CI job runs these tests before lint and build.

```bash
# Terminal 1 — backend
cd backend && ./.venv/Scripts/activate
python -m golf_sim.api.server

# Terminal 2 — desktop app (or `npm run dev` for browser-only)
cd frontend && npm run electron:dev
```

In the app: **arm listening** → hit a shot → session appears → **process swing** → review
video + 3D skeleton + metrics + tips. Settings are editable in-app; disarm/arm to apply.

CLI equivalents: `golf_sim.audio.cli listen`, `golf_sim.pose.cli full --latest`,
`golf_sim.analysis.cli --latest`.

## 7. Validate the rig (first-time checks)

### Metric confidence and saved results

Analysis version 2 returns all 19 measurements with `valid`, `estimated`, or
`unavailable` status. A finite number is not proof of reliable tracking. Only valid
measurements with compatible targets receive pass/fail verdicts or coaching. Estimated
results show their reason; unavailable results have no numeric value. Wrist visibility
does not establish that the shoulders, hips, or head were reconstructed correctly.

Shoulder/hip turn and X-Factor are supported peak horizontal backswing measurements,
not necessarily top-frame values or rotation around the spine. Head movement is maximum
excursion from address through impact, not just the difference between two frames.
Impact hip rotation is positive open and negative closed; shoulder tilt is positive
when the trail shoulder drops. Early extension is positive ballward and negative away;
reverse spine is positive targetward and negative away. Knee angle is 180 degrees when
straight. Hand speed is a supported peak near impact, and hand-path inclination remains
an endpoint body-pose proxy, not a club-shaft or fitted-plane measurement.

Older results remain inspectable as **legacy-unverified** without current verdicts,
coaching, or inclusion in comparable trends. Opening them does not rewrite captures.
Choose **reanalyze saved 3D** to explicitly recompute metrics using saved landmarks;
this does not rerun pose reconstruction and cannot repair missing or corrupt landmarks.
Missing source landmarks produce an actionable error. Full processing is a separate action.

Body-derived up is an estimate. Inconsistent torso/leg geometry makes that reference
unavailable, and an ambiguous ball direction makes directional measurements unavailable.
The measured ground-reference workflow supplies independently checked board evidence;
ordinary handheld lens calibration alone does not establish a level floor normal.

Ground evidence is generated from accepted camera/reference bundles and transferred to
the actual filtered TRC through its recorded coordinate transform. Analysis verifies the
camera manifest, ground fingerprint, capture signatures, exact TRC bytes and evidence
digest in session metadata. Manually adding `validated: true` or guessed vectors to a
session does not authorize measurement confidence. Reanalysis never substitutes an
unrelated current calibration for missing original evidence.

Evidence settings live under `metrics`: time-based `turn_filter_window_s` (0.05),
`address_window_s` (0.1), and `hand_speed_window_s` (0.1); `turn_outlier_deg` (20);
`min_projected_width_m` (0.02); `min_supported_fraction` (0.8);
`frozen_tolerance_m` (0.0001); `max_marker_speed_ms` (20);
`max_limb_length_ratio` (1.5); plausible pelvis-height bounds (0.3-1.5 m);
`held_observation_motion_px` (2); and `marker_outlier_distance_m` (0.05).
These are configurable engineering checks, not clinical confidence probabilities.

Targets now declare `metrics.range_definition_version: 2`. Legacy custom target files
without compatible metadata remain readable, but their old ranges are not silently
applied. Review values against the definitions before opting into version 2; do not
merely change the version marker to make old ranges apply. Shipped bands are editable
coaching heuristics, not independently certified biomechanical norms. Early extension
uses a signed -8 to 8 cm stability band; reverse spine flags targetward bend above
12 degrees, with -90 as the mathematical lower limit for away-target bend rather than
a recommended posture. Other posture/head targets retain their numeric limits but now
apply to the documented forward-component and excursion definitions. Club overrides
remain in effect only for compatible targets.

Physical accuracy still requires independent reference geometry and synchronized video
review. The October recordings with held torso landmarks demonstrate correct rejection,
not certified corrected shoulder/hip angles. Their original files are unchanged.

1. **Sync check:** clap once in view of both cameras, capture manually, then
   `python -m golf_sim.capture.sync_check <session>/camera_1.mp4 <session>/camera_2.mp4`.
   Offset should be within ~1 frame. If not, lower resolution/fps or try different USB ports
   (separate controllers help).
2. **Occlusion check (spec.md OQ4):** process a few real swings and watch the 2D overlay
   videos (`<session>/pose2sim/pose/camera_N_pose.mp4`). If the trail arm or lead hip loses
   tracking mid-swing from one view, angle that camera a little toward 45° and recalibrate.

## 8. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "could not open camera index N" | Wrong index (re-run enumerate), camera in use by another app, or USB bandwidth — try lower resolution or another port |
| "camera_N not responding" while armed | Camera unplugged/asleep; the app keeps running — fix the device, then disarm/arm |
| Mic error in header; level meter blank | Device index invalid or unplugged; run `audio.cli devices`, set a WASAPI index |
| Triggers on speech/noise | Raise `threshold_db` (less negative) or increase `trigger_cooldown_s`; re-run calibrate in the actual room |
| Misses real impacts | Lower `threshold_db`; check mic distance to impact position; use manual capture as fallback |
| Clip misses top of backswing | Increase `pre_capture_delay_s` (and `capture_duration_s` if the finish is cut) |
| "No .toml calibration directory found" during processing | Rig not calibrated (§5), or the session's `pose2sim/Config.toml` anchor file was deleted — reprocess to regenerate |
| Metrics look absurd | Check the 2D overlays first (bad tracking → bad 3D); confirm calibration is current and square size was right |
| Processing slow | CPU-only ONNX is ~30s/swing; set `pose.mode: lightweight`, or install a GPU ONNX runtime |
| Settings save "restart capture to apply" | Expected — disarm/arm reloads the capture pipeline with new values |
| Live preview in the calibrate tab shows "no signal" | Capture isn't armed yet — click **arm listening** first |
| A camera goes solid black after the app's been running a long time | Known cheap-webcam driver stall; the app detects a run of all-black frames and reopens the device automatically within a few seconds — no action needed |
| Calibration compute error mentions "correspondences" or "keypoints" | Step 3 capture didn't have enough of the body visible in both cameras at once — recapture standing further back or adjust framing |
