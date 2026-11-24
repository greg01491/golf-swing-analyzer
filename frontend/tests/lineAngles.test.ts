import assert from 'node:assert/strict'
import test from 'node:test'
import {
  findVisibleLineIntersections,
  intersectLineSegments,
  lineAngleDegrees,
  snapLineEndpointToAngle,
  type Line,
} from '../src/lineAngles.ts'

const diagonal: Line = { x1: 20, y1: 80, x2: 80, y2: 20 }
const reversedDiagonal: Line = { x1: 80, y1: 20, x2: 20, y2: 80 }

function lineWithAngle(angle: number, lean: 'up' | 'down'): Line {
  const dy = 60 * Math.tan((angle * Math.PI) / 180) * (lean === 'up' ? -1 : 1)
  return { x1: 20, y1: 50, x2: 80, y2: 50 + dy }
}

test('line angle uses image dimensions for landscape and portrait views', () => {
  assert.ok(Math.abs((lineAngleDegrees(diagonal, 1280, 720) ?? 0) - 29.4) < 0.1)
  assert.ok(Math.abs((lineAngleDegrees(diagonal, 720, 1280) ?? 0) - 60.6) < 0.1)
  assert.equal(lineAngleDegrees(diagonal, 1280, 720), lineAngleDegrees(reversedDiagonal, 1280, 720))
  assert.equal(lineAngleDegrees(diagonal, 0, 720), null)
  assert.equal(lineAngleDegrees({ x1: 1, y1: 1, x2: 1, y2: 1 }, 100, 100), null)
})

test('finite segment intersections report an acute image-space angle only within both segments', () => {
  const horizontal: Line = { x1: 20, y1: 50, x2: 80, y2: 50 }
  const vertical: Line = { x1: 50, y1: 20, x2: 50, y2: 80 }
  assert.deepEqual(intersectLineSegments(horizontal, vertical, 100, 100), {
    x: 50,
    y: 50,
    angle: 90,
  })

  const crossing = intersectLineSegments(
    lineWithAngle(30, 'up'),
    lineWithAngle(40, 'down'),
    100,
    100,
  )
  assert.ok(crossing)
  if (crossing) {
    assert.ok(Math.abs(crossing.angle - 70) < 1e-10)
    assert.ok(crossing.x >= 20 && crossing.x <= 80)
  }

  const shortHorizontal: Line = { x1: 20, y1: 50, x2: 40, y2: 50 }
  assert.equal(intersectLineSegments(shortHorizontal, vertical, 100, 100), null)
  assert.equal(intersectLineSegments(horizontal, { ...horizontal, y1: 40, y2: 40 }, 100, 100), null)
})

test('all visible line pairs are enumerated and hidden lines are excluded', () => {
  const lines = [
    { x1: 20, y1: 50, x2: 80, y2: 50, visible: true },
    { x1: 50, y1: 20, x2: 50, y2: 80, visible: true },
    { x1: 20, y1: 20, x2: 80, y2: 80, visible: true },
  ]
  const intersections = findVisibleLineIntersections(lines, 100, 100)
  assert.equal(intersections.length, 3)
  assert.deepEqual(
    intersections.map(({ firstIndex, secondIndex }) => [firstIndex, secondIndex]),
    [
      [0, 1],
      [0, 2],
      [1, 2],
    ],
  )
  assert.equal(
    findVisibleLineIntersections(lines.map((line, index) => ({ ...line, visible: index !== 1 })), 100, 100)
      .length,
    1,
  )
})

test('Shift-snap quantizes direction and includes level and plumb', () => {
  const fixed = { x: 50, y: 50 }
  const snappedDiagonal = snapLineEndpointToAngle(fixed, { x: 80, y: 22 }, 100, 100)
  assert.ok(snappedDiagonal)
  assert.ok(Math.abs((lineAngleDegrees({ x1: fixed.x, y1: fixed.y, x2: snappedDiagonal.x, y2: snappedDiagonal.y }, 100, 100) ?? 0) - 45) < 1e-10)

  assert.deepEqual(snapLineEndpointToAngle(fixed, { x: 80, y: 50 }, 100, 100), {
    x: 80,
    y: 50,
  })
  assert.deepEqual(snapLineEndpointToAngle(fixed, { x: 50, y: 80 }, 100, 100), {
    x: 50,
    y: 80,
  })
  assert.equal(snapLineEndpointToAngle(fixed, { x: 70, y: 70 }, 0, 100), null)
})
