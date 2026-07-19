import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CameraCheckResult, SystemCheckResult } from '../api'

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return <span className={`status-badge ${ok ? 'ok' : 'fail'}`}>{label}</span>
}

export default function SystemCheck() {
  const [system, setSystem] = useState<SystemCheckResult | null>(null)
  const [systemError, setSystemError] = useState<string | null>(null)
  const [cameras, setCameras] = useState<CameraCheckResult[] | null>(null)
  const [camerasError, setCamerasError] = useState<string | null>(null)
  const [checkingCameras, setCheckingCameras] = useState(false)

  useEffect(() => {
    api
      .diagnosticsSystem()
      .then(setSystem)
      .catch((e) => setSystemError(String(e)))
  }, [])

  const runCameraCheck = async () => {
    setCheckingCameras(true)
    setCamerasError(null)
    try {
      const result = await api.diagnosticsCameras()
      setCameras(result)
    } catch (e) {
      const msg = String(e)
      setCamerasError(
        msg.includes('409')
          ? 'disarm capture first (arm control in the header) -- the cameras are in use'
          : msg,
      )
    } finally {
      setCheckingCameras(false)
    }
  }

  return (
    <div className="wizard">
      <h2>System check</h2>
      <p className="muted">
        Verifies this PC and your cameras can keep up with real-time dual-camera capture and 3D
        pose analysis, before you rely on it for a real session.
      </p>

      <div className="panel">
        <h3>PC specs</h3>
        {systemError && <p className="error">{systemError}</p>}
        {system && (
          <>
            <div className="spec-row">
              <span>CPU cores</span>
              <strong>{system.cpu_cores}</strong>
            </div>
            <div className="spec-row">
              <span>RAM</span>
              <strong>{system.ram_gb} GB</strong>
            </div>
            <div className="spec-row">
              <span>free disk space</span>
              <strong>{system.free_disk_gb} GB</strong>
            </div>
            <div className="spec-row">
              <span>current CPU load</span>
              <strong>{system.cpu_load_pct.toFixed(0)}%</strong>
            </div>
            <div className="spec-row">
              <span>current RAM used</span>
              <strong>{system.ram_used_pct.toFixed(0)}%</strong>
            </div>
            <div className="spec-row">
              <span>overall</span>
              <StatusBadge
                ok={system.meets_recommended}
                label={
                  system.meets_recommended
                    ? 'meets recommended specs'
                    : system.meets_minimum
                      ? 'meets minimum, below recommended'
                      : 'below minimum specs'
                }
              />
            </div>
            {system.warnings.length > 0 && (
              <ul className="check-warnings">
                {system.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      <div className="panel">
        <h3>Camera specs</h3>
        <p className="muted">
          Opens each configured camera briefly and measures what it actually delivers (not just
          what the driver claims) -- disarm capture first, since this needs exclusive access.
        </p>
        <button onClick={runCameraCheck} disabled={checkingCameras}>
          {checkingCameras ? 'checking…' : 'run camera check'}
        </button>
        {camerasError && <p className="error">{camerasError}</p>}
        {cameras && (
          <div className="camera-check-results">
            {cameras.map((c) => (
              <div key={c.role} className="camera-check-result">
                <h4>
                  {c.role}
                  {c.opened && (
                    <StatusBadge
                      ok={c.meets_minimum}
                      label={c.meets_minimum ? 'ok' : 'below minimum'}
                    />
                  )}
                </h4>
                {c.error && <p className="error">{c.error}</p>}
                {c.opened && (
                  <>
                    <div className="spec-row">
                      <span>resolution</span>
                      <strong>
                        {c.actual_width}x{c.actual_height}
                      </strong>
                    </div>
                    <div className="spec-row">
                      <span>measured frame rate</span>
                      <strong>{c.measured_fps ?? '?'} fps</strong>
                    </div>
                    {c.warnings.length > 0 && (
                      <ul className="check-warnings">
                        {c.warnings.map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
