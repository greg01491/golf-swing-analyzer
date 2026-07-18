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
  /** ghost reference pose for the currently-selected P-position, keyed by
   * marker name (see golf_sim.analysis.ideal_pose on the backend) */
  idealFrame?: Record<string, [number, number, number]> | null
}

type Point = { x: number; y: number } | null

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

function projectXY(
  xyz: readonly (number | null)[],
  up: number,
  sign: number,
  horiz: number[],
  azimuthRad: number,
): Point {
  if (xyz[0] === null || xyz[1] === null || xyz[2] === null) return null
  const u = xyz[horiz[0]] as number
  const v = xyz[horiz[1]] as number
  const h = (xyz[up] as number) * sign
  return { x: u * Math.cos(azimuthRad) + v * Math.sin(azimuthRad), y: h }
}

export default function SkeletonCanvas({
  landmarks,
  time,
  width = 420,
  height = 420,
  idealFrame,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [azimuth, setAzimuth] = useState(30)

  const upInfo = useMemo(() => findUpAxis(landmarks), [landmarks])

  // camera bounds span the whole clip (plus the ideal ghost, if shown) so
  // nothing gets clipped or rescales mid-swing; recomputed only per
  // clip/angle/ghost, not per animation tick
  const bounds = useMemo(() => {
    const { axis: up, sign } = upInfo
    const horiz = [0, 1, 2].filter((i) => i !== up)
    const a = (azimuth * Math.PI) / 180
    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity
    const extend = (p: Point) => {
      if (!p) return
      minX = Math.min(minX, p.x)
      maxX = Math.max(maxX, p.x)
      minY = Math.min(minY, p.y)
      maxY = Math.max(maxY, p.y)
    }
    for (const f of landmarks.frames) {
      for (const m of f) extend(projectXY(m, up, sign, horiz, a))
    }
    if (idealFrame) {
      for (const xyz of Object.values(idealFrame)) extend(projectXY(xyz, up, sign, horiz, a))
    }
    return { minX, maxX, minY, maxY }
  }, [landmarks, azimuth, upInfo, idealFrame])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const { axis: up, sign } = upInfo
    const horiz = [0, 1, 2].filter((i) => i !== up)
    const a = (azimuth * Math.PI) / 180

    const frameIdx = Math.min(
      landmarks.frames.length - 1,
      Math.max(0, Math.round(time * landmarks.fps)),
    )
    const frame = landmarks.frames[frameIdx]
    const pts = frame.map((m) => projectXY(m, up, sign, horiz, a))

    const { minX, maxX, minY, maxY } = bounds
    const scale = 0.85 * Math.min(width / (maxX - minX || 1), height / (maxY - minY || 1))
    const cx = (minX + maxX) / 2
    const cy = (minY + maxY) / 2
    const toScreen = (p: { x: number; y: number }) => ({
      x: width / 2 + (p.x - cx) * scale,
      y: height / 2 - (p.y - cy) * scale,
    })

    const drawSkeleton = (
      points: Point[],
      indexOf: (name: string) => number,
      color: string,
      dotColor: string,
      dashed: boolean,
    ) => {
      ctx.setLineDash(dashed ? [6, 4] : [])
      ctx.strokeStyle = color
      ctx.lineWidth = 3
      for (const [na, nb] of EDGES) {
        const ia = indexOf(na)
        const ib = indexOf(nb)
        if (ia < 0 || ib < 0) continue
        const pa = points[ia]
        const pb = points[ib]
        if (!pa || !pb) continue
        const sa = toScreen(pa)
        const sb = toScreen(pb)
        ctx.beginPath()
        ctx.moveTo(sa.x, sa.y)
        ctx.lineTo(sb.x, sb.y)
        ctx.stroke()
      }
      ctx.setLineDash([])
      ctx.fillStyle = dotColor
      for (const p of points) {
        if (!p) continue
        const s = toScreen(p)
        ctx.beginPath()
        ctx.arc(s.x, s.y, 4, 0, 2 * Math.PI)
        ctx.fill()
      }
    }

    ctx.clearRect(0, 0, width, height)

    if (idealFrame) {
      const idealNames = Object.keys(idealFrame)
      const idealPts = idealNames.map((n) => projectXY(idealFrame[n], up, sign, horiz, a))
      drawSkeleton(idealPts, (name) => idealNames.indexOf(name), '#fbbf24', '#fde68a', true)
    }

    drawSkeleton(
      pts,
      (name) => landmarks.marker_names.indexOf(name),
      '#4ade80',
      '#a7f3d0',
      false,
    )
  }, [landmarks, time, azimuth, width, height, upInfo, bounds, idealFrame])

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
      {idealFrame && (
        <div className="ghost-legend">
          <span className="swatch actual" /> you &nbsp;
          <span className="swatch ideal" /> reference
        </div>
      )}
    </div>
  )
}
