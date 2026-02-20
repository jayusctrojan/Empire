/**
 * Assets API
 * AI Studio asset management (prompts, agents, workflows, etc.)
 */

import { get, post, patch, getApiBaseUrl } from './client'
import { useAuthStore } from '@/stores/auth'
import { useOrgStore } from '@/stores/org'
import { fetch } from '@tauri-apps/plugin-http'

// Types
export type AssetType = 'skill' | 'command' | 'agent' | 'prompt' | 'workflow'
export type AssetStatus = 'draft' | 'published' | 'archived'
export type AssetFormat = 'yaml' | 'md' | 'json'

export interface Asset {
  id: string
  assetType: AssetType
  department: string
  name: string
  title: string
  content: string
  format: AssetFormat
  status: AssetStatus
  sourceDocumentId?: string
  sourceDocumentTitle?: string
  classificationConfidence?: number
  classificationReasoning?: string
  version: number
  createdAt?: string
  updatedAt?: string
}

export interface AssetVersion {
  id: string
  version: number
  content: string
  createdAt: string
  createdBy?: string
  isCurrent: boolean
}

export interface AssetFilters {
  assetType?: AssetType
  department?: string
  status?: AssetStatus
  search?: string
}

export interface AssetListResponse {
  assets: Asset[]
  total: number
  limit: number
  skip: number
}

export interface AssetHistoryResponse {
  asset: Asset
  history: AssetVersion[]
}

export interface AssetStatsResponse {
  total: number
  byType: Record<AssetType, number>
  byDepartment: Record<string, number>
  byStatus: Record<AssetStatus, number>
}

export interface AssetUpdateRequest {
  title?: string
  content?: string
  format?: AssetFormat
  department?: string
}

export interface AssetReclassifyRequest {
  newType: AssetType
  newDepartment?: string
  reason?: string
}

// Department configuration
export const DEPARTMENTS = [
  { value: 'it-engineering', label: 'IT & Engineering' },
  { value: 'sales-marketing', label: 'Sales & Marketing' },
  { value: 'customer-support', label: 'Customer Support' },
  { value: 'operations-hr-supply', label: 'Operations & HR & Supply Chain' },
  { value: 'finance-accounting', label: 'Finance & Accounting' },
  { value: 'project-management', label: 'Project Management' },
  { value: 'real-estate', label: 'Real Estate' },
  { value: 'private-equity-ma', label: 'Private Equity & M&A' },
  { value: 'consulting', label: 'Consulting' },
  { value: 'personal-continuing-ed', label: 'Personal & Continuing Education' },
]

export const ASSET_TYPE_CONFIG = {
  skill: { label: 'Skill', icon: '⚡', color: 'blue' },
  command: { label: 'Command', icon: '📟', color: 'green' },
  agent: { label: 'Agent', icon: '🤖', color: 'purple' },
  prompt: { label: 'Prompt', icon: '💬', color: 'yellow' },
  workflow: { label: 'Workflow', icon: '🔄', color: 'orange' },
}

export const ASSET_STATUS_CONFIG = {
  draft: { label: 'Draft', color: 'amber' },
  published: { label: 'Published', color: 'green' },
  archived: { label: 'Archived', color: 'gray' },
}

// Stream chunk type for asset testing
export interface AssetTestStreamChunk {
  type: 'start' | 'phase' | 'sources' | 'token' | 'artifact' | 'done' | 'error'
  phase?: 'analyzing' | 'searching' | 'reasoning' | 'formatting'
  label?: string
  content?: string
  message?: Record<string, unknown>
  query_time_ms?: number
  pipeline_mode?: string
  error?: string
  // Artifact fields
  id?: string
  title?: string
  format?: string
  mimeType?: string
  sizeBytes?: number
  previewMarkdown?: string
  status?: string
}

// API Functions

export async function listAssets(
  filters?: AssetFilters,
  skip = 0,
  limit = 20
): Promise<AssetListResponse> {
  const params = new URLSearchParams()
  if (filters?.assetType) params.set('asset_type', filters.assetType)
  if (filters?.department) params.set('department', filters.department)
  if (filters?.status) params.set('status', filters.status)
  if (filters?.search) params.set('search', filters.search)
  params.set('skip', String(skip))
  params.set('limit', String(limit))
  return get<AssetListResponse>(`/api/studio/assets?${params.toString()}`)
}

export async function getAsset(assetId: string): Promise<Asset> {
  return get<Asset>(`/api/studio/assets/${assetId}`)
}

export async function updateAsset(assetId: string, updates: AssetUpdateRequest): Promise<Asset> {
  return patch<Asset>(`/api/studio/assets/${assetId}`, updates)
}

export async function publishAsset(assetId: string): Promise<Asset> {
  return post<Asset>(`/api/studio/assets/${assetId}/publish`, {})
}

export async function archiveAsset(assetId: string): Promise<Asset> {
  return post<Asset>(`/api/studio/assets/${assetId}/archive`, {})
}

export async function getAssetHistory(assetId: string): Promise<AssetHistoryResponse> {
  return get<AssetHistoryResponse>(`/api/studio/assets/${assetId}/history`)
}

export async function reclassifyAsset(assetId: string, request: AssetReclassifyRequest): Promise<Asset> {
  return post<Asset>(`/api/studio/assets/${assetId}/reclassify`, request)
}

export async function getAssetStats(): Promise<AssetStatsResponse> {
  return get<AssetStatsResponse>('/api/studio/assets/stats')
}

export async function getAssetHealth(): Promise<{ status: string; issues: string[] }> {
  return get('/api/studio/assets/health')
}

/**
 * Stream an asset test through the CKO pipeline with asset context injected.
 * Returns SSE events: phase, token, artifact, done, error.
 */
export async function* testAssetStream(
  assetId: string,
  query: string,
  signal?: AbortSignal
): AsyncGenerator<AssetTestStreamChunk> {
  const baseUrl = getApiBaseUrl()
  const url = `${baseUrl}/api/studio/assets/${assetId}/test`

  const token = useAuthStore.getState().jwt
  const currentOrg = useOrgStore.getState().currentOrg

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (currentOrg) headers['X-Org-Id'] = currentOrg.id

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Asset test stream failed: ${response.status} ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let eventData = ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        // event type line — next data line will follow
      } else if (line.startsWith('data: ')) {
        eventData += (eventData ? '\n' : '') + line.slice(6)
      } else if (line === '' && eventData) {
        try {
          const chunk = JSON.parse(eventData) as AssetTestStreamChunk
          yield chunk
        } catch {
          // Ignore malformed JSON
        }
        eventData = ''
      }
    }
  }

  // Flush any remaining buffered event
  if (buffer.trim()) {
    const remaining = buffer.split('\n')
    let eventData = ''
    for (const line of remaining) {
      if (line.startsWith('data: ')) {
        eventData += (eventData ? '\n' : '') + line.slice(6)
      } else if (line === '' && eventData) {
        try {
          yield JSON.parse(eventData) as AssetTestStreamChunk
        } catch { /* ignore */ }
        eventData = ''
      }
    }
    if (eventData) {
      try {
        yield JSON.parse(eventData) as AssetTestStreamChunk
      } catch { /* ignore */ }
    }
  }
}
