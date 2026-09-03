import { useEffect, useRef, useState } from 'react'

interface LineState {
  x1: number
  y1: number
  x2: number
  y2: number
  color: string
  visible: boolean
}

// Sensible default: a diagonal from lower-left to upper-right, hidden until
// the golfer turns it on -- no line clutters the view for people who never use it.
const DEFAULT_LINE: LineState = { x1: 20, y1: 80, x2: 80, y2: 20, color: '#facc15', visible: false }

const storageKey = (camera: string) => `swing-plane-line:${camera}`

/** Per-camera reference-line state, persisted the same way `pro-mode` is. */
export function useSwingPlaneLine(camera: string) {
  const [line, setLine] = useState<LineState>(() => {
    try {
      const raw = localStorage.getItem(storageKey(camera))
      if (raw) return { ...DEFAULT_LINE, ...JSON.parse(raw) }
    } catch {
      // malformed/legacy storage value; fall back to the default below
    }
    return DEFAULT_LINE
  })

  useEffect(() => {
    localStorage.setItem(storageKey(camera), JSON.stringify(line))
  }, [camera, line])

  return {
    line,
    setColor: (color: string) => setLine((prev) => ({ ...prev, color })),
    toggleVisible: () => setLine((prev) => ({ ...prev, visible: !prev.visible })),
    movePoint: (which: 'p1' | 'p2', x: number, y: number) =>
      setLine((prev) =>
        which === 'p1' ? { ...prev, x1: x, y1: y } : { ...prev, x2: x, y2: y },
      ),
  }
}

/** Draggable straight-line overlay drawn over a video, independent of any
 * pose/club tracking -- purely a manual visual aid (see design.md). */
export function SwingPlaneLineOverlay({
  line,
  onMovePoint,
}: {
  line: LineState
  onMovePoint: (which: 'p1' | 'p2', x: number, y: number) => void
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const draggingRef = useRef<'p1' | 'p2' | null>(null)

  if (!line.visible) return null

  const pointFromEvent = (e: React.PointerEvent) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return null
    return {
      x: Math.min(100, Math.max(0, ((e.clientX - rect.left) / rect.width) * 100)),
      y: Math.min(100, Math.max(0, ((e.clientY - rect.top) / rect.height) * 100)),
    }
  }

  const startDrag = (which: 'p1' | 'p2') => (e: React.PointerEvent) => {
    e.preventDefault()
    draggingRef.current = which
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!draggingRef.current) return
    const point = pointFromEvent(e)
    if (point) onMovePoint(draggingRef.current, point.x, point.y)
  }
  const stopDrag = () => {
    draggingRef.current = null
  }

  return (
    <svg
      ref={svgRef}
      className="swing-plane-line"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      onPointerMove={onPointerMove}
      onPointerUp={stopDrag}
      onPointerLeave={stopDrag}
    >
      <line
        x1={line.x1}
        y1={line.y1}
        x2={line.x2}
        y2={line.y2}
        stroke={line.color}
        strokeWidth={0.6}
        vectorEffect="non-scaling-stroke"
      />
      {(['p1', 'p2'] as const).map((which) => (
        <circle
          key={which}
          cx={which === 'p1' ? line.x1 : line.x2}
          cy={which === 'p1' ? line.y1 : line.y2}
          r={1.8}
          fill={line.color}
          className="swing-plane-line-handle"
          onPointerDown={startDrag(which)}
        />
      ))}
    </svg>
  )
}

/** Drop-in per-camera control: toolbar (toggle + color) plus the draggable
 * overlay itself. Each camera view gets its own independent instance, since
 * the useful line angle differs between the down-the-line and face-on views. */
export default function SwingPlaneLine({ camera }: { camera: string }) {
  const { line, setColor, toggleVisible, movePoint } = useSwingPlaneLine(camera)

  return (
    <>
      <div className="swing-plane-line-toolbar">
        <label className="swing-plane-line-toggle">
          <input type="checkbox" checked={line.visible} onChange={toggleVisible} />
          line
        </label>
        {line.visible && (
          <input
            type="color"
            value={line.color}
            onChange={(e) => setColor(e.target.value)}
            title="line color"
          />
        )}
      </div>
      <SwingPlaneLineOverlay line={line} onMovePoint={movePoint} />
    </>
  )
}
