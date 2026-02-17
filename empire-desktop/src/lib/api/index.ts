/**
 * Empire API Client
 * Unified export for all API modules
 */

// Imports for internal use (globalSearch function)
import { listCKOSessions as _listCKOSessions } from './cko'
import { listAssets as _listAssets } from './assets'
import { listClassifications as _listClassifications } from './classifications'

// Core client
export { apiRequest, get, post, postFormData, del, getApiBaseUrl, EmpireAPIError } from './client'

// Projects API (cloud-persisted)
export {
  listProjects,
  getProject,
  createProject as createRemoteProject,
  updateProject as updateRemoteProject,
  deleteProject as deleteRemoteProject,
  syncProjects,
  type APIProject,
  type CreateProjectRequest,
  type UpdateProjectRequest,
  type CreateProjectResponse,
  type GetProjectResponse,
  type ListProjectsResponse,
  type UpdateProjectResponse,
  type DeleteProjectResponse,
} from './projects'

// Documents API
export {
  uploadDocuments,
  listDocuments,
  getDocument,
  deleteDocument,
  getDocumentDownloadUrl,
} from './documents'

// Project Sources API
export {
  listSources,
  getSource,
  addFileSources,
  addUrlSources,
  deleteSource,
  retrySource,
  getCapacity,
  detectUrlType,
  isValidUrl,
  type SourceSortField,
  type SortOrder,
} from './sources'

// Query API (streaming)
export { queryStream, query, collectStreamResponse } from './query'

// WebSocket Chat
export {
  ChatWebSocketClient,
  getChatClient,
  disconnectChatClient,
  type ConnectionState,
  type ChatClientHandlers,
} from './websocket'

// Conversations API (cloud-persisted chat history)
export {
  listConversations as apiListConversations,
  getConversation as apiGetConversation,
  createConversation as createRemoteConversation,
  updateConversation as updateRemoteConversation,
  deleteConversation as deleteRemoteConversation,
  listMessages as apiListMessages,
  createMessage as createRemoteMessage,
  updateMessage as updateRemoteMessage,
  syncConversations,
  type APIConversation,
  type APIConversationSummary,
  type APIMessage,
  type CreateConversationRequest,
  type UpdateConversationRequest,
  type CreateMessageRequest,
  type UpdateMessageRequest,
  type MessageRole,
} from './conversations'

// CKO Conversation API (AI Studio)
export {
  createCKOSession,
  getCKOSession,
  listCKOSessions,
  deleteCKOSession,
  updateCKOSession,
  getCKOMessages,
  sendCKOMessage,
  streamCKOMessage,
  rateCKOMessage,
  answerCKOClarification,
  skipCKOClarification,
  getPendingClarificationsCount,
  type CKOSession,
  type CKOMessage,
  type CKOSource,
  type CKOAction,
  type CKOStreamChunk,
  type CKOConfig,
  type CKOMessageRequest,
  type CKOSessionCreate,
} from './cko'

// Assets API (AI Studio)
export {
  listAssets,
  getAsset,
  updateAsset,
  publishAsset,
  archiveAsset,
  getAssetHistory,
  reclassifyAsset,
  getAssetStats,
  getAssetHealth,
  ASSET_TYPE_CONFIG,
  DEPARTMENTS,
  type Asset,
  type AssetType,
  type AssetStatus,
  type AssetFormat,
  type AssetVersion,
  type AssetFilters,
  type AssetListResponse,
  type AssetHistoryResponse,
  type AssetStatsResponse,
  type AssetUpdateRequest,
  type AssetReclassifyRequest,
} from './assets'

// Classifications API (AI Studio)
export {
  listClassifications,
  getClassification,
  correctClassification,
  getClassificationStats,
  getClassificationHealth,
  getConfidenceLevel,
  getConfidenceColor,
  getConfidenceBadgeColor,
  getDepartmentLabel,
  DEPARTMENTS as CLASSIFICATION_DEPARTMENTS,
  type Classification,
  type ClassificationFilters,
  type ClassificationListResponse,
  type ClassificationStatsResponse,
  type ClassificationCorrectionRequest,
  type ConfidenceLevel,
} from './classifications'

// Feedback API (AI Studio)
export {
  listFeedback,
  getFeedback,
  submitFeedback,
  getFeedbackStats,
  getFeedbackImpact,
  getFeedbackSummary,
  getFeedbackTypes,
  getFeedbackHealth,
  getFeedbackTypeLabel,
  getRatingLabel,
  getRatingIcon,
  getRatingColor,
  getRatingBadgeColor,
  getTrendIcon,
  getTrendColor,
  FEEDBACK_TYPES,
  type Feedback,
  type FeedbackType,
  type FeedbackFilters,
  type FeedbackListResponse,
  type FeedbackStatsResponse,
  type FeedbackImpact,
  type FeedbackImpactListResponse,
  type FeedbackSummaryResponse,
  type FeedbackSubmitRequest,
  type FeedbackTypeInfo,
  type RatingValue,
} from './feedback'

