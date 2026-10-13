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

2. **Separate diagnostic confidence from actual triangulation dropout per camera and wrist.** Report coverage at 0.6 as an advisory and at Pose2Sim's actual 0.3 triangulation cutoff as blocking evidence; mark the reconstruction unreliable only when cutoff coverage is below 80%. The 0.6 threshold matches the pose-confidence convention used by rig keypoint matching, while 0.3 is the installed Pose2Sim triangulator's default for rejecting 2D points. This avoids disabling checkpoints merely because a usable point is less certain. Alternatives considered: copying one wrist onto the other erases real hand separation and distorts lead-arm measurements; averaging both cameras hides unilateral failures.

3. **Separate tracking warnings from calibration warnings.** Low swing-window movement and per-camera wrist coverage below Pose2Sim's triangulation cutoff produce blocking visibility/tracking warnings. Lower confidence above the cutoff produces advisory guidance only. Preserve the existing calibration recommendation only when reconstructed hand travel exceeds 4.5 m. Alternatives considered: recommending recalibration for every confidence dip contradicts the healthy calibration report and can prompt unnecessary wizard work.

4. **Keep the quality result additive and distinguish advisories.** Preserve `moving_fraction`, `hand_vertical_range_m`, `reliable`, and `warnings`; add `swing_moving_fraction`, per-threshold `camera_wrist_visibility`, and `advisories`. Advisory-only sessions remain reliable for checkpoint navigation, while blocking warnings still disable it. Existing clients can ignore the new fields. Alternatives considered: treating every confidence advisory as unreliable overstates risk; omitting advisories hides camera conditions that can still affect precision.

5. **Replace boundary-nearest fallbacks with labeled phase-progress estimates.** When no proxy crossing occurs, choose the frame nearest the midpoint of the proxy's phase-start and phase-end values if the series changes meaningfully; label it estimated and keep it selectable when tracking is reliable. If the phase is degenerate, preserve a diagnostic frame but mark it unavailable. Keep P1/P4/P7 anchors and P10's finish peak. Alternatives considered: marking every miss unavailable removes useful checkpoints; silently presenting the phase-start nearest frame as detected produced the observed address-as-P3 error; copying one wrist onto the other distorts real geometry.

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