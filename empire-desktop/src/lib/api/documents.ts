/**
 * Documents API
 * Endpoints for document upload and management
 */

import { get, postFormData, del } from './client'
import type {
  DocumentMetadata,
  DocumentListResponse,
  ListDocumentsParams,
  UploadResult,
} from '@/types'

/**
 * Upload documents to Empire backend
 */
export async function uploadDocuments(files: File[]): Promise<UploadResult[]> {
  const formData = new FormData()

  for (const file of files) {
    formData.append('files', file)
  }

  const response = await postFormData<{ results: UploadResult[] }>(
    '/api/documents/upload',
    formData
  )

  return response.results
}

/**
 * List documents with optional filters
 */
export async function listDocuments(params?: ListDocumentsParams): Promise<DocumentListResponse> {
  const queryParams: Record<string, string> = {}

  if (params?.projectId) {
    queryParams.project_id = params.projectId
  }
  if (params?.status) {
    queryParams.status = params.status
  }
  if (params?.limit !== undefined) {
    queryParams.limit = String(params.limit)
  }
  if (params?.offset !== undefined) {
    queryParams.offset = String(params.offset)
  }

  return get<DocumentListResponse>('/api/documents', queryParams)
}

/**
 * Get single document metadata
 */
export async function getDocument(documentId: string): Promise<DocumentMetadata> {
  return get<DocumentMetadata>(`/api/documents/${documentId}`)
}

/**
 * Delete a document
 */
export async function deleteDocument(documentId: string): Promise<void> {
  await del<void>(`/api/documents/${documentId}`)
}

/**
 * Get document download URL
 */
export async function getDocumentDownloadUrl(documentId: string): Promise<string> {
  const response = await get<{ url: string }>(`/api/documents/${documentId}/download`)
  return response.url
}
