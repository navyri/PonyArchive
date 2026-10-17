/** Tipos compartidos entre la API (FastAPI) y la interfaz. */

export interface User {
  id: number
  email: string
  display_name: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface Source {
  doc_id: number | null
  title: string
  doc_type: string
  source: string
  source_url: string
  fragment: string
  score: number
}

export interface ChatResponse {
  answer: string
  sources: Source[]
  refused: boolean
  intent: string | null
  theme: string | null
  sufficient: boolean
  retrieval_notes: string[]
  refusal_reason: string | null
  conversation_id: number | null
}

export interface ConversationSummary {
  id: number
  title: string
  updated_at: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  refused: boolean
  created_at?: string
}

export interface ConversationDetail {
  id: number
  title: string
  messages: Message[]
}

export interface DocumentItem {
  id: number
  title: string
  doc_type: string
  source: string
  source_id: string | null
  source_url: string | null
  status: string
  chunk_count: number
  license_note: string | null
  owner: 'personal' | 'biblioteca'
  created_at: string
}

export interface UploadResponse {
  message: string
  document: DocumentItem
  already_indexed: boolean
}

export interface Health {
  status: string
  app: string
  env: string
  model: string
  auth_provider: string
  chunks_indexados: number | null
}
