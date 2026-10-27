# Calibration Investigation Checklist

Status updated 2026-10-26 for the installed rig. This tracks observed evidence and the next checks; it is not a calibration acceptance record.

## Resume Here: 2026-10-26

- The user says the 2026-10-26 11:49 capture is as good as they can get and is done with further board captures. Do not request another capture or restart the calibration wizard. The physical calibration work is paused; leave the rig unaccepted unless the user later opts to use a rigid, flat target.
- The rig moved after 2026-09-02 and has been stationary since approximately 2026-10-20. The active `Calib_rig.toml` is stale for the current placement. Its original SHA-256 is `e51037a4ae7d91cbaa3b4c85c4735b0e5fb12b4088d385ab15c1c60acc339f`.
- The user confirmed the floor bubble is centered and the golf mat is 35 mm thick. That height offset has not been applied or accepted; it cannot repair pixel reprojection or board edge-length failures.
- A real software bug was fixed on 2026-10-26: OpenCV checkerboard flags were passed in the `corners` positional slot. Both calls now use `flags=` and regression tests cover SB success and classic fallback. Full backend suite: 301 passed, one existing Starlette/httpx deprecation warning; Ruff and Black pass.
- Revalidating the original six-fit/four-held-out board split with the corrected detector gives fitted baseline 3.1351 m and held-out p95 4.03/4.91 px. This clears the existing 15 px geometry gate but does not accept ground reference.
- Refit intrinsics from existing saved clips pass independent held-out lens checks, but do not improve the new board's camera-2 planar fit. Do not replace intrinsics on this evidence.
- A corrected-corner fixed-intrinsics stereo refit, trained only on the six original fit placements, gives 0.99 px fit RMS and 3.1315 m baseline. Its independent board holdouts pass 15 px, but no ground-reference candidate passes strict limits.
- Exhaustive grid-order sweep finds no orientation that passes the ground gate. Best case: 0.90 degree normal repeatability, 2.32 px max reprojection (limit 2 px), and 7.85% square-edge error (limit 5%). No calibration or reference was activated; no threshold was relaxed.
- The new `2026-10-26_11-49-26_5510680e` capture has all corners detected in all 24 sampled frames (minimum spans 138 px camera 1 / 241 px camera 2). On the 2026-10-26 corrected-corner stereo diagnostic candidate, this whole placement passes the broad 15 px held-out gate: p95 3.86 px camera 1-to-2 and 2.43 px reverse, with positive depth. The reviewed frames show the checkerboard upright on the side of a box, so it adds relative-pose evidence but is not a ground-plane capture. Report: `%TEMP%\golf-board-20261026-114926\candidate-check.json`.
- Diagnostic artifacts are under `%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1`. The latest corrected-corner stereo report is `fixed-detector-stereo-refinement\stereo-refinement-report.json`; the exhaustive order sweep is `ground-orientation-sweep-20261026.json`.
- Next work, if resumed: investigate the strict geometry/edge-length mismatch offline. Only ask for physical data if a rigid, flat target becomes available; reserve acceptance captures from all fitting and threshold selection. Do not reuse the current paper captures as ground-reference acceptance evidence.

## Confirmed

