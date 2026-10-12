## 1. Tracking Quality Evidence

- [x] 1.1 Add optional address-to-impact motion assessment while preserving the whole-clip moving fraction; verify stationary lead-in and finish frames do not trigger the active-swing motion warning.
- [x] 1.2 Aggregate per-camera left/right wrist coverage at both the diagnostic 0.6 threshold and Pose2Sim's 0.3 triangulation cutoff; verify advisory-only visibility does not mark the swing unreliable and true cutoff gaps do.
- [x] 1.3 Keep impossible-scale warnings distinct from movement/visibility warnings and preserve the existing calibration recommendation only for scale evidence; verify scale regression tests remain valid.

## 2. Session Diagnostics

- [x] 2.1 Extend the quality payload and frontend types with swing-window movement, per-camera wrist visibility, and separate advisories; verify the session panel displays specific warning causes and measured coverage.
- [x] 2.2 Verify old quality payloads still render, advisory-only wrist confidence keeps P-position navigation enabled, hard failures disable it, and video playback remains available; run the frontend typecheck/build.

## 3. Validation

- [x] 3.1 Re-evaluate the latest 7-iron session in memory with updated workspace code, without overwriting saved analysis; verify 0.6-only wrist drops are advisories and below-0.3 coverage remains blocking.
- [x] 3.2 Run the full backend test suite, Ruff, Black, frontend lint/build, and strict OpenSpec validation; verify no regressions.