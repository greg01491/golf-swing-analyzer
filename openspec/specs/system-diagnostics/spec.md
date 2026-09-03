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

The system SHALL open each configured camera and measure what it actually delivers,
not just what was requested.

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

- **WHEN** measured resolution or frame rate falls below `min_camera_width`,
  `min_camera_height` or `min_camera_fps`
- **THEN** `meets_minimum` is false and a warning names each shortfall, because a camera
  that cannot sustain those settings blurs or drops the impact frame

#### Scenario: Stalled camera cannot hang the check

- **WHEN** a camera does not respond within the probe timeout
- **THEN** the probe is abandoned and the result carries an error saying the camera may
  be stalled, rather than blocking indefinitely on a stuck USB driver

#### Scenario: Camera check requires exclusive access

- **WHEN** the camera check is requested while capture is running
- **THEN** the request is refused as a conflict, telling the operator to disarm capture
  first because the cameras are in use