- [x] Installed app is v0.1.19 and the local backend starts successfully.
- [x] Existing swing sessions, videos, TRC files, and metrics remain on disk.
- [x] A rejected candidate did not replace the active `Calib_rig.toml`.
- [x] The measured camera baseline is about 3.11 m; the candidate used 3.115 m. Keep this value unless a new tape measurement contradicts it.
- [x] Both cameras passed the live device check at the configured 120 fps mode.
- [x] Both cameras' saved lens clips independently pass held-out calibration. Camera 1: 0.58 px fit RMS, 0.37 px held-out median, 1.36 px p95 (16 clips, 144 fit views, 48 held-out views). Camera 2: 0.52 px fit RMS, 0.26 px held-out median, 0.64 px p95 (16 clips, 138 fit views, 48 held-out views).
- [x] The wizard accepted matching camera identity, dimensions, rotation, and frame-rate signatures across lens and position captures; it reached held-out camera-position validation.
- [x] Camera 1 held-out geometry passed: median 2.28 px, p95 9.39 px, 100% overall coverage, and 100% in every body region.
- [x] Camera 2's second candidate improved over the first: overall coverage 93.2% and p95 error 16.76 px, versus 87.3% and 18.09 px on the first candidate.
- [x] Camera 2 still fails held-out validation: pelvis coverage 62.6% (required 80%) and p95 error 16.76 px (limit 15 px). Its shoulder, head, and leg region coverage passed on the second candidate.
- [x] Pose detections for both camera-2 hip keypoints exceeded 0.6 confidence in all 360 saved frames of the second position shot. The pelvis failure is therefore not explained by missing 2D hip detections alone.
- [x] Sampled mid-swing frames show the full body in both views; obvious cropping is not the cause.
- [x] The second candidate's fit error is 0.21 px, baseline 3.115 m, camera 2 overall held-out coverage 93.2%, and camera 2 p95 16.76 px. The fit score passes; independent validation does not.
- [x] The second position shot is saved as `2026-10-20_14-47-24_69632f28`; its videos and metadata are intact.
- [x] Software synchronization uses one host monotonic clock and resamples both cameras onto the same time grid. The 362-vs-368 source-frame counts alone do not indicate a frame offset.
- [x] The brightness-jump detector selected frame 301 in both clips of clap-test session `2026-10-21_10-44-07_e9a8f665`. This does not verify a shared physical flash or alignment of a different swing recording.
- [x] v0.1.19 screenshot labels both Pro Mode players frame 178 at 1.483 s. Equal media timestamps do not establish equal camera exposure times or corresponding physical club positions.
- [x] Per-joint held-out residuals reproduced for position shot `2026-10-20_14-47-24_69632f28`. Camera 2 RHip is the main outlier: 2.2% within 15 px, median 19.36 px, p95 22.48 px. Camera 2 LHip is 87.8% within 15 px (p95 16.00 px), and Hip center is 97.8% within 15 px (p95 12.92 px).
- [x] The worst camera-2 pelvis residuals cluster near the end of the position clip (held-out frames 333-359). Sampled frames 349 and 359 show the golfer remains in view; there is no obvious full-body crop.
- [x] Camera-2 RHip detections at frames 333, 349, and 359 have confidence 0.83-0.93 and appear on the waistband in the source frames; no obvious left/right swap or single-view mislocalization is visible.
- [x] v0.1.19 screenshots show both camera players at frame 177 / 1.475 s and frame 178 / 1.483 s. In one screenshot the shared control readout is frame 179 / 1.492 s while both per-camera presented-frame callbacks still report 178; treat the callbacks as per-player presentation updates, not an atomic screen snapshot.
- [x] Clap-test camera-2 decoded frames 177 and 178 differ (mean absolute pixel difference 1.57 raw and 2.47 overlay). Pixel changes alone do not establish new exposures, club movement, or correct swing playback. The extracted comparison images show a clap, not the club swing reported by the user.
- [x] The active calibration remains legacy-unverified and has no accepted ground reference. The failed candidate is not active.
- [x] Read-only raw-video comparison of latest swing `2026-10-21_11-07-43_b1272505` reproduces different club phases at frame 178: DTL shaft down toward the floor, front-on shaft up-left from the hands. This is present before pose overlays or browser playback; whether this is the exact red-marked screenshot session is not yet confirmed.
- [x] Sequential decoding of that swing shows held front-on content: camera-2 golfer-region adjacent-frame mean absolute differences are 0 at 165->166, 166->167, and 167->168; at 169->174 they are at most 0.005, followed by a 15.443 jump at 175->176. This supports the user's report of advancing frame labels without corresponding visible motion.
- [x] That swing's metadata records camera-1 source effective rate 90.667 fps (273 source frames) and camera-2 70.667 fps (213 source frames), then resamples each to 360 frames at 120 fps. The encoded 120 fps is not a measurement of 120 unique camera exposures per second.
- [x] Capture-side fixes implemented locally: explicitly request MJPEG before resolution/FPS negotiation in both recording and camera checks; timestamp successful reads before rotation; save driver mode readbacks and per-output-frame source receipt offsets. Equal output timestamps no longer discard the source receipt evidence. These changes do not establish unique exposures or hardware synchronization.
- [x] All 256 backend tests pass, including regressions for transport negotiation order, rotation-independent receipt timestamps, held-frame provenance, and saved source receipt offsets.
- [x] Inventory of existing calibration captures on 2026-10-22 found 18 shots: 8 intrinsics clips per camera, with the board detected in all 6 sampled frames of every clip, plus 2 existing position clips. No new captures are needed to continue diagnosis.
- [x] Recomputed intrinsics from the saved board clips without writing a candidate. Camera 1: 0.58 px fit RMS, 0.37 px held-out median, 1.36 px p95. Camera 2: 0.52 px fit RMS, 0.26 px held-out median, 0.64 px p95.
- [x] Re-evaluated both saved position clips. Both have full 2D body-keypoint detections, but both fail held-out camera-2 pelvis geometry: the 14:26 clip has 60% pelvis coverage and 18.09 px p95; the 14:47 clip has 62.6% coverage and 16.76 px p95. Camera 1 passes both.
- [x] Per-joint residuals identify camera-2 RHip as the repeated outlier in both saved clips. In the 14:47 clip RHip median/p95 is 19.4/22.5 px and only 2% are within 15 px; LHip is 11.2/16.0 px and Hip center is 9.6/12.9 px.
- [x] Camera-1 left/right hip image separation on held-out frames has 17.1 px p10 in the 14:47 clip versus 40.0 px in the 14:26 clip. This supports possible DTL occlusion/ambiguity despite high model confidence; confidence alone does not prove the far hip was independently visible.
- [x] Read-only diagnostic fit excluding camera-1 RHip from fitting improved the 14:47 camera-2 overall p95 from 16.8 to 15.1 px, but RHip coverage only improved from 2% to 23% within 15 px. The earlier 14:26 clip worsened from 18.1 to 25.7 px p95. Excluding the joint is not an acceptable calibration fix; the result shows the fit is sensitive to this correspondence.
- [x] Read-only test of a symmetric RHip estimate (`RHip = 2 * Hip - LHip`) against held-out frames made camera-2 agreement worse in both saved clips. For the 14:47 clip, direct RHip median/p95 error was 16.4/19.4 px while the symmetric estimate was 28.5/37.6 px; the estimate had 0% of frames within 15 px. Do not add a synthetic opposite-hip marker or use this assumption for calibration.
- [x] Visual overlay of observed RHip, direct triangulated/projected RHip, and the mirrored estimate at held-out frames 333, 349 and 359 confirms that a mirrored point moves closer to the DTL observation but farther from the front-on observation. Per-frame direct-vs-mirrored errors (DTL/front-on px): frame 333 13.5/22.1 vs 10.3/30.5; frame 349 13.8/23.6 vs 11.0/29.1; frame 359 9.2/16.1 vs 4.2/27.3. The views disagree; symmetry does not resolve the measurement.
- [x] Literature review found occlusion-aware multi-view research uses per-joint reprojection evidence and treats limb-length symmetry as a soft optimization constraint, not a hard replacement for an unobserved hip. The cited fusion method uses per-view monocular 3D predictions and is not directly transferable to this 2D triangulation pipeline: https://arxiv.org/html/2408.15810v1.
- [x] All diagnostics used existing files in memory only; no candidate calibration was written or activated.
- [x] New swing `2026-10-22_11-29-22_37ec62c1` was inspected without changing calibration. Source delivery was 119.7 fps for camera_1 and 122.3 fps for camera_2, both resampled to 360 frames.
- [x] The new swing has valid phase anchors and all ten P-position entries; P1-P7 and P9-P10 are detected, while P8 is an estimate. This is not evidence that 3D metrics are validated.
- [x] The new swing's reconstruction validation fails for shoulder support (54%), head (0%), and legs (0%); pelvis support is 80.8%. Camera reprojection p95 is 35.2 px for camera_1 and 62.6 px for camera_2. Several metrics remain unavailable; backswing time, reverse spine, and swing-plane are estimates without validated target verdicts.
- [x] Per-marker residuals for the new swing shift the main outliers away from RHip: camera_1 Head p95 49.1 px and LElbow p95 48.6 px; camera_2 Head p95 120.2 px, LElbow p95 107.8 px, and LWrist p95 69.3 px. Inspect these observations before treating the black-jumper swing as metric-ready.
- [x] The new swing's RHip passes the per-camera support threshold (camera_1 81.6%, camera_2 98.3%); its 80.8% pelvis region passes narrowly. The current failure is instead shoulders 54%, head 0%, and legs 0%, with 3D Head support 0% in both cameras. Do not carry the earlier RHip-only diagnosis forward to this session.

