# desktop-review-ui Specification Delta

## MODIFIED Requirements

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
