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
  const [showPassword, setShowPassword] = useState(false)

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
        <div className="auth-titlebar">
          <div className="dots"><i className="a" /><i className="m" /><i className="o" /></div>
          <span className="t">PONYARCHIVE.EXE</span>
          <span className="p">/acceso</span>
        </div>
        <div className="auth-body">
          <h1>PONYARCHIVE</h1>
          <p className="muted small">
            Biblioteca inteligente de My Little Pony: Friendship Is Magic. Tus conversaciones y documentos son privados.
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

          <div className="field">
            <label htmlFor="auth-password">Contraseña</label>
            <div className="field-input">
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                required
                minLength={6}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                placeholder="mínimo 6 caracteres"
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="pw-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                aria-pressed={showPassword}
                title={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              >
                {showPassword ? (
                  <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                    <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {error && <p className="error-box">{error}</p>}

          <button className="btn primary block" type="submit" disabled={busy}>
            {busy ? 'Un momento…' : mode === 'login' ? 'Entrar' : 'Crear cuenta'}
          </button>
        </div>
      </form>
    </div>
  )
}
