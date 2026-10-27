import assert from 'node:assert/strict'
import test from 'node:test'
import {
  clampPlaybackPercent,
  MIN_SUPPORTED_PLAYBACK_RATE,
  playbackRateForPercent,
  stepFrameTime,
  commonPlaybackDuration,
  clampSeekTime,
} from '../src/playback.ts'

test('slow-motion rates respect Chromium minimum and preserve explicit pause', () => {
  assert.equal(playbackRateForPercent(0), 0)
  assert.equal(clampPlaybackPercent(0.06), MIN_SUPPORTED_PLAYBACK_RATE * 100)
  assert.equal(playbackRateForPercent(6), MIN_SUPPORTED_PLAYBACK_RATE)
  assert.equal(
    playbackRateForPercent(MIN_SUPPORTED_PLAYBACK_RATE * 100),
    MIN_SUPPORTED_PLAYBACK_RATE,
  )
  assert.equal(playbackRateForPercent(100), 1)
  assert.equal(clampPlaybackPercent(Number.NaN), 100)
})

test('shared duration waits for all cameras and uses the shorter recording', () => {
  assert.equal(commonPlaybackDuration([3, 2.5]), 2.5)
  assert.equal(commonPlaybackDuration([3]), 3)
  for (const durations of [[], [3, 0], [3, NaN], [Infinity], [-1]]) {
    assert.equal(commonPlaybackDuration(durations), 0)
  }
})

test('seeking clamps to valid frames including unequal durations', () => {
  assert.equal(clampSeekTime(10, 3, 120), 359 / 120)
  assert.equal(clampSeekTime(-1, 3, 120), 0)
  assert.equal(clampSeekTime(1.5, 3, 120), 1.5)
  assert.equal(clampSeekTime(2, NaN, 120), 0)
  assert.equal(clampSeekTime(NaN, 3, 120), 0)
})

test('frame stepping moves exactly one frame and clamps to clip bounds', () => {
  assert.equal(stepFrameTime(1, 120, 1), 1 + 1 / 120)
  assert.equal(stepFrameTime(1, 120, -1), 1 - 1 / 120)
  assert.equal(stepFrameTime(0, 120, -1), 0)
  assert.equal(stepFrameTime(2.99, 120, 1, 3), 359 / 120)
})
