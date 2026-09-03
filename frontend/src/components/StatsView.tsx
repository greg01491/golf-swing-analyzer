import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { StatsSession } from '../api'
import { METRIC_INFO, formatMetricName } from '../metricInfo'

interface Point {
  label: string
  value: number
  inRange: boolean | null
}

interface Series {
  name: string
  unit: string
  range: { min: number; max: number } | null
  points: Point[]
}

// SVG geometry (a viewBox coordinate space; the <svg> scales to its box).
const W = 560
const H = 200
const PAD_L = 46
const PAD_R = 14
const PAD_T = 14
const PAD_B = 30
const GREEN = '#4ade80'
const RED = '#f87171'

function MetricChart({ series }: { series: Series }) {
  const values = series.points.map((p) => p.value)
  const lo = Math.min(...values, series.range?.min ?? Infinity)
  const hi = Math.max(...values, series.range?.max ?? -Infinity)
  const span = hi - lo || 1
  const yMin = lo - span * 0.12
  const yMax = hi + span * 0.12

  const plotW = W - PAD_L - PAD_R
  const plotH = H - PAD_T - PAD_B
  const n = series.points.length
  const x = (i: number) => PAD_L + (n <= 1 ? plotW / 2 : (plotW * i) / (n - 1))
  const y = (v: number) => PAD_T + plotH * (1 - (v - yMin) / (yMax - yMin))

  const line = series.points.map((p, i) => `${x(i)},${y(p.value)}`).join(' ')
  const bandTop = series.range ? y(series.range.max) : 0
  const bandBottom = series.range ? y(series.range.min) : 0
  const latest = series.points[series.points.length - 1]

  return (
    <div className="panel stat-card">
      <div className="stat-card-head">
        <h4>{formatMetricName(series.name)}</h4>
        <span
          className="stat-latest"
          style={{ color: latest.inRange === false ? RED : latest.inRange ? GREEN : 'inherit' }}
        >
          {latest.value} {series.unit}
        </span>
      </div>
      {series.range && (
        <p className="muted stat-target">
          target {series.range.min}–{series.range.max} {series.unit}
        </p>
      )}
      <svg className="stat-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {/* target range band (green = in range) */}
        {series.range && (
          <>
            <rect
              x={PAD_L}
              y={bandTop}
              width={plotW}
              height={Math.max(0, bandBottom - bandTop)}
              fill={GREEN}
              opacity={0.12}
            />
            <line
              x1={PAD_L}
              x2={W - PAD_R}
              y1={bandTop}
              y2={bandTop}
              stroke={GREEN}
              strokeWidth={1}
              strokeDasharray="4 4"
              opacity={0.6}
            />
            <line
              x1={PAD_L}
              x2={W - PAD_R}
              y1={bandBottom}
              y2={bandBottom}
              stroke={GREEN}
              strokeWidth={1}
              strokeDasharray="4 4"
              opacity={0.6}
            />
          </>
        )}
        {/* axis frame */}
        <line x1={PAD_L} x2={PAD_L} y1={PAD_T} y2={H - PAD_B} stroke="#2d3743" strokeWidth={1} />
        <line
          x1={PAD_L}
          x2={W - PAD_R}
          y1={H - PAD_B}
          y2={H - PAD_B}
          stroke="#2d3743"
          strokeWidth={1}
        />
        {/* y labels */}
        <text x={PAD_L - 6} y={PAD_T + 4} className="stat-axis" textAnchor="end">
          {yMax.toFixed(0)}
        </text>
        <text x={PAD_L - 6} y={H - PAD_B} className="stat-axis" textAnchor="end">
          {yMin.toFixed(0)}
        </text>
        {/* trend line */}
        {n > 1 && (
          <polyline points={line} fill="none" stroke="#8b98a5" strokeWidth={1.5} opacity={0.7} />
        )}
        {/* points: green in range, red out of range */}
        {series.points.map((p, i) => (
          <circle
            key={i}
            cx={x(i)}
            cy={y(p.value)}
            r={3.5}
            fill={p.inRange === false ? RED : p.inRange ? GREEN : '#8b98a5'}
          >
            <title>
              {p.label}: {p.value} {series.unit}
            </title>
          </circle>
        ))}
      </svg>
    </div>
  )
}

export default function StatsView() {
  const [stats, setStats] = useState<StatsSession[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch(() => setError(true))
  }, [])

  const seriesList = useMemo<Series[]>(() => {
    if (!stats) return []
    // stable metric order: known metrics first (METRIC_INFO order), then any
    // extras in first-seen order
    const order = Object.keys(METRIC_INFO)
    const seen = new Set<string>()
    for (const s of stats) for (const m of s.metrics) seen.add(m.name)
    const names = [
      ...order.filter((n) => seen.has(n)),
      ...[...seen].filter((n) => !order.includes(n)),
    ]
    return names
      .map((name) => {
        const points: Point[] = []
        let unit = ''
        let range: { min: number; max: number } | null = null
        for (const s of stats) {
          const m = s.metrics.find((mm) => mm.name === name)
          if (!m || m.value === null) continue
          unit = m.unit
          if (m.range) range = m.range
          const dt = s.created_at ? new Date(s.created_at) : null
          points.push({
            label: dt
              ? dt.toLocaleDateString([], { day: 'numeric', month: 'short' }) +
                ' ' +
                dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : s.id,
            value: m.value,
            inRange: m.in_range,
          })
        }
        return { name, unit, range, points }
      })
      .filter((s) => s.points.length > 0)
  }, [stats])

  if (error) {
    return (
      <div className="stats-view">
        <p className="error">couldn't load stats — is the backend running?</p>
      </div>
    )
  }
  if (!stats) return <div className="stats-view">loading…</div>

  const swingCount = stats.length

  return (
    <div className="stats-view">
      <h2>stats over time</h2>
      {seriesList.length === 0 ? (
        <p className="muted">no processed swings yet — capture and process a swing first.</p>
      ) : (
        <>
          <p className="muted">
            {swingCount} processed swing{swingCount === 1 ? '' : 's'}. Each dot is one swing (oldest
            on the left); green means in range, red means out of range. The shaded band is the target
            range.
          </p>
          <div className="stats-grid">
            {seriesList.map((s) => (
              <MetricChart key={s.name} series={s} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
