/**
 * Empire Backend API Types
 * Types for Empire v7.3 REST and WebSocket APIs
 */

// ============ Query API Types ============

/**
 * Request for auto-routed query endpoint
 */
export interface QueryRequest {
  query: string
  projectId?: string
  maxIterations?: number
  includeSourceCitations?: boolean
}

/**
 * Streaming chunk from query response
 */
export interface StreamChunk {
  type: 'token' | 'source' | 'workflow' | 'done' | 'error' | 'phase' | 'artifact'
  content?: string
  source?: SourceCitation
  workflow?: string
  error?: string
  phase?: 'analyzing' | 'searching' | 'reasoning' | 'formatting'
  label?: string
  pipeline_mode?: 'full' | 'no_prompt_engineer' | 'no_output_architect' | 'direct'
  // Artifact fields (present when type === 'artifact')
  id?: string
  title?: string
  format?: string
  mimeType?: string
  sizeBytes?: number
  previewMarkdown?: string
  status?: string
}

/**
 * Pipeline phase names for CKO streaming
 */
export type PipelinePhase = 'analyzing' | 'searching' | 'reasoning' | 'formatting'

/**
 * Source citation from query response
 */
export interface SourceCitation {
  id: string
  documentId: string
  documentTitle: string
  pageNumber?: number
  excerpt: string
  relevanceScore: number
}

/**
 * Complete query response (non-streaming)
 */
export interface QueryResponse {
  answer: string
  sources: SourceCitation[]
  workflowType: 'langgraph' | 'crewai' | 'simple'
  iterations?: number
  processingTimeMs: number
}

// ============ Documents API Types ============

/**
 * Document metadata from API
 */
export interface DocumentMetadata {
  id: string
  filename: string
  mimeType: string
  fileSize: number
  uploadedAt: string
  projectId?: string
  status: 'pending' | 'processing' | 'indexed' | 'error'
  pageCount?: number
  chunkCount?: number
}

/**
 * Document upload result
 */
export interface UploadResult {
  id: string
  filename: string
  status: 'success' | 'error'
  error?: string
}

/**
 * List documents request params
 */
export interface ListDocumentsParams {
  projectId?: string
  status?: DocumentMetadata['status']
  limit?: number
  offset?: number
}

/**
 * Paginated document list response
 */
export interface DocumentListResponse {
  documents: DocumentMetadata[]
  total: number
  limit: number
  offset: number
}

// ============ WebSocket Chat Types ============

/**
 * WebSocket message types
 */
export type WSMessageType =
  | 'chat_start'
  | 'chat_token'
  | 'chat_source'
  | 'chat_end'
  | 'error'
  | 'ping'
  | 'pong'

/**
 * WebSocket incoming message
 */
export interface WSMessage {
  type: WSMessageType
  data?: unknown
  timestamp: number
}

/**
 * Chat start message
 */
export interface WSChatStart {
  type: 'chat_start'
  conversationId: string
  messageId: string
}

/**
 * Chat token message (streaming content)
 */
export interface WSChatToken {
  type: 'chat_token'
  token: string
  messageId: string
}

/**
 * Chat source message
 */
export interface WSChatSource {
  type: 'chat_source'
  source: SourceCitation
  messageId: string
}

/**
 * Chat end message
 */
export interface WSChatEnd {
  type: 'chat_end'
  messageId: string
  processingTimeMs: number
}

/**
 * WebSocket error message
 */
export interface WSError {
  type: 'error'
  code: string
  message: string
}

/**
 * Outgoing chat message
 */
export interface ChatMessage {
  type: 'chat'
  content: string
  conversationId?: string
  projectId?: string
}

// ============ Health API Types ============

/**
 * Health check response
 */
export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  version: string
  components: {
    database: boolean
    neo4j: boolean
    redis: boolean
    embeddings: boolean
  }
}

// ============ API Error Types ============

/**
 * API error response
 */
export interface APIError {
  code: string
  message: string
  details?: Record<string, unknown>
}

/**
 * Retry configuration
 */
export interface RetryConfig {
  maxRetries: number
  baseDelayMs: number
  maxDelayMs: number
}
