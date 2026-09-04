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

- [x] 2.1 Extend `SwingPlaneLine` to manage up to five independent line records per
      camera and render one absolutely-positioned SVG `<line>` with two draggable
      circle-handle endpoints for each line; verify by rendering five lines and
      confirming they remain aligned over resize
- [x] 2.2 Wire pointer/drag events to update the selected line only, and add controls to
      select, add, and remove lines; verify by editing one of five lines and confirming
      the other four remain unchanged and a sixth cannot be added
- [x] 2.3 Add a color picker and show/hide toggle for the selected line; verify by
      changing one line's color/visibility and confirming the other lines are unaffected

## 3. Persistence

- [x] 3.1 Persist each camera's line collection (`lines[]` plus selected line) to
      `localStorage` keyed as `swing-plane-lines:<camera>`, following the existing
      `pro-mode` persistence pattern; verify by setting multiple lines, reloading the
      app, and confirming all reappear in the same positions, colors, and order
- [x] 3.2 Load persisted line collections per camera on mount, defaulting to an empty
      collection when none is stored; verify by clearing `localStorage` and confirming
      a fresh session shows no line until the golfer adds one

## 4. Integration into SessionView

- [x] 4.1 Render up to five `SwingPlaneLine` overlays per visible camera view in both Pro
      Mode's grid and the single-camera view's video frame; verify by checking both
      layouts show independent, correctly positioned collections
- [x] 4.2 Add the add/remove/select-line, color, and visibility controls to each camera
      panel's
      `video-controls` area, styled consistently with existing overlay/speed controls;
      verify visually against the existing control row styling
      (implemented as a small per-camera toolbar over each video, not the shared
      bottom bar, since each of the two camera views needs its own independent
      toggle/color control)
- [x] 4.3 Run `npm run lint` and `npm run build` in `frontend/` and confirm both succeed
      with no new errors
