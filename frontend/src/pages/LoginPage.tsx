import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

/** Login y registro en la misma vista (pestañas). */
export default function LoginPage() {
  const { user, login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') await login(email.trim(), password)
      else await register(email.trim(), password, displayName.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error inesperado')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <form className="card auth-card" onSubmit={onSubmit}>
        <h1>
          <span className="brand-mark">★</span> PonyArchive
        </h1>
        <p className="muted">
          Pregunta por la biblioteca de <em>My Little Pony: Friendship Is Magic</em> y consulta el
          Friendship Journal. Tus conversaciones y documentos son privados.
        </p>

        <div className="tabs">
          <button
            type="button"
            className={mode === 'login' ? 'tab active' : 'tab'}
            onClick={() => setMode('login')}
          >
            Iniciar sesión
          </button>
          <button
            type="button"
            className={mode === 'register' ? 'tab active' : 'tab'}
            onClick={() => setMode('register')}
          >
            Crear cuenta
          </button>
        </div>

        <label className="field">
          Correo electrónico
          <input
            type="email"
            value={email}
            required
            autoComplete="email"
            placeholder="tu@correo.com"
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        {mode === 'register' && (
          <label className="field">
            Nombre visible (opcional)
            <input
              type="text"
              value={displayName}
              maxLength={120}
              placeholder="Cómo quieres que te llame la app"
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </label>
        )}

        <label className="field">
          Contraseña
          <input
            type="password"
            value={password}
            required
            minLength={6}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            placeholder="mínimo 6 caracteres"
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && <p className="error-box">{error}</p>}

        <button className="btn primary block" type="submit" disabled={busy}>
          {busy ? 'Un momento…' : mode === 'login' ? 'Entrar' : 'Crear cuenta'}
        </button>
      </form>
    </div>
  )
}
