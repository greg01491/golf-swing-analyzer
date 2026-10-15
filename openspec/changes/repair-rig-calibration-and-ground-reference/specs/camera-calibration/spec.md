## MODIFIED Requirements

### Requirement: Rig Calibration Computation

The system SHALL compute lens intrinsics and inter-camera extrinsics asynchronously,
and SHALL validate candidate geometry independently of its fitting inliers before activation.

#### Scenario: Compute requires a plausible measured camera distance

- **WHEN** computation is requested
- **THEN** camera separation must be a number between 0.3 and 20 metres, otherwise the request is rejected

#### Scenario: Computation runs in the background and is pollable

- **WHEN** computation starts
- **THEN** progress reports running stages followed by done with a result or error with guidance
- **AND** another compute request while running returns current status rather than starting a second solve

#### Scenario: Intrinsics are solved per camera from pooled board views

- **WHEN** lens calibration runs
- **THEN** at least six usable measured-board views are required per camera
- **AND** only captures with compatible camera identity, image orientation, resolution and validated capture-mode provenance are pooled
- **AND** board dimensions are converted from the measured millimetre square size into metres
- **AND** enough independent usable frames remain for validation rather than evaluating only the fitted views

#### Scenario: Extrinsics are solved from body keypoint correspondences

- **WHEN** camera-position calibration runs
- **THEN** matched frame identities and timestamps are used across the views, retaining unambiguous single-person observations above 0.6 confidence in both cameras
- **AND** at least 100 fitting correspondences are required
- **AND** robust relative-pose estimation uses a fitting partition disjoint from temporally held-out validation frames
- **AND** insufficient held-out coverage is a validation failure, not permission to reuse fitting observations

#### Scenario: Scale comes from the measured camera separation

- **WHEN** translation is recovered as a direction
- **THEN** measured camera separation establishes metre scale
- **AND** baseline, depth and independent measured-length checks are included in the validation outcome

#### Scenario: Poor calibration is rejected, not saved

- **WHEN** a candidate exceeds configured lens/held-out reprojection limits, lacks required body-region coverage, fails depth/scale checks, or has incompatible capture evidence
- **THEN** it is not activated and the previous accepted calibration remains unchanged
- **AND** errors identify the failed camera, region, coverage or compatibility check
- **AND** a low fitting-inlier score alone cannot qualify the candidate

#### Scenario: Result is written in Pose2Sim's format

- **WHEN** camera calibration is accepted
- **THEN** the active bundle contains Pose2Sim-compatible per-camera name, size, matrix, distortions, Rodrigues rotation, metre translation and fisheye fields
- **AND** metadata retains correspondence count and a clearly labeled fitting error for compatibility
- **AND** the result separately reports per-camera held-out error distributions, acceptance coverage, body-region coverage, depth/scale checks, capture signatures and calibration fingerprint
- **AND** publication of the calibration and its validation metadata is atomic
- **AND** ground-reference readiness is reported separately rather than implied by a successful camera solve

### Requirement: Calibration Status Reporting

The system SHALL distinguish existence, age, camera compatibility, validated geometry,
and ground-reference readiness without equating missing evidence with successful calibration.

#### Scenario: Status fields

- **WHEN** calibration status is requested
- **THEN** existing file, age, stale, reprojection and broken fields remain readable
- **AND** status also distinguishes accepted, failed, incompatible and legacy-unverified validation evidence, with reasons
- **AND** camera-geometry acceptance and ground/target readiness are separately identified

#### Scenario: Stale calibration

- **WHEN** age exceeds the configured maximum
- **THEN** the calibration is reported stale
- **AND** age alone neither proves camera movement nor substitutes for compatibility and geometric validation

#### Scenario: Broken calibration

- **WHEN** recorded legacy mean error exceeds 50 px or current independent validation fails
- **THEN** the calibration is reported broken or failed with cause-specific guidance
- **AND** missing modern validation evidence is reported as legacy-unverified, not fabricated as a measured failure or valid result

## ADDED Requirements

### Requirement: Camera Capture Compatibility

The system SHALL bind accepted camera geometry to the evidence describing the rig and
capture mode used to validate it.

#### Scenario: Camera geometry settings differ

- **WHEN** camera identity, image dimensions, rotation or geometry-affecting lens settings differ from the accepted signature
- **THEN** the bundle is incompatible until independently revalidated or replaced
- **AND** the specific differences are reported before validated reconstruction is offered

#### Scenario: Frame-rate mode changes

- **WHEN** requested or delivered capture mode differs, including 60 fps versus 120 fps
- **THEN** compatibility requires evidence that the mode preserves geometry or a fresh independent validation
- **AND** the system does not claim that frame-rate change alone proves a camera moved
- **AND** equal image dimensions alone do not establish unchanged field of view

### Requirement: Measured Ground And Target Reference

The system SHALL provide a guided measured-board workflow that establishes a physical
ground plane, oriented target direction and golfer/ball side for an accepted camera bundle.

#### Scenario: Reference capture has physical evidence

- **WHEN** the operator captures the rigid measured board on the hitting surface
- **THEN** the workflow requires confirmation that the board is level, a marked board edge aligned with the intended target, and the golfer's side of that line
- **AND** both cameras must observe enough board geometry in synchronized frames to validate the reference
- **AND** insufficient visibility, unresolved orientation or inadequate geometry leaves the reference unaccepted with recapture guidance

#### Scenario: Ground reference is validated separately

- **WHEN** ground/target reference evidence is evaluated
- **THEN** reprojection, metric board geometry, repeatability and normal orientation are checked against configurable limits
- **AND** independent withheld reference frames validate the result
- **AND** neither a handheld intrinsics board nor body posture alone is promoted to a measured floor normal
- **AND** camera geometry remains separately reportable when only ground-reference capture fails

#### Scenario: Reference is bound to calibration

- **WHEN** a ground/target reference is accepted
- **THEN** its axes, units, coordinate convention, capture evidence and parent calibration fingerprint are retained
- **AND** replacing camera geometry invalidates that reference until it is re-established or explicitly revalidated
- **AND** an automatic ordinary-swing refit cannot install a new accepted reference