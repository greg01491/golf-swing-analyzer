import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { CalibrationComputeStatus, CalibrationInfo, CalibrationShot } from '../api'

type Stage = 'camera_1' | 'camera_2' | 'position'

const STAGE_INFO: Record<Stage, { title: string; instructions: string; camera: string }> = {
  camera_1: {
    title: 'Step 1 of 3 — down-the-line camera lens',
    instructions:
      "Hold the board about arm's length from this camera, well lit. Slowly tilt and move it to different parts of the frame between captures — corners, edges, angled toward/away.",
    camera: 'camera_1',
  },
  camera_2: {
    title: 'Step 2 of 3 — face-on camera lens',
    instructions:
      "Same again, but for the other camera. Hold the board about arm's length away and vary its angle and position between captures.",
    camera: 'camera_2',
  },
  position: {
    title: 'Step 3 of 3 — camera position',
    instructions:
      'Stand at your normal hitting position, fully visible to BOTH cameras. When the countdown ends, do a slow practice swing (no club needed) so your whole body sweeps through the view.',
    camera: 'camera_1',
  },
}

function LivePreview({ camera, label }: { camera: string; label: string }) {
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

function ShotCountdown({
  onCapture,
  disabled,
}: {
  onCapture: () => void
  disabled: boolean
}) {
  const [counting, setCounting] = useState<number | null>(null)
  const timerRef = useRef<number | null>(null)

  const start = () => {
    if (counting !== null) return
    setCounting(10)
  }

  useEffect(() => {
    if (counting === null) return
    if (counting === 0) {
      onCapture()
      setCounting(null)
      return
    }
    timerRef.current = window.setTimeout(() => setCounting((c) => (c ?? 1) - 1), 1000)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [counting])

  return (
    <button className="countdown-btn" onClick={start} disabled={disabled || counting !== null}>
      {counting !== null ? `capturing in ${counting}…` : 'capture (10s countdown)'}
    </button>
  )
}

function DistanceGate({
  onConfirm,
}: {
  onConfirm: (distanceM: number) => void
}) {
  const [value, setValue] = useState('')
  const [touched, setTouched] = useState(false)

  const parsed = Number(value)
  const valid = Number.isFinite(parsed) && parsed > 0

  return (
    <div className="wizard">
      <h2>Camera calibration</h2>
      <div className="panel">
        <h3>Step 0 — measure the distance between your cameras</h3>
        <p>
          Before anything else, measure the straight-line distance between the two cameras'
          <strong> lenses</strong> — not the camera bodies, mounts, or tripods. Use the{' '}
          <strong>same reference point on each lens</strong> (e.g. the centre of the front
          glass on both) — measuring from a different point on each camera introduces an
          error that scales <em>every</em> 3D measurement the calibration produces afterward,
          so it's worth getting right.
        </p>
        <p className="muted">
          If the cameras are far apart, at different heights, or awkward to reach at the same
          time, it's much easier with a second person: one of you holds the tape measure at
          one lens while the other reads the measurement at the other.
        </p>
        <label className="field">
          distance between the two camera lenses (metres)
          <input
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setTouched(true)
            }}
            placeholder="e.g. 2.5"
          />
        </label>
        {touched && !valid && <p className="error">enter a distance greater than 0</p>}
        <button disabled={!valid} onClick={() => onConfirm(parsed)}>
          confirm distance and continue
        </button>
      </div>
    </div>
  )
}

