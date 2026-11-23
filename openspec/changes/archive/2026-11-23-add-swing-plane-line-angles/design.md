## Context

See `proposal.md` for motivation and `specs/desktop-review-ui/spec.md` for the user-visible contract. Reference-line endpoints are currently persisted as normalized coordinates for each camera, and the SVG overlay is stretched to fill its container. In Pro mode, the video may be letterboxed inside that container, so overlay-box coordinates do not necessarily correspond to image coordinates.

## Goals / Non-Goals

**Goals:**
- Keep the angle calculation independent of React and test it with known portrait and landscape inputs.
- Keep each comparison local to its camera view and update the readout as either line changes.
- Keep controls out of the footage and make line selection practical with both pointer and panel interaction.

**Non-Goals:**
- Recover a true 3D line or compare lines across cameras.
- Add user-defined line names, a magnifier, keyboard nudging, frame stamps, angle arcs, or an all-pairs matrix.
- Change backend behavior, APIs, or configuration.

## Decisions

### Calculate in image pixels and anchor the overlay to the displayed image

Convert each endpoint from normalized image coordinates into the displayed image's pixel dimensions before computing an angle. Use the actual post-rotation dimensions for the selected clip. The absolute line angle is the acute angle from the image's horizontal axis, in the range 0 to 90 degrees; round only for display and retain full precision for comparisons. This avoids treating a non-square image as a square and keeps the readout consistent between normal and Pro modes.

The current local-storage format contains normalized endpoint coordinates. Keep those values when moving to image anchoring, without a migration; a line previously placed against Pro-mode letterboxing can shift once when rendered against the actual image. This avoids discarding existing user drawings or introducing a migration whose original image geometry may no longer be available.

### Annotate crossings automatically

Remove the pair selectors. For each pair of visible line segments in one camera view, calculate the segment intersection in image-pixel coordinates. Emit an annotation only when both segment parameters fall within their finite endpoints and the segments are not parallel or collinear. Compute the acute angle between their undirected image-space directions, identify the pair by its A-E labels, and place the angle annotation at the crossing. Recompute the annotation when either line moves or its visibility changes. This ties the measurement to the geometry the operator can see and avoids an extra comparison-selection step; parallel and non-crossing segments intentionally have no comparison annotation.

Draw a short arc at each crossing and a compact pair-and-angle label nearby. When multiple crossings are close together, offset their labels so the line identities and values remain readable. Continue to show each line's individual image-plane angle in its own on-video label and in the below-video list.

### Place line management below the video

Render line management below each video using the existing toolbar portal integration point. Identify lines by letters A-E as well as their distinct colors; show each line's current angle in its on-video label. Clicking the line's visible stroke or its panel row selects it. Use a sufficiently wide, transparent stroke hit target for line selection, while keeping endpoint handles separately draggable and large enough to use reliably.

During Shift-drag, keep the endpoint opposite the dragged endpoint fixed and quantize the resulting image-plane angle to 5-degree increments. This grid naturally includes level and plumb. Show a temporary or persistent visual cue while snapping is active so the constrained motion is understandable.

### Persist per-label visibility and placement

Store line-angle visibility by line index and crossing-angle visibility by pair key, alongside optional manually chosen label positions in normalized image coordinates in the existing per-camera local-storage value. Missing fields mean all available angles are visible and automatically placed, preserving compatibility with existing saved lines. Keep crossing visibility and positions keyed by the two line indices; when a line is removed, discard its pair settings and reindex the remaining settings. Dragging a label changes only its image-relative position. A reset control clears manual positions but does not change visibility. Automatically stagger all labels initially; do not auto-hide overlaps.

### Keep the measurement caveat close to the values

Place a short 2D-image caveat with the line-angle controls. The values describe projected directions in the selected camera image, not a calibrated world-space angle; do not label them as the application's 3D `swing_plane_deg` metric.

## Risks / Trade-offs

- [Old lines may shift when the overlay becomes image-anchored] -> Preserve stored coordinates and verify portrait Pro-mode alignment visually; call out the one-time shift in release notes if it is noticeable.
- [Crossing annotations can overlap when several pairs intersect close together] -> Offset nearby pair labels and keep each line's row as an unambiguous identity and angle reference.
- [Manually moved labels can obscure other annotations] -> Provide per-label visibility controls, retain manual positions per camera, and allow positions to be reset to automatic placement.
- [Angle measurements can look more precise than the footage supports] -> Limit display precision to one decimal place, use unrounded values only internally, and keep the 2D-image caveat beside the line list.
- [Line labels or hit targets may overlap on crowded drawings] -> Keep the line panel as the unambiguous selection fallback and visually test several close, crossing lines.
- [Snapping while dragging may feel surprising] -> Apply snapping only while Shift is held and show a clear snap cue.
- [Nearly vertical lines can make lean classification unstable] -> Treat exact vertical as a boundary and use the acute-angle wording for comparisons involving it.

## Migration Plan

No persisted-data migration is planned. Retain the existing per-camera line data and interpret normalized endpoints relative to the displayed image. Verify existing portrait drawings after the coordinate mapping changes; rollback is the prior renderer, which continues reading the same stored line data.
