import { useEffect, useMemo, useRef, useState } from 'react'
import type { Landmarks } from '../api'

// bone connections by marker name; missing pairs are skipped
const EDGES: [string, string][] = [
  ['Head', 'Neck'],
  ['Neck', 'RShoulder'],
  ['Neck', 'LShoulder'],
  ['RShoulder', 'RElbow'],
  ['RElbow', 'RWrist'],
  ['LShoulder', 'LElbow'],
  ['LElbow', 'LWrist'],
  ['Neck', 'Hip'],
  ['Hip', 'RHip'],
  ['Hip', 'LHip'],
  ['RHip', 'RKnee'],
  ['RKnee', 'RAnkle'],
  ['LHip', 'LKnee'],
  ['LKnee', 'LAnkle'],
  ['RAnkle', 'RHeel'],
  ['RAnkle', 'RBigToe'],
  ['LAnkle', 'LHeel'],
  ['LAnkle', 'LBigToe'],
]

interface Props {
  landmarks: Landmarks
  /** current playback time in seconds (synced to the video element) */
  time: number
  width?: number
  height?: number
}

/** Detect which axis is vertical: largest spread of the Head/Neck marker
 * relative to ankles across the clip (same trick as the backend). */
function findUpAxis(lm: Landmarks): { axis: number; sign: number } {
  const head = lm.marker_names.indexOf('Head') >= 0 ? 'Head' : 'Neck'
  const headIdx = lm.marker_names.indexOf(head)
  const ankleIdx = lm.marker_names.indexOf('RAnkle')
  if (headIdx < 0 || ankleIdx < 0) return { axis: 1, sign: -1 }
  const mid = Math.floor(lm.frames.length / 2)
  const h = lm.frames[mid][headIdx]
  const a = lm.frames[mid][ankleIdx]
  let best = 1
  let bestVal = 0
  for (let i = 0; i < 3; i++) {
    const d = (h[i] ?? 0) - (a[i] ?? 0)
    if (Math.abs(d) > Math.abs(bestVal)) {
      best = i
      bestVal = d
    }
  }
  return { axis: best, sign: bestVal >= 0 ? 1 : -1 }
}

export default function SkeletonCanvas({ landmarks, time, width = 420, height = 420 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [azimuth, setAzimuth] = useState(30)

  const upInfo = useMemo(() => findUpAxis(landmarks), [landmarks])

  // camera bounds span the whole clip so the skeleton doesn't rescale
  // mid-swing; computed once per clip/angle, NOT per animation tick
  const bounds = useMemo(() => {
    const { axis: up, sign } = upInfo
    const horiz = [0, 1, 2].filter((i) => i !== up)
    const a = (azimuth * Math.PI) / 180
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const f of landmarks.frames) {
      for (const m of f) {
        if (m[0] === null) continue
        const u = m[horiz[0]] as number
        const v = m[horiz[1]] as number
        const h = (m[up] as number) * sign
        const x = u * Math.cos(a) + v * Math.sin(a)
        minX = Math.min(minX, x); maxX = Math.max(maxX, x)
        minY = Math.min(minY, h); maxY = Math.max(maxY, h)
      }
    }
    return { minX, maxX, minY, maxY }
  }, [landmarks, azimuth, upInfo])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const frameIdx = Math.min(
      landmarks.frames.length - 1,
      Math.max(0, Math.round(time * landmarks.fps)),
    )
    const frame = landmarks.frames[frameIdx]
    const { axis: up, sign } = upInfo
    const horiz = [0, 1, 2].filter((i) => i !== up)

    // orthographic projection with azimuth rotation about the vertical axis
    const a = (azimuth * Math.PI) / 180
    const pts: ({ x: number; y: number } | null)[] = frame.map((m) => {
      if (m[0] === null || m[1] === null || m[2] === null) return null
      const u = m[horiz[0]] as number
      const v = m[horiz[1]] as number
      const h = (m[up] as number) * sign
      return { x: u * Math.cos(a) + v * Math.sin(a), y: h }
    })

    const { minX, maxX, minY, maxY } = bounds
    const scale = 0.85 * Math.min(width / (maxX - minX || 1), height / (maxY - minY || 1))
    const cx = (minX + maxX) / 2
    const cy = (minY + maxY) / 2
    const toScreen = (p: { x: number; y: number }) => ({
      x: width / 2 + (p.x - cx) * scale,
      y: height / 2 - (p.y - cy) * scale,
    })

    ctx.clearRect(0, 0, width, height)
    ctx.strokeStyle = '#4ade80'
    ctx.lineWidth = 3
    for (const [na, nb] of EDGES) {
      const ia = landmarks.marker_names.indexOf(na)
      const ib = landmarks.marker_names.indexOf(nb)
      if (ia < 0 || ib < 0) continue
      const pa = pts[ia]
      const pb = pts[ib]
      if (!pa || !pb) continue
      const sa = toScreen(pa)
      const sb = toScreen(pb)
      ctx.beginPath()
      ctx.moveTo(sa.x, sa.y)
      ctx.lineTo(sb.x, sb.y)
      ctx.stroke()
    }
    ctx.fillStyle = '#a7f3d0'
    for (const p of pts) {
      if (!p) continue
      const s = toScreen(p)
      ctx.beginPath()
      ctx.arc(s.x, s.y, 4, 0, 2 * Math.PI)
      ctx.fill()
    }
  }, [landmarks, time, azimuth, width, height, upInfo, bounds])

  return (
    <div className="skeleton-canvas">
      <canvas ref={canvasRef} width={width} height={height} />
      <label className="azimuth">
        rotate
        <input
          type="range"
          min={-180}
          max={180}
          value={azimuth}
          onChange={(e) => setAzimuth(Number(e.target.value))}
        />
      </label>
    </div>
  )
}
