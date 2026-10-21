export const MIN_SUPPORTED_PLAYBACK_RATE = 0.0625

export function clampPlaybackPercent(value: number): number {
  if (!Number.isFinite(value)) return 100
  const bounded = Math.max(0, Math.min(100, value))
  return bounded === 0 ? 0 : Math.max(MIN_SUPPORTED_PLAYBACK_RATE * 100, bounded)
}

export function playbackRateForPercent(value: number): number {
  const percent = clampPlaybackPercent(value)
  return percent === 0 ? 0 : Math.max(MIN_SUPPORTED_PLAYBACK_RATE, Math.min(1, percent / 100))
}

export function stepFrameTime(
  currentTime: number,
  fps: number,
  direction: -1 | 1,
  duration = Number.POSITIVE_INFINITY,
): number {
  const frameRate = Number.isFinite(fps) && fps > 0 ? fps : 30
  const currentFrame = Math.round(Math.max(0, currentTime) * frameRate)
  const lastFrame = Number.isFinite(duration)
    ? Math.max(0, Math.ceil(duration * frameRate) - 1)
    : Number.POSITIVE_INFINITY
  return Math.min(lastFrame, Math.max(0, currentFrame + direction)) / frameRate
}