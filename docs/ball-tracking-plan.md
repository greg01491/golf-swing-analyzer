# Implementation plan: coloured-ball detection → address/impact anchoring

Handoff for continuing the work. Read this fully before coding. It captures
findings from live testing on Greg's real rig so you don't repeat the dead ends.

## Goal
Auto-detect the golf ball at address in the **down-the-line camera (camera_1)**,
then use it to anchor two swing events precisely:
- **Address (P1)** = ball present next to the club head AND still.
- **Impact (P7)** = the frame the ball disappears (is struck).

This fixes the current inaccuracy where the detected P7 has the club still far
from the ball (phases are currently audio-trigger + geometry anchored; see
`backend/src/golf_sim/analysis/phases.py::detect_phases`, which takes an
`impact_hint_frame`).

## Hard-won findings (do NOT relitigate)
1. **Full-frame ball/club CV fails.** The room has many round/bright distractors
   (downlights, sockets, monitors, a grey exercise ball, scattered practice
   balls, a green launch pad). Hough circles/lines lock onto the wrong things.
2. **Wrist-anchored ROI works spatially.** The pose model already outputs wrists
   per camera. At address the ball sits in a small box just below/target-side of
   the wrist midpoint. Restrict all ball search to that ROI. Verified: the ball
   falls inside `x∈[wx-120, wx+220], y∈[wy+40, wy+300]` for camera_1 (wx,wy =
   wrist midpoint in pixels; tune, don't hardcode).
3. **A plain WHITE ball is undetectable in this lighting.** Measured at address:
   ball HSV ≈ `[44,49,117]`, green mat ≈ `[44,45,112]` — same hue, same
   brightness. No threshold separates them. **Greg has switched to a bright
   coloured (orange/yellow) ball** — build around hue segmentation of that.
4. Club tracking through the swing is out of scope (spec NG2) and not feasible
   with 2 consumer webcams (thin, motion-blurred). Only estimate the club head
   at address (≈ ball position).

## Data available per session (on disk under `data/sessions/<id>/`)
- `camera_1.mp4`, `camera_2.mp4` (H.264, already transcoded).
- `metadata.json`: `pre_capture_delay_s`, per-camera dims, fps.
- `metrics.json`: `phases` (address/top/impact frames), `p_positions`,
  `tracking_quality`.
- `pose2sim/pose/camera_1_json/*.json`: per-frame 2D keypoints (HALPE_26,
  `people[0].pose_keypoints_2d` as flat [x,y,conf]*26). RWrist=idx10, LWrist=idx9
  (confirmed live). Use these for the wrist anchor.

## Build steps
1. **New module** `backend/src/golf_sim/analysis/ball_detect.py`:
   - `find_ball_at_address(clip: Path, wrist_xy: tuple[float,float], hue_range) ->
     (cx, cy, radius) | None`. Convert ROI to HSV, `cv2.inRange` on the coloured
     hue (orange ≈ H 5–22, yellow ≈ H 22–35 in OpenCV's 0–179 scale; make the
     range configurable in config.yaml under a new `ball:` section), morph-open,
     take the largest sufficiently-circular contour (`area/(πr²) > 0.6`).
   - `ball_present(frame_roi, ball_template_or_huemask) -> bool`: cheap per-frame
     presence check at the locked ball location (hue-mask pixel count over a
     threshold, or template match score).
   - `detect_impact_by_disappearance(clip, ball_xy, start_frame, fps) -> int|None`:
     from a few frames after address, first frame where `ball_present` goes
     false for ≥2 consecutive frames → impact.
2. **Wire into analysis** (`backend/src/golf_sim/analysis/cli.py::analyze_session`):
   - Read wrist pixel at the current address frame from `camera_1_json`.
   - Detect ball; if found, refine `address` (ball still + present) and compute
     `impact` via disappearance; pass the ball-derived impact as
     `impact_hint_frame` to `detect_phases` (already supported), OR add a
     stronger override path. Keep the audio-trigger fallback when no ball found.
   - Add `ball` info (address pixel xy, radius, impact frame, detected bool) to
     `metrics.json` for the UI.
3. **Config** (`config/config.yaml` + `backend/src/golf_sim/config.py`): new
   `ball:` block — `hue_min`/`hue_max`, `min_saturation`, `min_value`,
   `roi` offsets relative to wrist. All user-editable (NFR4).
4. **UI** (`frontend/src/components/SessionView.tsx`): draw a marker on the video
   at the detected ball position on the address frame; optionally show
   "impact detected from ball" vs "estimated". Types in `frontend/src/api.ts`.
5. **Tests** (`backend/tests/test_ball_detect.py`): synthesise a small frame with
   a coloured circle on a green field; assert detection finds it, and that a
   frame with the circle removed reads as "ball gone" → impact. No real-footage
   dependency (keep CI green; CI installs `.[dev]`, not `.[pose]`).

## Verify against the newest real session
Greg captured a swing with the coloured ball just before handoff — it's the most
recent `data/sessions/*` dir with a `metrics.json`. Extract its address frame
(`metrics.json.phases.address_frame`) from `camera_1.mp4`, get the wrist pixel
from `camera_1_json`, and confirm `find_ball_at_address` locks onto the coloured
ball. Then confirm the disappearance frame ≈ the audio trigger frame
(`round(pre_capture_delay_s * fps)`), and that the new P7 has the club at the ball.

## Gotchas
- Windows shuffles camera/mic indices across reboots (selected by name already
  for cameras; mic is a bare index in config — may need re-checking).
- Pose2Sim's filtering deadlocks if its qtagg matplotlib figure first runs on a
  worker thread — `reconstruct.preload_headless_pose_stack()` handles it; don't
  remove it.
- The backend must be restarted to pick up code/config changes (no auto-reload).
- Always run `pytest -q && ruff check src tests && black --check src tests` in
  `backend/`, and `npm run build && npm run lint` in `frontend/`, before commit.
