## 1. Independent Regression Evidence

- [x] 1.1 Extend existing metric fixtures with independently specified geometry and expected values for all 19 definitions; verify each entry has a named numeric tolerance and an oracle that does not call production geometry helpers.
- [x] 1.2 Add frozen-shoulder/hip-with-moving-wrists, head-return excursion, collapsed projection, left/right swap, and isolated turn-spike reproductions; verify they fail for the intended current defects before implementing fixes.
- [x] 1.3 Add tilted/rotated/translated coordinate and mirrored-handedness cases with reference evidence transformed consistently; verify invariance expectations and anatomical signs are asserted explicitly.
- [x] 1.4 Add missing-marker, supported-stillness, invalid-scale, irregular/non-increasing-time, and uncertain-phase/reference cases; verify expected per-metric validity and unaffected independent entries are specified.

## 2. Result Contracts And Legacy Reading

- [x] 2.1 Add analysis version, per-metric definition IDs, valid/estimated/unavailable status, and reason metadata to backend result contracts; verify serialization tests retain existing fields and exactly 19 metric entries.
- [x] 2.2 Normalize unavailable/non-finite values to JSON null and validate strict JSON output; verify NaN/Infinity never appear and estimates/unavailable values have null target verdicts.
- [x] 2.3 Add backward-compatible API/frontend readers for missing version/confidence metadata; verify legacy payloads load as unverified without rewriting files or being treated as current valid measurements.

## 3. Supported Reference Frame And Quality Dependencies

- [x] 3.1 Trace available session calibration provenance and TRC coordinate conventions, then supply supported ground evidence to pure analysis through a public reference contract; verify an unrelated calibration or arbitrarily oriented board cannot be accepted as the session floor normal.
- [x] 3.2 Implement multi-landmark reference assessment with estimated/unavailable fallback and normalized-vector projections; verify frozen/conflicting head data cannot select an arbitrary axis and rigid-transform regressions pass.
- [x] 3.3 Resolve target and ball-facing directions only from supported geometry and configured handedness; verify mirrored cases preserve anatomical meaning and ambiguous ball-side evidence makes dependent directional metrics unavailable.
- [x] 3.4 Extend existing quality evidence to shoulders, hips, head, and other metric dependencies using available 2D support, gap/held-run evidence, pair geometry, and timestamps; verify frozen torso is caught without marking genuinely supported stillness as tracking loss.
- [x] 3.5 Add configurable, validated evidence thresholds and time-based windows to the existing config system; verify config tests reject invalid settings and old configurations load with documented defaults.
- [x] 3.6 Propagate reference/phase/marker uncertainty per metric and update the aggregate quality verdict; verify good wrist coverage cannot override torso failure while independent supported metrics remain reportable.

## 4. Turn And X-Factor Corrections

- [x] 4.1 Establish a robust circular address reference from supported quiet-window samples without moving phase anchors; verify seam-crossing and contaminated-address fixtures preserve expected rotations.
- [x] 4.2 Reject unsupported pair observations and use time-based robust turn aggregation before selecting backswing peaks; verify the isolated 160-degree outlier is excluded, real peaks remain within declared tolerances across frame rates, and no coaching-band clamp is used.
- [x] 4.3 Compute peak X-Factor from simultaneous supported circular differences; verify seam crossings never produce values above 180 degrees, unrelated peak times are not subtracted, and inadequate shared coverage becomes unavailable.
- [x] 4.4 Verify shared-reference integration with phases, P-position anchors, and ideal overlays using existing neighboring tests; confirm no raw landmark fabrication or unrelated checkpoint-algorithm redesign is introduced.

## 5. Remaining Metric Definitions

