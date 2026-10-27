import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import type {
  Landmarks,
  MarkerReviewLabel,
  MetricReviewLabel,
  PPosition,
  SessionPoseKeypoint,
  SessionReviewIssues,
  ReviewWhatIfResult,
  SessionDetail,
  SessionReviewAnnotations,
} from '../api'
import {
  eligibleTips,
  isValidatedMetric,
  metricReason,
  metricStatus,
  metricSummary,
} from '../metricFeedback'
import { METRIC_INFO, VIEW_LABELS, formatMetricName, type MetricView } from '../metricInfo'
import { clampPlaybackPercent, playbackRateForPercent, stepFrameTime, commonPlaybackDuration, clampSeekTime } from '../playback'
import { DEFAULT_CAMERA_VIEW, type CameraView, type Size } from '../videoFraming'
import { counterpartReviewTarget, groupReviewIssues, observationReview, queuedReviewIssues, reviewIssueTarget } from '../reviewIssues'
import PPositionPanel from './PPositionPanel'
import Skeleton3D from './Skeleton3D'
import SwingPlaneLine from './SwingPlaneLine'
import CameraViewport from './CameraViewport'

interface Props {
  sessionId: string
  onChanged?: () => void
  focusedMetric: string | null
  onFocusMetric: (metric: string | null) => void
}

const cameraLabel = (camera: string) => {
  if (camera === 'camera_1') return 'Down-the-line view'
  if (camera === 'camera_2') return 'Face-on view'
  return camera.replaceAll('_', ' ')
}

const REVIEW_MARKERS = [
  'Nose',
  'Neck',
  'Head',
  'LShoulder',
  'RShoulder',
  'LElbow',
  'RElbow',
  'LWrist',
  'RWrist',
  'Hip',
  'LHip',
  'RHip',
  'LKnee',
  'RKnee',
  'LAnkle',
  'RAnkle',
]

function FrameStepControls({
  frame,
  time,
  onStep,
  playing,
  duration,
  onToggle,
  onSeek,
}: {
  frame: number
  time: number
  onStep: (direction: -1 | 1) => void
  playing: boolean
  duration: number
  onToggle: () => void
  onSeek: (time: number) => void
}) {
  return (
    <div className="review-transport" role="group" aria-label="Playback controls">
      <div className="frame-step-controls">
      <button type="button" title="Previous frame" aria-label="Previous frame" disabled={!duration} onClick={() => onStep(-1)}>
        |&lt;
      </button>
      <button type="button" className="play-pause" title={playing ? 'Pause' : 'Play'} aria-label={playing ? 'Pause' : 'Play'} disabled={!duration} onClick={onToggle}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d={playing ? 'M6 4H10V20H6ZM14 4H18V20H14Z' : 'M7 4L20 12L7 20Z'} /></svg>
      </button>
      <button type="button" title="Next frame" aria-label="Next frame" disabled={!duration} onClick={() => onStep(1)}>
        &gt;|
      </button>
      </div>
      <label className="review-timeline">
        <span className="muted">frame {frame} @ {time.toFixed(3)}s / {duration.toFixed(3)}s</span>
        <input aria-label="Playback timeline" type="range" min={0} max={duration || 0} step="any" value={Math.min(time, duration)} disabled={!duration} onChange={(event) => onSeek(Number(event.target.value))} />
      </label>
    </div>
  )
}

const applyPlaybackRate = (video: HTMLVideoElement, percent: number) => {
  if (!video.isConnected) return
  if (percent <= 0) {
    video.pause()
    return
  }
  video.playbackRate = playbackRateForPercent(percent)
}

