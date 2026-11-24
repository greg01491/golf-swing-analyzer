## Context

See `proposal.md` for the observed failure. The 15:15:09 capture has plausible P-position indices, but its metric payload has all values null. Its saved reconstruction evidence reports a zero-valued Head trajectory, failed camera/body-region validation, and weak torso/leg support. Separately, the active user config has no `range_definition_version`, so its existing ranges are not compatible with the current definitions. The calibration and metric-confidence OpenSpec changes remain active and own physical acceptance and formula accuracy respectively.

The 15:15 recording is diagnostic evidence only: it was processed with legacy-unverified camera geometry and is not an acceptance sample. User recordings and calibration files must not be copied into the repository or rewritten implicitly.

## Goals / Non-Goals

**Goals:**

- Make metric values, evidence status, reference-range compatibility, and coaching eligibility independently understandable.
- Ensure each metric's support check uses only its required markers and analysis interval while rejecting held, interpolated, degenerate, or otherwise unsupported samples.
- Provide a safe, explicit path for reviewing and migrating legacy user-authored reference ranges.
- Add synthetic regressions for P-position availability alongside failed metric evidence, zero/sentinel landmarks, partial per-metric coverage, and legacy configuration.
- Let users build a local review set of camera/frame/marker judgments and metric judgments, with optional manual expected values.
- Offer a clearly labeled what-if metric pass that can exclude reviewed marker observations from support without modifying original analysis.

**Non-Goals:**

- Recalibrate or certify this rig, change camera synchronization, or close the physical gate in `repair-rig-calibration-and-ground-reference`.
- Change metric formulas, target bands, evidence thresholds, or coaching advice owned by `improve-metric-accuracy-and-confidence`.
- Promote a P-position, finite filled coordinate, or visually plausible skeleton to proof that a metric is supported.
- Automatically rewrite existing sessions or user configuration during read, startup, or reanalysis.
- Train a pose model, classify manual review as objective ground truth, or claim a what-if exclusion repairs 3D coordinates or calibration.

## Decisions

1. **Keep measurement availability separate from verdict eligibility.** A finite value may be returned as estimated when its required geometric observations are sufficient but its target range or physical reference is not validated. A metric whose required evidence fails remains unavailable; no provisional value is surfaced as a coaching fact. This is safer than either discarding every finite estimate because a range is stale or displaying values from unsupported geometry.

2. **Retain per-metric evidence gates.** Evaluate the markers and frames required for each metric, and report the specific support/reference failure. Do not use session-level P-position success or another metric's coverage as a substitute. Preserve the existing configured minimums until evidence justifies a separately reviewed threshold change.

3. **Treat legacy ranges as unverified, not current by default.** A missing or unknown definition version keeps user ranges readable but incompatible for verdicts. Offer an explicit review/migration path that preserves the original values and records the chosen current version; do not silently stamp version 2 onto an old file.

4. **Treat zero-valued missing markers as invalid geometry.** Use reconstruction provenance to distinguish a genuine measured origin from a missing/degenerate landmark. Keep unsupported dependent metrics unavailable and identify the affected marker rather than substituting a neighboring point.

5. **Consume calibration evidence; do not duplicate calibration work.** Metric validation uses the exact session-bound reconstruction and reference evidence. A failed legacy reconstruction is not repaired by metric reanalysis; any new calibration or 3D reconstruction remains an explicit operator action governed by the calibration change.

6. **Store review as a versioned per-session sidecar.** Keep annotations in a separate local review file keyed by session ID. Marker observations include camera role, that camera's frame index, marker name, judgment, and optional note; metric judgments include the metric definition ID, judgment, optional expected value, unit, and note. Do not assume equal frame indices across cameras are simultaneous exposures. Do not edit `metadata.json`, `metrics.json`, videos, TRCs, evidence files, or calibration bundles when saving a review.

7. **Make what-if exclusions invalidate support, not fabricate geometry.** Apply chosen camera/marker/frame exclusions to a copy of the analysis support mask and rerun metrics from the same saved 3D sequence. This answers which metrics depend on an observation; because the 3D point was already triangulated, the result is not a repaired measurement. If the remaining evidence is insufficient, the affected metric stays unavailable. A corrected 3D point or new calibration requires a separate explicit workflow.

8. **Treat user labels as evaluation data.** Manual correct/incorrect/uncertain judgments and expected values are for comparing algorithm outputs and building regressions. They do not feed automatic model training, threshold tuning, or metric formulas.

9. **Highlight reviewed markers on the source-view overlay.** Read the saved per-camera 2D keypoint for the selected camera, frame, and marker, then draw a screen-space pulse over the pose overlay video. Use that camera's presented media time to select the frame; do not assume the other view is at the same physical exposure. If the 2D coordinate is absent or invalid, hide the indicator rather than estimating it.

