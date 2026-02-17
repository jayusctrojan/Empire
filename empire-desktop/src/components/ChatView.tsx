import { useEffect, useRef, useCallback } from 'react'
import { useChatStore } from '@/stores/chat'
import { MessageBubble, ChatInput, PhaseIndicator, ArtifactPanel } from '@/components/chat'
import { queryStream, uploadDocuments, EmpireAPIError, downloadArtifact } from '@/lib/api'
import { createConversation, createMessage } from '@/lib/database'
import type { Message, Artifact, ArtifactFormat } from '@/types'

export function ChatView() {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const {
    messages,
    isStreaming,
    streamingContent,
    streamingMessageId,
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
    // Pipeline state
    currentPhase,
    currentPhaseLabel,
    setPhase,
    // Artifact state
    activeArtifact,
    isArtifactPanelOpen,
    setActiveArtifact,
    toggleArtifactPanel,
    addArtifactToMessage,
  } = useChatStore()

  // Handle rating a message
  const handleRateMessage = useCallback((messageId: string, rating: -1 | 0 | 1, feedback?: string) => {
    rateMessage(messageId, rating, feedback)
    // TODO: Send rating to backend API for AI Studio feedback collection
  }, [rateMessage])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Handle opening an artifact in the side panel
  const handleOpenArtifact = useCallback((artifact: Artifact) => {
    setActiveArtifact(artifact)
  }, [setActiveArtifact])

  // Handle downloading an artifact via Tauri save dialog
  const handleDownloadArtifact = useCallback(async (artifact: Artifact, format?: ArtifactFormat) => {
    try {
      await downloadArtifact(artifact, format)
    } catch (err) {
      console.error('Artifact download failed:', err)
      setError('Failed to download artifact. Please try again.')
    }
  }, [setError])

  // Handle sending a message
  const handleSendMessage = useCallback(async (content: string, files?: File[]) => {
    try {
      setError(null)
      setPhase(null)

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
            // Clear phase indicator once tokens start flowing
            setPhase(null)
            appendStreamingContent(chunk.content)
          } else if (chunk.type === 'source' && chunk.source) {
            addStreamingSource(chunk.source)
          } else if (chunk.type === 'phase' && chunk.phase) {
            // Pipeline phase indicator
            setPhase(chunk.phase, chunk.label)
          } else if (chunk.type === 'artifact') {
            // Artifact generated — attach to message
            const validFormats = new Set(['docx', 'xlsx', 'pptx', 'pdf', 'md'])
            const validStatuses = new Set(['uploading', 'ready', 'error'])
            const artifact: Artifact = {
              id: chunk.id || crypto.randomUUID(),
              sessionId: conversationId,
              title: chunk.title || 'Document',
              format: (validFormats.has(chunk.format || '') ? chunk.format : 'md') as Artifact['format'],
              mimeType: chunk.mimeType || 'text/markdown',
              sizeBytes: chunk.sizeBytes || 0,
              previewMarkdown: chunk.previewMarkdown,
              status: (validStatuses.has(chunk.status || '') ? chunk.status : 'uploading') as Artifact['status'],
            }
            addArtifactToMessage(assistantMessageId, artifact)
          } else if (chunk.type === 'error') {
            setError(chunk.error || 'An error occurred')
            break
          } else if (chunk.type === 'done') {
            // Capture pipeline mode if present
            if (chunk.pipeline_mode) {
              updateStoreMessage(assistantMessageId, { pipelineMode: chunk.pipeline_mode })
            }
            break
          }
        }

        // Finalize the message - get fresh state for final values
        setPhase(null)
        const state = useChatStore.getState()
        const finalContent = state.streamingContent
        const finalSources = state.streamingSources

        updateStoreMessage(assistantMessageId, {
          content: finalContent,
          sources: finalSources.length > 0 ? finalSources : undefined,
          status: 'complete',
        })

        // Save to database
        await createMessage(conversationId, 'assistant', finalContent, 'complete')
      } catch (err) {
        console.error('Streaming error:', err)
        setPhase(null)
        const errorContent = useChatStore.getState().streamingContent
        if (err instanceof EmpireAPIError) {
          setError(err.message)
        } else {
          setError('Failed to get response. Please try again.')
        }

        updateStoreMessage(assistantMessageId, {
          content: errorContent || 'Error: Failed to get response',
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
    setPhase,
    addArtifactToMessage,
  ])

  // Handle stop button
  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort()
    setPhase(null)
    finalizeStreamingMessage()
  }, [finalizeStreamingMessage, setPhase])

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
    <div className="flex h-full bg-empire-bg">
      {/* Main chat area */}
      <div className="flex flex-col flex-1 min-w-0">
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
                    message.id === streamingMessageId
                      ? { ...message, content: streamingContent || message.content }
                      : message
                  }
                  isStreaming={
                    isStreaming &&
                    message.id === streamingMessageId
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
                  onOpenArtifact={handleOpenArtifact}
                  onDownloadArtifact={handleDownloadArtifact}
                />
              ))}

              {/* Phase indicator (shows during pipeline phases before tokens stream) */}
              {isStreaming && currentPhase && (
                <PhaseIndicator phase={currentPhase} label={currentPhaseLabel} />
              )}

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

      {/* Artifact side panel */}
      {isArtifactPanelOpen && activeArtifact && (
        <ArtifactPanel
          artifact={activeArtifact}
          onClose={() => toggleArtifactPanel(false)}
          onDownload={handleDownloadArtifact}
        />
      )}
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
