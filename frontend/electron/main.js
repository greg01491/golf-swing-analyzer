const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const isDev = !app.isPackaged;
const backendUrl = "http://127.0.0.1:8765";
let backendProcess = null;
let backendLog = null;
let backendSpawnFailed = false;
let mainWindow = null;

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
  };
}

async function startBackend() {
  if (await healthCheck()) return { ready: true, logPath: null };

  const paths = runtimePaths();
  backendLog = fs.createWriteStream(paths.logPath, { flags: "a" });
  backendLog.write(`\n--- backend start ${new Date().toISOString()} ---\n`);

  const command = isDev
    ? { executable: process.env.GOLF_SIM_PYTHON ?? "python", args: ["-m", "golf_sim.api.server"] }
    : {
        executable: path.join(process.resourcesPath, "backend", "golf-sim-backend.exe"),
        args: [],
      };

  backendProcess = spawn(command.executable, command.args, {
    cwd: isDev ? path.resolve(__dirname, "../../backend") : process.resourcesPath,
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
  if (backendProcess?.exitCode == null) backendProcess.kill();
  backendProcess = null;
  backendLog?.end();
  backendLog = null;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL ?? "http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  const backend = await startBackend();
  if (!backend.ready) {
    dialog.showErrorBox(
      "Golf Swing Analyzer could not start",
      `The analysis service failed to start. No capture was attempted.\n\nDiagnostic log: ${backend.logPath ?? "unavailable"}`,
    );
    app.quit();
    return;
  }

  createWindow();
  app.on("activate", () => {
    if (!mainWindow) createWindow();
  });
});

app.on("before-quit", stopBackend);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
