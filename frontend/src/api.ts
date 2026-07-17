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
  last_session: string | null
  last_error: string | null
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export const api = {
  sessions: () => fetch('/api/sessions').then((r) => json<SessionSummary[]>(r)),
  session: (id: string) => fetch(`/api/sessions/${id}`).then((r) => json<SessionDetail>(r)),
  landmarks: (id: string) =>
    fetch(`/api/sessions/${id}/landmarks`).then((r) => json<Landmarks>(r)),
  videoUrl: (id: string, camera: string) => `/api/sessions/${id}/video/${camera}`,
  process: (id: string) =>
    fetch(`/api/sessions/${id}/process`, { method: 'POST' }).then((r) =>
      json<{ status: string }>(r),
    ),
  processStatus: (id: string) =>
    fetch(`/api/sessions/${id}/process`).then((r) => json<{ status: string }>(r)),
  config: () => fetch('/api/config').then((r) => json<Record<string, unknown>>(r)),
  saveConfig: (config: Record<string, unknown>) =>
    fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }).then((r) => json<{ status: string }>(r)),
  captureStatus: () => fetch('/api/capture/status').then((r) => json<CaptureStatus>(r)),
  arm: () => fetch('/api/capture/arm', { method: 'POST' }).then((r) => json<unknown>(r)),
  disarm: () => fetch('/api/capture/disarm', { method: 'POST' }).then((r) => json<unknown>(r)),
  trigger: () => fetch('/api/capture/trigger', { method: 'POST' }).then((r) => json<unknown>(r)),
}
