## Why

Recorded swings can report a frozen shoulder as 0.19 degrees, hip turn as 175.62 degrees, and X-Factor as 297.41 degrees while tracking quality still says reliable. The metric audit also found lost direction and mismatches between formulas and descriptions, so passing clean synthetic tests does not establish trustworthy coaching.

## What Changes

- Validate the analysis reference frame and the landmarks required by each of the 19 metrics; expose valid, estimated, or unavailable results with reasons instead of presenting reconstructed artifacts as measured facts.
- Retain peak backswing shoulder and hip turn, but reject degenerate projections and tracking spikes, use a stable address reference, and compute circular shoulder/hip separation correctly.
- Resolve directional measurements using configured handedness and a supported target/ball reference. Do not infer fault direction from an unsigned magnitude.
- Define every metric's geometry, sampling interval, dependencies, and limitations; align review labels, target ranges, tips, voice feedback, and stats with those definitions.
- **BREAKING**: Corrected posture, directional fault, and head-excursion definitions may change values under existing metric names. Version metric definitions; old and new measurements must not be silently compared as equivalent.
- Keep saved sessions readable without rewriting them automatically. Reanalysis is explicit; unverified legacy results are not promoted to validated measurements.
- Add noisy, frozen, missing-marker, angle-wrap, handedness, and coordinate-transform regressions plus a recorded-video validation gate. Do not tune formulas to make results fall inside target bands.

## Capabilities

### New Capabilities

None. Extend the existing analysis and review capabilities.

### Modified Capabilities

- `swing-analysis`: Reference-frame validity, all metric definitions, per-metric confidence, directional coaching, safe serialization, and versioned analysis output.
- `desktop-review-ui`: Confidence-aware values and feedback, accurate descriptions, and safe handling of legacy or incompatible metric history.

## Impact

- Backend analysis: `frame_of_reference`, `metrics`, `quality`, `phases`, `tips`, and analysis serialization; API/storage contracts where results are exposed. Shared-frame changes require regression checks for P-positions and ideal overlays without redesigning their algorithms.
- Configuration: Document and validate any reference-frame, filtering, and confidence settings in the existing configuration system. Review affected shared and club-specific ranges against their actual definitions.
- Frontend: Metric API types, session review, metric metadata, stats, and spoken feedback.
- Verification: Existing Python tests and frontend checks, deterministic fixtures independent of installed-app data, and a documented manual review of synchronized recordings with uncertainty bounds.
- No new pose model, club tracking, automatic historical migration, release publishing, or camera-calibration workflow redesign is included. Where existing data cannot establish a trustworthy frame or measurement, report that limitation rather than manufacturing a corrected number.