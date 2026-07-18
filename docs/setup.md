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

Laptop/mic near the hitting area; the impact sound is the trigger.

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

Done in-app via the **calibrate** tab — no separate capture tool needed, since the rig
cameras are already held open by the running backend.

1. Print `data/calibration_board_A4.png` (or generate your own) at **100% scale — not
   "fit to page"**. Measure one square with a ruler; the printed size rarely matches the
   nominal one exactly, and a wrong size silently scales all 3D output. Enter the measured
   size in `calibration.checkerboard_square_size_mm` in config.yaml (corner count in
   `calibration.checkerboard_corners`, default 4×7). Tape the board to something rigid.
2. Measure the straight-line distance between the two cameras in metres — you'll enter this
   in the wizard to anchor real-world scale.
3. Open the app → **calibrate** tab. For **Step 1** and **Step 2** (one per camera): hold the
   board about arm's length from that camera in view of the live preview, click **capture (10s
   countdown)**, and move/tilt the board to a new position before each capture. Aim for at
   least 4-6 captures per camera with the board clearly, fully visible in the preview.
4. For **Step 3**: stand at your normal hitting position, fully visible to *both* camera
   previews at once, click capture, and do a slow practice swing (no club needed) during the
   countdown + recording so your body sweeps through the shared view volume.
5. Enter the camera-to-camera distance and click **compute calibration**. Watch for the
   reprojection error in the result (well under 5px is good) and the estimated-height sanity
   figure (should be roughly your real height) — if either looks wrong, recapture Step 3 with
   more of your body visible in both views and try again.

Recalibrate whenever a camera moves. The app flags calibration older than
`calibration.max_age_days` (shown at the top of the calibrate tab and via
`python -m golf_sim.pose.cli status`).

## 6. Run

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
