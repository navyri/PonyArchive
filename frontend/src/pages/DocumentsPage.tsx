import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { DocumentItem } from '../types'
const TYPE_LABEL: Record<string, string> = {
  episodio: 'Episodio',
  personaje: 'Personaje',
  ficha_narrativa: 'Ficha narrativa',
  upload: 'Subido',
  cancion: 'Canción',
}

/** Carga y listado de documentos (requisito §2.4: extracción → fragmentación → embeddings). */
export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [total, setTotal] = useState(0)
  const [scope, setScope] = useState<'all' | 'mine' | 'shared'>('all')
  const [filter, setFilter] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    api
      .documents(scope)
      .then((page) => {
        setDocs(page.items)
        setTotal(page.total)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'No se pudo cargar la lista.'))
  }, [scope])

  useEffect(load, [load])

  async function onUpload(file: File) {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const res = await api.upload(file)
      setMessage(res.message + (res.already_indexed ? ' (ya estaba indexado)' : ''))
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo subir el archivo.')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function onDelete(doc: DocumentItem) {
    if (!confirm(`¿Borrar "${doc.title}"? Se eliminará también de la base vectorial.`)) return
    setError(null)
    try {
      await api.deleteDocument(doc.id)
      setMessage(`Documento "${doc.title}" eliminado.`)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo borrar el documento.')
    }
  }

  const visible = docs.filter((d) => d.title.toLowerCase().includes(filter.trim().toLowerCase()))
  const personal = docs.filter((d) => d.owner === 'personal').length

  return (
    <div className="page">
      <h1>Documentos</h1>
      <p className="muted">
        La biblioteca compartida (personajes, episodios y fichas) procede de Pony API, de la
        wiki de Fandom (mlp.fandom.com, sinopsis bajo licencia CC BY-SA) y de la redacción
        propia del equipo. Tus cargas son privadas: solo tú puedes consultarlas y borrarlas.
      </p>

      <div className="card">
        <h3>Cargar documento (.txt o .md, máx. 20 MB)</h3>
        <div className="upload-row">
          <label className="file-upload">
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.md,text/plain,text/markdown"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void onUpload(f)
              }}
            />
            <span className="file-upload-label">▸ Elegir archivo</span>
          </label>
          {busy && <span className="muted">Indexando (extracción → fragmentación → embeddings)</span>}
        </div>
        <p className="muted small">
          Una vez indexado, puedes preguntar por su contenido en el chat.
        </p>
        {message && <p className="ok-box">{message}</p>}
        {error && <p className="error-box">{error}</p>}
      </div>

      <div className="card">
        <div className="toolbar">
          <div className="tabs">
            {(['all', 'shared', 'mine'] as const).map((s) => (
              <button
                key={s}
                className={scope === s ? 'tab active' : 'tab'}
                onClick={() => setScope(s)}
              >
                {s === 'all' ? 'Todos' : s === 'shared' ? 'Biblioteca' : `Mis documentos (${personal})`}
              </button>
            ))}
          </div>
          <input
            className="search"
            placeholder="Filtrar por título…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>

        <p className="muted small">
          Mostrando {visible.length} de {total} documentos indexados.
        </p>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Título</th>
                <th>Tipo</th>
                <th>Origen</th>
                <th>Fragmentos</th>
                <th>Propietario</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((d) => (
                <tr key={d.id}>
                  <td title={d.license_note ?? ''}>
                    {d.source_url ? (
                      <a href={d.source_url} target="_blank" rel="noreferrer">
                        {d.title}
                      </a>
                    ) : (
                      d.title
                    )}
                  </td>
                  <td>
                    <span className="pill">{TYPE_LABEL[d.doc_type] ?? d.doc_type}</span>
                  </td>
                  <td className="muted">{d.source}</td>
                  <td>{d.chunk_count}</td>
                  <td>{d.owner === 'personal' ? 'Tuyo' : 'Biblioteca'}</td>
                  <td>
                    {d.owner === 'personal' && (
                      <button className="btn danger small" onClick={() => void onDelete(d)}>
                        Borrar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    Sin documentos que coincidan.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
