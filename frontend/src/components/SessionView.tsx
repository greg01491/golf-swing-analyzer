import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Landmarks, PPosition, SessionDetail } from '../api'
import PPositionPanel from './PPositionPanel'
import SkeletonCanvas from './SkeletonCanvas'

export default function SessionView({ sessionId }: { sessionId: string }) {
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [landmarks, setLandmarks] = useState<Landmarks | null>(null)
  const [camera, setCamera] = useState<string>('camera_1')
  const [time, setTime] = useState(0)
  const [processState, setProcessState] = useState<string>('idle')
  const [selectedPosition, setSelectedPosition] = useState<PPosition | null>(null)
  const [showIdeal, setShowIdeal] = useState(true)
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

  if (!detail) return <div className="panel">loading…</div>

  const metrics = detail.metrics
  const createdAt = detail.metadata?.created_at as string | undefined
  const when = createdAt ? new Date(createdAt) : null

  return (
    <div className="session-view">
      <h2>
        {when
          ? `${when.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })} at ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
          : sessionId}
      </h2>

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
            key={`${sessionId}-${camera}`}
            ref={videoRef}
            src={api.videoUrl(sessionId, camera)}
            controls
            loop
            width={480}
          />
        </div>

        <div className="panel">
          <h3>3D skeleton</h3>
          {landmarks ? (
            <SkeletonCanvas
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
                    <td>
                      {m.value} {m.unit}
                    </td>
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
