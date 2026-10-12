## Why

The current low-quality warning counts frozen hand positions across the whole clip, including normal pauses before address and after impact, and does not identify which camera or keypoints likely caused missing 3D motion. This can make a sound calibration appear suspect and leaves the golfer without a useful corrective action.

## What Changes

- Measure hand-motion coverage within the detected address-to-impact swing window separately from whole-clip motion.
- Report address-to-impact confidence/visibility for each camera's wrists, and identify weak camera/keypoint coverage in quality warnings.
- Distinguish insufficient in-swing motion, weak camera/keypoint tracking, and physically implausible reconstructed scale; recommend recalibration only for the scale failure.
- Preserve the quality verdict and provide actionable diagnostics in the session review warning.
- Add regression coverage for stationary clip tails, low in-swing motion, weak single-camera wrists, and implausible scale.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `swing-analysis`: assess motion over the active swing, include per-camera wrist visibility diagnostics, and make warnings identify the evidence behind an unreliable verdict.
- `desktop-review-ui`: present the specific quality causes and corrective guidance alongside low-confidence results.

## Impact

- Backend tracking quality assessment and analysis serialization under `backend/src/golf_sim/analysis`.
- Pose-confidence aggregation from the existing per-camera 2D pose outputs in `backend/src/golf_sim/analysis/cli.py`.
- Frontend tracking-quality API types and session warning presentation.
- Focused backend quality/analysis tests and frontend build validation.