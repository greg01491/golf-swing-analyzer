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

### Requirement: Check for Updates

The system SHALL let the golfer check for and install a newer packaged build from the
desktop app itself.

#### Scenario: Manual check

- **WHEN** the golfer selects "Check for Updates" from the File menu
- **THEN** the app queries GitHub Releases for this repository and reports whether a
  newer version than the running one is available

#### Scenario: Already up to date

- **WHEN** no newer release is available
- **THEN** the app tells the golfer they already have the latest version

#### Scenario: Downloading an update

- **WHEN** a newer release is found
- **THEN** the app downloads and verifies the new installer in the background while
  the golfer keeps using the app
- **AND** the taskbar icon shows download progress so the golfer can tell a download is
  happening

#### Scenario: Prompt to install

- **WHEN** the update finishes downloading and verifying
- **THEN** the golfer is asked whether to restart now to install it or install it later
  on next launch

#### Scenario: Update check failure

- **WHEN** the update check or download fails (e.g. no network)
- **THEN** the golfer is told the check failed rather than the app silently doing
  nothing or crashing

#### Scenario: No update checking outside the packaged app

- **WHEN** the app is running under the development launcher (not an installed,
  packaged build)
- **THEN** no update check is performed

### Requirement: About Dialog

The system SHALL let the golfer see the running app's version number from the File
menu, so they can confirm whether an update actually applied.

#### Scenario: Viewing the version

- **WHEN** the golfer selects "About" from the File menu
- **THEN** the app shows the currently running version number

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

#### Scenario: Club changes apply to the next capture while armed

- **WHEN** the golfer selects a different club while capture is armed
- **THEN** the selector remains enabled and the selected club is updated
- **AND** the next triggered session records the newly selected club
- **AND** sessions already captured retain the club recorded when their trigger was
  received
- **AND** the UI explains that club selection is saved per capture and a change applies
  to the next swing

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

### Requirement: Shared slow-motion control

The system SHALL initialize the shared playback rate from the review view's current session state in multi-camera and Pro view and SHALL allow the golfer to change it repeatedly without crashing or desynchronizing the camera views.

#### Scenario: Session playback rate is restored safely

- **WHEN** a session is opened in multi-camera review mode or Pro view
- **THEN** the UI applies the session's current playback rate once the video elements are ready
- **AND** the rate is clamped to the supported range from 0% (paused) through 100% (normal speed)
- **AND** an absent or invalid stored rate falls back to 100%

#### Scenario: Slow-motion rate changes do not crash

- **WHEN** the golfer changes the slow-motion control before, during, or immediately after video loading
- **THEN** every available camera view in multi-camera review mode or Pro view receives the bounded playback rate
- **AND** views that are not yet ready are updated when they become ready
- **AND** missing or disposed video elements are skipped without throwing
- **AND** the playback position and synchronized-view state remain valid

#### Scenario: Repeated rate changes remain synchronized

- **WHEN** the golfer changes the rate multiple times, including pause and normal speed
- **THEN** all ready camera views in multi-camera review mode or Pro view converge on the latest selected rate
- **AND** changing the rate does not recreate the media elements or reset the selected session

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

### Requirement: Tracking Quality Causes And Guidance

The system SHALL show the measured cause of low tracking quality and guidance
appropriate to that cause, rather than treating every warning as evidence of bad
calibration.

#### Scenario: Weak camera keypoint visibility

- **WHEN** tracking quality reports low wrist visibility for a camera
- **THEN** the session warning identifies the camera, wrist, and measured coverage
- **AND** it recommends improving that wrist's visibility, camera framing, or lighting
- **AND** it does not recommend recalibration solely because of low keypoint visibility

#### Scenario: Low motion during the active swing

- **WHEN** tracking quality reports insufficient hand motion between address and impact
- **THEN** the session warning names the active-swing motion coverage and states that
  positions and metrics may be unreliable
- **AND** stationary setup or follow-through footage is not described as missing swing
  tracking

#### Scenario: Recalibration guidance requires scale evidence

- **WHEN** reconstructed hand travel exceeds the physically plausible range
- **THEN** the session warning identifies the impossible scale and recommends
  recalibration
- **AND** other tracking warnings do not independently claim that calibration is wrong

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

### Requirement: P-Position Reliability Gate

The system SHALL not let the golfer seek to estimated P-System checkpoints when tracking
quality marks the reconstruction unreliable.

#### Scenario: Checkpoints are unreliable

- **WHEN** session tracking quality is marked unreliable
- **THEN** the P-position panel explains that checkpoint frames may be inaccurate
- **AND** checkpoint navigation controls are disabled
- **AND** video playback remains available for manual review

#### Scenario: Checkpoints are eligible for review

- **WHEN** session tracking quality is reliable or no quality verdict is available
- **THEN** checkpoint navigation remains available as before

### Requirement: Complete Metric Target Presentation

The system SHALL present every finite metric with its applicable target range and SHALL
describe the absence of coaching tips without overstating the result.

#### Scenario: Session metric has an applicable range

- **WHEN** a processed session reports a finite metric with an applicable reference range
- **THEN** session review shows its value, unit, range, and in-range or out-of-range
  state
- **AND** the metric is visually distinguished when it is outside the range

#### Scenario: Stats metric has an applicable range

- **WHEN** a finite metric is plotted in stats over time
- **THEN** its chart shows the applicable target range as a labelled shaded band
- **AND** each point reflects that session's in-range or out-of-range verdict

#### Scenario: Metric is unavailable or explicitly unranged

- **WHEN** a metric is unmeasurable or a custom configuration has no applicable range
- **THEN** the UI identifies the missing value or target state instead of presenting it
  as in range

#### Scenario: No coaching tips are generated

- **WHEN** a processed swing has no generated coaching tips
- **THEN** visual and spoken summaries say that there are no actionable tips
- **AND** they claim that everything measured is in range only when every finite ranged
  metric is actually in range

#### Scenario: Newly ranged metric is outside its bounds

- **WHEN** `backswing_time_s`, `downswing_time_s`, `hand_speed_impact_ms`, or
  `swing_plane_deg` is outside its applicable range and its advice is selected within
  the top-three limit
- **THEN** the corresponding coaching tip is shown and is eligible to be spoken

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
- **THEN** the most severe tip is spoken when one exists
- **AND** when no tips exist, a "nice swing, everything measured was in range" message
  is spoken only if every finite ranged metric is actually in range
- **AND** otherwise the spoken summary says there are no actionable tips

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
