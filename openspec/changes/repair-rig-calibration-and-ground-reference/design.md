## Context

See proposal.md and the three capability deltas for motivation and external contracts.
The existing solver uses undistorted person correspondences, but reconstruction inherits
a demo default that does not correct distortion. The saved summary evaluates recovered
fitting inliers in one camera. Large rejected gaps can subsequently become held coordinates.
The implemented metric-confidence change rejects unsupported geometry, but no supported
capture workflow currently supplies its measured ground/target evidence.

Read-only evidence from the current rig:

| Check | Finding | Limit |
| --- | --- | --- |
| Saved calibration summary | 0.2 px fitting error, 612 retained correspondences | Not a held-out or whole-body accuracy score |
| Original calibration observations | 4,067 high-confidence matches over 180 frames; 2.11 px median two-view error | Original videos were deleted; camera-movement comparison is unavailable |
| Recent swing diagnostic | Fit on frames 0-179, evaluate 180-359; 4,363 fit and 4,193 held-out high-confidence pairs | One ordinary swing is not an approved calibration capture |
| Saved versus diagnostic camera geometry | Held-out median 23.9 versus 3.19 px; within 15 px, 30.0% versus 98.4% | Shows a promising geometry repair, not certified body angles |
| Capture modes | Calibration 60 fps, swings 120 fps, same dimensions and portrait rotation | Mode changed; physical movement or field-of-view change is not proven |
| Lens-correction-only experiment | Did not consistently improve the old geometry | Distortion consistency is necessary, not a complete repair by itself |

Nothing in that investigation activated a new calibration or rewrote recordings. The
diagnostic refit must not become an automatic ordinary-swing calibration feature.

## Goals / Non-Goals

**Goals:**

- Reject unreliable camera geometry before it silently propagates into swing metrics.
- Establish a real measured ground/target reference through an operator-usable workflow.
- Keep accepted calibration, reference and reconstruction provenance internally consistent.
- Make independent validation and missing evidence visible without overclaiming accuracy.

**Non-Goals:**

- Replacing Pose2Sim/RTMPose or retuning the metric formulas from the companion change.
- Automatically refitting the rig on every swing, inferring the floor from a bent golfer,
  or accepting reference metadata solely because an operator marks it validated.
- Automatically recovering deleted videos, migrating personal recordings, or publishing.
- Claiming low reprojection residual alone establishes correct scale, physical angles,
  camera synchronization or anatomical landmark accuracy.

## Decisions

### 1. Independent capture partitions and a richer acceptance report

Keep OpenCV intrinsics and robust relative-pose solvers. Split before fitting: reserve
whole intrinsics captures/view groups and contiguous extrinsics time blocks, with a
configurable time gap, so adjacent duplicate poses cannot leak into validation. Require
enough fitting samples, withheld frames and shoulder/pelvis/head/leg observations.
Pair frames by recorded identity/time, not positional zip of possibly missing JSON files.
Insufficient independent evidence fails explicitly; no fallback to training-only scoring.

Evaluate both cameras in their original distorted pixel coordinates. Report fitting
inliers separately from held-out counts, per-camera median/tail errors, fraction below
the error limit, per-region support, cheirality and metric baseline/known-length checks.
Count rejection and occlusion rather than filtering them out to improve the summary.
Reserve an additional dedicated verification capture for final acceptance, untouched by
candidate selection or threshold tuning.

Configure these checks under calibration rather than adding literal thresholds. Initial
engineering defaults are lens RMS at most 5 px, held-out median at most 5 px per camera,
95th percentile at most 15 px, at least 80% supported acceptance per required region,
and at least 95% positive-depth coverage. Retain existing minimum fitting counts.
Require at least 20 independent held-out frames and 100 held-out correspondences,
including required regions; defaults are not certified physical-accuracy guarantees.
Do not loosen limits just to pass the documented recordings. Add a measured-length
check whose tolerance reflects board measurement and image uncertainty.

Alternative rejected: increasing the existing 50 px guard or reporting only the RANSAC
inliers. Neither tests whether the fitted model explains unseen parts of the golfer.

### 2. One explicit distortion convention at every pose boundary

Document raw JSON coordinates as distorted image pixels. Use calibrated intrinsics and
distortion exactly once when evaluating associations and triangulating; evaluate residuals
by projecting back into raw pixels. Verify the actual installed Pose2Sim adapter behavior
with synthetic distorted cameras rather than assuming an option name has identical meaning
across stages. Pin or guard supported adapter behavior if needed, without editing the
installed dependency. Save the resolved convention with each reconstruction.

Retain per-frame/per-marker associated-person identity, 2D support, triangulation rejection,
interpolation and held-fill provenance beside the TRC. Existing display gap filling can
remain, but downstream measurement eligibility uses the observation provenance, not just
finite coordinates. Use the associated golfer, not arbitrarily person zero in raw detections.

Alternative rejected: changing only triangulation's undistort flag. Association and
residual computation must agree, and the observed stale geometry also needs repair.

### 3. Camera-mode signatures and immutable accepted bundles

A versioned bundle contains camera matrices, lens model, validation report and capture
signatures: stable device identity when available, role, delivered dimensions, applied
rotation, requested/delivered frame mode, geometry-affecting focus/zoom/crop settings and
known control readbacks. Record missing information as unknown, not default success.
Changes to identity/resolution/rotation/lens geometry invalidate compatibility. Frame-rate
mode differences require a fresh validation or recorded mode-equivalence evidence; this
does not assert a physical camera move or reject ordinary small delivered-FPS variation
inside the same requested mode. Geometry signatures exclude exposure/gain/brightness
controls that do not change the camera projection.

