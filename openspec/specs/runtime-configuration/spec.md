# runtime-configuration Specification

## Purpose

Keep every tunable parameter of the analyzer in a single user-editable
`config/config.yaml`, validated on load and on save, and editable from the desktop app
without losing the comments that document each parameter. Implemented by
`golf_sim.config` and the config endpoints in `golf_sim.api.server`.

## Requirements

### Requirement: Single Source Of Tunable Parameters

The system SHALL read all tunable parameters from the configuration file rather than
hardcoding them.

#### Scenario: Configuration sections

- **WHEN** configuration is loaded
- **THEN** it provides the `audio_trigger`, `cameras`, `pose`, `calibration`, `metrics`,
  `analysis`, `processing`, `storage`, `api` and `system_requirements` sections

#### Scenario: Validation on load

- **WHEN** the configuration file is loaded
- **THEN** it is validated against the typed configuration model before use, so a
  malformed value fails at startup rather than mid-capture

#### Scenario: Relative storage paths resolve against the repository root

- **WHEN** `storage.data_dir` or `calibration.dir` is a relative path
- **THEN** it is resolved against the repository root, so the app behaves the same
  regardless of the working directory it was started from

### Requirement: Configuration Retrieval

The system SHALL expose the current configuration to the desktop app.

#### Scenario: Reading configuration

- **WHEN** the configuration is requested
- **THEN** the parsed contents of the active configuration file are returned

### Requirement: Configuration Update

The system SHALL validate, persist and hot-apply configuration edits made from the app.

#### Scenario: Invalid edit is rejected before it is written

- **WHEN** a configuration update fails model validation
- **THEN** the request fails as unprocessable with the validation error and the file on
  disk is left unchanged, so a bad edit cannot brick the app

#### Scenario: Comments survive a UI edit

- **WHEN** a valid configuration update is saved
- **THEN** the new values are merged into the existing YAML document in round-trip mode
- **AND** the file's existing comments, which document each parameter including hardware
  findings, are preserved

#### Scenario: Live runtime picks up the change

- **WHEN** a valid configuration update is saved
- **THEN** the live capture runtime's configuration is replaced with the validated one
- **AND** the response tells the operator to disarm and re-arm capture to apply it,
  which works because disarming fully tears the capture service down

### Requirement: Club Catalogue

The system SHALL expose the selectable clubs so the app never hardcodes them.

#### Scenario: Listing clubs

- **WHEN** the club list is requested
- **THEN** every supported club is returned with its `id` and a human-readable `label`

#### Scenario: Club maps to a metric profile

- **WHEN** a club is recorded on a session
- **THEN** the configured club-to-profile mapping determines which reference-range
  profile the analysis uses for that swing

### Requirement: Local-Only API Surface

The system SHALL serve the API for a locally installed desktop app only.

#### Scenario: Loopback binding

- **WHEN** the API server starts
- **THEN** it binds the configured `api.host` and `api.port`, which default to the
  loopback interface

#### Scenario: Cross-origin access for the packaged renderer

- **WHEN** the packaged Electron renderer, which runs from a `file://` origin, calls the
  API
- **THEN** cross-origin requests are permitted, which is acceptable because the server is
  loopback-bound and holds no secrets beyond what is already on the machine
