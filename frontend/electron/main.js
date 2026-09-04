const { app, BrowserWindow, dialog, Menu } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const isDev = !app.isPackaged;
// Set by the desktop launcher (launch.ps1): load the built UI even though
// Electron isn't "packaged" (we run in-place from the repo so the Python venv,
// config.yaml and data/ all stay where they already live).
const appMode = process.env.GOLF_SIM_APP === "1";
const useDevServer = Boolean(process.env.VITE_DEV_SERVER_URL) || (isDev && !appMode);

const backendUrl = "http://127.0.0.1:8765";
let backendProcess = null;
let backendLog = null;
let rendererLog = null;
let backendSpawnFailed = false;
let mainWindow = null;

function repoRoot() {
  // frontend/electron -> repo root
  return path.resolve(__dirname, "..", "..");
}

function backendPython() {
  const root = repoRoot();
  return process.platform === "win32"
    ? path.join(root, "backend", ".venv", "Scripts", "python.exe")
    : path.join(root, "backend", ".venv", "bin", "python");
}

function writeRendererLog(message) {
  rendererLog?.write(`${new Date().toISOString()} ${message}\n`);
}

process.on("uncaughtException", (error) => {
  writeRendererLog(`main uncaught exception: ${error.stack ?? error}`);
});
process.on("unhandledRejection", (reason) => {
  writeRendererLog(`main unhandled rejection: ${reason?.stack ?? reason}`);
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
}

app.on("second-instance", () => {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();
});

function healthCheck() {
  return new Promise((resolve) => {
    const request = http.get(`${backendUrl}/api/health`, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.setTimeout(1000, () => request.destroy());
    request.on("error", () => resolve(false));
  });
}

async function waitForBackend(timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await healthCheck()) return true;
    if (backendSpawnFailed) return false;
    if (backendProcess?.exitCode != null) return false;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

function runtimePaths() {
  const root = app.getPath("userData");
  const configDir = path.join(root, "config");
  const dataDir = path.join(root, "data");
  const calibrationDir = path.join(root, "calibration");
  const logsDir = path.join(root, "logs");
  for (const directory of [configDir, dataDir, calibrationDir, logsDir]) {
    fs.mkdirSync(directory, { recursive: true });
  }

  const configPath = path.join(configDir, "config.yaml");
  const defaultConfig = isDev
    ? path.resolve(__dirname, "../../config/config.yaml")
    : path.join(process.resourcesPath, "defaults", "config.yaml");
  if (!fs.existsSync(configPath)) fs.copyFileSync(defaultConfig, configPath);

  return {
    configPath,
    dataDir,
    calibrationDir,
    logPath: path.join(logsDir, "backend.log"),
    rendererLogPath: path.join(logsDir, "renderer.log"),
  };
}

async function startBackend() {
  const paths = runtimePaths();
  rendererLog = fs.createWriteStream(paths.rendererLogPath, { flags: "a" });
  rendererLog.write(`\n--- renderer start ${new Date().toISOString()} ---\n`);
  if (await healthCheck()) return { ready: true, logPath: paths.logPath };

  backendLog = fs.createWriteStream(paths.logPath, { flags: "a" });
  backendLog.write(`\n--- backend start ${new Date().toISOString()} ---\n`);

  const command = isDev
    ? {
        executable: process.env.GOLF_SIM_PYTHON ?? backendPython(),
        args: ["-m", "golf_sim.api.server"],
      }
    : {
        executable: path.join(process.resourcesPath, "backend", "golf-sim-backend.exe"),
        args: [],
      };

  backendProcess = spawn(command.executable, command.args, {
    cwd: isDev ? path.join(repoRoot(), "backend") : process.resourcesPath,
    env: {
      ...process.env,
      GOLF_SIM_CONFIG_PATH: paths.configPath,
      GOLF_SIM_DATA_DIR: paths.dataDir,
      GOLF_SIM_CALIBRATION_DIR: paths.calibrationDir,
      TORCH_HOME: isDev
        ? path.resolve(__dirname, "../../backend/runtime-models")
        : path.join(process.resourcesPath, "models", "rtmlib"),
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  backendProcess.stdout.pipe(backendLog, { end: false });
  backendProcess.stderr.pipe(backendLog, { end: false });
  backendProcess.on("error", (error) => {
    backendSpawnFailed = true;
    backendLog.write(`${error.stack ?? error}\n`);
  });

  return { ready: await waitForBackend(), logPath: paths.logPath };
}

function stopBackend() {
  if (backendProcess?.exitCode == null) backendProcess?.kill();
  backendProcess = null;
  backendLog?.end();
  backendLog = null;
  rendererLog?.end();
  rendererLog = null;
}

// Update checking only makes sense for an installed, packaged build -- under
// launch.ps1/dev mode there is no GitHub-published release to compare against.
let updateCheckInFlight = false;

function checkForUpdates() {
  if (!app.isPackaged) return;
  if (updateCheckInFlight) return;
  updateCheckInFlight = true;
  autoUpdater.checkForUpdates().catch((error) => {
    updateCheckInFlight = false;
    writeRendererLog(`update check failed to start: ${error?.stack ?? error}`);
    dialog.showMessageBox({
      type: "error",
      title: "Check for Updates",
      message: "Could not check for updates.",
      detail: String(error?.message ?? error),
    });
  });
}

autoUpdater.on("update-not-available", () => {
  updateCheckInFlight = false;
  dialog.showMessageBox({
    type: "info",
    title: "Check for Updates",
    message: "You already have the latest version.",
  });
});

autoUpdater.on("update-available", () => {
  // Download proceeds silently in the background; only the outcome (ready to
  // install, or error) is worth interrupting the golfer for.
  updateCheckInFlight = false;
});

autoUpdater.on("update-downloaded", async (info) => {
  const { response } = await dialog.showMessageBox({
    type: "info",
    title: "Update Ready",
    message: `Golf Swing Analyzer ${info.version} has been downloaded.`,
    detail: "Restart now to install it, or install it later on next launch.",
    buttons: ["Restart Now", "Later"],
    defaultId: 0,
    cancelId: 1,
  });
  if (response === 0) autoUpdater.quitAndInstall();
});

autoUpdater.on("error", (error) => {
  updateCheckInFlight = false;
  writeRendererLog(`autoUpdater error: ${error?.stack ?? error}`);
  dialog.showMessageBox({
    type: "error",
    title: "Check for Updates",
    message: "The update check failed.",
    detail: String(error?.message ?? error),
  });
});

function buildApplicationMenu() {
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: "File",
        submenu: [
          { label: "Check for Updates", click: checkForUpdates },
          { type: "separator" },
          { role: "quit", label: "Exit" },
        ],
      },
    ]),
  );
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    icon: path.join(__dirname, "..", "build", "icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  mainWindow.webContents.on("console-message", (_event, detailsOrLevel, message, line, sourceId) => {
    const details =
      typeof detailsOrLevel === "object"
        ? detailsOrLevel
        : { level: detailsOrLevel, message, lineNumber: line, sourceId };
    const level = details.level ?? 0;
    if (level < 2) return;
    writeRendererLog(
      `console[${level}] ${details.message} (${details.sourceId}:${details.lineNumber})`,
    );
  });
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    writeRendererLog(`renderer gone: ${JSON.stringify(details)}`);
  });
  mainWindow.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL) => {
      writeRendererLog(`load failed: ${errorCode} ${errorDescription} ${validatedURL}`);
    },
  );
  if (useDevServer) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL ?? "http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(async () => {
  // Match the desktop shortcut's AppUserModelID so Windows shows our icon on
  // the taskbar and groups windows correctly.
  if (process.platform === "win32") {
    app.setAppUserModelId("com.gregbrown.golfswinganalyzer");
  }

  const backend = await startBackend();
  if (!backend.ready) {
    dialog.showErrorBox(
      "Golf Swing Analyzer could not start",
      `The analysis service failed to start. No capture was attempted.\n\nDiagnostic log: ${backend.logPath ?? "unavailable"}`,
    );
    app.quit();
    return;
  }

  buildApplicationMenu();
  createWindow();
  app.on("activate", () => {
    if (!mainWindow) createWindow();
  });
});

app.on("before-quit", stopBackend);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
