## Context

See proposal.md for motivation and the delta specs for observable contracts. The current
engine uses one inferred world axis, one address sample, raw backswing extrema, and
session-level wrist checks. Results flow into review, stats, tips, and speech without
metric-specific confidence. Existing saved JSON must remain readable.

Read-only investigation on 2026-10-15 established:

| Evidence | Observation | Interpretation limit |
| --- | --- | --- |
| Session `2026-10-12_19-27-18_9ecfcf82` | Shoulder 0.19 degrees, hip 175.62 degrees; head, neck and left shoulder frozen; hip projection approaches 1.9 mm | Cannot recover true shoulder rotation from these landmarks |
| Session `2026-10-13_14-44-28_b5c83be3` | X-Factor 297.41 degrees; session labeled reliable | Circular-angle and confidence failures, not a credible coil measurement |
| Two latest analyzed sessions on Oct 13 | Sustained shoulder peaks approximately 124-128 degrees | Not explained by one isolated frame; needs independent reference and pose validation |
| Controlled single shoulder outlier | Approximately 88 degrees becomes 160 degrees | Raw maximum is vulnerable even with preserved shoulder width |
| Controlled opposite directions | Open/closed hip, targetward/away bend, and pelvis thrust/retreat collapse to matching magnitudes | Direction cannot be recovered downstream from an absolute value |
| Current test suite slice | 27 metric/quality/tip/serialization tests pass | Clean fixtures and serialization coverage do not certify physical accuracy |

Six saved metric payloads match fresh current-source calculations. This is not a display
rounding or stale-result issue. Existing installed-app recordings are investigation
evidence, not mandatory CI fixtures and not independently measured 3D ground truth.

## Goals / Non-Goals

**Goals:**

- Make metric validity a property of evidence and dependencies, not numerical finiteness.
- Keep geometry independent of world-axis labels and shared consistently across analysis.
- Make every number explainable by its definition, supported interval, and reference.
- Prevent invalid measurements from becoming confident coaching or misleading trends.
- Provide falsifiable acceptance tests before claiming improved physical accuracy.

**Non-Goals:**

- Replacing Pose2Sim, synthesizing missing landmarks, or forcing values into target bands.
- Measuring club motion, fitting a true club plane, or reconstructing ground truth from one 2D image.
- Redesigning capture/calibration, automatically migrating history, or publishing a release.
- Redesigning P-position detection or ideal poses; only shared-reference compatibility and regression coverage are included.

## Decisions

### 1. One evidence-bearing analysis reference

Introduce a small public reference-frame value owned by analysis, carrying a normalized
up vector, optional target/ball directions, source, status, and reasons. Pass it through
metric evaluation and shared-frame consumers rather than independently guessing axes.
The orchestration layer supplies available calibration/session evidence; pure analysis
functions do not inspect user files or camera devices.

Prefer a calibration ground datum only when its coordinate convention and relationship
to the session TRC are established. A board being calibrated does not prove it was level.
Check anatomical consistency with multiple usable torso and lower-body landmarks; do
not select the first present head marker. Body-only up estimates are explicitly estimated,
not a measured floor normal. Missing trustworthy ground evidence is an allowed outcome.
Do not add a calibration workflow to solve it within this change.

Project vectors using the supplied up normal rather than deleting one coordinate.
Resolve target side from supported stance geometry and configured handedness. Resolve
the ball-facing perpendicular only from supported address geometry/session evidence;
if ambiguous, directional metrics remain unavailable. Frame transforms must also
transform reference metadata. No hard-coded X/Y/Z interpretation is permitted.

Alternative rejected: simply choose another axis or use neck instead of head. That can
make one recording look better but neither validates the plane nor fixes tilted rigs.

### 2. Assess dependencies before aggregating measurements

Extend existing quality analysis with marker-pair and interval evidence: finite coverage,
per-camera support where available, held runs, changing limb lengths, projected width,
discontinuities, scale, and timestamp validity. Retain existing wrist diagnostics.
Use available interpolation/provenance evidence and 2D observations; exact stillness
alone is not sufficient proof of tracking loss. Missing evidence is unknown, not a pass.

