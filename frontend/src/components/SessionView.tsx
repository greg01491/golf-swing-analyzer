import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import type { Landmarks, PPosition, SessionDetail } from '../api'
import PPositionPanel from './PPositionPanel'
import Skeleton3D from './Skeleton3D'

interface Props {
  sessionId: string
  focusedMetric: string | null
  onFocusMetric: (metric: string | null) => void
}

const cameraLabel = (camera: string) => {
  if (camera === 'camera_1') return 'Down-the-line view'
  if (camera === 'camera_2') return 'Face-on view'
  return camera.replaceAll('_', ' ')
}

export default function SessionView({ sessionId, focusedMetric, onFocusMetric }: Props) {
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [landmarks, setLandmarks] = useState<Landmarks | null>(null)
  const [camera, setCamera] = useState<string>('camera_1')
  const [time, setTime] = useState(0)
  const [processState, setProcessState] = useState<string>('idle')
  const [selectedPosition, setSelectedPosition] = useState<PPosition | null>(null)
  const [showIdeal, setShowIdeal] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)
  const [proMode, setProMode] = useState(() => localStorage.getItem('pro-mode') === 'on')
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({})

  useEffect(() => {
    localStorage.setItem('pro-mode', proMode ? 'on' : 'off')
  }, [proMode])

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
    for (const video of Object.values(videoRefs.current)) {
      if (video) {
        video.pause()
        video.currentTime = position.time_s
      }
    }
  }

  // drive skeleton time from the video element
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const video = videoRefs.current[camera] ?? Object.values(videoRefs.current)[0]
      if (video) setTime(video.currentTime)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [camera])

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
  const cameraKey = detail?.cameras.join('|') ?? ''
  const overlayKey = detail?.overlay_cameras?.join('|') ?? ''
  // memoized because videoUrl embeds a cache-buster: this component
  // re-renders every animation frame (video->skeleton time sync), and a
  // fresh URL per render would reset the <video> src continuously, pinning
  // playback at 0:00
  const videoSources = useMemo(
    () =>
      Object.fromEntries(
        (detail?.cameras ?? []).map((cam) => [
          cam,
          api.videoUrl(
            sessionId,
            cam,
            showOverlay && (detail?.overlay_cameras ?? []).includes(cam),
          ),
        ]),
      ),
    // cameraKey and overlayKey deliberately represent array contents.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, cameraKey, overlayKey, showOverlay],
  )
  const videoSrc = videoSources[camera]

  const syncProVideos = (action: 'play' | 'pause' | 'seek' | 'rate') => {
    const primary = videoRefs.current[detail?.cameras[0] ?? '']
    if (!primary) return
    for (const [cam, video] of Object.entries(videoRefs.current)) {
      if (!video || cam === detail?.cameras[0]) continue
      if (Math.abs(video.currentTime - primary.currentTime) > 0.05) {
        video.currentTime = primary.currentTime
      }
      video.playbackRate = primary.playbackRate
      if (action === 'play') void video.play().catch(() => undefined)
      if (action === 'pause') video.pause()
    }
  }

  if (!detail) return <div className="panel">loading…</div>

  const metrics = detail.metrics
  const quality = metrics?.tracking_quality
  const createdAt = detail.metadata?.created_at as string | undefined
  const club = (metrics?.club ?? detail.metadata?.club) as string | undefined
  const when = createdAt ? new Date(createdAt) : null

  return (
    <div className="session-view">
      <div className="session-heading">
        <h2>
          {when
            ? `${when.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })} at ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
            : sessionId}
        </h2>
        <button
          className={proMode ? 'active pro-mode-toggle' : 'pro-mode-toggle'}
          onClick={() => setProMode((enabled) => !enabled)}
        >
          {proMode ? 'Pro Mode on' : 'Pro Mode'}
        </button>
      </div>
      {club && <p className="session-club">{club.replaceAll('_', ' ')}</p>}

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

      {proMode ? (
        <>
          <div className="pro-playback-grid">
            {detail.cameras.map((cam, index) => (
              <div className="panel pro-camera" key={cam}>
                <h3>{cameraLabel(cam)}</h3>
                <video
                  ref={(node) => {
                    videoRefs.current[cam] = node
                  }}
                  src={videoSources[cam]}
                  controls={index === 0}
                  loop
                  onPlay={index === 0 ? () => syncProVideos('play') : undefined}
                  onPause={index === 0 ? () => syncProVideos('pause') : undefined}
                  onSeeked={index === 0 ? () => syncProVideos('seek') : undefined}
                  onRateChange={index === 0 ? () => syncProVideos('rate') : undefined}
                  onTimeUpdate={index === 0 ? () => syncProVideos('seek') : undefined}
                />
                {index > 0 && <span className="muted sync-label">synced to left view</span>}
              </div>
            ))}
          </div>
          {(detail.overlay_cameras?.length ?? 0) > 0 && (
            <label className="overlay-toggle">
              <input
                type="checkbox"
                checked={showOverlay}
                onChange={(e) => setShowOverlay(e.target.checked)}
              />
              show skeleton drawn on the video
            </label>
          )}
        </>
      ) : (
        <div className="playback-row">
          <div className="panel">
            <div className="camera-tabs">
              {detail.cameras.map((cam) => (
                <button
                  key={cam}
                  className={cam === camera ? 'active' : ''}
                  onClick={() => setCamera(cam)}
                >
                  {cameraLabel(cam)}
                </button>
              ))}
            </div>
            <video
              key={videoSrc}
              ref={(node) => {
                videoRefs.current[camera] = node
              }}
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
      )}

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
            <div className="metrics-heading">
              <h3>metrics</h3>
              {focusedMetric && (
                <button className="link-btn" onClick={() => onFocusMetric(null)}>
                  clear voice focus
                </button>
              )}
            </div>
            <p className="muted metric-instruction">
              Click a metric to make every spoken result focus on it.
            </p>
            <table>
              <tbody>
                {metrics.metrics.map((m) => (
                  <tr
                    key={m.name}
                    className={[
                      m.in_range === false ? 'flagged' : '',
                      focusedMetric === m.name ? 'voice-focused' : '',
                    ].join(' ')}
                  >
                    <td>
                      <button
                        className="metric-focus"
                        aria-pressed={focusedMetric === m.name}
                        onClick={() => onFocusMetric(m.name)}
                      >
                        {m.name.replaceAll('_', ' ')}
                        {focusedMetric === m.name && <span>voice focus</span>}
                      </button>
                    </td>
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
