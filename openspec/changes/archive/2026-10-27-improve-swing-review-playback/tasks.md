## 1. Recording geometry and framing state

- [x] 1.1 Inspect current playback, annotation, and configuration helpers against existing worktree edits; implement the smallest shared typed geometry needed for contained image fitting, zoom, bounded pan, and inverse pointer mapping. Verify portrait/landscape fit, transform round trips, finite bounds, and viewport resize with focused frontend unit tests.
- [x] 1.2 Add session-scoped, camera-keyed framing state with Reset view and retention across same-session mode/overlay changes. Follow existing configuration conventions for any new adjustable zoom limits. Verify camera independence, session reset, and same-session retention with focused tests.

## 2. Viewports and independent camera controls

- [x] 2.1 Render equal-sized Pro Mode viewports with contained recordings and clipped transformed image surfaces; retain responsive stacking and single-camera/3D layout. Verify identical side-by-side viewport dimensions, full images at reset, and no horizontal page overflow at desktop and narrow widths in the browser.
- [x] 2.2 Add zoom in/out, percentage, Reset view, and pointer-captured drag-to-pan for each camera, with controls outside the image and accessible keyboard framing. Verify independent zoom/pan, reset, drag cancellation, and arrow-key focus behavior without accidental frame stepping.
- [x] 2.3 Integrate ball/review markers and swing-plane reference lines with the shared image transform while preserving stored line endpoint meaning. Isolate handle dragging from camera panning. Verify alignment before and after zoom, pan, resize, overlay toggling, and reset, including dragging endpoints on both portrait and landscape recordings.

## 3. Shared external playback transport

- [x] 3.1 Replace native review transport with an accessible icon-only play/pause button, shared seek timeline, elapsed time, and existing frame-step/slow-motion controls below the images in Pro Mode and single-camera review. Preserve relevant full-screen access outside the image. Verify no native controls obscure either recording and all actions operate the active media elements.
- [x] 3.2 Wire readiness, duration, playing state, seeking, looping, and errors to media events through the existing synchronization path. Preserve checkpoint navigation and 3D synchronization. Verify play rejection, source changes, absent/invalid metadata, unequal clip durations, one-camera sessions, camera-specific frame rates, and repeated slow-motion changes without invalid time or a false playing state.

## 4. Documentation and integrated validation

- [x] 4.1 Update directly related review usage documentation and relevant original spec/plan/task descriptions without changing unrelated work. Verify documentation explains uncropped reset view, independent framing, shared transport, keyboard interactions, and reset behavior consistently.
- [x] 4.2 Run focused playback/framing frontend tests, frontend lint, and the production TypeScript/Vite build; inspect the final diff to ensure existing worktree edits are retained. Verify all checks pass or identify unrelated baseline failures explicitly.
- [x] 4.3 Compare the running review with the approved mock-up using representative landscape/portrait clips. Verify equal viewports, an unobstructed ball, synchronized play/pause/seek/frame-step/loop/slow-motion, independent framing, annotation alignment and editing, checkpoint seeking, single-camera/3D review, and narrow-window controls; record the validation outcome.

### Validation outcome (2026-10-27)

- All 18 frontend tests and 302 backend tests passed. Frontend lint/build and backend Ruff/Black checks passed; existing Fast Refresh and bundle-size warnings remain.
- Saved 1280x720 and 720x1280 recordings render in identical 559.8x480 viewports at the tested desktop width. Tested 700px and 390px windows without horizontal page overflow.
- Browser verified synchronized transport, exact 120fps frame steps, repeated slow-motion changes, looping, checkpoint seeking, single-camera/3D review, and independent framing retained across mode/source changes and reset on session change.
- Both cameras' line handles remain editable without panning; zoomed pointer-to-image mapping, keyboard panning, pointer cancellation, reset, full screen, and Space play/pause passed.
- The ball marker's normalized location remained stable through zoom and resize. Single-camera sessions, unequal/invalid durations, and explicit playback rejection were checked with temporary browser-only fixtures; real API behavior was restored afterward.
- Existing worktree edits were retained and included in the release at the user's explicit request.
