## 1. Range Defaults And Coverage

- [x] 1.1 Define documented, conservative defaults for `backswing_time_s`, `downswing_time_s`, `hand_speed_impact_ms`, and the body-pose `swing_plane_deg` proxy, including club-profile overrides where appropriate; verify the values match metric units/formulas and the existing timing guidance.
- [x] 1.2 Add the four ranges to `config/config.yaml` without changing the configuration schema; verify the application config parses and every mapped club resolves an applicable range for all 19 metrics.
- [x] 1.3 Add an inventory regression test that computes a complete synthetic swing and verifies every finite metric produced under the shipped configuration has a non-null range and verdict; verify the focused metrics/config tests pass.

## 2. Coaching Tips

- [x] 2.1 Add low/high advice for backswing time, downswing time, hand speed, and swing-plane proxy, keeping hand-speed wording neutral about useful speed and identifying swing plane as hand path; verify focused tests exercise both directions for all four metrics.
- [x] 2.2 Verify newly ranged metrics participate in normalized severity ordering and the existing top-three cap alongside established metrics, including overlapping tempo/timing candidates; verify ranking tests pass.
- [x] 2.3 Add a coverage assertion that the four newly ranged metrics have non-empty advice in both directions while preserving intentionally non-actionable directions for existing metrics; verify the focused tip suite passes.

## 3. Review And Feedback UI

- [x] 3.1 Verify session review and stats charts render the four ranges from API payloads as labelled target ranges and shaded bands, adding focused frontend coverage or the smallest test seam supported by the existing setup.
- [x] 3.2 Derive visual and spoken no-tip summaries from metric verdicts so they say "everything measured is in range" only when true and otherwise say there are no actionable tips; verify in-range, out-of-range-without-selected-tip, unranged, and unavailable cases.
- [x] 3.3 Verify an out-of-range newly ranged metric is visually flagged, can appear in the displayed top-three tips, and can drive focused spoken feedback; run the frontend typecheck and focused regression checks.
- [x] 3.4 Keep club selection enabled while capture is armed and explain that changes apply to the next capture; verify an armed club change is accepted by the API and saved on the triggered session.
- [x] 3.5 Show an inline warning and disable P-position seeking when tracking quality is explicitly unreliable, while preserving video playback and navigation when reliable or unknown; verify the frontend typecheck/build and inspect both quality states.

## 4. Documentation And Validation

- [x] 4.1 Update `spec.md`, `plan.md`, and the root `tasks.md` to reflect the complete 19-metric inventory, range coverage, and coaching behavior; verify the hand-maintained documents agree with the OpenSpec requirements.
- [x] 4.2 Run focused backend tests and lint for configuration, metrics, tips, and API serialization, plus frontend typecheck, lint, and build; verify no new failures.
- [x] 4.3 Re-analyse representative sessions for at least a driver and an iron, inspect all four target bands and out-of-bounds tips, and tune only configuration defaults if real rig values show the conservative targets are unsuitable. Verified driver `2026-10-12_11-15-17_0ece0c1d` and 7-iron `2026-10-12_11-25-18_19d7baad` with updated workspace code; out-of-range new metrics produced candidates, but neither swing's candidates ranked in the displayed top three. Both reconstructions were unreliable (56% and 60% estimated frames), so defaults were not tuned from these measurements.