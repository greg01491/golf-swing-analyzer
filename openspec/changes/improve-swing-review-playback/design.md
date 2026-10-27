## Context

See [proposal.md](proposal.md) for motivation and scope. The approved HTML mock-up establishes the visual arrangement, including independent camera framing and icon-only playback.

`SessionView.tsx` currently enables native transport on the first Pro Mode video and uses its media events to synchronize the remaining cameras. The existing external controls already provide frame stepping and slow motion. `App.css` provides equal grid columns but allows videos to select different intrinsic heights. Single-camera review also uses native transport.

Markers are positioned relative to the video/frame geometry. `SwingPlaneLine.tsx` stores per-camera normalized endpoints and derives drag coordinates from the overlay bounds. Replacing the frame geometry without updating these integrations would introduce annotation drift. Existing uncommitted changes in these files must be retained.

This design is required because viewport transforms cross playback rendering, annotation placement, and pointer interaction boundaries.

## Goals / Non-Goals

**Goals:**

- Reuse existing playback helpers and synchronization rather than introducing a second playback clock.
- Separate the clipped recording surface from fixed controls.
- Keep view transforms transient, camera-keyed, and independent from media state.
- Make coordinate conversion testable with deterministic geometry.

**Non-Goals:**

- Backend changes, new dependencies, a general-purpose video editor, or saving transforms across app restarts.
- Altering stored annotations as a side effect of framing.
- Changing full-screen behavior without preserving an explicit accessible entry point if existing review relies on it.

## Decisions

### 1. Equal outer viewports, contained inner recording surfaces

Use the existing Pro Mode grid with a common responsive viewport height. Calculate the contained recording rectangle from intrinsic media dimensions and viewport size. Center that surface at the default view, leaving black padding. Stack panels at the established narrow-window breakpoint.

Keep the video and image-space annotations together on a transformed surface inside an overflow-clipped viewport. Keep transport, zoom controls, and the annotation toolbar outside the transformed surface so they do not scale or pan away. The existing annotation toolbar need not be relocated beyond what is necessary to separate it from the image transform.

Alternative: cropping with `cover` would fill both panels but could hide the ball or club. Scaling only the video would leave annotations behind.

### 2. External transport uses existing media elements

Retain the first available camera as Pro Mode playback leader and the active camera in single-camera mode. Derive playing state, time, duration, and readiness from actual media events, including source changes. The shared play/pause control commands the relevant videos through the existing synchronization path; the timeline seeks through that same path. Preserve the existing frame-step helper and frame-rate source.

Do not treat a requested `play()` as success until playback starts. Surface rejected playback or media errors using the review UI's normal error presentation. Disable unusable controls during metadata loading; clamp seeks to valid media bounds. Ensure media listeners and sources remain stable, and do not seek the leader recursively from its own seek event.

Keep native controls disabled on the review videos. Reuse an existing full-screen action if one exists; otherwise provide a labeled explicit action if needed to preserve the functionality previously exposed by native transport.

Alternative: driving playback with a new animation timer would duplicate media state and risk drift; copying the mock-up's simulated timeline would not operate actual recordings.

### 3. Camera-keyed transient view state

Maintain scale and translation per session camera. Preserve state when switching review modes or overlay sources within a session, and reset it when the session changes. Reset view affects only the selected camera, never playback.

Zoom in/out controls and a percentage readout live below each camera. Use pointer capture for drag-to-pan, handle pointer cancellation, and support focused arrow-key panning without activating frame-step shortcuts. Pan bounds must keep the recording reachable; Reset view always restores the original contained rectangle.

The mock-up's 100%-400% range and 25 percentage-point increment are a reference, not new unconfigured tunables: check for reusable project settings first, and follow the project's configuration convention if adjustable bounds are introduced. Do not silently duplicate divergent limits between controls and geometry.

Alternative: linked framing was explicitly rejected because the two camera angles and aspect ratios require different compositions.

### 4. One coordinate model for annotations

Use the contained recording rectangle plus scale and translation consistently for marker projection and pointer-to-image conversion. Existing line storage remains compatible; inspect its normalized-coordinate convention and preserve endpoint meaning rather than silently rewriting local storage.

Line-handle pointer events must stop camera-pan initiation. Toolbar interactions must not initiate panning. Verify both drag directions and resizing while zoomed. Do not assume the viewport bounds equal the recorded image bounds when padding is present.

Alternative: ad hoc offset corrections for each overlay are fragile and duplicate geometry; share the smallest useful typed helper instead.

## Risks / Trade-offs

- Mixed aspect ratios necessarily produce padding at reset view -> preserve the full recording as explicitly approved.
- Annotation drift or reference-line migration regressions -> test forward/inverse geometry and existing stored endpoints, then inspect representative clips.
- Native controls supplied extra features such as full screen -> explicitly preserve relevant review actions outside the image.
- Media readiness, unequal durations, and play rejection can desynchronize UI -> derive status from media events, clamp seeks, and test loading/failure paths.
- Pointer handling can conflict with line dragging or range inputs -> isolate interaction surfaces, stop conflicting propagation, and test pointer cancellation and keyboard focus.
- Worktree contains substantial unrelated edits -> integrate the latest files, limit changes to playback and framing, and never revert existing work.

## Migration Plan

No recording, API, or database migration is required. Implement against the current frontend, validate with existing focused tests, lint, and build, then compare the running review against the approved mock-up with portrait/landscape clips. Update directly related review documentation and keep the original specification/plan/task documents consistent where their playback descriptions change. Rollback consists only of reverting this change's frontend and documentation edits while retaining other work.
