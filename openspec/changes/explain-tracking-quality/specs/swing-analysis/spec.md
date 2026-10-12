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
- **AND** it reports coverage at the diagnostic confidence threshold of 0.6 and Pose2Sim's triangulation cutoff of 0.3
- **AND** wrist confidence at or above 0.3 in fewer than 80% of active-swing frames produces an unreliable warning naming the camera, wrist, and coverage
- **AND** confidence between 0.3 and 0.6 in fewer than 80% of active-swing frames produces an advisory naming the camera, wrist, and coverage without by itself marking the reconstruction unreliable
- **AND** visibility guidance recommends framing or lighting changes, not recalibration

#### Scenario: Physically impossible reconstructions are flagged

- **WHEN** the reconstructed hand travel range exceeds 4.5 m
- **THEN** a warning states the rig calibration looks wrong and recommends recalibrating before trusting results

#### Scenario: Quality payload

- **WHEN** tracking quality is assessed
- **THEN** it reports whole-clip `moving_fraction`, nullable `swing_moving_fraction`, `hand_vertical_range_m`, per-camera wrist confidence coverage at both thresholds when available, a `reliable` flag that reflects blocking motion/scale/keypoint warnings, and separate `warnings` and `advisories` lists

#### Scenario: No phase window is available

- **WHEN** address or impact frames are unavailable
- **THEN** the whole-clip moving fraction is used as the fallback motion measure
- **AND** warnings identify that the motion measure covers the whole clip

#### Scenario: Too few frames

- **WHEN** the sequence has fewer than 2 frames
- **THEN** quality is reported as unreliable with a "too few frames to analyse" warning