import { useEffect, useId, useRef, useState, type PointerEvent } from 'react'
import { createPortal } from 'react-dom'
import {
  findVisibleLineIntersections,
  lineAngleDegrees,
  snapLineEndpointToAngle,
  type Point,
  type VisibleLine,
  type VisibleLineIntersection,
} from '../lineAngles'
import { containedImageRect, imagePointFromClient } from '../videoFraming'

interface LineState extends VisibleLine {
  color: string
}

interface StoredLines {
  lines: LineState[]
  selectedIndex: number
  lineAngleVisibility: Record<string, boolean>
  crossingAngleVisibility: Record<string, boolean>
  lineAngleLabelPositions: Record<string, Point>
  crossingAngleLabelPositions: Record<string, Point>
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
const LINE_LABELS = ['A', 'B', 'C', 'D', 'E']
const storageKey = (camera: string) => `swing-plane-lines:${camera}`
const oldStorageKey = (camera: string) => `swing-plane-line:${camera}`

function booleanMap(value: unknown): Record<string, boolean> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean'),
  )
}

function pointMap(value: unknown): Record<string, Point> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return Object.fromEntries(
    Object.entries(value).filter(
      (entry): entry is [string, Point] =>
        Boolean(entry[1]) &&
        typeof entry[1] === 'object' &&
        Number.isFinite((entry[1] as Point).x) &&
        Number.isFinite((entry[1] as Point).y),
    ),
  )
}

function reindexLineMap<T>(map: Record<string, T>, removedIndex: number): Record<string, T> {
  return Object.fromEntries(
    Object.entries(map).flatMap(([key, value]) => {
      const index = Number(key)
      if (!Number.isInteger(index) || index === removedIndex) return []
      return [[String(index > removedIndex ? index - 1 : index), value]]
    }),
  )
}

function reindexCrossingMap<T>(map: Record<string, T>, removedIndex: number): Record<string, T> {
  return Object.fromEntries(
    Object.entries(map).flatMap(([key, value]) => {
      const match = /^(\d+)-(\d+)$/.exec(key)
      if (!match) return []
      const first = Number(match[1])
      const second = Number(match[2])
      if (first === removedIndex || second === removedIndex) return []
      const nextFirst = first > removedIndex ? first - 1 : first
      const nextSecond = second > removedIndex ? second - 1 : second
      return [[`${nextFirst}-${nextSecond}`, value]]
    }),
  )
}

function loadStoredLines(camera: string): StoredLines {
  try {
    const current = localStorage.getItem(storageKey(camera))
    if (current) {
      const parsed = JSON.parse(current) as StoredLines
      if (Array.isArray(parsed.lines)) {
        const lines = parsed.lines.slice(0, MAX_LINES)
        return {
          lines,
          selectedIndex: Math.max(0, Math.min(parsed.selectedIndex ?? 0, lines.length - 1)),
          lineAngleVisibility: booleanMap(parsed.lineAngleVisibility),
          crossingAngleVisibility: booleanMap(parsed.crossingAngleVisibility),
          lineAngleLabelPositions: pointMap(parsed.lineAngleLabelPositions),
          crossingAngleLabelPositions: pointMap(parsed.crossingAngleLabelPositions),
        }
      }
    }
    const legacy = localStorage.getItem(oldStorageKey(camera))
    if (legacy) {
      return {
        lines: [{ ...DEFAULT_LINE, ...JSON.parse(legacy) }],
        selectedIndex: 0,
        lineAngleVisibility: {},
        crossingAngleVisibility: {},
        lineAngleLabelPositions: {},
        crossingAngleLabelPositions: {},
      }
    }
  } catch {
    // Ignore malformed local storage and start with no lines.
  }
  return {
    lines: [],
    selectedIndex: 0,
    lineAngleVisibility: {},
    crossingAngleVisibility: {},
    lineAngleLabelPositions: {},
    crossingAngleLabelPositions: {},
  }
}

