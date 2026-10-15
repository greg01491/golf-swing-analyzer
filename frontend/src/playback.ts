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