## ADDED Requirements

### Requirement: P-Position Proxy Availability

The system SHALL distinguish detected P-position checkpoints from estimates whose body-pose proxy target was not observed.

#### Scenario: Proxy checkpoint is unavailable

- **WHEN** a P-position is marked unavailable because its proxy target was not crossed
- **THEN** its entry remains visible with its checkpoint name and label
- **AND** the entry is visibly marked as not detected and cannot be selected to seek the video
- **AND** other available checkpoints remain selectable

#### Scenario: Proxy checkpoint was detected

- **WHEN** a P-position proxy target was observed and session tracking quality permits checkpoint review
- **THEN** the checkpoint remains selectable and seeks video to its detected frame

### Requirement: Tracking Quality Causes And Guidance

The system SHALL show the measured cause of low tracking quality and guidance appropriate to that cause, rather than treating every warning as evidence of bad calibration.

#### Scenario: Weak camera keypoint visibility

- **WHEN** tracking quality reports low wrist visibility for a camera
- **THEN** the session warning identifies the camera, wrist, and measured coverage
- **AND** it recommends improving that wrist's visibility, camera framing, or lighting
- **AND** it does not recommend recalibration solely because of low keypoint visibility
- **AND** confidence advisories that do not make the reconstruction unreliable are displayed without disabling P-position navigation

#### Scenario: Low motion during the active swing

- **WHEN** tracking quality reports insufficient hand motion between address and impact
- **THEN** the session warning names the active-swing motion coverage and states that positions and metrics may be unreliable
- **AND** stationary setup or follow-through footage is not described as missing swing tracking

#### Scenario: Recalibration guidance requires scale evidence

- **WHEN** reconstructed hand travel exceeds the physically plausible range
- **THEN** the session warning identifies the impossible scale and recommends recalibration
- **AND** other tracking warnings do not independently claim that calibration is wrong