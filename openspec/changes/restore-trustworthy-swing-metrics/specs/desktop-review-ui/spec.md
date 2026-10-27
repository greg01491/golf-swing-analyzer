## ADDED Requirements

### Requirement: Metric Value Availability And Verdict Are Distinct

The review UI SHALL distinguish whether a measurement value is available from whether it has a compatible target verdict or coaching eligibility.

#### Scenario: Estimated value has no compatible range
- **WHEN** a metric has a finite estimated value but no compatible range
- **THEN** the UI shows the value as estimated, omits in-range/out-of-range styling and explains the range incompatibility

#### Scenario: Metric is unavailable because evidence failed
- **WHEN** a metric is unavailable
- **THEN** the UI shows the specific evidence reason, such as unsupported marker, failed reconstruction validation, missing reference or invalid configuration
- **AND** it does not imply that P-position detection also failed when checkpoints are available

#### Scenario: Metric evidence is incomplete for only some measurements
- **WHEN** some metrics are valid or estimated and others are unavailable
- **THEN** each metric retains its own status and reason rather than hiding all values behind one session-wide unavailable state

### Requirement: Manual Marker And Metric Review

The review UI SHALL let the operator record per-camera, per-frame marker observations and per-metric judgments for a session without changing the original analysis.

#### Scenario: Mark a marker observation
- **WHEN** the operator reviews a video frame and selects a camera and marker
- **THEN** the operator can label that observation correct, occluded, mislocalized, or uncertain and add an optional note
- **AND** the label is visibly tied to the camera, frame, and marker

#### Scenario: Selected marker is highlighted on the camera overlay
- **WHEN** the operator selects a marker for review
- **THEN** the selected camera's pose overlay shows a pulsing indicator at that frame's saved 2D keypoint coordinate
- **AND** the indicator follows the selected camera's presented frame rather than assuming both camera frame indices represent the same exposure
- **AND** a missing keypoint coordinate is not replaced with a guessed position

#### Scenario: Mark a metric result
- **WHEN** the operator reviews a metric
- **THEN** the operator can label it correct, incorrect, or uncertain and optionally enter an expected value and note
- **AND** the computed value, status, range verdict, tips, and voice feedback remain unchanged

#### Scenario: Run a what-if exclusion analysis
- **WHEN** the operator selects marker observations to exclude and requests a diagnostic recalculation
- **THEN** the UI presents the separate what-if result alongside the unchanged original result
- **AND** unavailable dependent metrics remain visibly unavailable rather than being replaced by guessed values
- **AND** the result states that exclusions do not reconstruct or infer missing 3D positions
- **AND** the UI identifies the exclusions used for that result

#### Scenario: Reopen a reviewed session
- **WHEN** the operator reopens a session after adding review annotations
- **THEN** saved annotations remain associated with that session and its metric definition
- **AND** viewing or annotating the session does not rewrite captured videos, reconstruction artifacts, or original metrics

### Requirement: Evidence-Backed Review Queue

The manual review SHALL list affected metrics, markers, camera-native frames and rejection reasons from actual metric dependency evidence, grouping repeated failures while keeping individual frames accessible.

#### Scenario: Investigate rejected observation support
- **WHEN** the operator opens the issue table
- **THEN** rejected observations are restricted to each metric's required analysis frames
- **AND** selecting an observation seeks its camera to its native frame, selects the marker, highlights its saved point when available, and shows the saved judgment for that observation
- **AND** a combined reconstruction rejection does not identify either camera as the proven cause
- **AND** unknown camera frame mapping is reported without a guessed seek target

#### Scenario: Diagnose historical metrics without rewriting them
- **WHEN** saved metrics lack frame-level evidence
- **THEN** a read-only diagnostic uses the saved phase anchors and identifies its use of current settings separately from the original saved result
- **AND** no session artifacts or review annotations are changed
- **AND** target, reference, phase, timestamp and scale problems are separate from marker observations
- **AND** a failed target verdict alone does not create a tracking-failure row

#### Scenario: Default queue contains only measured camera-check failures
- **WHEN** the operator opens manual review
- **THEN** the default queue excludes passing camera observations and unresolved combined support rejections
- **AND** it shows only camera-native frames whose measured reprojection error, depth or confidence fails an existing check, with the measured value and configured limit visible
- **AND** a failed reprojection check is not presented as proof of a misplaced 2D marker because reconstruction or calibration can also cause the error
- **AND** unresolved support rejections remain available through an opt-in control
- **AND** missing bound calibration evidence is reported rather than replaced with guessed tolerance failures

#### Scenario: Largest reprojection errors are reviewed first
- **WHEN** measured camera failures are grouped for manual review
- **THEN** groups are ordered by their largest finite pixel reprojection error, descending
- **AND** each group's default selected frame is the frame with that largest error
- **AND** individual frame lists remain chronological and non-pixel checks are not compared numerically with pixel errors

#### Scenario: Review the other camera alongside a flagged observation
- **WHEN** the operator selects a frame in a marker issue group
- **THEN** the group includes review actions for the source view and the counterpart at the same clip time, using each camera's saved native frame rate
- **AND** the counterpart remains accessible even when it has no tolerance failure or separate queue row
- **AND** each view shows its own frame, saved judgment and flagged-or-comparison status
- **AND** missing counterpart mapping disables guessed navigation, and matching clip time does not claim verified exposure synchronization

### Requirement: Read-Only Continuous Crown Comparison Playback

The diagnostic UI SHALL play the existing source-bound crown-comparison videos without changing saved observations, independent judgments or metric output.

#### Scenario: Review candidate movement over time
- **WHEN** the operator opens comparison playback
- **THEN** normal, half and quarter speeds, looping, native-frame stepping and scrubbing are available
- **AND** paired camera switching retains clip time without claiming exposure synchronization
- **AND** unavailable image-tracking frames are explicitly identified and do not display a fabricated held candidate
- **AND** the player identifies detector and candidate colors and remains visibly diagnostic-only

#### Scenario: Preserve unfinished independent checks
- **WHEN** a swing view has incomplete independent frame judgments for the exact comparison
- **THEN** playback of that view is refused until its checks are complete
- **AND** viewing or streaming comparisons does not modify seed or validation sidecars