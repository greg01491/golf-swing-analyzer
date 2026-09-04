import { useEffect, useRef, useState, type PointerEvent } from 'react'

interface LineState {
  x1: number
  y1: number
  x2: number
  y2: number
  color: string
  visible: boolean
}

interface StoredLines {
  lines: LineState[]
  selectedIndex: number
}

const MAX_LINES = 5
const DEFAULT_LINE: LineState = {
  x1: 20,
  y1: 80,
  x2: 80,
  y2: 20,
  color: '#facc15',
  visible: true,
}
const COLORS = ['#facc15', '#ef4444', '#22d3ee', '#4ade80', '#c084fc']
const storageKey = (camera: string) => `swing-plane-lines:${camera}`
const oldStorageKey = (camera: string) => `swing-plane-line:${camera}`

function loadStoredLines(camera: string): StoredLines {
  try {
    const current = localStorage.getItem(storageKey(camera))
    if (current) {
      const parsed = JSON.parse(current) as StoredLines
      if (Array.isArray(parsed.lines)) {
        const lines = parsed.lines.slice(0, MAX_LINES)
        return { lines, selectedIndex: Math.max(0, Math.min(parsed.selectedIndex ?? 0, lines.length - 1)) }
      }
    }
    const legacy = localStorage.getItem(oldStorageKey(camera))
    if (legacy) return { lines: [{ ...DEFAULT_LINE, ...JSON.parse(legacy) }], selectedIndex: 0 }
  } catch {
    // Ignore malformed local storage and start with no lines.
  }
  return { lines: [], selectedIndex: 0 }
}

export function useSwingPlaneLines(camera: string) {
  const [stored, setStored] = useState<StoredLines>(() => loadStoredLines(camera))

  useEffect(() => {
    localStorage.setItem(storageKey(camera), JSON.stringify(stored))
  }, [camera, stored])

  const updateSelected = (update: (line: LineState) => LineState) => {
    setStored((prev) => ({
      ...prev,
      lines: prev.lines.map((line, index) => (index === prev.selectedIndex ? update(line) : line)),
    }))
  }

  return {
    lines: stored.lines,
    selectedIndex: stored.selectedIndex,
    selectedLine: stored.lines[stored.selectedIndex] ?? null,
    selectLine: (index: number) =>
      setStored((prev) => ({
        ...prev,
        selectedIndex: Math.max(0, Math.min(index, Math.max(0, prev.lines.length - 1))),
      })),
    addLine: () =>
      setStored((prev) => {
        if (prev.lines.length >= MAX_LINES) return prev
        const nextLine = { ...DEFAULT_LINE, color: COLORS[prev.lines.length % COLORS.length] }
        return { lines: [...prev.lines, nextLine], selectedIndex: prev.lines.length }
      }),
    removeSelected: () =>
      setStored((prev) => {
        if (prev.lines.length === 0) return prev
        const lines = prev.lines.filter((_line, index) => index !== prev.selectedIndex)
        return { lines, selectedIndex: Math.max(0, Math.min(prev.selectedIndex, lines.length - 1)) }
      }),
    setColor: (color: string) => updateSelected((line) => ({ ...line, color })),
    toggleVisible: () => updateSelected((line) => ({ ...line, visible: !line.visible })),
    movePoint: (which: 'p1' | 'p2', x: number, y: number) =>
      updateSelected((line) =>
        which === 'p1' ? { ...line, x1: x, y1: y } : { ...line, x2: x, y2: y },
      ),
  }
}

function SwingPlaneLineOverlay({
  lines,
  selectedIndex,
  onMovePoint,
}: {
  lines: LineState[]
  selectedIndex: number
  onMovePoint: (which: 'p1' | 'p2', x: number, y: number) => void
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const draggingRef = useRef<'p1' | 'p2' | null>(null)

  const pointFromEvent = (event: PointerEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return null
    return {
      x: Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100)),
      y: Math.min(100, Math.max(0, ((event.clientY - rect.top) / rect.height) * 100)),
    }
  }
  const startDrag = (which: 'p1' | 'p2') => (event: PointerEvent<SVGCircleElement>) => {
    event.preventDefault()
    draggingRef.current = which
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!draggingRef.current) return
    const point = pointFromEvent(event)
    if (point) onMovePoint(draggingRef.current, point.x, point.y)
  }
  const stopDrag = () => {
    draggingRef.current = null
  }

  const selectedLine = lines[selectedIndex]
  if (!lines.some((line) => line.visible)) return null
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
      {lines.map((line, index) =>
        line.visible ? (
          <line
            key={index}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke={line.color}
            strokeWidth={0.6}
            vectorEffect="non-scaling-stroke"
          />
        ) : null,
      )}
      {selectedLine?.visible &&
        (['p1', 'p2'] as const).map((which) => (
          <circle
            key={which}
            cx={which === 'p1' ? selectedLine.x1 : selectedLine.x2}
            cy={which === 'p1' ? selectedLine.y1 : selectedLine.y2}
            r={1.8}
            fill={selectedLine.color}
            className="swing-plane-line-handle"
            onPointerDown={startDrag(which)}
          />
        ))}
    </svg>
  )
}

export default function SwingPlaneLine({ camera }: { camera: string }) {
  const {
    lines,
    selectedIndex,
    selectedLine,
    selectLine,
    addLine,
    removeSelected,
    setColor,
    toggleVisible,
    movePoint,
  } = useSwingPlaneLines(camera)

  return (
    <>
      <div className="swing-plane-line-toolbar">
        <button type="button" onClick={addLine} disabled={lines.length >= MAX_LINES}>
          + line ({lines.length}/{MAX_LINES})
        </button>
        {lines.length > 0 && (
          <>
            <select
              value={selectedIndex}
              onChange={(event) => selectLine(Number(event.target.value))}
              aria-label="select swing plane line"
            >
              {lines.map((_line, index) => (
                <option key={index} value={index}>
                  line {index + 1}
                </option>
              ))}
            </select>
            <button type="button" onClick={removeSelected}>
              remove
            </button>
            <label className="swing-plane-line-toggle">
              <input
                type="checkbox"
                checked={selectedLine?.visible ?? false}
                onChange={toggleVisible}
              />
              show
            </label>
            <input
              type="color"
              value={selectedLine?.color ?? DEFAULT_LINE.color}
              onChange={(event) => setColor(event.target.value)}
              title="line color"
              disabled={!selectedLine}
            />
          </>
        )}
      </div>
      <SwingPlaneLineOverlay
        lines={lines}
        selectedIndex={selectedIndex}
        onMovePoint={movePoint}
      />
    </>
  )
}
