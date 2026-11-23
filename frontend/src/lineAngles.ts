export interface Line {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface Point {
  x: number
  y: number
}

export interface LineIntersection {
  x: number
  y: number
  angle: number
}

export interface VisibleLine extends Line {
  visible: boolean
}

export interface VisibleLineIntersection extends LineIntersection {
  firstIndex: number
  secondIndex: number
}

const toRadians = (degrees: number) => (degrees * Math.PI) / 180
const toDegrees = (radians: number) => (radians * 180) / Math.PI

export function lineAngleDegrees(line: Line, imageWidth: number, imageHeight: number): number | null {
  if (
    ![line.x1, line.y1, line.x2, line.y2, imageWidth, imageHeight].every(Number.isFinite) ||
    imageWidth <= 0 ||
    imageHeight <= 0
  ) {
    return null
  }

  const dx = (line.x2 - line.x1) * imageWidth
  const dy = (line.y2 - line.y1) * imageHeight
  if (dx === 0 && dy === 0) return null
  return toDegrees(Math.atan2(Math.abs(dy), Math.abs(dx)))
}

export function intersectLineSegments(
  first: Line,
  second: Line,
  imageWidth: number,
  imageHeight: number,
): LineIntersection | null {
  if (
    ![imageWidth, imageHeight].every(Number.isFinite) ||
    imageWidth <= 0 ||
    imageHeight <= 0 ||
    lineAngleDegrees(first, imageWidth, imageHeight) === null ||
    lineAngleDegrees(second, imageWidth, imageHeight) === null
  ) {
    return null
  }

  const firstStart = { x: (first.x1 * imageWidth) / 100, y: (first.y1 * imageHeight) / 100 }
  const firstVector = {
    x: ((first.x2 - first.x1) * imageWidth) / 100,
    y: ((first.y2 - first.y1) * imageHeight) / 100,
  }
  const secondStart = { x: (second.x1 * imageWidth) / 100, y: (second.y1 * imageHeight) / 100 }
  const secondVector = {
    x: ((second.x2 - second.x1) * imageWidth) / 100,
    y: ((second.y2 - second.y1) * imageHeight) / 100,
  }
  const cross = (a: Point, b: Point) => a.x * b.y - a.y * b.x
  const denominator = cross(firstVector, secondVector)
  const scale = Math.hypot(firstVector.x, firstVector.y) * Math.hypot(secondVector.x, secondVector.y)
  if (scale === 0 || Math.abs(denominator) <= scale * 1e-10) return null

  const betweenStarts = {
    x: secondStart.x - firstStart.x,
    y: secondStart.y - firstStart.y,
  }
  const firstParameter = cross(betweenStarts, secondVector) / denominator
  const secondParameter = cross(betweenStarts, firstVector) / denominator
  const epsilon = 1e-10
  if (
    firstParameter < -epsilon ||
    firstParameter > 1 + epsilon ||
    secondParameter < -epsilon ||
    secondParameter > 1 + epsilon
  ) {
    return null
  }

  const x = firstStart.x + firstParameter * firstVector.x
  const y = firstStart.y + firstParameter * firstVector.y
  if (x < -epsilon || x > imageWidth + epsilon || y < -epsilon || y > imageHeight + epsilon) {
    return null
  }
  const dot =
    firstVector.x * secondVector.x + firstVector.y * secondVector.y
  const angle = toDegrees(Math.atan2(Math.abs(denominator), Math.abs(dot)))
  return {
    x: Math.max(0, Math.min(100, (x / imageWidth) * 100)),
    y: Math.max(0, Math.min(100, (y / imageHeight) * 100)),
    angle,
  }
}

export function findVisibleLineIntersections(
  lines: readonly VisibleLine[],
  imageWidth: number,
  imageHeight: number,
): VisibleLineIntersection[] {
  const intersections: VisibleLineIntersection[] = []
  for (let firstIndex = 0; firstIndex < lines.length; firstIndex += 1) {
    if (!lines[firstIndex].visible) continue
    for (let secondIndex = firstIndex + 1; secondIndex < lines.length; secondIndex += 1) {
      if (!lines[secondIndex].visible) continue
      const intersection = intersectLineSegments(
        lines[firstIndex],
        lines[secondIndex],
        imageWidth,
        imageHeight,
      )
      if (intersection) intersections.push({ ...intersection, firstIndex, secondIndex })
    }
  }
  return intersections
}

export function snapLineEndpointToAngle(
  fixed: Point,
  dragged: Point,
  imageWidth: number,
  imageHeight: number,
  stepDegrees = 5,
): Point | null {
  if (
    ![fixed.x, fixed.y, dragged.x, dragged.y, imageWidth, imageHeight, stepDegrees].every(
      Number.isFinite,
    ) ||
    imageWidth <= 0 ||
    imageHeight <= 0 ||
    stepDegrees <= 0
  ) {
    return null
  }

  const fixedX = (fixed.x * imageWidth) / 100
  const fixedY = (fixed.y * imageHeight) / 100
  const dx = ((dragged.x - fixed.x) * imageWidth) / 100
  const dy = ((dragged.y - fixed.y) * imageHeight) / 100
  const length = Math.hypot(dx, dy)
  if (length === 0) return dragged

  const angleDegrees = Math.round(toDegrees(Math.atan2(dy, dx)) / stepDegrees) * stepDegrees
  const angle = toRadians(angleDegrees)
  const unitX = Math.cos(angle)
  const unitY = Math.sin(angle)
  const maxX = unitX > 0 ? (imageWidth - fixedX) / unitX : unitX < 0 ? -fixedX / unitX : Infinity
  const maxY =
    unitY > 0 ? (imageHeight - fixedY) / unitY : unitY < 0 ? -fixedY / unitY : Infinity
  const snappedLength = Math.min(length, maxX, maxY)

  return {
    x: ((fixedX + unitX * snappedLength) / imageWidth) * 100,
    y: ((fixedY + unitY * snappedLength) / imageHeight) * 100,
  }
}
