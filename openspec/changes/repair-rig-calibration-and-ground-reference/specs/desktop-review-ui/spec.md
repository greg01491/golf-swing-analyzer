## ADDED Requirements

### Requirement: Independent Calibration Evidence Display

The system SHALL display fitting quality, held-out validation, camera compatibility and
ground/target readiness as separate calibration states.

#### Scenario: Candidate computation completes

- **WHEN** the wizard receives a calibration result
- **THEN** it shows per-camera held-out errors and coverage separately from fitting-inlier errors
- **AND** a failed or unverified candidate cannot be presented as accepted based only on its fitting score
- **AND** the operator can identify the active accepted bundle and any failed candidate without losing the previous accepted result

#### Scenario: Capture setup no longer matches

- **WHEN** current camera settings are incompatible or legacy provenance is incomplete
- **THEN** the UI identifies the differing or missing evidence and the required validation/recapture action
- **AND** a frame-rate difference is not described as proof of physical camera movement
- **AND** video review remains available without asserting metric readiness

### Requirement: Guided Ground Reference Capture

The system SHALL guide the operator through capturing and validating a level measured
board, marked target edge and golfer/ball side using the existing camera previews.

#### Scenario: Capture prerequisites are visible

- **WHEN** ground-reference capture is selected
- **THEN** the wizard identifies the accepted camera bundle and requires measured board size, level confirmation, target-edge alignment and golfer-side orientation
- **AND** capture feedback shows whether both views provide enough visible geometry

#### Scenario: Reference capture fails

- **WHEN** visibility, orientation, repeatability or geometric validation is insufficient
- **THEN** the failure reason and a specific corrective action are shown
- **AND** the UI does not claim that all calibration failed when only ground-reference readiness is missing
- **AND** cancellation or failure does not replace accepted evidence

#### Scenario: Reference capture succeeds

- **WHEN** an independently checked reference is accepted for the active camera bundle
- **THEN** ground/target readiness and provenance are shown distinctly from camera geometry
- **AND** subsequent analysis is eligible for validated directional metrics only when all other metric dependencies also pass
- **AND** the UI does not claim certified shoulder/hip accuracy merely from completing the wizard

#### Scenario: Old sessions need explicit reconstruction

- **WHEN** an older session lacks matching reference/calibration evidence
- **THEN** it retains its existing unverified measurement state
- **AND** the UI distinguishes saved-landmark metric reanalysis from explicit pose reconstruction using a deliberately selected compatible calibration
- **AND** reading a session never silently recalibrates, reprocesses or overwrites its evidence