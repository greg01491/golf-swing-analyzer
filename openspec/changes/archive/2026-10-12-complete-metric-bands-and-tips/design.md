## Context

See `proposal.md` for motivation. Metric comparison, chart bands, and tip generation already share the backend range payload: a configured range produces `in_range` plus `range`, and the React stats chart draws a band whenever `range` is present. The computed metric inventory has grown to 19, while the default configuration covers 15 and the canonical swing-analysis metric list still names the original seven.

The four uncovered metrics have different semantics. Backswing and downswing duration are components of tempo; hand speed generally rewards useful speed rather than a narrow universal optimum; and swing plane is derived from body-pose hand travel, not club tracking, and varies with club and golfer geometry.

## Goals / Non-Goals

**Goals:**

- Keep one backend-owned source of truth for target ranges, verdicts, chart bands, and tip eligibility.
- Give all shipped metrics default range coverage while preserving user-editable configuration.
- Make advice for the four newly ranged metrics useful without overstating what body pose can measure.
- Detect future drift between computed metrics, configured defaults, metadata, and tip rules.

**Non-Goals:**

- Infer a golfer-specific ideal from age, sex, handicap, height, or mobility.
- Treat hand-path inclination as measured club-shaft plane.
- Remove the existing top-three coaching limit or redesign the stats charts.
- Change metric formulas or phase detection.

## Decisions

1. **Complete default ranges in configuration rather than synthesizing bands in the UI.** Add shared defaults for the two phase durations and baseline defaults plus club-profile overrides for hand speed and swing plane. This keeps API verdicts, session review, stats, settings, and tips consistent. Numeric defaults will be documented and conservative; timing starts from the existing UI guidance, while speed and plane defaults must be checked against the meaning and scale of these body-pose proxies. Alternatives considered: UI-only bands would disagree with backend flags and tips; hardcoded analysis thresholds would violate the project's tunable-configuration rule.

2. **Preserve the existing null behavior for deliberately incomplete custom configurations.** The shipped configuration is complete, but a user-edited or older configuration that omits a range continues to report that metric as unranged instead of failing analysis. A coverage test checks the shipped defaults, not every possible custom file. Alternatives considered: making every range a required Pydantic field would be a breaking configuration migration and would prevent intentional opt-out.

3. **Use the existing direction-specific rule table for the four metrics.** Add low and high advice for backswing time, downswing time, hand speed, and swing-plane proxy. Hand-speed advice frames unusually high values around control or possible measurement quality rather than claiming speed itself is bad. Swing-plane advice explicitly says hand path and uses "flatter" or "steeper" rather than claiming the club shaft was measured. Alternatives considered: generic advice generated from metric labels would be less useful and could make unsafe biomechanical claims.

4. **Keep independent severity candidates and the current top-three cap.** Tempo and its component durations can all be outside their ranges, but each remains independently inspectable and eligible for coaching. Existing normalized ranking determines what is surfaced. Alternatives considered: suppressing timing components whenever tempo is flagged could hide whether the backswing, downswing, or both caused the ratio; adding fault groups would broaden this change into a coaching-engine redesign.

5. **Derive summary truth from metric verdicts, not from an empty tip list.** No tips can mean all metrics are good, an out-of-range direction has intentionally empty advice, values are unavailable, or candidates fell outside the top-three display. Visual and spoken summaries therefore use "no actionable tips" unless every finite ranged metric is explicitly in range. Alternatives considered: retaining the current message is shorter but factually wrong in these cases.

6. **Add inventory-level regression checks.** Tests compare the metric names produced by a complete synthetic sequence with default range coverage and verify advice for both directions of each newly ranged metric. Frontend checks cover band rendering from range payloads and summary wording. Alternatives considered: isolated tests for four literal keys would pass even if a future metric silently reintroduced the same gap.

7. **Allow club changes while armed and snapshot attribution per capture.** Keep the selector enabled; the runtime reads the selected club into a local value at the start of each trigger callback, and the capture writer stores that value in that session's metadata. Explain beside the control that a selection change applies to the next capture. This avoids stopping the listener between clubs without relabeling an existing capture. Alternatives considered: requiring disarm is safe but adds friction and is unnecessary because each trigger snapshots its own club; silently changing it without explanation would make the selected club's timing ambiguous.

8. **Gate checkpoint seeking on the existing tracking-quality verdict.** Keep computed checkpoint data available for diagnostics, but show an inline warning and disable seek controls when the reconstruction is explicitly unreliable. Leave controls enabled when quality is reliable or unavailable for backward compatibility. A nearest-proxy fallback can produce an ordered frame even when the expected geometric crossing never occurs, so presenting that frame as a usable P3 is misleading. Alternatives considered: substituting a time-fraction estimate would invent a position unsupported by pose data; suppressing video playback would unnecessarily block manual review.

## Risks / Trade-offs

- [Risk] Generic speed or plane targets may not fit every golfer. -> Mitigation: keep values editable, use club profiles, describe swing plane as a proxy, and choose conservative defaults.
- [Risk] Timing and tempo tips can overlap. -> Mitigation: make component advice explain the specific phase and retain severity ranking rather than always showing all related tips.
- [Risk] Existing sessions retain null ranges in stored analysis output. -> Mitigation: new and re-analysed sessions receive the new defaults; do not rewrite historical analysis silently.
- [Risk] Club-aware ranges can differ across points in a stats history. -> Mitigation: retain each point's backend verdict and avoid implying that point color comes from one chart-wide range; a richer variable-band history is outside this change.

## Migration Plan

1. Add documented default ranges and club-profile overrides without changing the configuration schema.
2. Add direction-specific rules and backend inventory/rule coverage tests.
3. Update UI summaries and verify range-driven session and stats presentation.
4. Re-analyse selected sessions to validate the four bands and tips with real rig data; tune configuration values rather than changing code.
5. Roll back by removing the four default ranges and rules; older and custom configurations remain parseable throughout.