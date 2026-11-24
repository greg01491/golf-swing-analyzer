# React + TypeScript + Vite

## Swing review controls

- Pro Mode gives down-the-line and face-on recordings equally sized viewing areas.
  At 100%, the full recording is fitted without stretching or cropping; black padding
  accommodates different camera orientations. Narrow windows stack the panels.
- Play/pause (icon only), the shared timeline, frame stepping, elapsed time, and slow
  motion are below the images, not over the ball. Pro Mode controls both recordings
  together; single-camera review controls the active recording.
- Each camera has independent zoom in/out, a zoom percentage, drag-to-pan, Reset view,
  and full-screen controls. Zoom intentionally crops the magnified image within its
  viewing area. Drag even at 100% to reposition the image. Reset view recenters and
  fits only that camera, without changing playback.
- Focus an image and use arrow keys to pan, or Space to play/pause. The transport
  buttons and timeline also work with the keyboard. Dragging a reference-line handle
  edits that line without panning the image.
- Framing survives mode changes and skeleton-overlay toggles within the same swing.
  Opening another swing starts with centered, full-recording views. Markers and
  reference lines move with their recording, not with the surrounding controls.

## Development

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
