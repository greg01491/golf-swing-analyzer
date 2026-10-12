# swing-analysis Specification

## Purpose

Turn a reconstructed 3D landmark sequence into coaching output: swing phases, the ten
P-System checkpoints, measured swing metrics compared against club-aware reference
ranges, plain-English tips for whatever is out of range, and an honest assessment of
whether the reconstruction was good enough to trust. Implemented by
`golf_sim.analysis.*`.

## Requirements

### Requirement: Handedness- And Orientation-Neutral Frame Of Reference

The system SHALL derive its own vertical axis and report angles as magnitudes, so
results do not depend on how the rig happens to be calibrated.

#### Scenario: Vertical axis is detected per clip

- **WHEN** any analysis needs "up"
- **THEN** the axis with the largest head-to-ankle separation is used as vertical, with
  its sign resolved from that separation

#### Scenario: Turn angles are measured relative to address

- **WHEN** a turn angle series is computed for a marker pair
- **THEN** each frame's horizontal orientation is expressed relative to the same pair's
  orientation at the address frame
- **AND** the result is wrapped into the range -180° to 180°

#### Scenario: Lead side follows configured handedness

- **WHEN** analysis needs the lead arm
- **THEN** `analysis.golfer_handedness` selects the left shoulder and wrist for a
  right-handed golfer and the right ones for a left-handed golfer, because body pose
  alone cannot distinguish the two

### Requirement: Swing Phase Detection

The system SHALL locate the address, top-of-backswing and impact frames from the hand
trajectory.

#### Scenario: Address is the last quiet frame

- **WHEN** phases are detected
- **THEN** the hand speed series is compared against 10% of its own peak speed
- **AND** address is the frame just before hand speed first exceeds that fraction

#### Scenario: Impact is anchored on the audio trigger

- **WHEN** the session metadata carries `pre_capture_delay_s`
- **THEN** the impact frame is searched only within ±0.25 s of that offset into the clip
  and taken as the lowest hand position in that window
- **AND** this anchoring is used because hands are low at both address and impact, so a
  global lowest-hands search cannot tell them apart

#### Scenario: Impact falls back to geometry

- **WHEN** no impact hint is available, for example a manually assembled clip
- **THEN** impact is the lowest hand position after address

#### Scenario: Top is the highest hands before impact

- **WHEN** impact is known
- **THEN** the top of the backswing is the highest hand position strictly before impact,
  which prevents the follow-through finish from being mistaken for the top

#### Scenario: Single-frame triangulation spikes are suppressed

- **WHEN** hand height is evaluated
- **THEN** a NaN-tolerant rolling median over a 5-frame window is applied first, so one
  badly triangulated frame cannot become a false highest or lowest position

#### Scenario: Non-swings are rejected

- **WHEN** the clip has fewer than 5 frames, the hands never move, or impact is not
  clearly after address
- **THEN** phase detection raises an error rather than returning meaningless frames

### Requirement: P-System Checkpoints

The system SHALL detect the ten P-System checkpoints P1 through P10 from body pose
alone, using documented geometric proxies for the club-based textbook definitions.

#### Scenario: Checkpoints and labels

- **WHEN** P-positions are detected
- **THEN** exactly ten checkpoints are returned, named P1–P10 and labelled Address,
  Takeaway, Halfway Back, Top of Backswing, Early Downswing, Pre-Impact, Impact,
  Release, Follow-Through and Finish
- **AND** each carries its frame index and time in seconds

#### Scenario: Phase-derived checkpoints

- **WHEN** checkpoints are derived
- **THEN** P1, P4 and P7 reuse the detected address, top and impact frames

#### Scenario: Shaft-parallel proxy

- **WHEN** P2, P6 and P8 are located
- **THEN** the frame where the hand midpoint crosses the golfer's own address hip height
  is used, as the proxy for "club shaft parallel to the ground", because club tracking
  is out of scope

#### Scenario: Lead-arm-parallel proxy

- **WHEN** P3, P5 and P9 are located
- **THEN** the frame where the lead shoulder-to-wrist vector crosses horizontal (0°
  elevation) is used, as the proxy for "lead arm parallel to the ground"