Each metric declares required landmarks, reference components, anchors, and interval.
Evaluate it independently. A missing shoulder makes shoulder turn and X-Factor
unavailable, not every joint angle. A missing common frame invalidates only its dependents.
Blocking torso/reference failures also prevent a wholly reliable session verdict; per-entry
status remains authoritative even when session-level gating disables P-position controls.

Use `valid`, `estimated`, and `unavailable`. Valid means all required evidence meets the
declared checks, not clinical accuracy. Estimated means a useful finite result rests on
explicitly estimated evidence. Unavailable has null value. Only valid entries receive
target verdicts and coaching. Carry machine-readable reason codes with readable details.
Avoid presenting an arbitrary confidence percentage as a calibrated probability.

Alternative rejected: suppress all metrics with one global wrist-based boolean. This
both misses torso failures and discards independent measurements unnecessarily.

### 3. Robust turn aggregation without altering raw landmarks

Use supported observations in a configurable quiet address window to establish a
circular reference orientation; keep the address phase anchor itself unchanged. Reject
collapsed projections, implausible pair behavior, and unsupported jumps before peak
selection. Use time-based robust angular filtering, respecting missing intervals and the
angle seam; require sufficient supported coverage rather than accepting a lone maximum.
All adjustable windows and evidence thresholds belong in the existing configuration.

Retain peak backswing shoulder/hip turns, matching the canonical metric definition.
Compute X-Factor frame by frame as the shortest signed circular difference between
the two address-relative turns, then take the supported peak magnitude. Do not subtract
independently timed maxima, and do not treat a left/right marker swap as angle wrapping.
Do not impose the coaching band as a plausibility clamp.

Alternative rejected: always sample exactly at P4 or clip rotation to 100 degrees.
Those silently redefine the statistic or conceal evidence instead of correcting it.

### 4. Definition contract for every metric

Use stable definition IDs per metric, incremented whenever semantics change. The following
contracts drive formulas, fixture expectations, labels, and target review together:

| Metric | Definition / interval | Essential dependencies |
| --- | --- | --- |
| Shoulder turn | Supported peak absolute horizontal rotation, address to top | Both shoulders, up, stable address reference, phases |
| Hip turn | Same statistic for the pelvis line | Both hips, up, stable address reference, phases |
| X-Factor | Peak circular separation of simultaneous address-relative turns | Common shoulder/hip coverage and reference |
| Spine tilt | Forward hip-to-neck bend at address, excluding lateral bend | Hip, neck, up, ball-facing plane |
| Tempo | Address-to-top time divided by top-to-impact time | Supported ordered phases and timestamps |
| Hip sway at top | Absolute stance-axis displacement from address / stance width | Hip center, both ankles, up, address/top |
| Hip sway at impact | Same at impact | Hip center, both ankles, up, address/impact |
| Hip rotation at impact | Signed address-relative horizontal rotation, positive open | Hips, up, target direction, address/impact |
| Backswing time | Top time minus address time | Supported address/top and timestamps |
| Downswing time | Impact time minus top time | Supported top/impact and timestamps |
| Shoulder tilt at impact | Inclination to horizontal, positive trail shoulder lower | Both shoulders, up, handedness, impact |
| Spine-angle change | Absolute change in forward-bend component, address to impact | Hip, neck, up, ball-facing plane, phases |
| Head movement | Maximum 3D excursion from address through impact | Supported head samples, address reference, scale |
| Early extension | Signed address-to-impact pelvis displacement, positive toward ball | Hip, up, ball direction, scale, phases |
| Reverse spine | Signed top-frame lateral spine bend, positive targetward | Hip, neck, up, target direction, top |
| Knee flex | Mean included joint angle of both knees at address; 180 straight | Both hip-knee-ankle chains, address |
| Lead-arm straightness | Included shoulder-elbow-wrist angle at top | Configured lead chain, top |
| Hand speed | Peak supported individual-wrist speed near impact | Wrists, valid timestamps and scale, impact |
| Swing plane | Inclination of hand-midpoint address-to-top displacement | Both wrists, up, nonzero path, phases |

