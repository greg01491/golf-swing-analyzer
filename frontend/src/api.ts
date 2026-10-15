export interface SessionSummary {
  id: string
  created_at: string | null
  // which section the swing is filed under in the sidebar (e.g. "My Swings"
  // or "Professional Swings"); friendly name shown instead of the timestamp
  group: string
  label: string | null
  cameras: string[]
  has_pose: boolean
  has_3d: boolean
  has_metrics: boolean
}

export interface ClubOption {
  id: string
  label: string
}

export interface MetricEntry {
  name: string
  // null when the metric couldn't be computed (e.g. a keypoint the pose model
  // lost in the relevant frames) -- the backend sanitizes NaN to null
  value: number | null
  unit: string
  in_range: boolean | null
  range: { min: number; max: number } | null
  status?: 'valid' | 'estimated' | 'unavailable' | 'legacy-unverified'
  definition_id?: string
  reasons?: string[]
}

export interface TipEntry {
  metric: string
  direction: string
  severity: number
  text: string
}

export interface StatsSession {
  id: string
  created_at: string | null
  metrics: MetricEntry[]
  analysis_version?: number | null
  club?: string | null
}

export interface PPosition {
  name: string
  label: string
  frame_index: number
  time_s: number
  available?: boolean
  detected?: boolean
  estimate_reason?: string | null
  unavailable_reason?: string | null
  ideal_frame: Record<string, [number, number, number]>
}

export interface TrackingQuality {
  moving_fraction: number
  hand_vertical_range_m: number
  reliable: boolean
  warnings: string[]
  advisories?: string[]
  swing_moving_fraction?: number | null
  camera_wrist_visibility?: Record<string, { LWrist: number; RWrist: number }> | null
  camera_wrist_triangulation_coverage?: Record<string, { LWrist: number; RWrist: number }> | null
}

export interface SessionDetail {
  id: string
  metadata: Record<string, unknown>
  cameras: string[]
  // cameras that have a pose-overlay debug video (skeleton drawn on the
  // golfer) available for playback
  overlay_cameras?: string[]
  metrics: {
    analysis_version?: number
    reference_frame?: { source: string; status: string; reasons: string[] }
    club?: string | null
    club_profile?: string | null
    phases?: { address_frame: number; top_frame: number; impact_frame: number }
    ball?: {
      detected: boolean
      source_camera?: string
      address_xy: [number, number] | null
      radius: number | null
      impact_frame: number | null
      impact_source: 'ball' | 'estimated'
    }
    tracking_quality?: TrackingQuality
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
  selected_club: string | null
}

export interface StartupStatus {
  ready: boolean
  pose_ready: boolean
  models_ready: boolean
  calibration_ready: boolean
  audio_ready: boolean
  audio_device: number | null
  messages: string[]
}

export interface CalibrationInfo {
  exists: boolean
  file: string | null
  age_days: number | null
  stale: boolean
  reprojection_error_px?: number | null
  broken?: boolean
  validation_status?: string
  validation?: CalibrationValidation | null
  bundle_id?: string | null
  ground_status?: string
  last_candidate?: {
    status: string
    error: string
    validation: CalibrationValidation | null
  } | null
  compatibility?: { status: string; reasons: string[] }
  reasons?: string[]
}

export interface CalibrationValidation {
  status: string
  reasons: string[]
  cameras: Record<
    string,
    {
      median_px: number | null
      p95_px: number | null
      coverage: number
      regions: Record<string, number>
    }
  >
}

export interface GroundReferenceStatus {
  state: 'idle' | 'running' | 'done' | 'error'
  error?: string
  result?: { ground_id: string; bundle_id: string }
}

export interface CalibrationShot {
  id: string
  kind: 'intrinsics' | 'extrinsics' | 'ground'
  bundle_id?: string | null
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
  validation?: CalibrationValidation
  result?: {
    calib_file: string
    camera_1: { lens_views: number; lens_rms_px: number }
    camera_2: { lens_views: number; lens_rms_px: number }
    keypoint_correspondences: number
    mean_reprojection_error_px: number
    estimated_person_height_m: number | null
    validation?: CalibrationValidation
    compatibility?: { status: string; reasons: string[] }
    ground_status?: string
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
  controls: Record<
    string,
    { requested: number | boolean; set_ok: boolean; readback: number | null }
  >
  sharpness: number | null
  brightness: number | null
  meets_minimum: boolean
  warnings: string[]
  error: string | null
}

// In dev, Vite proxies /api to the backend. In the packaged Electron app the
// renderer runs from file://, so relative URLs must become absolute.
const BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:8765' : ''

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text()
    console.error(`${res.url} failed: ${res.status} ${body}`)
    throw new Error(`${res.status} ${body}`)
  }
  return res.json()
}