## Still To Investigate

- [ ] Identify the exact swing session and raw/overlay sources shown in the user's red-marked screenshot. Compare adjacent recorded frames for the actual club: DTL below the waist versus front-on above the waist. Do not attribute this to viewpoint without checking motion correspondence.
- [ ] Verify physical event alignment and repeated exposures independently of output timestamps. The saved-video brightness detector has not established exposure synchronization.
- [ ] Determine the cause and magnitude of the raw swing's motion offset and held exposures. Inspect source-read timestamping, camera buffering, and source-to-grid mapping; do not apply a guessed constant frame shift or claim the nominal camera FPS proves unique exposures.
- [ ] Run the updated backend on a fresh two-camera motion recording and verify negotiated transport, source delivery cadence, held images, and physical motion correspondence. The installed v0.1.19 app does not contain these local changes; no hardware retest or new installer publication has been performed.
- [x] Reproduce per-held-out-frame/per-joint reprojection residuals; the failed-candidate report itself only contains aggregate region statistics.
- [ ] Manually adjudicate camera-1 and camera-2 RHip image locations against the source pixels across the held-out frames 270-359, focusing on the DTL overlap and the camera-2 residual. Determine whether either 2D point is anatomically misplaced or the residual is consistent with extrinsics/timing; confidence alone is not enough.
- [ ] Compare actual presented images during stepping and continuous playback against the correct stored swing frames. Matching frame/time labels cannot rule out delayed or repeated source images, incorrect source selection, or playback issues.
- [ ] Confirm both cameras stayed rigid and camera 2 is positioned perpendicular to camera 1, with the same focus/zoom and orientation used for the lens shots.
- [x] Recorded corrected-detector lens refits from saved clips: camera 1 RMS 0.600 px, held-out median/p95 0.447/1.388 px (143 fit, 48 held-out views); camera 2 RMS 0.541 px, held-out median/p95 0.262/0.679 px (139 fit, 48 held-out views). Both pass held-out lens validation; the refit does not improve the new board's camera-2 fit. Do not repeat lens captures or replace intrinsics based on current evidence.
- [ ] Only after residual analysis identifies a likely cause, decide whether a position retake or a physical camera adjustment is justified. Do not request another blind position shot. The wizard uses the latest position shot; do not clear all shots.
- [ ] Only after camera geometry passes, complete the two measured ground-reference captures and validate them independently.
- [ ] Keep the prior calibration and all historical swing outputs until a candidate passes; do not reprocess old sessions as a diagnostic.

