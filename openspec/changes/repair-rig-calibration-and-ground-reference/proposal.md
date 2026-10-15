## Why

The saved calibration reports 0.2 px error but gives 23.9 px median error on held-out observations from a recent swing; an in-memory diagnostic refit reduces that to 3.19 px without certifying physical turn accuracy. Calibration validation, reconstruction conventions, and missing ground/target evidence must be repaired before the remaining physical-accuracy gate in `improve-metric-accuracy-and-confidence` can be closed.

## What Changes

- Validate candidate camera geometry on temporally held-out observations from both cameras, report body-region coverage and depth/scale checks, and reject insufficient evidence rather than accepting a favorable fit-inlier score.
- Apply one explicit lens-distortion convention across association, triangulation, and reprojection; retain observation/gap provenance so held landmarks are not mistaken for measurements.
- Bind calibration to camera identity, resolution, rotation, capture mode, lens settings, and content fingerprints; detect mismatches and flag unsupported legacy provenance without claiming that a frame-rate change alone proves camera movement.
- Add a guided capture of a rigid measured board on a confirmed level ground plane, with a marked target direction and confirmed golfer/ball side. Validate visibility, geometry, and the transform into the actual TRC coordinate convention.
- Publish accepted calibration/reference bundles atomically, snapshot provenance per reconstruction, and generate source-bound reference metadata for analysis. Keep old sessions unchanged unless the operator explicitly reprocesses them.
- Show fit quality separately from held-out validation, compatibility, and ground-reference readiness, with cause-specific corrective actions.
- **BREAKING**: Calibration files accepted by the old single-score gate may be legacy-unverified or incompatible under the new evidence checks. They remain readable, but are not silently certified as valid for current metric coaching.

## Capabilities

### New Capabilities

None. Extend the existing calibration, reconstruction, and review contracts.

### Modified Capabilities

- `camera-calibration`: Held-out two-view validation, camera-mode compatibility, measured ground/target references, and safe activation with provenance.
- `pose-reconstruction`: Consistent distortion handling, calibration snapshots, TRC-frame reference transfer, and reconstruction observation provenance.
- `desktop-review-ui`: Guided reference capture and separate calibration validation, compatibility, and metric-readiness states.

## Impact

- Backend pose calibration, wizard orchestration, reconstruction adapters, session metadata, readiness/API payloads, configuration, and the existing analysis-reference handoff.
- Frontend calibration wizard and readiness display; existing confidence-aware metric review remains authoritative.
- Extend existing calibration/reconstruction/API tests with independent synthetic camera geometry, distortion, held-out failures, camera-mode changes, provenance, and ground-normal transforms. Add a hardware acceptance protocol with stated uncertainty.
- Reuse OpenCV, Pose2Sim, and the printed board; no new pose model, automatic calibration from ordinary swings, release publishing, or automatic rewriting/deletion of personal recordings.
- Depends on the implemented metric-confidence contracts of `improve-metric-accuracy-and-confidence`. This change supplies the missing evidence path; it does not mark that change's remaining physical acceptance task complete by declaration.