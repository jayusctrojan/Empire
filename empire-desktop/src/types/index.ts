// Core Empire Desktop Types

// Re-export API types
export * from './api'

// User & Authentication
export interface User {
  id: string
  email: string
  name: string
  avatarUrl?: string
  createdAt: Date
  lastLoginAt: Date
}

// Chat & Messages
export interface Message {
  id: string
  conversationId: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  artifacts?: Artifact[]
  createdAt: Date
  updatedAt: Date
  status: 'sending' | 'streaming' | 'complete' | 'error'
  // Response metadata (for KB mode)
  rating?: -1 | 0 | 1
  ratingFeedback?: string
  workflow?: string
  agent?: string
  department?: string
  isKBResponse?: boolean
  // Context window protection (Feature 011)
  isProtected?: boolean
  // Pipeline metadata
  pipelineMode?: 'full' | 'no_prompt_engineer' | 'no_output_architect' | 'direct'
}

// Document Artifacts
export type ArtifactFormat = 'docx' | 'xlsx' | 'pptx' | 'pdf' | 'md'
export type ArtifactStatus = 'uploading' | 'ready' | 'error'

export interface Artifact {
  id: string
  messageId?: string
  sessionId: string
  title: string
  format: ArtifactFormat
  mimeType: string
  sizeBytes: number
  storageUrl?: string
  previewMarkdown?: string
  summary?: string
  status: ArtifactStatus
  createdAt?: string
}

export interface Source {
  id: string
  documentId: string
  documentTitle: string
  pageNumber?: number
  excerpt: string
  relevanceScore: number
}

export interface Conversation {
  id: string
  projectId?: string
  title: string
  createdAt: Date
  updatedAt: Date
  messageCount: number
  lastMessageAt?: Date
}

// Projects
export interface Project {
  id: string
  name: string
  description?: string
  department: Department
  instructions?: string
  createdAt: Date
  updatedAt: Date
  conversationCount: number
  fileCount?: number
  memoryContext?: string
  // Cloud-synced source counts from Supabase
  sourceCount?: number
  readySourceCount?: number
}

// Project Files
export interface ProjectFile {
  id: string
  name: string
  size: number
  type: string
  uploadedAt: Date
}

// Project Sources (NotebookLM-style)
export type SourceType = 'file' | 'url' | 'youtube'
export type SourceStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface ProjectSource {
  id: string
  projectId: string
  title: string
  sourceType: SourceType
  url?: string
  filePath?: string
  fileName?: string
  fileSize?: number
  mimeType?: string
  status: SourceStatus
  processingProgress: number
  processingError?: string
  retryCount: number
  summary?: string
  metadata?: {
    duration?: string       // YouTube video duration
    channel?: string        // YouTube channel
    author?: string         // Web article author
    publishDate?: string    // Publish date
    pageCount?: number      // PDF page count
    thumbnailUrl?: string   // YouTube thumbnail
    chapters?: Array<{ title: string; timestamp: string }>
  }
  createdAt: Date
  updatedAt: Date
}

// Source status update event (WebSocket)
export interface SourceStatusUpdate {
  type: 'source_status'
  sourceId: string
  projectId: string
  status: SourceStatus
  progress: number
  error?: string
}

export type Department =
  | 'IT & Engineering'
  | 'Sales & Marketing'
  | 'Customer Support'
  | 'Operations & HR & Supply Chain'
  | 'Finance & Accounting'
  | 'Project Management'
  | 'Real Estate'
  | 'Private Equity & M&A'
  | 'Consulting'
  | 'Personal & Continuing Education'

// Settings
export interface Settings {
  theme: 'dark' | 'light' | 'system'
  fontSize: 'small' | 'medium' | 'large'
  keyboardShortcutsEnabled: boolean
  apiEndpoint: string
}

// API Response Types
export interface StreamingResponse {
  type: 'token' | 'source' | 'done' | 'error'
  content?: string
  source?: Source
  error?: string
}

// MCP Types (for future phases)
export interface MCPServer {
  id: string
  name: string
  status: 'connected' | 'disconnected' | 'error'
  capabilities: string[]
}

// Context Window Types (Feature 011)
export type ContextStatus = 'normal' | 'warning' | 'critical'

export interface ContextWindowStatus {
  conversationId: string
  currentTokens: number
  maxTokens: number
  reservedTokens: number
  thresholdPercent: number
  usagePercent: number
  status: ContextStatus
  availableTokens: number
  estimatedMessagesRemaining: number
  isCompacting: boolean
  lastCompactionAt?: Date
  lastUpdated: Date
}

// Context Window WebSocket update event
export interface ContextWindowUpdate {
  type: 'context_status_update'
  data: ContextWindowStatus
}

// Compaction Event Types (Feature 011 - Task 204)
export type CompactionTrigger = 'auto' | 'manual' | 'force' | 'threshold' | 'error_recovery'

export interface CompactionEvent {
  id: string
  conversationId: string
  preTokens: number
  postTokens: number
  reductionPercent: number
  messagesCondensed: number
  summary: string
  summaryPreview?: string
  trigger: CompactionTrigger
  timestamp: Date
  durationMs?: number
}

// Compaction WebSocket update event
export interface CompactionUpdate {
  type: 'compaction_started' | 'compaction_completed'
  data: CompactionEvent | { conversationId: string }
}
