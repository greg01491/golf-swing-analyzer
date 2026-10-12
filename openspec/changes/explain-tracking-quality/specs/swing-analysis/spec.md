## MODIFIED Requirements

### Requirement: Tracking Quality Gate

The system SHALL assess reconstruction trustworthiness using motion during the detected swing, camera-specific wrist visibility when available, and physically plausible reconstructed scale, and SHALL explain the evidence behind each warning.

#### Scenario: Gap-filled reconstructions are flagged

- **WHEN** address and impact frames are available
- **THEN** the quality verdict uses the fraction of hand-midpoint steps of at least 1 mm between address and impact
- **AND** it reports that swing-window fraction separately from the whole-clip moving fraction
- **AND** stationary frames before address or after impact do not by themselves mark the swing unreliable
- **AND** fewer than 60% moving steps within the active swing marks the session unreliable with the percentage and interval named in the warning

#### Scenario: Camera-specific wrist visibility is reported

- **WHEN** per-camera 2D wrist confidence is available for the active swing
- **THEN** the quality payload reports each camera's left- and right-wrist confidence coverage
- **AND** a wrist tracked above confidence 0.6 in fewer than 80% of active-swing frames produces a warning naming the camera, wrist, and coverage
- **AND** the warning recommends improving visibility, framing, or lighting rather than recalibration

#### Scenario: Physically impossible reconstructions are flagged

- **WHEN** the reconstructed hand travel range exceeds 4.5 m
- **THEN** a warning states the rig calibration looks wrong and recommends recalibrating before trusting results

#### Scenario: Quality payload

- **WHEN** tracking quality is assessed
- **THEN** it reports whole-clip `moving_fraction`, nullable `swing_moving_fraction`, `hand_vertical_range_m`, per-camera wrist confidence coverage when available, a `reliable` flag that is true only when there are no warnings, and the `warnings` list

#### Scenario: No phase window is available

- **WHEN** address or impact frames are unavailable
- **THEN** the whole-clip moving fraction is used as the fallback motion measure
- **AND** warnings identify that the motion measure covers the whole clip

#### Scenario: Too few frames

- **WHEN** the sequence has fewer than 2 frames
- **THEN** quality is reported as unreliable with a "too few frames to analyse" warning