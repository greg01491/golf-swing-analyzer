## 1. Tracking Quality Evidence

- [x] 1.1 Add optional address-to-impact motion assessment while preserving the whole-clip moving fraction; verify stationary lead-in and finish frames do not trigger the active-swing motion warning.
- [x] 1.2 Aggregate per-camera left/right wrist confidence coverage over the active swing and produce camera/keypoint-specific warnings below the documented coverage threshold; verify missing detections and weak single-camera wrists are identified correctly.
- [x] 1.3 Keep impossible-scale warnings distinct from movement/visibility warnings and preserve the existing calibration recommendation only for scale evidence; verify scale regression tests remain valid.

## 2. Session Diagnostics

- [x] 2.1 Extend the quality payload and frontend types with swing-window movement and per-camera wrist visibility, preserving compatibility when older sessions omit the fields; verify the session panel displays specific warning causes and measured coverage.
- [x] 2.2 Verify existing sessions with old quality payloads still render, unreliable P-position gating still follows `reliable`, and video playback remains available; run the frontend typecheck/build.

## 3. Validation

- [x] 3.1 Re-evaluate the 7-iron session `2026-10-12_15-26-18_2640a56a` in memory with updated workspace code, without overwriting saved analysis; verify the warning distinguishes whole-clip pauses from active-swing motion and identifies low wrist confidence by camera.
- [x] 3.2 Run the full backend test suite, Ruff, Black, frontend lint/build, and strict OpenSpec validation; verify no regressions.