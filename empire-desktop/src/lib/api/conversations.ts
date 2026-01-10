/**
 * Empire Conversations API
 * CRUD operations for chat conversations stored in Supabase
 *
 * Conversations are persisted in the cloud to survive desktop app updates
 */

import { get, post, del, apiRequest } from './client'
import type { Conversation, Message, Source } from '@/types'

// ============ API Types ============

export type MessageRole = 'user' | 'assistant'

export interface APIConversation {
  id: string
  user_id: string
  project_id: string | null
  title: string
  summary: string | null
  message_count: number
  total_tokens: number
  is_active: boolean
  metadata: Record<string, unknown> | null
  first_message_at: string | null
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export interface APIConversationSummary {
  id: string
  project_id: string | null
  title: string
  message_count: number
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export interface APIMessage {
  id: string
  session_id: string
  message_index: number
  role: MessageRole
  content: string
  sources: Array<Record<string, unknown>> | null
  metadata: Record<string, unknown> | null
  model_name: string | null
  tokens_used: number | null
  processing_time_ms: number | null
  created_at: string
}

export interface CreateConversationRequest {
  title?: string
  project_id?: string
  metadata?: Record<string, unknown>
}

export interface UpdateConversationRequest {
  title?: string
  summary?: string
  is_active?: boolean
  metadata?: Record<string, unknown>
}

export interface CreateMessageRequest {
  role: MessageRole
  content: string
  sources?: Array<Record<string, unknown>>
  metadata?: Record<string, unknown>
  model_name?: string
  tokens_used?: number
  processing_time_ms?: number
}

export interface UpdateMessageRequest {
  content?: string
  sources?: Array<Record<string, unknown>>
  metadata?: Record<string, unknown>
}

// Response types
export interface CreateConversationResponse {
  success: boolean
  conversation?: APIConversation
  message: string
  error?: string
}

export interface GetConversationResponse {
  success: boolean
  conversation?: APIConversation
  error?: string
}

export interface ListConversationsResponse {
  success: boolean
  conversations: APIConversationSummary[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface UpdateConversationResponse {
  success: boolean
  conversation?: APIConversation
  message: string
  error?: string
}

export interface DeleteConversationResponse {
  success: boolean
  conversation_id?: string
  message: string
  deleted_messages_count: number
  error?: string
}

export interface CreateMessageResponse {
  success: boolean
  message?: APIMessage
  error?: string
}

export interface ListMessagesResponse {
  success: boolean
  messages: APIMessage[]
  total: number
}

export interface UpdateMessageResponse {
  success: boolean
  message?: APIMessage
  error?: string
}

// ============ Helper Functions ============

/**
 * Convert API conversation to client Conversation type
 */
function toClientConversation(apiConv: APIConversation | APIConversationSummary): Conversation {
  return {
    id: apiConv.id,
    projectId: apiConv.project_id ?? undefined,
    title: apiConv.title,
    messageCount: apiConv.message_count,
    lastMessageAt: apiConv.last_message_at ? new Date(apiConv.last_message_at) : undefined,
    createdAt: new Date(apiConv.created_at),
    updatedAt: new Date(apiConv.updated_at),
  }
}

/**
 * Convert API message to client Message type
 */
function toClientMessage(apiMsg: APIMessage): Message {
  return {
    id: apiMsg.id,
    conversationId: apiMsg.session_id,
    role: apiMsg.role,
    content: apiMsg.content,
    sources: apiMsg.sources as Source[] | undefined,
    createdAt: new Date(apiMsg.created_at),
    updatedAt: new Date(apiMsg.created_at), // API doesn't track updated_at for messages
    status: 'complete',
  }
}

// ============ Conversation API Functions ============

/**
 * Get all conversations for the current user
 */
export async function listConversations(options?: {
  projectId?: string
  isActive?: boolean
  sortBy?: 'created_at' | 'updated_at' | 'last_message_at' | 'title'
  sortOrder?: 'asc' | 'desc'
  limit?: number
  offset?: number
}): Promise<Conversation[]> {
  const params: Record<string, string> = {}

  if (options?.projectId) params.project_id = options.projectId
  if (options?.isActive !== undefined) params.is_active = String(options.isActive)
  if (options?.sortBy) params.sort_by = options.sortBy
  if (options?.sortOrder) params.sort_order = options.sortOrder
  if (options?.limit) params.limit = options.limit.toString()
  if (options?.offset) params.offset = options.offset.toString()

  const response = await get<ListConversationsResponse>('/api/conversations', params)

  if (!response.success) {
    throw new Error('Failed to load conversations')
  }

  return response.conversations.map(toClientConversation)
}

/**
 * Get a single conversation by ID
 */
export async function getConversation(id: string): Promise<Conversation> {
  const response = await get<GetConversationResponse>(`/api/conversations/${id}`)

  if (!response.success || !response.conversation) {
    throw new Error(response.error || 'Conversation not found')
  }

  return toClientConversation(response.conversation)
}

/**
 * Create a new conversation
 */
export async function createConversation(
  title: string = 'New Conversation',
  projectId?: string
): Promise<Conversation> {
  const body: CreateConversationRequest = { title }
  if (projectId) body.project_id = projectId

  const response = await post<CreateConversationResponse>('/api/conversations', body)

  if (!response.success || !response.conversation) {
    throw new Error(response.error || 'Failed to create conversation')
  }

  return toClientConversation(response.conversation)
}

/**
 * Update a conversation
 */
export async function updateConversation(
  id: string,
  updates: UpdateConversationRequest
): Promise<Conversation> {
  const response = await apiRequest<UpdateConversationResponse>(`/api/conversations/${id}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  })

  if (!response.success || !response.conversation) {
    throw new Error(response.error || 'Failed to update conversation')
  }

  return toClientConversation(response.conversation)
}

/**
 * Delete a conversation and all its messages
 */
export async function deleteConversation(id: string): Promise<{ deletedMessagesCount: number }> {
  const response = await del<DeleteConversationResponse>(`/api/conversations/${id}`)

  if (!response.success) {
    throw new Error(response.error || 'Failed to delete conversation')
  }

  return { deletedMessagesCount: response.deleted_messages_count }
}

// ============ Message API Functions ============

/**
 * Get all messages in a conversation
 */
export async function listMessages(
  conversationId: string,
  options?: {
    limit?: number
    offset?: number
  }
): Promise<Message[]> {
  const params: Record<string, string> = {}

  if (options?.limit) params.limit = options.limit.toString()
  if (options?.offset) params.offset = options.offset.toString()

  const response = await get<ListMessagesResponse>(
    `/api/conversations/${conversationId}/messages`,
    params
  )

  if (!response.success) {
    throw new Error('Failed to load messages')
  }

  return response.messages.map(toClientMessage)
}

/**
 * Create a new message in a conversation
 */
export async function createMessage(
  conversationId: string,
  role: MessageRole,
  content: string,
  options?: {
    sources?: Source[]
    modelName?: string
    tokensUsed?: number
    processingTimeMs?: number
  }
): Promise<Message> {
  const body: CreateMessageRequest = {
    role,
    content,
  }

  if (options?.sources) body.sources = options.sources as Array<Record<string, unknown>>
  if (options?.modelName) body.model_name = options.modelName
  if (options?.tokensUsed) body.tokens_used = options.tokensUsed
  if (options?.processingTimeMs) body.processing_time_ms = options.processingTimeMs

  const response = await post<CreateMessageResponse>(
    `/api/conversations/${conversationId}/messages`,
    body
  )

  if (!response.success || !response.message) {
    throw new Error(response.error || 'Failed to create message')
  }

  return toClientMessage(response.message)
}

/**
 * Update a message
 */
export async function updateMessage(
  conversationId: string,
  messageId: string,
  updates: UpdateMessageRequest
): Promise<Message> {
  const response = await apiRequest<UpdateMessageResponse>(
    `/api/conversations/${conversationId}/messages/${messageId}`,
    {
      method: 'PUT',
      body: JSON.stringify(updates),
    }
  )

  if (!response.success || !response.message) {
    throw new Error(response.error || 'Failed to update message')
  }

  return toClientMessage(response.message)
}

/**
 * Sync conversations from API to local cache
 */
export async function syncConversations(projectId?: string): Promise<{
  conversations: Conversation[]
  syncedAt: string
}> {
  const conversations = await listConversations({
    projectId,
    sortBy: 'updated_at',
    sortOrder: 'desc',
  })

  return {
    conversations,
    syncedAt: new Date().toISOString(),
  }
}