function useSwingPlaneLines(camera: string) {
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
        return { ...prev, lines: [...prev.lines, nextLine], selectedIndex: prev.lines.length }
      }),
    removeSelected: () =>
      setStored((prev) => {
        if (prev.lines.length === 0) return prev
        const removedIndex = prev.selectedIndex
        const lines = prev.lines.filter((_line, index) => index !== prev.selectedIndex)
        return {
          ...prev,
          lines,
          selectedIndex: Math.max(0, Math.min(prev.selectedIndex, lines.length - 1)),
          lineAngleVisibility: reindexLineMap(prev.lineAngleVisibility, removedIndex),
          lineAngleLabelPositions: reindexLineMap(prev.lineAngleLabelPositions, removedIndex),
          crossingAngleVisibility: reindexCrossingMap(
            prev.crossingAngleVisibility,
            removedIndex,
          ),
          crossingAngleLabelPositions: reindexCrossingMap(
            prev.crossingAngleLabelPositions,
            removedIndex,
          ),
        }
      }),
    setColor: (color: string) => updateSelected((line) => ({ ...line, color })),
    toggleVisible: () => updateSelected((line) => ({ ...line, visible: !line.visible })),
    setLineAngleVisibility: (index: number, visible: boolean) =>
      setStored((prev) => ({
        ...prev,
        lineAngleVisibility: { ...prev.lineAngleVisibility, [index]: visible },
      })),
    setCrossingAngleVisibility: (key: string, visible: boolean) =>
      setStored((prev) => ({
        ...prev,
        crossingAngleVisibility: { ...prev.crossingAngleVisibility, [key]: visible },
      })),
    setLineAngleLabelPosition: (index: number, position: Point) =>
      setStored((prev) => ({
        ...prev,
        lineAngleLabelPositions: { ...prev.lineAngleLabelPositions, [index]: position },
      })),
    setCrossingAngleLabelPosition: (key: string, position: Point) =>
      setStored((prev) => ({
        ...prev,
        crossingAngleLabelPositions: {
          ...prev.crossingAngleLabelPositions,
          [key]: position,
        },
      })),
    resetAngleLabelPositions: () =>
      setStored((prev) => ({
        ...prev,
        lineAngleLabelPositions: {},
        crossingAngleLabelPositions: {},
      })),
    movePoint: (which: 'p1' | 'p2', x: number, y: number) =>
      updateSelected((line) =>
        which === 'p1' ? { ...line, x1: x, y1: y } : { ...line, x2: x, y2: y },
      ),
    isLineAngleVisible: (index: number) => stored.lineAngleVisibility[String(index)] !== false,
    isCrossingAngleVisible: (key: string) => stored.crossingAngleVisibility[key] !== false,
    lineAngleVisibility: stored.lineAngleVisibility,
    crossingAngleVisibility: stored.crossingAngleVisibility,
    hasManualAngleLabelPositions:
      Object.keys(stored.lineAngleLabelPositions).length > 0 ||
      Object.keys(stored.crossingAngleLabelPositions).length > 0,
    lineAngleLabelPositions: stored.lineAngleLabelPositions,
    crossingAngleLabelPositions: stored.crossingAngleLabelPositions,
  }
}