// Compaction API (Task 209 - Context Window Management)
export {
  triggerCompaction,
  triggerAsyncCompaction,
  getCompactionProgress,
  getCompactionHistory,
  getTaskProgress,
  cancelCompactionTask,
  type TriggerCompactionRequest,
  type CompactionLogEntry,
  type CompactionResultResponse,
  type CompactionHistoryResponse,
  type CompactionProgressResponse,
} from './compaction'

// Error Recovery API (Task 210 - Automatic Error Recovery)
export {
  isContextOverflowError,
  triggerRecovery,
  getRecoveryProgress,
  sendWithRecovery,
  type RecoveryResponse,
  type RecoveryProgressResponse,
} from './compaction'

// Organizations API
export {
  listOrganizations,
  getOrganization,
  createOrganization,
  updateOrganization,
  listMembers,
  addMember,
  removeMember,
  exportOrganization,
  type CreateOrgRequest,
  type UpdateOrgRequest,
  type AddMemberRequest,
  type OrgMember,
} from './organizations'

// Artifacts API (Document Generation)
export {
  getArtifact,
  listArtifacts,
  deleteArtifact,
  downloadArtifact,
  type ArtifactListResponse,
} from './artifacts'

// Health check
import { get } from './client'
import type { HealthResponse } from '@/types'

export async function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>('/api/health')
}

// Global Search API (AI Studio)
export interface GlobalSearchResult {
  id: string
  type: 'session' | 'asset' | 'classification' | 'document'
  title: string
  snippet: string
  department?: string
  date: string
  metadata?: {
    sessionId?: string
    messageId?: string
    assetType?: string
    confidence?: number
    status?: string
  }
}

export interface GlobalSearchResponse {
  results: GlobalSearchResult[]
  total: number
}

export async function globalSearch(
  query: string,
  options?: {
    types?: Array<'session' | 'asset' | 'classification' | 'document'>
    limit?: number
  }
): Promise<GlobalSearchResponse> {
  if (!query || query.length < 2) {
    return { results: [], total: 0 }
  }

  const results: GlobalSearchResult[] = []

  const typesToSearch = options?.types || ['session', 'asset', 'classification']
  const limit = options?.limit || 20

  try {
    // Search in parallel across all types
    const searchPromises: Promise<void>[] = []

    if (typesToSearch.includes('session')) {
      searchPromises.push(
        _listCKOSessions({ limit: 50 }).then(sessions => {
          // Client-side filtering since sessions API doesn't support search
          const queryLower = query.toLowerCase()
          sessions
            .filter(s =>
              (s.title && s.title.toLowerCase().includes(queryLower)) ||
              (s.context_summary && s.context_summary.toLowerCase().includes(queryLower))
            )
            .slice(0, 10)
            .forEach(s => {
              results.push({
                id: s.id,
                type: 'session',
                title: s.title || 'Untitled Conversation',
                snippet: s.context_summary || `${s.message_count} messages`,
                date: s.last_message_at || s.created_at,
                metadata: { sessionId: s.id }
              })
            })
        }).catch(console.error)
      )
    }

    if (typesToSearch.includes('asset')) {
      searchPromises.push(
        _listAssets({ search: query }, 0, 10).then(response => {
          response.assets.forEach(a => {
            results.push({
              id: a.id,
              type: 'asset',
              title: a.title,
              snippet: a.content.substring(0, 150) + (a.content.length > 150 ? '...' : ''),
              department: a.department,
              date: a.updatedAt || a.createdAt || '',
              metadata: {
                assetType: a.assetType,
                status: a.status
              }
            })
          })
        }).catch(console.error)
      )
    }

    if (typesToSearch.includes('classification')) {
      searchPromises.push(
        _listClassifications({ search: query }, 0, 10).then(response => {
          response.classifications.forEach(c => {
            results.push({
              id: c.id,
              type: 'classification',
              title: c.filename || 'Untitled',
              snippet: c.contentPreview || c.reasoning || '',
              department: c.department,
              date: c.createdAt || '',
              metadata: {
                confidence: c.confidence
              }
            })
          })
        }).catch(console.error)
      )
    }

    await Promise.all(searchPromises)

    // Sort by date (most recent first)
    results.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

    return {
      results: results.slice(0, limit),
      total: results.length
    }
  } catch (error) {
    console.error('Global search error:', error)
    return { results: [], total: 0 }
  }
}
