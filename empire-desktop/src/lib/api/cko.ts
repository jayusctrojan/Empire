/**
 * CKO (Chief Knowledge Officer) API Client
 * AI Studio conversation management with multi-model pipeline
 */

import { get, post, del, getApiBaseUrl } from './client'
import { useAuthStore } from '@/stores/auth'
import { useOrgStore } from '@/stores/org'
import { fetch } from '@tauri-apps/plugin-http'

// ============================================================================
// Types
// ============================================================================

export interface CKOSession {
  id: string
  userId: string
  title: string | null
  messageCount: number
  pendingClarifications: number
  contextSummary: string | null
  projectId: string | null
  createdAt: string
  updatedAt: string
  lastMessageAt: string | null
  /** @deprecated Use camelCase `messageCount` instead. Kept for backend snake_case compat. */
  message_count?: number
  /** @deprecated Use camelCase `contextSummary` instead. */
  context_summary?: string | null
  /** @deprecated Use camelCase `lastMessageAt` instead. */
  last_message_at?: string | null
  /** @deprecated Use camelCase `createdAt` instead. */
  created_at?: string
}

export interface CKOSource {
  docId: string
  title: string
  snippet: string
  relevanceScore: number
  pageNumber?: number
  department?: string
  documentType?: string
  chunkIndex?: number
}

export interface CKOAction {
  type: string
  description: string
  metadata?: Record<string, unknown>
}

export interface CKOMessage {
  id: string
  sessionId: string
  role: 'user' | 'cko'
  content: string
  sources: CKOSource[]
  actionsPerformed: CKOAction[]
  isClarification: boolean
  clarificationType?: string
  clarificationStatus?: string
  clarificationAnswer?: string
  rating?: number
  ratingFeedback?: string
  createdAt: string
}

export interface CKOStreamChunk {
  type: 'start' | 'phase' | 'sources' | 'token' | 'artifact' | 'done' | 'error'
  session_id?: string
  phase?: 'analyzing' | 'searching' | 'reasoning' | 'formatting'
  label?: string
  sources?: CKOSource[]
  content?: string
  message?: CKOMessage
  query_time_ms?: number
  pipeline_mode?: string
  error?: string
  // Artifact fields
  id?: string
  title?: string
  format?: string
  mimeType?: string
  sizeBytes?: number
  previewMarkdown?: string
  status?: string
}

export interface CKOConfig {
  enableQueryExpansion?: boolean
  numQueryVariations?: number
  expansionStrategy?: string
  globalKbLimit?: number
}

export interface CKOMessageRequest {
  message: string
  enable_query_expansion?: boolean
  num_query_variations?: number
  expansion_strategy?: string
  global_kb_limit?: number
}

export interface CKOSessionCreate {
  title?: string
  projectId?: string
}

// ============================================================================
// Session API
// ============================================================================

export async function createCKOSession(data?: CKOSessionCreate): Promise<CKOSession> {
  const body: Record<string, unknown> = {}
  if (data?.title) body.title = data.title
  if (data?.projectId) body.project_id = data.projectId
  return post<CKOSession>('/api/studio/cko/sessions', body)
}

export async function getCKOSession(sessionId: string): Promise<CKOSession> {
  return get<CKOSession>(`/api/studio/cko/sessions/${sessionId}`)
}

export async function listCKOSessions(options?: { limit?: number }): Promise<CKOSession[]> {
  const params: Record<string, string> = {}
  if (options?.limit) params.limit = String(options.limit)
  return get<CKOSession[]>('/api/studio/cko/sessions', params)
}

export async function deleteCKOSession(sessionId: string): Promise<void> {
  return del<void>(`/api/studio/cko/sessions/${sessionId}`)
}

export async function updateCKOSession(sessionId: string, title: string): Promise<CKOSession> {
  return post<CKOSession>(`/api/studio/cko/sessions/${sessionId}`, { title })
}

// ============================================================================
// Message API
// ============================================================================

export async function getCKOMessages(sessionId: string): Promise<CKOMessage[]> {
  return get<CKOMessage[]>(`/api/studio/cko/sessions/${sessionId}/messages`)
}

export async function sendCKOMessage(
  sessionId: string,
  request: CKOMessageRequest
): Promise<CKOMessage> {
  const response = await post<{ message: CKOMessage }>(
    `/api/studio/cko/sessions/${sessionId}/messages`,
    request
  )
  return response.message
}

/**
 * Stream a CKO message using SSE (Server-Sent Events).
 * Yields CKOStreamChunk events including phase indicators and artifact events.
 */
export async function* streamCKOMessage(
  sessionId: string,
  request: CKOMessageRequest,
  signal?: AbortSignal,
): AsyncGenerator<CKOStreamChunk> {
  const baseUrl = getApiBaseUrl()
  const url = `${baseUrl}/api/studio/cko/sessions/${sessionId}/messages/stream`

  const token = useAuthStore.getState().jwt
  const currentOrg = useOrgStore.getState().currentOrg

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (currentOrg) headers['X-Org-Id'] = currentOrg.id

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new Error(`CKO stream failed: ${response.status} ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let eventData = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done || signal?.aborted) break

      buffer += decoder.decode(value, { stream: true })

      // Parse SSE events
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          // Event type line — currently unused but parsed for completeness
        } else if (line.startsWith('data: ')) {
          eventData += line.slice(6)
        } else if (line === '' && eventData) {
          // End of event
          try {
            const chunk = JSON.parse(eventData) as CKOStreamChunk
            yield chunk
          } catch {
            // Ignore malformed JSON
          }
          eventData = ''
        }
      }
    }
  } finally {
    reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

// ============================================================================
// Rating & Clarification API
// ============================================================================

export async function rateCKOMessage(
  messageId: string,
  rating: -1 | 0 | 1,
  feedback?: string
): Promise<void> {
  await post(`/api/studio/cko/messages/${messageId}/rate`, { rating, feedback })
}

export async function answerCKOClarification(
  messageId: string,
  answer: string
): Promise<CKOMessage> {
  const response = await post<{ message: CKOMessage }>(
    `/api/studio/cko/messages/${messageId}/clarify`,
    { answer }
  )
  return response.message
}

export async function skipCKOClarification(messageId: string): Promise<void> {
  await post(`/api/studio/cko/messages/${messageId}/skip`)
}

export async function getPendingClarificationsCount(): Promise<{ count: number; hasOverdue: boolean }> {
  return get<{ count: number; hasOverdue: boolean }>('/api/studio/cko/clarifications/count')
}
