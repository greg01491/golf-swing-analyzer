export interface Size {
  width: number
  height: number
}

export interface CameraView {
  zoom: number
  x: number
  y: number
}

export const DEFAULT_CAMERA_VIEW: CameraView = { zoom: 1, x: 0, y: 0 }

export function containImage(image: Size, viewport: Size): Size {
  if (
    ![image.width, image.height, viewport.width, viewport.height].every(
      (value) => Number.isFinite(value) && value > 0,
    )
  )
    return { width: 0, height: 0 }
  const scale = Math.min(viewport.width / image.width, viewport.height / image.height)
  return { width: image.width * scale, height: image.height * scale }
}

// Pan is stored as a fraction of the viewport, so resizing preserves composition.
export function boundCameraView(view: CameraView, image: Size, viewport: Size): CameraView {
  const zoom = Number.isFinite(view.zoom) ? Math.max(1, view.zoom) : 1
  const bound = (value: number, imageLength: number, viewportLength: number) => {
    if (!Number.isFinite(value) || viewportLength <= 0 || imageLength <= 0) return 0
    const limit = Math.max(0.5, (imageLength * zoom) / (2 * viewportLength))
    return Math.max(-limit, Math.min(limit, value))
  }
  return {
    zoom,
    x: bound(view.x, image.width, viewport.width),
    y: bound(view.y, image.height, viewport.height),
  }
}

export function imagePointFromClient(
  x: number,
  y: number,
  rect: { left: number; top: number; width: number; height: number },
): { x: number; y: number } | null {
  if (
    ![x, y, rect.left, rect.top, rect.width, rect.height].every(Number.isFinite) ||
    rect.width <= 0 ||
    rect.height <= 0
  )
    return null
  return {
    x: Math.max(0, Math.min(100, ((x - rect.left) / rect.width) * 100)),
    y: Math.max(0, Math.min(100, ((y - rect.top) / rect.height) * 100)),
  }
}
