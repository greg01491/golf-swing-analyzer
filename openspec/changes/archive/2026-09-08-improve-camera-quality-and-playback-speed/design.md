## Context

The proposal covers two existing boundaries: DirectShow camera configuration/readiness and the React multi-camera review player. Current camera opening sets resolution and nominal FPS but leaves image controls dependent on persistent driver state. Current readiness reporting measures resolution and frame rate, while the review UI must coordinate more than one HTML video element whose lifecycle is asynchronous.

## Goals / Non-Goals

**Goals:**

- Make camera image controls explicit, optional, and observable without breaking existing configurations.
- Keep readiness probes bounded and independent per camera.
- Record enough capture timing information to distinguish real samples from duplicated/resampled frames.
- Make playback-rate initialization and repeated changes safe across video loading and teardown in both multi-camera review and Pro view.
- Preserve synchronized multi-camera playback and existing public API shapes where possible.

**Non-Goals:**

- Computationally deblur already-recorded frames.
- Guarantee a camera supports a control that its driver does not expose.
- Replace the existing capture architecture or add a camera SDK dependency.
- Redesign the review UI or change the meaning of the 0%-100% playback control.

## Decisions

1. **Use optional per-camera control fields with conservative defaults.** Add nullable/optional exposure, gain, autofocus, and focus settings to the camera configuration model. `None` means leave the driver default unchanged. This preserves old config files and avoids forcing unsupported UVC controls. Alternatives considered: hardcoding one global exposure would not fit two cameras with different drivers; requiring every setting would make existing rigs fail validation.

2. **Apply controls through the existing OpenCV DirectShow seam and report read-back values.** Capture and diagnostic opening share a small control-application helper so runtime behavior and readiness checks agree. Each set operation records success and the value read back; unsupported controls become diagnostics rather than fatal errors. Alternatives considered: Windows-specific camera APIs would improve control coverage but add a dependency and diverge from the current OpenCV seam.

3. **Keep quality warnings advisory and measurable.** The readiness probe uses a bounded sample after warm-up to report timing and a lightweight sharpness/exposure signal. It warns about likely analysis degradation but does not reject a usable stream solely because the scene is soft or dark. Alternatives considered: a hard sharpness threshold would depend too heavily on scene texture and camera framing.

4. **Treat capture timing as measured data, not a nominal promise.** Preserve configured/requested values for reproducibility while recording measured frame timing/counts. Resampling remains available for synchronization, but metadata and diagnostics must make frame duplication or drops visible. Alternatives considered: silently changing the configured FPS would obscure the device behavior and break existing interpretation of clips.

5. **Make playback-rate updates idempotent and lifecycle-safe in every shared-view mode.** Store one bounded rate in React state, apply it to currently available videos, and reapply it from the video-ready path in both multi-camera review and Pro view. Guard refs and media operations so loading, unmounting, and missing overlay/raw elements cannot throw. Alternatives considered: rebuilding the player on each rate change risks losing position and causes the observed crash-prone lifecycle churn.

## Risks / Trade-offs

- [Risk] Camera drivers accept a setting but clamp or ignore it. -> Mitigation: report read-back values and warnings; keep settings optional.
- [Risk] Sharpness varies with scene content. -> Mitigation: use it as advisory evidence and expose the measurement context rather than a hard availability gate.
- [Risk] Actual capture timing differs between cameras. -> Mitigation: retain per-frame timestamps/counts and test resampling/synchronization behavior with synthetic sources.
- [Risk] A video element can disappear while a rate update is in flight. -> Mitigation: guard element refs, event handlers, and cleanup; test repeated updates during loading and unmount.
- [Risk] More configuration can confuse operators. -> Mitigation: provide safe defaults and surface unsupported controls clearly in readiness diagnostics.

## Migration Plan

1. Add optional configuration fields with defaults that preserve current behavior.
2. Implement shared camera-control/read-back logic, diagnostics, and metadata changes.
3. Add playback lifecycle guards and rate regression tests.
4. Run backend tests/lint and frontend build/lint; verify with the physical two-camera probe.
5. Rollback is configuration-compatible: remove or leave new fields unset and revert the implementation while retaining existing session files.
