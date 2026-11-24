## 1. Angle calculations

- [x] 1.1 Add a pure TypeScript module for image-space line angles, finite segment intersections, acute intersection angles, and 5-degree snapping; verify it with unit tests for portrait and landscape aspect ratios, endpoint order, crossing and non-crossing segments, and snap boundaries.
- [x] 1.2 Keep the calculation tests in the existing frontend test workflow and verify they pass with `npm test` from `frontend`.

## 2. Image-anchored line display

- [x] 2.1 Map persisted normalized endpoints to the actual displayed video image in both normal and Pro views while retaining the existing local-storage data; verify a portrait clip's lines align in both layouts and review the expected one-time shift for lines previously drawn in letterbox space.
- [x] 2.2 Show lettered on-video line labels with each line's one-decimal image-space angle and a nearby 2D measurement caveat; verify adding or dragging a line updates its label and angle.

## 3. Line controls and comparison

- [x] 3.1 Move line-management controls into a panel below each video and show visible, lettered line entries with selection state; verify the panel works in normal and Pro review layouts without covering the footage.
- [x] 3.2 Add automatic acute-angle annotations for every visible finite segment intersection in the same camera view, identifying both lines and omitting non-crossing or parallel pairs; verify segment bounds, multiple crossings, and updates after line edits.
- [x] 3.3 Make line strokes selectable with a practical pointer hit area and keep endpoint handles independently draggable; verify clicking either a line or its panel entry selects the same line.
- [x] 3.4 Snap endpoint movement to 5-degree image-space increments only while Shift is held, keeping the opposite endpoint fixed; verify level and plumb snapping and unrestricted dragging without Shift.
- [x] 3.5 Add independent visibility controls and drag-to-reposition for line-angle labels and crossing-angle annotations, persisting visibility and image-relative positions per camera; verify automatic staggering, reset-to-automatic placement, and restoration across remounts.

## 4. Integration and validation

- [x] 4.1 Add responsive styling and accessible labels/targets for line controls, selectors, and snap state; verify the panel remains usable at the application's supported review widths and does not obstruct video controls.
- [x] 4.2 Run `npm test`, `npm run lint`, and `npm run build` from `frontend`, then manually verify line alignment, selection, angle readouts, and pair comparisons on both camera orientations.
