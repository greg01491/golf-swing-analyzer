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

type FigureMode = 'skeleton' | 'body'

// Half-thickness (radius) of each limb in METRES -- TRC coords are metres, so
// these scale with the figure automatically. Rough human proportions: thighs
// thicker than forearms, etc. Drives the "body" render mode's limb capsules.
const LIMB_RADIUS_M: Record<string, number> = {
  'Neck-RShoulder': 0.055,
  'Neck-LShoulder': 0.055,
  'RShoulder-RElbow': 0.05,
  'LShoulder-LElbow': 0.05,
  'RElbow-RWrist': 0.035,
  'LElbow-LWrist': 0.035,
  'RHip-RKnee': 0.075,
  'LHip-LKnee': 0.075,
  'RKnee-RAnkle': 0.05,
  'LKnee-LAnkle': 0.05,
  'RAnkle-RHeel': 0.03,
  'RAnkle-RBigToe': 0.03,
  'LAnkle-LHeel': 0.03,
  'LAnkle-LBigToe': 0.03,
}
const HEAD_RADIUS_M = 0.1

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
  const [figureMode, setFigureMode] = useState<FigureMode>('body')

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

    // Fuller "human" figure: filled torso quad + tapered limb capsules + a
    // head disc, so it reads as a body rather than a wireframe. Same
    // projected joints as the skeleton, just drawn as solids.
    const drawBody = (points: Point[], indexOf: (name: string) => number) => {
      const at = (name: string): Point => {
        const i = indexOf(name)
        return i >= 0 ? points[i] : null
      }
      // torso as a filled quad shoulders -> hips
      const rs = at('RShoulder')
      const ls = at('LShoulder')
      const lh = at('LHip')
      const rh = at('RHip')
      ctx.fillStyle = 'rgba(74, 222, 128, 0.35)'
      ctx.strokeStyle = '#4ade80'
      ctx.lineWidth = 2
      if (rs && ls && lh && rh) {
        const quad = [rs, ls, lh, rh].map(toScreen)
        ctx.beginPath()
        ctx.moveTo(quad[0].x, quad[0].y)
        for (let i = 1; i < quad.length; i++) ctx.lineTo(quad[i].x, quad[i].y)
        ctx.closePath()
        ctx.fill()
        ctx.stroke()
      }
      // limbs as round-capped capsules, thickness per body part
      ctx.lineCap = 'round'
      ctx.strokeStyle = 'rgba(74, 222, 128, 0.55)'
      for (const [na, nb] of EDGES) {
        const radius = LIMB_RADIUS_M[`${na}-${nb}`]
        if (!radius) continue
        const pa = at(na)
        const pb = at(nb)
        if (!pa || !pb) continue
        const sa = toScreen(pa)
        const sb = toScreen(pb)
        ctx.lineWidth = Math.max(3, 2 * radius * scale)
        ctx.beginPath()
        ctx.moveTo(sa.x, sa.y)
        ctx.lineTo(sb.x, sb.y)
        ctx.stroke()
      }
      ctx.lineCap = 'butt'
      // head disc
      const head = at('Head') ?? at('Neck')
      if (head) {
        const s = toScreen(head)
        ctx.fillStyle = 'rgba(74, 222, 128, 0.6)'
        ctx.beginPath()
        ctx.arc(s.x, s.y, Math.max(5, HEAD_RADIUS_M * scale), 0, 2 * Math.PI)
        ctx.fill()
      }
      // small joint dots keep articulation legible over the solid fills
      ctx.fillStyle = '#a7f3d0'
      for (const p of points) {
        if (!p) continue
        const s = toScreen(p)
        ctx.beginPath()
        ctx.arc(s.x, s.y, 2.5, 0, 2 * Math.PI)
        ctx.fill()
      }
    }

    ctx.clearRect(0, 0, width, height)

    // ghost reference stays a dashed wireframe in both modes -- it's a
    // guide, and a second solid body would just occlude the real one
    if (idealFrame) {
      const idealNames = Object.keys(idealFrame)
      const idealPts = idealNames.map((n) => projectXY(idealFrame[n], up, sign, horiz, a))
      drawSkeleton(idealPts, (name) => idealNames.indexOf(name), '#fbbf24', '#fde68a', true)
    }

    const actualIndexOf = (name: string) => landmarks.marker_names.indexOf(name)
    if (figureMode === 'body') {
      drawBody(pts, actualIndexOf)
    } else {
      drawSkeleton(pts, actualIndexOf, '#4ade80', '#a7f3d0', false)
    }
  }, [landmarks, time, azimuth, width, height, upInfo, bounds, idealFrame, figureMode])

  return (
    <div className="skeleton-canvas">
      <div className="figure-mode">
        <button
          className={figureMode === 'body' ? 'active' : ''}
          onClick={() => setFigureMode('body')}
        >
          body
        </button>
        <button
          className={figureMode === 'skeleton' ? 'active' : ''}
          onClick={() => setFigureMode('skeleton')}
        >
          skeleton
        </button>
      </div>
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