## Current Decision

The corrected checkerboard detector is covered by regression tests, and all existing backend tests pass. The corrected six-fit/four-held-out relative-pose fit passes the 15 px cross-view gate, but the ground-reference solver still fails its stricter maximum reprojection and square-length gates. Lens refits pass their own held-out checks and do not improve the new board fit. The user is done taking captures with the tiled paper board. Do not ask for more paper-board captures, run the calibration wizard, change thresholds, change the active `Calib_rig.toml`, activate either diagnostic candidate, or apply the 35 mm floor-to-mat offset. Leave physical calibration and 3D metrics unvalidated. If the user resumes this work, first require access to a rigid, flat checkerboard target; otherwise continue only with offline diagnostics or unrelated software work. Never imply that this candidate or these sessions are accepted ground-reference evidence.

## Independent Geometry Audit: 2026-10-22

The subsequent crown experiment improved visual 2D tracking but did not pass saved-camera
geometry checks, including the controlled still-head clip. Median paired-crown errors
were about 26/33 px for still, 26/31 px for slow motion and 22/25 px for the swing
(DTL/face-on), with zero pairs passing both existing 15 px reprojection gates. This is
not evidence that the visually reviewed tracker must be wrong, nor permission to raise
the pixel threshold. Cross-view anatomical correspondence and saved relative camera
geometry remain unverified; native clip-time pairing does not verify exposure timing.

