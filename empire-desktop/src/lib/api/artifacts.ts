/**
 * Artifacts API
 * Download and manage generated document artifacts
 */

import { fetch } from '@tauri-apps/plugin-http'
import { save } from '@tauri-apps/plugin-dialog'
import { writeFile } from '@tauri-apps/plugin-fs'
import { get, del, getApiBaseUrl } from './client'
import { useAuthStore } from '@/stores/auth'
import { useOrgStore } from '@/stores/org'
import type { Artifact, ArtifactFormat } from '@/types'

// ============================================================================
// Types
// ============================================================================

export interface ArtifactListResponse {
  artifacts: Artifact[]
  total: number
}

// ============================================================================
// API Functions
// ============================================================================

export async function getArtifact(id: string): Promise<Artifact> {
  return get<Artifact>(`/api/studio/artifacts/${id}`)
}

export async function listArtifacts(options?: {
  sessionId?: string
  format?: ArtifactFormat
}): Promise<ArtifactListResponse> {
  const params: Record<string, string> = {}
  if (options?.sessionId) params.session_id = options.sessionId
  if (options?.format) params.format = options.format
  return get<ArtifactListResponse>('/api/studio/artifacts', params)
}

export async function deleteArtifact(id: string): Promise<void> {
  return del<void>(`/api/studio/artifacts/${id}`)
}

/**
 * Download an artifact file via Tauri save dialog.
 * Fetches the binary from the API and writes it to the user-selected path.
 */
export async function downloadArtifact(artifact: Artifact, format?: ArtifactFormat): Promise<void> {
  const baseUrl = getApiBaseUrl()
  const params = format && format !== artifact.format ? `?format=${format}` : ''
  const url = `${baseUrl}/api/studio/artifacts/${artifact.id}/download${params}`

  const token = useAuthStore.getState().jwt
  const currentOrg = useOrgStore.getState().currentOrg

  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (currentOrg) headers['X-Org-Id'] = currentOrg.id

  const response = await fetch(url, { method: 'GET', headers })

  if (!response.ok) {
    throw new Error(`Download failed: ${response.status} ${response.statusText}`)
  }

  const blob = await response.blob()
  const arrayBuffer = await blob.arrayBuffer()
  const bytes = new Uint8Array(arrayBuffer)

  // Determine file extension
  const ext = format || artifact.format
  const defaultName = `${artifact.title.replace(/[^a-zA-Z0-9_\- ]/g, '')}.${ext}`

  // Tauri save dialog
  const filePath = await save({
    defaultPath: defaultName,
    filters: [{
      name: ext.toUpperCase(),
      extensions: [ext],
    }],
  })

  if (filePath) {
    await writeFile(filePath, bytes)
  }
}