Write candidates in isolation, validate, then atomically activate an immutable bundle
identifier. A failed or cancelled candidate cannot modify the active pointer. Keep the
last accepted bundle for rollback, but never fall back to incompatible geometry silently.
Retain Pose2Sim's TOML format as an export inside the bundle. Legacy TOMLs are readable
as legacy-unverified and need a validation path; existence and age alone do not certify them.

Alternative rejected: mutating one global TOML then overwriting session copies. That
destroys the evidence needed to interpret older results or undo a failed solve.

### 4. A measured ground/target capture, not a guessed body axis

Extend the existing wizard after camera-geometry acceptance. Reuse the printed measured
checkerboard on a rigid backing placed on the hitting surface. Require the operator to
confirm level with an independent level, align a visibly marked board edge to the intended
target line, and confirm which side contains the golfer. The board axes then establish
ground normal, target arrow and perpendicular ball-facing direction with explicit signs.
This is not the ordinary handheld lens-calibration shot.

Capture multiple synchronized observations in both cameras, preserving a consistent physical
board pose and orientation labels. Detect corners with OpenCV, triangulate measured geometry
with the accepted camera model, and robustly estimate the board plane and oriented axes.
Validate on withheld frames and a repeated board placement with the same marked target
alignment. Disambiguate board indexing/normal flips using the marked edge, operator side
confirmation and both-view geometry; reject unresolved symmetry rather than guessing.

Initial reference checks use configurable corner residual limits (2 px per camera),
normal-repeatability tolerance (3 degrees) and measured-length relative tolerance (5%).
Require enough visible corner span and coverage in each view; characterize minimum usable
image span with synthetic/downsampled fixtures rather than assuming A4 always suffices.
If the current print is too small, clipped or too oblique, leave readiness incomplete and
give capture guidance. Do not silently promote low-resolution evidence, require a new sensor,
or claim that the user's level confirmation replaces geometric validation.

Ground acceptance is independent of camera acceptance. A reference failure leaves the
camera solve usable for non-ground-dependent diagnostics, but not for validated turns.
Replacing the parent camera bundle invalidates the reference until independently revalidated.

Alternative rejected: ankle-to-head direction, an arbitrary world axis, or a checkbox
that directly writes `validated: true` without observing the measured reference.

### 5. Transform provenance and explicit historical reconstruction

The calibration world is camera_1's frame; Pose2Sim exports a TRC axis conversion. Derive
and test the actual conversion, units and handedness from the supported adapter, storing
it explicitly rather than inferring it from filenames or body pose. Transform up/target/
ball vectors with the same rotation as the coordinates; translate board origin/points
where appropriate, never translate direction vectors. Normalize and check orthogonality.

After the selected filtered TRC is written, bind its exact fingerprint to the parent
camera and ground bundles and their validation reports. Adapt this generated evidence to
the existing analysis-reference contract; expand its reader to verify both bundle provenance
and source-artifact binding, not merely a trusted-looking string or boolean. Pure metric
code continues receiving evidence through public analysis inputs rather than reading files.

Snapshot accepted bundles for new captures/reconstructions. Saved-landmark metric reanalysis
does not repair geometry and must not adopt a new calibration. Explicit historical
reconstruction requires the operator to select compatible evidence, records the change,
and invalidates/regenerates downstream analysis and reference hashes. If original capture
compatibility cannot be established, stop with guidance. No session or media is rewritten
merely by browsing, computing a candidate, or reading status.

Alternative rejected: attach newly measured axes to old distorted coordinates just to
make them eligible for coaching. The coordinate artifact and its reference must agree.

### 6. Wizard/API states and truthful readiness

Expose separate camera validation, capture compatibility and ground readiness, each with
status, causes and provenance. Keep existing status fields readable for clients, but label
the old reprojection score as fit-only. Failed candidates have their own reports, distinct
from the active bundle. Preserve background compute/progress behavior and capture safety.
The UI offers targeted actions: improve landmark visibility, redo geometry at the current
mode, recapture the reference, or explicitly reconstruct a compatible old session.

Do not claim all calibration failed when only the ground reference is missing, and do not
claim angle accuracy when the wizard finishes. Existing per-metric confidence remains the
final eligibility rule. Update the companion change's physical-validation evidence only
after the independent acceptance protocol is actually performed.

## Risks / Trade-offs

- Sparse or correlated calibration motion -> disjoint temporal validation and body-region coverage, plus a separate acceptance capture.
- Lens-mode changes or unknown driver controls -> compatibility states with measured evidence rather than assumptions from equal dimensions.
- Small floor board or severe obliquity -> visibility/span gates and explicit incomplete readiness; no automatic threshold relaxation.
- Ambiguous checkerboard axes or an unlevel board -> marked orientation, independent level confirmation, repeat placements and rejection of unresolved flips.
- Low pixel residual but incorrect 3D scale or body angles -> positive-depth, known-length and independent angular validation with stated uncertainty.
- Deleted legacy videos -> retain existing files, do not promise historical certification from pose JSON alone.
- Companion change still in progress -> reuse its contracts without duplicating metric changes or closing its acceptance task automatically.

## Migration Plan

1. Add read-compatible bundle/status contracts and independent validation fixtures.
2. Add candidate validation, distortion/provenance integration and safe activation.
3. Add ground/target capture and source-bound TRC handoff, then wire wizard/readiness.
4. Leave legacy sessions/bundles unverified until explicit operator validation or reconstruction.
5. Run automated gates and an independent hardware acceptance capture. Record scale,
   reference-orientation, synchronization and shoulder/hip measurement uncertainty.

Rollback changes the active bundle only through an explicit compatibility-checked action;
existing snapshots remain immutable. Code rollback does not rewrite or falsely certify
newer reference metadata. No release or archive is part of this planning change.