Recomputed lens fits use eight existing clips per camera, reserving the final two clips
before fitting. Both refits pass the existing held-out lens checks:

| Camera | Fit RMS | Held-Out Median | Held-Out P95 |
| --- | ---: | ---: | ---: |
| DTL | 0.58 px | 0.37 px | 1.36 px |
| Face-on | 0.52 px | 0.26 px | 0.64 px |

On those same board observations the active lens models give median/p95 0.40/1.45 px
and 0.27/0.55 px. The active models' original fit membership is not established here,
so that comparison is a consistency check, not a new independent acceptance claim.
Replacing only the lens matrices while retaining old relative camera pose would be an
unvalidated calibration change and was not performed.

Capture signatures match in identity, dimensions, rotations and requested fps, but all
examined focus/autofocus readbacks are unknown. The original lens shots did not record
a full checkerboard detected in both views, so they could not independently resolve the
two-camera transform. A later dedicated shared-board diagnostic is recorded below.

### Multi-Placement Relative-Pose Diagnostic: 2026-10-23

The assembled board measures 78.4 mm per square. A read-only diagnostic used six whole
placements for fitting and four separate whole placements for held-out validation. It
excluded `2026-10-23_14-37-06_2d96c43f`. The active lens intrinsics and measured 3.115 m
baseline were used to constrain scale and resolve checkerboard corner-order ambiguity;
no fitting placement was reused for held-out error.

The fitted baseline is 3.1353 m (0.65% from the measured baseline), with 0.75 deg p95
rotation spread across fit placements. Relative to the active transform, the fitted
rotation differs by 12.38 deg. Across 112 held-out corners in each direction,
camera-1-to-camera-2 reprojection has 2.41 px median / 4.05 px p95, and the reverse has
2.05 px median / 4.25 px p95. Every held-out corner has positive depth and lies within
the existing 15 px limit in both directions. Each held-out placement independently
passes that limit in both directions.

Scoring the active transform against the same held-out observations gives 80.79 px
median / 101.82 px p95 camera-1-to-camera-2 and 111.92 px median / 115.23 px p95 in
reverse; 0% of corners pass 15 px. Allowing each held-out placement either
baseline-compatible checkerboard ordering barely changes those errors. The current
active TOML was last modified 2026-09-02, before these 2026-10-23 captures. That file
timestamp, and the user confirms the cameras were moved after 2026-09-02 and have not
moved since approximately 2026-10-20. The failed body-keypoint position capture is
`2026-10-20_14-47-24_69632f28`; its rejection report was saved around 14:50 that day.
This likely describes the current physical setup, although the exact move time that day
is unknown. The rejected report contains validation metrics but no estimated extrinsics,
so its pose cannot be compared retrospectively with the board fit. Treat the September
active transform as stale for the current rig.

