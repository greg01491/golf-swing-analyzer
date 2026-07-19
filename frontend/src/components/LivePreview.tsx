import { useEffect, useState } from 'react'
import { api } from '../api'

export default function LivePreview({ camera, label }: { camera: string; label: string }) {
  const [tick, setTick] = useState(0)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 400)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="preview-box">
      <div className="preview-label">{label}</div>
      {failed ? (
        <div className="preview-placeholder">no signal — is capture armed?</div>
      ) : (
        <img
          src={`${api.previewUrl(camera)}?t=${tick}`}
          onError={() => setFailed(true)}
          onLoad={() => setFailed(false)}
          alt={`${label} live preview`}
        />
      )}
    </div>
  )
}
