# system-diagnostics Specification

## Purpose

Tell the operator, before they rely on the rig, whether this PC and these cameras can
actually do the job — static hardware specs, current machine load, and empirically
measured camera resolution and frame rate. Implemented by
`golf_sim.diagnostics.system_check` and `camera_check`.

## Requirements

### Requirement: PC Readiness Check

The system SHALL report the machine's hardware and current load against configured
minimum and recommended requirements.

#### Scenario: Reported fields

- **WHEN** the system check runs
- **THEN** it reports `cpu_cores`, `ram_gb`, `free_disk_gb`, `cpu_load_pct`,
  `ram_used_pct`, `meets_minimum`, `meets_recommended` and `warnings`

#### Scenario: Below minimum specs

- **WHEN** CPU cores, RAM or free disk fall below the configured `min_*` requirements
- **THEN** `meets_minimum` is false and a warning names the shortfall

#### Scenario: Between minimum and recommended

- **WHEN** the machine meets the minimums but falls below `recommended_cpu_cores` or
  `recommended_ram_gb`
- **THEN** `meets_minimum` is true, `meets_recommended` is false, and the operator is
  told it will work but may be sluggish

#### Scenario: Live load warnings

- **WHEN** current CPU load exceeds `high_cpu_load_pct` or RAM usage exceeds
  `high_ram_used_pct`
- **THEN** a warning advises closing other applications, separately from the static
  hardware verdict

#### Scenario: Free disk is measured even before first capture

- **WHEN** the configured data directory does not exist yet
- **THEN** free space is measured on its nearest existing ancestor rather than failing

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
