import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Landmarks, SessionDetail } from '../api'
import SkeletonCanvas from './SkeletonCanvas'

export default function SessionView({ sessionId }: { sessionId: string }) {
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [landmarks, setLandmarks] = useState<Landmarks | null>(null)
  const [camera, setCamera] = useState<string>('camera_1')
  const [time, setTime] = useState(0)
  const [processState, setProcessState] = useState<string>('idle')
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    setDetail(null)
    setLandmarks(null)
    setProcessState('idle')
    api.session(sessionId).then((d) => {
      setDetail(d)
      if (d.cameras.length && !d.cameras.includes(camera)) setCamera(d.cameras[0])
    })
    api.landmarks(sessionId).then(setLandmarks).catch(() => setLandmarks(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

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

  return (
    <div className="session-view">
      <h2>{sessionId}</h2>

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
            <SkeletonCanvas landmarks={landmarks} time={time} />
          ) : (
            <p className="muted">no 3D data yet — run processing</p>
          )}
        </div>
      </div>

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
