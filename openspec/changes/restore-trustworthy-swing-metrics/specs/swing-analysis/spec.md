## ADDED Requirements

### Requirement: Metric Readiness Is Independent Of P-Position Availability

The system SHALL assess the observation, geometry and reference evidence required by each metric independently of whether P-positions can be detected.

#### Scenario: P-positions are available but metric evidence is insufficient
- **WHEN** a session has detectable P-positions but a metric's required observations, geometry or reference do not meet its existing evidence requirements
- **THEN** the P-positions remain available for review
- **AND** that metric is reported unavailable with its specific missing or rejected evidence
- **AND** interpolated, held or otherwise unsupported coordinates are not counted as observations

#### Scenario: Metric evidence is sufficient but its target range is incompatible
- **WHEN** a metric has sufficient supported observations and finite geometry but its configured reference range is missing or uses an incompatible definition
- **THEN** the measurement value may be reported as estimated without an in-range verdict or coaching tip
- **AND** the range incompatibility is reported separately from measurement availability

### Requirement: Metric Availability Identifies Reconstruction Evidence

The system SHALL expose enough per-metric evidence to distinguish unavailable measurements caused by marker support, geometry, calibration reference, timing, scale or definition compatibility.

#### Scenario: A marker is degenerate or unsupported
- **WHEN** a required marker is a sentinel value, has insufficient independent observation support, or fails session reconstruction validation
- **THEN** dependent metrics are unavailable with the affected marker or validation reason identified
- **AND** independent metrics whose own dependencies pass are not made unavailable solely by an unrelated marker failure

### Requirement: Manual Review Annotations Do Not Change Original Analysis

The system SHALL store operator judgments about individual per-camera marker observations and metric results separately from captured evidence and automatically computed analysis.

#### Scenario: A camera marker observation is reviewed
- **WHEN** an operator labels a marker observation for a specific camera, frame, and marker as correct, occluded, mislocalized, or uncertain
- **THEN** the annotation records the session, camera, frame, marker, label, and optional note
- **AND** the annotation alone does not promote or demote reconstruction support or change the saved metric result

#### Scenario: A metric result is reviewed
- **WHEN** an operator labels a metric result as correct, incorrect, or uncertain
- **THEN** the review records the session and metric definition, with an optional expected value, unit, and note
- **AND** the original computed value, confidence, target verdict, and tips remain unchanged

#### Scenario: A what-if analysis excludes reviewed marker observations
- **WHEN** the operator requests a diagnostic recalculation excluding selected camera/marker/frame observations
- **THEN** the system returns a separate result tied to the original session and the selected exclusions
- **AND** only metrics whose required evidence is affected are recomputed
- **AND** affected metrics remain unavailable when remaining evidence is insufficient
- **AND** the system does not infer or synthesize a replacement 3D point from one camera or bilateral symmetry
- **AND** the original analysis, reconstruction evidence, and calibration bundle are not overwritten

#### Scenario: Review labels are not used for automatic training
- **WHEN** manual review annotations are saved
- **THEN** they remain evaluation data and are not automatically used to train a model, change metric formulas, or tune confidence thresholds

### Requirement: Isolated Image-Supported Head Tracking Experiment

The system SHALL permit a diagnostic-only image-motion experiment on copied footage and saved Head observations without changing production pose, reconstruction, metrics or tolerance gates.

#### Scenario: Compare jitter with real image movement
- **WHEN** the diagnostic experiment tracks local image features across frames
- **THEN** forward/backward optical flow and robust motion consistency checks reject insufficient image evidence and detector disagreement rather than fill missing points
- **AND** synthetic known motion verifies that real movement is followed without temporal averaging lag
- **AND** the comparison reports coverage, rejections, jitter and motion retention together rather than declaring lower jitter alone a success
- **AND** an image-consistent trajectory remains anatomically unverified unless independent crown annotations establish correctness

#### Scenario: Keep experiment outputs separate
- **WHEN** an operator runs the experiment on controlled still, slow-movement and swing footage
- **THEN** all comparison artifacts are written outside the source session and never authorize metric support
- **AND** original videos, pose observations, annotations and metric files remain unchanged
- **AND** the existing 15-pixel reconstruction tolerance is not changed

#### Scenario: Operator supplies an independent crown starting point
- **WHEN** an operator selects and explicitly confirms a visible crown point on a native diagnostic frame
- **THEN** a separate diagnostic sidecar binds that point to the exact video hash, camera, frame and image dimensions
- **AND** operator-seeded tracking follows image motion without snapping to the absolute detector location
- **AND** lost tracking waits for a new explicit operator seed instead of automatically reseeding from the detector
- **AND** wrong-video, out-of-bounds or unconfirmed seeds are rejected
- **AND** a confirmed starting point alone does not certify the remaining trajectory or enable metric support

#### Scenario: Detector jitter does not veto operator-seeded image tracking
- **WHEN** an operator-seeded diagnostic track has valid independent image-motion evidence
- **THEN** detector position jumps, missing detections and low detector confidence neither guide nor reject that image track
- **AND** the search is initialized from prior accepted image motion rather than detector motion
- **AND** detector differences remain diagnostic values while forward/backward flow, robust feature support and image bounds still control acceptance
- **AND** a rejected image track remains unsupported until another explicit operator seed
- **AND** detector-seeded experiments and production reconstruction tolerances retain their existing gates

#### Scenario: Validate later-frame crown placement without seed leakage
- **WHEN** an operator independently marks held-out swing frames 80, 137 and 177 in both views
- **THEN** the predicted location remains hidden until that frame's judgment is saved
- **AND** the judgment is bound to the source video and exact comparison hash in a validation-only sidecar that cannot be loaded as tracking seeds
- **AND** judgments cannot be revised after prediction reveal, and seed frames cannot be used as held-out checks
- **AND** the UI then shows prediction-to-annotation image distance or an unavailable track without asserting anatomical or metric acceptance
- **AND** a changed comparison invalidates the check rather than silently scoring a new experiment

### Requirement: Isolated Paired Crown Geometry Diagnostic

The system SHALL evaluate paired image-tracked crown observations against their session-bound saved calibration without replacing original reconstruction or authorizing metric support.

#### Scenario: Triangulate diagnostic tracks with consistent camera coordinates
- **WHEN** the operator runs a paired crown geometry diagnostic
- **THEN** source hashes and native image dimensions are checked before saved distorted pixels are undistorted and triangulated
- **AND** per-camera distorted-pixel reprojection and positive depth are evaluated against existing limits
- **AND** operator seeds, rejected tracks, unmatched times and failed geometry remain missing in the gate-passed coordinate sequence
- **AND** raw and tracked reprojection comparisons use the same available frame pairs
- **AND** output is restricted to a new separate directory and all source hashes are verified unchanged

#### Scenario: Equal clip time does not establish physical timing or metric validity
- **WHEN** paired native clip times are available without independent exposure timing evidence
- **THEN** exact native frame/time identity is validated and pairing is explicitly labelled as assumed equal clip time
- **AND** no interpolation, held positions or tuned lag is used to improve apparent agreement
- **AND** camera receipt/resampling metadata is reported without claiming optical synchronization
- **AND** the diagnostic remains ineligible for metrics even where pixel and depth gates pass