/**
 * Empire API Client
 * Unified export for all API modules
 */

// Core client
export { apiRequest, get, post, postFormData, del, getApiBaseUrl, EmpireAPIError } from './client'

// Documents API
export {
  uploadDocuments,
  listDocuments,
  getDocument,
  deleteDocument,
  getDocumentDownloadUrl,
} from './documents'

// Query API (streaming)
export { queryStream, query, collectStreamResponse } from './query'

// WebSocket Chat
export {
  ChatWebSocketClient,
  getChatClient,
  disconnectChatClient,
  type ConnectionState,
  type ChatClientHandlers,
} from './websocket'

// Health check
import { get } from './client'
import type { HealthResponse } from '@/types'

export async function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>('/api/health')
}
