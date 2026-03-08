/**
 * Compaction API
 * Context window management and error recovery
 */

import { get, post } from './client'

// Types for Compaction
export interface TriggerCompactionRequest {
  conversationId: string
  force?: boolean
}

export interface CompactionLogEntry {
  id: string
  conversationId: string
  preTokens: number
  postTokens: number
  reductionPercent: number
  messagesCondensed: number
  summary: string
  trigger: 'auto' | 'manual' | 'threshold' | 'error_recovery'
  timestamp: string
  durationMs?: number
  // Snake case aliases for API response compatibility
  pre_tokens: number
  post_tokens: number
  reduction_percent: number
  messages_condensed: number
}

export interface CompactionResultResponse {
  success: boolean
  entry?: CompactionLogEntry
  error?: string
  log?: CompactionLogEntry
}

export interface CompactionHistoryResponse {
  entries: CompactionLogEntry[]
  total: number
}

export interface CompactionProgressResponse {
  taskId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress?: number
  result?: CompactionResultResponse
  error?: string
}

// Types for Error Recovery
export interface RecoveryResponse {
  success: boolean
  taskId?: string
  message: string
  error?: string
  reduction_percent?: number
  pre_tokens?: number
  post_tokens?: number
}

export interface RecoveryProgressResponse {
  taskId: string
  status: 'pending' | 'recovering' | 'completed' | 'failed'
  stage?: 'compacting' | 'retrying' | 'complete'
  progress?: number
  error?: string
  result?: {
    success: boolean
    response?: string
    error?: string
  }
}

// Compaction API Functions

export async function triggerCompaction(
  conversationId: string,
  options?: { force?: boolean; fast?: boolean }
): Promise<CompactionResultResponse> {
  return post<CompactionResultResponse>('/api/compaction/trigger', {
    conversationId,
    force: options?.force,
    fast: options?.fast,
  })
}

export async function triggerAsyncCompaction(
  request: TriggerCompactionRequest
): Promise<{ taskId: string }> {
  return post<{ taskId: string }>('/api/compaction/trigger/async', request)
}

export async function getCompactionProgress(taskId: string): Promise<CompactionProgressResponse> {
  return get<CompactionProgressResponse>(`/api/compaction/progress/${taskId}`)
}

export async function getCompactionHistory(
  conversationId: string,
  limit = 10
): Promise<CompactionHistoryResponse> {
  return get<CompactionHistoryResponse>(
    `/api/compaction/history/${conversationId}?limit=${limit}`
  )
}

export async function getTaskProgress(taskId: string): Promise<CompactionProgressResponse> {
  return get<CompactionProgressResponse>(`/api/tasks/${taskId}/progress`)
}

export async function cancelCompactionTask(taskId: string): Promise<{ success: boolean }> {
  return post<{ success: boolean }>(`/api/tasks/${taskId}/cancel`, {})
}

// Error Recovery Functions

export function isContextOverflowError(error: unknown): boolean {
  if (error instanceof Error) {
    const message = error.message.toLowerCase()
    return (
      message.includes('context') &&
      (message.includes('overflow') ||
        message.includes('too long') ||
        message.includes('token limit') ||
        message.includes('max tokens'))
    )
  }
  return false
}

export async function triggerRecovery(
  conversationId: string,
  originalMessage?: string
): Promise<RecoveryResponse> {
  return post<RecoveryResponse>('/api/recovery/trigger', {
    conversationId,
    originalMessage,
  })
}

export async function getRecoveryProgress(taskId: string): Promise<RecoveryProgressResponse> {
  return get<RecoveryProgressResponse>(`/api/recovery/progress/${taskId}`)
}

export async function sendWithRecovery(
  conversationId: string,
  message: string,
  onRecoveryStart?: () => void
): Promise<string> {
  try {
    // Try to send message normally first
    const response = await post<{ response: string }>('/api/chat/send', {
      conversationId,
      message,
    })
    return response.response
  } catch (error) {
    if (isContextOverflowError(error)) {
      // Trigger recovery
      onRecoveryStart?.()
      const recovery = await triggerRecovery(conversationId, message)

      if (!recovery.success || !recovery.taskId) {
        throw new Error(recovery.message || 'Recovery failed to start')
      }

      // Poll for recovery completion
      let progress: RecoveryProgressResponse
      do {
        await new Promise(resolve => setTimeout(resolve, 1000))
        progress = await getRecoveryProgress(recovery.taskId)
      } while (progress.status === 'pending' || progress.status === 'recovering')

      if (progress.status === 'failed' || !progress.result?.success) {
        throw new Error(progress.error || progress.result?.error || 'Recovery failed')
      }

      return progress.result.response || ''
    }
    throw error
  }
}
