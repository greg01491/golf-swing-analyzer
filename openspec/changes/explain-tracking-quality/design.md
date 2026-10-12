## Context

See `proposal.md` for motivation. `analysis/quality.py` currently decides motion quality from every frame in the clip, although clips include stationary lead-in and follow-through. The existing analysis pipeline has detected address/top/impact frames, and Pose2Sim stores per-camera 2D keypoint confidence alongside each pose. The UI already lists backend quality warnings.

The latest 7-iron sample has 52.2% moving steps over the full clip but 73.9% between address and impact. During that active window, camera 1's left wrist is below 0.6 confidence in 29% of frames; calibration reports 0.2 px reprojection error and is not stale or broken.

## Goals / Non-Goals

**Goals:**

- Base motion reliability on the active swing window while preserving whole-clip movement as diagnostic context.
- Report per-camera wrist confidence coverage for the active swing and identify weak camera/keypoint combinations.
- Keep calibration warnings tied to physically implausible reconstructed scale.
- Preserve backward compatibility for callers that do not provide phases or per-camera pose confidence.

**Non-Goals:**

- Change pose estimation, triangulation, filtering, or calibration algorithms.
- Automatically recalibrate or modify camera settings.
- Claim that confidence coverage proves a 3D keypoint is accurate.
- Change the existing metric formulas or P-position proxies.

## Decisions

1. **Use address-to-impact motion for the reliability threshold.** Continue reporting the existing whole-clip `moving_fraction`, add `swing_moving_fraction`, and apply the existing 0.6 threshold to the active interval whenever phases exist. Whole-clip motion remains the fallback when phase bounds are absent. This avoids counting quiet lead-in and post-impact footage as lost tracking while still preserving the original signal for comparison. Alternatives considered: removing motion diagnostics would hide frozen runs; using a fixed time slice would not align across clips or frame rates.

2. **Aggregate wrist visibility per camera and side in the same active interval.** For each camera, count the share of address-through-impact frames where each wrist confidence is at least 0.6. Warn when coverage is below 80%, naming the camera and wrist and reporting the percentage. The 0.6 score threshold matches the pose confidence convention already used by rig keypoint matching; the 80% coverage threshold tolerates occasional occlusion while exposing the observed 29% weak-camera loss. Alternatives considered: averaging both wrists and cameras hides unilateral occlusion; using 2D confidence as proof of 3D correctness overstates what it measures.

3. **Separate tracking warnings from calibration warnings.** Low swing-window movement and low per-camera wrist coverage produce visibility/tracking guidance. Preserve the existing calibration recommendation only when reconstructed hand travel exceeds 4.5 m. Alternatives considered: recommending recalibration for every frozen run contradicts the healthy calibration report and can prompt unnecessary wizard work.

4. **Keep the quality result additive.** Preserve `moving_fraction`, `hand_vertical_range_m`, `reliable`, and `warnings`; add `swing_moving_fraction` and `camera_wrist_visibility`. Existing clients still receive the original fields, and the current UI can render more specific warning text without a new diagnostic screen. Alternatives considered: replacing `moving_fraction` would break API consumers and remove whole-clip context.

## Risks / Trade-offs

- [Risk] Address/impact phase errors can skew the quality interval. -> Mitigation: retain the whole-clip measure, require valid bounds, and fall back when bounds are unavailable.
- [Risk] A wrist can be occluded from one view while still triangulating well from the other. -> Mitigation: use confidence warnings as camera-specific evidence and keep the measured 3D motion/scale checks in the verdict.
- [Risk] Confidence thresholds are heuristic and model-dependent. -> Mitigation: report observed coverage, name the threshold in diagnostics, and avoid asserting that a specific camera is definitively broken.

## Migration Plan

1. Extend quality assessment with optional swing bounds and per-camera wrist coverage.
2. Collect those confidence summaries from existing 2D pose JSON during session analysis.
3. Update focused quality tests and the frontend quality type; the existing warning list displays the more specific explanations.
4. Reprocess the 7-iron session and verify stationary clip tails no longer drive the motion warning, while camera 1 wrist weakness is named and calibration is not blamed.
5. Rollback by reverting the additive diagnostics and restoring whole-clip motion gating; no stored session files or calibration data need migration.