function SwingPlaneLineOverlay({
  lines,
  selectedIndex,
  onMovePoint,
  onSelectLine,
  onImageSize,
  intersections,
  lineAngleVisibility,
  crossingAngleVisibility,
  lineAngleLabelPositions,
  crossingAngleLabelPositions,
  onMoveLineAngleLabel,
  onMoveCrossingAngleLabel,
}: {
  lines: LineState[]
  selectedIndex: number
  onMovePoint: (which: 'p1' | 'p2', x: number, y: number) => void
  onSelectLine: (index: number) => void
  onImageSize: (size: { width: number; height: number } | null) => void
  intersections: VisibleLineIntersection[]
  lineAngleVisibility: Record<string, boolean>
  crossingAngleVisibility: Record<string, boolean>
  lineAngleLabelPositions: Record<string, Point>
  crossingAngleLabelPositions: Record<string, Point>
  onMoveLineAngleLabel: (index: number, position: Point) => void
  onMoveCrossingAngleLabel: (key: string, position: Point) => void
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const draggingRef = useRef<'p1' | 'p2' | null>(null)
  const draggingLabelRef = useRef<{
    kind: 'line' | 'crossing'
    key: string
    offsetX: number
    offsetY: number
    width: number
  } | null>(null)
  const clipId = useId().replaceAll(':', '')
  const [snapping, setSnapping] = useState(false)
  const [imageGeometry, setImageGeometry] = useState<{
    left: number
    top: number
    width: number
    height: number
    imageWidth: number
    imageHeight: number
  } | null>(null)

  useEffect(() => {
    const frame = svgRef.current?.parentElement
    const video = frame?.querySelector('video')
    if (!frame || !video) return

    const updateGeometry = () => {
      if (video.videoWidth <= 0 || video.videoHeight <= 0) {
        setImageGeometry(null)
        onImageSize(null)
        return
      }
      // CameraViewport scales the whole surface; the overlay inherits that zoom from its parent.
      const imageRect = containedImageRect(
        { width: video.videoWidth, height: video.videoHeight },
        { left: video.offsetLeft, top: video.offsetTop, width: video.clientWidth, height: video.clientHeight },
        { left: 0, top: 0, width: frame.clientWidth, height: frame.clientHeight },
      )
      if (!imageRect) {
        setImageGeometry(null)
        onImageSize(null)
        return
      }
      onImageSize({ width: video.videoWidth, height: video.videoHeight })
      const nextGeometry = {
        ...imageRect,
        imageWidth: video.videoWidth,
        imageHeight: video.videoHeight,
      }
      setImageGeometry((previous) =>
        previous &&
        Object.keys(nextGeometry).every(
          (key) =>
            previous[key as keyof typeof nextGeometry] === nextGeometry[key as keyof typeof nextGeometry],
        )
          ? previous
          : nextGeometry,
      )
    }

    updateGeometry()
    const resizeObserver =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(updateGeometry)
    resizeObserver?.observe(frame)
    resizeObserver?.observe(video)
    video.addEventListener('loadedmetadata', updateGeometry)
    return () => {
      resizeObserver?.disconnect()
      video.removeEventListener('loadedmetadata', updateGeometry)
    }
  }, [onImageSize])

  const pointFromClient = (clientX: number, clientY: number) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return null
    return imagePointFromClient(clientX, clientY, rect)
  }
  const startLabelDrag =
    (kind: 'line' | 'crossing', key: string, left: number, top: number, width: number) =>
    (event: PointerEvent<SVGGElement>) => {
      if (!imageGeometry) return
      event.preventDefault()
      event.stopPropagation()
      const point = pointFromClient(event.clientX, event.clientY)
      if (!point) return
      draggingLabelRef.current = {
        kind,
        key,
        offsetX: (point.x / 100) * imageGeometry.width - left,
        offsetY: (point.y / 100) * imageGeometry.height - top,
        width,
      }
      event.currentTarget.setPointerCapture(event.pointerId)
    }
  const startDrag = (which: 'p1' | 'p2') => (event: PointerEvent<SVGCircleElement>) => {
    event.preventDefault()
    event.stopPropagation()
    draggingRef.current = which
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const point = pointFromClient(event.clientX, event.clientY)
    if (draggingLabelRef.current && point && imageGeometry) {
      const label = draggingLabelRef.current
      const left = Math.max(
        0,
        Math.min(
          imageGeometry.width - label.width,
          (point.x / 100) * imageGeometry.width - label.offsetX,
        ),
      )
      const top = Math.max(
        0,
        Math.min(imageGeometry.height - 24, (point.y / 100) * imageGeometry.height - label.offsetY),
      )
      const position = {
        x: (left / imageGeometry.width) * 100,
        y: (top / imageGeometry.height) * 100,
      }
      if (label.kind === 'line') onMoveLineAngleLabel(Number(label.key), position)
      else onMoveCrossingAngleLabel(label.key, position)
      return
    }
    if (!draggingRef.current) return
    setSnapping(event.shiftKey)
    const selectedLine = lines[selectedIndex]
    if (!point || !selectedLine || !imageGeometry) return
    if (event.shiftKey) {
      const fixed = draggingRef.current === 'p1'
        ? { x: selectedLine.x2, y: selectedLine.y2 }
        : { x: selectedLine.x1, y: selectedLine.y1 }
      const snapped = snapLineEndpointToAngle(
        fixed,
        point,
        imageGeometry.imageWidth,
        imageGeometry.imageHeight,
      )
      if (snapped) onMovePoint(draggingRef.current, snapped.x, snapped.y)
      return
    }
    onMovePoint(draggingRef.current, point.x, point.y)
  }
  const stopDrag = () => {
    draggingRef.current = null
    draggingLabelRef.current = null
    setSnapping(false)
  }

  const selectedLine = lines[selectedIndex]
  const canShowLines = imageGeometry !== null && lines.some((line) => line.visible)
  const visibleHeight = imageGeometry ? Math.max(0, imageGeometry.height - 44) : 0
  const coordinateX = (value: number) => ((value / 100) * (imageGeometry?.width ?? 0))
  const coordinateY = (value: number) => ((value / 100) * (imageGeometry?.height ?? 0))
  const automaticLineLabelPositions: Array<{ x: number; y: number; width: number; height: number }> = []
  const lineAngleAnnotations =
    imageGeometry === null
      ? []
      : lines.flatMap((line, index) => {
          if (!line.visible || lineAngleVisibility[String(index)] === false) return []
          const x1 = coordinateX(line.x1)
          const y1 = coordinateY(line.y1)
          const x2 = coordinateX(line.x2)
          const y2 = coordinateY(line.y2)
          const angle = lineAngleDegrees(line, imageGeometry.imageWidth, imageGeometry.imageHeight)
          const distanceToNearestCrossing = (x: number, y: number) =>
            intersections.length
              ? Math.min(
                  ...intersections.map((intersection) =>
                    Math.hypot(
                      x - coordinateX(intersection.x),
                      y - coordinateY(intersection.y),
                    ),
                  ),
                )
              : 0
          const firstDistance = distanceToNearestCrossing(x1, y1)
          const secondDistance = distanceToNearestCrossing(x2, y2)
          const atSecondEndpoint =
            secondDistance > firstDistance ||
            (secondDistance === firstDistance && index % 2 === 1)
          const pointX = atSecondEndpoint ? x2 : x1
          const pointY = atSecondEndpoint ? y2 : y1
          const label = `${LINE_LABELS[index]} ${angle === null ? '--' : `${angle.toFixed(1)}°`}`
          const width = label.length * 8 + 12
          const autoX = pointX > imageGeometry.width * 0.68 ? pointX - width - 10 : pointX + 10
          const autoY = Math.max(
            0,
            Math.min(imageGeometry.height - 24, pointY - 12 + Math.floor(index / 2) * 24),
          )
          const candidates = [0, -26, 26, -52, 52].flatMap((offsetY) =>
            [autoX, pointX > imageGeometry.width * 0.68 ? pointX + 10 : pointX - width - 10].map(
              (candidateX) => ({
                x: Math.max(0, Math.min(imageGeometry.width - width, candidateX)),
                y: Math.max(0, Math.min(imageGeometry.height - 24, autoY + offsetY)),
              }),
            ),
          )
          const automaticPosition =
            candidates.find(
              (position) =>
                !automaticLineLabelPositions.some(
                  (placed) =>
                    position.x < placed.x + placed.width + 4 &&
                    position.x + width + 4 > placed.x &&
                    position.y < placed.y + placed.height + 4 &&
                    position.y + 28 > placed.y,
                ),
            ) ?? candidates[0]
          const saved = lineAngleLabelPositions[String(index)]
          const position = saved
            ? {
                x: Math.max(
                  0,
                  Math.min(imageGeometry.width - width, (saved.x / 100) * imageGeometry.width),
                ),
                y: Math.max(
                  0,
                  Math.min(imageGeometry.height - 24, (saved.y / 100) * imageGeometry.height),
                ),
              }
            : automaticPosition
          automaticLineLabelPositions.push({ ...position, width, height: 24 })
          return [{ key: String(index), index, label, width, ...position }]
        })
  const placedLabels: Array<{ x: number; y: number; width: number; height: number }> =
    lineAngleAnnotations.map(({ x, y, width }) => ({ x, y, width, height: 24 }))
  const crossingAnnotations =
    imageGeometry === null
      ? []
      : intersections.flatMap((intersection) => {
          const key = `${intersection.firstIndex}-${intersection.secondIndex}`
          if (crossingAngleVisibility[key] === false) return []
          const first = lines[intersection.firstIndex]
          const second = lines[intersection.secondIndex]
          const x = coordinateX(intersection.x)
          const y = coordinateY(intersection.y)
          const firstDirection = Math.atan2(
            (first.y2 - first.y1) * imageGeometry.height,
            (first.x2 - first.x1) * imageGeometry.width,
          )
          const secondDirection = Math.atan2(
            (second.y2 - second.y1) * imageGeometry.height,
            (second.x2 - second.x1) * imageGeometry.width,
          )
          let angleDifference = secondDirection - firstDirection
          while (angleDifference > Math.PI / 2) angleDifference -= Math.PI
          while (angleDifference < -Math.PI / 2) angleDifference += Math.PI
          const radius = 18
          const startX = x + radius * Math.cos(firstDirection)
          const startY = y + radius * Math.sin(firstDirection)
          const endX = x + radius * Math.cos(firstDirection + angleDifference)
          const endY = y + radius * Math.sin(firstDirection + angleDifference)
          const label = `${LINE_LABELS[intersection.firstIndex]}/${LINE_LABELS[intersection.secondIndex]} ${intersection.angle.toFixed(1)}°`
          const labelWidth = label.length * 8 + 12
          const candidates = [
            { x: x + 14, y: y - 12 },
            { x: x - labelWidth - 14, y: y - 12 },
            { x: x + 14, y: y + 14 },
            { x: x - labelWidth - 14, y: y + 14 },
            { x: x + 14, y: y - 38 },
            { x: x - labelWidth - 14, y: y - 38 },
            { x: x + 14, y: y + 38 },
            { x: x - labelWidth - 14, y: y + 38 },
          ].map((position) => ({
            x: Math.max(0, Math.min(imageGeometry.width - labelWidth, position.x)),
            y: Math.max(0, Math.min(imageGeometry.height - 24, position.y)),
          }))
          const automaticPosition =
            candidates.find(
              (position) =>
                !placedLabels.some(
                  (placed) =>
                    position.x < placed.x + placed.width + 4 &&
                    position.x + labelWidth + 4 > placed.x &&
                    position.y < placed.y + placed.height + 4 &&
                    position.y + 28 > placed.y,
                ),
            ) ?? candidates[0]
          const storedPosition = crossingAngleLabelPositions[key]
          const labelPosition = storedPosition
            ? {
                x: Math.max(
                  0,
                  Math.min(imageGeometry.width - labelWidth, (storedPosition.x / 100) * imageGeometry.width),
                ),
                y: Math.max(
                  0,
                  Math.min(imageGeometry.height - 24, (storedPosition.y / 100) * imageGeometry.height),
                ),
              }
            : automaticPosition
          placedLabels.push({ ...labelPosition, width: labelWidth, height: 24 })
          return [
            {
              key,
              firstIndex: intersection.firstIndex,
              secondIndex: intersection.secondIndex,
              path: `M ${startX} ${startY} A ${radius} ${radius} 0 0 ${angleDifference >= 0 ? 1 : 0} ${endX} ${endY}`,
              label,
              labelX: labelPosition.x,
              labelY: labelPosition.y,
              labelWidth,
              x,
              y,
            },
          ]
        })

  const intersectionDescription = intersections.length
    ? crossingAnnotations.length
      ? crossingAnnotations.map((intersection) => intersection.label).join('. ')
      : 'Line intersection angle labels are hidden.'
    : 'No visible reference-line segments intersect.'

  return (
    <>
      <svg
        ref={svgRef}
        className="swing-plane-line"
        viewBox={imageGeometry ? `0 0 ${imageGeometry.width} ${imageGeometry.height}` : undefined}
        preserveAspectRatio="none"
        style={
          canShowLines && imageGeometry
            ? {
                left: imageGeometry.left,
                top: imageGeometry.top,
                width: imageGeometry.width,
                height: imageGeometry.height,
              }
            : { display: 'none' }
        }
        onPointerMove={onPointerMove}
        onPointerUp={stopDrag}
        onPointerCancel={stopDrag}
        onLostPointerCapture={stopDrag}
        role="img"
        aria-label={`Swing plane reference lines. ${intersectionDescription}`}
      >
      {imageGeometry && canShowLines && (
        <>
          <defs>
            <clipPath id={clipId} clipPathUnits="userSpaceOnUse">
              <rect x="0" y="0" width={imageGeometry.width} height={visibleHeight} />
            </clipPath>
          </defs>
          {lines.map((line, index) => {
            if (!line.visible) return null
            const x1 = coordinateX(line.x1)
            const y1 = coordinateY(line.y1)
            const x2 = coordinateX(line.x2)
            const y2 = coordinateY(line.y2)
            return (
              <g key={index}>
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={line.color}
                  strokeWidth={2}
                  vectorEffect="non-scaling-stroke"
                  className="swing-plane-line-visible"
                />
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke="transparent"
                  strokeWidth={28}
                  clipPath={`url(#${clipId})`}
                  className="swing-plane-line-hit-target"
                  onPointerDown={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    onSelectLine(index)
                  }}
                />
              </g>
            )
          })}
          {lineAngleAnnotations.map((annotation) => {
            const line = lines[annotation.index]
            return (
              <g
                className="swing-plane-line-label"
                key={`label-${annotation.key}`}
                onPointerDown={startLabelDrag(
                  'line',
                  annotation.key,
                  annotation.x,
                  annotation.y,
                  annotation.width,
                )}
              >
                <rect
                  x={annotation.x}
                  y={annotation.y}
                  width={annotation.width}
                  height={24}
                  rx={12}
                  fill="rgba(10, 14, 18, 0.9)"
                  stroke={line.color}
                  strokeWidth={1.5}
                />
                <text
                  x={annotation.x + annotation.width / 2}
                  y={annotation.y + 16}
                  textAnchor="middle"
                  fill="#fff"
                  fontSize={13}
                  fontWeight={700}
                >
                  {annotation.label}
                </text>
              </g>
            )
          })}
          {crossingAnnotations.map((intersection) => (
            <g className="swing-plane-line-intersection" key={intersection.key}>
              <path d={intersection.path} />
              <g
                className="swing-plane-line-intersection-label"
                onPointerDown={startLabelDrag(
                  'crossing',
                  intersection.key,
                  intersection.labelX,
                  intersection.labelY,
                  intersection.labelWidth,
                )}
              >
                <rect
                  x={intersection.labelX}
                  y={intersection.labelY}
                  width={intersection.labelWidth}
                  height={24}
                  rx={12}
                />
                <text
                  x={intersection.labelX + intersection.labelWidth / 2}
                  y={intersection.labelY + 16}
                  textAnchor="middle"
                >
                  {intersection.label}
                </text>
              </g>
            </g>
          ))}
          {snapping && (
            <g className="swing-plane-line-snap-cue">
              <rect x="8" y="8" width="104" height="26" rx="13" />
              <text x="60" y="25" textAnchor="middle">
                Shift snap 5°
              </text>
            </g>
          )}
          {selectedLine?.visible &&
            (['p1', 'p2'] as const).map((which) => (
              <g key={which}>
                <circle
                  cx={coordinateX(which === 'p1' ? selectedLine.x1 : selectedLine.x2)}
                  cy={coordinateY(which === 'p1' ? selectedLine.y1 : selectedLine.y2)}
                  r={12}
                  fill="transparent"
                  className="swing-plane-line-handle-target"
                  onPointerDown={startDrag(which)}
                />
                <circle
                  cx={coordinateX(which === 'p1' ? selectedLine.x1 : selectedLine.x2)}
                  cy={coordinateY(which === 'p1' ? selectedLine.y1 : selectedLine.y2)}
                  r={6}
                  fill={selectedLine.color}
                  className="swing-plane-line-handle"
                />
              </g>
            ))}
        </>
      )}
      </svg>
      <span className="swing-plane-line-sr-only" role="status">
        {snapping ? 'Angle snapping is active in 5-degree increments.' : ''}
      </span>
    </>
  )
}

