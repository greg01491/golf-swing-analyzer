# system-diagnostics Specification Delta

## MODIFIED Requirements

### Requirement: Camera Readiness Check

The system SHALL open each configured camera, apply its configured capture controls, and report what the device actually delivers rather than only what was requested.

#### Scenario: Camera controls are applied and reported

- **WHEN** a configured camera is opened for capture or readiness checking
- **THEN** the system applies the configured exposure mode/value, gain, autofocus mode, and focus value when the device exposes those controls
- **AND** the result reports requested and read-back control values, including whether a control was unsupported or rejected
- **AND** omitted control settings preserve the existing driver behavior

#### Scenario: Reported fields per camera

- **WHEN** the camera check runs
- **THEN** each configured camera reports `role`, `name`, `opened`, the
	`requested_width`, `requested_height` and `requested_fps`, the `actual_width`,
	`actual_height` and `measured_fps`, `meets_minimum`, `warnings` and `error`

#### Scenario: Frame rate is measured, not trusted

- **WHEN** a camera opens successfully
- **THEN** frames are discarded during a warm-up period before timing begins, because
	auto-exposure and white-balance settling otherwise masquerades as a slow camera
- **AND** the frame rate is then measured empirically over a fixed number of sampled
	frames

#### Scenario: Camera below requirements

- **WHEN** measured resolution or frame rate falls below configured minimums
- **THEN** `meets_minimum` is false and a warning names each shortfall, because a
	camera that cannot sustain the configured capture may blur or drop the impact frame

#### Scenario: Camera quality warning

- **WHEN** a camera produces frames successfully
- **THEN** the readiness result may include a quality warning based on measurable sharpness, exposure, or timing at the configured resolution and frame rate
- **AND** a quality warning identifies the camera role and the condition that may degrade fast-swing analysis
- **AND** a quality warning does not mark a camera unavailable when it remains usable

#### Scenario: Capture metadata reflects delivered timing

- **WHEN** a session is saved
- **THEN** its camera metadata records the requested settings and the measured capture timing or delivered frame count needed to interpret the clip
- **AND** downstream processing does not silently treat duplicated frames as genuine additional motion samples

#### Scenario: Stalled camera cannot hang the check

- **WHEN** a camera does not respond within the probe timeout
- **THEN** the probe is abandoned and the result carries an error saying the camera may
	be stalled, rather than blocking indefinitely on a stuck USB driver

#### Scenario: One camera fails while another is available

- **WHEN** one camera cannot be opened or stalls during probing
- **THEN** that camera receives an error result
- **AND** other configured cameras are still probed and reported
- **AND** no worker synchronization failure leaves the readiness request hanging

#### Scenario: Camera check requires exclusive access

- **WHEN** the camera check is requested while capture is running
- **THEN** the request is refused as a conflict, telling the operator to disarm capture
	first because the cameras are in use
