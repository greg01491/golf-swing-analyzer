# swing-capture Specification

## Purpose

Capture a golf swing hands-free. Two USB cameras stream continuously into rolling
buffers while a microphone listens for the impact sound; when impact is detected the
system extracts a fixed window of footage from *before and after* that instant and
saves it as a session on disk. Implemented by `golf_sim.audio.*`, `golf_sim.capture.*`
and `golf_sim.api.runtime.CaptureRuntime`.

## Requirements

### Requirement: Continuous Multi-Camera Buffering

The system SHALL stream every configured camera into its own rolling frame buffer
while capture is running, so footage from before a trigger is still available when
that trigger fires.

#### Scenario: Buffer retains the whole capture window

- **WHEN** `CaptureService` is constructed from config
- **THEN** each camera gets a `RollingBuffer` whose `max_age_s` is
  `audio_trigger.capture_duration_s + cameras.buffer_margin_s`
- **AND** frames older than that relative to the newest buffered frame are evicted

#### Scenario: Each camera runs on its own thread with a declared role

- **WHEN** `CaptureService.start()` is called
- **THEN** one `CameraStream` per entry in `cameras.devices` is started
- **AND** each stream is keyed by its configured `role` (`camera_1` = down-the-line,
  `camera_2` = face-on)

#### Scenario: Camera health is tracked

- **WHEN** a camera stream accumulates consecutive failed reads
- **THEN** its `healthy` flag becomes false and is exposed per role via
  `CaptureRuntime.camera_health`
- **AND** the failing read does not stop the other cameras or the audio listener

#### Scenario: Cameras are selected by device name

- **WHEN** a camera device config declares a `name`
- **THEN** the DirectShow device with that name is opened rather than the `id` index,
  because Windows shuffles camera indices between processes
- **AND** `id` is used only as the fallback when no `name` is set

#### Scenario: Physically rotated cameras are corrected at capture time

- **WHEN** a camera device declares `rotation_deg` of 90, 180 or 270
- **THEN** every captured frame is rotated before buffering, not just the preview,
  because the pose model expects upright people
- **AND** for 90 or 270 the width and height recorded in session metadata are swapped
  so the metadata matches the saved clip

### Requirement: Audio Impact Trigger

The system SHALL detect ball impact from microphone level and start a capture when
the configured threshold is exceeded, subject to a cooldown.

#### Scenario: Level above threshold triggers a capture

- **WHEN** the service is armed and an audio block's level reaches
  `audio_trigger.threshold_db`
- **THEN** `TriggerDetector.check()` returns true and a capture is dispatched with the
  exact monotonic time the impact was detected

#### Scenario: Cooldown suppresses re-triggers

- **WHEN** a trigger fired less than `audio_trigger.trigger_cooldown_s` ago
- **THEN** further level exceedances are ignored and no capture is started

#### Scenario: Level below threshold does nothing

- **WHEN** the measured level is below `audio_trigger.threshold_db`
- **THEN** no capture is started, regardless of cooldown state

#### Scenario: Live microphone level is exposed

- **WHEN** the audio trigger service is running
- **THEN** the most recent level in dBFS is readable as `CaptureRuntime.mic_level_db`
- **AND** any microphone failure is reported as `CaptureRuntime.mic_error` instead of
  crashing the listener

#### Scenario: Threshold can be calibrated from recordings

- **WHEN** the operator runs the audio calibration helper
- **THEN** ambient noise and impact recordings are compared to suggest a
  `threshold_db` value that sits above ambient and below impact

### Requirement: Arm, Disarm And Manual Trigger

The system SHALL let the operator arm the trigger, disarm it, and fire a capture
manually without an impact sound.

#### Scenario: Arming starts the services

- **WHEN** `arm()` is called while capture is not running
- **THEN** the camera streams and the audio trigger service are started and the
  detector begins accepting triggers

#### Scenario: Disarming tears the pipeline down

- **WHEN** `disarm()` is called
- **THEN** both the audio service and the capture service are fully stopped and
  released, so a later `arm()` rebuilds them from the current config and picks up
  edited camera settings

