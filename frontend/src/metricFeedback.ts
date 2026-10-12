import type { MetricEntry } from './api'

export function allMeasuredMetricsInRange(metrics: MetricEntry[]): boolean {
  return (
    metrics.length > 0 &&
    metrics.every(
      (metric) =>
        metric.value !== null && metric.range !== null && metric.in_range === true,
    )
  )
}