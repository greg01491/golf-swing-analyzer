import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { SessionDetail, SessionSummary, StartupStatus } from './api'
import ArmControl from './components/ArmControl'
import CalibrationWizard from './components/CalibrationWizard'
import SessionView from './components/SessionView'
import Settings from './components/Settings'
import SystemCheck from './components/SystemCheck'
import './App.css'

type View = 'sessions' | 'settings' | 'calibrate' | 'system-check'
type Theme = 'dark' | 'light'

const humanizeMetric = (metric: string) => metric.replace(/_(deg|pct)$/, '').replaceAll('_', ' ')

function spokenFeedback(detail: SessionDetail, focusedMetric: string | null): string {
  const analysis = detail.metrics
  if (!analysis) return ''

  if (focusedMetric) {
    const label = humanizeMetric(focusedMetric)
    const tip = analysis.tips.find((item) => item.metric === focusedMetric)
    if (tip) return `Your ${label} needs attention. ${tip.text}`

    const metric = analysis.metrics.find((item) => item.name === focusedMetric)
    if (!metric || metric.value === null) {
      return `I could not measure your ${label} reliably on this swing.`
    }
    const result =
      metric.in_range === true
        ? 'is in your target range'
        : metric.in_range === false
          ? 'is outside your target range'
          : 'has been recorded'
    return `Your ${label} was ${metric.value} ${metric.unit}, and ${result}. Keep working on consistent ${label}.`
  }

  if (analysis.tips.length > 0) {
    const tip = analysis.tips[0]
    return `The main issue is ${humanizeMetric(tip.metric)}. ${tip.text}`
  }
  return 'Nice swing. Everything measured was in range.'
}

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<View>('sessions')
  const [backendUp, setBackendUp] = useState(true)
  const [startup, setStartup] = useState<StartupStatus | null>(null)
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem('theme') as Theme | null) ?? 'dark',
  )
  const [voiceEnabled, setVoiceEnabled] = useState(
    () => localStorage.getItem('voice-feedback') !== 'off',
  )
  const [focusedMetric, setFocusedMetric] = useState<string | null>(
    () => localStorage.getItem('voice-metric-focus'),
  )
  const voiceEnabledRef = useRef(voiceEnabled)
  const focusedMetricRef = useRef(focusedMetric)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    voiceEnabledRef.current = voiceEnabled
    localStorage.setItem('voice-feedback', voiceEnabled ? 'on' : 'off')
    if (!voiceEnabled) window.speechSynthesis.cancel()
  }, [voiceEnabled])

  useEffect(() => {
    focusedMetricRef.current = focusedMetric
    if (focusedMetric) localStorage.setItem('voice-metric-focus', focusedMetric)
    else localStorage.removeItem('voice-metric-focus')
  }, [focusedMetric])

  const refresh = useCallback(() => {
    api
      .sessions()
      .then((list) => {
        setBackendUp(true)
        setSessions(list)
        setSelected((cur) => cur ?? list[0]?.id ?? null)
      })
      .catch(() => setBackendUp(false))
  }, [])

  useEffect(refresh, [refresh])

  useEffect(() => {
    const update = () => {
      api
        .startup()
        .then((status) => {
          setBackendUp(true)
          setStartup(status)
        })
        .catch(() => {
          setBackendUp(false)
          setStartup(null)
        })
    }
    update()
    const interval = setInterval(update, 5000)
    return () => clearInterval(interval)
  }, [])

  const speak = useCallback((text: string) => {
    if (!text || !voiceEnabledRef.current) return
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text))
  }, [])

  const announceWhenReady = useCallback(
    async (sessionId: string) => {
      for (let attempt = 0; attempt < 300; attempt += 1) {
        try {
          const detail = await api.session(sessionId)
          if (detail.metrics) {
            speak(spokenFeedback(detail, focusedMetricRef.current))
            return
          }
        } catch {
          // A newly captured session can briefly appear before its metadata is readable.
        }
        await new Promise((resolve) => setTimeout(resolve, 2000))
      }
    },
    [speak],
  )

  const handleCapture = useCallback(
    (sessionId: string) => {
      refresh()
      setSelected(sessionId)
      void announceWhenReady(sessionId)
    },
    [announceWhenReady, refresh],
  )

  const focusMetric = useCallback(
    (metric: string | null) => {
      setFocusedMetric(metric)
      speak(metric ? `Voice feedback focused on ${humanizeMetric(metric)}.` : 'Voice feedback will cover the main issue.')
    },
    [speak],
  )

  return (
    <div className="app">
      <header>
        <h1>golf swing analyzer</h1>
        <ArmControl captureReady={startup?.ready ?? false} onCapture={handleCapture} />
        <label className="voice-toggle">
          <input
            type="checkbox"
            checked={voiceEnabled}
            onChange={(event) => setVoiceEnabled(event.target.checked)}
          />
          voice feedback
        </label>
        <button
          className="theme-toggle"
          onClick={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
        >
          {theme === 'dark' ? 'light mode' : 'dark mode'}
        </button>
        <nav className="view-nav">
          <button className={view === 'sessions' ? 'active' : ''} onClick={() => setView('sessions')}>
            sessions
          </button>
          <button className={view === 'calibrate' ? 'active' : ''} onClick={() => setView('calibrate')}>
            calibrate
          </button>
          <button
            className={view === 'system-check' ? 'active' : ''}
            onClick={() => setView('system-check')}
          >
            system check
          </button>
          <button className={view === 'settings' ? 'active' : ''} onClick={() => setView('settings')}>
            settings
          </button>
        </nav>
      </header>

      {!backendUp && (
        <div className="error banner">
          The analysis service is unavailable. Restart the desktop app; startup logs are saved in
          the app data folder.
        </div>
      )}
      {backendUp && startup && !startup.ready && (
        <div className="setup-banner">
          <strong>Complete setup before capturing a swing.</strong>
          <span>{startup.messages.join(' ')}</span>
          <button
            onClick={() =>
              setView(
                !startup.calibration_ready
                  ? 'calibrate'
                  : !startup.audio_ready
                    ? 'settings'
                    : 'system-check',
              )
            }
          >
            {!startup.calibration_ready ? 'open calibration' : 'review setup'}
          </button>
        </div>
      )}

      {view === 'settings' && (
        <div className="view-scroll">
          <Settings />
        </div>
      )}
      {view === 'calibrate' && (
        <div className="view-scroll">
          <CalibrationWizard />
        </div>
      )}
      {view === 'system-check' && (
        <div className="view-scroll">
          <SystemCheck />
        </div>
      )}
      {view === 'sessions' && (
        <div className="main">
          <aside>
            <h3>sessions</h3>
            {sessions.length === 0 && <p className="muted">no swings captured yet</p>}
            <ul>
              {sessions.map((s) => {
                const dt = s.created_at ? new Date(s.created_at) : null
                return (
                  <li key={s.id}>
                    <button
                      className={s.id === selected ? 'active' : ''}
                      onClick={() => setSelected(s.id)}
                    >
                      {dt ? (
                        <span className="session-when">
                          <span className="session-time">
                            {dt.toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </span>
                          <span className="session-date">
                            {dt.toLocaleDateString([], {
                              weekday: 'short',
                              day: 'numeric',
                              month: 'short',
                            })}
                          </span>
                        </span>
                      ) : (
                        <span className="session-id">{s.id}</span>
                      )}
                      <span className="badges">
                        {s.has_3d && <em>3D</em>}
                        {s.has_metrics && <em>metrics</em>}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </aside>
          <main>
            {selected ? (
              <SessionView
                sessionId={selected}
                focusedMetric={focusedMetric}
                onFocusMetric={focusMetric}
              />
            ) : (
              <p className="muted">arm the mic and hit a shot, or use manual capture.</p>
            )}
          </main>
        </div>
      )}
    </div>
  )
}
