# desktop-review-ui Specification

## Purpose

The Electron-wrapped React app the golfer actually uses: arm the rig and pick a club,
watch live camera previews, review each swing's videos, 3D skeleton and metrics, hear
spoken feedback between shots, run the calibration wizard and the readiness checks, and
edit settings. Implemented by `frontend/src` and `frontend/electron`.

## Requirements

### Requirement: Desktop Shell

The system SHALL run the review UI as a desktop application.

#### Scenario: Window creation

- **WHEN** the desktop app starts
- **THEN** a single application window is created with context isolation enabled and
  Node integration disabled in the renderer

#### Scenario: Development versus packaged renderer

- **WHEN** the app runs in development
- **THEN** it loads the local Vite dev server, and in a packaged build it loads the
  built renderer bundle from disk

#### Scenario: Backend is a separate process

- **WHEN** the backend API is not reachable
- **THEN** the UI shows a banner telling the operator to start it with
  `python -m golf_sim.api.server`, because the desktop shell does not spawn the backend

### Requirement: Capture Control

The system SHALL let the golfer arm, disarm and manually trigger capture, and choose a
club, from the main screen.

#### Scenario: Arm and disarm

- **WHEN** the golfer toggles arming
- **THEN** the corresponding arm or disarm call is made and the displayed state follows
  the backend's reported `armed` and `running` flags

#### Scenario: Live status polling

- **WHEN** the main screen is open
- **THEN** capture status is polled continuously so the microphone level meter, camera
  health, selected club and last error stay current

#### Scenario: Club selection is required before capture

- **WHEN** no club has been selected
- **THEN** the UI surfaces the backend's "select a club before capturing" error rather
  than silently discarding the swing

#### Scenario: Manual trigger

- **WHEN** the golfer presses the manual capture control
- **THEN** a capture is triggered without an impact sound

#### Scenario: Live camera preview

- **WHEN** a live preview is displayed
- **THEN** it refreshes the camera preview image on a short interval with a cache-busting
  parameter
- **AND** it shows a "no signal — is capture armed?" placeholder when the image cannot
  be loaded

### Requirement: Swing Review

The system SHALL present each captured swing with its videos and analysis results.

#### Scenario: Session list

- **WHEN** the app loads
- **THEN** captured swings are listed newest first and refresh as new captures arrive

#### Scenario: Processing progress

- **WHEN** a session has not finished processing
- **THEN** the UI polls its processing status and reflects running, done or error
- **AND** when automatic processing is disabled, a control is offered to process the
  swing on demand

#### Scenario: Video playback with overlay toggle

- **WHEN** a session is opened
- **THEN** each camera's clip can be played
- **AND** a pose-overlay toggle is offered only for cameras the backend reports as
  having an overlay video

#### Scenario: Multi-camera synchronised playback

- **WHEN** the golfer enables the multi-camera review mode
- **THEN** the camera views are shown together and one video drives the playback
  position of the others
- **AND** the preference persists across app restarts

#### Scenario: Shared slow-motion control

- **WHEN** the golfer adjusts the slow-motion control in multi-camera review mode
- **THEN** every camera view's playback rate changes together, from 0% (paused) to
  100% (normal speed)

### Requirement: Swing Plane Reference Line

The system SHALL let the golfer overlay up to five independent straight reference lines
on each camera view to visually judge the swing's plane (e.g. steep-to-shallow through
the backswing and downswing), independent of any pose or club tracking.

#### Scenario: Adding a reference line

- **WHEN** the golfer adds a reference line to a camera view with fewer than five lines
- **THEN** a new straight line is drawn over that video that the golfer can position by
  dragging its endpoints

#### Scenario: Maximum reference lines

- **WHEN** the camera view already has five reference lines
- **THEN** the add-line control is unavailable and no sixth line is created

#### Scenario: Per-camera independence

- **WHEN** the golfer adds, removes, or positions a reference line on one camera view
- **THEN** it has no effect on the collection of reference lines shown on the other camera
  view, since each view's swing plane looks different from its angle

#### Scenario: Choosing a line color

- **WHEN** the golfer sets a selected reference line's color
- **THEN** that line is redrawn in the selected color, and every line can use a different
  color

#### Scenario: Toggling visibility

- **WHEN** the golfer hides a selected reference line
- **THEN** it is no longer drawn over the video, without discarding its saved position
  and color

#### Scenario: Removing a reference line

- **WHEN** the golfer removes a selected reference line
- **THEN** that line and its handles disappear, while the other lines remain unchanged

#### Scenario: Line position does not track the swing

- **WHEN** the video plays through the swing
- **THEN** the reference line stays fixed in the same screen position, since it is not
  derived from body pose or club tracking

#### Scenario: Persisted per camera

- **WHEN** the golfer reopens the app or a different session
- **THEN** each camera's collection of up to five reference lines (position, color,
  visibility, and selected line) is remembered, the same way the multi-camera review
  preference persists

#### Scenario: Metrics presentation

- **WHEN** a session's metrics are available
- **THEN** each metric is shown with its value, unit and reference range, and is marked
  as in or out of range
