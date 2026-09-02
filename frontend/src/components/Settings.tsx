import { useEffect, useState } from 'react'
import { api } from '../api'
import LivePreview from './LivePreview'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Cfg = Record<string, any>

type FieldSpec = { key: string; label: string; unit?: string; hint?: string }
type SectionSpec = { key: string; title: string; hint?: string; fields: FieldSpec[] }

/** Settings edits the live config.yaml through the API (spec.md FR22).
 * Numeric leaf fields of the sections below are editable; anything else
 * stays untouched in the saved document. Labels/units are spelled out here
 * rather than showing the raw snake_case config keys. */
const SECTIONS: SectionSpec[] = [
  {
    key: 'audio_trigger',
    title: 'Audio trigger',
    hint: 'How the microphone decides a ball has been struck, and how much footage is kept around it.',
    fields: [
      {
        key: 'threshold_db',
        label: 'Trigger threshold',
        unit: 'dB',
        hint: 'How loud a sound must be to count as a strike. Closer to 0 is less sensitive.',
      },
      {
        key: 'pre_capture_delay_s',
        label: 'Pre-roll',
        unit: 's',
        hint: 'How much footage from before the strike is kept, so the backswing is included.',
      },
      {
        key: 'capture_duration_s',
        label: 'Capture length',
        unit: 's',
        hint: 'Total length of each recorded clip.',
      },
      {
        key: 'trigger_cooldown_s',
        label: 'Cooldown',
        unit: 's',
        hint: 'Ignore further strikes for this long, so one shot is not captured twice.',
      },
    ],
  },
  {
    key: 'cameras',
    title: 'Recording buffer',
    hint: 'Extra footage held in memory so a strike is never clipped short.',
    fields: [
      {
        key: 'buffer_margin_s',
        label: 'Buffer margin',
        unit: 's',
        hint: 'Higher values are safer but use more memory.',
      },
    ],
  },
  {
    key: 'calibration',
    title: 'Calibration',
    fields: [
      {
        key: 'max_age_days',
        label: 'Recalibration reminder',
        unit: 'days',
        hint: 'Warn that the camera calibration is stale after this many days.',
      },
    ],
  },
]

const CAMERA_FIELDS: FieldSpec[] = [
  { key: 'id', label: 'Device index' },
  { key: 'width', label: 'Width', unit: 'px' },
  { key: 'height', label: 'Height', unit: 'px' },
  { key: 'fps', label: 'Frame rate', unit: 'fps' },
]

const prettifyMetric = (metric: string) =>
  metric.replace(/_(deg|pct|s|m)$/, '').replaceAll('_', ' ')

const metricUnit = (metric: string) => {
  if (metric.endsWith('_deg')) return '°'
  if (metric.endsWith('_pct')) return '%'
  if (metric.endsWith('_s')) return 's'
  if (metric.endsWith('_m')) return 'm'
  return ''
}

