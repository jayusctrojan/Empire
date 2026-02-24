/**
 * Session Memory API Client
 * Project memory management (accumulated knowledge + manual notes)
 */

import { get, post, patch, del } from './client'

// ============================================================================
// Types
// ============================================================================

export interface MemorySummary {
  id: string
  conversationId: string
  projectId: string | null
  summaryPreview: string
  tags: string[]
  createdAt: string
  updatedAt: string
}

export interface MemoryDetail {
  id: string
  conversationId: string
  projectId: string | null
  summary: string
  keyDecisions: Array<{ text: string; phrase?: string }>
  filesMentioned: Array<{ path: string; context?: string }>
  codePreserved: Array<{ language?: string; content: string }>
  tags: string[]
  retentionType: string
  createdAt: string
  updatedAt: string
  expiresAt: string | null
}

interface MemoryListResponse {
  success: boolean
  memories: Array<{
    id: string
    conversation_id: string
    project_id: string | null
    summary_preview: string
    tags: string[]
    created_at: string
    updated_at: string
  }>
  total: number
}

interface MemoryDetailResponse {
  success: boolean
  memory: {
    id: string
    conversation_id: string
    project_id: string | null
    summary: string
    key_decisions: Array<{ text: string; phrase?: string }>
    files_mentioned: Array<{ path: string; context?: string }>
    code_preserved: Array<{ language?: string; content: string }>
    tags: string[]
    retention_type: string
    created_at: string
    updated_at: string
    expires_at: string | null
  } | null
}

interface SaveNoteResponse {
  success: boolean
  memory_id: string | null
  summary_preview: string | null
}

// ============================================================================
// Helpers — snake_case → camelCase
// ============================================================================

function toMemorySummary(raw: MemoryListResponse['memories'][number]): MemorySummary {
  return {
    id: raw.id,
    conversationId: raw.conversation_id,
    projectId: raw.project_id,
    summaryPreview: raw.summary_preview,
    tags: raw.tags ?? [],
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  }
}

function toMemoryDetail(raw: NonNullable<MemoryDetailResponse['memory']>): MemoryDetail {
  return {
    id: raw.id,
    conversationId: raw.conversation_id,
    projectId: raw.project_id,
    summary: raw.summary,
    keyDecisions: raw.key_decisions ?? [],
    filesMentioned: raw.files_mentioned ?? [],
    codePreserved: raw.code_preserved ?? [],
    tags: raw.tags ?? [],
    retentionType: raw.retention_type,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    expiresAt: raw.expires_at,
  }
}

// ============================================================================
// API Functions
// ============================================================================

export async function getProjectMemories(
  projectId: string,
  limit = 10,
  offset = 0,
): Promise<{ memories: MemorySummary[]; total: number }> {
  const params: Record<string, string> = { limit: String(limit) }
  if (offset > 0) params.offset = String(offset)
  const res = await get<MemoryListResponse>(
    `/api/session-memory/project/${projectId}`,
    params,
  )
  return {
    memories: (res.memories ?? []).map(toMemorySummary),
    total: res.total ?? 0,
  }
}

export async function getMemoryDetail(memoryId: string): Promise<MemoryDetail | null> {
  const res = await get<MemoryDetailResponse>(`/api/session-memory/${memoryId}`)
  return res.memory ? toMemoryDetail(res.memory) : null
}

export async function updateMemory(
  memoryId: string,
  updates: { summary?: string; tags?: string[]; retentionType?: string },
): Promise<MemoryDetail | null> {
  const body: Record<string, unknown> = {}
  if (updates.summary !== undefined) body.summary = updates.summary
  if (updates.tags !== undefined) body.tags = updates.tags
  if (updates.retentionType !== undefined) body.retention_type = updates.retentionType
  const res = await patch<MemoryDetailResponse>(`/api/session-memory/${memoryId}`, body)
  return res.memory ? toMemoryDetail(res.memory) : null
}

export async function deleteMemory(memoryId: string): Promise<void> {
  await del<{ success: boolean }>(`/api/session-memory/${memoryId}`)
}

export async function addMemoryNote(
  projectId: string,
  content: string,
  tags?: string[],
): Promise<{ memoryId: string | null }> {
  const res = await post<SaveNoteResponse>('/api/session-memory/note', {
    project_id: projectId,
    content,
    tags,
  })
  return { memoryId: res.memory_id }
}

export async function searchMemories(
  query: string,
  projectId?: string,
  limit = 10,
): Promise<{ memories: MemorySummary[]; total: number }> {
  const body: Record<string, unknown> = { query, limit }
  if (projectId) body.project_id = projectId
  const res = await post<MemoryListResponse>('/api/session-memory/search', body)
  return {
    memories: (res.memories ?? []).map(toMemorySummary),
    total: res.total ?? 0,
  }
}
