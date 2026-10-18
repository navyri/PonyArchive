import type { ReactNode } from 'react'
import type { Source } from '../types'

/** Renderiza el texto de la respuesta con formato básico (**negrita**, *cursiva*, listas). */
export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  const lines = text.split('\n')
  let list: string[] = []
  let key = 0

  const flushList = () => {
    if (list.length === 0) return
    blocks.push(
      <ul key={key++}>
        {list.map((item, i) => (
          <li key={i}>{inline(item)}</li>
        ))}
      </ul>,
    )
    list = []
  }

  for (const raw of lines) {
    const line = raw.trim()
    if (line === '') {
      flushList()
      continue
    }
    if (/^([-*•]|\d+\.)\s+/.test(line)) {
      list.push(line.replace(/^([-*•]|\d+\.)\s+/, ''))
      continue
    }
    flushList()
    blocks.push(<p key={key++}>{inline(line)}</p>)
  }
  flushList()

  return <div className="rich-text">{blocks}</div>
}

/** Negrita **x**, cursiva *x* y `código`. */
function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g).filter(Boolean)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('*') && part.endsWith('*')) return <em key={i}>{part.slice(1, -1)}</em>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>
    return <span key={i}>{part}</span>
  })
}

const TYPE_LABEL: Record<string, string> = {
  episodio: 'Episodio',
  personaje: 'Personaje',
  ficha_narrativa: 'Ficha narrativa',
  upload: 'Documento subido',
  cancion: 'Canción',
}

/** Lista de fuentes recuperadas (estrategia anti-alucinación E5): título, tipo y similitud.
 *  Desplegable y plegada por defecto para no abarcar visualmente la respuesta. */
export function SourceList({ sources }: { sources: Source[] }) {
  if (!sources || sources.length === 0) return null
  return (
    <details className="sources">
      <summary>
        <span className="sources-caret">▸</span> Fuentes ({sources.length})
      </summary>
      <ol>
        {sources.map((s, i) => (
          <li key={i} className="source-item">
            <span className="source-title">{s.title}</span>
            <span className="source-meta">
              {TYPE_LABEL[s.doc_type] ?? s.doc_type}
              {s.source ? ` · ${s.source}` : ''} · similitud {(s.score * 100).toFixed(1)}%
            </span>
            {s.fragment && <blockquote>{s.fragment}</blockquote>}
          </li>
        ))}
      </ol>
    </details>
  )
}
