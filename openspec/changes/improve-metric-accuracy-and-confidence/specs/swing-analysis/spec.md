## MODIFIED Requirements

### Requirement: Handedness- And Orientation-Neutral Frame Of Reference

The system SHALL use a validated analysis reference frame, preserve direction where the
measurement requires it, and express results independently of calibrated world-axis labels.

#### Scenario: Vertical axis is detected per clip

- **WHEN** analysis needs up or a horizontal plane
- **THEN** it uses a reference supported by calibration metadata or consistent usable body landmarks
- **AND** a marker's presence alone does not establish that it was tracked reliably
- **AND** a frozen, implausibly placed, or conflicting head cannot silently select the reference
- **AND** missing physical ground evidence is disclosed as an estimated reference rather than a validated floor normal

#### Scenario: Reference cannot be established

- **WHEN** usable evidence cannot establish the required reference
- **THEN** dependent measurements are unavailable with a reason, rather than calculated using an arbitrary world axis
- **AND** measurements independent of that reference remain eligible for evaluation

#### Scenario: Turn angles are measured relative to address

- **WHEN** a turn angle series is computed for a marker pair
- **THEN** horizontal rotation is relative to a stable supported address orientation
- **AND** signed rotations wrap into -180 to 180 degrees without introducing separation discontinuities
- **AND** a collapsed horizontal projection is invalid, not a zero-degree turn

#### Scenario: Lead side follows configured handedness

- **WHEN** analysis needs the lead arm or directional target interpretation
- **THEN** configured handedness selects the left lead side for a right-handed golfer and the right lead side for a left-handed golfer
- **AND** target and ball directions require supported geometry; handedness alone does not determine which perpendicular points toward the ball

#### Scenario: Coordinate representation does not change a measurement

- **WHEN** a known swing and its supported reference frame undergo the same rigid coordinate transformation
- **THEN** physical metric values and confidence classifications remain unchanged within declared numerical tolerances
- **AND** mirrored right- and left-handed equivalents retain the same anatomical interpretation when handedness is changed accordingly

### Requirement: Swing Metrics

The system SHALL return the fixed set of 19 metric entries with explicit units,
documented geometry and sampling intervals, and confidence assessed from their dependencies.

#### Scenario: Metric set

- **WHEN** metrics are computed
- **THEN** exactly these entries are produced, including entries that cannot be measured:
  `shoulder_turn_deg`, `hip_turn_deg`, `x_factor_deg`, `spine_tilt_deg`, `tempo_ratio`,
  `hip_sway_top_pct`, `hip_sway_impact_pct`, `hip_rotation_impact_deg`,
  `backswing_time_s`, `downswing_time_s`, `shoulder_tilt_impact_deg`,
  `spine_angle_change_deg`, `head_movement_cm`, `early_extension_cm`,
  `reverse_spine_deg`, `knee_flex_deg`, `lead_arm_deg`, `hand_speed_impact_ms`,
  and `swing_plane_deg`
- **AND** each carries its unit, definition identifier, confidence status, and supporting reason where needed

#### Scenario: Turn metrics are peak backswing values

- **WHEN** shoulder turn and hip turn are computed
- **THEN** each is the peak absolute supported horizontal rotation between address and top inclusive
- **AND** isolated invalid observations do not become the reported peak
- **AND** the result is described as horizontal peak backswing rotation, not rotation around the spine or necessarily the value at the top frame

#### Scenario: X-factor uses circular separation

- **WHEN** X-factor is computed
- **THEN** it is the peak supported absolute circular difference between address-relative shoulder and hip rotations during the backswing
- **AND** only frames where both rotations are supported contribute
- **AND** crossing the angle seam cannot create a separation greater than 180 degrees
- **AND** insufficient common coverage makes X-factor unavailable instead of subtracting unrelated peaks

#### Scenario: Spine tilt is measured at address

- **WHEN** spine tilt is computed
- **THEN** it is forward hip-to-neck bend at address in the supported ball-facing vertical plane
- **AND** it is not the total 3D inclination combining forward and lateral bend

#### Scenario: Posture measurements separate forward bend and side bend

- **WHEN** spine tilt, spine-angle change, or reverse spine are computed
- **THEN** `spine_tilt_deg` is forward hip-to-neck bend at address in the supported ball-facing vertical plane
- **AND** `spine_angle_change_deg` is the absolute change of that forward-bend component from address to impact
- **AND** `reverse_spine_deg` is targetward lateral hip-to-neck bend at the top, with away-from-target bend negative
- **AND** missing required posture or directional evidence affects these entries rather than producing a plausible-looking magnitude

