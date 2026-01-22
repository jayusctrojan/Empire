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
  createdAt: Date
  updatedAt: Date
  status: 'sending' | 'streaming' | 'complete' | 'error'
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
  memoryContext?: string
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
