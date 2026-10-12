## ADDED Requirements

### Requirement: P-Position Reliability Gate

The system SHALL not let the golfer seek to estimated P-System checkpoints when tracking quality marks the reconstruction unreliable.

#### Scenario: Checkpoints are unreliable

- **WHEN** session tracking quality is marked unreliable
- **THEN** the P-position panel explains that checkpoint frames may be inaccurate
- **AND** checkpoint navigation controls are disabled
- **AND** video playback remains available for manual review

#### Scenario: Checkpoints are eligible for review

- **WHEN** session tracking quality is reliable or no quality verdict is available
- **THEN** checkpoint navigation remains available as before

### Requirement: Club Selection While Capture Is Armed

The system SHALL allow the golfer to change the selected club while capture is armed and SHALL make clear which club is recorded for each capture.

#### Scenario: Club changes apply to the next capture

- **WHEN** the golfer selects a different club while capture is armed
- **THEN** the selector remains enabled and the selected club is updated
- **AND** the next triggered session records the newly selected club
- **AND** sessions already captured retain the club recorded when their trigger was received
- **AND** the UI explains that club selection is saved per capture and a change applies to the next swing

### Requirement: Complete Metric Target Presentation

The system SHALL present every finite metric with its applicable target range and SHALL describe the absence of coaching tips without overstating the result.

#### Scenario: Session metric has an applicable range

- **WHEN** a processed session reports a finite metric with an applicable reference range
- **THEN** session review shows its value, unit, range, and in-range or out-of-range state
- **AND** the metric is visually distinguished when it is outside the range

#### Scenario: Stats metric has an applicable range

- **WHEN** a finite metric is plotted in stats over time
- **THEN** its chart shows the applicable target range as a labelled shaded band
- **AND** each point reflects that session's in-range or out-of-range verdict

#### Scenario: Metric is unavailable or explicitly unranged

- **WHEN** a metric is unmeasurable or a custom configuration has no applicable range
- **THEN** the UI identifies the missing value or target state instead of presenting it as in range

#### Scenario: No coaching tips are generated

- **WHEN** a processed swing has no generated coaching tips
- **THEN** visual and spoken summaries say that there are no actionable tips
- **AND** they claim that everything measured is in range only when every finite ranged metric is actually in range

#### Scenario: Newly ranged metric is outside its bounds

- **WHEN** `backswing_time_s`, `downswing_time_s`, `hand_speed_impact_ms`, or `swing_plane_deg` is outside its applicable range and its advice is selected within the top-three limit
- **THEN** the corresponding coaching tip is shown and is eligible to be spoken