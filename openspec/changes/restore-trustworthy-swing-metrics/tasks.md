## 1. Reproduce Metric Unavailability

- [x] 1.1 Add synthetic regressions where P-position inputs are present but required metric markers are unsupported, held, or degenerate; verify P-position output remains available while dependent metrics remain unavailable with specific reasons.
- [x] 1.2 Add metric-range compatibility tests for current, missing, and unknown definition versions; verify an incompatible range removes verdict/coaching eligibility without hiding a finite supported measurement.

## 2. Preserve Metric Evidence

- [x] 2.1 Trace zero/sentinel marker values through reconstruction and evidence generation; distinguish unsupported zero-filled markers from genuine observed coordinates and verify dependent metrics do not treat them as valid.
- [x] 2.2 Verify metric support is evaluated for each metric's required markers and frames, with held/interpolated samples excluded and unrelated failed markers not suppressing independent supported metrics.
- [x] 2.3 Separate metric measurement status from range compatibility and coaching eligibility in the serialized result; verify unavailable geometry stays null while supported estimates remain explicitly estimated and never receive a verdict or tip.

## 3. Handle Legacy Metric Configuration

- [x] 3.1 Report missing and unsupported metric range-definition versions as legacy/incompatible while loading existing user configuration; verify custom ranges are preserved and startup/capture continue.
- [x] 3.2 Add an explicit review/migration flow for metric ranges; verify the original config is recoverable and no version is silently assigned to unreviewed ranges.
- [x] 3.3 Verify current-version ranges are applied to the intended metrics and club profiles, while incompatible ranges produce no target verdict or coaching.

## 4. Explain Metric Readiness In Review

- [x] 4.3 Add versioned per-session review annotation storage for camera/frame/marker and metric-definition judgments; verify annotations use a separate sidecar and reads/saves never rewrite original metrics, video, or calibration evidence.
- [x] 4.4 Add marker-observation review controls for correct, occluded, mislocalized, and uncertain labels with optional notes; verify each label is bound to the selected camera, frame, and marker.
- [x] 4.5 Add per-metric correct, incorrect, and uncertain review with an optional expected value/unit/note; verify labels remain distinct from generated confidence and coaching status.
- [x] 4.6 Add a separate what-if analysis that excludes selected marker observations from metric support; verify dependent metrics remain unavailable when evidence is insufficient and the result never alters the original analysis or claims to repair 3D geometry.
- [x] 4.7 Pulse the selected marker's saved 2D coordinate over the selected camera's pose overlay at that camera's presented frame; verify missing coordinates are not guessed and highlighting follows frame stepping.

- [x] 4.8 Add and verify an evidence-backed review queue with metric-specific rejected spans, camera-native frame navigation, existing judgments, explicit uncertain attribution and separate non-observation blockers; historical diagnostics must remain read-only.

- [x] 4.9 Default the review queue to actual per-camera numeric tolerance failures, display measured values and existing limits, exclude passing/unresolved observations, and retain all support rejections behind an opt-in control without modifying saved evidence.

- [x] 4.10 Order review groups by descending peak pixel reprojection error and default to the worst frame, preserving chronological frame lists and keeping unlike units separate; verify with frontend tests and the live review table.

- [x] 4.11 Group source and counterpart camera review actions for each selected issue frame, including unflagged comparisons and separate saved judgments; verify independent native frame rates, unavailable mappings and live Head face-on frame 136 navigation.

- [x] 4.12 Implement and test an isolated image-supported Head tracking experiment; compare still/slow baselines and the original swing, inspect anatomical drift and lag, preserve source hashes and leave production metrics and tolerance gates unchanged. The experiment remains anatomically unverified and is not production-enabled; real-footage lag is not certified without independent crown ground truth.

- [x] 4.13 Add source-bound operator crown starting points and a separate local native-frame annotation page; verify explicit visibility confirmation, coordinate mapping, invalid-seed rejection, no automatic detector reseeding and non-metric output. Leave actual anatomical clicks to the operator.

- [x] 4.14 Decouple operator-seeded diagnostic acceptance and search initialization from detector jitter/missing observations; retain image gates and explicit reseeding, test known motion and occlusion, rerun all six seeded cases without tuning, and verify source preservation and non-metric output.

- [x] 4.15 Add blinded check-only review of swing frames 80/137/177 in both cameras, with immutable source/comparison-bound validation records, post-save prediction reveal, no tracking-seed leakage, and explicit distinction from reconstruction tolerance or metric acceptance.

- [x] 4.16 Add read-only continuous comparison playback with normal/slow speeds, looping, native-frame stepping, scrubbing and paired-view time preservation; verify media streaming, unavailable states, independent-check access locks, unchanged sidecars and desktop/mobile rendering.

- [x] 4.17 Implement and verify isolated paired-crown triangulation using saved session calibration, distortion-consistent reprojection, depth gates and exact native-time pairing; compare all three cases with raw observations on the same frames, preserve gaps/source hashes, and leave synchronization/calibration/metric acceptance unverified. All three real-data cases failed the paired 15-pixel reprojection gates, including the still clip; no production metric support was enabled.

## 5. Integration And Evidence

- [x] 5.1 Run focused analysis, reconstruction-evidence, configuration/API, session serialization and frontend review tests; verify historical sessions remain readable and are not rewritten on load.
- [x] 5.2 Run the full backend and frontend validation suites plus strict OpenSpec validation; verify no support threshold is weakened and no unsupported metric becomes valid.
- [ ] 5.3 After the separate calibration change provides accepted compatible geometry/reference evidence, review a new capture and explicitly reanalyze it; verify supported metrics and ranges appear where evidence passes and unsupported entries retain precise reasons.
- [x] 5.4 Run marker/metric annotation and what-if integration tests; verify camera frame indices remain camera-specific, annotations survive reload, and user labels never feed automatic training or default metric output.