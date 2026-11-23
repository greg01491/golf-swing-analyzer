## Why

The swing-plane reference lines currently have no angle readout, and comparing lines requires estimating their difference by eye. A clear, camera-specific angle comparison will make the existing drawing tool more useful while explaining that it measures a 2D image, not the golfer's true 3D swing plane.

## What Changes

- Show each reference line's angle and automatically show the acute angle where visible reference-line segments intersect.
- Move line controls into a panel below the video, with visible line identities and labels on the video.
- Let operators independently hide or drag angle labels; retain their per-camera choices across sessions.
- Improve line selection and support Shift-drag snapping to 5-degree increments, including level and plumb.
- Keep the angle interpretation and comparison scoped to the camera image; do not imply a 3D measurement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `desktop-review-ui`: add requirements for line angle readouts, pairwise comparison, and improved reference-line interaction.

## Impact

- Frontend reference-line overlay and controls in `frontend/src/components/SwingPlaneLine.tsx`, with integration in `SessionView.tsx` and related styles.
- A pure TypeScript angle-calculation module and focused frontend tests.
- No backend, API, or configuration changes.