export default function Settings() {
  const [config, setConfig] = useState<Cfg | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.config().then((c) => setConfig(c as Cfg))
  }, [])

  if (!config) return <div className="panel">loading…</div>

  const setField = (section: string, field: string, value: number) =>
    setConfig({ ...config, [section]: { ...config[section], [field]: value } })

  const setRange = (metric: string, bound: 'min' | 'max', value: number) =>
    setConfig({
      ...config,
      metrics: {
        ...config.metrics,
        reference_ranges: {
          ...config.metrics.reference_ranges,
          [metric]: { ...config.metrics.reference_ranges[metric], [bound]: value },
        },
      },
    })

  const setCameraField = (index: number, field: string, value: number) => {
    const devices = config.cameras.devices.map((d: Cfg, i: number) =>
      i === index ? { ...d, [field]: value } : d,
    )
    setConfig({ ...config, cameras: { ...config.cameras, devices } })
  }

  const save = async () => {
    setMessage(null)
    setSaving(true)
    try {
      const res = await api.saveConfig(config)
      setFailed(false)
      setMessage(`Saved — ${res.note}`)
    } catch (e) {
      setFailed(true)
      setMessage(String(e))
    } finally {
      setSaving(false)
    }
  }

  const numberField = (
    spec: FieldSpec,
    value: number,
    onChange: (value: number) => void,
  ) => (
    <label key={spec.key} className="field">
      <span className="field-text">
        <span className="field-label">{spec.label}</span>
        {spec.hint && <span className="field-hint">{spec.hint}</span>}
      </span>
      <span className="field-control">
        <input
          type="number"
          step="any"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        {spec.unit && <span className="field-unit">{spec.unit}</span>}
      </span>
    </label>
  )

  return (
    <div className="settings">
      <div className="settings-header">
        <h2>Settings</h2>
        <p className="settings-intro">
          These values are written straight to your configuration file. Most changes take
          effect the next time capture is armed.
        </p>
      </div>

      {SECTIONS.map((section) => (
        <section className="settings-section" key={section.key}>
          <h3>{section.title}</h3>
          {section.hint && <p className="section-hint">{section.hint}</p>}
          <div className="field-list">
            {section.fields.map((spec) =>
              numberField(spec, config[section.key][spec.key], (value) =>
                setField(section.key, spec.key, value),
              ),
            )}
          </div>
        </section>
      ))}

      <section className="settings-section">
        <h3>Processing</h3>
        <div className="field-list">
          <label className="field">
            <span className="field-text">
              <span className="field-label">Analyse every capture automatically</span>
              <span className="field-hint">
                Runs pose tracking, 3D reconstruction, metrics and tips as soon as a swing is
                recorded. Turn off to record now and analyse later.
              </span>
            </span>
            <span className="field-control">
              <input
                type="checkbox"
                checked={Boolean(config.processing?.auto_process)}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    processing: { ...config.processing, auto_process: e.target.checked },
                  })
                }
              />
            </span>
          </label>
        </div>
      </section>

      <section className="settings-section">
        <h3>Cameras</h3>
        <p className="section-hint">
          If a camera is mounted sideways or upside down, use rotation to correct it. This
          fixes the saved footage itself, not just the preview — a rotated person confuses the
          pose-tracking model. The previews show the orientation that is currently running;
          cameras start automatically on this screen, and saving restarts them with your
          changes.
        </p>
        {config.cameras.devices.map((dev: Cfg, i: number) => (
          <div key={i} className="camera-config">
            <div className="camera-config-name">{dev.role}</div>
            <div className="camera-fields">
              {CAMERA_FIELDS.map((spec) =>
                numberField(spec, dev[spec.key], (value) => setCameraField(i, spec.key, value)),
              )}
            </div>
            <label className="field">
              <span className="field-text">
                <span className="field-label">Rotation</span>
              </span>
              <span className="field-control">
                <select
                  value={dev.rotation_deg ?? 0}
                  onChange={(e) => setCameraField(i, 'rotation_deg', Number(e.target.value))}
                >
                  <option value={0}>None</option>
                  <option value={90}>90° clockwise</option>
                  <option value={180}>180°</option>
                  <option value={270}>270° clockwise</option>
                </select>
              </span>
            </label>
            <LivePreview camera={dev.role} label={`${dev.role} preview`} />
          </div>
        ))}
      </section>

      <section className="settings-section">
        <h3>Metric reference ranges</h3>
        <p className="section-hint">
          A swing metric is flagged when it falls outside these bounds. Adjust them to match
          your own targets.
        </p>
        <div className="field-list">
          {Object.entries(config.metrics.reference_ranges as Cfg).map(([metric, range]) => (
            <div key={metric} className="range-row">
              <span className="range-name">{prettifyMetric(metric)}</span>
              <label className="field">
                <span className="field-unit">min</span>
                <input
                  type="number"
                  step="any"
                  value={(range as Cfg).min}
                  onChange={(e) => setRange(metric, 'min', Number(e.target.value))}
                />
                {metricUnit(metric) && <span className="field-unit">{metricUnit(metric)}</span>}
              </label>
              <label className="field">
                <span className="field-unit">max</span>
                <input
                  type="number"
                  step="any"
                  value={(range as Cfg).max}
                  onChange={(e) => setRange(metric, 'max', Number(e.target.value))}
                />
                {metricUnit(metric) && <span className="field-unit">{metricUnit(metric)}</span>}
              </label>
            </div>
          ))}
        </div>
      </section>

      <div className="settings-actions">
        <button className="save-btn" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save settings'}
        </button>
        {message && <p className={failed ? 'save-message error' : 'save-message muted'}>{message}</p>}
      </div>
    </div>
  )
}