export default function SwingPlaneLine({
  camera,
  toolbarTarget,
}: {
  camera: string
  toolbarTarget?: HTMLDivElement | null
}) {
  const {
    lines,
    selectedIndex,
    selectLine,
    addLine,
    removeSelected,
    setColor,
    toggleVisible,
    movePoint,
    lineAngleVisibility,
    crossingAngleVisibility,
    lineAngleLabelPositions,
    crossingAngleLabelPositions,
    setLineAngleVisibility,
    setCrossingAngleVisibility,
    setLineAngleLabelPosition,
    setCrossingAngleLabelPosition,
    resetAngleLabelPositions,
    hasManualAngleLabelPositions,
  } = useSwingPlaneLines(camera)
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null)
  const intersections = imageSize
    ? findVisibleLineIntersections(lines, imageSize.width, imageSize.height)
    : []

  const toolbar = (
    <div className="swing-plane-line-panel" onPointerDown={(event) => event.stopPropagation()}>
      <div className="swing-plane-line-panel-heading">
        <strong>Plane lines</strong>
        <button type="button" onClick={addLine} disabled={lines.length >= MAX_LINES}>
          + Add line ({lines.length}/{MAX_LINES})
        </button>
      </div>
      {lines.length > 0 && (
        <div className="swing-plane-line-list">
          {lines.map((line, index) => {
            const angle = imageSize
              ? lineAngleDegrees(line, imageSize.width, imageSize.height)
              : null
            return (
              <div className="swing-plane-line-row" key={index}>
                <button
                  type="button"
                  className={`swing-plane-line-select${index === selectedIndex ? ' is-selected' : ''}`}
                  aria-pressed={index === selectedIndex}
                  onClick={() => selectLine(index)}
                >
                  <span className="swing-plane-line-color" style={{ backgroundColor: line.color }} />
                  <span>Line {LINE_LABELS[index]}</span>
                  <span className="swing-plane-line-angle">
                    {angle === null ? '--' : `${angle.toFixed(1)}°`}
                  </span>
                </button>
                <label className="swing-plane-line-toggle">
                  <input
                    type="checkbox"
                    checked={line.visible}
                    onChange={() => {
                      selectLine(index)
                      toggleVisible()
                    }}
                    aria-label={`Show line ${LINE_LABELS[index]}`}
                  />
                  <span>Show</span>
                </label>
                <label className="swing-plane-line-toggle">
                  <input
                    type="checkbox"
                    checked={lineAngleVisibility[String(index)] !== false}
                    onChange={(event) => setLineAngleVisibility(index, event.target.checked)}
                    aria-label={`Show angle for line ${LINE_LABELS[index]}`}
                  />
                  <span>Angle</span>
                </label>
                <input
                  className="swing-plane-line-color-input"
                  type="color"
                  value={line.color}
                  onFocus={() => selectLine(index)}
                  onChange={(event) => {
                    selectLine(index)
                    setColor(event.target.value)
                  }}
                  title={`Line ${LINE_LABELS[index]} color`}
                  aria-label={`Line ${LINE_LABELS[index]} color`}
                />
                <button
                  type="button"
                  className="swing-plane-line-remove"
                  onClick={() => {
                    selectLine(index)
                    removeSelected()
                  }}
                  aria-label={`Remove line ${LINE_LABELS[index]}`}
                >
                  Remove
                </button>
              </div>
            )
          })}
        </div>
      )}
      {intersections.length > 0 && (
        <div className="swing-plane-line-crossing-list">
          <strong>Crossing angles</strong>
          {intersections.map((intersection) => {
            const key = `${intersection.firstIndex}-${intersection.secondIndex}`
            const first = LINE_LABELS[intersection.firstIndex]
            const second = LINE_LABELS[intersection.secondIndex]
            return (
              <label className="swing-plane-line-crossing-toggle" key={key}>
                <input
                  type="checkbox"
                  checked={crossingAngleVisibility[key] !== false}
                  onChange={(event) => setCrossingAngleVisibility(key, event.target.checked)}
                  aria-label={`Show angle between lines ${first} and ${second}`}
                />
                <span>
                  {first}/{second} {intersection.angle.toFixed(1)}°
                </span>
              </label>
            )
          })}
        </div>
      )}
      {hasManualAngleLabelPositions && (
        <button
          type="button"
          className="swing-plane-line-reset-labels"
          onClick={resetAngleLabelPositions}
        >
          Reset label positions
        </button>
      )}
      <p className="swing-plane-line-caveat">
        Angles are measured in this camera&apos;s 2D image, not in 3D.
      </p>
    </div>
  )
  return (
    <>
      {toolbarTarget ? createPortal(toolbar, toolbarTarget) : toolbarTarget === undefined ? toolbar : null}
      <SwingPlaneLineOverlay
        lines={lines}
        selectedIndex={selectedIndex}
        onMovePoint={movePoint}
        onSelectLine={selectLine}
        onImageSize={setImageSize}
        intersections={intersections}
        lineAngleVisibility={lineAngleVisibility}
        crossingAngleVisibility={crossingAngleVisibility}
        lineAngleLabelPositions={lineAngleLabelPositions}
        crossingAngleLabelPositions={crossingAngleLabelPositions}
        onMoveLineAngleLabel={setLineAngleLabelPosition}
        onMoveCrossingAngleLabel={setCrossingAngleLabelPosition}
      />
    </>
  )
}
