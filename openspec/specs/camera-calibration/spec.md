# camera-calibration Specification

## Purpose

Produce the two-camera rig calibration that 3D triangulation depends on: per-camera
lens intrinsics from a printed checkerboard, plus the relative position and
orientation of the two cameras, scaled to metres by a measured camera separation.
Implemented by `golf_sim.pose.board_image`, `board_detect`, `rig_calibration`,
`calibrate` and `wizard`.

## Requirements

### Requirement: Printable Calibration Board

The system SHALL generate a printable checkerboard sized from the configured
inner-corner count.

#### Scenario: Board PNG is generated for A4

- **WHEN** the calibration board image is requested
- **THEN** a PNG sized for A4 at 300 DPI is returned
- **AND** it contains `(corners + 1)` squares per axis for the configured
  `calibration.checkerboard_corners`
- **AND** it carries printed instructions to measure one square with a ruler and enter
  that size in the wizard, because printers rescale

#### Scenario: Board too large to print is refused

- **WHEN** the configured corner count cannot fit on A4 at the nominal square size
- **THEN** generation fails with an error rather than emitting a clipped board

### Requirement: Guided Calibration Capture

The system SHALL let the operator capture calibration shots through a wizard that
marks each shot with its purpose, and SHALL report progress back.

#### Scenario: Intrinsics shot is tagged per camera

- **WHEN** a calibration shot is captured with kind `intrinsics` for a given camera role
- **THEN** the session is marked with `calibration_shot.json` recording `kind`,
  `for_camera` and the capture time
- **AND** the marker is invalid unless the kind is `intrinsics` or `extrinsics` and the
  camera is one of the configured roles

#### Scenario: Board detection gives immediate feedback

- **WHEN** an intrinsics shot is marked
- **THEN** a sample of frames from each camera clip is checked for a fully visible
  checkerboard
- **AND** the per-camera detected-frame counts and the number of samples checked are
  returned so the wizard can tell the operator whether the shot was usable

#### Scenario: Extrinsics shot uses the golfer, not the board

- **WHEN** a calibration shot is captured with kind `extrinsics`
- **THEN** the session is marked without board detection, because the person's body
  keypoints seen from both cameras are the calibration signal

#### Scenario: Calibration shots are listed and clearable

- **WHEN** the operator lists calibration shots
- **THEN** every marked session is returned with its id, kind, target camera, creation
  time and board detection counts
- **AND** clearing calibration shots deletes those marked sessions and returns how many
  were deleted, so a fresh run is not polluted by stale shots

#### Scenario: Calibration captures stay out of the swing library

- **WHEN** sessions are listed for review
- **THEN** any session carrying `calibration_shot.json` is excluded

### Requirement: Rig Calibration Computation

The system SHALL compute lens intrinsics and inter-camera extrinsics from the captured
shots, run asynchronously with progress reporting.

#### Scenario: Compute requires a plausible measured camera distance

- **WHEN** computation is requested
- **THEN** `camera_distance_m` must be a number between 0.3 and 20 metres, otherwise
  the request is rejected as invalid

#### Scenario: Computation runs in the background and is pollable

- **WHEN** computation starts
- **THEN** it runs on a background thread and its state is reported as `running` with a
  human-readable stage, progressing to `done` with a result or `error` with a message
- **AND** requesting computation again while one is already running returns the current
  status instead of starting a second run

#### Scenario: Intrinsics are solved per camera from pooled board views

- **WHEN** lens calibration runs for a camera
- **THEN** board detections from all of that camera's intrinsics clips are pooled
- **AND** at least 6 usable board views are required, otherwise it fails with a
  data error
- **AND** the object points are built from `calibration.checkerboard_square_size_mm`
  converted to metres, so the solve is metrically scaled

#### Scenario: Extrinsics are solved from body keypoint correspondences

- **WHEN** camera-position calibration runs
- **THEN** 2D pose estimation is run on the extrinsics clip and keypoints are matched
  between the two views, keeping only frames with exactly one person detected and
  keypoints above 0.6 confidence in both views
- **AND** at least 100 correspondences are required, otherwise it fails with a data error
- **AND** the essential matrix is solved with RANSAC and decomposed into a rotation and
  a unit translation

#### Scenario: Scale comes from the measured camera separation

- **WHEN** the recovered translation between the cameras is a direction only
- **THEN** it is scaled to `camera_distance_m`, giving the reconstruction absolute
  metric scale

#### Scenario: Poor calibration is rejected, not saved

- **WHEN** either camera's lens RMS reprojection error exceeds 5 px, or the extrinsic
  mean reprojection error exceeds 50 px
- **THEN** computation fails with guidance to re-capture rather than writing a
  calibration file that would silently corrupt every later reconstruction

#### Scenario: Result is written in Pose2Sim's format

- **WHEN** calibration succeeds
- **THEN** `Calib_rig.toml` is written into `calibration.dir` with a section per camera
  carrying `name`, `size`, `matrix`, `distortions`, `rotation` (Rodrigues vector),
  `translation` (metres) and `fisheye`
- **AND** a `metadata` section records `n_correspondences` and
  `mean_reprojection_error_px`
- **AND** the returned summary reports the calibration file path, per-camera lens view
  counts and RMS, correspondence count, mean reprojection error and the estimated
  person height

### Requirement: Calibration Status Reporting

The system SHALL report whether a usable calibration exists and whether it should be
redone.

#### Scenario: Status fields

- **WHEN** calibration status is requested
- **THEN** it reports `exists`, the calibration `file`, its `age_days`, whether it is
  `stale`, its `reprojection_error_px` and whether it is `broken`

#### Scenario: Stale calibration

- **WHEN** the most recent calibration file is older than `calibration.max_age_days`
- **THEN** it is reported as stale, because cameras drift and get bumped over time

#### Scenario: Broken calibration

- **WHEN** the recorded mean reprojection error exceeds 50 px
- **THEN** the calibration is reported as broken so the UI can prompt for recalibration
