# Calibration Investigation Checklist

Status recorded 2026-10-21 for the installed rig. This tracks observed evidence and the next checks; it is not a calibration acceptance record.

## Confirmed

- [x] Installed app is v0.1.17 and the local backend starts successfully.
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
- [x] Shared flash/clap sync check on session `2026-10-21_10-44-07_e9a8f665`: both clips detect the event at frame 301, giving zero frame-level offset (one frame is 8.33 ms at 120 fps).
- [x] Per-joint held-out residuals reproduced for position shot `2026-10-20_14-47-24_69632f28`. Camera 2 RHip is the main outlier: 2.2% within 15 px, median 19.36 px, p95 22.48 px. Camera 2 LHip is 87.8% within 15 px (p95 16.00 px), and Hip center is 97.8% within 15 px (p95 12.92 px).
- [x] The worst camera-2 pelvis residuals cluster near the end of the position clip (held-out frames 333-359). Sampled frames 349 and 359 show the golfer remains in view; there is no obvious full-body crop.
- [x] Camera-2 RHip detections at frames 333, 349, and 359 have confidence 0.83-0.93 and appear on the waistband in the source frames; no obvious left/right swap or single-view mislocalization is visible.
- [x] The active calibration remains legacy-unverified and has no accepted ground reference. The failed candidate is not active.

## Still To Investigate

- [ ] If the reprojection issue remains after per-joint analysis, measure sub-frame camera exposure latency with an external timing method. The saved-video flash check only resolves alignment to the same 8.33 ms output frame.
- [x] Reproduce per-held-out-frame/per-joint reprojection residuals; the failed-candidate report itself only contains aggregate region statistics.
- [ ] Compare observed and candidate-projected camera-2 RHip coordinates on the worst frames to determine whether the remaining error is in 2D pose localization or the extrinsic camera geometry. A read-only reproduction using the workspace OpenCV 5 interpreter has not completed successfully yet.
- [ ] After installing v0.1.19, use frame stepping on sync-test session `2026-10-21_10-44-07_e9a8f665`; compare each camera's presented-frame/time readout. Matching readouts with different-looking poses indicate viewpoint differences; mismatched readouts identify playback drift.
- [ ] Confirm both cameras stayed rigid and camera 2 is positioned perpendicular to camera 1, with the same focus/zoom and orientation used for the lens shots.
- [ ] Record the held-out lens RMS and p95 values for each camera on the next report; do not repeat lens captures unless their own validation fails or camera optics/settings changed.
- [ ] Only after residual analysis identifies a likely cause, decide whether a position retake or a physical camera adjustment is justified. Do not request another blind position shot. The wizard uses the latest position shot; do not clear all shots.
- [ ] Only after camera geometry passes, complete the two measured ground-reference captures and validate them independently.
- [ ] Keep the prior calibration and all historical swing outputs until a candidate passes; do not reprocess old sessions as a diagnostic.

## Current Decision

Do not change the 3.115 m baseline, repeat lens captures, or loosen validation limits. Both lens models, hip confidence, full-body framing, software resampling, and frame-level shared-event sync have passed their checks. The per-joint report isolates camera 2 RHip late in the clip; next compare its observed and projected points to distinguish pose labeling/localization from camera geometry. Do not request another blind position swing.
