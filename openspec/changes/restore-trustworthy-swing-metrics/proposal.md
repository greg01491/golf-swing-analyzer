## Why

The 2026-10-21 15:15:09 session detected all ten P positions, but all 19 metrics were saved as unavailable. Its reconstruction has weak body-region support and a degenerate Head marker, while the installed user configuration lacks the current metric range-definition version. P-position success and metric readiness therefore need distinct evidence, compatibility, and review behavior.

## What Changes

- Diagnose and correct metric availability on reconstructions with incomplete or degenerate marker evidence, while preserving conservative per-metric validation and never treating filled coordinates as observations.
- Handle legacy metric-range configuration explicitly: retain custom values, identify incompatible definitions, and provide a safe migration or correction path instead of silently applying old ranges to new metric definitions.
- Make the review UI distinguish an unavailable measurement from a computed estimate without a compatible range, and show the specific missing observation, reference, reconstruction, or configuration evidence.
- Let the operator annotate individual per-camera, per-frame marker observations as correct, occluded, mislocalized, or uncertain, and metric results as correct, incorrect, or uncertain, with optional notes/expected values; store review data locally and separately from source evidence and original analysis.
- Provide an optional what-if metric calculation using selected marker exclusions, clearly separated from the original results; exclusions affect only metrics that depend on those markers, and the system does not invent a replacement 3D point or claim to retriangulate from one camera.
- Use manual annotations as a local validation/evaluation set; do not automatically train a model, change metric formulas, or tune thresholds from the labels.
- Add an evidence-backed manual-review issue table linking affected metrics and rejected marker spans to camera-native frames, without assigning camera blame when only combined 3D support is known.
- Provide an isolated image-supported Head tracking diagnostic for evaluating jitter, motion following and anatomical drift on copied inputs; no diagnostic trajectory is promoted to production observations or metric support.
- Add regression coverage for the reported failure shape: P positions can be present while metric prerequisites fail. Do not commit personal swing footage or calibration data.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `swing-analysis`: Keep P-position output separate from metric eligibility; report per-metric evidence and range-definition compatibility without weakening observation or geometry requirements.
- `desktop-review-ui`: Explain why a metric is unavailable or estimated, distinguish value availability from range verdict/coaching eligibility, and support local marker/metric review annotations plus a separate what-if analysis.
- `runtime-configuration`: Safely handle existing user configurations that omit or use an incompatible metric range-definition version, preserving custom settings and requiring explicit resolution where automatic migration is unsafe.

## Impact

- Backend analysis, metric serialization, configuration loading/migration, session validation evidence, and frontend metric review.
- Depends on validated reconstruction evidence from `repair-rig-calibration-and-ground-reference`; does not replace that change's independent hardware acceptance task or certify the 15:15:09 session.
- Does not lower confidence thresholds, promote interpolated/held markers to observations, revise metric formulas or coaching ranges, alter P-position detection, or modify personal recordings.