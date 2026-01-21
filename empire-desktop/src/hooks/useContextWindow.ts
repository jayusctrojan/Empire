import { useState, useEffect, useCallback, useRef } from 'react'
import type { ContextWindowStatus, ContextStatus } from '@/types'

interface UseContextWindowOptions {
  conversationId?: string
  pollInterval?: number // milliseconds, default 5000
  enableWebSocket?: boolean
}

interface UseContextWindowReturn {
  // State
  status: ContextWindowStatus | null
  isLoading: boolean
  error: string | null
  isConnected: boolean

  // Computed values
  usedPercent: number
  reservedPercent: number
  availablePercent: number
  contextStatus: ContextStatus

  // Actions
  refresh: () => Promise<void>
  disconnect: () => void
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Threshold constants
const WARNING_THRESHOLD = 70
const CRITICAL_THRESHOLD = 85

/**
 * Hook to manage context window state and real-time updates
 *
 * Provides:
 * - Current token usage and status
 * - Calculated percentages for progress bar
 * - WebSocket connection for real-time updates
 * - Manual refresh capability
 */
export function useContextWindow(options: UseContextWindowOptions = {}): UseContextWindowReturn {
  const {
    conversationId,
    pollInterval = 5000,
    enableWebSocket = true,
  } = options

  const [status, setStatus] = useState<ContextWindowStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Calculate percentages
  const usedPercent = status
    ? (status.currentTokens / status.maxTokens) * 100
    : 0
  const reservedPercent = status
    ? (status.reservedTokens / status.maxTokens) * 100
    : 5
  const availablePercent = Math.max(0, 100 - usedPercent - reservedPercent)

  // Determine status based on thresholds
  const contextStatus: ContextStatus = usedPercent >= CRITICAL_THRESHOLD
    ? 'critical'
    : usedPercent >= WARNING_THRESHOLD
      ? 'warning'
      : 'normal'

  // Fetch status from API
  const fetchStatus = useCallback(async () => {
    if (!conversationId) return

    try {
      setIsLoading(true)
      setError(null)

      const response = await fetch(
        `${API_BASE_URL}/api/context-window/${conversationId}/status`,
        {
          headers: {
            'Content-Type': 'application/json',
            // Auth header would be added by auth middleware
          },
        }
      )

      if (!response.ok) {
        if (response.status === 404) {
          // No context exists yet, use defaults
          setStatus({
            conversationId,
            currentTokens: 0,
            maxTokens: 200000,
            reservedTokens: 10000,
            thresholdPercent: 80,
            usagePercent: 0,
            status: 'normal',
            availableTokens: 190000,
            estimatedMessagesRemaining: 950,
            isCompacting: false,
            lastUpdated: new Date(),
          })
          return
        }
        throw new Error(`Failed to fetch context status: ${response.statusText}`)
      }

      const data = await response.json()

      setStatus({
        conversationId: data.conversation_id,
        currentTokens: data.current_tokens,
        maxTokens: data.max_tokens,
        reservedTokens: data.reserved_tokens,
        thresholdPercent: data.threshold_percent,
        usagePercent: data.usage_percent,
        status: data.status as ContextStatus,
        availableTokens: data.available_tokens,
        estimatedMessagesRemaining: data.estimated_messages_remaining,
        isCompacting: data.is_compacting,
        lastCompactionAt: data.last_compaction_at
          ? new Date(data.last_compaction_at)
          : undefined,
        lastUpdated: new Date(data.last_updated),
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [conversationId])

  // Connect WebSocket for real-time updates
  const connectWebSocket = useCallback(() => {
    if (!conversationId || !enableWebSocket) return

    // Build WebSocket URL
    const wsProtocol = API_BASE_URL.startsWith('https') ? 'wss' : 'ws'
    const wsBaseUrl = API_BASE_URL.replace(/^https?/, wsProtocol)
    const wsUrl = `${wsBaseUrl}/api/context-window/${conversationId}/ws`

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        setIsConnected(true)
        setError(null)
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)

          if (message.type === 'context_status_update') {
            const data = message.data
            setStatus({
              conversationId: data.conversation_id,
              currentTokens: data.current_tokens,
              maxTokens: data.max_tokens,
              reservedTokens: data.reserved_tokens || 10000,
              thresholdPercent: data.threshold_percent || 80,
              usagePercent: data.usage_percent,
              status: data.status as ContextStatus,
              availableTokens: data.available_tokens,
              estimatedMessagesRemaining: data.estimated_messages_remaining,
              isCompacting: data.is_compacting,
              lastUpdated: new Date(data.last_updated),
            })
          } else if (message.type === 'pong') {
            // Heartbeat response
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        // Attempt reconnect after delay
        setTimeout(() => {
          if (wsRef.current === ws) {
            connectWebSocket()
          }
        }, 3000)
      }

      ws.onerror = () => {
        setIsConnected(false)
        setError('WebSocket connection error')
      }

      wsRef.current = ws

      // Send periodic pings to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000)

      return () => {
        clearInterval(pingInterval)
        ws.close()
      }
    } catch (err) {
      setError('Failed to establish WebSocket connection')
    }
  }, [conversationId, enableWebSocket])

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    setIsConnected(false)
  }, [])

  // Refresh status
  const refresh = useCallback(async () => {
    await fetchStatus()
  }, [fetchStatus])

  // Initial fetch and WebSocket setup
  useEffect(() => {
    if (conversationId) {
      fetchStatus()

      if (enableWebSocket) {
        const cleanup = connectWebSocket()
        return () => {
          cleanup?.()
          disconnect()
        }
      } else {
        // Fall back to polling
        pollIntervalRef.current = setInterval(fetchStatus, pollInterval)
        return () => {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
          }
        }
      }
    }

    return () => {
      disconnect()
    }
  }, [conversationId, enableWebSocket, pollInterval, fetchStatus, connectWebSocket, disconnect])

  return {
    status,
    isLoading,
    error,
    isConnected,
    usedPercent,
    reservedPercent,
    availablePercent,
    contextStatus,
    refresh,
    disconnect,
  }
}

export default useContextWindow
