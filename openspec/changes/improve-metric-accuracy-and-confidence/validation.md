# Metric Accuracy Evidence Record

Reviewed 2026-10-15. Original session files and metrics were read only. Temporary contact
sheets were generated outside the repository; personal recordings are not committed.

## Recorded Sources

All three sessions are under `%APPDATA%/golf-swing-analyzer/data/sessions/`. Each uses
`pose2sim/pose-3d/pose2sim_0-359_filt_butterworth.trc` and `camera_1.mp4` / `camera_2.mp4`.
Both videos report 360 frames at 120 fps. The same stored frame index was reviewed in
both views; this is nominal timeline alignment, not an independent camera-sync certificate.

| Session | Stored address / top / impact | Old shoulder / hip | New classification |
| --- | --- | --- | --- |
| `2026-10-12_19-27-18_9ecfcf82` | 45 / 114 / 182 | 0.19 / 175.62 degrees | Turns and head unavailable; 4 estimated and 15 unavailable entries |
| `2026-10-13_22-29-04_8d1094b4` | 46 / 143 / 178 | 128.29 / 30.69 degrees | Turns and head unavailable; 5 estimated and 14 unavailable entries |
| `2026-10-13_22-29-32_973f0e13` | 45 / 145 / 179 | 123.65 / 43.54 degrees | Turns and head unavailable; 5 estimated and 14 unavailable entries |

The new classifications above were evaluated in memory with recorded anchors explicitly
treated as estimated, current per-camera observation masks and actual session metadata.
No new valid turn was manufactured. SHA-256 checks confirmed every original metrics.json
was byte-for-byte unchanged after inspection.

## Observations And Measurement Limits

- Both views visibly show address, backswing and impact-region movement. The older
  recording's reconstructed Head, Neck and LShoulder remain held despite visible body
  movement. Its old near-zero shoulder value is therefore not supported by the video.
- The two newer stored top frames visibly have a raised backswing arm/club position,
  but this alone does not validate their old 124-128 degree 3D shoulder peaks.
- The lower-body candidate up vectors are approximately `[-0.24, 0.96, -0.17]`,
  `[-0.26, 0.95, -0.17]`, and `[-0.27, 0.95, -0.17]`. In each reconstruction the
  torso-to-pelvis relationship contradicts that candidate. Their reference status is
  unavailable, not a validated floor orientation.
- No selected session contains validated source-bound ground metadata. A checkerboard
  or camera baseline is not, on its own, evidence of a floor normal. The analysis does
  not silently borrow a current calibration for these old sessions.
- The views are oblique and some joints are occluded. A line drawn on either image is
  a projected 2D angle; neither view supplies exact 3D shoulder/hip rotation. The stored
  phase labels are also not independent certifications of true top or ball-contact time.
- Nominal frame spacing is 8.33 ms. Physical event and angular error bounds cannot be
  defensibly specified from this evidence; no invented +/-degree tolerance is claimed.

## Acceptance Status

Software verification: 220 backend tests and 3 frontend behavior tests pass. Ruff and
Black pass across backend source/tests; the frontend production build and lint gate
pass. Remaining baseline warnings are the Starlette/httpx deprecation, the existing
SwingPlaneLine fast-refresh export warning, and Vite's bundle-size advisory.
The frontend CI configuration now uses Node 24 and runs the behavior tests before
lint/build; the workflow structure was parsed locally, but no remote CI run or release
was triggered as part of this implementation.

Browser review at 1440x1000 and 390x844 verified confidence labels, readable reasons,
no pass/fail styling on unverified values, no horizontal metric overflow, and explicit
reanalysis. Estimated/unavailable states were exercised through temporary browser-only
response substitution; saved sessions were not changed. Pure frontend tests separately
cover complete-assessment speech and incompatible history/target separation.

Corrupt-data rejection is demonstrated on all three recorded examples. Deterministic
geometry tests independently cover the 19 definitions, signed/mirrored behavior,
coordinate transforms, time intervals, spikes, missing evidence, and strict serialization.
These tests do not certify real-world physical accuracy or the coaching bands.

**Physical accuracy acceptance remains blocked.** Completion needs independent known
reference orientation and usable supported landmarks, synchronized event review, and
defensible 3D measurement uncertainty. If the rig cannot supply that evidence, results
must remain estimated or unavailable. Do not archive this change or publish an accuracy
claim merely because automated tests pass. Camera/reconstruction workflow redesign is
outside this change and needs separate scope approval if required to obtain that evidence.

The separately approved `repair-rig-calibration-and-ground-reference` change now implements
the independent camera-validation and measured-reference workflow in source. Its software
checks pass, but its new rig acceptance capture is still pending. This does not close the
metric change's task 8.4 or certify corrected angles for the earlier recordings.