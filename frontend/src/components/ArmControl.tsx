import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CaptureStatus } from '../api'

export default function ArmControl({ onCapture }: { onCapture: () => void }) {
  const [status, setStatus] = useState<CaptureStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastSeen, setLastSeen] = useState<string | null>(null)

  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const s = await api.captureStatus()
        setStatus(s)
        if (s.last_session && s.last_session !== lastSeen) {
          setLastSeen(s.last_session)
          onCapture()
        }
      } catch {
        setStatus(null)
      }
    }, 500)
    return () => clearInterval(id)
  }, [lastSeen, onCapture])

  const level = status?.mic_level_db
  // map dB (-80..0) to a 0..100% bar
  const levelPct = level == null ? 0 : Math.max(0, Math.min(100, ((level + 80) / 80) * 100))

  const call = (fn: () => Promise<unknown>) => async () => {
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="arm-control">
      <div className="mic-meter" title={level == null ? 'mic off' : `${level.toFixed(1)} dB`}>
        <div className="mic-fill" style={{ width: `${levelPct}%` }} />
      </div>
      {status?.armed ? (
        <button className="armed" onClick={call(api.disarm)}>
          ● armed — disarm
        </button>
      ) : (
        <button onClick={call(api.arm)}>arm listening</button>
      )}
      <button onClick={call(api.trigger)}>manual capture</button>
      {status?.last_error && <span className="error">{status.last_error}</span>}
      {error && <span className="error">{error}</span>}
    </div>
  )
}
