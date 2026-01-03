/**
 * Query API
 * Streaming query endpoint for Empire knowledge base
 */

import { fetch } from '@tauri-apps/plugin-http'
import { useAuthStore } from '@/stores/auth'
import { getApiBaseUrl, EmpireAPIError } from './client'
import type { QueryRequest, StreamChunk, QueryResponse } from '@/types'

/**
 * Streaming query endpoint using AsyncGenerator
 * Connects to POST /api/query/auto with streaming response
 */
export async function* queryStream(request: QueryRequest): AsyncGenerator<StreamChunk, void, undefined> {
  const url = `${getApiBaseUrl()}/api/query/auto`
  const token = useAuthStore.getState().jwt

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new EmpireAPIError(
      errorText || 'Query failed',
      'QUERY_ERROR',
      response.status
    )
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new EmpireAPIError('No response body', 'NO_BODY', 500)
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        // Process any remaining buffer
        if (buffer.trim()) {
          const chunk = parseSSELine(buffer)
          if (chunk) yield chunk
        }
        break
      }

      buffer += decoder.decode(value, { stream: true })

      // Process complete lines (SSE format)
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer

      for (const line of lines) {
        const chunk = parseSSELine(line)
        if (chunk) {
          yield chunk

          // Stop on done or error
          if (chunk.type === 'done' || chunk.type === 'error') {
            return
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * Parse SSE line into StreamChunk
 */
function parseSSELine(line: string): StreamChunk | null {
  const trimmed = line.trim()

  // Skip empty lines and comments
  if (!trimmed || trimmed.startsWith(':')) {
    return null
  }

  // Parse data: prefix
  if (trimmed.startsWith('data:')) {
    const jsonStr = trimmed.slice(5).trim()
    if (!jsonStr || jsonStr === '[DONE]') {
      return { type: 'done' }
    }

    try {
      return JSON.parse(jsonStr) as StreamChunk
    } catch {
      // Plain text token
      return { type: 'token', content: jsonStr }
    }
  }

  // Plain text (fallback)
  return { type: 'token', content: trimmed }
}

/**
 * Non-streaming query (waits for complete response)
 */
export async function query(request: QueryRequest): Promise<QueryResponse> {
  const url = `${getApiBaseUrl()}/api/query/auto`
  const token = useAuthStore.getState().jwt

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      ...request,
      stream: false,
    }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new EmpireAPIError(
      errorText || 'Query failed',
      'QUERY_ERROR',
      response.status
    )
  }

  return await response.json() as QueryResponse
}

/**
 * Helper to collect all streaming chunks into final response
 */
export async function collectStreamResponse(request: QueryRequest): Promise<{
  content: string
  sources: StreamChunk[]
}> {
  let content = ''
  const sources: StreamChunk[] = []

  for await (const chunk of queryStream(request)) {
    if (chunk.type === 'token' && chunk.content) {
      content += chunk.content
    } else if (chunk.type === 'source') {
      sources.push(chunk)
    } else if (chunk.type === 'error') {
      throw new EmpireAPIError(chunk.error || 'Stream error', 'STREAM_ERROR', 500)
    }
  }

  return { content, sources }
}
