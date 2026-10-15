## 1. Independent Evidence And Contracts

- [x] 1.1 Extend existing calibration fixtures with known camera poses, lens distortion, baseline, board dimensions and independent expected projections; verify geometry/units without deriving the oracle from production helpers.
- [x] 1.2 Add regressions for low fitting-inlier error with bad held-out geometry, missing body-region coverage, degenerate/negative-depth solutions, and missing frame files; verify the current single-score/positional-pairing behavior fails the intended cases before repair.
- [x] 1.3 Define versioned candidate, accepted-bundle, validation-report and capture-signature contracts; verify legacy TOMLs remain readable as unverified and missing evidence cannot default to accepted.
- [x] 1.4 Add validated configuration fields for partition gaps/counts, per-camera error/coverage gates, scale checks, board visibility and reference repeatability; verify invalid settings are rejected and engineering defaults are documented separately from physical accuracy claims.

## 2. Held-Out Camera Validation

- [x] 2.1 Pair observations by recorded frame identity/time and partition whole intrinsics capture groups plus disjoint extrinsics time blocks before fitting; verify dropped files, adjacent repeated frames and inadequate held-out evidence cannot leak into or bypass validation.
- [x] 2.2 Compute separate fitting and held-out reports for both cameras, including median/tail errors, threshold coverage and shoulder/pelvis/head/leg support; verify a candidate that only fits selected inliers is rejected.
- [x] 2.3 Validate positive depth, baseline scale and independent measured lengths; verify low pixel residual alone cannot accept a reflected, wrong-scale or physically implausible solution.
- [x] 2.4 Integrate candidate acceptance into existing asynchronous wizard computation; verify a failed/cancelled candidate returns precise guidance without replacing the active calibration and concurrent requests do not start duplicate computations.

## 3. Distortion, Identity And Reconstruction Evidence

- [x] 3.1 Make distorted-pixel, undistorted-coordinate and reprojection conventions explicit across person association and triangulation adapters; verify known distorted-camera fixtures fail when correction is omitted/doubled and pass with exactly one consistent correction.
- [x] 3.2 Preserve the associated person's per-frame landmark support and rejection/interpolation/held-fill provenance alongside TRC output; verify downstream confidence uses the triangulated golfer rather than raw person zero and does not treat filled coordinates as observations.
- [x] 3.3 Derive and record the supported Pose2Sim world-to-TRC transform and units; verify known basis vectors, rotations, axis permutations, translations and metre-scale points round-trip independently.
- [x] 3.4 Add per-session two-view/body-region reconstruction checks against the exact snapshot; verify bad session geometry is flagged despite a previously low calibration fitting score, and full-frame/headless reconstruction behavior remains intact.

## 4. Compatibility And Safe Bundle Activation

- [x] 4.1 Record stable camera identities, roles, image dimensions, applied rotations, requested/delivered capture mode and geometry-affecting control readbacks; verify unknown fields remain unknown and exposure/gain changes do not falsely imply changed camera geometry.
- [x] 4.2 Implement compatibility decisions for identity/resolution/rotation/lens changes and frame-rate-mode changes; verify 60-to-120 fps requires validation/equivalence evidence without claiming movement, while small delivered-FPS variation within the same requested mode is handled correctly.
- [x] 4.3 Publish accepted immutable bundles through an atomic active pointer and retain rollback candidates; verify interruption/failure cannot expose a half-written active calibration or silently select an incompatible older bundle.
- [x] 4.4 Snapshot calibration/provenance per session and require explicit compatible-evidence selection for historical reconstruction; verify reads, candidate computation and saved-landmark metric reanalysis do not replace old snapshots or rewrite recordings.

## 5. Measured Ground And Target Reference

- [x] 5.1 Extend calibration capture metadata/API for a rigid measured board on the hitting surface, independent level confirmation, marked target edge and golfer-side selection; verify ordinary handheld intrinsics captures and a bare validated checkbox cannot authorize a measured floor reference.
- [x] 5.2 Detect and triangulate board corners in both views, resolve oriented axes and estimate the plane against known board geometry; verify synthetic perspective/distortion cases, axis reversals, normal flips and ambiguous orientation are accepted or rejected correctly.
- [x] 5.3 Validate withheld reference frames, repeated placements, per-view corner span, reprojection, measured lengths and normal repeatability; verify clipped/small/oblique boards leave readiness incomplete without replacing an accepted camera bundle or reference.
- [x] 5.4 Bind accepted reference evidence to its parent camera bundle and transfer axes through the recorded TRC transform; verify replacing calibration invalidates the old reference and up/target/ball directions remain orthogonal with correct anatomical signs.
- [x] 5.5 Generate exact filtered-TRC source binding plus calibration/reference fingerprints for the existing metric-confidence handoff; verify raw/filtered swaps, tampered metadata and unrelated-session fingerprints cannot promote estimated/unavailable measurements to valid.

## 6. Wizard, Readiness And Operator Guidance

- [x] 6.1 Expose separate fitting, held-out-validation, compatibility and ground-readiness states through existing API/status endpoints; verify legacy fields stay readable and failed candidates remain distinct from the active accepted bundle.
- [x] 6.2 Extend the existing wizard with measured reference capture, two-view visibility feedback, orientation/level confirmation and cause-specific failure/cancel/retry states; verify the operator can complete the flow without manually editing reference vectors and a reference-only failure is not described as total calibration failure.
- [x] 6.3 Display incompatibility and legacy-evidence guidance, distinguish metric reanalysis from explicit 3D reconstruction, and retain manual video review; verify the UI never silently recalibrates/reprocesses sessions or claims angle certification from wizard completion.

## 7. Integration And Independent Physical Acceptance

- [x] 7.1 Run focused calibration, reconstruction, config, API, reference-transfer and companion metric-confidence tests against verified checkout imports, then the full backend suite, Ruff/Black, frontend tests/lint/build and strict OpenSpec validation; verify failures introduced by this change are resolved and existing warnings are reported separately.
- [x] 7.2 Perform desktop/mobile browser checks for candidate failure, incompatible settings, legacy bundles, successful reference capture and missing-ground readiness; verify controls, reasons and active-bundle identity remain readable and capture/video review is not falsely advertised as metric certification.
- [x] 7.3 Document the rig protocol before collecting a new dedicated acceptance capture: fixed camera settings, measured baseline/lengths, independent board level/target orientation, optical sync evidence, known rotations and uncertainty bounds; verify this data is withheld from fitting, model selection and threshold tuning.
- [ ] 7.4 Run the independent hardware protocol and document per-camera held-out coverage/errors, scale/reference repeatability, event alignment and defensible shoulder/hip angle error bounds; verify all predeclared tolerances pass or leave acceptance explicitly blocked with the failed evidence named.
- [x] 7.5 Update setup/calibration guidance and the original project spec/plan/tasks, record migration/rollback behavior, and reconcile the companion metric-accuracy validation record only with actually observed evidence; verify neither change's physical gate is closed merely because software tests or a diagnostic ordinary-swing refit pass.

Task 7.4 requires a new independent physical rig capture following
`docs/calibration-validation.md`. No personal calibration was activated and no new
hardware acceptance footage was collected during implementation. Do not archive this
change or close the companion metric-accuracy gate until that evidence passes.