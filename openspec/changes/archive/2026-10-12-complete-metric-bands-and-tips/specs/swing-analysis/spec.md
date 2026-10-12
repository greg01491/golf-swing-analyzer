## MODIFIED Requirements

### Requirement: Swing Metrics

The system SHALL compute a fixed set of swing metrics with explicit units from the 3D landmark sequence.

#### Scenario: Metric set

- **WHEN** metrics are computed
- **THEN** exactly these are produced: `shoulder_turn_deg`, `hip_turn_deg`, `x_factor_deg`, `spine_tilt_deg`, `tempo_ratio`, `hip_sway_top_pct`, `hip_sway_impact_pct`, `hip_rotation_impact_deg`, `backswing_time_s`, `downswing_time_s`, `shoulder_tilt_impact_deg`, `spine_angle_change_deg`, `head_movement_cm`, `early_extension_cm`, `reverse_spine_deg`, `knee_flex_deg`, `lead_arm_deg`, `hand_speed_impact_ms`, and `swing_plane_deg`
- **AND** each metric carries its explicit unit
- **AND** `swing_plane_deg` is identified as a body-pose hand-path proxy rather than a measurement of the club shaft

#### Scenario: Turn metrics are peak backswing values

- **WHEN** shoulder turn, hip turn and X-factor are computed
- **THEN** each is the maximum absolute value over the frames from address to top inclusive
- **AND** X-factor is the peak separation between the shoulder and hip turn series

#### Scenario: Spine tilt is measured at address

- **WHEN** spine tilt is computed
- **THEN** it is the angle of the hip-to-neck line from vertical at the address frame

#### Scenario: Tempo is backswing over downswing

- **WHEN** tempo ratio is computed
- **THEN** it is the address-to-top duration divided by the top-to-impact duration
- **AND** it fails as a phase detection error if impact is not after top

#### Scenario: Hip sway is relative to stance width

- **WHEN** hip sway is computed
- **THEN** the hip centre's displacement from address is projected onto the ankle-to-ankle stance line at address, and reported at the top and at impact as a percentage of stance width
- **AND** magnitudes are reported, leaving direction interpretation to the tips layer

### Requirement: Club-Aware Reference Ranges

The system SHALL compare each metric against configurable reference ranges that account for the club used, and the shipped configuration SHALL provide an applicable range for every finite displayed metric.

#### Scenario: Default range coverage

- **WHEN** the shipped configuration is used and a computed metric has a finite value
- **THEN** the metric resolves to a reference range and an in-range verdict
- **AND** `backswing_time_s` and `downswing_time_s` use shared timing ranges
- **AND** `hand_speed_impact_ms` and the body-pose-derived `swing_plane_deg` may use club-profile overrides

#### Scenario: Club profile overrides shared ranges

- **WHEN** a session records a club that maps to a club profile
- **THEN** the profile's ranges for the club-dependent metrics are used in place of the shared ranges
- **AND** metrics without a profile entry keep the shared reference range

#### Scenario: Metric inside its range

- **WHEN** a metric's value lies between its range minimum and maximum inclusive
- **THEN** it is reported as in range along with that range

#### Scenario: Metric with no configured range

- **WHEN** a custom configuration has no applicable reference range for a metric
- **THEN** the metric is still computed and reported, with its in-range verdict and range left null

#### Scenario: Non-finite metric

- **WHEN** a metric evaluates to NaN or infinity because a required keypoint was never tracked
- **THEN** it is reported without an in-range verdict rather than being flagged

### Requirement: Coaching Tips

The system SHALL turn out-of-range metrics into ranked, plain-English tips and SHALL provide direction-specific advice for each newly ranged timing, hand-speed, and swing-plane metric.

#### Scenario: Only out-of-range metrics produce tips

- **WHEN** tips are generated
- **THEN** a metric that is in range, unranged or unmeasurable produces no tip

#### Scenario: Direction-specific advice

- **WHEN** a metric falls below its range minimum
- **THEN** the "too low" advice for that metric is used, and the "too high" advice is used when it exceeds the maximum
- **AND** advice for `swing_plane_deg` states that the value is a body-pose hand-path proxy
- **AND** advice for `hand_speed_impact_ms` does not imply that more speed is inherently a fault
- **AND** a metric with no advice text for a non-actionable direction, such as low hip sway, produces no tip

#### Scenario: Newly ranged metric is outside its bounds

- **WHEN** `backswing_time_s`, `downswing_time_s`, `hand_speed_impact_ms`, or `swing_plane_deg` is below or above its applicable range
- **THEN** that metric contributes direction-appropriate advice to the ranked tip candidates

#### Scenario: Ranking by normalised severity

- **WHEN** several metrics are out of range
- **THEN** severity is each metric's deviation from its range divided by the range width, so deviations on different scales are comparable
- **AND** tips are returned most severe first, capped at 3

#### Scenario: Tip payload

- **WHEN** tips are serialised
- **THEN** each carries `metric`, `direction` (`low` or `high`), a rounded `severity` and the advice `text`