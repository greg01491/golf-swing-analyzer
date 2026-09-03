# Project Context

Golf Swing Analyzer — a desktop application for a home golf setup that records a swing
hands-free, reconstructs it in 3D from two cameras, and gives the golfer measured
feedback between shots.

The rig: two USB cameras (`camera_1` down-the-line, `camera_2` face-on) and a
microphone. The mic hears ball impact and triggers a capture; because both cameras are
continuously buffering, the saved clip covers the swing *before* the impact as well as
after it. The clips are run through pose estimation and triangulation into a 3D skeleton,
which is measured against club-aware reference ranges and turned into coaching tips.

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/` | Python package `golf_sim` (`backend/src/golf_sim`) plus `backend/tests` |
| `frontend/` | React + TypeScript renderer (`src/`) wrapped by Electron (`electron/`) |
| `config/` | `config.yaml` — every tunable parameter; `config/calibration/` holds the rig's `Calib*.toml` |
| `data/` | Runtime output: `data/sessions/<session_id>/` per swing, plus `sessions.db` |
| `docs/` | `setup.md`, `ball-tracking-plan.md` |
| `spec.md`, `plan.md`, `tasks.md` | The project's original spec → plan → tasks cycle (see `CONTRIBUTING.md`) |

## Backend modules

`golf_sim` is split into modules with deliberate data-contract boundaries so any one can
be swapped without touching the others. No module reaches into another's internals.

- `audio/` — mic input, level detection, trigger events. Emits triggers only; knows
  nothing about cameras or storage.
- `capture/` — camera enumeration, rolling buffers, windowed clip extraction, frame
  resampling, H.264 transcode, session writing.
- `pose/` — 2D pose estimation per camera, camera calibration (board, wizard, rig solve),
  3D triangulation.
- `analysis/` — swing phases, P-System checkpoints, metrics, ideal pose, tips, tracking
  quality. Pure functions of landmark data plus config.
- `storage/` — session persistence; the only module allowed to read/write `data/`.
- `api/` — FastAPI app (`api/server.py`) plus `CaptureRuntime`, the live capture/audio
  lifecycle holder.
- `diagnostics/` — PC and camera readiness checks.
- `config.py`, `trc.py` — Pydantic config models and loader; TRC (OpenSim marker
  trajectory) reader.

## Tech stack

**Backend** — Python ≥ 3.11. FastAPI + uvicorn, Pydantic v2, NumPy, OpenCV
(`opencv-python`), sounddevice (mic I/O), pygrabber (name-based camera selection on
Windows, because DirectShow indices shuffle), PyYAML + ruamel.yaml (comment-preserving
config writes), psutil (system check), imageio-ffmpeg (bundled ffmpeg for H.264
transcoding — OpenCV can only write mp4v, which Chromium will not decode). Pose
estimation and triangulation come from Pose2Sim (RTMPose, HALPE-26 keypoints), kept in a
`pose` optional extra so capture-only installs stay lean.

**Frontend** — React 19 + TypeScript, Vite, three.js for the 3D skeleton player, Electron
+ electron-builder for packaging. The renderer talks to the backend over HTTP on
`127.0.0.1:8765`; Electron does **not** spawn the backend, which is started separately.

## Conventions

- **Never hardcode a tunable.** Anything a user might want to change lives in
  `config/config.yaml`. Do not add a new tunable as a bare constant in code.
- **Python:** format with `black`, lint with `ruff` (line length 100, target py311, rule
  set `E,F,I,UP`). Type hints on public functions.
- **TypeScript:** lint with `oxlint`, format with Prettier.
- Comments explain *why*, especially where the code works around real hardware quirks
  (camera index shuffling, mp4v playback, Qt/matplotlib deadlocks off the main thread).
  Preserve that reasoning when editing.
- Keep `spec.md`, `plan.md` and `tasks.md` consistent with each other when scope changes;
  tick off `tasks.md` items as work completes.

## Running it

```bash
# Backend
cd backend
python -m venv .venv
./.venv/Scripts/activate      # source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"       # add ".[dev,pose]" for the pose/3D pipeline
python -m golf_sim.api.server # serves http://127.0.0.1:8765

# Frontend
cd frontend
npm install
npm run electron:dev          # Vite + Electron together
```

Useful dev entrypoints: `python -m golf_sim.audio.cli devices|listen|calibrate`,
`python -m golf_sim.capture.cli`, `python -m golf_sim.pose.cli full`,
`python -m golf_sim.analysis.cli --latest`.

## Testing and checks

```bash
cd backend && pytest -q            # test suite (backend/tests)
cd backend && ruff check src tests && black --check src tests
cd frontend && npm run lint        # oxlint
cd frontend && npm run build       # tsc -b && vite build
```

Tests inject synthetic camera and audio sources, so the whole capture pipeline and the
FastAPI app are testable without real hardware. Keep it that way: new hardware-touching
code should sit behind a source/service seam that a fake can replace.

## Domain notes

- **P-System (P1–P10)** — the ten checkpoints of a golf swing. Textbook definitions are
  club-based, but club tracking is out of scope, so they are approximated from body pose
  using documented geometric proxies. Say so wherever they surface.
- **Handedness** is configured (`analysis.golfer_handedness`), not inferred — body pose
  alone cannot tell a left- from a right-handed golfer.
- **Club affects the ranges, not the tips.** Reference ranges and the ideal pose are
  club-aware via `metrics.club_profiles` / `club_profile_mapping`; the tip text is shared.
- **Reconstruction quality varies a lot.** When the golfer cannot be tracked in both views
  the pose stack gap-fills, producing confidently wrong results. `analysis/quality.py`
  exists to flag that; never present low-confidence checkpoints as fact.