export default function SessionView({ sessionId, onChanged, focusedMetric, onFocusMetric }: Props) {
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [landmarks, setLandmarks] = useState<Landmarks | null>(null)
  const [review, setReview] = useState<SessionReviewAnnotations | null>(null)
  const [reviewCamera, setReviewCamera] = useState<'camera_1' | 'camera_2'>('camera_1')
  const [reviewMarker, setReviewMarker] = useState('')
  const [reviewMarkerLabel, setReviewMarkerLabel] = useState<MarkerReviewLabel | ''>('')
  const [reviewMarkerNote, setReviewMarkerNote] = useState('')
  const [reviewKeypoint, setReviewKeypoint] = useState<SessionPoseKeypoint | null>(null)
  const [reviewMetric, setReviewMetric] = useState('')
  const [reviewMetricLabel, setReviewMetricLabel] = useState<MetricReviewLabel | ''>('')
  const [reviewExpectedValue, setReviewExpectedValue] = useState('')
  const [reviewMetricNote, setReviewMetricNote] = useState('')
  const [reviewSaving, setReviewSaving] = useState(false)
  const [reviewLoadFailed, setReviewLoadFailed] = useState(false)
  const [reviewMessage, setReviewMessage] = useState<string | null>(null)
  const [reviewIssues, setReviewIssues] = useState<SessionReviewIssues | null>(null)
  const [reviewIssuesError, setReviewIssuesError] = useState<string | null>(null)
  const [issueMetricFilter, setIssueMetricFilter] = useState('')
  const [showAllSupport, setShowAllSupport] = useState(false)
  const [issueFrames, setIssueFrames] = useState<Record<string, number>>({})
  const [reviewSeek, setReviewSeek] = useState<{
    camera: 'camera_1' | 'camera_2'; marker: string; frame: number; time: number
  } | null>(null)
  const [whatIfSelected, setWhatIfSelected] = useState<Set<string>>(() => new Set())
  const [whatIfResult, setWhatIfResult] = useState<ReviewWhatIfResult | null>(null)
  const [whatIfRunning, setWhatIfRunning] = useState(false)
  const [whatIfError, setWhatIfError] = useState<string | null>(null)
  const [camera, setCamera] = useState<string>('camera_1')
  const [time, setTime] = useState(0)
  const [cameraTimes, setCameraTimes] = useState<Record<string, number>>({})
  const [videoSizes, setVideoSizes] = useState<Record<string, Size>>({})
  const [cameraViews, setCameraViews] = useState<Record<string, CameraView>>({})
  const [mediaState, setMediaState] = useState<Record<string, { duration: number; playing: boolean }>>({})
  const [playbackError, setPlaybackError] = useState<string | null>(null)
  const [processState, setProcessState] = useState<string>('idle')
  const [selectedPosition, setSelectedPosition] = useState<PPosition | null>(null)
  const [showIdeal, setShowIdeal] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)
  const [show3D, setShow3D] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [speed, setSpeed] = useState(() => {
    const stored = Number(localStorage.getItem('playback-speed'))
    return clampPlaybackPercent(stored)
  })
  const [labelDraft, setLabelDraft] = useState('')
  const [groupDraft, setGroupDraft] = useState('My Swings')
  const [savingMeta, setSavingMeta] = useState(false)
  const [proMode, setProMode] = useState(() => localStorage.getItem('pro-mode') === 'on')
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({})
  const reviewFrameRef = useRef(0)

  useEffect(() => {
    localStorage.setItem('pro-mode', proMode ? 'on' : 'off')
  }, [proMode])

  useEffect(() => {
    localStorage.setItem('playback-speed', String(speed))
  }, [speed])

  useEffect(() => {
    setDetail(null)
    setLandmarks(null)
    setProcessState('idle')
    setSelectedPosition(null)
    setVideoSizes({})
    setCameraViews({})
    setMediaState({})
    setPlaybackError(null)
    setTime(0)
    setCameraTimes({})
    setReview(null)
    setReviewLoadFailed(false)
    setReviewMessage(null)
    setReviewIssues(null)
    setReviewIssuesError(null)
    setIssueMetricFilter('')
    setShowAllSupport(false)
    setIssueFrames({})
    setReviewSeek(null)
    setWhatIfSelected(new Set())
    setWhatIfResult(null)
    setWhatIfError(null)
    api.session(sessionId).then((d) => {
      setDetail(d)
      setLabelDraft((d.metadata?.label as string) ?? '')
      setGroupDraft((d.metadata?.group as string) ?? 'My Swings')
      if (d.cameras.length && !d.cameras.includes(camera)) setCamera(d.cameras[0])
      if (d.cameras.includes('camera_1')) setReviewCamera('camera_1')
      else if (d.cameras.includes('camera_2')) setReviewCamera('camera_2')
    })
    api
      .sessionReview(sessionId)
      .then(setReview)
      .catch((error) => {
        setReviewLoadFailed(true)
        setReviewMessage(`Could not load saved review annotations; editing is disabled. ${String(error)}`)
      })
    api
      .landmarks(sessionId)
      .then(setLandmarks)
      .catch(() => setLandmarks(null))
    // reflect any in-progress/failed auto-processing kicked off at capture,
    // so the panel shows "processing…" or the error rather than a stale
    // "process swing" button (the video itself plays regardless)
    api.processStatus(sessionId).then(({ status }) => {
      if (status !== 'idle') setProcessState(status)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const selectPosition = (position: PPosition) => {
    if (position.available === false) return
    setSelectedPosition(position)
    for (const video of Object.values(videoRefs.current)) {
      if (video) {
        video.pause()
        if (video.readyState >= 1) video.currentTime = clampSeekTime(position.time_s, video.duration, playbackFrameRate())
      }
    }
  }

  const cameraKey = detail?.cameras.join('|') ?? ''

  // drive skeleton time from the video element
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const video = videoRefs.current[proMode ? cameraKey.split('|')[0] : camera]
      if (video && video.readyState >= 1) setTime(video.currentTime)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [camera, cameraKey, proMode])

  useEffect(() => {
    let cancelled = false
    const callbacks = new Map<HTMLVideoElement, number>()
    const cameras = proMode ? cameraKey.split('|').filter(Boolean) : [camera]

    const watchPresentedFrames = (cameraName: string, video: HTMLVideoElement) => {
      if (typeof video.requestVideoFrameCallback !== 'function') return
      const callbackId = video.requestVideoFrameCallback((_now, metadata) => {
        if (cancelled) return
        setCameraTimes((previous) => ({ ...previous, [cameraName]: metadata.mediaTime }))
        watchPresentedFrames(cameraName, video)
      })
      callbacks.set(video, callbackId)
    }

    for (const cameraName of cameras) {
      const video = videoRefs.current[cameraName]
      if (video) watchPresentedFrames(cameraName, video)
    }

    return () => {
      cancelled = true
      for (const [video, callbackId] of callbacks) {
        video.cancelVideoFrameCallback(callbackId)
      }
    }
  }, [camera, cameraKey, proMode, sessionId, showOverlay])

  // apply the slow-motion playback rate (100% = normal, 0% = paused) to
  // every currently mounted video -- in Pro Mode that's both camera views
  useEffect(() => {
    for (const video of Object.values(videoRefs.current)) {
      if (video) applyPlaybackRate(video, speed)
    }
  }, [speed])

  // poll processing status while running
  useEffect(() => {
    if (processState !== 'running') return
    const id = setInterval(async () => {
      const { status } = await api.processStatus(sessionId)
      setProcessState(status)
      if (status === 'done') {
        api.session(sessionId).then(setDetail)
        api
          .landmarks(sessionId)
          .then(setLandmarks)
          .catch(() => setLandmarks(null))
      }
    }, 500)
    return () => clearInterval(id)
  }, [processState, sessionId])

  const overlayAvailable = (detail?.overlay_cameras ?? []).includes(camera)
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
  useEffect(() => {
    setMediaState({})
    setPlaybackError(null)
  }, [videoSources, camera, proMode])
  useEffect(() => {
    if (!detail?.metrics || processState === 'running') return
    let active = true
    setReviewIssues(null)
    setReviewIssuesError(null)
    api.sessionReviewIssues(sessionId).then(
      (result) => { if (active) setReviewIssues(result) },
      (error) => { if (active) setReviewIssuesError(String(error)) },
    )
    return () => { active = false }
  }, [sessionId, detail, processState])

  useEffect(() => {
    if (!reviewSeek) return
    const video = videoRefs.current[reviewSeek.camera]
    if (!video) return
    const finish = () => {
      setCameraTimes((previous) => ({ ...previous, [reviewSeek.camera]: video.currentTime }))
      setReviewSeek((current) => current === reviewSeek ? null : current)
    }
    const seek = () => {
      for (const current of Object.values(videoRefs.current)) current?.pause()
      setSelectedPosition(null)
      if (!video.seeking && Math.abs(video.currentTime - reviewSeek.time) < 0.000001) finish()
      else video.currentTime = reviewSeek.time
    }
    video.addEventListener('seeked', finish, { once: true })
    if (video.readyState >= 1) seek()
    else video.addEventListener('loadedmetadata', seek, { once: true })
    return () => {
      video.removeEventListener('loadedmetadata', seek)
      video.removeEventListener('seeked', finish)
    }
  }, [reviewSeek, camera, proMode, videoSources])

  const frameRateForCamera = (cameraName: string) => {
    const cameraMetadata = detail?.metadata.cameras as
      | Record<string, { fps?: number }>
      | undefined
    const fps = cameraMetadata?.[cameraName]?.fps ?? landmarks?.fps
    return fps && Number.isFinite(fps) && fps > 0 ? fps : 30
  }
  const playbackFrameRate = () =>
    frameRateForCamera(proMode ? detail?.cameras[0] ?? camera : camera)

  const reviewTime =
    cameraTimes[reviewCamera] ?? videoRefs.current[reviewCamera]?.currentTime ?? time
  const reviewFrame = Math.max(
    0,
    Math.round(reviewTime * frameRateForCamera(reviewCamera)),
  )
  reviewFrameRef.current = reviewFrame

  useEffect(() => {
    const annotation = observationReview(
      review?.marker_annotations ?? [], reviewCamera, reviewMarker, reviewFrame,
    )
    setReviewMarkerLabel(annotation?.label ?? '')
    setReviewMarkerNote(annotation?.note ?? '')
  }, [review, reviewCamera, reviewMarker, reviewFrame])

  const issueGroups = useMemo(
    () => groupReviewIssues(queuedReviewIssues(reviewIssues, showAllSupport)),
    [reviewIssues, showAllSupport],
  )

  useEffect(() => {
    setReviewKeypoint(null)
    if (!reviewMarker) return
    let active = true
    let latestRequest = 0
    let lastFrame = -1
    const refreshKeypoint = async () => {
      const frameIndex = reviewFrameRef.current
      if (frameIndex === lastFrame) return
      lastFrame = frameIndex
      const requestId = ++latestRequest
      try {
        const point = await api.sessionKeypoint(sessionId, reviewCamera, frameIndex, reviewMarker)
        if (!active || requestId !== latestRequest || frameIndex !== reviewFrameRef.current) return
        setReviewKeypoint(point)
      } catch {
        if (active && requestId === latestRequest) setReviewKeypoint(null)
      }
    }
    void refreshKeypoint()
    const interval = setInterval(() => void refreshKeypoint(), 100)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [sessionId, reviewCamera, reviewMarker])

  const reviewKeypointStyle = (cameraName: string) => {
    const point = reviewKeypoint
    if (
      !point ||
      point.camera !== cameraName ||
      point.frame_index !== reviewFrameRef.current ||
      point.width <= 0 ||
      point.height <= 0
    ) {
      return undefined
    }
    return {
      left: `${(point.x / point.width) * 100}%`,
      top: `${(point.y / point.height) * 100}%`,
    }
  }

  const saveMarkerReview = async () => {
    if (!review || reviewLoadFailed || !reviewMarker || !reviewMarkerLabel) return
    const current = review
    const annotation = {
      camera: reviewCamera,
      frame_index: reviewFrame,
      marker: reviewMarker,
      label: reviewMarkerLabel,
      note: reviewMarkerNote.trim() || null,
    }
    const next = {
      ...current,
      marker_annotations: [
        ...current.marker_annotations.filter(
          (item) =>
            item.camera !== annotation.camera ||
            item.frame_index !== annotation.frame_index ||
            item.marker !== annotation.marker,
        ),
        annotation,
      ],
    }
    setReviewSaving(true)
    setReviewMessage(null)
    try {
      setReview(await api.saveSessionReview(sessionId, next))
      setReviewMessage(
        `${cameraLabel(reviewCamera)}, frame ${reviewFrame}: ${reviewMarker} marked ${reviewMarkerLabel}.`,
      )
    } catch (error) {
      setReviewMessage(String(error))
    } finally {
      setReviewSaving(false)
    }
  }

  const saveMetricReview = async () => {
    if (!review || reviewLoadFailed || !detail?.metrics || !reviewMetric || !reviewMetricLabel) return
    const metric = detail.metrics.metrics.find((item) => item.name === reviewMetric)
    if (!metric) return
    const expectedValue = reviewExpectedValue.trim() ? Number(reviewExpectedValue) : null
    if (expectedValue !== null && !Number.isFinite(expectedValue)) {
      setReviewMessage('Expected value must be a finite number.')
      return
    }
    const definitionId = metric.definition_id ?? `legacy:${metric.name}`
    const current = review
    const annotation = {
      metric: metric.name,
      definition_id: definitionId,
      label: reviewMetricLabel,
      expected_value: expectedValue,
      unit: metric.unit,
      note: reviewMetricNote.trim() || null,
    }
    const next = {
      ...current,
      metric_annotations: [
        ...current.metric_annotations.filter(
          (item) => item.metric !== annotation.metric || item.definition_id !== definitionId,
        ),
        annotation,
      ],
    }
    setReviewSaving(true)
    setReviewMessage(null)
    try {
      setReview(await api.saveSessionReview(sessionId, next))
      setReviewMessage(`${formatMetricName(metric.name)} review saved.`)
    } catch (error) {
      setReviewMessage(String(error))
    } finally {
      setReviewSaving(false)
    }
  }

  const markerReviewKey = (annotation: {
    camera: string
    frame_index: number
    marker: string
  }) => `${annotation.camera}/${annotation.frame_index}/${annotation.marker}`

  const runReviewWhatIf = async () => {
    const exclusions = (review?.marker_annotations ?? []).filter((annotation) =>
      whatIfSelected.has(markerReviewKey(annotation)),
    )
    if (!review || reviewLoadFailed || !exclusions.length) return
    setWhatIfRunning(true)
    setWhatIfError(null)
    setWhatIfResult(null)
    try {
      setWhatIfResult(await api.sessionReviewWhatIf(sessionId, exclusions))
    } catch (error) {
      setWhatIfError(String(error))
    } finally {
      setWhatIfRunning(false)
    }
  }

  const syncProVideos = (action: 'play' | 'pause' | 'seek' | 'rate') => {
    if (!proMode) return
    const primary = videoRefs.current[detail?.cameras[0] ?? '']
    if (!primary) return
    for (const [cam, video] of Object.entries(videoRefs.current)) {
      if (!video || cam === detail?.cameras[0]) continue
      if (Math.abs(video.currentTime - primary.currentTime) > 0.05) {
        if (video.readyState >= 1) video.currentTime = clampSeekTime(primary.currentTime, video.duration, frameRateForCamera(cam))
      }
      applyPlaybackRate(video, speed)
      if (action === 'play') void video.play().catch((error) => reportPlaybackError(error))
      if (action === 'pause') video.pause()
    }
  }

  const activeCameras = proMode ? detail?.cameras ?? [] : [camera]
  const leaderCamera = activeCameras[0]
  const duration = commonPlaybackDuration(activeCameras.map((cam) => mediaState[cam]?.duration ?? 0))
  const playing = mediaState[leaderCamera]?.playing ?? false

  const reportPlaybackError = (error: unknown) => {
    for (const video of Object.values(videoRefs.current)) video?.pause()
    setPlaybackError(`Could not play recording: ${String(error)}`)
  }
  const updateMediaState = (cam: string, video: HTMLVideoElement) => {
    setMediaState((previous) => ({
      ...previous,
      [cam]: {
        duration: video.readyState >= 1 ? video.duration : 0,
        playing: !video.paused && !video.ended,
      },
    }))
  }
  const seekPlayback = (target: number) => {
    if (!duration) return
    const next = clampSeekTime(target, duration, playbackFrameRate())
    for (const cam of activeCameras) {
      const video = videoRefs.current[cam]
      if (video && video.readyState >= 1) video.currentTime = next
    }
    setSelectedPosition(null)
    setTime(next)
  }
  const togglePlayback = () => {
    const leader = videoRefs.current[leaderCamera]
    if (!leader || !duration) return
    setPlaybackError(null)
    if (!leader.paused) {
      for (const cam of activeCameras) videoRefs.current[cam]?.pause()
    } else {
      if (speed === 0) setSpeed(100)
      for (const cam of activeCameras) {
        const video = videoRefs.current[cam]
        if (!video) continue
        applyPlaybackRate(video, speed || 100)
        void video.play().catch((error) => reportPlaybackError(error))
      }
    }
  }

  const stepFrame = (direction: -1 | 1) => {
    const cameraNames = proMode ? detail?.cameras ?? [] : [camera]
    const videos = cameraNames
      .map((name) => videoRefs.current[name])
      .filter((video): video is HTMLVideoElement => video !== null && video !== undefined)
    if (videos.length === 0) return

    const primaryCamera = proMode ? detail?.cameras[0] : camera
    const primary = primaryCamera ? videoRefs.current[primaryCamera] ?? videos[0] : videos[0]
    const fps = playbackFrameRate()
    if (!duration) return
    const targetTime = stepFrameTime(primary.currentTime, fps, direction, duration)

    for (const video of videos) {
      video.pause()
      video.currentTime = targetTime
    }
    setSelectedPosition(null)
    setTime(targetTime)
  }

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
      setVideoSizes({})
    } catch {
      // best-effort; a failed unlink leaves the clip in place
    } finally {
      setDeleting(false)
    }
  }

  if (!detail) return <div className="panel">loading…</div>

  const metrics = detail.metrics
  const tips = metrics ? eligibleTips(metrics) : []
  const quality = metrics?.tracking_quality
  const ball = metrics?.ball
  const addressTime = metrics?.phases ? metrics.phases.address_frame / (landmarks?.fps ?? 1) : null
  const createdAt = detail.metadata?.created_at as string | undefined
  const club = (metrics?.club ?? detail.metadata?.club) as string | undefined
  const when = createdAt ? new Date(createdAt) : null
  const renderCamera = (cam: string) => {
    const primary = cam === leaderCamera
    const size = videoSizes[cam]
    return (
      <CameraViewport
        key={`${sessionId}:${cam}`}
        label={cameraLabel(cam)}
        imageSize={size}
        view={cameraViews[cam] ?? DEFAULT_CAMERA_VIEW}
        onChange={(view) => setCameraViews((previous) => ({ ...previous, [cam]: view }))}
        onError={setPlaybackError}
      >
        {(toolbar) => (
          <>
            <video
              ref={(node) => { videoRefs.current[cam] = node }}
              src={videoSources[cam]}
              loop
              playsInline
              onLoadedMetadata={(event) => {
                const video = event.currentTarget
                applyPlaybackRate(video, speed)
                setVideoSizes((previous) => ({ ...previous, [cam]: { width: video.videoWidth, height: video.videoHeight } }))
                video.currentTime = clampSeekTime(time, video.duration, frameRateForCamera(cam))
                updateMediaState(cam, video)
              }}
              onDurationChange={(event) => updateMediaState(cam, event.currentTarget)}
              onEmptied={(event) => updateMediaState(cam, event.currentTarget)}
              onPlay={(event) => {
                updateMediaState(cam, event.currentTarget)
                if (primary) syncProVideos('play')
              }}
              onPause={(event) => {
                updateMediaState(cam, event.currentTarget)
                if (primary) syncProVideos('pause')
              }}
              onSeeked={(event) => {
                const currentTime = event.currentTarget.currentTime
                setCameraTimes((previous) => ({ ...previous, [cam]: currentTime }))
                if (primary) syncProVideos('seek')
              }}
              onRateChange={() => { if (primary) syncProVideos('rate') }}
              onTimeUpdate={(event) => {
                if (!primary) return
                const video = event.currentTarget
                if (!video.paused && duration && video.currentTime >= duration - 1 / playbackFrameRate()) {
                  seekPlayback(0)
                } else syncProVideos('seek')
              }}
              onError={(event) => reportPlaybackError(event.currentTarget.error?.message ?? `${cameraLabel(cam)} recording could not be loaded.`)}
            />
            {reviewMarker && reviewKeypointStyle(cam) && (
              <div className="marker-review-pulse" style={reviewKeypointStyle(cam)} title={`${reviewMarker}, ${Math.round((reviewKeypoint?.confidence ?? 0) * 100)}% 2D confidence`} />
            )}
            {ball?.detected && ball.address_xy && ball.source_camera === cam && size && addressTime != null && Math.abs(time - addressTime) < 0.15 && (
              <div
                className="ball-marker"
                style={{ left: `${(ball.address_xy[0] / size.width) * 100}%`, top: `${(ball.address_xy[1] / size.height) * 100}%` }}
                title={`ball detected at address (${ball.impact_source})`}
              />
            )}
            <SwingPlaneLine camera={cam} toolbarTarget={toolbar} />
          </>
        )}
      </CameraViewport>
    )
  }

  return (
    <div
      className="session-view"
      onKeyDown={(event) => {
        if (event.target instanceof HTMLElement &&
          event.target.closest('button, input, select, textarea, [contenteditable="true"]')) return
        if (event.code === 'Space') {
          event.preventDefault()
          togglePlayback()
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault()
          stepFrame(event.key === 'ArrowLeft' ? -1 : 1)
        }
      }}
    >
      <div className="session-heading">
        <h2>
          {detail.metadata?.label
            ? (detail.metadata.label as string)
            : when
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

      {quality && (!quality.reliable || (quality.advisories?.length ?? 0) > 0) && (
        <div className="panel quality-warning">
          <strong>
            {quality.reliable
              ? 'Tracking confidence advisory — some keypoints are less certain.'
              : '⚠ Low tracking quality — metrics and positions below may be unreliable.'}
          </strong>
          {quality.swing_moving_fraction != null && (
            <p className="muted">
              Hand motion: {Math.round(quality.swing_moving_fraction * 100)}% from address to
              impact; {Math.round(quality.moving_fraction * 100)}% across the full clip.
            </p>
          )}
          {quality.camera_wrist_visibility && (
            <ul>
              {Object.entries(quality.camera_wrist_visibility).map(([camera, wrists]) => (
                <li key={camera}>
                  {cameraLabel(camera)} wrist confidence: left {Math.round(wrists.LWrist * 100)}%,
                  right {Math.round(wrists.RWrist * 100)}%.
                </li>
              ))}
            </ul>
          )}
          {quality.warnings.length > 0 && (
            <ul>
              {quality.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
          {(quality.advisories?.length ?? 0) > 0 && (
            <ul>
              {quality.advisories?.map((advisory) => (
                <li key={advisory}>{advisory}</li>
              ))}
            </ul>
          )}
          <p className="muted">
            {quality.reliable
              ? 'These keypoints are still accepted for 3D tracking; the advisory means their positions may be less precise. Improve wrist visibility, framing, or lighting if possible.'
              : 'The video and skeleton are still shown, but some positions may be unreliable. Use the specific causes above: improve wrist visibility, framing, or lighting for camera warnings. Recalibrate only when the warning identifies physically impossible hand travel.'}
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
          reliable={quality?.reliable !== false}
        />
      )}
      {playbackError && <p className="error" role="alert">{playbackError}</p>}

      {detail.cameras.length === 0 ? (
        <div className="panel">
          <p className="muted">
            Videos removed to save space. Your stats are kept — see the metrics and the stats tab.
          </p>
        </div>
      ) : proMode ? (
        <>
          <div className="pro-playback-grid">
            {detail.cameras.map((cam) => (
              <div className="panel pro-camera" key={cam}>
                <h3>{cameraLabel(cam)}</h3>
                {renderCamera(cam)}
                <span className="muted sync-label">
                  frame {Math.round((cameraTimes[cam] ?? videoRefs.current[cam]?.currentTime ?? 0) * frameRateForCamera(cam))}{' '}
                  @ {(cameraTimes[cam] ?? videoRefs.current[cam]?.currentTime ?? 0).toFixed(3)}s
                </span>
              </div>
            ))}
          </div>
          <div className="video-controls">
            <FrameStepControls
              frame={Math.round(time * playbackFrameRate())}
              time={time}
              onStep={stepFrame}
              playing={playing}
              duration={duration}
              onToggle={togglePlayback}
              onSeek={seekPlayback}
            />
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
            <label className="speed-control">
              slow motion
              <input
                type="range"
                min={0}
                max={100}
                step={0.25}
                value={speed}
                onChange={(e) => setSpeed(clampPlaybackPercent(Number(e.target.value)))}
              />
              <span className="speed-value">{speed}%</span>
            </label>
          </div>
        </>
      ) : (
        <div className="playback-row">
          <div className="panel video-panel">
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
            {renderCamera(camera)}
            <div className="video-controls">
              <FrameStepControls
                frame={Math.round(time * playbackFrameRate())}
                time={time}
                onStep={stepFrame}
                playing={playing}
                duration={duration}
                onToggle={togglePlayback}
                onSeek={seekPlayback}
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
              <label className="speed-control">
                slow motion
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={0.25}
                  value={speed}
                  onChange={(e) => setSpeed(clampPlaybackPercent(Number(e.target.value)))}
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
          </div>
        </div>
      )}

      {detail.cameras.length > 0 && (
        <section className="panel manual-review-panel">
          <div className="metrics-heading">
            <h3>manual review</h3>
          </div>
          <p className="muted">
            Labels are saved separately and do not change this session's analysis.
          </p>
          {detail.metrics && (
            <div className="review-issue-section">
              <h4>Outside tracking tolerances</h4>
              {reviewIssuesError ? (
                <p className="error" role="alert">{reviewIssuesError}</p>
              ) : !reviewIssues ? (
                <p className="muted" role="status">Checking metric evidence...</p>
              ) : (
                <>
                  <p className="muted review-diagnostic-note">{reviewIssues.warning}</p>
                  {reviewIssues.tolerance_check?.available === false && <p className="muted">Camera-tolerance evidence unavailable: {reviewIssues.tolerance_check.reason}</p>}
                  <div className="manual-review-fields review-issue-filter">
                    <label>
                      Affected metric
                      <select aria-label="Affected metric" value={issueMetricFilter} onChange={(event) => setIssueMetricFilter(event.target.value)}>
                        <option value="">all metrics</option>
                        {detail.metrics.metrics.map((metric) => (
                          <option key={metric.name} value={metric.name}>{formatMetricName(metric.name)}</option>
                        ))}
                      </select>
                    </label>
                    <span className="muted">{issueGroups.filter((group) => !issueMetricFilter || group.metrics.includes(issueMetricFilter)).length} observation groups</span>
                  </div>
                  <label className="what-if-exclusion-toggle review-support-toggle">
                    <input type="checkbox" checked={showAllSupport} onChange={(event) => setShowAllSupport(event.target.checked)} />
                    Show all support rejections
                  </label>
                  <div className="review-issue-table-wrap" role="region" aria-label="Metric observation issues" tabIndex={0}>
                    <table className="what-if-table review-issue-table">
                      <thead>
                        <tr><th>Affected metric / saved result</th><th>Marker</th><th>View to inspect</th><th>Frames / time</th><th>Evidence</th><th>Review</th></tr>
                      </thead>
                      <tbody>
                        {issueGroups.filter((group) => !issueMetricFilter || group.metrics.includes(issueMetricFilter)).map((group) => {
                          const frame = issueFrames[group.key] ?? group.worst_frame_index ?? group.frame_indices[0] ?? -1
                          const measurement = group.measurements?.[frame]
                          const annotation = observationReview(review?.marker_annotations ?? [], group.camera, group.marker, frame)
                          const pairedTarget = counterpartReviewTarget(group, frame, (detail.metadata.cameras ?? {}) as Record<string, { fps?: number }>)
                          const counterpart = pairedTarget && detail.cameras.includes(pairedTarget.camera) ? pairedTarget : null
                          const counterpartAnnotation = counterpart ? observationReview(review?.marker_annotations ?? [], counterpart.camera, counterpart.marker, counterpart.frame) : undefined
                          const counterpartFlagged = counterpart && reviewIssues.tolerance_issues?.some((issue) => issue.camera === counterpart.camera && issue.marker === counterpart.marker && issue.frame_indices.includes(counterpart.frame))
                          const reviewedCount = group.frame_indices.filter((index) => observationReview(review?.marker_annotations ?? [], group.camera, group.marker, index)).length
                          const inspect = (index: number, paired = false) => {
                            const target = paired ? counterpart : reviewIssueTarget(group, index)
                            if (!target) return
                            setReviewSeek(target)
                            setReviewCamera(target.camera)
                            setReviewMarker(target.marker)
                            setCamera(target.camera)
                            setShowOverlay(true)
                            setSpeed(0)
                            setReviewMetric(group.metrics[0])
                          }
                          return (
                            <tr key={group.key}>
                              <td>{group.metrics.map((name) => {
                                const saved = detail.metrics?.metrics.find((metric) => metric.name === name)
                                const diagnostic = reviewIssues.metrics.find((metric) => metric.name === name)
                                return <div className="review-issue-metric" key={name}>
                                  <strong>{formatMetricName(name)}</strong>
                                  <span className="muted">Saved: {saved?.value == null ? 'unavailable' : `${saved.value} ${saved.unit}`} ({saved ? metricStatus(saved) : 'unknown'})</span>
                                  <span className="muted">Diagnostic: {diagnostic?.status ?? 'unknown'}</span>
                                </div>
                              })}</td>
                              <td>{group.marker ?? 'Combined geometry'}</td>
                              <td>{group.camera ? cameraLabel(group.camera) : 'Not isolated'}</td>
                              <td>
                                {group.frame_indices.length && group.fps ? <>
                                  <span className="review-issue-span">{group.frame_indices[0]} - {group.frame_indices.at(-1)} ({group.frame_indices.length} frames)</span>
                                  <select
                                    aria-label={`Frame for ${group.marker} in ${group.camera} for ${group.metrics.join(', ')}`}
                                    value={frame}
                                    onChange={(event) => {
                                      const next = Number(event.target.value)
                                      setIssueFrames((previous) => ({ ...previous, [group.key]: next }))
                                      inspect(next)
                                    }}
                                  >
                                    {group.frame_indices.map((index) => <option key={index} value={index}>{index} @ {(index / group.fps!).toFixed(3)}s{observationReview(review?.marker_annotations ?? [], group.camera, group.marker, index) ? ' (saved)' : ''}</option>)}
                                  </select>
                                </> : <span className="muted">{group.start_time_s.toFixed(3)} - {group.end_time_s.toFixed(3)}s<br />{group.mapping_reason}</span>}
                              </td>
                              <td>
                                {measurement?.reason ?? group.reason}
                                {measurement && <strong className="review-issue-span">{measurement.value.toFixed(2)} {measurement.unit}; allowed {measurement.unit === 'score' ? '>=' : measurement.unit === 'm' ? '>' : '<='} {measurement.threshold.toFixed(2)} {measurement.unit}</strong>}
                                <span className="muted review-issue-span">{measurement ? 'Geometry/calibration may also be responsible' : 'No isolated camera-tolerance failure'}</span>
                              </td>
                              <td>
                                <strong className="review-issue-span">{group.camera ? cameraLabel(group.camera) : 'Source view'}</strong>
                                <button type="button" disabled={!reviewIssueTarget(group, frame) || reviewSaving} onClick={() => inspect(frame)} aria-label={`Review ${group.marker ?? 'geometry'} in ${group.camera ?? 'unknown camera'} at frame ${frame}`}>Review</button>
                                <span className="review-issue-span" title={annotation?.note ?? undefined}>{annotation?.label ?? 'not reviewed'}</span>
                                <span className="muted review-issue-span">{reviewedCount}/{group.frame_indices.length} saved</span>
                                <div className="review-counterpart">
                                  {counterpart ? <>
                                    <strong className="review-issue-span">{cameraLabel(counterpart.camera)}</strong>
                                    <span className="review-issue-span">frame {counterpart.frame}</span>
                                    <span className="muted review-issue-span">{counterpartFlagged ? 'Also outside tolerance' : 'Comparison view (not flagged)'}</span>
                                    <button type="button" disabled={reviewSaving} onClick={() => inspect(frame, true)} aria-label={`Review counterpart ${counterpart.marker} in ${counterpart.camera} at frame ${counterpart.frame}`}>Review counterpart</button>
                                    <span className="review-issue-span" title={counterpartAnnotation?.note ?? undefined}>{counterpartAnnotation?.label ?? 'not reviewed'}</span>
                                    <span className="muted review-issue-span">Clip-time match; sync unverified</span>
                                  </> : <span className="muted">Counterpart frame mapping unavailable</span>}
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                    {!issueGroups.some((group) => !issueMetricFilter || group.metrics.includes(issueMetricFilter)) && <p className="muted">{showAllSupport ? 'No support rejections identified for this selection.' : 'No measured camera-tolerance failures identified for this selection.'}</p>}
                  </div>
                  {reviewIssues.blockers.length > 0 && (
                    <details className="review-other-blockers">
                      <summary>Other metric blockers (current settings)</summary>
                      <ul className="manual-review-list">{reviewIssues.blockers.filter((blocker) => !issueMetricFilter || blocker.metric === issueMetricFilter).map((blocker) => <li key={blocker.metric}><strong>{formatMetricName(blocker.metric)}</strong>: {blocker.reasons.join('; ')}</li>)}</ul>
                    </details>
                  )}
                  {detail.metrics.metrics.some((metric) => isValidatedMetric(metric) && metric.in_range === false) && (
                    <details className="review-other-blockers">
                      <summary>Outside target in saved results (not a tracking failure)</summary>
                      <ul className="manual-review-list">{detail.metrics.metrics.filter((metric) => isValidatedMetric(metric) && metric.in_range === false).map((metric) => <li key={metric.name}>{formatMetricName(metric.name)}: {metric.value} {metric.unit}; target {metric.range?.min} - {metric.range?.max}</li>)}</ul>
                    </details>
                  )}
                </>
              )}
            </div>
          )}
          <div className="manual-review-fields">
            <label>
              Camera
              <select
                value={reviewCamera}
                onChange={(event) => {
                  const next = event.target.value as 'camera_1' | 'camera_2'
                  setReviewCamera(next)
                  if (!proMode) setCamera(next)
                }}
              >
                {detail.cameras.map((name) => (
                  <option key={name} value={name}>
                    {cameraLabel(name)}
                  </option>
                ))}
              </select>
            </label>
            <span className="manual-review-frame">
              frame {reviewFrame} @ {reviewTime.toFixed(3)}s
            </span>
            <label>
              Marker
              <select
                value={reviewMarker}
                onChange={(event) => {
                  const marker = event.target.value
                  setReviewMarker(marker)
                }}
              >
                <option value="">select marker</option>
                {(landmarks?.marker_names ?? REVIEW_MARKERS).map((name) => (
                  <option key={name} value={name}>
                    {formatMetricName(name)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Observation
              <select
                value={reviewMarkerLabel}
                onChange={(event) => setReviewMarkerLabel(event.target.value as MarkerReviewLabel | '')}
              >
                <option value="">select assessment</option>
                <option value="correct">correct</option>
                <option value="occluded">occluded</option>
                <option value="mislocalized">mislocalized</option>
                <option value="uncertain">uncertain</option>
              </select>
            </label>
            <label className="manual-review-note">
              Note
              <input
                type="text"
                maxLength={2000}
                value={reviewMarkerNote}
                onChange={(event) => setReviewMarkerNote(event.target.value)}
                placeholder="optional"
              />
            </label>
            <button
              type="button"
              disabled={!review || reviewLoadFailed || !reviewMarker || !reviewMarkerLabel || reviewSaving || reviewSeek !== null}
              onClick={() => void saveMarkerReview()}
            >
              {reviewSaving ? 'saving…' : 'save marker review'}
            </button>
          </div>
          {reviewMessage && <p className="muted" role="status">{reviewMessage}</p>}
          {review?.marker_annotations.length ? (
            <ul className="manual-review-list">
              {review.marker_annotations.map((annotation) => (
                <li
                  key={`${annotation.camera}-${annotation.frame_index}-${annotation.marker}`}
                >
                  {cameraLabel(annotation.camera)}, frame {annotation.frame_index}: {annotation.marker}{' '}
                  <strong>{annotation.label}</strong>
                  {annotation.note ? `, ${annotation.note}` : ''}
                  <label className="what-if-exclusion-toggle">
                    <input
                      type="checkbox"
                      checked={whatIfSelected.has(markerReviewKey(annotation))}
                      onChange={(event) => {
                        const key = markerReviewKey(annotation)
                        setWhatIfSelected((previous) => {
                          const next = new Set(previous)
                          if (event.target.checked) next.add(key)
                          else next.delete(key)
                          return next
                        })
                        setWhatIfResult(null)
                      }}
                    />
                    exclude in what-if
                  </label>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="what-if-actions">
            <button
              type="button"
              disabled={!review || reviewLoadFailed || !whatIfSelected.size || whatIfRunning}
              onClick={() => void runReviewWhatIf()}
            >
              {whatIfRunning ? 'calculating…' : 'run what-if metrics'}
            </button>
            {whatIfError && <span className="error" role="alert">{whatIfError}</span>}
          </div>
          {whatIfResult && (
            <div className="what-if-result" role="status">
              <h4>What-if analysis (diagnostic only)</h4>
              <p className="muted">{whatIfResult.warning}</p>
              <ul className="manual-review-list">
                {whatIfResult.exclusions.map((item) => (
                  <li key={`${item.camera}-${item.frame_index}-${item.marker}`}>
                    excluded {cameraLabel(item.camera)} frame {item.frame_index}, {item.marker};
                    masked TRC frame {item.trc_frame_index} ({item.trc_time_s.toFixed(3)}s)
                  </li>
                ))}
              </ul>
              <div className="what-if-table-wrap">
                <table className="what-if-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Original</th>
                      <th>What-if</th>
                    </tr>
                  </thead>
                  <tbody>
                    {whatIfResult.metrics.map((whatIfMetric) => {
                      const original = metrics?.metrics.find(
                        (item) => item.name === whatIfMetric.name,
                      )
                      const formatValue = (item: typeof whatIfMetric | undefined) => {
                        if (!item || item.value === null || metricStatus(item) === 'unavailable') {
                          return 'unavailable'
                        }
                        return `${item.value} ${item.unit} (${metricStatus(item)})`
                      }
                      return (
                        <tr key={whatIfMetric.name}>
                          <td>{formatMetricName(whatIfMetric.name)}</td>
                          <td>{formatValue(original)}</td>
                          <td>
                            {formatValue(whatIfMetric)}
                            {whatIfMetric.reasons?.length ? (
                              <small className="muted what-if-reason">
                                {metricReason(whatIfMetric)}
                              </small>
                            ) : null}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <div className="manual-review-metric">
            <h4>Metric result</h4>
            <div className="manual-review-fields">
              <label>
                Metric
                <select
                  value={reviewMetric}
                  onChange={(event) => {
                    const name = event.target.value
                    setReviewMetric(name)
                    const metric = metrics?.metrics.find((item) => item.name === name)
                    const definitionId = metric?.definition_id ?? `legacy:${name}`
                    const annotation = review?.metric_annotations.find(
                      (item) => item.metric === name && item.definition_id === definitionId,
                    )
                    setReviewMetricLabel(annotation?.label ?? '')
                    setReviewExpectedValue(
                      annotation?.expected_value == null ? '' : String(annotation.expected_value),
                    )
                    setReviewMetricNote(annotation?.note ?? '')
                  }}
                  disabled={!metrics}
                >
                  <option value="">select metric</option>
                  {metrics?.metrics.map((metric) => (
                    <option key={metric.name} value={metric.name}>
                      {formatMetricName(metric.name)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Judgment
                <select
                  value={reviewMetricLabel}
                  onChange={(event) => setReviewMetricLabel(event.target.value as MetricReviewLabel | '')}
                >
                  <option value="">select judgment</option>
                  <option value="correct">correct</option>
                  <option value="incorrect">incorrect</option>
                  <option value="uncertain">uncertain</option>
                </select>
              </label>
              <label>
                Expected value
                <input
                  type="number"
                  step="any"
                  value={reviewExpectedValue}
                  onChange={(event) => setReviewExpectedValue(event.target.value)}
                  placeholder="optional"
                />
              </label>
              <label className="manual-review-note">
                Note
                <input
                  type="text"
                  maxLength={2000}
                  value={reviewMetricNote}
                  onChange={(event) => setReviewMetricNote(event.target.value)}
                  placeholder="optional"
                />
              </label>
              <button
                type="button"
                disabled={!review || reviewLoadFailed || !reviewMetric || !reviewMetricLabel || reviewSaving}
                onClick={() => void saveMetricReview()}
              >
                {reviewSaving ? 'saving…' : 'save metric review'}
              </button>
            </div>
            {review?.metric_annotations.length ? (
              <ul className="manual-review-list">
                {review.metric_annotations.map((annotation) => (
                  <li key={`${annotation.metric}-${annotation.definition_id}`}>
                    {formatMetricName(annotation.metric)} <strong>{annotation.label}</strong>
                    {annotation.expected_value != null
                      ? `, expected ${annotation.expected_value} ${annotation.unit ?? ''}`
                      : ''}
                    {annotation.note ? `, ${annotation.note}` : ''}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </section>
      )}

      {metrics && (
        <div className="panel metrics-panel">
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
                      const validated = isValidatedMetric(m)
                      const status = metricStatus(m)
                      return (
                        <tr
                          key={m.name}
                          className={[
                            validated && m.in_range === false ? 'flagged' : '',
                            focusedMetric === m.name ? 'voice-focused' : '',
                          ].join(' ')}
                        >
                          <td>
                            <button
                              className="metric-focus"
                              aria-pressed={focusedMetric === m.name}
                              onClick={() => onFocusMetric(m.name)}
                            >
                              <span className="metric-name">{formatMetricName(m.name)}</span>
                              {focusedMetric === m.name && <span>voice focus</span>}
                            </button>
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
                              validated && m.in_range === true
                                ? 'metric-value in-range'
                                : validated && m.in_range === false
                                  ? 'metric-value out-range'
                                  : 'metric-value'
                            }
                          >
                            {status === 'unavailable' || m.value === null
                              ? 'unavailable'
                              : `${m.value} ${m.unit}`}
                            {!validated && <small className="muted"> {status}</small>}
                          </td>
                          <td>
                            {validated
                              ? m.in_range === null
                                ? 'no compatible target'
                                : m.in_range
                                  ? 'OK'
                                  : 'out of range'
                              : metricReason(m)}
                            {validated && m.range ? ` (${m.range.min}–${m.range.max})` : ''}
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
            Ball detected at address{' '}
            {ball.address_xy ? `(${ball.address_xy[0]}, ${ball.address_xy[1]})` : ''}
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
          {tips.length === 0 ? (
            <p>{metricSummary(metrics.metrics)}</p>
          ) : (
            <ol>
              {tips.map((tip) => (
                <li key={tip.metric}>{tip.text}</li>
              ))}
            </ol>
          )}
          <button
            disabled={processState === 'running'}
            onClick={() => {
              setProcessState('running')
              api
                .reanalyze(sessionId)
                .catch((error: unknown) => setProcessState(`error: ${String(error)}`))
            }}
          >
            {processState === 'running' ? 'reanalysing...' : 'reanalyze saved 3D'}
          </button>
          <button
            disabled={processState === 'running'}
            onClick={async () => {
              try {
                const calibration = await api.calibrationInfo()
                if (!calibration.bundle_id || calibration.validation_status !== 'accepted')
                  throw new Error('An independently accepted camera bundle is required.')
                if (
                  !window.confirm(
                    `Reconstruct this session with active camera bundle ${calibration.bundle_id}? Existing 3D and metrics will be archived. Saved capture compatibility must pass.`,
                  )
                )
                  return
                setProcessState('running')
                await api.reconstruct(sessionId, calibration.bundle_id)
              } catch (failure) {
                setProcessState(`error: ${String(failure)}`)
              }
            }}
          >
            reconstruct with active calibration
          </button>
          {processState.startsWith('error') && <p className="error">{processState}</p>}
        </div>
      )}
    </div>
  )
}
