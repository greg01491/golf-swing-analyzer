## 1. Pro Mode shared slow motion

- [x] 1.1 Move the existing slow-motion slider markup out of the single-camera-only
      block so it also renders inside the Pro Mode (`proMode`) branch, reusing the same
      `speed` state and `onChange` handler; verify by toggling Pro Mode and confirming
      the slider is visible in both modes
- [x] 1.2 Confirm the existing `speed`-driven `useEffect` (which sets `playbackRate` on
      every ref in `videoRefs.current`) covers both Pro Mode videos with no changes
      needed; verify by opening Pro Mode, dragging the slider, and observing both videos'
      `playbackRate` change together in devtools
- [x] 1.3 Manually verify: with Pro Mode on, press play, drag the slow-motion slider
      mid-playback, and confirm both camera views stay in sync and change speed together

## 2. Reference line overlay component

- [x] 2.1 Add a `SwingPlaneLine` component that renders an absolutely-positioned SVG
      `<line>` with two draggable circle-handle endpoints, sized against the same
      `videoSize` percentage-based positioning already used by the ball marker; verify
      by rendering it over a static test video and confirming the line follows window
      resizes
- [x] 2.2 Wire pointer/drag events on the endpoint handles to update line position state;
      verify by dragging each endpoint and confirming the line updates live with no lag
- [x] 2.3 Add a color picker control and a show/hide toggle per camera's line; verify by
      switching colors and toggling visibility and confirming the SVG updates
      accordingly

## 3. Persistence

- [x] 3.1 Persist each camera's line state (`x1, y1, x2, y2, color, visible`) to
      `localStorage` keyed as `swing-plane-line:<camera>`, following the existing
      `pro-mode` persistence pattern; verify by setting a line, reloading the app, and
      confirming it reappears in the same position and color
- [x] 3.2 Load persisted line state per camera on mount, defaulting to a sensible
      diagonal placement and hidden state when none is stored; verify by clearing
      `localStorage` and confirming a fresh session shows no line until the golfer adds
      one

## 4. Integration into SessionView

- [x] 4.1 Render one `SwingPlaneLine` per visible camera view in both Pro Mode's grid and
      the single-camera view's video frame; verify by checking both layouts show
      independent, correctly positioned overlays
- [x] 4.2 Add the add/remove-line and color controls to each camera panel's
      `video-controls` area, styled consistently with existing overlay/speed controls;
      verify visually against the existing control row styling
      (implemented as a small per-camera toolbar over each video, not the shared
      bottom bar, since each of the two camera views needs its own independent
      toggle/color control)
- [x] 4.3 Run `npm run lint` and `npm run build` in `frontend/` and confirm both succeed
      with no new errors
