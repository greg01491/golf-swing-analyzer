import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CalibrationInfo, CalibrationShot, GroundReferenceStatus } from '../api'
import LivePreview from './LivePreview'

export default function GroundReferencePanel({
  info,
  shots,
  onChanged,
}: {
  info: CalibrationInfo
  shots: CalibrationShot[]
  onChanged: () => void
}) {
  const [level, setLevel] = useState(false)
  const [target, setTarget] = useState(false)
  const [side, setSide] = useState('')
  const [origins, setOrigins] = useState<Record<string, Record<string, string>>>({})
  const [status, setStatus] = useState<GroundReferenceStatus>({ state: 'idle' })
  const [capturing, setCapturing] = useState(false)
  const [error, setError] = useState('')
  const captures = shots
    .filter((shot) => shot.kind === 'ground' && shot.bundle_id === info.bundle_id)
    .slice(-2)
  const ready = info.validation_status === 'accepted' && info.compatibility?.status === 'compatible'
  const selected =
    captures.length === 2 &&
    captures.every((shot) =>
      ['camera_1', 'camera_2'].every((camera) => origins[shot.id]?.[camera]),
    ) &&
    side !== ''

  useEffect(() => {
    if (status.state !== 'running') return
    const interval = setInterval(() => {
      api
        .groundReferenceStatus()
        .then((result) => {
          setStatus(result)
          if (result.state === 'done') onChanged()
        })
        .catch((failure: unknown) => setError(String(failure)))
    }, 1000)
    return () => clearInterval(interval)
  }, [status.state, onChanged])

  const capture = async () => {
    setCapturing(true)
    setError('')
    try {
      await api.calibrationShot('ground', undefined, {
        level_confirmed: level,
        target_confirmed: target,
      })
      onChanged()
    } catch (failure) {
      setError(String(failure))
    } finally {
      setCapturing(false)
    }
  }

  return (
    <section className="ground-reference">
      <h3>Ground and target reference</h3>
      <p>Reference: {info.ground_status ?? 'unavailable'}</p>
      {!ready ? (
        <p className="muted">
          Accepted camera geometry and compatible capture settings are required.
        </p>
      ) : (
        <>
          <p>
            Place the rigid measured board level on the hitting surface. Mark the first inner corner
            and align its row toward the target. Repeat the placement with the same orientation for
            the second capture.
          </p>
          <div className="preview-grid">
            <LivePreview camera="camera_1" label="camera_1" />
            <LivePreview camera="camera_2" label="camera_2" />
          </div>
          <label>
            <input
              type="checkbox"
              checked={level}
              onChange={(event) => setLevel(event.target.checked)}
            />{' '}
            Board checked with an independent level
          </label>
          <label>
            <input
              type="checkbox"
              checked={target}
              onChange={(event) => setTarget(event.target.checked)}
            />{' '}
            Marked board row points toward the intended target
          </label>
          <button
            onClick={capture}
            disabled={!level || !target || capturing || status.state === 'running'}
          >
            {capturing ? 'capturing...' : 'capture board placement'}
          </button>
          {captures.map((shot) => (
            <div key={shot.id} className="ground-capture">
              <h4>Placement {shot.id}</h4>
              <div className="preview-grid">
                {['camera_1', 'camera_2'].map((camera) => (
                  <div key={camera}>
                    <img
                      src={api.groundPreviewUrl(shot.id, camera)}
                      alt={`${camera} first and last detected board corners`}
                      style={{ width: '100%', maxHeight: 300, objectFit: 'contain' }}
                    />
                    <label>
                      Marked origin in {camera}
                      <select
                        value={origins[shot.id]?.[camera] ?? ''}
                        onChange={(event) =>
                          setOrigins((previous) => ({
                            ...previous,
                            [shot.id]: { ...previous[shot.id], [camera]: event.target.value },
                          }))
                        }
                      >
                        <option value="">select marked corner</option>
                        <option value="first">FIRST</option>
                        <option value="last">LAST</option>
                      </select>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <label>
            Golfer side, looking along the marked row toward the target
            <select value={side} onChange={(event) => setSide(event.target.value)}>
              <option value="">select side</option>
              <option value="1">toward the remaining board rows</option>
              <option value="-1">opposite the remaining board rows</option>
            </select>
          </label>
          <button
            disabled={!selected || status.state === 'running' || capturing}
            onClick={() => {
              setError('')
              api
                .groundReference(
                  captures.map((shot) => shot.id),
                  origins,
                  Number(side),
                )
                .then(setStatus)
                .catch((failure: unknown) => setError(String(failure)))
            }}
          >
            {status.state === 'running' ? 'validating...' : 'validate ground reference'}
          </button>
          {status.state === 'running' && (
            <button
              onClick={() =>
                api
                  .groundReferenceCancel()
                  .then(setStatus)
                  .catch((failure: unknown) => setError(String(failure)))
              }
            >
              cancel validation
            </button>
          )}
        </>
      )}
      {status.state === 'done' && (
        <p>
          Measured reference accepted for this camera bundle. Individual metric evidence still
          applies.
        </p>
      )}
      {(error || status.error) && <p className="error">{error || status.error}</p>}
    </section>
  )
}
