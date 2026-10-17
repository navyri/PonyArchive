import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { RichText, SourceList } from '../components/Answer'
import type { Source } from '../types'

interface Result {
  answer: string
  sources: Source[]
  refused: boolean
}

/** Friendship Journal: consultas temáticas y comparaciones sobre la biblioteca. */
export default function JournalPage() {
  const [themes, setThemes] = useState<string[]>([])
  const [theme, setTheme] = useState('')
  const [question, setQuestion] = useState('')
  const [itemA, setItemA] = useState('')
  const [itemB, setItemB] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState<'' | 'theme' | 'compare'>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .themes()
      .then((r) => setThemes(r.themes))
      .catch((err) => setError(err instanceof Error ? err.message : 'No se pudieron cargar los temas.'))
  }, [])

  async function onTheme(e: FormEvent) {
    e.preventDefault()
    if (!theme || busy) return
    setBusy('theme')
    setError(null)
    setResult(null)
    try {
      const r = await api.journalQuery(theme, question.trim() || null)
      setResult({ answer: r.answer, sources: r.sources, refused: r.refused })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error en la consulta temática.')
    } finally {
      setBusy('')
    }
  }

  async function onCompare(e: FormEvent) {
    e.preventDefault()
    if (!itemA.trim() || !itemB.trim() || busy) return
    setBusy('compare')
    setError(null)
    setResult(null)
    try {
      const r = await api.compare(itemA.trim(), itemB.trim())
      setResult({ answer: r.answer, sources: r.sources, refused: r.refused })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error en la comparación.')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="page">
      <h1>Friendship Journal</h1>
      <p className="muted">
        Diario temático de la biblioteca: consulta qué documentos tratan un tema (lealtad, amistad,
        honestidad…) o compara dos elementos según la documentación indexada. Responde con el mismo
        agente RAG y sus mismas garantías.
      </p>

      <div className="grid-2">
        <form className="card" onSubmit={onTheme}>
          <h3>Consulta temática</h3>
          <label className="field">
            Tema
            <select value={theme} onChange={(e) => setTheme(e.target.value)} required>
              <option value="">— elige un tema —</option>
              {themes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Pregunta (opcional)
            <input
              type="text"
              value={question}
              maxLength={1000}
              placeholder="Si la dejas vacía, se usa una genérica del tema"
              onChange={(e) => setQuestion(e.target.value)}
            />
          </label>
          <button className="btn primary" type="submit" disabled={busy !== '' || !theme}>
            {busy === 'theme' ? 'Consultando…' : 'Consultar tema'}
          </button>
        </form>

        <form className="card" onSubmit={onCompare}>
          <h3>Comparar elementos</h3>
          <label className="field">
            Elemento A
            <input
              type="text"
              value={itemA}
              maxLength={120}
              required
              placeholder="Ej.: Twilight Sparkle"
              onChange={(e) => setItemA(e.target.value)}
            />
          </label>
          <label className="field">
            Elemento B
            <input
              type="text"
              value={itemB}
              maxLength={120}
              required
              placeholder="Ej.: Rainbow Dash"
              onChange={(e) => setItemB(e.target.value)}
            />
          </label>
          <button className="btn primary" type="submit" disabled={busy !== ''}>
            {busy === 'compare' ? 'Comparando…' : 'Comparar'}
          </button>
        </form>
      </div>

      {error && <p className="error-box">{error}</p>}

      {result && (
        <div className={`card result${result.refused ? ' refused' : ''}`}>
          {result.refused && <div className="refusal-tag">Sin evidencia suficiente</div>}
          <RichText text={result.answer} />
          <SourceList sources={result.sources} />
        </div>
      )}
    </div>
  )
}
