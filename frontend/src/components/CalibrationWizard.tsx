import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { CalibrationComputeStatus, CalibrationInfo, CalibrationShot } from '../api'
import LivePreview from './LivePreview'

type Stage = 'camera_1' | 'camera_2' | 'position'

const STAGE_INFO: Record<Stage, { title: string; instructions: string; camera: string }> = {
  camera_1: {
    title: 'Step 1 of 3 — down-the-line camera lens',
    instructions:
      'Walk UP TO this camera and hold the printed board close to the lens (about 30–50cm away) so the checkerboard FILLS most of the frame — do NOT stand back at your hitting position; a board seen from across the room is far too small to detect. Keep it flat, still, and in sharp focus, and between captures tilt it and move it to different parts of the frame (corners, edges, angled toward/away). Watch the "board detected" count below climb — if it stays 0, the board is too far, too small, blurry, or badly lit.',
    camera: 'camera_1',
  },
  camera_2: {
    title: 'Step 2 of 3 — face-on camera lens',
    instructions:
      'Same again, up close to the OTHER camera: hold the board 30–50cm from that lens so it fills the frame, flat and in focus, varying its angle and position between captures. Again, watch the "board detected" count climb.',
    camera: 'camera_2',
  },
  position: {
    title: 'Step 3 of 3 — camera position',
    instructions:
      'Stand at your normal hitting position, fully visible to BOTH cameras. When the countdown ends, do a slow practice swing (no club needed) so your whole body sweeps through the view.',
    camera: 'camera_1',
  },
}

// Target shot counts shown as a big "X / N" readout -- also the auto-loop's
// stopping point, not just display: once reached, the loop below stops
// itself instead of making the user keep re-clicking.
const SHOT_TARGET = { intrinsics: 8, extrinsics: 1 } as const

const COUNTDOWN_OPTIONS = [3, 5, 10, 15]

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

