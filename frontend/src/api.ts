/** Cliente HTTP de PonyArchive.
 *
 * - Añade el Bearer token a cada petición.
 * - Si el access token caduca (401), intenta UNA vez refrescarlo y reintenta.
 * - Centraliza los mensajes de error en español para la interfaz.
 */
import type { ChatResponse, ConversationDetail, ConversationSummary, DocumentItem, Health, TokenResponse, UploadResponse, User } from './types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://127.0.0.1:8000'

const ACCESS_KEY = 'ponyarchive.access'
const REFRESH_KEY = 'ponyarchive.refresh'

export const tokenStore = {
  get access(): string | null {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  },
  save(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Traduce la respuesta de error del backend a un mensaje legible. */
async function toApiError(res: Response): Promise<ApiError> {
  let detail = `Error HTTP ${res.status}`
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') detail = body.detail
    else if (Array.isArray(body?.detail)) detail = body.detail.map((d: any) => d.msg).join('; ')
  } catch {
    /* sin cuerpo JSON */
  }
  return new ApiError(res.status, detail)
}

async function raw(path: string, init: RequestInit = {}, token?: string | null): Promise<Response> {
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(`${BASE}${path}`, { ...init, headers })
}

/** Refresca el access token. Devuelve null si el refresh también falló. */
async function tryRefresh(): Promise<string | null> {
  const refresh = tokenStore.refresh
  if (!refresh) return null
  try {
    const res = await raw('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) return null
    const data: TokenResponse = await res.json()
    tokenStore.save(data.access_token, data.refresh_token)
    return data.access_token
  } catch {
    return null
  }
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  let res = await raw(path, init, tokenStore.access)
  if (res.status === 401 && retry && tokenStore.refresh) {
    const fresh = await tryRefresh()
    if (fresh) res = await raw(path, init, fresh)
  }
  if (!res.ok) throw await toApiError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const api = {
  base: BASE,

  health: () => request<Health>('/health'),

  // --- autenticación ---
  register: (email: string, password: string, display_name: string) =>
    request<TokenResponse>('/api/auth/register', jsonInit('POST', { email, password, display_name })),
  login: (email: string, password: string) =>
    request<TokenResponse>('/api/auth/login', jsonInit('POST', { email, password })),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }, false),
  me: () => request<User>('/api/auth/me'),

  // --- chat ---
  ask: (question: string, conversation_id: number | null) =>
    request<ChatResponse>('/api/chat', jsonInit('POST', { question, conversation_id })),
  conversations: () => request<ConversationSummary[]>('/api/chat/conversations'),
  conversation: (id: number) => request<ConversationDetail>(`/api/chat/conversations/${id}`),
  deleteConversation: (id: number) => request<void>(`/api/chat/conversations/${id}`, { method: 'DELETE' }),

  // --- documentos ---
  documents: (scope: 'all' | 'mine' | 'shared' = 'all') =>
    request<DocumentItem[]>(`/api/documents?scope=${scope}`),
  upload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    // sin Content-Type manual: el navegador pone el boundary multipart
    return request<UploadResponse>('/api/documents', { method: 'POST', body: form })
  },
  deleteDocument: (id: number) => request<void>(`/api/documents/${id}`, { method: 'DELETE' }),

  // --- friendship journal ---
  themes: () => request<{ themes: string[] }>('/api/journal/themes'),
  journalQuery: (theme: string, question: string | null) =>
    request<{ theme: string; answer: string; sources: ChatResponse['sources']; refused: boolean }>(
      '/api/journal/query',
      jsonInit('POST', { theme, question: question || null }),
    ),
  compare: (item_a: string, item_b: string) =>
    request<{ answer: string; sources: ChatResponse['sources']; refused: boolean }>(
      '/api/journal/compare',
      jsonInit('POST', { item_a, item_b }),
    ),
}