For knee flex, require both legs for a valid bilateral mean; a one-leg estimate is only
allowed if explicitly identified as estimated. Do not silently substitute neck for head.
Keep the current impact-centered hand-speed window concept, explicitly documented as
plus/minus 0.1 seconds by default and configurable; validate samples and differentiation
intervals before taking a maximum. This remains a hand-speed proxy, not clubhead speed.
Spine bend uses signed components internally; unsigned posture-change or sway statistics
must not generate unsupported claims about motion direction.

Review shipped ranges and advice under these definitions. Preserve per-club precedence.
For changed definitions, associate custom targets with the definition they were authored
for; incompatible legacy overrides stay inspectable but are not applied silently. Negative
pelvis retreat or away-from-target bend must not be described as ballward thrust or reverse
tilt. Test low and high advice against the signed convention, not just interval arithmetic.

### 5. Versioned output and confidence-aware consumers

Add an `analysis_version` and reference-frame metadata to session JSON. Retain current
top-level fields and metric `name`, `value`, `unit`, `range`, and `in_range`; add per-metric
`definition_id`, `status`, and `reasons`. Normalize unavailable/non-finite values to JSON
null and null target verdicts for estimates. A reason distinguishes missing targets from
missing measurements. Reference provenance records the calibration/session evidence used.

Treat results lacking metadata as legacy-unverified in API/frontend adapters. Keep their
saved payloads untouched. Display legacy numbers for inspection with no current pass/fail
styling or coaching. Explicit reanalysis uses recorded club, capture context, and applicable
reference provenance; if the original reference is absent, disclose it rather than applying
an unrelated current calibration. No new background batch migration is introduced.

Review and speech use the same confidence eligibility rule as tip generation. Stats use
only valid compatible definitions for comparable series, splitting or excluding legacy,
estimated, unavailable, or changed definitions explicitly. Respect per-session club targets.
An all-in-range claim requires all 19 measurements to be valid, compatible, ranged, and
in range; an empty list or partial assessment cannot satisfy that claim vacuously.

Alternative rejected: bump only the package version or relabel all old values as current.
Neither makes historical values comparable or supplies missing confidence evidence.

### 6. Independent validation before claiming physical accuracy

Build deterministic geometry with known positions and reference normals. Assert expected
values directly, without calling production helpers to derive the oracle. Include rotations,
translations, axis relabeling, tilted coordinates, mirrors, frame-rate changes, missing data,
frozen torso, realistic stillness, outliers, near-zero projections, angle seams, and false
phase anchors. Preserve clean-swing performance with declared per-metric tolerances.

Use recorded cases to test failure classification and compare synchronized videos at
address/top/impact. Record reference orientation, frame choices, observed visibility,
independent measurements and uncertainty. A 2D projected angle alone cannot certify 3D
shoulder/hip rotation; if ground truth cannot be established, the accuracy gate remains
unmet and the report must say so. Correct abstention is a passing outcome for corrupted data.

## Risks / Trade-offs

- Existing recordings lack trustworthy ground evidence -> estimates/unavailable values are preferable to confident fabricated turns; state the capture-evidence limitation.
- Conservative checks suppress usable measurements -> tune evidence thresholds against independent clean/noisy fixtures, never target ranges; supported stillness remains valid.
- Filtering attenuates real peaks -> use time-based windows and retain peak/timing error bounds across frame rates.
- Reference changes affect phases, checkpoints and overlays -> regression-test their shared frame and preserve anchor semantics; do not compensate by altering raw pose landmarks.
- Directional and excursion definitions change coaching and history -> version definitions and ranges and explicitly segregate old results.
- Large personal recordings are unavailable in CI -> keep synthetic regression oracles self-contained and document manual evidence without committing recordings by default.

## Migration Plan

1. Land version/status contracts and legacy readers before enabling corrected measurements.
2. Add the evidence-bearing reference and dependency checks with deterministic regressions.
3. Correct metrics, review ranges and coaching, and update all UI consumers together.
4. Run focused and full gates, then perform the recorded-video acceptance review.
5. Leave existing session files unchanged until explicit reanalysis; document limitations.

Rollback restores the earlier application version without rewriting saved captures. New
metadata is additive, but older software cannot validate newer definitions; do not claim
cross-version trend compatibility or automatically downgrade reanalyzed results.