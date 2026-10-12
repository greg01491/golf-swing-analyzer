## Why

Four displayed swing metrics currently have no reference range, so their charts show no target band, they can never be marked out of range, and they can never produce coaching tips. This makes the metrics experience inconsistent and can falsely report that everything measured was in range.

## What Changes

- Add configurable reference ranges for `backswing_time_s`, `downswing_time_s`, `hand_speed_impact_ms`, and the body-pose-derived `swing_plane_deg` proxy so every displayed metric has an applicable target band.
- Make reference ranges club-aware where the expected value materially depends on club, while retaining shared ranges for club-independent timing metrics.
- Add direction-specific coaching advice for newly ranged metrics when a low or high result represents an actionable swing issue.
- Keep all out-of-range metrics eligible for the existing normalized-severity ranking and top-three tip limit.
- Show target bands consistently in session review and stats, and replace misleading "everything in range" feedback with wording that distinguishes no actionable tips from all metrics being in range.
- Allow the selected club to change while capture is armed, explain that each session records the club selected at trigger time, and apply a club change to the next capture only.
- Add regression coverage that keeps the computed metric set, configured ranges, displayed bands, and tip rules aligned.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `swing-analysis`: require applicable configurable ranges for every displayed metric and coaching advice for actionable out-of-range results, including the four currently unranged metrics.
- `desktop-review-ui`: require every ranged metric to show its target range/band and require result summaries to describe no actionable tips accurately.

## Impact

- Metric defaults and club profiles in `config/config.yaml`, plus the configuration UI that exposes those ranges.
- Backend metric comparison and coaching rules under `backend/src/golf_sim/analysis`, with focused metric and tip tests.
- Frontend session review, stats charts, spoken feedback, and associated types/tests under `frontend/src`.
- Armed club selection in the capture controls and capture API/runtime regression coverage.
- The hand-maintained project requirements, plan, and task documents must remain consistent with the OpenSpec artifacts.