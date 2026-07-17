import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { SessionSummary } from './api'
import ArmControl from './components/ArmControl'
import SessionView from './components/SessionView'
import Settings from './components/Settings'
import './App.css'

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [showSettings, setShowSettings] = useState(false)
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
        <button className="settings-btn" onClick={() => setShowSettings((s) => !s)}>
          {showSettings ? 'sessions' : 'settings'}
        </button>
      </header>

      {!backendUp && (
        <div className="error banner">
          backend not reachable — start it with: python -m golf_sim.api.server
        </div>
      )}

      {showSettings ? (
        <Settings />
      ) : (
        <div className="main">
          <aside>
            <h3>sessions</h3>
            {sessions.length === 0 && <p className="muted">no swings captured yet</p>}
            <ul>
              {sessions.map((s) => (
                <li key={s.id}>
                  <button
                    className={s.id === selected ? 'active' : ''}
                    onClick={() => setSelected(s.id)}
                  >
                    <span className="session-id">{s.id}</span>
                    <span className="badges">
                      {s.has_3d && <em>3D</em>}
                      {s.has_metrics && <em>metrics</em>}
                    </span>
                  </button>
                </li>
              ))}
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
