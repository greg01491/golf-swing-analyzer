# Crown Tracking Diagnostic

This experiment is not part of pose estimation, triangulation or metric calculation.
It follows an unverified HALPE-26 Head seed using local image motion, not a
temporally averaged coordinate. Image consistency does not establish crown placement.

## Running

Use the backend environment and a separate, new output directory outside the input
session. Run one camera at a time. A pose JSON is expected for every native video frame;
missing, malformed or ambiguous observations remain unsupported.

```powershell
python -m golf_sim.diagnostics.crown_tracking `
  --video <diagnostic-copy>/camera_1.mp4 `
  --poses <diagnostic-copy>/pose2sim/pose/camera_1_json `
  --output <separate-new-directory> `
  --config <config.yaml> `
  --write-video
```

Parameters live under `pose.crown_tracking_diagnostic`. They do not change the
existing reconstruction tolerance. Existing configurations load diagnostic defaults
without being rewritten. No runtime API or automatic-processing path invokes this tool.

## Evidence And Rejections

- Local Shi-Tomasi features supply image evidence around the last tracked point.
- Forward/backward Lucas-Kanade checks and robust partial-affine inliers validate motion.
- Detector displacement is only a search initialization, not a replacement for image evidence.
- Missing observations, weak texture, inconsistent flow and detector disagreement create
  unsupported frames. Reacquisition starts an unverified seed; no point is emitted for it.
- JSON records contain raw and candidate coordinates, rejection reasons and settings.
  Every report says `diagnostic_only: true`, `eligible_for_metrics: false` and
  `anatomical_crown_verified: false`.
- Comparison videos show orange detector circles and green image-tracked markers.
  No green point is drawn for a rejected or seed frame.
- Before/after hashes cover the input video and existing pose JSONs. Source metadata,
  reviews, calibration and metrics are never written. Existing output directories
  cannot be overwritten.

## Interpreting Results

Compare jitter on identical supported consecutive frame pairs, together with coverage,
rejection counts, seed resets, displacement and anatomical placement. Report the full
raw baseline separately. Gaps and reseeds are excluded from consecutive-step summaries;
apparently lower jitter must not conceal lost support or segment-to-segment offsets.

Synthetic tests cover stationary detector jitter, known translation at two speeds,
missing/blank images, detector jumps, output isolation and preservation. These establish
algorithm behavior, not physical crown accuracy or measured lag on a real person.

The first fixed-settings trial on controlled still/slow clips and a held-out swing
reduced point jitter with high image-support coverage. Close-up inspection still showed
stable points near the temple in the down-the-line view. Consequently this experiment
does **not** pass anatomical crown-placement acceptance and must not supply head-excursion
values. Detailed personal footage and per-frame results remain outside the repository.

Independent crown annotations or a separately validated anatomical locator are needed
to assess placement error and real-motion lag before any production proposal.

## Operator Starting Points

Start a separate loopback-only annotation page over an existing diagnostic root:

```powershell
python -m golf_sim.diagnostics.crown_annotation --root <diagnostic-root> --port 8772
```

The page shows the native frames for the two controlled clips and original swing.
Select a clearly visible crown point in each camera, using zoom and a later frame if
needed. Explicitly confirm visibility before saving; skip views where the crown cannot
be identified. No point is preselected, and the page never treats the detector as an
operator annotation. Saved points go only to the diagnostic root's separate
`operator_crown_seeds.json`, bound to video SHA-256, camera, native frame and dimensions.

Run a new comparison with the original diagnostic arguments plus:

```powershell
--seeds <diagnostic-root>/operator_crown_seeds.json
```

Operator mode waits for an explicit seed and uses image motion to propagate it. Image
motion from the previous accepted step initializes the next search. Detector positions,
confidence and jumps do not guide or veto operator-mode tracking; detector differences
are recorded only as diagnostics. Forward/backward consistency, robust feature support
and image bounds remain mandatory. Missing image evidence or rejected motion ends the
segment; tracking cannot restart from the detector and must wait for another operator seed.
An operator-confirmed starting point is not proof of later anatomical accuracy, so
reports remain `anatomical_crown_verified: false` and `eligible_for_metrics: false`.

The first operator-seeded version used a detector-motion disagreement veto and stopped
on raw detector jumps even when optical-flow support agreed. The subsequent isolated
version removed that dependency without changing image thresholds or reconstruction
tolerances. On the six diagnostic views, five tracks reached the final frame; the DTL
swing stopped at a forward/backward image-consistency failure around the club crossing
the head region. Sampled images are useful for review, not independent anatomical error
or real-motion-lag measurements. Both versions' personal outputs remain outside the repo.

## Held-Out Accuracy Checks

Open the same local page with `?mode=check`. It presents native swing frames 80, 137
and 177 in both views from the fixed operator-v2 comparison. The comparison's predicted
point is not sent to the page until an independent visible-crown judgment is saved.
After saving, orange marks the operator point, green marks the tracked point, and the
page reports their image-plane distance. Use Next check after inspecting the reveal.

Checks are stored separately in `operator_crown_checks.json`, with an explicit
`validation_only` purpose plus video and comparison hashes. They are not seed inputs:
the seed schema and seed endpoint reject validation records. A frame already used as
a seed cannot be offered as a held-out check. Once a judgment has revealed a prediction,
the API refuses edits so it cannot be revised toward the displayed point. Comparison
changes invalidate the evaluation instead of silently scoring a different experiment.

The reported distance is annotation-to-prediction image error, not the separate
15-pixel reconstruction reprojection criterion. No automatic anatomical or metric
acceptance follows from one operator click or from a small distance.

## Continuous Playback

Open the same local service with `?mode=playback` to review the existing operator-v2
comparison videos. The six controlled/swing camera views are available at normal,
half and quarter speed, with looping, native-frame stepping and scrubbing. Switching
between the two cameras for the same clip retains clip time, not a claim of verified
exposure synchronization. Orange marks the original detector; green marks the
image-tracked candidate. Rejected frames have no green candidate and show an explicit
unavailable status rather than presenting a held position as valid.

Playback is read-only: it does not change seeds, independent checks, source media or
metrics. Swing playback is refused until all three independent judgments for that
view are saved against the exact comparison, protecting unfinished check-only review
from prediction exposure. Visual judgments about sticking, drift and lag remain
operator evaluation, not certification of 3D excursion, timing or calibration.