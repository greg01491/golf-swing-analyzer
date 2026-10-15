# Calibration Repair Verification

## Software Verification

- 249 backend tests pass against this checkout using explicit `pythonpath=backend/src`.
- Three frontend confidence/history tests pass; frontend production build succeeds.
- Ruff and Black pass across backend source/tests. Frontend lint passes with the existing
  SwingPlaneLine fast-refresh export warning. The existing Starlette/httpx deprecation and
  Vite bundle-size warning remain; no newly introduced lint findings remain.
- Strict OpenSpec validation passes.

Deterministic regressions cover known camera geometry, missing frame files, disjoint
temporal/clip partitions, bad held-out geometry hidden by good inliers, missing body-region
coverage, negative depth, lens correction, measured board scale/axes, accepted-bundle
integrity, cancelled/failed activation, capture-mode compatibility, explicit historical
archives, and exact filtered-TRC/reference/sidecar binding.

A direct test against the installed Pose2Sim implementation demonstrated a corrected-pixel
residual mismatch: native handling rejected an exact distorted-camera point, while the
guarded consistent-coordinate adapter recovered it to within 0.1 mm. The adapter restores
dependency functions after use and does not modify installed Pose2Sim files.

Ground-reference axes are validated against known synthetic board geometry, repeated
placements and measured lengths. The `(Y,Z,X)` TRC export is tested against the installed
dependency. Pre-fill triangulation rejection survives filtering through explicit masks;
finite held coordinates alone cannot authorize metric confidence.

## Browser Verification

The existing local preview at `http://127.0.0.1:5174/` was checked at 1440x1000 and
390x844 using temporary browser-only responses. No hardware startup/capture action was
sent to the real backend. Camera previews correctly remained unavailable without hardware.

Verified states:

- Accepted cameras with missing ground evidence, with capture/validation prerequisites enforced.
- Explicit level/target confirmations, per-camera FIRST/LAST marked-origin selection and golfer-side choice.
- Ground validation failure with a specific scale reason, retry eligibility and unchanged camera acceptance.
- Successful reference state that still states individual metric evidence is required.
- Incompatible 60-to-120 fps evidence and legacy provenance preventing measured-reference capture.
- Rejected candidate held-out results displayed separately from active camera acceptance.
- Readable controls and confirmation labels without horizontal overflow on mobile/desktop.

These mocked state checks validate software presentation, not successful physical board
capture or a certified camera/ground solution. Real annotated previews and optical sync
must still be exercised during the rig protocol.

## Physical Acceptance: Blocked

Task 7.4 remains open. Follow `docs/calibration-validation.md` with fixed documented camera
mode and lens settings, measured baseline/board lengths, independently checked board level,
marked target/side orientation, optical timing evidence, and independent angular measurements
with predeclared limits and defensible uncertainty. Keep acceptance captures separate from
fitting, candidate selection and threshold tuning.

No calibration candidate or ground reference was installed into the user's rig during
software work. Existing session data was not silently reprocessed or migrated. Neither this
change nor `improve-metric-accuracy-and-confidence` is ready to archive or claim physical
shoulder/hip certification merely because the software tests pass.