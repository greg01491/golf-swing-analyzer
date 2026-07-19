import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import type { Landmarks, PPosition, SessionDetail } from '../api'
import PPositionPanel from './PPositionPanel'
import Skeleton3D from './Skeleton3D'

export default function SessionView({ sessionId }: { sessionId: string }) {
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [landmarks, setLandmarks] = useState<Landmarks | null>(null)
  const [camera, setCamera] = useState<string>('camera_1')
  const [time, setTime] = useState(0)
  const [processState, setProcessState] = useState<string>('idle')
  const [selectedPosition, setSelectedPosition] = useState<PPosition | null>(null)
  const [showIdeal, setShowIdeal] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    setDetail(null)
    setLandmarks(null)
    setProcessState('idle')
    setSelectedPosition(null)
    api.session(sessionId).then((d) => {
      setDetail(d)
      if (d.cameras.length && !d.cameras.includes(camera)) setCamera(d.cameras[0])
    })
    api.landmarks(sessionId).then(setLandmarks).catch(() => setLandmarks(null))
    // reflect any in-progress/failed auto-processing kicked off at capture,
    // so the panel shows "processing…" or the error rather than a stale
    // "process swing" button (the video itself plays regardless)
    api.processStatus(sessionId).then(({ status }) => {
      if (status !== 'idle') setProcessState(status)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const selectPosition = (position: PPosition) => {
    setSelectedPosition(position)
    if (videoRef.current) {
      videoRef.current.pause()
      videoRef.current.currentTime = position.time_s
    }
  }

  // drive skeleton time from the video element
  useEffect(() => {
    let raf = 0
    const tick = () => {
      if (videoRef.current) setTime(videoRef.current.currentTime)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  // poll processing status while running
  useEffect(() => {
    if (processState !== 'running') return
    const id = setInterval(async () => {
      const { status } = await api.processStatus(sessionId)
      setProcessState(status)
      if (status === 'done') {
        api.session(sessionId).then(setDetail)
        api.landmarks(sessionId).then(setLandmarks).catch(() => setLandmarks(null))
      }
    }, 2000)
    return () => clearInterval(id)
  }, [processState, sessionId])

  const overlayAvailable = (detail?.overlay_cameras ?? []).includes(camera)
  // memoized because videoUrl embeds a cache-buster: this component
  // re-renders every animation frame (video->skeleton time sync), and a
  // fresh URL per render would reset the <video> src continuously, pinning
  // playback at 0:00
  const videoSrc = useMemo(
    () => api.videoUrl(sessionId, camera, overlayAvailable && showOverlay),
    [sessionId, camera, overlayAvailable, showOverlay],
  )

  if (!detail) return <div className="panel">loading…</div>

  const metrics = detail.metrics
  const quality = metrics?.tracking_quality
  const createdAt = detail.metadata?.created_at as string | undefined
  const when = createdAt ? new Date(createdAt) : null

  return (
    <div className="session-view">
      <h2>
        {when
          ? `${when.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })} at ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
          : sessionId}
      </h2>

      {quality && !quality.reliable && (
        <div className="panel quality-warning">
          <strong>⚠ Low tracking quality — metrics and positions below may be unreliable.</strong>
          <ul>
            {quality.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <p className="muted">
            The video and skeleton are still shown, but the swing couldn't be reconstructed cleanly
            in 3D. This is usually a calibration or camera-framing issue — make sure your whole body
            stays in <em>both</em> camera views through the swing, and that the rig calibration is
            current.
          </p>
        </div>
      )}

      <div className="playback-row">
        <div className="panel">
          <div className="camera-tabs">
            {detail.cameras.map((cam) => (
              <button
                key={cam}
                className={cam === camera ? 'active' : ''}
                onClick={() => setCamera(cam)}
              >
                {cam}
              </button>
            ))}
          </div>
          <video
            key={videoSrc}
            ref={videoRef}
            src={videoSrc}
            controls
            loop
            width={480}
          />
          {overlayAvailable && (
            <label className="overlay-toggle">
              <input
                type="checkbox"
                checked={showOverlay}
                onChange={(e) => setShowOverlay(e.target.checked)}
              />
              show skeleton drawn on the video
            </label>
          )}
        </div>

        <div className="panel">
          <h3>3D skeleton</h3>
          {landmarks ? (
            <Skeleton3D
              landmarks={landmarks}
              time={time}
              idealFrame={showIdeal ? selectedPosition?.ideal_frame : null}
            />
          ) : (
            <p className="muted">no 3D data yet — run processing</p>
          )}
        </div>
      </div>

      {metrics?.p_positions && (
        <PPositionPanel
          positions={metrics.p_positions}
          selected={selectedPosition?.name ?? null}
          onSelect={selectPosition}
          showIdeal={showIdeal}
          onToggleIdeal={setShowIdeal}
        />
      )}

      {!metrics && (
        <div className="panel">
          <button
            disabled={processState === 'running'}
            onClick={() => {
              setProcessState('running')
              api.process(sessionId)
            }}
          >
            {processState === 'running' ? 'processing…' : 'process swing (pose → 3D → metrics)'}
          </button>
          {processState.startsWith('error') && <p className="error">{processState}</p>}
        </div>
      )}

      {metrics && (
        <div className="results-row">
          <div className="panel">
            <h3>metrics</h3>
            <table>
              <tbody>
                {metrics.metrics.map((m) => (
                  <tr key={m.name} className={m.in_range === false ? 'flagged' : ''}>
                    <td>{m.name}</td>
                    <td>{m.value === null ? '—' : `${m.value} ${m.unit}`}</td>
                    <td>
                      {m.in_range === null ? '' : m.in_range ? 'OK' : 'out of range'}
                      {m.range ? ` (${m.range.min}–${m.range.max})` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel">
            <h3>tips</h3>
            {metrics.tips.length === 0 ? (
              <p>everything in range — nice swing.</p>
            ) : (
              <ol>
                {metrics.tips.map((tip) => (
                  <li key={tip.metric}>{tip.text}</li>
                ))}
              </ol>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