#### Scenario: Tempo is backswing over downswing

- **WHEN** timing metrics are computed
- **THEN** backswing time is address-to-top duration, downswing time is top-to-impact duration, and tempo is their ratio
- **AND** non-increasing phase times cannot produce valid timing metrics
- **AND** a phase detection failure remains an error rather than fabricated phase anchors
- **AND** uncertain anchors propagate to dependent measurements

#### Scenario: Hip sway is relative to stance width

- **WHEN** hip sway is computed
- **THEN** hip-center displacement from address is projected onto the supported address ankle-to-ankle stance line
- **AND** magnitudes at top and impact are reported as percentages of supported stance width
- **AND** missing or degenerate stance width makes these measurements unavailable
- **AND** unsigned sway does not establish targetward or trailward fault direction

#### Scenario: Impact rotation and tilt preserve anatomical direction

- **WHEN** impact hip rotation and shoulder tilt are computed
- **THEN** `hip_rotation_impact_deg` is address-relative horizontal hip rotation, positive open toward the target and negative closed
- **AND** `shoulder_tilt_impact_deg` is shoulder-line inclination to the supported horizontal plane, positive when the trail shoulder is below the lead shoulder and negative for the opposite tilt
- **AND** opposite anatomical directions cannot yield the same signed value

#### Scenario: Head movement measures excursion

- **WHEN** head movement is computed
- **THEN** it is maximum supported 3D displacement from the address head position between address and impact inclusive, in centimeters
- **AND** movement followed by a return is not reported as zero
- **AND** a frozen or substituted marker is not silently treated as a stationary tracked head

#### Scenario: Early extension distinguishes retreat from thrust

- **WHEN** early extension is computed
- **THEN** it is pelvis displacement from address to impact along the supported ball-facing horizontal direction, in centimeters
- **AND** movement toward the ball is positive and movement away is negative
- **AND** a missing ball-facing direction makes this measurement unavailable

#### Scenario: Body angles retain their joint-angle definitions

- **WHEN** knee flex and lead-arm straightness are computed
- **THEN** knee flex is the mean supported included hip-knee-ankle angle at address, where 180 degrees is straight
- **AND** lead-arm straightness is the configured lead shoulder-elbow-wrist included angle at the top
- **AND** missing legs are not silently averaged as though both were measured, and zero-length limbs are invalid

#### Scenario: Hand speed and swing plane are explicit proxies

- **WHEN** hand speed and swing plane are computed
- **THEN** hand speed is the peak supported individual-wrist translational speed within the documented impact-centered time window, in meters per second
- **AND** invalid jumps and unsupported time intervals cannot produce speed peaks
- **AND** swing plane is the inclination of address-to-top hand-midpoint displacement, not a fitted plane or a club-shaft measurement
- **AND** a degenerate hand-path displacement is unavailable, not a zero-degree plane

### Requirement: Club-Aware Reference Ranges

The system SHALL compare only valid measurements against applicable configurable,
definition-compatible reference ranges, preserving club-profile overrides.

#### Scenario: Default range coverage

- **WHEN** the shipped configuration is used and a valid metric has a finite value
- **THEN** it resolves to a range compatible with its definition and an in-range verdict
- **AND** backswing and downswing times retain shared timing ranges
- **AND** hand speed and hand-path inclination support club-profile overrides

#### Scenario: Club profile overrides shared ranges

- **WHEN** a session records a club mapped to a profile
- **THEN** that profile's applicable entries override shared ranges
- **AND** other metrics retain applicable shared ranges

#### Scenario: Metric inside its range

- **WHEN** a valid value lies within its compatible range, inclusive
- **THEN** it is reported as in range with that range

#### Scenario: Metric with no configured range

- **WHEN** a custom configuration has no applicable range
- **THEN** the measurement remains available with its confidence status, and its verdict and range are null

#### Scenario: Non-finite metric

- **WHEN** a metric is non-finite, estimated, or unavailable
- **THEN** its in-range verdict is null, not an in-range or out-of-range judgment
- **AND** non-finite values are serialized as null

#### Scenario: Changed definition requires range review

- **WHEN** a metric's sign convention, geometry, or sampling interval changes
- **THEN** its shipped shared and club-specific ranges are reviewed against that definition
- **AND** incompatible legacy custom ranges are not silently reused
- **AND** tolerances and target ranges are not chosen merely to make recorded swings pass

### Requirement: Coaching Tips

The system SHALL generate ranked plain-English coaching only from valid out-of-range
measurements with compatible targets, without asserting unsupported anatomical direction.