#### Scenario: Manual trigger captures immediately

- **WHEN** `manual_trigger()` is called with a club selected
- **THEN** a capture runs as if impact had been detected
- **AND** the cooldown window is started so an immediately following real impact does
  not double-capture

#### Scenario: Manual trigger without a club is refused

- **WHEN** `manual_trigger()` is called and no club has been selected
- **THEN** the call raises and no session is written

### Requirement: Club Selection Recorded With Each Swing

The system SHALL require a club to be selected before an automatic capture and SHALL
store the selection with the session.

#### Scenario: Automatic trigger without a club is rejected

- **WHEN** an audio trigger fires while `selected_club` is `None`
- **THEN** no session is written
- **AND** `last_error` is set to `"select a club before capturing"`

#### Scenario: Selected club lands in metadata

- **WHEN** a capture completes with club `driver` selected
- **THEN** `metadata.json` for the session contains `"club": "driver"`

### Requirement: Trigger-Anchored Clip Extraction

The system SHALL build each saved clip from a window anchored on the trigger instant,
so impact lands at a known offset into the clip.

#### Scenario: Window spans before and after impact

- **WHEN** a trigger fires at time `T`
- **THEN** the extracted window starts at `T - audio_trigger.pre_capture_delay_s` and
  lasts `audio_trigger.capture_duration_s`
- **AND** impact therefore sits `pre_capture_delay_s` into the saved clip, which
  downstream analysis uses as its impact anchor

#### Scenario: Cameras are resampled onto a shared frame grid

- **WHEN** the raw windows have been extracted from each camera buffer
- **THEN** every camera's frames are resampled onto the same exact fps grid starting
  at the same instant
- **AND** all cameras therefore yield identical, time-aligned frame counts, which 3D
  triangulation requires because it pairs cameras by frame index

#### Scenario: Extraction that never fills the window fails cleanly

- **WHEN** the buffer does not reach the window's end time within the extraction
  timeout
- **THEN** extraction raises a timeout error naming the expected and latest buffered
  timestamps
- **AND** the error is recorded in `last_error` without stopping the trigger listener

### Requirement: Session Persistence

The system SHALL write each capture as a self-contained session directory under
`<data_dir>/sessions/`.

#### Scenario: Session directory layout

- **WHEN** a capture completes
- **THEN** a directory named `<YYYY-MM-DD>_<HH-MM-SS>_<8 hex chars>` is created
- **AND** it contains one `<role>.mp4` per camera plus `metadata.json`

#### Scenario: Metadata contents

- **WHEN** `metadata.json` is written
- **THEN** it contains `session_id`, `created_at` (ISO 8601 with offset),
  `pre_capture_delay_s`, `capture_duration_s`, and a `cameras` map whose entries carry
  `camera_id`, `width`, `height`, `fps`, `frame_count` and `file`

#### Scenario: Clips are transcoded to H.264

- **WHEN** a clip has been written with OpenCV's mp4v encoder
- **THEN** it is re-encoded to H.264 so the Chromium-based player can decode it
- **AND** if the transcode fails the original file is left in place rather than lost

### Requirement: Capture Status Reporting

The system SHALL expose the live state of the capture pipeline for the UI.

#### Scenario: Status snapshot

- **WHEN** capture status is requested
- **THEN** the response reports `running`, `armed`, `mic_level_db`, `mic_error`,
  `camera_health`, `last_session`, `last_error` and `selected_club`

#### Scenario: Session is published only after processing is registered

- **WHEN** a capture completes and an `on_session` processing hook is configured
- **THEN** the hook runs before `last_session_dir` is published
- **AND** the UI therefore cannot observe the new session while its processing status
  still reads idle

### Requirement: Live Camera Preview

The system SHALL expose the most recently buffered frame per camera as a JPEG so the
operator can aim and frame the cameras.

#### Scenario: Preview while running

- **WHEN** a preview is requested for a running camera role
- **THEN** the latest buffered frame is returned as a JPEG that must not be cached

#### Scenario: Preview while not running

- **WHEN** a preview is requested and capture is not running
- **THEN** the request fails with a message telling the operator to arm capture first
