/**
 * Empire API Client
 * Unified export for all API modules
 */

// Core client
export { apiRequest, get, post, patch, postFormData, del, getApiBaseUrl, EmpireAPIError } from './client'

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
  testAssetStream,
  ASSET_TYPE_CONFIG,
  ASSET_STATUS_CONFIG,
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
  type AssetTestStreamChunk,
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

// Unified Search API
export {
  unifiedSearch,
  type SearchContentType,
  type SearchResultItem,
  type UnifiedSearchResponse,
} from './search'

// Health check
import { get } from './client'
import type { HealthResponse } from '@/types'

export async function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>('/api/health')
}

