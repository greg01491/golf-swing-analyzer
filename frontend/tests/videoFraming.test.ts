import assert from 'node:assert/strict'
import test from 'node:test'
import {
  boundCameraView,
  containImage,
  DEFAULT_CAMERA_VIEW,
  imagePointFromClient,
} from '../src/videoFraming.ts'

test('portrait and landscape images fit without cropping or stretching', () => {
  assert.deepEqual(containImage({ width: 1920, height: 1080 }, { width: 600, height: 400 }), {
    width: 600,
    height: 337.5,
  })
  assert.deepEqual(containImage({ width: 1080, height: 1920 }, { width: 600, height: 400 }), {
    width: 225,
    height: 400,
  })
  assert.deepEqual(containImage({ width: 0, height: 0 }, { width: 600, height: 400 }), {
    width: 0,
    height: 0,
  })
  assert.deepEqual(containImage({ width: Infinity, height: 100 }, { width: 600, height: 400 }), {
    width: 0,
    height: 0,
  })
})

test('pan remains finite and bounded while allowing repositioning at default zoom', () => {
  const image = { width: 225, height: 400 }
  const viewport = { width: 600, height: 400 }
  assert.deepEqual(boundCameraView(DEFAULT_CAMERA_VIEW, image, viewport), DEFAULT_CAMERA_VIEW)
  assert.deepEqual(boundCameraView({ zoom: 2, x: 10, y: -10 }, image, viewport), {
    zoom: 2,
    x: 0.5,
    y: -1,
  })
  assert.deepEqual(
    boundCameraView({ zoom: NaN, x: NaN, y: Infinity }, image, viewport),
    DEFAULT_CAMERA_VIEW,
  )
  assert.deepEqual(
    boundCameraView({ zoom: 1, x: 1, y: 1 }, { width: 0, height: 0 }, { width: 0, height: 0 }),
    DEFAULT_CAMERA_VIEW,
  )
})

test('transformed image points round-trip for portrait and landscape, including resize', () => {
  for (const intrinsic of [
    { width: 1920, height: 1080 },
    { width: 1080, height: 1920 },
  ]) {
    for (const viewport of [
      { width: 600, height: 400 },
      { width: 320, height: 240 },
    ]) {
      const image = containImage(intrinsic, viewport)
      const view = boundCameraView({ zoom: 2.5, x: 0.2, y: -0.1 }, image, viewport)
      const rect = {
        left: (viewport.width - image.width * view.zoom) / 2 + view.x * viewport.width,
        top: (viewport.height - image.height * view.zoom) / 2 + view.y * viewport.height,
        width: image.width * view.zoom,
        height: image.height * view.zoom,
      }
      const point = imagePointFromClient(
        rect.left + rect.width * 0.3,
        rect.top + rect.height * 0.8,
        rect,
      )
      assert.ok(point)
      assert.ok(Math.abs(point.x - 30) < 1e-10)
      assert.ok(Math.abs(point.y - 80) < 1e-10)
    }
  }
})

test('line pointer mapping clips endpoints and rejects unloaded geometry', () => {
  assert.deepEqual(imagePointFromClient(-30, 200, { left: 0, top: 0, width: 100, height: 100 }), {
    x: 0,
    y: 100,
  })
  assert.equal(imagePointFromClient(10, 10, { left: 0, top: 0, width: 0, height: 0 }), null)
})
