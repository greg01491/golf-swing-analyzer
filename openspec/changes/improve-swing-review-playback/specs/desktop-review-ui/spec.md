## ADDED Requirements

### Requirement: Equal camera review viewports

The system SHALL display Pro Mode camera recordings in equal-width, equal-height viewing areas when side by side. At the default view, each entire recording SHALL remain visible at its original aspect ratio, with padding rather than stretching or cropping. The layout SHALL keep controls usable on narrower windows without horizontal page overflow.

#### Scenario: Mixed portrait and landscape recordings

- **WHEN** a golfer reviews landscape down-the-line and portrait face-on recordings together
- **THEN** both viewing areas have equal rendered width and height
- **AND** both complete recordings are visible at the default view with padding as needed

#### Scenario: Narrow review window

- **WHEN** the window is too narrow for usable side-by-side review
- **THEN** the panels stack and their controls remain available without horizontal page overflow

### Requirement: Unobstructed review transport

The system SHALL place playback controls outside the recording area in single-camera and Pro Mode review. Pro Mode SHALL expose one shared icon-only play/pause button and a seek timeline next to the frame-back and frame-forward controls below the camera panels. Controls SHALL have accessible names, keyboard operation, and visible focus indicators.

#### Scenario: Inspecting the ball

- **WHEN** playback is paused or running
- **THEN** no native play/pause controls, timeline, or transport gradient covers the recording
- **AND** play/pause, seeking, frame stepping, elapsed time, and slow motion are available outside the image

#### Scenario: Shared playback and seeking

- **WHEN** the golfer plays, pauses, or seeks using the shared controls
- **THEN** all available review cameras follow the same playback action and synchronized time
- **AND** frame readouts continue to use each camera's recording frame rate
- **AND** existing looping, slow motion, checkpoint seeking, and 3D playback synchronization remain functional

#### Scenario: Transport is not yet available

- **WHEN** recording metadata is unavailable or duration is not finite and positive
- **THEN** seeking is disabled rather than producing an invalid playback position
- **AND** a playback failure is visibly reported rather than displaying a false playing state

#### Scenario: Single-camera session

- **WHEN** a session has only one available recording or the golfer uses single-camera review
- **THEN** the same external transport controls operate the active recording without requiring another camera

### Requirement: Independent camera zoom and pan

The system SHALL provide separate zoom in, zoom out, zoom percentage, drag-to-pan, and Reset view controls for each review camera. View controls SHALL be outside the recording area. Changing one camera's framing SHALL NOT change another camera's framing or the playback time or rate.

#### Scenario: Independent magnification

- **WHEN** the golfer zooms the down-the-line view
- **THEN** that recording is magnified within its unchanged viewing area
- **AND** the face-on framing and both cameras' playback positions remain unchanged
- **AND** intentional cropping while zoomed is confined to the viewing area

#### Scenario: Positioning the recording

- **WHEN** the golfer drags within a camera viewing area
- **THEN** only that camera's image moves to the requested position within bounded pan limits
- **AND** releasing or cancelling the pointer ends the drag without leaving a stuck interaction

#### Scenario: Keyboard framing

- **WHEN** the golfer focuses a camera's framing area and uses arrow keys
- **THEN** that image pans without also stepping playback frames
- **AND** zoom and Reset view controls remain keyboard accessible

#### Scenario: Reset and session change

- **WHEN** the golfer selects Reset view
- **THEN** only that camera returns to its centered, full-recording default view
- **AND** playback time and rate are unchanged
- **WHEN** the golfer opens a different session
- **THEN** camera framing starts at the default view rather than inheriting the previous swing's transform

#### Scenario: Review mode or overlay changes

- **WHEN** the golfer switches review modes or toggles the skeleton recording overlay within the same session
- **THEN** each camera retains its own framing
- **AND** the controls operate the currently displayed recording

### Requirement: Image-aligned review annotations

The system SHALL keep existing ball and review-keypoint markers and swing-plane reference lines aligned with the recording through fitting, zooming, panning, and viewport resizing. Annotation manipulation SHALL remain distinct from camera panning.

#### Scenario: Annotation alignment

- **WHEN** a visible annotated recording is zoomed, panned, or resized
- **THEN** its annotation anchors stay on the same recorded image locations
- **AND** annotations outside the viewing area are clipped rather than covering adjacent controls

#### Scenario: Dragging a reference-line handle

- **WHEN** the golfer drags a swing-plane line handle in a zoomed or panned view
- **THEN** the intended endpoint moves accurately in image coordinates
- **AND** the camera image does not also pan
- **AND** resetting the view does not change the stored line endpoints
