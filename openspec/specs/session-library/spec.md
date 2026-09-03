# session-library Specification

## Purpose

Store, list, serve and process captured swings. Each session is a directory on disk;
this capability exposes it to the desktop app as a browsable library with videos, 3D
landmarks and analysis results, and orchestrates the pose → 3D → metrics pipeline that
fills those results in. Implemented by `golf_sim.api.sessions` and the processing
orchestration in `golf_sim.api.server`.

## Requirements

### Requirement: Session Listing

The system SHALL list captured swings newest first with enough state for the UI to show
progress.

#### Scenario: Summary fields

- **WHEN** sessions are listed
- **THEN** each entry reports `id`, `created_at`, the `cameras` present, and the flags
  `has_pose`, `has_3d` and `has_metrics`

#### Scenario: Newest first by recorded timestamp

- **WHEN** sessions are sorted
- **THEN** ordering uses the metadata `created_at` normalised to UTC rather than the
  directory name, because the session naming format changed once and name ordering
  would interleave old and new sessions
- **AND** sessions with a missing or unparseable timestamp sort last

#### Scenario: Corrupt session does not break the library

- **WHEN** one session's `metadata.json` is missing or unparseable
- **THEN** it is still listed with empty metadata and the rest of the library loads
  normally

#### Scenario: Empty library

- **WHEN** no sessions directory exists yet
- **THEN** an empty list is returned rather than an error

### Requirement: Session Detail

The system SHALL return everything known about one session in a single response.

#### Scenario: Detail fields

- **WHEN** a session's detail is requested
- **THEN** the response carries `id`, its raw `metadata`, its `metrics` (null when not
  yet analysed), the `cameras` present and the `overlay_cameras` that have a pose
  overlay video available

#### Scenario: Non-finite metrics are made JSON-safe

- **WHEN** `metrics.json` contains NaN or infinity, which happens when a metric derives
  from a keypoint the pose model could not track
- **THEN** those values are replaced with null throughout the response, because the JSON
  encoder rejects them and would otherwise fail the whole request
- **AND** the UI treats a null metric as unavailable

#### Scenario: Unknown session

- **WHEN** detail is requested for a session that does not exist
- **THEN** the request fails as not found

### Requirement: Session Id Safety

The system SHALL treat a session id as a bare directory name.

#### Scenario: Traversal attempt is rejected

- **WHEN** a session id contains path separators or otherwise does not equal its own
  basename
- **THEN** the lookup fails as not found and no path outside the sessions root is read

#### Scenario: Camera name is validated the same way

- **WHEN** a video is requested for a camera name that is not a bare filename
- **THEN** the request fails as not found

### Requirement: Video Playback

The system SHALL serve each session's clips, including the pose overlay variants.

#### Scenario: Raw clip

- **WHEN** a session's video is requested for a camera without the overlay flag
- **THEN** the session's `<camera>.mp4` is served as `video/mp4`

#### Scenario: Overlay clip

- **WHEN** the overlay flag is set
- **THEN** `pose2sim/pose/<camera>_pose.mp4` is served instead

#### Scenario: Missing clip

- **WHEN** the requested clip does not exist
- **THEN** the request fails as not found, distinguishing a missing overlay from a
  missing raw clip

#### Scenario: Replaced clips must not be served stale

- **WHEN** any clip is served
- **THEN** it is sent with a revalidate-before-reuse cache directive, because clips are
  replaced in place by H.264 migration and overlay rewrites and the browser media cache
  would otherwise keep serving an undecodable copy

### Requirement: 3D Landmark Delivery

The system SHALL expose a session's reconstructed 3D landmarks as JSON for the skeleton
player.

#### Scenario: Landmark payload

- **WHEN** landmarks are requested
- **THEN** the response carries the `source` file name, `marker_names`, `fps`, `times`
  and `frames` of per-marker 3D coordinates

#### Scenario: Untracked coordinates become null

- **WHEN** a coordinate is NaN
- **THEN** it is emitted as null, because NaN is not valid JSON

#### Scenario: Session without 3D data

- **WHEN** landmarks are requested for a session with no `.trc` output
- **THEN** the request fails as not found

### Requirement: Processing Orchestration

The system SHALL run the pose → 3D → metrics pipeline per session in the background and
report its status.

#### Scenario: Full pipeline order

- **WHEN** a session is processed
- **THEN** 2D pose estimation, 3D reconstruction and metric analysis run in that order
  for that session

#### Scenario: Automatic processing after capture

- **WHEN** `processing.auto_process` is enabled
- **THEN** every completed capture is queued for processing automatically, with no
  operator action

#### Scenario: Manual processing

- **WHEN** processing is requested for an existing session
- **THEN** it starts and the current status is returned
- **AND** requesting it again while that session is already running does not start a
  second run

#### Scenario: Processing is serialised

- **WHEN** captures arrive back to back
- **THEN** sessions are processed one at a time, because pose estimation is CPU-heavy
  and would otherwise thrash a machine that is also buffering cameras
- **AND** capture keeps working while processing runs

#### Scenario: Status values

- **WHEN** a session's processing status is polled
- **THEN** it reads `idle` before any run, `running` during one, `done` on success, or
  an `error: <message>` string on failure

#### Scenario: Optional overlay finalisation cannot fail a good analysis

- **WHEN** metrics have been computed and the deferred overlay video transcode then
  fails
- **THEN** the session's status stays `done` and the failure is only logged
