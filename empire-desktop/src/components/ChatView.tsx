import { useEffect, useRef, useCallback } from 'react'
import { useChatStore } from '@/stores/chat'
import { MessageBubble, ChatInput } from '@/components/chat'
import { queryStream, uploadDocuments, EmpireAPIError } from '@/lib/api'
import { createConversation, createMessage } from '@/lib/database'
import type { Message } from '@/types'

export function ChatView() {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const {
    messages,
    isStreaming,
    streamingContent,
    activeConversationId,
    activeProjectId,
    isKBMode,
    setKBMode,
    rateMessage,
    addMessage,
    setStreaming,
    appendStreamingContent,
    addStreamingSource,
    clearStreamingContent,
    finalizeStreamingMessage,
    updateMessage: updateStoreMessage,
    setError,
    error,
    setActiveConversation,
  } = useChatStore()

  // Handle rating a message
  const handleRateMessage = useCallback((messageId: string, rating: -1 | 0 | 1, feedback?: string) => {
    rateMessage(messageId, rating, feedback)
    // TODO: Send rating to backend API for AI Studio feedback collection
  }, [rateMessage])

  // Handle improve action - navigate to AI Studio with context
  const handleImprove = useCallback((messageId: string) => {
    window.dispatchEvent(new CustomEvent('navigate', {
      detail: {
        view: 'ai-studio',
        tab: 'feedback',
        context: { messageId, action: 'improve' }
      }
    }))
  }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Handle sending a message
  const handleSendMessage = useCallback(async (content: string, files?: File[]) => {
    try {
      setError(null)

      // Upload files first if any
      if (files?.length) {
        try {
          await uploadDocuments(files)
        } catch (err) {
          console.error('File upload failed:', err)
          setError('Failed to upload files. Please try again.')
          return
        }
      }

      // Create conversation if none exists
      let conversationId = activeConversationId
      if (!conversationId) {
        const title = content.slice(0, 50) + (content.length > 50 ? '...' : '')
        const conversation = await createConversation(title, activeProjectId || undefined)
        conversationId = conversation.id
        setActiveConversation(conversation.id)
      }

      // Create user message
      const userMessage: Message = {
        id: crypto.randomUUID(),
        conversationId,
        role: 'user',
        content,
        createdAt: new Date(),
        updatedAt: new Date(),
        status: 'complete',
      }

      addMessage(userMessage)
      await createMessage(conversationId, 'user', content, 'complete')

      // Create placeholder for assistant message
      const assistantMessageId = crypto.randomUUID()
      const assistantMessage: Message = {
        id: assistantMessageId,
        conversationId,
        role: 'assistant',
        content: '',
        createdAt: new Date(),
        updatedAt: new Date(),
        status: 'streaming',
      }

      addMessage(assistantMessage)
      setStreaming(true, assistantMessageId)

      // Create abort controller for stopping
      abortControllerRef.current = new AbortController()

      // Start streaming response
      try {
        for await (const chunk of queryStream({
          query: content,
          projectId: activeProjectId || undefined,
          includeSourceCitations: true,
        })) {
          // Check if aborted
          if (abortControllerRef.current?.signal.aborted) {
            break
          }

          if (chunk.type === 'token' && chunk.content) {
            appendStreamingContent(chunk.content)
          } else if (chunk.type === 'source' && chunk.source) {
            addStreamingSource(chunk.source)
          } else if (chunk.type === 'error') {
            setError(chunk.error || 'An error occurred')
            break
          } else if (chunk.type === 'done') {
            break
          }
        }

        // Finalize the message
        const finalContent = useChatStore.getState().streamingContent
        const finalSources = useChatStore.getState().streamingSources

        updateStoreMessage(assistantMessageId, {
          content: finalContent,
          sources: finalSources.length > 0 ? finalSources : undefined,
          status: 'complete',
        })

        // Save to database
        await createMessage(conversationId, 'assistant', finalContent, 'complete')
      } catch (err) {
        console.error('Streaming error:', err)
        if (err instanceof EmpireAPIError) {
          setError(err.message)
        } else {
          setError('Failed to get response. Please try again.')
        }

        updateStoreMessage(assistantMessageId, {
          content: streamingContent || 'Error: Failed to get response',
          status: 'error',
        })
      } finally {
        clearStreamingContent()
        setStreaming(false)
        abortControllerRef.current = null
      }
    } catch (err) {
      console.error('Send message error:', err)
      setError('Failed to send message. Please try again.')
    }
  }, [
    activeConversationId,
    activeProjectId,
    addMessage,
    setStreaming,
    appendStreamingContent,
    addStreamingSource,
    clearStreamingContent,
    updateStoreMessage,
    setError,
    setActiveConversation,
    streamingContent,
  ])

  // Handle stop button
  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort()
    finalizeStreamingMessage()
  }, [finalizeStreamingMessage])

  // Handle regenerate
  const handleRegenerate = useCallback(() => {
    if (messages.length < 2) return

    // Get the last user message
    const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user')
    if (lastUserMessage) {
      handleSendMessage(lastUserMessage.content)
    }
  }, [messages, handleSendMessage])

  return (
    <div className="flex flex-col h-full bg-empire-bg">
      {/* KB Mode Toggle Header */}
      <div className="px-4 py-3 border-b border-empire-border bg-empire-card/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-empire-text-muted">Mode:</span>
          <div className="flex items-center gap-2 bg-empire-bg rounded-lg p-1">
            <button
              className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                !isKBMode
                  ? 'bg-empire-primary text-white shadow-sm'
                  : 'text-empire-text-muted hover:text-empire-text'
              }`}
              onClick={() => setKBMode(false)}
            >
              Project
            </button>
            <button
              className={`px-3 py-1.5 text-sm rounded-md transition-all flex items-center gap-1.5 ${
                isKBMode
                  ? 'bg-empire-accent text-white shadow-sm'
                  : 'text-empire-text-muted hover:text-empire-text'
              }`}
              onClick={() => setKBMode(true)}
            >
              <span>📚</span>
              KB Chat
            </button>
          </div>
          {isKBMode && (
            <span className="text-xs px-2 py-1 rounded-full bg-empire-accent/20 text-empire-accent">
              Response feedback enabled
            </span>
          )}
        </div>
        <button
          className="text-sm text-empire-primary hover:text-empire-accent transition-colors flex items-center gap-1.5"
          onClick={() => {
            // Navigate to AI Studio - this would use the app's router
            window.dispatchEvent(new CustomEvent('navigate', { detail: { view: 'ai-studio' } }))
          }}
        >
          <span>🎨</span>
          AI Studio
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20">
          <p className="text-sm text-red-400 text-center">{error}</p>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {messages.length === 0 && !streamingContent ? (
          <WelcomeScreen />
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((message, idx) => (
              <MessageBubble
                key={message.id}
                message={
                  message.id === useChatStore.getState().streamingMessageId
                    ? { ...message, content: streamingContent || message.content }
                    : message
                }
                isStreaming={
                  isStreaming &&
                  message.id === useChatStore.getState().streamingMessageId
                }
                isKBMode={isKBMode}
                onRegenerate={
                  message.role === 'assistant' && idx === messages.length - 1
                    ? handleRegenerate
                    : undefined
                }
                onRate={
                  message.role === 'assistant'
                    ? (rating, feedback) => handleRateMessage(message.id, rating, feedback)
                    : undefined
                }
                onImprove={
                  message.role === 'assistant'
                    ? () => handleImprove(message.id)
                    : undefined
                }
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <ChatInput
        onSubmit={handleSendMessage}
        onStop={handleStop}
        disabled={!navigator.onLine}
      />
    </div>
  )
}

function WelcomeScreen() {
  const suggestions = [
    'What are the key terms in my employment contracts?',
    'Summarize our Q4 financial projections',
    'Find all documents related to compliance',
    'What is our company policy on remote work?',
  ]

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-empire-primary to-empire-accent flex items-center justify-center mb-6 shadow-lg shadow-empire-primary/20">
        <span className="text-4xl">🏛️</span>
      </div>
      <h2 className="text-2xl font-semibold text-empire-text mb-3">
        Welcome to Empire Desktop
      </h2>
      <p className="text-empire-text-muted max-w-md mb-8">
        Ask questions about your knowledge base. I'll search through your
        documents and provide answers with source citations.
      </p>

      {/* Suggestions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            className="p-3 text-left text-sm rounded-xl border border-empire-border bg-empire-card hover:bg-empire-border transition-colors text-empire-text-muted hover:text-empire-text"
            onClick={() => {
              const input = document.querySelector('textarea')
              if (input) {
                input.value = suggestion
                input.dispatchEvent(new Event('input', { bubbles: true }))
                input.focus()
              }
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}

export default ChatView