export default function CalibrationWizard() {
  const [info, setInfo] = useState<CalibrationInfo | null>(null)
  const [stage, setStage] = useState<Stage>('camera_1')
  const [shots, setShots] = useState<CalibrationShot[]>([])
  const [distance, setDistance] = useState<number | null>(null)
  const [editingDistance, setEditingDistance] = useState(false)
  const [compute, setCompute] = useState<CalibrationComputeStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshShots = () => api.calibrationShots().then(setShots)

  useEffect(() => {
    api.calibrationInfo().then(setInfo)
    refreshShots()
  }, [])

  useEffect(() => {
    if (compute?.state !== 'running') return
    const id = setInterval(async () => {
      const s = await api.calibrationComputeStatus()
      setCompute(s)
      if (s.state !== 'running') {
        clearInterval(id)
        api.calibrationInfo().then(setInfo)
      }
    }, 1000)
    return () => clearInterval(id)
  }, [compute?.state])

  const capture = async (kind: 'intrinsics' | 'extrinsics') => {
    setError(null)
    try {
      await api.calibrationShot(kind)
      await refreshShots()
    } catch (e) {
      setError(String(e))
    }
  }

  const runCompute = async () => {
    setError(null)
    if (!distance) {
      setError('camera distance is missing — please re-enter it')
      return
    }
    try {
      const s = await api.calibrationCompute(distance)
      setCompute(s)
    } catch (e) {
      setError(String(e))
    }
  }

  const countFor = (kind: 'intrinsics' | 'extrinsics') =>
    shots.filter((s) => s.kind === kind).length
  const boardHitsFor = (camera: string) =>
    shots
      .filter((s) => s.kind === 'intrinsics')
      .reduce((sum, s) => sum + (s.board_frames_detected[camera] ?? 0), 0)

  // Distance must be confirmed before anything else in the wizard is usable —
  // it's the one external measurement the whole calibration's scale depends on.
  if (distance === null || editingDistance) {
    return (
      <DistanceGate
        onConfirm={(d) => {
          setDistance(d)
          setEditingDistance(false)
        }}
      />
    )
  }

  const info_ = STAGE_INFO[stage]

  return (
    <div className="wizard">
      <h2>Camera calibration</h2>

      <div className="panel distance-confirmed">
        camera distance: <strong>{distance.toFixed(2)} m</strong>{' '}
        <button className="link-btn" onClick={() => setEditingDistance(true)}>
          change
        </button>
      </div>

      {info && (
        <div className={`panel calib-status ${info.stale ? 'stale' : info.exists ? 'ok' : ''}`}>
          {info.exists
            ? `Calibration on file: ${info.age_days?.toFixed(0)} day(s) old${info.stale ? ' — stale, recalibrate' : ''}`
            : 'No calibration on file yet.'}
        </div>
      )}

      <div className="wizard-tabs">
        {(['camera_1', 'camera_2', 'position'] as Stage[]).map((s) => (
          <button key={s} className={s === stage ? 'active' : ''} onClick={() => setStage(s)}>
            {STAGE_INFO[s].title.split('—')[0].trim()}
          </button>
        ))}
      </div>

      <div className="panel">
        <h3>{info_.title}</h3>
        <p>{info_.instructions}</p>

        {stage === 'position' ? (
          <div className="preview-grid">
            <LivePreview camera="camera_1" label="camera_1 (down-the-line)" />
            <LivePreview camera="camera_2" label="camera_2 (face-on)" />
          </div>
        ) : (
          <LivePreview camera={info_.camera} label={info_.camera} />
        )}

        <div className="wizard-actions">
          <ShotCountdown onCapture={() => capture(stage === 'position' ? 'extrinsics' : 'intrinsics')} disabled={false} />
          {stage !== 'position' && (
            <span className="muted">
              {countFor('intrinsics') > 0
                ? `board detected in ${boardHitsFor(info_.camera)} sampled frames across ${countFor('intrinsics')} capture(s) so far (need several with the board clearly visible)`
                : 'no captures yet — aim for at least 3-4 with the board clearly in frame'}
            </span>
          )}
          {stage === 'position' && (
            <span className="muted">
              {countFor('extrinsics') > 0
                ? `${countFor('extrinsics')} position capture(s) so far — the latest one is used`
                : 'capture once you’re in position and ready to swing'}
            </span>
          )}
        </div>
      </div>

      <div className="panel">
        <h3>Compute calibration</h3>
        <p className="muted">using camera distance: {distance.toFixed(2)} m</p>
        <button onClick={runCompute} disabled={compute?.state === 'running'}>
          {compute?.state === 'running' ? 'computing…' : 'compute calibration'}
        </button>

        {compute?.state === 'running' && <p className="muted">{compute.stage}</p>}
        {compute?.state === 'error' && <p className="error">{compute.error}</p>}
        {compute?.state === 'done' && compute.result && (
          <div className="calib-result">
            <p>Done — calibration written to {compute.result.calib_file}</p>
            <ul>
              <li>
                camera_1 lens: {compute.result.camera_1.lens_views} views, RMS{' '}
                {compute.result.camera_1.lens_rms_px}px
              </li>
              <li>
                camera_2 lens: {compute.result.camera_2.lens_views} views, RMS{' '}
                {compute.result.camera_2.lens_rms_px}px
              </li>
              <li>
                {compute.result.keypoint_correspondences} body-keypoint matches, mean
                reprojection error {compute.result.mean_reprojection_error_px}px
              </li>
              {compute.result.estimated_person_height_m && (
                <li>
                  sanity check — estimated body extent:{' '}
                  {compute.result.estimated_person_height_m}m (should be roughly your height)
                </li>
              )}
            </ul>
          </div>
        )}
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  )
}