/* eslint-disable @typescript-eslint/no-explicit-any */
function SetupGate({ onConfirm }: { onConfirm: (distanceM: number) => void }) {
  const [config, setConfig] = useState<Record<string, any> | null>(null)
  const [squareSize, setSquareSize] = useState('')
  const [distance, setDistance] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.config().then((c) => {
      setConfig(c)
      const current = (c as any).calibration?.checkerboard_square_size_mm
      if (current) setSquareSize(String(current))
    })
  }, [])

  const squareSizeNum = Number(squareSize)
  const distanceNum = Number(distance)
  const squareSizeValid = Number.isFinite(squareSizeNum) && squareSizeNum > 0
  const distanceValid = Number.isFinite(distanceNum) && distanceNum > 0

  const confirm = async () => {
    setError(null)
    if (!config) return
    setSaving(true)
    try {
      await api.saveConfig({
        ...config,
        calibration: { ...config.calibration, checkerboard_square_size_mm: squareSizeNum },
      })
      onConfirm(distanceNum)
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="wizard">
      <h2>Camera calibration</h2>

      <div className="panel">
        <h3>Step 0a — print the calibration board</h3>
        <p>
          Print this checkerboard at <strong>100% scale</strong> (not "fit to page"), then
          measure one square with a ruler — across several squares and divide, for accuracy —
          and enter the measured size below. Printers rarely reproduce exact scale, so the
          measured size matters more than the nominal one printed on the page.
        </p>
        {config ? (
          <img
            src={api.calibrationBoardUrl()}
            alt="printable calibration checkerboard"
            className="board-preview"
          />
        ) : (
          <p className="muted">loading board…</p>
        )}
        <label className="field">
          measured square size (mm)
          <input
            value={squareSize}
            onChange={(e) => setSquareSize(e.target.value)}
            placeholder="e.g. 28.4"
          />
        </label>
      </div>

      <div className="panel">
        <h3>Step 0b — measure the distance between your cameras</h3>
        <p>
          Measure the straight-line distance between the two cameras'
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
            value={distance}
            onChange={(e) => setDistance(e.target.value)}
            placeholder="e.g. 2.5"
          />
        </label>
      </div>

      {squareSize && !squareSizeValid && <p className="error">enter a square size greater than 0</p>}
      {distance && !distanceValid && <p className="error">enter a distance greater than 0</p>}
      <button
        disabled={!squareSizeValid || !distanceValid || !config || saving}
        onClick={confirm}
      >
        {saving ? 'saving…' : 'confirm and continue'}
      </button>
      {error && <p className="error">{error}</p>}
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

  const [justCaptured, setJustCaptured] = useState(false)

  // returns the freshly-fetched shot list (not just setting state) so the
  // capture loop below can check the up-to-date count without racing React's
  // render cycle
  const capture = async (kind: 'intrinsics' | 'extrinsics', forCamera: string) => {
    setError(null)
    try {
      // the position capture records both cameras at once, so a per-camera
      // tag would be meaningless there -- only lens shots carry one
      await api.calibrationShot(kind, kind === 'intrinsics' ? forCamera : undefined)
      const updated = await api.calibrationShots()
      setShots(updated)
      // confirms a shot actually landed -- from across the room you can't
      // see the small status text change, so flash something unmissable
      setJustCaptured(true)
      setTimeout(() => setJustCaptured(false), 1500)
      return updated
    } catch (e) {
      setError(String(e))
      return null
    }
  }

  const [countdownS, setCountdownS] = useState(5)
  const [counting, setCounting] = useState<number | null>(null)
  const [autoCapturing, setAutoCapturing] = useState(false)
  const [targetReached, setTargetReached] = useState(false)
  const [capturesThisRun, setCapturesThisRun] = useState(0)
  const autoCapturingRef = useRef(false)

  // Counts shots for one wizard stage. Intrinsics shots are tagged with the
  // camera the board was held up to -- without that tag, step 1 and step 2
  // shared one pooled total, so step 2 opened already showing "8 / 8".
  // Untagged legacy shots count toward no stage.
  const countStageShots = (
    list: CalibrationShot[],
    kind: 'intrinsics' | 'extrinsics',
    forCamera: string,
  ) =>
    list.filter((s) => s.kind === kind && (kind === 'extrinsics' || s.for_camera === forCamera))
      .length

  // Repeats the countdown -> capture cycle on its own (no re-clicking)
  // until the shot target is hit or the user hits stop -- the countdown
  // reappears automatically each time, acting as the "next capture in
  // 3, 2, 1" cue without any extra text needed.
  const runCaptureLoop = async (kind: 'intrinsics' | 'extrinsics', forCamera: string) => {
    while (autoCapturingRef.current) {
      for (let s = countdownS; s > 0 && autoCapturingRef.current; s--) {
        setCounting(s)
        await sleep(1000)
      }
      if (!autoCapturingRef.current) break
      setCounting(0)
      const updated = await capture(kind, forCamera)
      setCounting(null)
      if (!updated) break
      setCapturesThisRun((n) => n + 1)
      if (countStageShots(updated, kind, forCamera) >= SHOT_TARGET[kind]) {
        setTargetReached(true)
        break
      }
      // hold here so the "captured ✓" flash is actually visible -- starting
      // the next countdown immediately would cover it the same frame it
      // appeared (the overlay only renders the flash while no countdown is up)
      await sleep(1500)
    }
    autoCapturingRef.current = false
    setAutoCapturing(false)
    setCounting(null)
  }

  const startCapturing = () => {
    if (autoCapturingRef.current) return
    setTargetReached(false)
    setCapturesThisRun(0)
    autoCapturingRef.current = true
    setAutoCapturing(true)
    runCaptureLoop(stage === 'position' ? 'extrinsics' : 'intrinsics', STAGE_INFO[stage].camera)
  }

  const stopCapturing = () => {
    autoCapturingRef.current = false
    setAutoCapturing(false)
    setCounting(null)
  }

  const changeStage = (s: Stage) => {
    stopCapturing()
    setTargetReached(false) // target state is per-stage, not global
    setStage(s)
  }

  const [clearingShots, setClearingShots] = useState(false)

  // Intrinsics shots are pooled across every capture ever taken (not just
  // this run), so stale captures from before a rig change (e.g. the camera
  // rotation fix) silently keep feeding compute alongside new ones unless
  // explicitly wiped.
  const clearAllShots = async () => {
    if (!window.confirm('Delete all calibration captures (both cameras and the position shot) and start over?')) {
      return
    }
    stopCapturing()
    setClearingShots(true)
    setError(null)
    try {
      await api.calibrationShotsClear()
      await refreshShots()
      setTargetReached(false)
      setCapturesThisRun(0)
    } catch (e) {
      setError(String(e))
    } finally {
      setClearingShots(false)
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
    countStageShots(shots, kind, STAGE_INFO[stage].camera)
  const boardHitsFor = (camera: string) =>
    shots
      .filter((s) => s.kind === 'intrinsics')
      .reduce((sum, s) => sum + (s.board_frames_detected[camera] ?? 0), 0)

  // Board size + camera distance must be confirmed before anything else in
  // the wizard is usable -- they're the external measurements the whole
  // calibration's scale depends on.
  if (distance === null || editingDistance) {
    return (
      <SetupGate
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

      {info &&
        (info.broken ? (
          <div className="panel calib-status stale">
            <strong>⚠ The current calibration is broken</strong> (reprojection error{' '}
            {info.reprojection_error_px != null
              ? `${Math.round(info.reprojection_error_px).toLocaleString()}px`
              : 'very high'}
            ; a good one is under ~50px). Every session using it produces garbage 3D — tangled
            skeletons, wrong positions, nonsense metrics. <strong>Recalibrate:</strong> clear all
            captures, redo the board and position steps carefully, and recompute.
          </div>
        ) : (
          <div className={`panel calib-status ${info.stale ? 'stale' : info.exists ? 'ok' : ''}`}>
            {info.exists
              ? `Calibration on file: ${info.age_days?.toFixed(0)} day(s) old${info.stale ? ' — stale, recalibrate' : ''}` +
                (info.reprojection_error_px != null
                  ? ` — reprojection error ${Math.round(info.reprojection_error_px)}px`
                  : '')
              : 'No calibration on file yet.'}
          </div>
        ))}

      <div className="wizard-tabs">
        {(['camera_1', 'camera_2', 'position'] as Stage[]).map((s) => (
          <button key={s} className={s === stage ? 'active' : ''} onClick={() => changeStage(s)}>
            {STAGE_INFO[s].title.split('—')[0].trim()}
          </button>
        ))}
        <button className="link-btn clear-shots-btn" onClick={clearAllShots} disabled={clearingShots}>
          {clearingShots ? 'clearing…' : 'clear all captures and start over'}
        </button>
      </div>

      <div className="panel">
        <h3>{info_.title}</h3>
        <p>{info_.instructions}</p>

        <div className="preview-overlay-wrap">
          {stage === 'position' ? (
            <div className="preview-grid">
              <LivePreview camera="camera_1" label="camera_1 (down-the-line)" />
              <LivePreview camera="camera_2" label="camera_2 (face-on)" />
            </div>
          ) : (
            <LivePreview camera={info_.camera} label={info_.camera} />
          )}
          {counting !== null && (
            <div className="countdown-big">
              {counting}
              <div className="countdown-caption">
                {capturesThisRun === 0 ? 'get ready' : 'next capture in'}
              </div>
            </div>
          )}
          {justCaptured && counting === null && (
            <div className="countdown-big captured-flash">captured ✓</div>
          )}
          <div className="shot-progress-badge">
            {stage !== 'position'
              ? `${countFor('intrinsics')} / ${SHOT_TARGET.intrinsics} captures`
              : countFor('extrinsics') > 0
                ? `✓ ${countFor('extrinsics')} captured`
                : `0 / ${SHOT_TARGET.extrinsics} captures`}
          </div>
        </div>

        <div className="wizard-actions">
          <select
            value={countdownS}
            onChange={(e) => setCountdownS(Number(e.target.value))}
            disabled={autoCapturing}
            aria-label="countdown length"
          >
            {COUNTDOWN_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}s countdown
              </option>
            ))}
          </select>
          {autoCapturing ? (
            <button className="countdown-btn" onClick={stopCapturing}>
              stop capturing
            </button>
          ) : (
            <button className="countdown-btn" onClick={startCapturing}>
              start capturing
            </button>
          )}
          {stage !== 'position' && (
            <span className="muted">
              {targetReached
                ? `target reached (${countFor('intrinsics')} / ${SHOT_TARGET.intrinsics}) — move to the next step, or start capturing again for a few more`
                : countFor('intrinsics') > 0
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
