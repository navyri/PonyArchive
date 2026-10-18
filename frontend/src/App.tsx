import { useEffect, useState, type CSSProperties } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import './index.css'
import { useAuth } from './auth'
import { api } from './api'
import type { Health } from './types'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'

function Loading() {
  return <div className="center-screen">Cargando PonyArchive…</div>
}

/** Rutas protegidas: sin sesión se redirige a /login. */
function ProtectedRoutes() {
  const { ready, user } = useAuth()
  if (!ready) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return (
    <Routes>
      <Route path="/" element={<ChatPage />} />
      <Route path="/documentos" element={<DocumentsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

/** /login: si ya hay sesión, vuelve al chat. */
function LoginRoute() {
  const { ready, user } = useAuth()
  if (!ready) return <Loading />
  if (user) return <Navigate to="/" replace />
  return <LoginPage />
}

/** Destellos decorativos de fondo (solo estética, sin contenido). */
const SPARKLES: Array<{ x: string; y: string; s: number; d: number; delay: number; star: boolean }> = [
  { x: '6%', y: '14%', s: 12, d: 7, delay: 0, star: true },
  { x: '18%', y: '62%', s: 8, d: 9, delay: 1.2, star: false },
  { x: '27%', y: '30%', s: 14, d: 8.5, delay: 2.4, star: true },
  { x: '38%', y: '78%', s: 9, d: 7.5, delay: 0.6, star: false },
  { x: '47%', y: '18%', s: 10, d: 10, delay: 3.1, star: false },
  { x: '58%', y: '55%', s: 15, d: 8, delay: 1.7, star: true },
  { x: '66%', y: '26%', s: 7, d: 9.5, delay: 4.2, star: false },
  { x: '74%', y: '70%', s: 11, d: 7.2, delay: 2.2, star: true },
  { x: '83%', y: '38%', s: 9, d: 8.8, delay: 0.9, star: false },
  { x: '91%', y: '12%', s: 13, d: 9.8, delay: 3.6, star: true },
  { x: '12%', y: '88%', s: 10, d: 8.2, delay: 2.9, star: false },
  { x: '33%', y: '6%', s: 7, d: 10.5, delay: 1.4, star: false },
  { x: '52%', y: '92%', s: 12, d: 7.8, delay: 4.8, star: true },
  { x: '70%', y: '4%', s: 8, d: 9.2, delay: 0.3, star: false },
  { x: '88%', y: '58%', s: 14, d: 8.6, delay: 2.7, star: true },
  { x: '22%', y: '46%', s: 6, d: 11, delay: 3.9, star: false },
  { x: '44%', y: '44%', s: 7, d: 9.4, delay: 5.2, star: false },
  { x: '96%', y: '82%', s: 10, d: 8.4, delay: 1.1, star: false },
]

export default function App() {
  const { user, logout } = useAuth()
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      api
        .health()
        .then((h) => {
          if (alive) setHealth(h)
        })
        .catch(() => {
          if (alive) setHealth(null)
        })
    load()
    const id = setInterval(load, 30_000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  return (
    <div className="app">
      <div className="cosmos" aria-hidden="true">
        {SPARKLES.map((sp, i) => (
          <i
            key={i}
            className={sp.star ? 'star' : undefined}
            style={
              {
                '--x': sp.x,
                '--y': sp.y,
                '--s': `${sp.s}px`,
                '--d': `${sp.d}s`,
                '--delay': `${sp.delay}s`,
              } as CSSProperties
            }
          />
        ))}
      </div>

      <header className="topbar">
        <div className="titlebar">
          <div className="dots"><i className="a" /><i className="m" /><i className="o" /></div>
          <span className="title">PONYARCHIVE.EXE</span>
          <span className="path">/biblioteca / documentos</span>
        </div>
        <div className="topbar-row">
          <div className="brand">
            <span className="brand-mark">✦</span> PonyArchive
            <span className="brand-sub">biblioteca inteligente · MLP: Friendship Is Magic</span>
          </div>

          {user && (
            <nav className="nav">
              <NavLink to="/" end>
                Chat
              </NavLink>
              <NavLink to="/documentos">Documentos</NavLink>
            </nav>
          )}

          <div className="topbar-right">
            {health && (
              <span
                className={`pill ${health.status === 'ok' ? 'ok' : 'bad'}`}
                title={`Modelo: ${health.model} · Auth: ${health.auth_provider} · Fragmentos: ${health.chunks_indexados}`}
              >
                {health.status === 'ok' ? 'API OK' : 'API caída'} · {health.chunks_indexados ?? '—'} frag.
              </span>
            )}
            {user && (
              <>
                <span className="user-email" title={user.email}>
                  {user.display_name}
                </span>
                <button className="btn ghost" onClick={() => void logout()}>
                  Salir
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/*" element={<ProtectedRoutes />} />
        </Routes>
      </main>
    </div>
  )
}
