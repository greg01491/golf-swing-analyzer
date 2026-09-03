import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import type { Landmarks, PPosition, SessionDetail } from '../api'
import { METRIC_INFO, VIEW_LABELS, formatMetricName, type MetricView } from '../metricInfo'
import PPositionPanel from './PPositionPanel'
import Skeleton3D from './Skeleton3D'

export default function SessionView({
  sessionId,
  onChanged,
}: {
  sessionId: string
  onChanged?: () => void
}) {
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [landmarks, setLandmarks] = useState<Landmarks | null>(null)
  const [camera, setCamera] = useState<string>('camera_1')
  const [time, setTime] = useState(0)
  const [videoSize, setVideoSize] = useState<{ width: number; height: number } | null>(null)
  const [processState, setProcessState] = useState<string>('idle')
  const [selectedPosition, setSelectedPosition] = useState<PPosition | null>(null)
  const [showIdeal, setShowIdeal] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)
  const [show3D, setShow3D] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [speed, setSpeed] = useState(100)
  const [labelDraft, setLabelDraft] = useState('')
  const [groupDraft, setGroupDraft] = useState('My Swings')
  const [savingMeta, setSavingMeta] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    setDetail(null)
    setLandmarks(null)
    setProcessState('idle')
    setSelectedPosition(null)
    setVideoSize(null)
    api.session(sessionId).then((d) => {
      setDetail(d)
      setLabelDraft((d.metadata?.label as string) ?? '')
      setGroupDraft((d.metadata?.group as string) ?? 'My Swings')
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

  // apply the slow-motion playback rate (100% = normal, 0% = paused)
  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = speed / 100
  }, [speed])

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

  const saveMeta = async () => {
    setSavingMeta(true)
    try {
      await api.updateSession(sessionId, { label: labelDraft, group: groupDraft })
      setDetail(await api.session(sessionId))
      onChanged?.()
    } finally {
      setSavingMeta(false)
    }
  }

  const deleteVideos = async () => {
    if (
      !window.confirm(
        'Delete the video files for this swing to free up space?\n\nYour stats and metrics are kept — only the playback clips are removed.',
      )
    )
      return
    setDeleting(true)
    try {
      await api.deleteVideos(sessionId)
      setDetail(await api.session(sessionId))
      setVideoSize(null)
    } catch {
      // best-effort; a failed unlink leaves the clip in place
    } finally {
      setDeleting(false)
    }
  }

  if (!detail) return <div className="panel">loading…</div>

  const metrics = detail.metrics
  const quality = metrics?.tracking_quality
  const ball = metrics?.ball
  const addressTime = metrics?.phases ? metrics.phases.address_frame / (landmarks?.fps ?? 1) : null
  const showBallMarker = Boolean(
    ball?.detected &&
      ball.address_xy &&
      ball.source_camera === camera &&
      addressTime != null &&
      Math.abs(time - addressTime) < 0.15,
  )
  const createdAt = detail.metadata?.created_at as string | undefined
  const when = createdAt ? new Date(createdAt) : null

  return (
    <div className="session-view">
      <h2>
        {detail.metadata?.label
          ? (detail.metadata.label as string)
          : when
            ? `${when.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })} at ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
            : sessionId}
      </h2>

      <details className="session-meta-editor">
        <summary>rename / move</summary>
        <div className="session-meta-fields">
          <label>
            name
            <input
              type="text"
              value={labelDraft}
              placeholder="e.g. Rory McIlroy Iron Swing"
              onChange={(e) => setLabelDraft(e.target.value)}
            />
          </label>
          <label>
            folder
            <select value={groupDraft} onChange={(e) => setGroupDraft(e.target.value)}>
              <option value="My Swings">My Swings</option>
              <option value="Professional Swings">Professional Swings</option>
            </select>
          </label>
          <button type="button" onClick={saveMeta} disabled={savingMeta}>
            {savingMeta ? 'saving…' : 'save'}
          </button>
        </div>
      </details>

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

      {metrics?.p_positions && (
        <PPositionPanel
          positions={metrics.p_positions}
          selected={selectedPosition?.name ?? null}
          onSelect={selectPosition}
          showIdeal={showIdeal}
          onToggleIdeal={setShowIdeal}
        />
      )}

      <div className="playback-row">
        <div className="panel video-panel">
          {detail.cameras.length === 0 ? (
            <p className="muted">
              Videos removed to save space. Your stats are kept — see the metrics and the stats tab.
            </p>
          ) : (
            <>
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
              <div className="video-frame">
                <video
                  key={videoSrc}
                  ref={videoRef}
                  src={videoSrc}
                  controls
                  loop
                  onLoadedMetadata={(e) => {
                    const target = e.currentTarget
                    target.playbackRate = speed / 100
                    setVideoSize({ width: target.videoWidth, height: target.videoHeight })
                  }}
                />
                {showBallMarker && videoSize && ball?.address_xy && (
                  <div
                    className="ball-marker"
                    style={{
                      left: `${(ball.address_xy[0] / videoSize.width) * 100}%`,
                      top: `${(ball.address_xy[1] / videoSize.height) * 100}%`,
                    }}
                    title={`ball detected at address (${ball.impact_source})`}
                  />
                )}
              </div>
              <div className="video-controls">
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
                <label className="speed-control">
                  slow motion
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={1}
                    value={speed}
                    onChange={(e) => setSpeed(Number(e.target.value))}
                  />
                  <span className="speed-value">{speed}%</span>
                </label>
                <button
                  type="button"
                  className="collapse-toggle"
                  onClick={() => setShow3D((v) => !v)}
                  aria-expanded={show3D}
                >
                  {show3D ? 'hide 3D skeleton' : 'show 3D skeleton'}
                </button>
                <button
                  type="button"
                  className="delete-videos"
                  onClick={deleteVideos}
                  disabled={deleting}
                >
                  {deleting ? 'deleting…' : 'delete videos (keep stats)'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {metrics && (
        <div className="panel metrics-panel">
          <h3>metrics</h3>
          {(['down-the-line', 'front-on'] as MetricView[]).map((view) => {
            const rows = metrics.metrics.filter(
              (m) => (METRIC_INFO[m.name]?.view ?? 'down-the-line') === view,
            )
            if (rows.length === 0) return null
            return (
              <div key={view} className="metric-group">
                <h4 className="metric-group-title">{VIEW_LABELS[view]}</h4>
                <table>
                  <tbody>
                    {rows.map((m) => {
                      const info = METRIC_INFO[m.name]
                      return (
                        <tr key={m.name} className={m.in_range === false ? 'flagged' : ''}>
                          <td>
                            <span className="metric-name">{formatMetricName(m.name)}</span>
                            {info && (
                              <span className="help-icon" tabIndex={0} aria-label={info.label}>
                                i
                                <span className="help-tooltip" role="tooltip">
                                  <strong>{info.label}</strong>
                                  <span>{info.description}</span>
                                  <span className="help-good">
                                    <em>What good looks like:</em> {info.good}
                                  </span>
                                </span>
                              </span>
                            )}
                          </td>
                          <td
                            className={
                              m.in_range === true
                                ? 'metric-value in-range'
                                : m.in_range === false
                                  ? 'metric-value out-range'
                                  : 'metric-value'
                            }
                          >
                            {m.value === null ? '—' : `${m.value} ${m.unit}`}
                          </td>
                          <td>
                            {m.in_range === null ? '' : m.in_range ? 'OK' : 'out of range'}
                            {m.range ? ` (${m.range.min}–${m.range.max})` : ''}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )
          })}
        </div>
      )}

      {show3D && (
        <div className="panel skeleton-panel">
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
      )}

      {ball?.detected && (
        <div className="panel">
          <strong>ball tracking</strong>
          <p className="muted">
            Ball detected at address {ball.address_xy ? `(${ball.address_xy[0]}, ${ball.address_xy[1]})` : ''}
            {ball.radius != null ? `, radius ${ball.radius}` : ''}
            {ball.source_camera ? ` from ${ball.source_camera}` : ''}. Impact is{' '}
            {ball.impact_source === 'ball' ? 'detected from ball disappearance' : 'estimated'}.
          </p>
        </div>
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
      )}
    </div>
  )
}
