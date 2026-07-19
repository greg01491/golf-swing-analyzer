export interface SessionSummary {
  id: string
  created_at: string | null
  cameras: string[]
  has_pose: boolean
  has_3d: boolean
  has_metrics: boolean
}

export interface MetricEntry {
  name: string
  value: number
  unit: string
  in_range: boolean | null
  range: { min: number; max: number } | null
}

export interface TipEntry {
  metric: string
  direction: string
  severity: number
  text: string
}

export interface PPosition {
  name: string
  label: string
  frame_index: number
  time_s: number
  ideal_frame: Record<string, [number, number, number]>
}

export interface SessionDetail {
  id: string
  metadata: Record<string, unknown>
  cameras: string[]
  // cameras that have a pose-overlay debug video (skeleton drawn on the
  // golfer) available for playback
  overlay_cameras?: string[]
  metrics: {
    phases?: { address_frame: number; top_frame: number; impact_frame: number }
    metrics: MetricEntry[]
    tips: TipEntry[]
    p_positions?: PPosition[]
  } | null
}

export interface Landmarks {
  source: string
  marker_names: string[]
  fps: number
  times: number[]
  frames: (number | null)[][][]
}

export interface CaptureStatus {
  running: boolean
  armed: boolean
  mic_level_db: number | null
  mic_error: string | null
  camera_health: Record<string, boolean>
  last_session: string | null
  last_error: string | null
}

export interface CalibrationInfo {
  exists: boolean
  file: string | null
  age_days: number | null
  stale: boolean
}

export interface CalibrationShot {
  id: string
  kind: 'intrinsics' | 'extrinsics'
  // which camera the board was held up to (wizard step 1 vs 2); null on
  // shots captured before this field existed
  for_camera?: string | null
  created_at?: string | null
  board_frames_detected: Record<string, number>
}

export interface CalibrationComputeStatus {
  state: 'idle' | 'running' | 'done' | 'error'
  stage?: string
  error?: string
  result?: {
    calib_file: string
    camera_1: { lens_views: number; lens_rms_px: number }
    camera_2: { lens_views: number; lens_rms_px: number }
    keypoint_correspondences: number
    mean_reprojection_error_px: number
    estimated_person_height_m: number | null
  }
}

export interface SystemCheckResult {
  cpu_cores: number
  ram_gb: number
  free_disk_gb: number
  cpu_load_pct: number
  ram_used_pct: number
  meets_minimum: boolean
  meets_recommended: boolean
  warnings: string[]
}

export interface CameraCheckResult {
  role: string
  name: string | null
  opened: boolean
  requested_width: number
  requested_height: number
  requested_fps: number
  actual_width: number | null
  actual_height: number | null
  measured_fps: number | null
  meets_minimum: boolean
  warnings: string[]
  error: string | null
}

// In dev, Vite proxies /api to the backend. In the packaged Electron app the
// renderer runs from file://, so relative URLs must become absolute.
const BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:8765' : ''

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export const api = {
  sessions: () => fetch(`${BASE}/api/sessions`).then((r) => json<SessionSummary[]>(r)),
  session: (id: string) =>
    fetch(`${BASE}/api/sessions/${id}`).then((r) => json<SessionDetail>(r)),
  landmarks: (id: string) =>
    fetch(`${BASE}/api/sessions/${id}/landmarks`).then((r) => json<Landmarks>(r)),
  // cb= busts Chromium's media cache, which is separate from the HTTP cache
  // and survives hard reloads: clips get replaced in place (H.264 migration,
  // overlay rewrites on re-processing), and it kept replaying a stale
  // pre-transcode copy that no longer decoded. Local server, ~1.5MB clips --
  // refetching per view is a non-issue.
  videoUrl: (id: string, camera: string, overlay = false) =>
    `${BASE}/api/sessions/${id}/video/${camera}?overlay=${overlay}&cb=${Date.now()}`,
  process: (id: string) =>
    fetch(`${BASE}/api/sessions/${id}/process`, { method: 'POST' }).then((r) =>
      json<{ status: string }>(r),
    ),
  processStatus: (id: string) =>
    fetch(`${BASE}/api/sessions/${id}/process`).then((r) => json<{ status: string }>(r)),
  config: () => fetch(`${BASE}/api/config`).then((r) => json<Record<string, unknown>>(r)),
  saveConfig: (config: Record<string, unknown>) =>
    fetch(`${BASE}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }).then((r) => json<{ status: string }>(r)),
  captureStatus: () => fetch(`${BASE}/api/capture/status`).then((r) => json<CaptureStatus>(r)),
  arm: () => fetch(`${BASE}/api/capture/arm`, { method: 'POST' }).then((r) => json<unknown>(r)),
  disarm: () =>
    fetch(`${BASE}/api/capture/disarm`, { method: 'POST' }).then((r) => json<unknown>(r)),
  trigger: () =>
    fetch(`${BASE}/api/capture/trigger`, { method: 'POST' }).then((r) => json<unknown>(r)),
  previewUrl: (camera: string) => `${BASE}/api/capture/preview/${camera}`,
  calibrationBoardUrl: () => `${BASE}/api/calibration/board.png`,
  calibrationInfo: () =>
    fetch(`${BASE}/api/calibration/info`).then((r) => json<CalibrationInfo>(r)),
  calibrationShots: () =>
    fetch(`${BASE}/api/calibration/shots`).then((r) => json<CalibrationShot[]>(r)),
  calibrationShotsClear: () =>
    fetch(`${BASE}/api/calibration/shots`, { method: 'DELETE' }).then((r) =>
      json<{ deleted: number }>(r),
    ),
  calibrationShot: (kind: 'intrinsics' | 'extrinsics', camera?: string) =>
    fetch(`${BASE}/api/calibration/shot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, camera }),
    }).then((r) => json<CalibrationShot>(r)),
  calibrationCompute: (cameraDistanceM: number) =>
    fetch(`${BASE}/api/calibration/compute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ camera_distance_m: cameraDistanceM }),
    }).then((r) => json<CalibrationComputeStatus>(r)),
  calibrationComputeStatus: () =>
    fetch(`${BASE}/api/calibration/compute`).then((r) => json<CalibrationComputeStatus>(r)),
  diagnosticsSystem: () =>
    fetch(`${BASE}/api/diagnostics/system`).then((r) => json<SystemCheckResult>(r)),
  diagnosticsCameras: () =>
    fetch(`${BASE}/api/diagnostics/cameras`).then((r) => json<CameraCheckResult[]>(r)),
}
