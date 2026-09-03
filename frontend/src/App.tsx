import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { SessionSummary } from './api'
import ArmControl from './components/ArmControl'
import CalibrationWizard from './components/CalibrationWizard'
import SessionView from './components/SessionView'
import Settings from './components/Settings'
import StatsView from './components/StatsView'
import SystemCheck from './components/SystemCheck'
import './App.css'

type View = 'sessions' | 'stats' | 'settings' | 'calibrate' | 'system-check'

// Sidebar section order: a golfer's own swings first, then the pro reference
// benchmarks, then anything custom, so the layout is stable regardless of
// how the backend happens to iterate the folder.
const GROUP_ORDER = ['My Swings', 'Professional Swings']

function groupSessions(sessions: SessionSummary[]): [string, SessionSummary[]][] {
  const groups = new Map<string, SessionSummary[]>()
  for (const s of sessions) {
    const key = s.group || 'My Swings'
    const bucket = groups.get(key)
    if (bucket) bucket.push(s)
    else groups.set(key, [s])
  }
  return [...groups.keys()]
    .sort((a, b) => {
      const ia = GROUP_ORDER.indexOf(a)
      const ib = GROUP_ORDER.indexOf(b)
      if (ia !== -1 || ib !== -1) return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
      return a.localeCompare(b)
    })
    .map((key) => [key, groups.get(key)!] as [string, SessionSummary[]])
}

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<View>('sessions')
  const [backendUp, setBackendUp] = useState(true)
  const [deletingAll, setDeletingAll] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  const toggleGroup = useCallback((group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(group)) next.delete(group)
      else next.add(group)
      return next
    })
  }, [])

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

  const deleteAllVideos = useCallback(async () => {
    if (
      !window.confirm(
        'Delete the video files from ALL sessions? Stats and metrics are kept, but every raw clip and overlay video is permanently removed.',
      )
    )
      return
    setDeletingAll(true)
    try {
      const res = await api.deleteAllVideos()
      window.alert(
        `Removed ${res.deleted} video file(s) across ${res.sessions_cleared} session(s), freeing ${(
          res.bytes_freed /
          1024 /
          1024
        ).toFixed(1)} MB.`,
      )
      refresh()
    } finally {
      setDeletingAll(false)
    }
  }, [refresh])

  return (
    <div className="app">
      <header>
        <h1>golf swing analyzer</h1>
        <ArmControl onCapture={refresh} />
        <nav className="view-nav">
          <button className={view === 'sessions' ? 'active' : ''} onClick={() => setView('sessions')}>
            sessions
          </button>
          <button className={view === 'stats' ? 'active' : ''} onClick={() => setView('stats')}>
            stats
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
      {view === 'stats' && <StatsView />}
      {view === 'calibrate' && <CalibrationWizard />}
      {view === 'system-check' && <SystemCheck />}
      {view === 'sessions' && (
        <div className="main">
          <aside>
            <h3>sessions</h3>
            {sessions.length === 0 && <p className="muted">no swings captured yet</p>}
            {groupSessions(sessions).map(([group, groupSessionsList]) => {
              const collapsed = collapsedGroups.has(group)
              return (
                <section key={group} className="session-group">
                  <button
                    type="button"
                    className="session-group-title"
                    aria-expanded={!collapsed}
                    onClick={() => toggleGroup(group)}
                  >
                    <span className={`group-caret${collapsed ? ' collapsed' : ''}`} aria-hidden>
                      ▾
                    </span>
                    {group}
                    <span className="group-count">{groupSessionsList.length}</span>
                  </button>
                  {!collapsed && (
                    <ul>
                      {groupSessionsList.map((s) => {
                        const dt = s.created_at ? new Date(s.created_at) : null
                        return (
                          <li key={s.id}>
                            <button
                              className={s.id === selected ? 'active' : ''}
                              onClick={() => setSelected(s.id)}
                            >
                              {s.label ? (
                                <span className="session-label">{s.label}</span>
                              ) : dt ? (
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
                  )}
                </section>
              )
            })}
            {sessions.length > 0 && (
              <button
                type="button"
                className="delete-videos delete-all-videos"
                onClick={deleteAllVideos}
                disabled={deletingAll}
              >
                {deletingAll ? 'deleting…' : 'delete all videos (keep stats)'}
              </button>
            )}
          </aside>
          <main>
            {selected ? (
              <SessionView sessionId={selected} onChanged={refresh} />
            ) : (
              <p className="muted">arm the mic and hit a shot, or use manual capture.</p>
            )}
          </main>
        </div>
      )}
    </div>
  )
}
