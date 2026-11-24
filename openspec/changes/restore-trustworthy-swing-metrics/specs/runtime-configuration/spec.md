## ADDED Requirements

### Requirement: Metric Range Definition Compatibility

The system SHALL identify whether saved metric reference ranges are compatible with the active metric definitions without silently changing user-authored values.

#### Scenario: Existing configuration omits the metric definition version
- **WHEN** a saved user configuration has reference ranges but no metric range-definition version
- **THEN** the configuration remains loadable and its ranges are identified as legacy or unverified
- **AND** those ranges are not silently marked compatible with current metric definitions
- **AND** the operator is given a clear path to review and explicitly migrate or replace them

#### Scenario: Configuration contains a current metric definition version
- **WHEN** a configuration declares a version supported by the active metric definitions
- **THEN** only ranges compatible with that version are applied to verdicts and coaching
- **AND** custom values are preserved through configuration load and save

#### Scenario: Configuration version is unknown or unsupported
- **WHEN** a saved configuration declares an unsupported metric definition version
- **THEN** it remains readable for recovery, affected verdicts and coaching are withheld, and the incompatible version is reported
- **AND** unrelated capture, video review and P-position functions remain available