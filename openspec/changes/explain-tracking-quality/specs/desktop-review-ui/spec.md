## ADDED Requirements

### Requirement: P-Position Proxy Estimates

The system SHALL distinguish detected P-position checkpoints from phase-progress estimates and unavailable checkpoints.

#### Scenario: Proxy target is missed but phase moves

- **WHEN** a proxy target is not crossed but its phase has measurable progress
- **THEN** the entry remains selectable at the phase-progress estimate
- **AND** the UI clearly marks it as estimated rather than detected

#### Scenario: Proxy phase is degenerate

- **WHEN** a proxy target is not crossed and its phase has no meaningful progress
- **THEN** the entry remains visible with its checkpoint name and label
- **AND** the UI marks it unavailable and prevents seeking from that entry
- **AND** other available checkpoints remain selectable

#### Scenario: Estimated checkpoint selection

- **WHEN** an estimated P-position is selected and session tracking quality permits checkpoint review
- **THEN** playback seeks to its estimated frame and the UI retains the estimated label

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