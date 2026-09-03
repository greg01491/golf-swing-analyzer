# pose-reconstruction Specification

## Purpose

Turn a captured session's two video clips into a single 3D landmark trajectory: 2D
keypoints per camera via Pose2Sim/RTMPose, then person association, triangulation and
filtering into a TRC file that swing analysis reads. Implemented by
`golf_sim.pose.project`, `estimate`, `reconstruct` and `golf_sim.trc`.

## Requirements

### Requirement: Pose Project Preparation

The system SHALL assemble a Pose2Sim project inside the session directory before
running any pose stage, so the session stays self-contained.

#### Scenario: Clips are staged into a project

- **WHEN** pose estimation is prepared for a session
- **THEN** every `camera_*.mp4` in the session is copied into
  `<session>/pose2sim/videos/`
- **AND** a Pose2Sim `Config.toml` is installed into `<session>/pose2sim/`

### Requirement: Per-Camera 2D Pose Estimation

The system SHALL estimate 2D body keypoints for each camera clip.

#### Scenario: Estimation is driven by config

- **WHEN** 2D pose estimation runs
- **THEN** the model named by `pose.pose_model` is run in the accuracy/speed tradeoff
  named by `pose.mode`
- **AND** detection display is always disabled, because the backend runs headless

#### Scenario: Landmark output per camera

- **WHEN** estimation completes
- **THEN** one per-frame keypoint JSON directory exists per camera under
  `<session>/pose2sim/pose/`
- **AND** the result reports the project directory, the landmark directories and any
  overlay videos

#### Scenario: Debug overlay videos

- **WHEN** `pose.save_debug_video` is enabled
- **THEN** a `<camera>_pose.mp4` overlay video with the skeleton drawn on the golfer is
  produced per camera
- **AND** overlays are transcoded to H.264 so the in-app player can decode them

#### Scenario: Estimation that produces nothing fails loudly

- **WHEN** no landmark output is produced
- **THEN** estimation raises an error rather than letting reconstruction proceed on an
  empty project

### Requirement: 3D Triangulation

The system SHALL triangulate the per-camera 2D keypoints into a filtered 3D landmark
trajectory in metres.

#### Scenario: Calibration is required

- **WHEN** reconstruction starts
- **THEN** the rig's `Calib*.toml` is copied from `calibration.dir` into the session's
  pose project
- **AND** reconstruction fails with a missing-calibration error if none exists

#### Scenario: Reconstruction stages

- **WHEN** reconstruction runs
- **THEN** person association, triangulation and filtering are run in that order
- **AND** the golfer is treated as a single person and the full frame range is kept, so
  no part of the swing is auto-trimmed

#### Scenario: Reconstruction output

- **WHEN** triangulation and filtering complete
- **THEN** at least one `.trc` file exists under `<session>/pose2sim/pose-3d/`
- **AND** reconstruction fails with an error if no `.trc` was produced

#### Scenario: Missing 2D input is detected

- **WHEN** reconstruction is run for a session with no per-camera landmark directories
- **THEN** it fails with a not-found error naming the missing 2D pose output

### Requirement: Headless Reconstruction Safety

The system SHALL force the pose stack into a headless configuration before
reconstruction runs on a worker thread.

#### Scenario: Plotting stack is preloaded on the main thread

- **WHEN** the API server starts with `processing.auto_process` enabled
- **THEN** the pose filtering stack is imported on the main thread with a non-interactive
  plotting backend
- **AND** filter plot saving and figure display are disabled, because initialising the
  GUI toolkit first on a worker thread deadlocks the server

#### Scenario: Preload failure does not block serving

- **WHEN** the preload fails, for example because the optional pose dependency is not
  installed
- **THEN** the server logs a warning and still starts

### Requirement: Landmark Sequence Access

The system SHALL read TRC files into a landmark sequence that analysis and the UI can
query by marker name.

#### Scenario: Sequence contents

- **WHEN** a TRC file is read
- **THEN** the sequence exposes `marker_names`, per-frame `times` in seconds, and
  coordinates shaped frames × markers × 3 in metres
- **AND** it derives `n_frames` and `fps` from the time column

#### Scenario: Untracked markers are preserved as gaps

- **WHEN** a marker's coordinate is missing in a frame
- **THEN** it is represented as NaN rather than an interpolated or zeroed value, so
  downstream quality assessment can see the gap

#### Scenario: Marker lookup

- **WHEN** analysis asks for a named marker such as `RWrist`
- **THEN** its per-frame trajectory is returned
- **AND** the sequence can be asked whether a marker exists before requesting it

### Requirement: Filtered Output Preference

The system SHALL prefer the filtered triangulation output over the raw one wherever a
session's 3D data is consumed.

#### Scenario: Filtered TRC wins

- **WHEN** a session's 3D landmarks are loaded and both filtered and unfiltered `.trc`
  files exist
- **THEN** the filtered file is used

#### Scenario: Fallback to unfiltered

- **WHEN** only an unfiltered `.trc` exists
- **THEN** it is used instead of failing
