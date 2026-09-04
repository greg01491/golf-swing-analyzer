## Why

Pro Mode's synced down-the-line/face-on playback has no way to slow the swing down, making
fast transitions (e.g. the top-of-backswing-to-impact move) hard to see clearly. Golfers
also have no way to mark a straight reference line on top of the video to visually check
whether the swing plane goes from steep to shallow through the backswing/downswing, since
the app tracks body pose only (no club/shaft tracking).

## What Changes

- Add a single slow-motion slider (0-100%, matching the existing single-camera view's
  control) to Pro Mode that sets the playback rate of both synced camera views together.
- Add up to five independent straight reference lines per camera view: the golfer can
  draw/position each line independently, choose its color, toggle it on/off, and remove
  it. Lines stay fixed in screen space (no landmark or club tracking) so backswing and
  downswing paths can be compared by eye.
- Persist each camera's line collection, including each line's position, color, and
  visibility, the same way the Pro Mode preference already persists.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `desktop-review-ui`: the "Multi-camera synchronised playback" requirement gains a
  shared slow-motion control; a new requirement covers the reference-line overlay.

## Impact

- Affected code: `frontend/src/components/SessionView.tsx` (Pro Mode playback grid,
  video-controls), `frontend/src/App.css` (overlay/line styling).
- No backend changes: the line is a client-side drawing aid, not derived from pose data.
- No new dependencies expected (plain SVG/canvas overlay positioned over the `<video>`
  elements already rendered).
