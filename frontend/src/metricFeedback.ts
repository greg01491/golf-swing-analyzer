import type { MetricEntry, StatsSession, TipEntry } from './api'
import { METRIC_INFO, formatMetricName } from './metricInfo.ts'

export function metricStatus(metric: MetricEntry): NonNullable<MetricEntry['status']> {
  if (!metric.definition_id || metric.definition_id !== `${metric.name}:2` || !metric.status) {
    return 'legacy-unverified'
  }
  if (metric.value === null || !Number.isFinite(metric.value)) return 'unavailable'
  return metric.status
}

export function isValidatedMetric(metric: MetricEntry): boolean {
  return metricStatus(metric) === 'valid'
}

export function metricReason(metric: MetricEntry): string {
  if (metricStatus(metric) === 'legacy-unverified') return 'Legacy result; reanalysis required.'
  return metric.reasons?.map((reason) => reason.replace(/^[^:]+:\s*/, '')).join('; ') ?? ''
}

export function eligibleTips(analysis: { metrics: MetricEntry[]; tips: TipEntry[] }): TipEntry[] {
  const names = new Set(analysis.metrics.filter(isValidatedMetric).map((metric) => metric.name))
  return analysis.tips.filter((tip) => names.has(tip.metric))
}

export function allMeasuredMetricsInRange(metrics: MetricEntry[]): boolean {
  return (
    metrics.length === Object.keys(METRIC_INFO).length &&
    new Set(metrics.map((metric) => metric.name)).size === Object.keys(METRIC_INFO).length &&
    metrics.every(
      (metric) =>
        metric.name in METRIC_INFO &&
        isValidatedMetric(metric) &&
        metric.range !== null &&
        metric.in_range === true,
    )
  )
}

export function metricSummary(metrics: MetricEntry[]): string {
  if (allMeasuredMetricsInRange(metrics)) return 'Everything measured was in range.'
  if (
    metrics.length !== Object.keys(METRIC_INFO).length ||
    metrics.some((metric) => !isValidatedMetric(metric))
  ) {
    return 'Assessment incomplete: some measurements could not be verified.'
  }
  return 'There are no actionable tips for this swing.'
}

export function spokenMetricFeedback(
  analysis: { metrics: MetricEntry[]; tips: TipEntry[] },
  focusedMetric: string | null,
): string {
  const tips = eligibleTips(analysis)
  if (focusedMetric) {
    const label = formatMetricName(focusedMetric)
    const metric = analysis.metrics.find((item) => item.name === focusedMetric)
    if (!metric) return `I could not measure ${label} on this swing.`
    if (!isValidatedMetric(metric)) {
      return `${label} is ${metricStatus(metric)}. ${metricReason(metric)}`
    }
    const tip = tips.find((item) => item.metric === focusedMetric)
    if (tip) return `${label}: ${tip.text}`
    const result =
      metric.in_range === true
        ? 'in your target range'
        : metric.in_range === false
          ? 'outside your target range'
          : 'without a compatible target range'
    return `${label}: ${metric.value} ${metric.unit}, ${result}.`
  }
  if (tips.length) return tips[0].text
  return metricSummary(analysis.metrics)
}

export interface MetricSeries {
  key: string
  name: string
  context: string
  unit: string
  range: { min: number; max: number } | null
  points: { label: string; value: number; inRange: boolean | null }[]
}

export function comparableMetricSeries(sessions: StatsSession[]): MetricSeries[] {
  const groups = new Map<string, MetricSeries>()
  for (const session of sessions) {
    for (const metric of session.metrics) {
      if (!isValidatedMetric(metric) || metric.value === null) continue
      const key = JSON.stringify([
        metric.name,
        metric.definition_id,
        metric.unit,
        session.club ?? null,
        metric.range,
      ])
      let series = groups.get(key)
      if (!series) {
        series = {
          key,
          name: metric.name,
          context: `${session.club?.replaceAll('_', ' ') ?? 'club not recorded'}; ${metric.definition_id}`,
          unit: metric.unit,
          range: metric.range,
          points: [],
        }
        groups.set(key, series)
      }
      const date = session.created_at ? new Date(session.created_at) : null
      series.points.push({
        label: date ? date.toLocaleString() : session.id,
        value: metric.value,
        inRange: metric.in_range,
      })
    }
  }
  return [...groups.values()]
}
