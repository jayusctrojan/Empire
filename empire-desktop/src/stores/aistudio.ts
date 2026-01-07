import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ============================================================================
// Types
// ============================================================================

export type SidebarPanel = 'assets' | 'classifications' | 'weights' | 'feedback' | null

export interface CKOSession {
  id: string
  title: string | null
  messageCount: number
  pendingClarifications: number
  contextSummary: string | null
  createdAt: string
  updatedAt: string
  lastMessageAt: string | null
}

export interface CKOMessage {
  id: string
  sessionId: string
  role: 'user' | 'cko'
  content: string
  isClarification: boolean
  clarificationType?: string
  clarificationStatus?: 'pending' | 'answered' | 'skipped' | 'auto_skipped'
  clarificationAnswer?: string
  sources: Array<{
    docId: string
    title: string
    snippet: string
    relevanceScore: number
    pageNumber?: number
  }>
  actionsPerformed: Array<{
    action: string
    params: Record<string, unknown>
    result: Record<string, unknown>
  }>
  rating?: -1 | 0 | 1
  ratingFeedback?: string
  createdAt: string
}

export interface Asset {
  id: string
  assetType: 'skill' | 'command' | 'agent' | 'prompt' | 'workflow'
  department: string
  name: string
  title: string
  content: string
  format: 'yaml' | 'md' | 'json'
  status: 'draft' | 'published' | 'archived'
  sourceDocumentId?: string
  sourceDocumentTitle?: string
  classificationConfidence?: number
  classificationReasoning?: string
  version: number
  createdAt: string
  updatedAt: string
}

export interface Classification {
  id: string
  documentId?: string
  filename?: string
  contentPreview?: string
  department: string
  confidence: number
  reasoning?: string
  keywordsMatched: string[]
  secondaryDepartment?: string
  secondaryConfidence?: number
  userCorrectedDepartment?: string
  correctionReason?: string
  correctedAt?: string
  createdAt: string
}

export interface UserWeights {
  preset: 'balanced' | 'recent-focus' | 'verified-only' | 'custom'
  departments: Record<string, number>
  recency: {
    enabled: boolean
    last_30_days: number
    last_year: number
    older: number
  }
  sourceTypes: {
    enabled: boolean
    pdf: number
    video: number
    audio: number
    web: number
    notes: number
  }
  confidence: {
    enabled: boolean
    high: number
    medium: number
    low: number
  }
  verified: {
    enabled: boolean
    weight: number
  }
}

// ============================================================================
// Store State
// ============================================================================

interface AIStudioState {
  // Active sidebar panel
  activeSidebarPanel: SidebarPanel

  // CKO Conversation state
  activeSessionId: string | null
  sessions: CKOSession[]
  messages: CKOMessage[]
  isStreaming: boolean
  streamingContent: string

  // Connection and error state
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'degraded'
  degradationMessage: string | null
  lastError: string | null

  // Clarification tracking (FR-009, FR-010)
  pendingClarificationsCount: number
  hasOverdueClarifications: boolean

  // Assets state
  assets: Asset[]
  assetTypeFilter: string | null
  assetDepartmentFilter: string | null
  assetStatusFilter: string | null

  // Classifications state
  classifications: Classification[]
  classificationDepartmentFilter: string | null

  // Weights state
  userWeights: UserWeights

  // Search state
  searchQuery: string

  // Actions
  setActiveSidebarPanel: (panel: SidebarPanel) => void
  toggleSidebarPanel: (panel: SidebarPanel) => void

  // Session actions
  setActiveSession: (sessionId: string | null) => void
  setSessions: (sessions: CKOSession[]) => void
  addSession: (session: CKOSession) => void
  updateSession: (sessionId: string, updates: Partial<CKOSession>) => void
  deleteSession: (sessionId: string) => void

  // Message actions
  setMessages: (messages: CKOMessage[]) => void
  addMessage: (message: CKOMessage) => void
  updateMessage: (messageId: string, updates: Partial<CKOMessage>) => void
  setStreaming: (isStreaming: boolean, content?: string) => void

  // Clarification actions
  setPendingClarifications: (count: number, hasOverdue: boolean) => void

  // Asset actions
  setAssets: (assets: Asset[]) => void
  addAsset: (asset: Asset) => void
  updateAsset: (assetId: string, updates: Partial<Asset>) => void
  setAssetFilters: (filters: { type?: string | null; department?: string | null; status?: string | null }) => void