- [x] 5.1 Separate forward spine bend from lateral bend and compute forward-angle maintenance consistently; verify isolated forward/side-bend fixtures do not contaminate one another and missing ball-plane evidence propagates correctly.
- [x] 5.2 Preserve anatomical signs for impact hip rotation, impact shoulder tilt, reverse spine, and early extension; verify open/closed, trail/lead shoulder drop, targetward/away bend, and ballward/retreat fixtures produce distinct expected signs for both handedness settings.
- [x] 5.3 Replace address-to-impact head displacement with maximum supported excursion and remove silent anatomical substitution; verify a 30 cm excursion followed by return reports 30 cm and unsupported frozen head data is not scored as perfect stability.
- [x] 5.4 Harden knee and lead-arm included angles against missing or degenerate chains; verify 180 degrees means straight, a valid knee mean requires both supported legs, and any one-leg estimate is explicit.
- [x] 5.5 Validate stance-normalized sway and all timing metrics against their documented dependencies; verify zero stance width, invalid phase ordering, and uncertain anchors cannot produce valid results.
- [x] 5.6 Validate wrist speed intervals and the configurable impact window before peak selection; verify known constant-speed motion across frame rates, isolated tracking jumps, and invalid timestamps behave as specified.
- [x] 5.7 Preserve endpoint hand-path inclination as an explicit proxy and reject zero/unsupported displacement; verify known inclinations and estimated-up propagation without describing the result as a fitted club plane.

## 6. Targets And Coaching Eligibility

- [x] 6.1 Review shared and club-profile targets against every changed definition and attach definition compatibility to custom targets; verify club precedence, shipped coverage for valid metrics, and non-application of incompatible legacy overrides.
- [x] 6.2 Gate verdicts and tip candidates on valid confidence plus compatible ranges; verify estimated/unavailable/legacy-unverified entries cannot produce advice and existing top-three normalized severity ranking remains intact.
- [x] 6.3 Update direction-specific advice and proxy wording to match the definition matrix; verify negative pelvis retreat or away-target bend never produces ballward-thrust or reverse-tilt advice and unsigned sway never invents direction.

## 7. Review, Stats, Speech, And Explicit Reanalysis

- [x] 7.1 Render valid, estimated, unavailable, and legacy-unverified metric states with reasons and correct value/target styling; verify representative payloads show no false green/red verdict for uncertain entries and manual video review remains usable.
- [x] 7.2 Align all metric labels/help with geometry, sign, interval, and proxy limits; verify descriptions cover the 19-entry matrix, including peak horizontal turns, head excursion, included knee angle, and peak near-impact wrist speed.
- [x] 7.3 Segregate incompatible definition history and exclude uncertain values from comparable trend summaries; verify mixed-version and mixed-club examples do not create a misleading connected series or universal target band.
- [x] 7.4 Apply shared eligibility rules to focused speech and default summaries; verify empty/partial/uncertain assessments cannot claim all in range, all 19 valid in-range measurements can, and disabling voice still cancels speech.
- [x] 7.5 Integrate explicit session reanalysis with version/reference provenance and legacy guidance; verify read-only session/chart access preserves saved files and explicit reanalysis records current definitions without silently substituting unrelated calibration context.

## 8. Integration And Physical Accuracy Acceptance

- [x] 8.1 Run focused metric, config, quality, tip, serialization/API, phase, P-position, ideal-pose, and frontend consumer checks against the checkout's source; verify test imports resolve to this repository rather than a stale editable installation.
- [x] 8.2 Run the full backend suite, Ruff, Black, frontend lint/build, and strict OpenSpec validation; verify failures introduced by this change are resolved and unrelated baseline warnings are documented separately.
- [x] 8.3 Review representative synchronized recordings, including the documented frozen-body case and sustained 124-128-degree shoulder cases; deliver an evidence record with source provenance, address/top/impact frames, reference orientation, observations, independent measurements where defensible, and uncertainty bounds without committing personal videos by default.
- [ ] 8.4 Evaluate the recorded-video accuracy gate separately from synthetic test success; verify corrupted sessions abstain appropriately and leave physical accuracy acceptance explicitly blocked wherever trustworthy 3D ground truth is unavailable rather than substituting a projected 2D angle.
- [x] 8.5 Document definitions, evidence requirements, legacy/reanalysis behavior, target compatibility, and known measurement limits; verify setup guidance and the original project spec/plan/tasks are consistent with the implemented scope before requesting completion or archive.

Task 8.4 remains blocked on independently supported 3D reference geometry and physical
measurement uncertainty. See validation.md. Automated tests and correct abstention on
corrupt recordings do not satisfy this acceptance gate; do not archive or claim certified
shoulder/hip accuracy yet.