const { app, BrowserWindow, dialog } = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");
const { spawn } = require("node:child_process");

const isDev = !app.isPackaged;
// Set by the desktop launcher (launch.ps1): load the built UI and manage the
// backend even though Electron isn't "packaged" (we run in-place from the repo
// so the Python venv, config.yaml and data/ all stay where they already live).
const appMode = process.env.GOLF_SIM_APP === "1";
const useDevServer = Boolean(process.env.VITE_DEV_SERVER_URL) || (isDev && !appMode);

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = 8765;
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

let backendProc = null;

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

function pingBackend() {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/api/capture/status`, (res) => {
      res.resume();
      resolve(res.statusCode >= 200 && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForBackend(timeoutMs = 40000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await pingBackend()) return true;
    await wait(500);
  }
  return false;
}

async function startBackend() {
  // Don't launch a second copy if one is already listening (e.g. a dev server
  // started from a terminal); the new process would just fail to bind the port.
  if (await pingBackend()) return true;

  const python = backendPython();
  if (!fs.existsSync(python)) {
    dialog.showErrorBox(
      "Golf Swing Analyzer",
      `Could not find the Python environment at:\n${python}\n\n` +
        "Set it up once with (in the backend folder):\n" +
        "  python -m venv .venv\n" +
        "  .venv\\Scripts\\pip install -e .",
    );
    return false;
  }

  backendProc = spawn(python, ["-m", "golf_sim.api.server"], {
    cwd: path.join(repoRoot(), "backend"),
    stdio: "ignore",
    windowsHide: true,
  });
  backendProc.on("exit", () => {
    backendProc = null;
  });

  const up = await waitForBackend();
  if (!up) {
    dialog.showErrorBox(
      "Golf Swing Analyzer",
      "The analysis backend did not start in time. Try launching again.",
    );
  }
  return up;
}

function stopBackend() {
  // Only kill a backend we started ourselves; leave an externally-run dev
  // server alone.
  if (backendProc && !backendProc.killed) {
    backendProc.kill();
    backendProc = null;
  }
}

function createWindow() {
  const win = new BrowserWindow({
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

  win.once("ready-to-show", () => win.show());

  if (useDevServer) {
    win.loadURL(process.env.VITE_DEV_SERVER_URL ?? "http://localhost:5173");
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(async () => {
  // Match the desktop shortcut's AppUserModelID so Windows shows our icon on
  // the taskbar and groups windows correctly.
  if (process.platform === "win32") {
    app.setAppUserModelId("com.gregbrown.golfswinganalyzer");
  }
  // In pure Vite dev mode the developer runs the backend themselves; otherwise
  // (packaged app or desktop-launcher app mode) we bring it up automatically.
  if (appMode || app.isPackaged) {
    await startBackend();
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopBackend);
