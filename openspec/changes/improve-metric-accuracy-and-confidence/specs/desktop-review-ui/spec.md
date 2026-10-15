## MODIFIED Requirements

### Requirement: Complete Metric Target Presentation

The system SHALL present measurement confidence alongside values and applicable targets,
and SHALL not equate unavailable coaching with a successful swing.

#### Scenario: Session metric has an applicable range

- **WHEN** a processed session reports a valid finite metric with a compatible target range
- **THEN** review shows its value, unit, range, and in-range or out-of-range state
- **AND** an out-of-range valid measurement is visually distinguished

#### Scenario: Stats metric has an applicable range

- **WHEN** valid definition-compatible measurements are plotted over time
- **THEN** each point reflects its session's compatible target and verdict
- **AND** differing targets are represented per session or separate series rather than as one misleading universal band
- **AND** incompatible definitions are not joined into one trend

#### Scenario: Metric is unavailable or explicitly unranged

- **WHEN** a metric is unavailable or has no compatible configured target
- **THEN** the UI distinguishes unavailable measurement from absent target
- **AND** unavailable measurements show a reason rather than a numeric zero or pass/fail styling

#### Scenario: No coaching tips are generated

- **WHEN** a processed swing has no generated coaching tips
- **THEN** visual and spoken summaries do not infer that the swing was good
- **AND** an all-in-range claim requires all 19 expected measurements to be valid, ranged, definition-compatible, and in range
- **AND** otherwise the summary distinguishes incomplete assessment from valid measurements without actionable tips

#### Scenario: Newly ranged metric is outside its bounds

- **WHEN** valid timing, hand-speed, or hand-path inclination is out of range and selected within the top-three tip limit
- **THEN** the tip is displayed and eligible for speech
- **AND** estimated, unavailable, and legacy-unverified measurements are not coaching candidates

### Requirement: Spoken Feedback

The system SHALL speak definition-accurate feedback without presenting uncertain or
legacy-unverified measurements as validated coaching.

#### Scenario: Announcement when results are ready

- **WHEN** a new capture finishes processing and speech is enabled
- **THEN** the session is polled until metrics appear and confidence-aware feedback is spoken

#### Scenario: Focused metric takes priority

- **WHEN** the golfer has selected a focused metric
- **THEN** a valid metric supplies its eligible tip or value against its compatible range
- **AND** an estimated or unavailable metric supplies its uncertainty or unavailability reason instead of a pass/fail assessment
- **AND** a legacy-unverified focused result is identified as needing reanalysis, not read as current validated coaching

#### Scenario: Default feedback

- **WHEN** no metric is focused
- **THEN** the most severe eligible tip is spoken when one exists
- **AND** an all-in-range message is used only when all 19 expected measurements are valid, ranged, definition-compatible, and in range
- **AND** otherwise the summary describes incomplete assessment or no actionable tips without praising unverified measurements

#### Scenario: Voice can be turned off

- **WHEN** voice feedback is disabled
- **THEN** ongoing speech is cancelled, further announcements stop, and the preference persists across restarts

## ADDED Requirements

### Requirement: Metric Confidence And Definition Disclosure

The system SHALL distinguish validated measurements, estimates, unavailable results, and
legacy-unverified output consistently in review and metric history.

#### Scenario: Estimated measurement

- **WHEN** a metric is estimated
- **THEN** review identifies the value as an estimate and exposes its reason
- **AND** it has no green/red target verdict and is excluded from validated trend summaries

#### Scenario: Metric description matches its calculation

- **WHEN** metric help or a label describes a measurement
- **THEN** it identifies the actual geometry, sign convention, and sampling interval
- **AND** turns and X-factor are described as peak horizontal backswing measurements, not necessarily top-frame values or rotation around the spine
- **AND** head movement is maximum address-to-impact excursion, knee angle uses 180 degrees as straight, hand speed is a peak near impact, and swing plane is an endpoint hand-path proxy
- **AND** a proxy is not described as direct club or biomechanical ground truth

#### Scenario: Landmark-specific failure

- **WHEN** shoulder, hip, head, or reference evidence is insufficient
- **THEN** review names affected measurements and the cause
- **AND** a general wrist-reliability indicator cannot override per-metric status
- **AND** video remains available for manual review
- **AND** existing P-position reliability controls continue to follow the session verdict

#### Scenario: Historical measurement definitions differ

- **WHEN** history includes incompatible definitions or missing confidence metadata
- **THEN** the affected results are segregated or explicitly excluded from comparable trends and summaries
- **AND** legacy values remain inspectable as unverified without current pass/fail styling or coaching
- **AND** the UI identifies explicit reanalysis as the way to obtain current results when source data exists
- **AND** merely opening a session or chart never initiates reanalysis or modifies saved results