import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { api, ApiError } from '../api'
import { RichText, SourceList } from '../components/Answer'
import type { ConversationSummary, Message } from '../types'

const SUGGESTIONS = [
  '¿Quién es Twilight Sparkle?',
  '¿De qué trata el episodio Bridle Gossip?',
  '¿Qué episodios hablan de la amistad?',
  '¿Cuántos episodios y personajes documenta la biblioteca?',
  '¿Qué astronauta lleva el cohete?',
]

/** Chat con el agente RAG: preguntas, respuesta con fuentes e historial. */
export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [pendingKeys, setPendingKeys] = useState<(number | 'new')[]>([])
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  // Conversación visible y las que tienen consulta en vuelo (para no mezclar hilos)
  const viewKey = conversationId ?? 'new'
  const busyHere = pendingKeys.includes(viewKey)
  const viewRef = useRef(viewKey)
  viewRef.current = viewKey

  const refreshConversations = useCallback(() => {
    api
      .conversations()
      .then(setConversations)
      .catch(() => setConversations([]))
  }, [])

  useEffect(refreshConversations, [refreshConversations])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busyHere])

  async function send(question: string) {
    const text = question.trim()
    if (!text || busyHere) return
    const target = viewKey
    setError(null)
    setPendingKeys((prev) => [...prev, target])
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text, sources: [], refused: false }])
    try {
      const res = await api.ask(text, conversationId)
      // La respuesta solo se cuelga si la vista sigue siendo la conversación de origen
      if (viewRef.current === target) {
        setConversationId(res.conversation_id ?? conversationId)
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.answer,
            sources: res.sources,
            refused: res.refused,
          },
        ])
        setError(null)
      }
      refreshConversations()
    } catch (err) {
      const msg =
        err instanceof ApiError && err.status === 401
          ? 'Tu sesión ha caducado. Salga y vuelva a entrar.'
          : err instanceof Error
            ? err.message
            : 'No se pudo enviar la pregunta.'
      if (viewRef.current === target) {
        setError(msg)
        // retira el mensaje de usuario para reintentar sin duplicar
        setMessages((prev) => prev.slice(0, -1))
        setInput(text)
      }
    } finally {
      setPendingKeys((prev) => prev.filter((k) => k !== target))
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send(input)
    }
  }

  async function openConversation(id: number) {
    setError(null)
    try {
      const detail = await api.conversation(id)
      setConversationId(detail.id)
      setMessages(detail.messages)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo abrir la conversación.')
    }
  }

  async function removeConversation(id: number) {
    try {
      await api.deleteConversation(id)
      if (id === conversationId) newChat()
      refreshConversations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo borrar.')
    }
  }

  function newChat() {
    setMessages([])
    setConversationId(null)
    setError(null)
  }

  return (
    <div className="chat-layout">
      <aside className="side">
        <button className="btn primary block" onClick={newChat}>
          + Nueva conversación
        </button>
        <h3 className="side-title">Historial</h3>
        {conversations.length === 0 && <p className="muted small">Aún no hay conversaciones.</p>}
        <ul className="conv-list">
          {conversations.map((c) => (
            <li key={c.id} className={c.id === conversationId ? 'active' : ''}>
              <button className="conv-item" onClick={() => void openConversation(c.id)} title={c.title}>
                {c.title}
              </button>
              <button
                className="conv-del"
                title="Borrar conversación"
                onClick={() => void removeConversation(c.id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <p className="muted small side-note">
          Cada usuario solo ve sus propias conversaciones y documentos.
        </p>
      </aside>

      <section className="chat-main">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <h2>Pregunta sobre la biblioteca</h2>
              <p className="muted">
                El agente responde únicamente con los documentos indexados. Si no hay información
                suficiente, lo dice explícitamente.
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="chip" onClick={() => void send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} className="msg user">
                <div className="bubble">{m.content}</div>
              </div>
            ) : (
              <div key={i} className={`msg assistant${m.refused ? ' refused' : ''}`}>
                <div className="bubble">
                  {m.refused && <div className="refusal-tag">Sin evidencia suficiente</div>}
                  <RichText text={m.content} />
                  <SourceList sources={m.sources} />
                </div>
              </div>
            ),
          )}

          {busyHere && (
            <div className="msg assistant">
              <div className="bubble loading">
                <span className="shimmer">Consultando la base de conocimiento</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && <p className="error-box">{error}</p>}

        <form className="composer" onSubmit={onSubmit}>
          <textarea
            value={input}
            rows={2}
            maxLength={2000}
            placeholder="Escribe tu pregunta (Enter para enviar, Shift+Enter para nueva línea)"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={busyHere}
          />
          <button className="btn primary" type="submit" disabled={busyHere || !input.trim()}>
            {busyHere ? '…' : 'Enviar'}
          </button>
        </form>
      </section>
    </div>
  )
}
