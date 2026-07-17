# Contributing / Conventions

This project follows the spec → plan → tasks cycle in [spec.md](spec.md), [plan.md](plan.md),
and [tasks.md](tasks.md). Check off `tasks.md` items as they're completed; if scope changes,
update `spec.md`/`plan.md` first so the three stay consistent.

## Module boundaries

The backend is split into independent modules with clear data-contract boundaries, so any one
can be swapped later (e.g. a mesh model instead of a skeleton, per spec.md NG1/NFR6) without
touching the others:

- `backend/src/golf_sim/audio/` — mic input, level detection, trigger events. Emits trigger
  events only; knows nothing about cameras or storage.
- `backend/src/golf_sim/capture/` — camera enumeration, rolling buffers, windowed clip
  extraction. Consumes trigger events (or a manual trigger); knows nothing about pose/analysis.
- `backend/src/golf_sim/pose/` — 2D pose estimation per camera + 3D triangulation. Consumes
  saved sessions; the pose model implementation is swappable (spec.md OQ2).
- `backend/src/golf_sim/analysis/` — metrics computation + tip generation from 3D landmark
  sequences. Pure functions of landmark data + config; no I/O beyond reading config.
- `backend/src/golf_sim/storage/` — session persistence (filesystem + SQLite). The only module
  allowed to read/write `data/`.
- `backend/src/golf_sim/api/` — FastAPI app exposing the above to the Electron frontend.

No module should reach into another's internals — go through its public functions/API only.

## Configuration

All tunable parameters (trigger threshold, delays, durations, camera settings, metric reference
ranges — see `spec.md` §7) live in [config/config.yaml](config/config.yaml). Never hardcode a
value there's already a config key for, and never add a new tunable parameter as a bare constant
in code — add it to `config.yaml` instead.

## Coding conventions

**Python (`backend/`)**
- Format with `black`, lint with `ruff` (`pip install -e ".[dev]"` then `ruff check src tests`
  and `black src tests`).
- Type hints on public functions.
- Tests live in `backend/tests/`, run with `pytest`.

**Frontend (`frontend/`)**
- React + TypeScript via Vite; Electron wraps it (`frontend/electron/`).
- Lint with `npm run lint` (oxlint), format with Prettier (`.prettierrc.json`).
- `npm run electron:dev` runs Vite + Electron together for local development.

## Local setup

```bash
# Backend
cd backend
python -m venv .venv
./.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest -q

# Frontend
cd frontend
npm install
npm run electron:dev
```