  // Classification actions
  setClassifications: (classifications: Classification[]) => void
  updateClassification: (id: string, updates: Partial<Classification>) => void
  setClassificationFilter: (department: string | null) => void

  // Weights actions
  setUserWeights: (weights: UserWeights) => void
  updateWeightPreset: (preset: UserWeights['preset']) => void

  // Search actions
  setSearchQuery: (query: string) => void

  // Connection and error actions
  setConnectionStatus: (status: 'connected' | 'connecting' | 'disconnected' | 'degraded', message?: string) => void
  setError: (error: string | null) => void
  clearError: () => void

  // Reset
  resetStore: () => void
}

// ============================================================================
// Default State
// ============================================================================

const defaultWeights: UserWeights = {
  preset: 'balanced',
  departments: {},
  recency: {
    enabled: true,
    last_30_days: 1.5,
    last_year: 1.0,
    older: 0.7
  },
  sourceTypes: {
    enabled: true,
    pdf: 1.0,
    video: 0.9,
    audio: 0.85,
    web: 0.8,
    notes: 0.7
  },
  confidence: {
    enabled: true,
    high: 1.2,
    medium: 1.0,
    low: 0.8
  },
  verified: {
    enabled: true,
    weight: 1.5
  }
}

const initialState = {
  activeSidebarPanel: null as SidebarPanel,
  activeSessionId: null,
  sessions: [],
  messages: [],
  isStreaming: false,
  streamingContent: '',
  connectionStatus: 'connected' as const,
  degradationMessage: null as string | null,
  lastError: null as string | null,
  pendingClarificationsCount: 0,
  hasOverdueClarifications: false,
  assets: [],
  assetTypeFilter: null,
  assetDepartmentFilter: null,
  assetStatusFilter: null,
  classifications: [],
  classificationDepartmentFilter: null,
  userWeights: defaultWeights,
  searchQuery: ''
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useAIStudioStore = create<AIStudioState>()(
  persist(
    (set) => ({
      ...initialState,

      // Sidebar panel actions
      setActiveSidebarPanel: (panel) => set({ activeSidebarPanel: panel }),

      toggleSidebarPanel: (panel) => set((state) => ({
        activeSidebarPanel: state.activeSidebarPanel === panel ? null : panel
      })),

      // Session actions
      setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

      setSessions: (sessions) => set({ sessions }),

      addSession: (session) => set((state) => ({
        sessions: [session, ...state.sessions]
      })),

      updateSession: (sessionId, updates) => set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId ? { ...s, ...updates } : s
        )
      })),

      deleteSession: (sessionId) => set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== sessionId),
        activeSessionId: state.activeSessionId === sessionId ? null : state.activeSessionId,
        messages: state.activeSessionId === sessionId ? [] : state.messages
      })),

      // Message actions
      setMessages: (messages) => set({ messages }),

      addMessage: (message) => set((state) => ({
        messages: [...state.messages, message]
      })),

      updateMessage: (messageId, updates) => set((state) => ({
        messages: state.messages.map((m) =>
          m.id === messageId ? { ...m, ...updates } : m
        )
      })),

      setStreaming: (isStreaming, content = '') => set({
        isStreaming,
        streamingContent: content
      }),

      // Clarification actions
      setPendingClarifications: (count, hasOverdue) => set({
        pendingClarificationsCount: count,
        hasOverdueClarifications: hasOverdue
      }),

      // Asset actions
      setAssets: (assets) => set({ assets }),

      addAsset: (asset) => set((state) => ({
        assets: [asset, ...state.assets]
      })),

      updateAsset: (assetId, updates) => set((state) => ({
        assets: state.assets.map((a) =>
          a.id === assetId ? { ...a, ...updates } : a
        )
      })),

      setAssetFilters: ({ type, department, status }) => set((state) => ({
        assetTypeFilter: type !== undefined ? type : state.assetTypeFilter,
        assetDepartmentFilter: department !== undefined ? department : state.assetDepartmentFilter,
        assetStatusFilter: status !== undefined ? status : state.assetStatusFilter
      })),

      // Classification actions
      setClassifications: (classifications) => set({ classifications }),

      updateClassification: (id, updates) => set((state) => ({
        classifications: state.classifications.map((c) =>
          c.id === id ? { ...c, ...updates } : c
        )
      })),

      setClassificationFilter: (department) => set({
        classificationDepartmentFilter: department
      }),

      // Weights actions
      setUserWeights: (weights) => set({ userWeights: weights }),

      updateWeightPreset: (preset) => set((state) => ({
        userWeights: { ...state.userWeights, preset }
      })),

      // Search actions
      setSearchQuery: (query) => set({ searchQuery: query }),

      // Connection and error actions
      setConnectionStatus: (status, message) => set({
        connectionStatus: status,
        degradationMessage: message || null
      }),

      setError: (error) => set({ lastError: error }),

      clearError: () => set({ lastError: null }),

      // Reset
      resetStore: () => set(initialState)
    }),
    {
      name: 'empire-ai-studio-storage',
      partialize: (state) => ({
        activeSidebarPanel: state.activeSidebarPanel,
        userWeights: state.userWeights,
        assetTypeFilter: state.assetTypeFilter,
        assetDepartmentFilter: state.assetDepartmentFilter,
        assetStatusFilter: state.assetStatusFilter,
        classificationDepartmentFilter: state.classificationDepartmentFilter
      })
    }
  )
)

