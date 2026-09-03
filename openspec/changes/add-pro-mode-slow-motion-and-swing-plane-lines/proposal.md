## Why

Pro Mode's synced down-the-line/face-on playback has no way to slow the swing down, making
fast transitions (e.g. the top-of-backswing-to-impact move) hard to see clearly. Golfers
also have no way to mark a straight reference line on top of the video to visually check
whether the swing plane goes from steep to shallow through the backswing/downswing, since
the app tracks body pose only (no club/shaft tracking).

## What Changes

- Add a single slow-motion slider (0-100%, matching the existing single-camera view's
  control) to Pro Mode that sets the playback rate of both synced camera views together.
- Add a per-camera straight reference line overlay: the golfer can draw/position a
  straight line on each camera view independently, pick its color, toggle it on/off, and
  it stays fixed in screen space (no landmark or club tracking) so it can be compared by
  eye against the swing.
- Reference line position and color persist per camera the same way the Pro Mode
  preference already persists (so it doesn't need re-drawing every session).

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
