# Independent Calibration And Turn Validation

This protocol is an acceptance gate, not a calibration fitting procedure. Record the
chosen settings and tolerances before collecting acceptance data. Do not reuse these
captures for fitting, model selection, or threshold tuning. A failed gate stays failed
until a new, separately collected acceptance capture passes.

## 1. Fix And Record The Rig

- Secure both cameras. Record device identities, dimensions, rotation, requested frame
  mode and geometry-affecting focus/zoom settings. Use the same mode for calibration and
  swings. A change from 60 to 120 fps needs fresh validation, not an assumption of an
  unchanged field of view. Slight delivered-FPS variation within one requested mode is
  not itself a different optical calibration.
- Measure lens-to-lens separation and its uncertainty with a tape measure. Record the
  physical board square size and uncertainty. Do not copy nominal printed dimensions.
- Capture a shared optical event in both views and determine the source-frame alignment.
  Record a defensible timing uncertainty. Equal encoded FPS is not proof of camera sync.
- Keep exposure/gain changes distinct from geometry changes. Unknown identity or lens
  readbacks remain unverified; do not fill missing old metadata with current settings.

## 2. Fit And Independently Validate Cameras

Capture independent lens clips per camera, including the whole board at different image
positions and orientations. The solver reserves entire captures before fitting. Capture
a slow whole-body movement for camera position with head, shoulders, hips and legs visible
in both views. A disjoint temporal block and time gap are reserved for validation.

Current engineering limits are lens RMS <=5 px, per-camera held-out median <=5 px,
95th-percentile error <=15 px, >=80% acceptance coverage in every required body region,
and >=95% positive depth. At least 100 held-out correspondences over 20 withheld frames
are required. These checks are necessary but do not certify physical angles or scale.
The fitting-inlier score remains labeled fit-only. Do not increase limits to pass a swing.

Verify independent known lengths across the working volume, not only camera baseline.
Document reconstructed length error and uncertainty. Reflecting geometry or placing points
behind either camera is failure even if image residuals are low.

## 3. Measure Ground And Target

Use the rigid measured printed board on the hitting surface, independently checked with
a level. Mark its first inner corner and align the row from that corner toward the target.
Both cameras must see the board. Capture a placement, then repeat with the same orientation.
Identify the marked origin as FIRST or LAST in each annotated preview, and state the
golfer's side relative to the board rows. Ambiguous labels require recapture, not guessing.

The implementation validates corner reprojection <=2 px, reference-axis repeatability
<=3 degrees and relative measured-length error <=5%, with sufficient image span in both
views. These engineering tolerances do not replace the level measurement. A tiny, clipped
or very oblique board cannot authorize a reference; change framing/capture evidence and
revalidate the affected camera setup if necessary. Do not silently relax visibility gates.

Record the camera bundle and ground-reference fingerprints, capture identities, measured
dimensions, level/target evidence, and the reference uncertainty. Replacing camera geometry
invalidates its ground reference until independently revalidated.

## 4. Acceptance Capture And Angular Evidence

Collect a dedicated capture after fitting and reference selection are frozen. Include
independently measured rigid rotations and lengths near the shoulder/hip working volume,
followed by swings with well-supported landmarks. Record the measurement method and its
uncertainty separately from pose-model confidence.

Before capture, select a defensible angular error limit and measurement uncertainty for
the intended use. If the independent method cannot resolve that limit, acceptance is
blocked; do not substitute a 2D projected shoulder line for a 3D turn angle. A rigid test
object validates camera geometry, not the pose model's anatomical landmark accuracy.
Both parts need evidence before a shoulder/hip accuracy claim is justified.

Review synchronized address, top and impact frames, the actual peak-backswing measurement
interval, and directional signs for the configured handedness. Report per-camera/body-region
coverage, median/tail reprojection error, positive depth, known-length error, reference
repeatability, event alignment and measured angular differences with uncertainty bounds.

## 5. Record The Outcome

Use an evidence record containing:

- Capture/device/settings identities and calibration/reference/TRC fingerprints.
- Training/held-out/acceptance split with an explicit no-leakage declaration.
- Predeclared limits and measured results, including missing/occluded observations.
- Independent measurement and synchronization methods with uncertainty.
- Passed, failed or blocked status for geometry, reference and anatomical angle accuracy.

Only observed passing evidence can close physical acceptance in the calibration repair
and metric-accuracy changes. Automated synthetic tests, a diagnostic refit on an ordinary
swing, or wizard completion alone do not close either gate. Personal recordings remain
local unless separately approved for inclusion in a test corpus.

## Historical Sessions And Rollback

Accepted camera bundles are immutable and activated by an atomic pointer. Candidate
failure/cancellation leaves the active bundle unchanged. Browsing and metric reanalysis
never recalibrate or replace a session snapshot. Explicit reconstruction identifies the
active bundle, requires recorded compatibility, and archives previous calibration, 3D,
metadata and metrics under that session's reconstruction history before rebuilding.

If reconstruction fails, keep the archive and the failure reason. Do not call the partial
new result validated or silently adopt incompatible geometry. Rollback must use deliberate,
compatible evidence and preserve the original fingerprints; old legacy files are not
promoted to current accepted status merely because they are readable.