// ============================================================================
// Selectors
// ============================================================================

export const selectFilteredAssets = (state: AIStudioState) => {
  let filtered = state.assets

  if (state.assetTypeFilter) {
    filtered = filtered.filter((a) => a.assetType === state.assetTypeFilter)
  }
  if (state.assetDepartmentFilter) {
    filtered = filtered.filter((a) => a.department === state.assetDepartmentFilter)
  }
  if (state.assetStatusFilter) {
    filtered = filtered.filter((a) => a.status === state.assetStatusFilter)
  }
  if (state.searchQuery) {
    const query = state.searchQuery.toLowerCase()
    filtered = filtered.filter((a) =>
      a.title.toLowerCase().includes(query) ||
      a.content.toLowerCase().includes(query)
    )
  }

  return filtered
}

export const selectFilteredClassifications = (state: AIStudioState) => {
  let filtered = state.classifications

  if (state.classificationDepartmentFilter) {
    filtered = filtered.filter((c) => c.department === state.classificationDepartmentFilter)
  }
  if (state.searchQuery) {
    const query = state.searchQuery.toLowerCase()
    filtered = filtered.filter((c) =>
      c.filename?.toLowerCase().includes(query) ||
      c.contentPreview?.toLowerCase().includes(query) ||
      c.department.toLowerCase().includes(query)
    )
  }

  return filtered
}

export const selectPendingClarificationMessages = (state: AIStudioState) => {
  return state.messages.filter(
    (m) => m.isClarification && m.clarificationStatus === 'pending'
  )
}

// ============================================================================
// Constants
// ============================================================================

export const DEPARTMENTS = [
  { id: 'it-engineering', label: 'IT & Engineering' },
  { id: 'sales-marketing', label: 'Sales & Marketing' },
  { id: 'customer-support', label: 'Customer Support' },
  { id: 'operations-hr-supply', label: 'Operations/HR/Supply' },
  { id: 'finance-accounting', label: 'Finance & Accounting' },
  { id: 'project-management', label: 'Project Management' },
  { id: 'real-estate', label: 'Real Estate' },
  { id: 'private-equity-ma', label: 'Private Equity & M&A' },
  { id: 'consulting', label: 'Consulting' },
  { id: 'personal-continuing-ed', label: 'Personal & Continuing Ed' },
  { id: 'research-development', label: 'Research & Development' },
  { id: '_global', label: 'Global' }
] as const

export const ASSET_TYPES = [
  { id: 'skill', label: 'Skill', format: 'yaml' },
  { id: 'command', label: 'Command', format: 'md' },
  { id: 'agent', label: 'Agent', format: 'yaml' },
  { id: 'prompt', label: 'Prompt', format: 'md' },
  { id: 'workflow', label: 'Workflow', format: 'json' }
] as const

export const WEIGHT_PRESETS = [
  { id: 'balanced', label: 'Balanced', description: 'Default weights for general use' },
  { id: 'recent-focus', label: 'Recent Focus', description: 'Prioritize documents from last 30 days' },
  { id: 'verified-only', label: 'Verified Only', description: 'Only use high-confidence, verified sources' },
  { id: 'custom', label: 'Custom', description: 'Your custom weight configuration' }
] as const
