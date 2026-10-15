import assert from 'node:assert/strict'
import test from 'node:test'
import type { MetricEntry } from '../src/api.ts'
import { METRIC_INFO } from '../src/metricInfo.ts'
import {
  allMeasuredMetricsInRange,
  comparableMetricSeries,
  eligibleTips,
  metricStatus,
  metricSummary,
  spokenMetricFeedback,
} from '../src/metricFeedback.ts'

const measurements = (): MetricEntry[] =>
  Object.keys(METRIC_INFO).map((name) => ({
    name,
    value: 1,
    unit: 'deg',
    range: { min: 0, max: 2 },
    in_range: true,
    status: 'valid',
    definition_id: `${name}:2`,
    reasons: [],
  }))

test('all-in-range requires all nineteen compatible verified measurements', () => {
  assert.equal(allMeasuredMetricsInRange(measurements()), true)
  assert.equal(allMeasuredMetricsInRange([]), false)
  assert.equal(allMeasuredMetricsInRange(measurements().slice(1)), false)
  const metrics = measurements()
  metrics[0].status = 'estimated'
  assert.equal(allMeasuredMetricsInRange(metrics), false)
  assert.match(metricSummary(metrics), /incomplete/)
  metrics[0].status = undefined
  assert.equal(metricStatus(metrics[0]), 'legacy-unverified')
  metrics[0].status = 'valid'
  metrics[0].definition_id = `${metrics[0].name}:3`
  assert.equal(allMeasuredMetricsInRange(metrics), false)
})

test('uncertain and legacy measurements cannot supply tips or spoken verdicts', () => {
  for (const status of ['estimated', 'unavailable', 'legacy-unverified'] as const) {
    const metrics = measurements()
    metrics[0].status = status
    metrics[0].in_range = false
    metrics[0].reasons = ['missing_reference: the ground could not be verified']
    const analysis = {
      metrics,
      tips: [{ metric: metrics[0].name, direction: 'high', severity: 1, text: 'UNSAFE COACHING' }],
    }
    assert.equal(eligibleTips(analysis).length, 0)
    const speech = spokenMetricFeedback(analysis, metrics[0].name)
    assert.doesNotMatch(speech, /UNSAFE|target range/)
    assert.match(spokenMetricFeedback(analysis, null), /incomplete/)
  }
})

test('history separates targets and clubs and excludes incompatible definitions', () => {
  const metric = measurements()[0]
  const sessions = [
    { id: 'a', created_at: null, club: 'driver', metrics: [metric] },
    { id: 'b', created_at: null, club: '7_iron', metrics: [metric] },
    {
      id: 'c',
      created_at: null,
      club: 'driver',
      metrics: [{ ...metric, range: { min: 2, max: 3 } }],
    },
    {
      id: 'd',
      created_at: null,
      club: 'driver',
      metrics: [{ ...metric, definition_id: `${metric.name}:1` }],
    },
  ]
  const series = comparableMetricSeries(sessions)
  assert.equal(series.length, 3)
  assert.equal(
    series.reduce((count, item) => count + item.points.length, 0),
    3,
  )
})
