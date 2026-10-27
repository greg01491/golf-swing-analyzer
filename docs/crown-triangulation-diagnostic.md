# Paired Crown Triangulation Diagnostic

This is a separate geometry-consistency experiment, not a new source of metric
support and not a replacement reconstruction. It consumes the fixed operator-seeded
independent-image comparison JSONs and the selected session's own calibration snapshot.
It never uses the current active rig calibration in place of that saved snapshot.

```powershell
python -m golf_sim.diagnostics.crown_triangulation `
  --session <original-session> `
  --first-track <camera-1-comparison.json> `
  --second-track <camera-2-comparison.json> `
  --output <new-separate-output-directory> `
  --config <config.yaml>
```

## Geometry And Missing Evidence

Native distorted pixels are undistorted into normalized camera coordinates before
OpenCV triangulation with the saved world-to-camera rotation and translation. Candidate
points are projected back through the original distortion model to compute per-camera
pixel errors. Positive depth and the existing configured tail-error limit are separate
gates. Fisheye calibration is refused rather than processed as a pinhole model.

Operator seed frames, rejected image tracks, missing observations and unequal-rate
unmatched times stay missing. Native frame/time identities are validated and joined as
exact rational clip times; no nearest-frame matching, interpolation or held positions
are inserted. Failing candidate geometry may be retained for diagnosis, but the separate
gate-passed coordinate remains null. Even gate-passed points are not metric evidence.

The report compares raw and tracked reprojection on the same available frame pairs.
It records hashes for calibration, capture metadata, comparisons and their input
videos/observations/seeds, checks those hashes again, and writes only a new output
directory outside all source-session and tracking directories.

## Timing And Acceptance

Equal clip time is an explicit diagnostic assumption, not proof of equal exposure time.
Resampling to nominal fps and host receipt timestamps do not establish optical timing.
The report preserves available receipt/count/rate metadata but does not optimize a lag
to obtain a lower reprojection score. Optical synchronization, camera calibration
acceptance, scale and ground reference remain independently unverified by this tool.

Every report remains `diagnostic_only: true`, `eligible_for_metrics: false` and
`exposure_synchronization_verified: false`. Synthetic tests establish distorted-camera
geometry, cheirality, missing-data behavior, unequal-rate pairing and source isolation;
they do not certify the physical rig.

The first three-case diagnostic had positive depth but no paired tracked observations
passing both 15-pixel reprojection gates, including the controlled still-head clip.
This separates improved 2D visual tracking from unresolved saved-geometry/correspondence
consistency. Personal per-frame results remain outside the repository. Independent
calibration/reference and optical-timing evidence are needed before claiming reliable
3D crown excursion.