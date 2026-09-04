## Context

`frontend/electron/main.js` currently defines no application menu (Electron's default
File/Edit/View/Window/Help menu is shown as-is) and has no preload/IPC bridge
(`preload.js` is an empty scaffold). Main-process user-facing messages already use
native `dialog.showErrorBox`/`showMessageBox`-style calls (see the backend-start-failure
dialog), which this feature follows rather than introducing a renderer-side UI surface.

electron-builder already generates `latest.yml` and the installer's `.blockmap`
alongside the `.exe` for the `nsis` target with no special configuration (confirmed by
inspecting a local build's `release/` output) — the gap is that `release.yml` currently
only uploads `frontend/release/*.exe` to the GitHub Release, and `package.json` has no
`build.publish` block, so the packaged app has no baked-in `app-update.yml` telling it
which repo to query. See proposal.md for why this is needed.

## Goals / Non-Goals

**Goals:**
- Let the golfer trigger an update check on demand from a menu item.
- Keep the implementation entirely in the main process: no new IPC channel, no new
  renderer UI, consistent with how the existing backend-start-failure dialog works.
- Reuse GitHub Releases as the update host — no new hosting/infra.

**Non-Goals:**
- No automatic/background update checks on a timer or on every launch — check is
  user-initiated only, for this first pass.
- No rebuilding of Electron's full default menu (Edit/View/Window items); only a
  minimal File menu (Check for Updates, Exit).
- No attempt to shrink update payload size (e.g. excluding unchanged model files from
  the diff) — accepted as a known trade-off per proposal.md.

## Decisions

**`electron-updater` with the GitHub provider, not a custom update checker.**
It already understands electron-builder's `latest.yml`/blockmap format and handles
download, signature/hash verification, and the differential-download logic. Writing a
custom checker would re-implement all of that for no benefit.
Alternative considered: a simple "fetch GitHub's latest release tag and compare
strings" checker that just opens the browser to the release page — rejected because
the proposal explicitly asks for in-app download + install, not just a version-check
link.

**All prompts as native dialogs in main.js, no preload/IPC changes.**
`autoUpdater` emits events (`update-available`, `update-downloaded`, `error`, etc.) that
main.js listens to directly and responds to with `dialog.showMessageBox`, mirroring the
existing `dialog.showErrorBox` pattern for backend-start failures. This avoids adding
the app's first IPC bridge for a single on/off feature.
Alternative considered: an in-app banner (matching `App.tsx`'s existing
`setup-banner`/backend-down banner styling) — more polished, but requires a new
`contextBridge` API and renderer state; deferred as a possible follow-up, not needed to
satisfy the proposal's scope.

**Minimal custom `Menu` replacing Electron's default, with only File > Check for
Updates and File > Exit.**
Electron shows a default menu automatically only when no menu is explicitly set; adding
`Menu.setApplicationMenu` with just these two items satisfies exactly what was asked
without deciding on placement/behavior for unrelated default items (Reload, DevTools,
Edit, Window) that nobody requested.

**`build.publish` configured, but `electron:build` keeps `--publish never`.**
CI already uploads release assets via `softprops/action-gh-release` in `release.yml`,
so electron-builder itself does not need to publish. Setting `build.publish` in
`package.json` is still required, independent of the CLI's `--publish` flag, so
electron-builder bakes the correct `app-update.yml` (provider: github, owner, repo)
into the packaged app for `autoUpdater` to read at runtime.

## Risks / Trade-offs

- [Risk] Update downloads are large (~740 MB today) since the bundled Python/ML backend
  diffs poorly between versions. -> Mitigation: proposal.md states this explicitly;
  the download happens in the background so the golfer isn't blocked while it happens.
- [Risk] `autoUpdater`'s GitHub provider only considers the latest published (non-draft,
  non-prerelease) release; a mistagged or draft release would not be seen. ->
  Mitigation: `release.yml`'s existing `softprops/action-gh-release` step already
  publishes a normal release on every version tag push, matching this expectation.
- [Risk] No IPC/renderer surface means the update UI is limited to native OS dialogs
  (no progress bar, no styling). -> Mitigation: acceptable for a first pass per
  Goals/Non-Goals; a richer in-app banner is a clear, separable follow-up.
