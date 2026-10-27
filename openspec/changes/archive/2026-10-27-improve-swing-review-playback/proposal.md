## Why

The face-on and down-the-line recordings currently render at different heights, making comparison awkward. Native playback controls cover the ball near the bottom of the recording, and the golfer cannot independently frame each camera for close inspection.

## What Changes

- Give Pro Mode camera images equal-width, equal-height viewing areas, fitting complete recordings without stretching or cropping at the default view.
- Replace over-video native transport controls with an icon-only play/pause button and a shared timeline beside the existing frame-step controls below the images.
- Preserve synchronized playback, looping, slow motion, checkpoint navigation, and camera-specific frame-rate handling.
- Add independent zoom, drag-to-pan, and Reset view controls for each review camera, outside the image area.
- Keep review markers, ball markers, and swing-plane reference lines aligned with the transformed recording.
- Apply the unobstructed transport and view controls consistently in single-camera review; keep the adjacent 3D skeleton behavior intact.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `desktop-review-ui`: Equal-sized comparison viewports, unobstructed shared transport, and independent camera framing with correctly aligned annotations.

## Impact

- Frontend review rendering and playback state in `frontend/src/components/SessionView.tsx`, layout in `frontend/src/App.css`, and existing playback helpers and tests.
- Swing-plane interaction in `frontend/src/components/SwingPlaneLine.tsx` and review-marker positioning must account for the image transform.
- Directly related review documentation and frontend validation. No capture, analysis, recording, or backend API changes are intended.
- Existing unrelated worktree edits must be preserved. The approved standalone HTML mock-up is the visual reference, not production code to copy wholesale.

## Non-goals

- Changing camera recordings, adding tracking or calibration behavior, linking the cameras' zoom/pan, or persisting view transforms across app restarts.
- Redesigning the rest of the application or moving the existing annotation toolbar as part of this transport change.
