import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { CaptureStatus, ClubOption } from '../api'

interface Props {
  captureReady: boolean
  onCapture: (sessionId: string) => void
}

export default function ArmControl({ captureReady, onCapture }: Props) {
  const [status, setStatus] = useState<CaptureStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastSeen, setLastSeen] = useState<string | null>(null)
  const [clubs, setClubs] = useState<ClubOption[]>([])
  const [club, setClub] = useState('')
  const statusInitialized = useRef(false)

  useEffect(() => {
    api.clubs().then(setClubs).catch(() => setClubs([]))
  }, [])

  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const s = await api.captureStatus()
        setStatus(s)
        setClub((current) => current || s.selected_club || '')
        if (!statusInitialized.current) {
          statusInitialized.current = true
          setLastSeen(s.last_session)
        } else if (s.last_session && s.last_session !== lastSeen) {
          setLastSeen(s.last_session)
          onCapture(s.last_session)
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
      <select
        aria-label="Club"
        value={club}
        disabled={status?.armed}
        onChange={async (e) => {
          const selected = e.target.value
          setClub(selected)
          if (selected) await call(() => api.selectClub(selected))()
        }}
      >
        <option value="">select club…</option>
        {clubs.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
      {status?.armed ? (
        <button className="armed" onClick={call(api.disarm)}>
          ● armed — disarm
        </button>
      ) : (
        <button disabled={!club || !captureReady} onClick={call(api.arm)}>arm listening</button>
      )}
      <button disabled={!club || !captureReady} onClick={call(api.trigger)}>manual capture</button>
      {!captureReady && <span className="setup-required">setup required</span>}
      {status?.mic_error && <span className="error">mic: {status.mic_error}</span>}
      {status &&
        Object.entries(status.camera_health)
          .filter(([, ok]) => !ok)
          .map(([role]) => (
            <span key={role} className="error">
              {role} not responding
            </span>
          ))}
      {status?.last_error && <span className="error">{status.last_error}</span>}
      {error && <span className="error">{error}</span>}
    </div>
  )
}
