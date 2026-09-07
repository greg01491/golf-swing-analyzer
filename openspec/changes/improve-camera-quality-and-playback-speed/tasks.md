## 1. Camera Configuration And Control

- [x] 1.1 Add optional per-camera exposure, gain, autofocus, and focus fields with backward-compatible defaults in the Pydantic config model and `config/config.yaml`; verify existing configs still parse and new fields round-trip.
- [x] 1.2 Implement shared OpenCV/DirectShow control application and read-back reporting for runtime capture and readiness probes; verify with fake capture objects covering supported, rejected, and unsupported controls.
- [x] 1.3 Apply camera controls during `OpenCVCameraSource.open` without changing name-based device resolution or rotation behavior; verify the existing capture-source tests and a manual two-camera startup probe.

## 2. Diagnostics And Capture Metadata

- [x] 2.1 Extend camera readiness results with control read-back, measured timing, and advisory sharpness/exposure quality data; verify low-quality and unsupported-control warnings with deterministic fake frames.
- [x] 2.2 Make per-camera readiness workers fail independently and remain bounded when a device cannot open or stalls; verify the stalled-camera and mixed-success tests complete without hanging.
- [x] 2.3 Record requested versus delivered timing/frame-count information in session metadata and make resampling/duplication visible to downstream consumers; verify metadata and resampling tests with synthetic sources.
- [x] 2.4 Add or update API serialization and frontend types for the expanded camera readiness fields; verify backend API tests and the frontend typecheck/build.

## 3. Playback Speed Stability

- [x] 3.1 Trace the review UI's session playback-rate initialization, video refs, and rate-change handlers; identify the failing lifecycle path and add a focused regression test or test seam.
- [x] 3.2 Store a bounded playback rate with a 100% fallback, apply it to ready video elements, and reapply it when videos become ready without recreating media elements; verify session restore and repeated rate changes at 0%, 20%, and 100% in both multi-camera review and Pro view.
- [x] 3.3 Guard missing, loading, disposed, and overlay/raw video refs during synchronized playback updates; verify changing the rate before media readiness and during unmount does not throw or desynchronize available views.

## 4. Verification And Hardware Validation

- [x] 4.1 Run focused backend tests for camera source, diagnostics, capture metadata, and API behavior; verify with `pytest` and `ruff` for the touched modules.
- [x] 4.2 Run frontend typecheck, build, and lint checks plus the focused playback regression test; verify no new TypeScript or bundling errors.
- [x] 4.3 Run the physical two-camera readiness/capture probe with manual focus and lights on; verify actual delivered FPS, read-back controls, quality warnings, and a saved session with interpretable timing metadata.
