## ADDED Requirements

### Requirement: Tracking Quality Causes And Guidance

The system SHALL show the measured cause of low tracking quality and guidance appropriate to that cause, rather than treating every warning as evidence of bad calibration.

#### Scenario: Weak camera keypoint visibility

- **WHEN** tracking quality reports low wrist visibility for a camera
- **THEN** the session warning identifies the camera, wrist, and measured coverage
- **AND** it recommends improving that wrist's visibility, camera framing, or lighting
- **AND** it does not recommend recalibration solely because of low keypoint visibility

#### Scenario: Low motion during the active swing

- **WHEN** tracking quality reports insufficient hand motion between address and impact
- **THEN** the session warning names the active-swing motion coverage and states that positions and metrics may be unreliable
- **AND** stationary setup or follow-through footage is not described as missing swing tracking

#### Scenario: Recalibration guidance requires scale evidence

- **WHEN** reconstructed hand travel exceeds the physically plausible range
- **THEN** the session warning identifies the impossible scale and recommends recalibration
- **AND** other tracking warnings do not independently claim that calibration is wrong