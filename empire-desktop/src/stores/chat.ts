import { create } from 'zustand'
import type { Conversation, Message, Source, SourceCitation, CompactionEvent } from '@/types'

// Response metadata from KB mode
export interface KBResponseMetadata {
  workflow?: string
  agent?: string
  department?: string
}

interface ChatState {
  // Conversations
  conversations: Conversation[]
  activeConversationId: string | null
  activeProjectId: string | null

  // Messages for active conversation
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
  streamingSources: Source[]
  streamingMessageId: string | null

  // KB Mode state
  isKBMode: boolean
  streamingMetadata: KBResponseMetadata | null

  // Pending files for upload
  pendingFiles: File[]

  // Error state
  error: string | null

  // Compaction state (Feature 011 - Task 204)
  compactionEvents: CompactionEvent[]
  isCompacting: boolean

  // Actions
  setConversations: (conversations: Conversation[]) => void
  addConversation: (conversation: Conversation) => void
  setActiveConversation: (id: string | null) => void
  setActiveProject: (id: string | null) => void
  deleteConversation: (id: string) => void
  renameConversation: (id: string, title: string) => void

  // Message actions
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  updateMessage: (id: string, updates: Partial<Message>) => void
  setStreaming: (isStreaming: boolean, messageId?: string) => void
  appendStreamingContent: (content: string) => void
  addStreamingSource: (source: SourceCitation) => void
  clearStreamingContent: () => void
  finalizeStreamingMessage: () => void

  // KB Mode actions
  setKBMode: (enabled: boolean) => void
  setStreamingMetadata: (metadata: KBResponseMetadata | null) => void
  rateMessage: (messageId: string, rating: -1 | 0 | 1, feedback?: string) => void

  // File actions
  addPendingFiles: (files: File[]) => void
  removePendingFile: (index: number) => void
  clearPendingFiles: () => void

  // Error actions
  setError: (error: string | null) => void

  // Compaction actions (Feature 011 - Task 204)
  setCompacting: (isCompacting: boolean) => void
  addCompactionEvent: (event: CompactionEvent) => void
  setCompactionEvents: (events: CompactionEvent[]) => void
  clearCompactionEvents: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  conversations: [],
  activeConversationId: null,
  activeProjectId: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  streamingSources: [],
  streamingMessageId: null,
  isKBMode: false,
  streamingMetadata: null,
  pendingFiles: [],
  error: null,
  compactionEvents: [],
  isCompacting: false,

  // Conversation actions
  setConversations: (conversations) => set({ conversations }),

  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      activeConversationId: conversation.id,
    })),

  setActiveConversation: (id) =>
    set({
      activeConversationId: id,
      messages: [],
      streamingContent: '',
      streamingSources: [],
      error: null,
      compactionEvents: [],
      isCompacting: false,
    }),

  setActiveProject: (id) => set({ activeProjectId: id }),

  deleteConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId:
        state.activeConversationId === id ? null : state.activeConversationId,
    })),

  renameConversation: (id, title) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    })),

  // Message actions
  setMessages: (messages) => set({ messages }),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, ...updates } : m
      ),
    })),

  setStreaming: (isStreaming, messageId) =>
    set({
      isStreaming,
      streamingMessageId: messageId ?? null,
      ...(isStreaming ? {} : { streamingContent: '', streamingSources: [] }),
    }),

  appendStreamingContent: (content) =>
    set((state) => ({
      streamingContent: state.streamingContent + content,
    })),

  addStreamingSource: (source) =>
    set((state) => ({
      streamingSources: [
        ...state.streamingSources,
        {
          id: source.id,
          documentId: source.documentId,
          documentTitle: source.documentTitle,
          pageNumber: source.pageNumber,
          excerpt: source.excerpt,
          relevanceScore: source.relevanceScore,
        },
      ],
    })),

  clearStreamingContent: () =>
    set({ streamingContent: '', streamingSources: [], streamingMessageId: null }),

  finalizeStreamingMessage: () => {
    const state = get()
    if (state.streamingContent && state.streamingMessageId) {
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === s.streamingMessageId
            ? {
                ...m,
                content: s.streamingContent,
                sources: s.streamingSources.length > 0 ? s.streamingSources : m.sources,
                status: 'complete' as const,
                // Include KB metadata if in KB mode
                ...(s.isKBMode && s.streamingMetadata ? {
                  isKBResponse: true,
                  workflow: s.streamingMetadata.workflow,
                  agent: s.streamingMetadata.agent,
                  department: s.streamingMetadata.department,
                } : {}),
              }
            : m
        ),
        streamingContent: '',
        streamingSources: [],
        streamingMessageId: null,
        streamingMetadata: null,
        isStreaming: false,
      }))
    }
  },

  // KB Mode actions
  setKBMode: (enabled) => set({ isKBMode: enabled }),

  setStreamingMetadata: (metadata) => set({ streamingMetadata: metadata }),

  rateMessage: (messageId, rating, feedback) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId
          ? { ...m, rating, ratingFeedback: feedback }
          : m
      ),
    })),

  // File actions
  addPendingFiles: (files) =>
    set((state) => ({
      pendingFiles: [...state.pendingFiles, ...files],
    })),

  removePendingFile: (index) =>
    set((state) => ({
      pendingFiles: state.pendingFiles.filter((_, i) => i !== index),
    })),

  clearPendingFiles: () => set({ pendingFiles: [] }),

  // Error actions
  setError: (error) => set({ error }),

  // Compaction actions (Feature 011 - Task 204)
  setCompacting: (isCompacting) => set({ isCompacting }),

  addCompactionEvent: (event) =>
    set((state) => {
      if (state.activeConversationId && event.conversationId !== state.activeConversationId) {
        return state
      }
      return {
        compactionEvents: [...state.compactionEvents, event],
        isCompacting: false,
      }
    }),

  setCompactionEvents: (events) => set({ compactionEvents: events }),

  clearCompactionEvents: () => set({ compactionEvents: [], isCompacting: false }),
}))