The saved 2026-10-20 candidate report explains that attempt's rejection: fit error was
0.208 px with 599 inliers from 5,563 correspondences, but held-out camera-2 p95 was
16.76 px and pelvis coverage was 62.6% (required 80%). Camera-2 overall coverage was
93.2%; camera 1 passed all reported regions (p95 9.39 px). Positive-depth coverage was
100%, so cheirality was not the blocker. Ground reference was unavailable. This was a
failed body-keypoint held-out validation, distinct from the later static-board pose
diagnostic.

This is strong evidence that one consistent relative transform explains these static
board placements. It is not physical acceptance: corner-order choices use the known
baseline and board reprojection, and the captures do not establish optical exposure
timing, board-to-floor orientation, camera rigidity/focus over time, or anatomical
metric accuracy. The fitted transform remains diagnostic-only and was not written to
or activated in any calibration bundle. The report, including sampled corner points and
SHA-256 hashes for all 20 source videos plus calibration/config/code inputs, is at
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\report.json`. The same-points
active-versus-fitted comparison, including the symmetry-aware active result, is in
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\active-comparison.json`.
The Pose2Sim-format diagnostic candidate and its report are under
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\relative-pose-candidate\`;
candidate SHA-256 is `0c6f7df8355d3a9157ac8b2880ec5f3b26163e8c15902f77ba36fd12403075a0`.
It inherits the active lens parameters, replaces only camera-2 relative extrinsics, and
is not an accepted bundle. It remains outside app data; no active pointer or calibration
was changed.

The two later captures, `2026-10-23_15-58-19_89e67aed` and
`2026-10-23_15-58-43_d2a53ea8`, show the full pattern in both views (minimum sampled
span 124 px) but the board is upright on/against a box, not flat on the hitting surface.
They cannot establish level or ground reference. Projection through the diagnostic
candidate also disagrees across views: best-order camera-1-to-camera-2 p95 is 50.9 and
43.6 px; reverse p95 is 9.2 and 10.1 px. These clips are not accepted as candidate
validation or ground-reference evidence; the asymmetric errors may reflect the board
setup or geometry and do not isolate the cause.

The flat captures `2026-10-23_16-07-36_48dc3c2b` and
`2026-10-23_16-07-53_f3aca23d` detect in both views at all three sampled frames, with
minimum span 124 px. Candidate projection p95 is 4.52/6.89 px and 4.33/6.78 px in the
two directions; baseline-supported estimates are 3.108 and 3.109 m. Their corresponding
corners differ by only 0.05 px median, so these are effectively repeated recordings of
one placement, not two independent ground-reference placements. Level and target-edge
orientation were not verified from the saved metadata.

The later `2026-10-23_16-11-58_509c7077` clip keeps the pattern visible to camera 2
(about 172 px span), but camera 1 detects no board at frames 80, 180 or 280. The
exhaustive checkerboard detector also fails in camera 1 for either grid orientation.
The board is strongly foreshortened near the lower part of that view, so this clip cannot
be paired geometry or reference evidence. The saved video hashes are in the temporary
`flat-capture-review` directory; original sessions are unchanged.

The 16:07 and 16:30 flat captures do provide two distinct placements. Their board-corner
centers shift about 53 px in camera 1 and 131 px in camera 2. The baseline-supported
pose estimates are 3.108 m and 3.105 m. Adding these two placements as whole held-out
captures, without changing the original six-fit/four-held-out split, yields 168 paired
held-out corners per direction: camera-1-to-camera-2 median/p95 2.53/4.62 px and the
reverse 3.26/6.57 px. All are within 15 px with positive depth. The 16:30 camera-1
placement uses high-accuracy checkerboard corners at its middle frame; ordinary
detection misses at least one later sampled frame. The user confirms the floor bubble is
centered. The 16:39 marked capture supplies the target/golfer orientation cues. This
supports the diagnostic relative pose, but not yet an accepted floor reference. The
combined report is
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\flat-capture-review\two-flat-placements-heldout.json`.