export const api = {
  clubs: () => fetch(`${BASE}/api/clubs`).then((r) => json<ClubOption[]>(r)),
  startup: () => fetch(`${BASE}/api/startup`).then((r) => json<StartupStatus>(r)),
  sessions: () => fetch(`${BASE}/api/sessions`).then((r) => json<SessionSummary[]>(r)),
  stats: () => fetch(`${BASE}/api/stats`).then((r) => json<StatsSession[]>(r)),
  session: (id: string) => fetch(`${BASE}/api/sessions/${id}`).then((r) => json<SessionDetail>(r)),
  updateSession: (id: string, patch: { group?: string; label?: string }) =>
    fetch(`${BASE}/api/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).then((r) => json<{ id: string; group: string; label: string | null }>(r)),
  deleteVideos: (id: string) =>
    fetch(`${BASE}/api/sessions/${id}/media`, { method: 'DELETE' }).then((r) =>
      json<{ deleted: number; bytes_freed: number }>(r),
    ),
  deleteAllVideos: () =>
    fetch(`${BASE}/api/sessions/media`, { method: 'DELETE' }).then((r) =>
      json<{ deleted: number; bytes_freed: number; sessions_cleared: number }>(r),
    ),
  landmarks: (id: string) =>
    fetch(`${BASE}/api/sessions/${id}/landmarks`).then((r) => json<Landmarks>(r)),
  reanalyze: (id: string) =>
    fetch(`${BASE}/api/sessions/${id}/reanalyze`, { method: 'POST' }).then((r) =>
      json<{ status: string }>(r),
    ),
  // cb= busts Chromium's media cache, which is separate from the HTTP cache
  // and survives hard reloads: clips get replaced in place (H.264 migration,
  // overlay rewrites on re-processing), and it kept replaying a stale
  // pre-transcode copy that no longer decoded. Local server, ~1.5MB clips --
  // refetching per view is a non-issue.
  reconstruct: (id: string, bundleId: string) =>
    fetch(`${BASE}/api/sessions/${id}/reconstruct`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bundle_id: bundleId }),
    }).then((response) => json<{ status: string }>(response)),
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
    }).then((r) => json<{ status: string; note: string }>(r)),
  captureStatus: () => fetch(`${BASE}/api/capture/status`).then((r) => json<CaptureStatus>(r)),
  arm: () => fetch(`${BASE}/api/capture/arm`, { method: 'POST' }).then((r) => json<unknown>(r)),
  disarm: () =>
    fetch(`${BASE}/api/capture/disarm`, { method: 'POST' }).then((r) => json<unknown>(r)),
  trigger: () =>
    fetch(`${BASE}/api/capture/trigger`, { method: 'POST' }).then((r) => json<unknown>(r)),
  selectClub: (club: string) =>
    fetch(`${BASE}/api/capture/club`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ club }),
    }).then((r) => json<{ club: string }>(r)),
  previewUrl: (camera: string) => `${BASE}/api/capture/preview/${camera}`,
  previewStart: () =>
    fetch(`${BASE}/api/capture/preview/start`, { method: 'POST' }).then((r) =>
      json<{ running: boolean }>(r),
    ),
  calibrationBoardUrl: () => `${BASE}/api/calibration/board.png`,
  calibrationPreviewStart: () =>
    fetch(`${BASE}/api/calibration/preview/start`, { method: 'POST' }).then((r) =>
      json<{ running: boolean }>(r),
    ),
  calibrationPreviewStop: () =>
    fetch(`${BASE}/api/calibration/preview/stop`, { method: 'POST' }).then((r) =>
      json<{ running: boolean }>(r),
    ),
  calibrationInfo: () =>
    fetch(`${BASE}/api/calibration/info`).then((r) => json<CalibrationInfo>(r)),
  calibrationShots: () =>
    fetch(`${BASE}/api/calibration/shots`).then((r) => json<CalibrationShot[]>(r)),
  calibrationShotsClear: () =>
    fetch(`${BASE}/api/calibration/shots`, { method: 'DELETE' }).then((r) =>
      json<{ deleted: number }>(r),
    ),
  calibrationShot: (
    kind: 'intrinsics' | 'extrinsics' | 'ground',
    camera?: string,
    confirmations?: { level_confirmed: boolean; target_confirmed: boolean },
  ) =>
    fetch(`${BASE}/api/calibration/shot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, camera, ...confirmations }),
    }).then((r) => json<CalibrationShot>(r)),
  calibrationCompute: (cameraDistanceM: number) =>
    fetch(`${BASE}/api/calibration/compute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ camera_distance_m: cameraDistanceM }),
    }).then((r) => json<CalibrationComputeStatus>(r)),
  calibrationComputeStatus: () =>
    fetch(`${BASE}/api/calibration/compute`).then((r) => json<CalibrationComputeStatus>(r)),
  calibrationComputeCancel: () =>
    fetch(`${BASE}/api/calibration/compute`, { method: 'DELETE' }).then((response) =>
      json<CalibrationComputeStatus>(response),
    ),
  groundReference: (
    sessionIds: string[],
    origins: Record<string, Record<string, string>>,
    golferSide: number,
  ) =>
    fetch(`${BASE}/api/calibration/ground`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_ids: sessionIds, origins, golfer_side: golferSide }),
    }).then((response) => json<GroundReferenceStatus>(response)),
  groundReferenceStatus: () =>
    fetch(`${BASE}/api/calibration/ground`).then((response) =>
      json<GroundReferenceStatus>(response),
    ),
  groundReferenceCancel: () =>
    fetch(`${BASE}/api/calibration/ground`, { method: 'DELETE' }).then((response) =>
      json<GroundReferenceStatus>(response),
    ),
  groundPreviewUrl: (sessionId: string, camera: string) =>
    `${BASE}/api/calibration/shots/${sessionId}/ground-preview/${camera}`,
  diagnosticsSystem: () =>
    fetch(`${BASE}/api/diagnostics/system`).then((r) => json<SystemCheckResult>(r)),
  diagnosticsCameras: () =>
    fetch(`${BASE}/api/diagnostics/cameras`).then((r) => json<CameraCheckResult[]>(r)),
}