#### Scenario: Finish checkpoint

- **WHEN** P10 is located
- **THEN** it is the peak hand height after impact

#### Scenario: Checkpoints never go backwards

- **WHEN** windowed searches return frames that are out of order or collapsed onto one
  frame
- **THEN** each checkpoint is forced to be at least one frame after the previous one,
  capped at the final frame, so no two checkpoints share a frame

#### Scenario: Crossing search degrades gracefully

- **WHEN** a proxy series never actually crosses its target value within the search
  window
- **THEN** the frame closest to that value is used, because checkpoints are best-effort
  rather than a hard gate

### Requirement: Swing Metrics

The system SHALL compute a fixed set of swing metrics with explicit units from the 3D
landmark sequence.

#### Scenario: Metric set

- **WHEN** metrics are computed
- **THEN** exactly these are produced: `shoulder_turn_deg`, `hip_turn_deg`,
  `x_factor_deg`, `spine_tilt_deg`, `tempo_ratio`, `hip_sway_top_pct`,
  `hip_sway_impact_pct`, `hip_rotation_impact_deg`, `backswing_time_s`,
  `downswing_time_s`, `shoulder_tilt_impact_deg`, `spine_angle_change_deg`,
  `head_movement_cm`, `early_extension_cm`, `reverse_spine_deg`, `knee_flex_deg`,
  `lead_arm_deg`, `hand_speed_impact_ms` and `swing_plane_deg`
- **AND** each metric carries its explicit unit
- **AND** `swing_plane_deg` is identified as a body-pose hand-path proxy rather than a
  measurement of the club shaft

#### Scenario: Turn metrics are peak backswing values

- **WHEN** shoulder turn, hip turn and X-factor are computed
- **THEN** each is the maximum absolute value over the frames from address to top
  inclusive
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
- **THEN** the hip centre's displacement from address is projected onto the ankle-to-ankle
  stance line at address, and reported at the top and at impact as a percentage of
  stance width
- **AND** magnitudes are reported, leaving direction interpretation to the tips layer

### Requirement: Club-Aware Reference Ranges

The system SHALL compare each metric against configurable reference ranges that account
for the club used, and the shipped configuration SHALL provide an applicable range for
every finite displayed metric.

#### Scenario: Default range coverage

- **WHEN** the shipped configuration is used and a computed metric has a finite value
- **THEN** the metric resolves to a reference range and an in-range verdict
- **AND** `backswing_time_s` and `downswing_time_s` use shared timing ranges
- **AND** `hand_speed_impact_ms` and the body-pose-derived `swing_plane_deg` may use
  club-profile overrides

#### Scenario: Club profile overrides shared ranges

- **WHEN** a session records a club that maps to a club profile
- **THEN** the profile's ranges for the club-dependent metrics are used in place of the
  shared ranges
- **AND** metrics without a profile entry keep the shared reference range

#### Scenario: Metric inside its range

- **WHEN** a metric's value lies between its range minimum and maximum inclusive
- **THEN** it is reported as in range along with that range

#### Scenario: Metric with no configured range

- **WHEN** a custom configuration has no applicable reference range for a metric
- **THEN** the metric is still computed and reported, with its in-range verdict and
  range left null

#### Scenario: Non-finite metric

- **WHEN** a metric evaluates to NaN or infinity because a required keypoint was never
  tracked
- **THEN** it is reported without an in-range verdict rather than being flagged

### Requirement: Coaching Tips

The system SHALL turn out-of-range metrics into ranked, plain-English tips and SHALL
provide direction-specific advice for each newly ranged timing, hand-speed, and
swing-plane metric.

#### Scenario: Only out-of-range metrics produce tips

- **WHEN** tips are generated
- **THEN** a metric that is in range, unranged or unmeasurable produces no tip

#### Scenario: Direction-specific advice

- **WHEN** a metric falls below its range minimum
- **THEN** the "too low" advice for that metric is used, and the "too high" advice is
  used when it exceeds the maximum
- **AND** advice for `swing_plane_deg` states that the value is a body-pose hand-path
  proxy
- **AND** advice for `hand_speed_impact_ms` does not imply that more speed is inherently
  a fault
