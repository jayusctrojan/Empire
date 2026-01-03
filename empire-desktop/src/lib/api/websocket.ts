/**
 * WebSocket Chat Client
 * Real-time chat streaming via /ws/chat endpoint
 */

import { useAuthStore } from '@/stores/auth'
import { getApiBaseUrl } from './client'
import type {
  WSMessage,
  WSChatStart,
  WSChatToken,
  WSChatSource,
  WSChatEnd,
  WSError,
  ChatMessage,
} from '@/types'

// Connection states
export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

// Event handlers
export interface ChatClientHandlers {
  onChatStart?: (event: WSChatStart) => void
  onToken?: (event: WSChatToken) => void
  onSource?: (event: WSChatSource) => void
  onChatEnd?: (event: WSChatEnd) => void
  onError?: (event: WSError) => void
  onConnectionChange?: (state: ConnectionState) => void
}

// Retry configuration
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_DELAY_MS = 1000
const RECONNECT_MAX_DELAY_MS = 30000

/**
 * WebSocket Chat Client
 * Manages connection lifecycle and message handling
 */
export class ChatWebSocketClient {
  private ws: WebSocket | null = null
  private handlers: ChatClientHandlers = {}
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private _connectionState: ConnectionState = 'disconnected'
  private shouldReconnect = true

  constructor(handlers?: ChatClientHandlers) {
    if (handlers) {
      this.handlers = handlers
    }
  }

  /**
   * Get current connection state
   */
  get connectionState(): ConnectionState {
    return this._connectionState
  }

  /**
   * Set connection state and notify handler
   */
  private setConnectionState(state: ConnectionState): void {
    this._connectionState = state
    this.handlers.onConnectionChange?.(state)
  }

  /**
   * Connect to WebSocket chat endpoint
   */
  async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return // Already connected
    }

    this.shouldReconnect = true
    this.setConnectionState('connecting')

    const token = useAuthStore.getState().jwt
    const baseUrl = getApiBaseUrl().replace(/^http/, 'ws')
    const wsUrl = token
      ? `${baseUrl}/ws/chat?token=${encodeURIComponent(token)}`
      : `${baseUrl}/ws/chat`

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          this.reconnectAttempts = 0
          this.setConnectionState('connected')
          resolve()
        }

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data as string)
        }

        this.ws.onerror = (event) => {
          console.error('WebSocket error:', event)
          this.handlers.onError?.({
            type: 'error',
            code: 'WS_ERROR',
            message: 'WebSocket connection error',
          })
        }

        this.ws.onclose = (event) => {
          this.setConnectionState('disconnected')

          if (this.shouldReconnect && !event.wasClean) {
            this.scheduleReconnect()
          }

          if (this._connectionState === 'connecting') {
            reject(new Error('WebSocket connection failed'))
          }
        }
      } catch (error) {
        this.setConnectionState('disconnected')
        reject(error)
      }
    })
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    this.shouldReconnect = false

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }

    this.setConnectionState('disconnected')
  }

  /**
   * Send chat message
   */
  sendMessage(content: string, conversationId?: string, projectId?: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected')
    }

    const message: ChatMessage = {
      type: 'chat',
      content,
      conversationId,
      projectId,
    }

    this.ws.send(JSON.stringify(message))
  }

  /**
   * Send ping to keep connection alive
   */
  ping(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'ping' }))
    }
  }

  /**
   * Update event handlers
   */
  setHandlers(handlers: ChatClientHandlers): void {
    this.handlers = { ...this.handlers, ...handlers }
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data) as WSMessage

      switch (message.type) {
        case 'chat_start':
          this.handlers.onChatStart?.(message as unknown as WSChatStart)
          break
        case 'chat_token':
          this.handlers.onToken?.(message as unknown as WSChatToken)
          break
        case 'chat_source':
          this.handlers.onSource?.(message as unknown as WSChatSource)
          break
        case 'chat_end':
          this.handlers.onChatEnd?.(message as unknown as WSChatEnd)
          break
        case 'error':
          this.handlers.onError?.(message as unknown as WSError)
          break
        case 'pong':
          // Keep-alive response, no action needed
          break
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error, data)
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error('Max reconnect attempts reached')
      this.handlers.onError?.({
        type: 'error',
        code: 'MAX_RECONNECT',
        message: 'Maximum reconnection attempts reached',
      })
      return
    }

    const delay = Math.min(
      RECONNECT_BASE_DELAY_MS * Math.pow(2, this.reconnectAttempts),
      RECONNECT_MAX_DELAY_MS
    )

    this.setConnectionState('reconnecting')
    this.reconnectAttempts++

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)

    this.reconnectTimer = setTimeout(() => {
      this.connect().catch((error) => {
        console.error('Reconnection failed:', error)
      })
    }, delay)
  }
}

// Singleton instance
let chatClient: ChatWebSocketClient | null = null

/**
 * Get or create chat client singleton
 */
export function getChatClient(handlers?: ChatClientHandlers): ChatWebSocketClient {
  if (!chatClient) {
    chatClient = new ChatWebSocketClient(handlers)
  } else if (handlers) {
    chatClient.setHandlers(handlers)
  }
  return chatClient
}

/**
 * Disconnect and clear chat client
 */
export function disconnectChatClient(): void {
  if (chatClient) {
    chatClient.disconnect()
    chatClient = null
  }
}
