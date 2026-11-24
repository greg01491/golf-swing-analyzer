import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'
import {
  boundCameraView,
  containImage,
  DEFAULT_CAMERA_VIEW,
  type CameraView,
  type Size,
} from '../videoFraming'

interface Props {
  label: string
  imageSize: Size | undefined
  view: CameraView
  onChange: (view: CameraView) => void
  onError: (message: string) => void
  children: (toolbar: HTMLDivElement | null) => ReactNode
}

export default function CameraViewport({
  label,
  imageSize,
  view,
  onChange,
  onError,
  children,
}: Props) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [toolbar, setToolbar] = useState<HTMLDivElement | null>(null)
  const [viewport, setViewport] = useState<Size>({ width: 0, height: 0 })
  const [dragging, setDragging] = useState(false)
  const drag = useRef<{ id: number; x: number; y: number; view: CameraView } | null>(null)
  const image = containImage(imageSize ?? { width: 0, height: 0 }, viewport)
  const bounded = boundCameraView(view, image, viewport)
  const update = (next: CameraView) => onChange(boundCameraView(next, image, viewport))

  useEffect(() => {
    const node = viewportRef.current
    if (!node) return
    const observer = new ResizeObserver(([entry]) => {
      setViewport({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (drag.current?.id !== event.pointerId) return
    drag.current = null
    setDragging(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const fullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else await viewportRef.current?.parentElement?.requestFullscreen()
    } catch (error) {
      onError(`Could not open full screen: ${String(error)}`)
    }
  }

  return (
    <div className="camera-view">
      <div
        ref={viewportRef}
        className={`camera-viewport${dragging ? ' is-panning' : ''}`}
        role="group"
        aria-label={`${label} image. Drag to pan, or focus and use arrow keys. Space plays or pauses.`}
        tabIndex={0}
        onPointerDown={(event) => {
          if (!event.isPrimary || event.button !== 0 || !image.width) return
          event.preventDefault()
          event.currentTarget.focus()
          drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, view: bounded }
          event.currentTarget.setPointerCapture(event.pointerId)
          setDragging(true)
        }}
        onPointerMove={(event) => {
          const start = drag.current
          if (!start || start.id !== event.pointerId || !viewport.width || !viewport.height) return
          update({
            zoom: start.view.zoom,
            x: start.view.x + (event.clientX - start.x) / viewport.width,
            y: start.view.y + (event.clientY - start.y) / viewport.height,
          })
        }}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return
          if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
          event.preventDefault()
          event.stopPropagation()
          update({
            ...bounded,
            x:
              bounded.x +
              (event.key === 'ArrowLeft' ? -0.02 : event.key === 'ArrowRight' ? 0.02 : 0),
            y: bounded.y + (event.key === 'ArrowUp' ? -0.02 : event.key === 'ArrowDown' ? 0.02 : 0),
          })
        }}
      >
        <div
          className="camera-image-surface"
          style={{
            width: image.width,
            height: image.height,
            left: (viewport.width - image.width) / 2,
            top: (viewport.height - image.height) / 2,
            transform: `translate(${bounded.x * viewport.width}px, ${bounded.y * viewport.height}px) scale(${bounded.zoom})`,
          }}
        >
          {children(toolbar)}
        </div>
      </div>
      <div className="camera-view-controls" role="group" aria-label={`${label} framing`}>
        <button
          type="button"
          aria-label={`Zoom out ${label}`}
          disabled={bounded.zoom <= 1 || !image.width}
          onClick={() => update({ ...bounded, zoom: bounded.zoom - 0.25 })}
        >
          -
        </button>
        <output aria-label={`${label} zoom`}>{Math.round(bounded.zoom * 100)}%</output>
        <button
          type="button"
          aria-label={`Zoom in ${label}`}
          disabled={!image.width}
          onClick={() => update({ ...bounded, zoom: bounded.zoom + 0.25 })}
        >
          +
        </button>
        <button type="button" onClick={() => onChange({ ...DEFAULT_CAMERA_VIEW })}>
          Reset view
        </button>
        <button
          type="button"
          onClick={() => void fullscreen()}
          aria-label={`Full screen ${label}`}
          title="Full screen"
        >
          &#x26F6;
        </button>
        <span className="muted">Drag image to pan</span>
      </div>
      <div className="camera-line-controls" ref={setToolbar} />
    </div>
  )
}
