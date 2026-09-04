## Why

Getting a new build onto the golfer's laptop today means manually finding the right
GitHub Release, downloading the installer, and running it — easy to fetch a stale build
(as happened this session) or forget entirely. The app can check GitHub Releases itself
and let the golfer update on demand.

## What Changes

- Add a minimal application menu with a **File** menu containing **Check for Updates**
  and **Exit** (no other default Electron menu items are added at this point).
- Wire `electron-updater` (GitHub provider) into the Electron main process: checking,
  downloading, and prompting to restart-and-install, all via native dialogs — no new
  renderer/IPC surface.
- Configure `package.json`'s `build.publish` so the packaged app knows which GitHub
  repo to check, and extend `release.yml` to upload the `.blockmap` and `latest.yml`
  update-feed files alongside the installer `.exe` (currently only the `.exe` is
  uploaded).
- The update check only runs in the packaged app (never under `launch.ps1`/dev mode).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `desktop-review-ui`: gains a "Check for Updates" capability in the desktop shell.

## Impact

- Affected code: `frontend/electron/main.js` (menu + electron-updater wiring),
  `frontend/package.json` (new dependency, `build.publish` config),
  `.github/workflows/release.yml` (upload additional update-feed files).
- New dependency: `electron-updater`.
- No backend changes. No new IPC/preload surface — all prompts are native dialogs in
  the main process, matching the existing `dialog.showErrorBox` pattern already used
  for backend-start failures.
- Update payload size is realistically close to the full installer (~740 MB today)
  since the bundled Python/ML backend diffs poorly between versions; this is a known
  trade-off, not a defect.
