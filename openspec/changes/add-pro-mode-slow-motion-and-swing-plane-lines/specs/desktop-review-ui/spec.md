## MODIFIED Requirements

### Requirement: Multi-camera synchronised playback

The system SHALL let the golfer view all camera angles together with synchronised
playback and a shared slow-motion control.

#### Scenario: Multi-camera synchronised playback

- **WHEN** the golfer enables the multi-camera review mode
- **THEN** the camera views are shown together and one video drives the playback
  position of the others
- **AND** the preference persists across app restarts

#### Scenario: Shared slow-motion control

- **WHEN** the golfer adjusts the slow-motion control in multi-camera review mode
- **THEN** every camera view's playback rate changes together, from 0% (paused) to
  100% (normal speed)

## ADDED Requirements

### Requirement: Swing Plane Reference Line

The system SHALL let the golfer overlay a straight reference line on each camera view
to visually judge the swing's plane (e.g. steep-to-shallow through the backswing and
downswing), independent of any pose or club tracking.

#### Scenario: Adding a reference line

- **WHEN** the golfer adds a reference line to a camera view
- **THEN** a straight line is drawn over that video that the golfer can position by
  dragging its endpoints

#### Scenario: Per-camera independence

- **WHEN** the golfer positions a reference line on one camera view
- **THEN** it has no effect on the reference line (if any) shown on the other camera
  view, since each view's swing plane looks different from its angle

#### Scenario: Choosing a line color

- **WHEN** the golfer sets a reference line's color
- **THEN** the line is redrawn in that color, and different camera views' lines can use
  different colors

#### Scenario: Toggling visibility

- **WHEN** the golfer hides a reference line
- **THEN** it is no longer drawn over the video, without discarding its saved position
  and color

#### Scenario: Line position does not track the swing

- **WHEN** the video plays through the swing
- **THEN** the reference line stays fixed in the same screen position, since it is not
  derived from body pose or club tracking

#### Scenario: Persisted per camera

- **WHEN** the golfer reopens the app or a different session
- **THEN** each camera's most recently set reference line (position, color, visibility)
  is remembered, the same way the multi-camera review preference persists
