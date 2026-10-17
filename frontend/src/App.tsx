import { useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import './index.css'
import { useAuth } from './auth'
import { api } from './api'
import type { Health } from './types'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import JournalPage from './pages/JournalPage'

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
      <Route path="/journal" element={<JournalPage />} />
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
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">★</span> PonyArchive
          <span className="brand-sub">biblioteca inteligente · MLP: Friendship Is Magic</span>
        </div>

        {user && (
          <nav className="nav">
            <NavLink to="/" end>
              Chat
            </NavLink>
            <NavLink to="/documentos">Documentos</NavLink>
            <NavLink to="/journal">Friendship Journal</NavLink>
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
