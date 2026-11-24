## Why

The camera hardware can sustain the configured high frame rate, but capture currently relies on persistent driver defaults and does not expose or verify exposure, focus, gain, or delivered timing. That makes motion blur and camera quality difficult to diagnose or reproduce. Separately, the review UI can restore a session, but when it is opened in multi-camera or Pro view, a previously set slow-motion rate is not restored and changing the rate afterward crashes the system.

## What Changes

- Add user-editable per-camera image controls for exposure, gain, autofocus, and focus, with safe application and read-back diagnostics.
- Extend camera readiness information to report actual delivered timing and image-quality warnings, including conditions likely to make fast-swing footage unreliable.
- Preserve real capture timing in saved session metadata and avoid treating duplicated frames as genuine high-speed motion.
- Make review playback speed initialize from the selected session and remain safely changeable at runtime without invalid media or state transitions.
- Add focused backend and frontend regression tests for camera configuration and playback speed changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system-diagnostics`: camera readiness must support explicit image controls and report actual capture quality/timing rather than only requested resolution and FPS.
- `desktop-review-ui`: session playback speed must be restored consistently and changing slow motion must not crash or corrupt playback state.

## Impact

- Backend camera configuration, OpenCV DirectShow setup, capture metadata, and camera diagnostics under `backend/src/golf_sim/capture`, `config.py`, and `diagnostics`.
- Backend tests for camera sources, diagnostics, capture metadata, and session behavior.
- Frontend session playback state and video controls under `frontend/src`, plus frontend tests or build/lint coverage where the existing test setup supports them.
- Existing configuration files gain optional camera-control fields with backward-compatible defaults; no external service or dependency is required.
