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

export interface SessionDetail {
  id: string
  metadata: Record<string, unknown>
  cameras: string[]
  metrics: {
    phases?: { address_frame: number; top_frame: number; impact_frame: number }
    metrics: MetricEntry[]
    tips: TipEntry[]
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
  videoUrl: (id: string, camera: string) => `${BASE}/api/sessions/${id}/video/${camera}`,
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
}
