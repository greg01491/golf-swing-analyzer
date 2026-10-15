import assert from 'node:assert/strict'
import test from 'node:test'
import { clampPlaybackPercent, MIN_SUPPORTED_PLAYBACK_RATE, playbackRateForPercent } from '../src/playback.ts'

test('slow-motion rates respect Chromium minimum and preserve explicit pause', () => {
  assert.equal(playbackRateForPercent(0), 0)
  assert.equal(clampPlaybackPercent(0.06), MIN_SUPPORTED_PLAYBACK_RATE * 100)
  assert.equal(playbackRateForPercent(6), MIN_SUPPORTED_PLAYBACK_RATE)
  assert.equal(playbackRateForPercent(MIN_SUPPORTED_PLAYBACK_RATE * 100), MIN_SUPPORTED_PLAYBACK_RATE)
  assert.equal(playbackRateForPercent(100), 1)
  assert.equal(clampPlaybackPercent(Number.NaN), 100)
})