10. **Drive review from metric dependency evidence.** Retain rejected marker and combined-geometry spans at each metric's existing support gate, limited to that metric's required frames. A read-only diagnostic uses saved phase anchors and current settings for historical sessions, explicitly separate from the unchanged saved result. Map timestamps using each saved camera's own frame rate; if mapping or camera attribution is unavailable, say so rather than inventing it. Group repeated failures, expose individual frames, seek/select/highlight on review, and show existing labels. Keep target/reference/timing/scale failures separate from observation rows; an out-of-range value alone does not identify a bad marker.

11. **Default to measured tolerance failures, not support-mask guesses.** Reproject the exact saved TRC through its bound saved calibration and compare requested source-view observations with the existing reprojection, depth and confidence gates. The default queue contains only the failing camera-native frames and shows each value/limit. Passing views and unexplained support rejections remain outside that default queue; the broader support queue is opt-in. A reprojection mismatch is evidence of a failed consistency check, not proof that the 2D point is misplaced. Missing bound evidence yields an explicit unavailable check rather than guessed failures.

12. **Separate temporal image consistency from anatomical correctness.** The diagnostic tracker uses configurable local Shi-Tomasi features, forward/backward pyramidal Lucas-Kanade flow and RANSAC partial-affine motion. Detector displacement initializes the search but does not bypass independent image checks. Missing/low-confidence points, weak texture, inconsistent motion and excessive detector disagreement produce gaps and unverified reseeds, not filled coordinates. Known synthetic translation tests check motion following without an averaging filter. Native videos are streamed with one decoder thread; output directories must be new and outside input sessions, source hashes must match, and reports always state that anatomical crown correctness and metric eligibility are unverified/false. Controlled still/slow clips and the original swing use fixed settings; lower jitter is reported alongside coverage and never used as sole acceptance. Initial visual inspection found that detector-seeded tracking can remain on the temple, so the experiment is not a production head-excursion fix. Independent crown localization is required before acceptance.

13. **Keep operator-seeded motion independent of detector jitter.** In operator mode only, previous accepted image displacement initializes optical flow; detector position, confidence and motion do not guide or veto tracking. Detector differences remain reported for diagnosis. Forward/backward consistency, image-feature/RANSAC support, bounds and explicit operator reseeding still control the trajectory. Detector-seeded mode retains its existing confidence and disagreement gates, and production reconstruction tolerances remain unchanged. A fixed-settings six-view rerun improved coverage, with five tracks reaching clip end and the DTL swing stopping on image inconsistency at frame 222. Neither coverage nor sampled image placement certifies anatomical correctness or physical head-excursion accuracy.

14. **Keep paired-crown geometry a separately gated diagnostic.** Triangulate native pixels through each session's saved pinhole calibration with distortion-consistent normalization and reprojection; report positive depth and the existing pixel limit independently. Validate input hashes, dimensions and frame identities, pair only exact native clip times, and retain seed/rejected/unmatched frames as gaps. Raw/tracked comparisons use the same frame pairs. Host receipt timestamps and resampled fps do not establish exposure synchronization, and low residuals would not certify calibration, scale or physical excursion. The three-case first run had no paired observations passing both 15-pixel reprojection limits even in the still clip, so improved visual tracking is not promoted to metric support.

## Risks / Trade-offs

- [Legacy user ranges may have meanings that cannot be proven from their values alone] → Require operator review before assigning a current definition version; retain a backup and show which ranges remain unverified.
- [An estimated numeric value may be mistaken for a validated coaching result] → Keep range verdicts and coaching disabled for estimated/unavailable results and show status and reasons beside the value.
- [Strict support checks may still leave most metrics unavailable on the current rig] → Report marker-, camera-, and interval-specific evidence and link the failure to reconstruction/calibration validation; do not relax thresholds to improve apparent availability.
- [Users may treat a what-if result as a corrected measurement] → Keep original and what-if results visually separate and state that exclusions do not re-triangulate or replace bad 3D coordinates.
- [Manual reviews may become stale after analysis changes] → Bind metric reviews to definition IDs and clearly mark them for re-review when definitions change; keep camera/frame marker labels as the user's historical observations.
- [Personal capture artifacts could leak into tests] → Reproduce failure shapes with generated fixtures and synthetic support arrays; never add session video, calibration files, or personal metrics JSON to source control.

## Migration Plan

1. Add backward-compatible parsing and diagnostics for missing/unknown metric definition versions without modifying the user's config on read.
2. Add an explicit review/migration action that preserves current user ranges, records a backup, and changes the definition version only after confirmation.
3. Deploy the UI/API and analysis changes; existing sessions remain unchanged until explicit reanalysis, and reanalysis does not silently replace their reconstruction or calibration evidence.
4. Roll back by restoring the backed-up config and prior application build. Previously saved session JSON remains readable by the legacy reader.