#### Scenario: Only out-of-range metrics produce tips

- **WHEN** tips are generated
- **THEN** in-range, unranged, estimated, unavailable, or legacy-unverified measurements produce no coaching candidate
- **AND** the absence of a candidate does not imply a good swing

#### Scenario: Direction-specific advice

- **WHEN** a valid metric is below or above its applicable range
- **THEN** advice matches that metric's definition and measured direction
- **AND** opposite hip rotation, shoulder tilt, spine bend, or pelvis motion cannot produce the same directional fault claim
- **AND** unsigned sway advice does not invent a motion direction
- **AND** hand-path advice identifies its body-pose proxy and speed advice does not treat greater speed as inherently faulty
- **AND** no configured advice for that direction means no tip

#### Scenario: Newly ranged metric is outside its bounds

- **WHEN** valid timing, hand-speed, or hand-path inclination is outside its applicable range
- **THEN** it contributes definition-appropriate advice to the ranked candidates

#### Scenario: Ranking by normalised severity

- **WHEN** multiple eligible metrics are out of range
- **THEN** deviation is normalized by range width and candidates are ranked by severity, capped at three

#### Scenario: Tip payload

- **WHEN** tips are serialized
- **THEN** each retains `metric`, `direction` as low or high, rounded `severity`, and `text`

## ADDED Requirements

### Requirement: Per-Metric Measurement Confidence

The system SHALL distinguish `valid`, `estimated`, and `unavailable` measurements using
the reference, phase, marker, and time-window evidence actually required by each metric.

#### Scenario: Torso failure is not hidden by moving wrists

- **WHEN** shoulders or hips are frozen, implausible, missing, or insufficiently observed during an otherwise moving swing
- **THEN** their dependent metrics cannot be valid solely because wrist tracking passes
- **AND** the quality report identifies affected landmarks and measurements
- **AND** the session is not described as wholly reliable when blocking torso or reference failures exist
- **AND** independently supported metrics remain reportable with their own status

#### Scenario: Estimated reference or phase

- **WHEN** a finite measurement depends on explicitly estimated reference or phase evidence
- **THEN** it is labeled estimated with a reason and is not assigned a target verdict or coaching tip

#### Scenario: Evidence is insufficient

- **WHEN** required landmarks, common coverage, geometry, scale, or timestamps are missing or invalid
- **THEN** the metric is unavailable with a null value and a concrete reason
- **AND** a stationary segment alone does not prove tracking loss; confidence assessment distinguishes supported stillness from held or missing observations
- **AND** one failed entry does not abort the other metric entries

### Requirement: Versioned Metric Results

The system SHALL identify metric definitions and confidence evidence in saved analysis
without automatically changing existing sessions.

#### Scenario: New result contract

- **WHEN** new analysis is serialized
- **THEN** the existing session output fields remain present
- **AND** output also identifies the analysis version and reference-frame source and confidence
- **AND** each metric retains name, value, unit, range, and verdict plus a definition identifier, status, and reasons
- **AND** the payload contains no JSON NaN or Infinity tokens

#### Scenario: Legacy analysis remains readable

- **WHEN** analysis lacks definition or confidence metadata
- **THEN** it remains readable as legacy-unverified output
- **AND** missing metadata is not interpreted as valid confidence
- **AND** no read operation rewrites the session or silently upgrades its values

#### Scenario: Explicit reanalysis

- **WHEN** the user explicitly reanalyzes a saved session
- **THEN** its results are recomputed from the selected source landmarks using current definitions and recorded session context
- **AND** the new version and confidence are saved
- **AND** changed reference or definition provenance is disclosed rather than mixing old and new results

### Requirement: Metric Accuracy Verification

The system SHALL validate the metric definitions against independent deterministic
geometry and documented recorded-video evidence before presenting the change as an accuracy improvement.

#### Scenario: Adversarial ground-truth cases

- **WHEN** the metric regression suite is run
- **THEN** it covers all 19 definitions and missing dependencies, frozen torso with moving hands, spikes, collapsed projections, angle seams, handedness, coordinate transforms, and uncertain phase/reference evidence
- **AND** expected values and tolerances are specified independently of the production formulas

#### Scenario: Recorded-video review

- **WHEN** recorded swings are used to substantiate physical accuracy
- **THEN** synchronized address, top, and impact evidence, measurement definitions, reference orientation, and defensible uncertainty are documented
- **AND** a 2D video angle is not treated as exact 3D rotation ground truth
- **AND** sessions lacking sufficient evidence demonstrate correct rejection or uncertainty, not an invented corrected turn