The marked 16:39 capture (`2026-10-23_16-39-31_d86dea45`) visibly places the glove on
the golfer side and the club along the target direction, outside the checker pattern.
Using frame 80, detected by the standard corner detector in both views, its candidate
cross-view p95 is 5.55/4.66 px. Rechecking the original four holdouts plus this marked
placement gives 140 points per direction, aggregate median/p95 2.66/4.93 px forward
and 2.49/4.60 px reverse; all remain under 15 px with positive depth. The user confirms
the floor bubble is centered and the paper lies flat. An in-memory ground-reference solve
using the 16:07 and 16:39 captures found 24 and 16 paired standard-detected frames,
respectively, but failed for all 32 first/last-origin and golfer-side combinations at
the existing 2 px per-camera board-reprojection limit. A second run using high-accuracy
corner detections also failed that same limit. Fixed-intrinsics stereo refinement on the
original six fitting placements had 0.98 px RMS and 3.131 m baseline, but did not resolve
the strict held-out board residual. Thus level and visible orientation are now supported;
camera-pose/board-planarity precision still blocks reference acceptance. No threshold was
changed and no reference or calibration was written/activated. The source-bound report is
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\flat-capture-review\16-39-31-marked-heldout.json`.

The standard detector's best consistent origin choice over the 40 paired frames gives
camera-1 reprojection median/p95/max 0.40/0.85/1.59 px and camera-2 0.60/1.29/2.48 px.
Reconstructed square-edge relative error is median/p95/max 2.16/5.64/7.97%, exceeding
the 5% limit in the tail. The printed-board assembly instructions require the paper tiles
to be taped to a rigid board. The paper-only setup does not satisfy that rigidity
requirement and may flex even when the floor bubble is centered. Earlier advice that a
rigid backing was optional was incorrect; do not treat these paper-only captures as a
ground-reference attempt that can be accepted by loosening thresholds.

### Detector API Correction: 2026-10-26

OpenCV 5.0 exposes both checkerboard functions as
`(image, patternSize[, corners[, flags]])`. The detector passed the intended flags in
the third positional argument, which binds the output-corner buffer instead of flags.
Both calls now use explicit `flags=` keywords. Regressions verify the SB success and
classic fallback branches; they failed before the fix and pass afterward. No detector
options, calibration tolerances, saved observations or active calibration were changed.

On `2026-10-26_09-03-02_01c58856`, both old and corrected calls detect all 24 sampled
frames in both views, but some camera-1 corners change by up to 13.48 px (camera 2:
0.38 px), after accounting for complete order reversal. Against the unchanged diagnostic
candidate, the corrected detector still fails strict ground checks on all 24 frames:
maximum per-view reprojection is 5.19/8.17 px; maximum reconstructed edge error is
24.72%, and maximum reconstructed deviation from the corner-defined plane is 13.98 mm.
These are reconstruction residuals, not independent measurements of physical paper warp.
High-accuracy detection was a separate experiment, not enabled by this API correction.

The original six-fit/four-held-out split has now been re-extracted with the corrected
detector. The refitted baseline is 3.1351 m. Its 112 held-out correspondences per
direction have median/p95 2.65/4.03 px forward and 2.09/4.91 px reverse; all pass the
existing 15 px limit with positive depth. The active transform still fails those same
holdouts badly. The diagnostic fit is effectively unchanged; it remains non-activatable.

For the 16:07 and 16:39 ground placements, the best consistent grid ordering across 45
paired frames has p95 reprojection 0.99/1.49 px but max 1.76/2.75 px; the strict per-frame
2 px check therefore fails in camera 2. Reconstructed edge error reaches 7.99%, above
the 5% limit. High-accuracy corners improve the camera-1 single-view fit, but camera 2
still reaches 3.31 px and cross-view/edge checks remain outside the ground-reference
limits. The failure is not fixed by a different grid symmetry. Reports are
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\revalidated-fixed-detector-20261026.json`,
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\fixed-detector-ground-reference-20261026.json`,
and `%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\fixed-detector-candidate\revalidated-report.json`.
Source-video hashes were checked. The mat thickness is 35 mm, but no floor-to-mat offset
has been applied or accepted because the ground solve did not pass.

The saved 2026-10-20 lens clips were independently refit after the detector fix, keeping
the original last-two-captures-per-camera held-out split. Camera 1: 143 fit views,
held-out median/p95 0.45/1.39 px. Camera 2: 139 fit views, held-out median/p95
0.26/0.68 px. On the new 9:03 board's 24 high-accuracy frames, single-view PnP maximum
residual is 0.80 px for camera 1 with either active or refit intrinsics; camera 2 is
3.31 px with active intrinsics and 5.73 px with refit intrinsics. The refit is not an
improvement for this observation, so do not replace lens parameters on this evidence.
This localizes the remaining strict ground failure away from an obvious lens-refit fix,
but cannot distinguish paper nonplanarity from a residual relative-pose/model issue. The
hash-bound comparison is `%TEMP%\golf-flat-board-20261026-15h6rsix\lens-model-comparison.json`.

A final diagnostic fixed-intrinsics `stereoCalibrate` fit used only the corrected-corner
midframes from the original six training placements. Fit RMS was 0.99 px and baseline
3.132 m; the four untouched board holdouts remained under the existing 15 px gate
(112 points each direction, p95 4.27/4.68 px). Yet the separate ground solver still
failed all tested orientation choices at its stricter per-corner 2 px gate. This refit
does not justify activation or solve the ground reference. Its diagnostic candidate and
report are in `%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\fixed-detector-stereo-refinement\`.

A full 256-combination row/column symmetry sweep over the two level placements found
no strict ground-reference pass. The best hypothesis has positive depth and repeat
normals within 0.90 degrees, but maximum reprojection is 2.32 px and reconstructed edge
error is 7.85% (limits 2 px and 5%). Thus orientation ambiguity is not the remaining
blocker; measured square consistency is. The sweep report is
`%TEMP%\golf-shared-board-geometry-20261023-5f7xy_e1\ground-orientation-sweep-20261026.json`.

The 2026-10-26 11:49 box-mounted checkerboard capture supplies one more whole-placement
holdout for relative geometry. Its frame-level detector/15 px check passes, but the board
is upright and cannot establish the ground plane. It does not cure the strict ground
reprojection or square-length failure, and it is not authority to activate a candidate.

### Next Evidence Needed

- Preserve this relative-pose result as a diagnostic candidate only. Do not replace the
  active transform based on static-board reprojection alone.
- The 2026-10-20 body-keypoint attempt likely used the current physical placement; its
  saved report lacks the candidate pose, so it cannot be compared directly with the
  later board fit.
- Independently record and quantify a shared optical event in both cameras; the board
  clips do not validate exposure synchronization or swing-time correspondence.
- Complete the measured ground/target reference, level and independent known-length
  checks from the hardware acceptance protocol, using whole captures withheld from any
  fit or model selection.
- Resolve the strict 2 px board reprojection failure with a camera-pose/board-planarity
  investigation using separated fitting and validation placements; do not relax the
  ground-reference gate or reuse the same boards for both fitting and acceptance.
- The user is done with paper-board capture attempts. Do not request or run more captures.
  If they later opt to resume physical acceptance, first obtain a genuinely rigid, flat
  measured target and reserve separate fitting, ground-reference, and acceptance data.
- Validate the resulting candidate on a dedicated independent acceptance capture and
  predeclared physical error limits before any activation or metric reanalysis.

No active calibration, session snapshot, videos, pose observations, annotations or metrics
were changed by this audit. Physical acceptance remains blocked until independent shared
geometry, timing, scale and reference evidence passes the existing protocol.
