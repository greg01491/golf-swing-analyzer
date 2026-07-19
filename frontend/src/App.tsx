import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { SessionSummary } from './api'
import ArmControl from './components/ArmControl'
import CalibrationWizard from './components/CalibrationWizard'
import SessionView from './components/SessionView'
import Settings from './components/Settings'
import SystemCheck from './components/SystemCheck'
import './App.css'

type View = 'sessions' | 'settings' | 'calibrate' | 'system-check'

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<View>('sessions')
  const [backendUp, setBackendUp] = useState(true)

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

  return (
    <div className="app">
      <header>
        <h1>golf swing analyzer</h1>
        <ArmControl onCapture={refresh} />
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
          backend not reachable — start it with: python -m golf_sim.api.server
        </div>
      )}

      {view === 'settings' && <Settings />}
      {view === 'calibrate' && <CalibrationWizard />}
      {view === 'system-check' && <SystemCheck />}
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
              <SessionView sessionId={selected} />
            ) : (
              <p className="muted">arm the mic and hit a shot, or use manual capture.</p>
            )}
          </main>
        </div>
      )}
    </div>
  )
}
