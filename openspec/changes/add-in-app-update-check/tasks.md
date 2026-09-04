## 1. Dependencies and build config

- [x] 1.1 Add `electron-updater` to `frontend/package.json` dependencies and verify
      `npm install` succeeds with no peer-dependency errors
- [x] 1.2 Add a `build.publish` block (`provider: "github"`, matching this repo's
      owner/name) to `frontend/package.json`; verify a local `npm run electron:build`
      still completes and the packaged app contains `resources/app-update.yml`
- [x] 1.3 Update `.github/workflows/release.yml` to upload `frontend/release/*.blockmap`
      and `frontend/release/latest.yml` alongside the existing `*.exe` glob; verify by
      inspecting the `files:` list in the workflow diff

## 2. Application menu

- [x] 2.1 Add a minimal `Menu.setApplicationMenu` in `frontend/electron/main.js` with a
      single **File** menu containing **Check for Updates** and **Exit**; verify by
      launching the packaged app and confirming the menu shows only these two items
      under File

## 3. Update check wiring

- [x] 3.1 Wire the **Check for Updates** menu item to call
      `autoUpdater.checkForUpdates()`, guarded so it only runs when `app.isPackaged`
      (never under `launch.ps1`/dev mode); verify by triggering it in dev mode and
      confirming nothing happens
- [x] 3.2 Handle `update-not-available` with a native dialog telling the golfer they
      have the latest version; verify by running it when already on the latest release
- [x] 3.3 Handle `update-available`/download progress by proceeding silently in the
      background (no dialog spam per progress tick); verify by triggering a check
      against a newer release and confirming only start/finish produce dialogs
- [x] 3.4 Handle `update-downloaded` with a native dialog offering "Restart now" (calls
      `autoUpdater.quitAndInstall()`) or "Later"; verify both button paths manually
- [x] 3.5 Handle `error` events with a native dialog reporting the failure (e.g. no
      network); verify by simulating a failed check (disconnect network or point at an
      unreachable feed)

## 4. Validation

- [x] 4.1 Run `npm run lint` and `npm run build` in `frontend/` and confirm both
      succeed with no new errors
- [ ] 4.2 Build a fresh installer locally (`npm run electron:build`) and manually verify
      the full flow end-to-end: launch the packaged app, use File > Check for Updates,
      and confirm each dialog path (up to date / downloaded+restart / error) behaves as
      specified