- **AND** a metric reported as unavailable is shown as such rather than as a number

#### Scenario: Low-confidence swings are caveated

- **WHEN** the session's tracking quality is not reliable
- **THEN** its warnings are shown alongside the results, so poor reconstructions are not
  presented as fact

### Requirement: 3D Skeleton Playback

The system SHALL render the reconstructed swing as an interactive 3D skeleton.

#### Scenario: Skeleton rendering

- **WHEN** a session with 3D landmarks is opened
- **THEN** the landmark frames are fetched and drawn as a connected skeleton that the
  golfer can orbit and zoom

#### Scenario: Playback follows time

- **WHEN** the review time position changes
- **THEN** the rendered frame is selected from that time and the sequence's frame rate

#### Scenario: Ideal pose overlay

- **WHEN** a checkpoint's ideal frame is available
- **THEN** it is drawn as a semi-transparent reference skeleton beside the golfer's
  actual pose

### Requirement: P-Position Review

The system SHALL let the golfer step through the detected P-System checkpoints.

#### Scenario: Checkpoint navigation

- **WHEN** the checkpoint panel is shown
- **THEN** each detected checkpoint is listed with its name and label
- **AND** selecting one moves the review position to that checkpoint's time

### Requirement: Spoken Feedback

The system SHALL be able to speak a swing's feedback aloud so the golfer does not have
to walk to the screen between shots.

#### Scenario: Announcement when results are ready

- **WHEN** a new capture finishes processing
- **THEN** the session is polled until its metrics appear and the feedback is then
  spoken

#### Scenario: Focused metric takes priority

- **WHEN** the golfer has chosen a metric to focus on
- **THEN** the spoken feedback covers that metric — its tip if one was generated,
  otherwise its value against its range

#### Scenario: Default feedback

- **WHEN** no metric is focused
- **THEN** the most severe tip is spoken, or a "nice swing, everything measured was in
  range" message when there are no tips

#### Scenario: Voice can be turned off

- **WHEN** voice feedback is disabled
- **THEN** any in-progress speech is cancelled and no further announcements are made
- **AND** the preference persists across app restarts

### Requirement: Calibration Wizard

The system SHALL guide the operator through rig calibration step by step.

#### Scenario: Wizard steps

- **WHEN** the calibration wizard runs
- **THEN** it walks through printing and measuring the board, capturing lens shots for
  each camera in turn, and capturing the camera-position shot with the golfer in the
  hitting position

#### Scenario: Measured square size is saved

- **WHEN** the operator enters the measured checkerboard square size
- **THEN** it is saved into the configuration, because printers rescale the board

#### Scenario: Hands-free shot capture

- **WHEN** the operator starts the auto-capture loop for a step
- **THEN** shots are taken on a selectable countdown until the target shot count is
  reached, so the operator can hold the board rather than press a button

#### Scenario: Progress feedback

- **WHEN** shots have been captured
- **THEN** the current shot count against the target is shown, sourced from the backend's
  calibration shot list

#### Scenario: Compute with progress

- **WHEN** the operator enters the measured camera distance and starts the computation
- **THEN** the computation status is polled and its stage, error or result is shown,
  including the calibration file, per-camera lens quality, reprojection error and
  estimated person height

#### Scenario: Starting over

- **WHEN** the operator clears calibration shots
- **THEN** the captured shots are deleted so the next computation is not polluted by
  stale ones

### Requirement: Readiness Screen

The system SHALL surface the PC and camera diagnostics in the app.

#### Scenario: PC specs

- **WHEN** the readiness screen opens
- **THEN** CPU cores, RAM, free disk and current load are shown with an overall verdict
  of meets-recommended, meets-minimum, or below-minimum, plus any warnings

#### Scenario: Camera check on demand

- **WHEN** the operator runs the camera check
- **THEN** each camera's open state, actual resolution, measured frame rate and warnings
  are shown
- **AND** a conflict response is presented as "disarm capture first"

### Requirement: Settings Editing

The system SHALL let the operator edit the tunable settings without leaving the app.

#### Scenario: Editable settings

- **WHEN** the settings screen is open
- **THEN** the trigger threshold, pre-capture delay, capture duration and cooldown, the
  camera buffer margin, the calibration max age, automatic processing, per-camera device
  settings including rotation, and per-metric reference ranges can all be edited

#### Scenario: Saving settings

- **WHEN** the operator saves
- **THEN** the configuration is sent to the backend and the operator is told to disarm
  and re-arm to apply it
- **AND** a rejected edit surfaces the backend's validation error

#### Scenario: Camera orientation is verified visually

- **WHEN** camera rotation is being adjusted
- **THEN** a live preview of that camera is shown alongside the control so the operator
  can confirm the golfer appears upright

### Requirement: Appearance Preference

The system SHALL remember the golfer's display preference.

#### Scenario: Theme toggle persists

- **WHEN** the golfer switches between the dark and light themes
- **THEN** the choice is applied immediately and restored on the next launch
