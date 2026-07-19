import { useEffect, useState } from 'react'
import { api } from '../api'
import LivePreview from './LivePreview'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Cfg = Record<string, any>

/** Settings edits the live config.yaml through the API (spec.md FR22).
 * Numeric leaf fields of the sections below are editable; anything else
 * stays untouched in the saved document. */
const SECTIONS: [string, string[]][] = [
  ['audio_trigger', ['threshold_db', 'pre_capture_delay_s', 'capture_duration_s', 'trigger_cooldown_s']],
  ['cameras', ['buffer_margin_s']],
  ['calibration', ['max_age_days']],
]

export default function Settings() {
  const [config, setConfig] = useState<Cfg | null>(null)
  const [message, setMessage] = useState<string | null>(null)

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
    try {
      const res = await api.saveConfig(config)
      setMessage(`saved — ${res.status === 'saved' ? 'disarm/arm to apply' : res.status}`)
    } catch (e) {
      setMessage(String(e))
    }
  }

  return (
    <div className="settings">
      <h2>settings</h2>

      {SECTIONS.map(([section, fields]) => (
        <div className="panel" key={section}>
          <h3>{section}</h3>
          {fields.map((field) => (
            <label key={field} className="field">
              {field}
              <input
                type="number"
                step="any"
                value={config[section][field]}
                onChange={(e) => setField(section, field, Number(e.target.value))}
              />
            </label>
          ))}
        </div>
      ))}

      <div className="panel">
        <h3>processing</h3>
        <label className="field">
          auto-process each capture (pose → 3D → metrics → tips)
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
        </label>
      </div>

      <div className="panel">
        <h3>cameras</h3>
        <p className="muted">
          If a camera is physically mounted sideways or upside down, use rotation to correct
          it — this fixes the saved footage itself (not just the preview), since a rotated
          person confuses the pose-tracking model. The preview below shows the currently
          <em> running</em> orientation (arm capture first if it shows "no signal"); after
          changing rotation, save settings and disarm/arm to apply it, then check the preview
          again.
        </p>
        {config.cameras.devices.map((dev: Cfg, i: number) => (
          <div key={i} className="camera-config">
            <strong>{dev.role}</strong>
            {['id', 'width', 'height', 'fps'].map((field) => (
              <label key={field} className="field">
                {field}
                <input
                  type="number"
                  value={dev[field]}
                  onChange={(e) => setCameraField(i, field, Number(e.target.value))}
                />
              </label>
            ))}
            <label className="field">
              rotation
              <select
                value={dev.rotation_deg ?? 0}
                onChange={(e) => setCameraField(i, 'rotation_deg', Number(e.target.value))}
              >
                <option value={0}>0°</option>
                <option value={90}>90° clockwise</option>
                <option value={180}>180°</option>
                <option value={270}>270° clockwise (90° counter-clockwise)</option>
              </select>
            </label>
            <LivePreview camera={dev.role} label={`${dev.role} preview`} />
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>metric reference ranges</h3>
        {Object.entries(config.metrics.reference_ranges as Cfg).map(([metric, range]) => (
          <div key={metric} className="range-row">
            <span>{metric}</span>
            <label className="field">
              min
              <input
                type="number"
                step="any"
                value={(range as Cfg).min}
                onChange={(e) => setRange(metric, 'min', Number(e.target.value))}
              />
            </label>
            <label className="field">
              max
              <input
                type="number"
                step="any"
                value={(range as Cfg).max}
                onChange={(e) => setRange(metric, 'max', Number(e.target.value))}
              />
            </label>
          </div>
        ))}
      </div>

      <button onClick={save}>save settings</button>
      {message && <p className="muted">{message}</p>}
    </div>
  )
}
