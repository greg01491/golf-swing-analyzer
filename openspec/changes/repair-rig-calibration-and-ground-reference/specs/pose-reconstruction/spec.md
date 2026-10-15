## MODIFIED Requirements

### Requirement: 3D Triangulation

The system SHALL triangulate associated per-camera observations into metre-scale 3D
landmarks using compatible validated camera geometry and an explicit consistent lens model.

#### Scenario: Calibration is required

- **WHEN** reconstruction starts
- **THEN** a compatible calibration snapshot and its fingerprint are bound to the session
- **AND** missing calibration remains an explicit error
- **AND** failed or incompatible calibration is rejected with corrective guidance
- **AND** legacy geometry is identified as unverified rather than certified by a file's existence
- **AND** reprocessing never silently replaces an existing session snapshot with an unrelated active calibration

#### Scenario: Reconstruction stages

- **WHEN** reconstruction runs
- **THEN** person association, triangulation and filtering run in order for a single golfer over the full frame range
- **AND** association, triangulation and reprojection use consistent distortion and pixel-coordinate conventions
- **AND** correction is applied exactly once, not omitted or doubled
- **AND** per-camera support and reconstruction rejection reasons survive filtering or display gap filling

#### Scenario: Reconstruction output

- **WHEN** reconstruction completes
- **THEN** at least one TRC exists under the session pose-3d directory, otherwise reconstruction fails
- **AND** output identifies its calibration snapshot, coordinate transform, units, rejection/observed coverage and reference provenance
- **AND** held or interpolated samples cannot be presented as directly observed measurements solely because their coordinates are finite

#### Scenario: Missing 2D input is detected

- **WHEN** per-camera landmark directories are missing
- **THEN** reconstruction fails with an error naming the required input

## ADDED Requirements

### Requirement: Source-Bound Reference Transfer

The system SHALL transfer accepted ground/target evidence into the exact coordinate
convention of each generated landmark artifact before exposing it to metric analysis.

#### Scenario: Accepted reference reaches analysis

- **WHEN** reconstruction uses a camera bundle with an accepted matching ground reference
- **THEN** up, target and ball-facing directions are transformed consistently with the TRC coordinates
- **AND** the session records the exact selected TRC fingerprint plus parent calibration/reference fingerprints and validation provenance
- **AND** normalized axes preserve anatomical direction through rotation, axis permutation and handedness handling
- **AND** no user must manually invent or label unknown vectors as validated

#### Scenario: Evidence is missing or stale

- **WHEN** reference provenance is missing, mismatched or invalidated
- **THEN** dependent analysis remains estimated or unavailable under the existing metric-confidence contract
- **AND** the system does not infer measured ground from the skeleton to bypass this state

#### Scenario: Filtered artifact differs from raw artifact

- **WHEN** filtering produces a distinct TRC
- **THEN** provenance binds reference evidence to that actual artifact and its declared transform
- **AND** a fingerprint for the unfiltered or another session's file cannot authorize validated analysis of the filtered file

### Requirement: Session Reconstruction Validation

The system SHALL report observation-level reconstruction quality using the associated
golfer actually triangulated and the exact session calibration snapshot.

#### Scenario: Reconstruction exceeds geometric limits

- **WHEN** held-out or session observations fail per-camera/body-region reprojection, depth, scale or coverage checks
- **THEN** the affected reconstruction is not labeled validated merely because the calibration fitting score was low
- **AND** unsupported observations and affected landmarks remain identifiable downstream
- **AND** guidance distinguishes visibility, synchronization, capture compatibility and calibration geometry failures