- **AND** a metric with no advice text for that direction, such as low hip sway,
  produces no tip

#### Scenario: Newly ranged metric is outside its bounds

- **WHEN** `backswing_time_s`, `downswing_time_s`, `hand_speed_impact_ms`, or
  `swing_plane_deg` is below or above its applicable range
- **THEN** that metric contributes direction-appropriate advice to the ranked tip
  candidates

#### Scenario: Ranking by normalised severity

- **WHEN** several metrics are out of range
- **THEN** severity is each metric's deviation from its range divided by the range
  width, so deviations on different scales are comparable
- **AND** tips are returned most severe first, capped at 3

#### Scenario: Tip payload

- **WHEN** tips are serialised
- **THEN** each carries `metric`, `direction` (`low` or `high`), a rounded `severity`
  and the advice `text`

### Requirement: Tracking Quality Gate

The system SHALL assess reconstruction trustworthiness using motion during the detected
swing, camera-specific wrist visibility when available, and physically plausible
reconstructed scale, and SHALL explain the evidence behind each warning.

#### Scenario: Gap-filled reconstructions are flagged

- **WHEN** address and impact frames are available
- **THEN** the quality verdict uses the fraction of hand-midpoint steps of at least
  1 mm between address and impact
- **AND** it reports that swing-window fraction separately from the whole-clip moving
  fraction
- **AND** stationary frames before address or after impact do not by themselves mark
  the swing unreliable
- **AND** fewer than 60% moving steps within the active swing marks the session
  unreliable with the percentage and interval named in the warning

#### Scenario: Camera-specific wrist visibility is reported

- **WHEN** per-camera 2D wrist confidence is available for the active swing
- **THEN** the quality payload reports each camera's left- and right-wrist confidence
  coverage
- **AND** a wrist tracked above confidence 0.6 in fewer than 80% of active-swing
  frames produces a warning naming the camera, wrist, and coverage
- **AND** the warning recommends improving visibility, framing, or lighting rather
  than recalibration

#### Scenario: Physically impossible reconstructions are flagged

- **WHEN** the reconstructed hand travel range exceeds 4.5 m
- **THEN** a warning states the rig calibration looks wrong and recommends recalibrating
  before trusting results

#### Scenario: Quality payload

- **WHEN** tracking quality is assessed
- **THEN** it reports whole-clip `moving_fraction`, nullable `swing_moving_fraction`,
  `hand_vertical_range_m`, per-camera wrist confidence coverage when available, a
  `reliable` flag that is true only when there are no warnings, and the `warnings` list

#### Scenario: No phase window is available

- **WHEN** address or impact frames are unavailable
- **THEN** the whole-clip moving fraction is used as the fallback motion measure
- **AND** warnings identify that the motion measure covers the whole clip

#### Scenario: Too few frames

- **WHEN** the sequence has fewer than 2 frames
- **THEN** quality is reported as unreliable with a "too few frames to analyse" warning

### Requirement: Session Analysis Output

The system SHALL write one `metrics.json` per session containing everything the review
UI needs.

#### Scenario: Analysis input selection

- **WHEN** a session is analysed
- **THEN** the filtered TRC under `pose2sim/pose-3d/` is read, falling back to the
  unfiltered one
- **AND** analysis fails with guidance to run the pose pipeline first if no TRC exists

#### Scenario: Output payload

- **WHEN** `metrics.json` is written
- **THEN** it contains `source_trc`, `club`, `club_profile`, `tracking_quality`,
  `phases`, `metrics`, `tips` and `p_positions`
- **AND** tracking quality is placed before the results so the UI can caveat everything
  below it

#### Scenario: Ideal pose overlay per checkpoint

- **WHEN** P-positions are serialised
- **THEN** each carries `name`, `label`, `frame_index`, `time_s` and an `ideal_frame`
  map of marker names to 3D coordinates, so the UI can render a reference pose beside
  the golfer's actual pose

#### Scenario: Corrupt metadata does not abort analysis

- **WHEN** the session's `metadata.json` is missing or unreadable
- **THEN** analysis proceeds without an impact anchor and without a club, falling back
  to geometric phase detection and shared reference ranges
