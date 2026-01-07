import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Sparkles,
  Package,
  Tags,
  Scale,
  MessageSquareHeart,
  Send,
  Loader2,
  Bot,
  User,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  X,
  Plus,
  ChevronDown,
  ChevronUp,
  FileText,
  Edit3,
  Archive,
  Upload,
  History,
  RefreshCw,
  Search,
  Save,
  TrendingUp,
  TrendingDown,
  Minus,
  Filter,
  Trash2,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Wifi,
  WifiOff,
  AlertTriangle,
  RotateCcw
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAIStudioStore, DEPARTMENTS, ASSET_TYPES, type SidebarPanel, type CKOMessage } from '@/stores/aistudio'
import {
  createCKOSession,
  getCKOMessages,
  streamCKOMessage,
  rateCKOMessage,
  answerCKOClarification,
  skipCKOClarification,
  getPendingClarificationsCount,
  listCKOSessions,
  deleteCKOSession,
  listAssets,
  getAsset,
  updateAsset,
  publishAsset,
  archiveAsset,
  reclassifyAsset,
  getAssetHistory,
  ASSET_TYPE_CONFIG,
  type Asset,
  type AssetType,
  type AssetVersion,
  listClassifications,
  getClassification,
  correctClassification,
  getClassificationStats,
  getConfidenceLevel,
  getConfidenceBadgeColor,
  getDepartmentLabel,
  CLASSIFICATION_DEPARTMENTS,
  type Classification,
  type ClassificationStatsResponse,
  // Feedback API
  listFeedback,
  submitFeedback,
  getFeedbackStats,
  getFeedbackSummary,
  getTrendColor,
  getFeedbackTypeLabel,
  FEEDBACK_TYPES,
  type Feedback,
  type FeedbackType,
  type FeedbackStatsResponse,
  type FeedbackSummaryResponse,
  // Global Search API
  globalSearch,
  type GlobalSearchResult
} from '@/lib/api'

// ============================================================================
// Global Search Component
// ============================================================================

interface GlobalSearchProps {
  isOpen: boolean
  onClose: () => void
  onNavigate: (result: GlobalSearchResult) => void
}

function GlobalSearch({ isOpen, onClose, onNavigate }: GlobalSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GlobalSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [activeFilter, setActiveFilter] = useState<'all' | 'session' | 'asset' | 'classification'>('all')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
    if (!isOpen) {
      setQuery('')
      setResults([])
      setSelectedIndex(0)
    }
  }, [isOpen])

  // Search when query changes
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults([])
      return
    }

    const searchTimeout = setTimeout(async () => {
      setIsLoading(true)
      try {
        const types = activeFilter === 'all'
          ? ['session', 'asset', 'classification'] as const
          : [activeFilter] as const
        const response = await globalSearch(query, { types: [...types], limit: 20 })
        setResults(response.results)
        setSelectedIndex(0)
      } catch (error) {
        console.error('Search failed:', error)
      } finally {
        setIsLoading(false)
      }
    }, 300)

    return () => clearTimeout(searchTimeout)
  }, [query, activeFilter])

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => Math.min(prev + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      e.preventDefault()
      onNavigate(results[selectedIndex])
      onClose()
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  const getTypeIcon = (type: GlobalSearchResult['type']) => {
    switch (type) {
      case 'session': return <MessageSquare className="w-4 h-4" />
      case 'asset': return <Package className="w-4 h-4" />
      case 'classification': return <Tags className="w-4 h-4" />
      case 'document': return <FileText className="w-4 h-4" />
    }
  }

  const getTypeColor = (type: GlobalSearchResult['type']) => {
    switch (type) {
      case 'session': return 'text-blue-400 bg-blue-500/10'
      case 'asset': return 'text-purple-400 bg-purple-500/10'
      case 'classification': return 'text-yellow-400 bg-yellow-500/10'
      case 'document': return 'text-green-400 bg-green-500/10'
    }
  }

  const formatDate = (dateStr: string) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString()
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-empire-bg border border-empire-border rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Header */}
        <div className="flex items-center gap-3 p-4 border-b border-empire-border">
          <Search className="w-5 h-5 text-empire-text-muted" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search conversations, assets, classifications..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-empire-text placeholder:text-empire-text-muted outline-none text-lg"
          />
          <kbd className="px-2 py-1 text-xs text-empire-text-muted bg-empire-card rounded border border-empire-border">
            ESC
          </kbd>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 p-2 border-b border-empire-border bg-empire-card/50">
          {(['all', 'session', 'asset', 'classification'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={cn(
                'px-3 py-1.5 text-xs rounded-lg transition-colors capitalize',
                activeFilter === filter
                  ? 'bg-empire-primary text-white'
                  : 'text-empire-text-muted hover:text-empire-text hover:bg-empire-border'
              )}
            >
              {filter === 'all' ? 'All' : filter === 'session' ? 'Conversations' : filter === 'asset' ? 'Assets' : 'Classifications'}
            </button>
          ))}
        </div>

        {/* Results */}
        <div className="max-h-[400px] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-empire-primary" />
            </div>
          ) : results.length > 0 ? (
            <div className="p-2">
              {results.map((result, index) => (
                <button
                  key={`${result.type}-${result.id}`}
                  onClick={() => {
                    onNavigate(result)
                    onClose()
                  }}
                  className={cn(
                    'w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors',
                    index === selectedIndex
                      ? 'bg-empire-primary/10 border border-empire-primary/20'
                      : 'hover:bg-empire-card'
                  )}
                >
                  <div className={cn('p-2 rounded-lg', getTypeColor(result.type))}>
                    {getTypeIcon(result.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-empire-text truncate">{result.title}</p>
                      {result.metadata?.status && (
                        <span className={cn(
                          'px-1.5 py-0.5 text-xs rounded',
                          result.metadata.status === 'published' && 'bg-green-500/20 text-green-400',
                          result.metadata.status === 'draft' && 'bg-yellow-500/20 text-yellow-400',
                          result.metadata.status === 'archived' && 'bg-gray-500/20 text-gray-400'
                        )}>
                          {result.metadata.status}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-empire-text-muted line-clamp-1 mt-0.5">{result.snippet}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-empire-text-muted">
                      <span className="capitalize">{result.type}</span>
                      {result.department && <span>{result.department}</span>}
                      {result.date && <span>{formatDate(result.date)}</span>}
                      {result.metadata?.confidence !== undefined && (
                        <span>{Math.round(result.metadata.confidence * 100)}% confidence</span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : query.length >= 2 ? (
            <div className="flex flex-col items-center justify-center py-12 text-empire-text-muted">
              <Search className="w-8 h-8 mb-2 opacity-50" />
              <p>No results found for "{query}"</p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-empire-text-muted">
              <Search className="w-8 h-8 mb-2 opacity-50" />
              <p>Type at least 2 characters to search</p>
              <p className="text-xs mt-2">Search across conversations, assets, and classifications</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-empire-border bg-empire-card/50 text-xs text-empire-text-muted">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-empire-border rounded">↑</kbd>
              <kbd className="px-1.5 py-0.5 bg-empire-border rounded">↓</kbd>
              to navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-empire-border rounded">↵</kbd>
              to select
            </span>
          </div>
          <span>{results.length} result{results.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// Sidebar Panel Components
// ============================================================================

// Asset Detail Modal Component
function AssetDetailModal({
  asset,
  onClose,
  onUpdate,
  onPublish,
  onArchive,
  onReclassify
}: {
  asset: Asset
  onClose: () => void
  onUpdate: (updates: { title?: string; content?: string }) => Promise<void>
  onPublish: () => Promise<void>
  onArchive: () => Promise<void>
  onReclassify: (newType: AssetType, newDepartment?: string) => Promise<void>
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedTitle, setEditedTitle] = useState(asset.title)
  const [editedContent, setEditedContent] = useState(asset.content)
  const [showReclassify, setShowReclassify] = useState(false)
  const [newType, setNewType] = useState<AssetType>(asset.assetType as AssetType)
  const [newDepartment, setNewDepartment] = useState(asset.department)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<AssetVersion[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const loadHistory = async () => {
    try {
      setIsLoading(true)
      const response = await getAssetHistory(asset.id)
      setHistory(response.history)
      setShowHistory(true)
    } catch (err) {
      console.error('Failed to load history:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setIsSaving(true)
      await onUpdate({ title: editedTitle, content: editedContent })
      setIsEditing(false)
    } catch (err) {
      console.error('Failed to save:', err)
    } finally {
      setIsSaving(false)
    }
  }

  const handleReclassify = async () => {
    try {
      setIsSaving(true)
      await onReclassify(newType, newDepartment !== asset.department ? newDepartment : undefined)
      setShowReclassify(false)
    } catch (err) {
      console.error('Failed to reclassify:', err)
    } finally {
      setIsSaving(false)
    }
  }

  const config = ASSET_TYPE_CONFIG[asset.assetType as AssetType]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-empire-bg border border-empire-border rounded-xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-empire-border">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{config?.icon || '📄'}</span>
            {isEditing ? (
              <input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                className="bg-empire-card border border-empire-border rounded px-2 py-1 text-empire-text font-semibold"
              />
            ) : (
              <h2 className="text-lg font-semibold text-empire-text">{asset.title}</h2>
            )}
          </div>
          <button onClick={onClose} className="p-2 hover:bg-empire-card rounded-lg">
            <X className="w-5 h-5 text-empire-text-muted" />
          </button>
        </div>

        {/* Meta info */}
        <div className="flex items-center gap-4 px-4 py-2 border-b border-empire-border text-sm">
          <span className={cn(
            'px-2 py-0.5 rounded text-xs font-medium uppercase',
            asset.assetType === 'skill' && 'bg-purple-500/20 text-purple-400',
            asset.assetType === 'command' && 'bg-blue-500/20 text-blue-400',
            asset.assetType === 'agent' && 'bg-green-500/20 text-green-400',
            asset.assetType === 'prompt' && 'bg-yellow-500/20 text-yellow-400',
            asset.assetType === 'workflow' && 'bg-pink-500/20 text-pink-400'
          )}>
            {asset.assetType}
          </span>
          <span className="text-empire-text-muted">{asset.department}</span>
          <span className={cn(
            'px-2 py-0.5 rounded text-xs',
            asset.status === 'draft' && 'bg-yellow-500/20 text-yellow-400',
            asset.status === 'published' && 'bg-green-500/20 text-green-400',
            asset.status === 'archived' && 'bg-gray-500/20 text-gray-400'
          )}>
            {asset.status}
          </span>
          <span className="text-empire-text-muted">v{asset.version}</span>
          {asset.classificationConfidence && (
            <span className="text-empire-text-muted">
              {Math.round(asset.classificationConfidence * 100)}% confidence
            </span>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {showHistory ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-empire-text">Version History</h3>
                <button
                  onClick={() => setShowHistory(false)}
                  className="text-sm text-empire-primary hover:underline"
                >
                  Back to content
                </button>
              </div>
              {history.map((version) => (
                <div
                  key={version.id}
                  className={cn(
                    'p-3 rounded-lg border',
                    version.isCurrent
                      ? 'bg-empire-primary/10 border-empire-primary'
                      : 'bg-empire-card border-empire-border'
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-empire-text">Version {version.version}</span>
                    {version.isCurrent && (
                      <span className="text-xs bg-empire-primary/20 text-empire-primary px-2 py-0.5 rounded">
                        Current
                      </span>
                    )}
                    {version.createdAt && (
                      <span className="text-xs text-empire-text-muted">
                        {new Date(version.createdAt).toLocaleString()}
                      </span>
                    )}
                  </div>
                  <pre className="text-sm text-empire-text-muted whitespace-pre-wrap font-mono bg-empire-bg p-2 rounded max-h-32 overflow-y-auto">
                    {version.content.substring(0, 500)}...
                  </pre>
                </div>
              ))}
            </div>
          ) : showReclassify ? (
            <div className="space-y-4">
              <h3 className="font-semibold text-empire-text">Reclassify Asset</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-empire-text-muted mb-1">Asset Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value as AssetType)}
                    className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text"
                  >
                    {ASSET_TYPES.map((type) => (
                      <option key={type.id} value={type.id}>
                        {type.label} ({type.format.toUpperCase()})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-empire-text-muted mb-1">Department</label>
                  <select
                    value={newDepartment}
                    onChange={(e) => setNewDepartment(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text"
                  >
                    {DEPARTMENTS.map((dept) => (
                      <option key={dept.id} value={dept.id}>{dept.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleReclassify}
                  disabled={isSaving}
                  className="px-4 py-2 bg-empire-primary text-white rounded-lg hover:bg-empire-primary/90 disabled:opacity-50"
                >
                  {isSaving ? 'Saving...' : 'Apply'}
                </button>
                <button
                  onClick={() => setShowReclassify(false)}
                  className="px-4 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {isEditing ? (
                <textarea
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  className="w-full h-80 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text font-mono text-sm resize-none"
                />
              ) : (
                <pre className="text-sm text-empire-text whitespace-pre-wrap font-mono bg-empire-card p-4 rounded-lg max-h-80 overflow-y-auto">
                  {asset.content}
                </pre>
              )}

              {asset.sourceDocumentTitle && (
                <div className="text-sm">
                  <span className="text-empire-text-muted">Source: </span>
                  <span className="text-empire-primary">{asset.sourceDocumentTitle}</span>
                </div>
              )}

              {asset.classificationReasoning && (
                <div className="text-sm">
                  <span className="text-empire-text-muted">Classification reasoning: </span>
                  <span className="text-empire-text">{asset.classificationReasoning}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between p-4 border-t border-empire-border">
          <div className="flex gap-2">
            <button
              onClick={loadHistory}
              disabled={isLoading}
              className="flex items-center gap-2 px-3 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border text-sm"
            >
              <History className="w-4 h-4" />
              History
            </button>
            <button
              onClick={() => setShowReclassify(true)}
              className="flex items-center gap-2 px-3 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              Reclassify
            </button>
          </div>

          <div className="flex gap-2">
            {isEditing ? (
              <>
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="flex items-center gap-2 px-4 py-2 bg-empire-primary text-white rounded-lg hover:bg-empire-primary/90 disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {isSaving ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => {
                    setEditedTitle(asset.title)
                    setEditedContent(asset.content)
                    setIsEditing(false)
                  }}
                  className="px-4 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-2 px-3 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border text-sm"
                >
                  <Edit3 className="w-4 h-4" />
                  Edit
                </button>
                {asset.status === 'draft' && (
                  <button
                    onClick={onPublish}
                    className="flex items-center gap-2 px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
                  >
                    <Upload className="w-4 h-4" />
                    Publish
                  </button>
                )}
                {asset.status !== 'archived' && (
                  <button
                    onClick={onArchive}
                    className="flex items-center gap-2 px-3 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border text-sm"
                  >
                    <Archive className="w-4 h-4" />
                    Archive
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function AssetsPanel() {
  const {
    assets,
    setAssets,
    assetTypeFilter,
    assetDepartmentFilter,
    assetStatusFilter,
    setAssetFilters,
    searchQuery,
    setSearchQuery,
    updateAsset: updateAssetInStore
  } = useAIStudioStore()

  const [isLoading, setIsLoading] = useState(false)
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null)
  const [localSearch, setLocalSearch] = useState('')

  // Load assets on mount and when filters change
  useEffect(() => {
    const loadAssets = async () => {
      try {
        setIsLoading(true)
        const response = await listAssets({
          assetType: assetTypeFilter as AssetType | undefined,
          department: assetDepartmentFilter || undefined,
          status: assetStatusFilter as 'draft' | 'published' | 'archived' | undefined,
          search: searchQuery || undefined
        })
        // Transform API response to store format
        const storeAssets = response.assets.map(a => ({
          id: a.id,
          assetType: a.assetType as 'skill' | 'command' | 'agent' | 'prompt' | 'workflow',
          department: a.department,
          name: a.name,
          title: a.title,
          content: a.content,
          format: a.format as 'yaml' | 'md' | 'json',
          status: a.status as 'draft' | 'published' | 'archived',
          sourceDocumentId: a.sourceDocumentId,
          sourceDocumentTitle: a.sourceDocumentTitle,
          classificationConfidence: a.classificationConfidence,
          classificationReasoning: a.classificationReasoning,
          version: a.version,
          createdAt: a.createdAt || '',
          updatedAt: a.updatedAt || ''
        }))
        setAssets(storeAssets)
      } catch (err) {
        console.error('Failed to load assets:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadAssets()
  }, [assetTypeFilter, assetDepartmentFilter, assetStatusFilter, searchQuery, setAssets])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(localSearch)
    }, 300)
    return () => clearTimeout(timer)
  }, [localSearch, setSearchQuery])

  const handleAssetClick = async (assetId: string) => {
    try {
      const asset = await getAsset(assetId)
      setSelectedAsset(asset)
    } catch (err) {
      console.error('Failed to load asset:', err)
    }
  }

  const handleUpdate = async (updates: { title?: string; content?: string }) => {
    if (!selectedAsset) return
    try {
      const updated = await updateAsset(selectedAsset.id, updates)
      setSelectedAsset(updated)
      updateAssetInStore(updated.id, {
        title: updated.title,
        content: updated.content,
        version: updated.version,
        updatedAt: updated.updatedAt || ''
      })
    } catch (err) {
      console.error('Failed to update:', err)
      throw err
    }
  }

  const handlePublish = async () => {
    if (!selectedAsset) return
    try {
      const updated = await publishAsset(selectedAsset.id)
      setSelectedAsset(updated)
      updateAssetInStore(updated.id, {
        status: 'published' as const,
        updatedAt: updated.updatedAt || ''
      })
    } catch (err) {
      console.error('Failed to publish:', err)
    }
  }

  const handleArchive = async () => {
    if (!selectedAsset) return
    try {
      const updated = await archiveAsset(selectedAsset.id)
      setSelectedAsset(updated)
      updateAssetInStore(updated.id, {
        status: 'archived' as const,
        updatedAt: updated.updatedAt || ''
      })
    } catch (err) {
      console.error('Failed to archive:', err)
    }
  }

  const handleReclassify = async (newType: AssetType, newDepartment?: string) => {
    if (!selectedAsset) return
    try {
      const updated = await reclassifyAsset(selectedAsset.id, { newType, newDepartment })
      setSelectedAsset(updated)
      updateAssetInStore(updated.id, {
        assetType: updated.assetType as 'skill' | 'command' | 'agent' | 'prompt' | 'workflow',
        department: updated.department,
        format: updated.format as 'yaml' | 'md' | 'json',
        updatedAt: updated.updatedAt || ''
      })
    } catch (err) {
      console.error('Failed to reclassify:', err)
      throw err
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-empire-text">Assets</h3>
        <span className="text-xs text-empire-text-muted">
          {isLoading ? 'Loading...' : `${assets.length} items`}
        </span>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-empire-text-muted" />
        <input
          type="text"
          placeholder="Search assets..."
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm placeholder:text-empire-text-muted"
        />
      </div>

      {/* Filters */}
      <div className="space-y-2">
        <select
          value={assetTypeFilter || ''}
          onChange={(e) => setAssetFilters({ type: e.target.value || null })}
          className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
        >
          <option value="">All Types</option>
          {ASSET_TYPES.map((type) => (
            <option key={type.id} value={type.id}>{type.label}</option>
          ))}
        </select>

        <select
          value={assetDepartmentFilter || ''}
          onChange={(e) => setAssetFilters({ department: e.target.value || null })}
          className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
        >
          <option value="">All Departments</option>
          {DEPARTMENTS.map((dept) => (
            <option key={dept.id} value={dept.id}>{dept.label}</option>
          ))}
        </select>

        <select
          value={assetStatusFilter || ''}
          onChange={(e) => setAssetFilters({ status: e.target.value || null })}
          className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
        >
          <option value="">All Statuses</option>
          <option value="draft">Drafts</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {/* Asset List */}
      <div className="space-y-2 max-h-[400px] overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-empire-primary" />
          </div>
        ) : assets.length === 0 ? (
          <div className="text-center py-8 text-empire-text-muted">
            <Package className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No assets yet</p>
            <p className="text-xs mt-1">Assets will appear here as CKO processes your content</p>
          </div>
        ) : (
          assets.map((asset) => (
            <button
              key={asset.id}
              onClick={() => handleAssetClick(asset.id)}
              className="w-full p-3 rounded-lg bg-empire-card border border-empire-border hover:border-empire-primary/50 text-left transition-colors"
            >
              <div className="flex items-start gap-3">
                <span className={cn(
                  'px-2 py-0.5 rounded text-xs font-medium uppercase',
                  asset.assetType === 'skill' && 'bg-purple-500/20 text-purple-400',
                  asset.assetType === 'command' && 'bg-blue-500/20 text-blue-400',
                  asset.assetType === 'agent' && 'bg-green-500/20 text-green-400',
                  asset.assetType === 'prompt' && 'bg-yellow-500/20 text-yellow-400',
                  asset.assetType === 'workflow' && 'bg-pink-500/20 text-pink-400'
                )}>
                  {asset.assetType}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-empire-text truncate">{asset.title}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-xs text-empire-text-muted truncate">{asset.department}</p>
                    <span className={cn(
                      'text-xs px-1.5 py-0.5 rounded',
                      asset.status === 'draft' && 'bg-yellow-500/20 text-yellow-400',
                      asset.status === 'published' && 'bg-green-500/20 text-green-400',
                      asset.status === 'archived' && 'bg-gray-500/20 text-gray-400'
                    )}>
                      {asset.status}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          ))
        )}
      </div>

      {/* Asset Detail Modal */}
      {selectedAsset && (
        <AssetDetailModal
          asset={selectedAsset}
          onClose={() => setSelectedAsset(null)}
          onUpdate={handleUpdate}
          onPublish={handlePublish}
          onArchive={handleArchive}
          onReclassify={handleReclassify}
        />
      )}
    </div>
  )
}

// Classification Correction Modal
function ClassificationCorrectionModal({
  classification,
  onClose,
  onCorrect
}: {
  classification: Classification
  onClose: () => void
  onCorrect: (newDepartment: string, reason?: string) => Promise<void>
}) {
  const [newDepartment, setNewDepartment] = useState(classification.department)
  const [reason, setReason] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const handleSubmit = async () => {
    if (newDepartment === classification.department) return
    try {
      setIsSaving(true)
      await onCorrect(newDepartment, reason || undefined)
      onClose()
    } catch (err) {
      console.error('Failed to correct classification:', err)
    } finally {
      setIsSaving(false)
    }
  }

  const confidenceLevel = getConfidenceLevel(classification.confidence)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-empire-bg border border-empire-border rounded-xl w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-empire-border">
          <h2 className="text-lg font-semibold text-empire-text">Correct Classification</h2>
          <button onClick={onClose} className="p-2 hover:bg-empire-card rounded-lg">
            <X className="w-5 h-5 text-empire-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Current classification info */}
          <div className="p-3 rounded-lg bg-empire-card border border-empire-border">
            <p className="text-sm font-medium text-empire-text truncate">
              {classification.filename || 'Untitled Content'}
            </p>
            {classification.contentPreview && (
              <p className="text-xs text-empire-text-muted mt-1 line-clamp-2">
                {classification.contentPreview}
              </p>
            )}
          </div>

          {/* Current classification */}
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <label className="text-xs text-empire-text-muted uppercase tracking-wider">Current</label>
              <p className="text-sm text-empire-text">{getDepartmentLabel(classification.department)}</p>
            </div>
            <div>
              <span className={cn('px-2 py-0.5 rounded text-xs font-medium', getConfidenceBadgeColor(classification.confidence))}>
                {Math.round(classification.confidence * 100)}% {confidenceLevel}
              </span>
            </div>
          </div>

          {/* Reasoning */}
          {classification.reasoning && (
            <div>
              <label className="text-xs text-empire-text-muted uppercase tracking-wider">AI Reasoning</label>
              <p className="text-sm text-empire-text-muted mt-1">{classification.reasoning}</p>
            </div>
          )}

          {/* Keywords */}
          {classification.keywordsMatched && classification.keywordsMatched.length > 0 && (
            <div>
              <label className="text-xs text-empire-text-muted uppercase tracking-wider">Keywords Matched</label>
              <div className="flex flex-wrap gap-1 mt-1">
                {classification.keywordsMatched.map((kw, i) => (
                  <span key={i} className="px-2 py-0.5 rounded bg-empire-border text-xs text-empire-text">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* New department selection */}
          <div>
            <label className="text-xs text-empire-text-muted uppercase tracking-wider">Correct Department</label>
            <select
              value={newDepartment}
              onChange={(e) => setNewDepartment(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text"
            >
              {CLASSIFICATION_DEPARTMENTS.map((dept) => (
                <option key={dept.value} value={dept.value}>{dept.label}</option>
              ))}
            </select>
          </div>

          {/* Reason */}
          <div>
            <label className="text-xs text-empire-text-muted uppercase tracking-wider">Reason (optional)</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is this the correct department?"
              rows={2}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm resize-none placeholder:text-empire-text-muted"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 p-4 border-t border-empire-border">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSaving || newDepartment === classification.department}
            className="px-4 py-2 bg-empire-primary text-white rounded-lg hover:bg-empire-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? 'Saving...' : 'Save Correction'}
          </button>
        </div>
      </div>
    </div>
  )
}

function ClassificationsPanel() {
  const { classificationDepartmentFilter, setClassificationFilter } = useAIStudioStore()

  const [classifications, setClassificationsLocal] = useState<Classification[]>([])
  const [stats, setStats] = useState<ClassificationStatsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedClassification, setSelectedClassification] = useState<Classification | null>(null)
  const [localSearch, setLocalSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [confidenceFilter, setConfidenceFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all')
  const [correctedFilter, setCorrectedFilter] = useState<'all' | 'corrected' | 'uncorrected'>('all')

  // Load classifications and stats on mount and when filters change
  useEffect(() => {
    const loadClassifications = async () => {
      try {
        setIsLoading(true)

        // Build filters
        const confidenceMin = confidenceFilter === 'high' ? 0.8 :
                             confidenceFilter === 'medium' ? 0.5 :
                             confidenceFilter === 'low' ? 0 : undefined
        const corrected = correctedFilter === 'corrected' ? true :
                         correctedFilter === 'uncorrected' ? false : undefined

        const response = await listClassifications({
          department: classificationDepartmentFilter || undefined,
          confidence_min: confidenceMin,
          corrected,
          search: searchQuery || undefined
        })

        setClassificationsLocal(response.classifications)
      } catch (err) {
        console.error('Failed to load classifications:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadClassifications()
  }, [classificationDepartmentFilter, searchQuery, confidenceFilter, correctedFilter])

  // Load stats on mount
  useEffect(() => {
    const loadStats = async () => {
      try {
        const statsData = await getClassificationStats()
        setStats(statsData)
      } catch (err) {
        console.error('Failed to load classification stats:', err)
      }
    }
    loadStats()
  }, [])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(localSearch)
    }, 300)
    return () => clearTimeout(timer)
  }, [localSearch])

  const handleClassificationClick = async (classificationId: string) => {
    try {
      const classification = await getClassification(classificationId)
      setSelectedClassification(classification)
    } catch (err) {
      console.error('Failed to load classification:', err)
    }
  }

  const handleCorrect = async (newDepartment: string, reason?: string) => {
    if (!selectedClassification) return
    try {
      const updated = await correctClassification(selectedClassification.id, {
        newDepartment,
        reason
      })
      // Update local state
      setClassificationsLocal(prev =>
        prev.map(c => c.id === updated.id ? updated : c)
      )
      // Refresh stats
      const statsData = await getClassificationStats()
      setStats(statsData)
    } catch (err) {
      console.error('Failed to correct classification:', err)
      throw err
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-empire-text">Classifications</h3>
        <span className="text-xs text-empire-text-muted">
          {isLoading ? 'Loading...' : `${classifications.length} items`}
        </span>
      </div>

      {/* Stats Summary */}
      {stats && (
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 rounded-lg bg-green-500/10 border border-green-500/20">
            <p className="text-lg font-semibold text-green-400">{stats.byConfidence.high}</p>
            <p className="text-xs text-green-400/70">High</p>
          </div>
          <div className="p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
            <p className="text-lg font-semibold text-yellow-400">{stats.byConfidence.medium}</p>
            <p className="text-xs text-yellow-400/70">Medium</p>
          </div>
          <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
            <p className="text-lg font-semibold text-red-400">{stats.byConfidence.low}</p>
            <p className="text-xs text-red-400/70">Low</p>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-empire-text-muted" />
        <input
          type="text"
          placeholder="Search classifications..."
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm placeholder:text-empire-text-muted"
        />
      </div>

      {/* Filters */}
      <div className="space-y-2">
        <select
          value={classificationDepartmentFilter || ''}
          onChange={(e) => setClassificationFilter(e.target.value || null)}
          className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
        >
          <option value="">All Departments</option>
          {CLASSIFICATION_DEPARTMENTS.map((dept) => (
            <option key={dept.value} value={dept.value}>{dept.label}</option>
          ))}
        </select>

        <div className="flex gap-2">
          <select
            value={confidenceFilter}
            onChange={(e) => setConfidenceFilter(e.target.value as 'all' | 'high' | 'medium' | 'low')}
            className="flex-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
          >
            <option value="all">All Confidence</option>
            <option value="high">High (80%+)</option>
            <option value="medium">Medium (50-80%)</option>
            <option value="low">Low (&lt;50%)</option>
          </select>

          <select
            value={correctedFilter}
            onChange={(e) => setCorrectedFilter(e.target.value as 'all' | 'corrected' | 'uncorrected')}
            className="flex-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
          >
            <option value="all">All Status</option>
            <option value="corrected">Corrected</option>
            <option value="uncorrected">Uncorrected</option>
          </select>
        </div>
      </div>

      {/* Classifications List */}
      <div className="space-y-2 max-h-[350px] overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-empire-primary" />
          </div>
        ) : classifications.length === 0 ? (
          <div className="text-center py-8 text-empire-text-muted">
            <Tags className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No classifications yet</p>
            <p className="text-xs mt-1">Content classifications will appear here</p>
          </div>
        ) : (
          classifications.map((classification) => (
            <button
              key={classification.id}
              onClick={() => handleClassificationClick(classification.id)}
              className="w-full p-3 rounded-lg bg-empire-card border border-empire-border hover:border-empire-primary/50 text-left transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-empire-text truncate">
                    {classification.filename || 'Untitled'}
                  </p>
                  <p className="text-xs text-empire-text-muted">
                    {getDepartmentLabel(classification.department)}
                  </p>
                </div>
                <span className={cn(
                  'px-2 py-0.5 rounded text-xs font-medium',
                  getConfidenceBadgeColor(classification.confidence)
                )}>
                  {Math.round(classification.confidence * 100)}%
                </span>
              </div>
              {classification.userCorrectedDepartment && (
                <p className="mt-2 text-xs text-empire-primary flex items-center gap-1">
                  <RefreshCw className="w-3 h-3" />
                  Corrected to: {getDepartmentLabel(classification.userCorrectedDepartment)}
                </p>
              )}
            </button>
          ))
        )}
      </div>

      {/* Correction Modal */}
      {selectedClassification && (
        <ClassificationCorrectionModal
          classification={selectedClassification}
          onClose={() => setSelectedClassification(null)}
          onCorrect={handleCorrect}
        />
      )}
    </div>
  )
}

// Weight slider component
function WeightSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 2,
  step = 0.1
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-empire-text-muted flex-1 min-w-0 truncate">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-24 h-1.5 bg-empire-border rounded-lg appearance-none cursor-pointer accent-empire-primary"
      />
      <span className="text-sm text-empire-text w-10 text-right">{value.toFixed(1)}x</span>
    </div>
  )
}

// Toggle switch component
function WeightToggle({
  label,
  enabled,
  onChange
}: {
  label: string
  enabled: boolean
  onChange: (enabled: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between">
      <label className="text-xs text-empire-text-muted uppercase tracking-wider">{label}</label>
      <button
        onClick={() => onChange(!enabled)}
        className={cn(
          'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
          enabled ? 'bg-empire-primary' : 'bg-empire-border'
        )}
      >
        <span
          className={cn(
            'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
            enabled ? 'translate-x-5' : 'translate-x-1'
          )}
        />
      </button>
    </div>
  )
}

function WeightsPanel() {
  const { userWeights, setUserWeights, updateWeightPreset } = useAIStudioStore()
  const [expandedSection, setExpandedSection] = useState<string | null>(null)

  // Update a specific weight category
  const updateRecency = (key: keyof typeof userWeights.recency, value: number | boolean) => {
    setUserWeights({
      ...userWeights,
      preset: 'custom',
      recency: { ...userWeights.recency, [key]: value }
    })
  }

  const updateSourceType = (key: keyof typeof userWeights.sourceTypes, value: number | boolean) => {
    setUserWeights({
      ...userWeights,
      preset: 'custom',
      sourceTypes: { ...userWeights.sourceTypes, [key]: value }
    })
  }

  const updateDepartment = (deptId: string, value: number) => {
    setUserWeights({
      ...userWeights,
      preset: 'custom',
      departments: { ...userWeights.departments, [deptId]: value }
    })
  }

  const updateConfidence = (key: keyof typeof userWeights.confidence, value: number | boolean) => {
    setUserWeights({
      ...userWeights,
      preset: 'custom',
      confidence: { ...userWeights.confidence, [key]: value }
    })
  }

  const updateVerified = (key: keyof typeof userWeights.verified, value: number | boolean) => {
    setUserWeights({
      ...userWeights,
      preset: 'custom',
      verified: { ...userWeights.verified, [key]: value }
    })
  }

  // Apply preset
  const handlePresetChange = (preset: typeof userWeights.preset) => {
    if (preset === 'balanced') {
      setUserWeights({
        preset: 'balanced',
        departments: {},
        recency: { enabled: true, last_30_days: 1.5, last_year: 1.0, older: 0.7 },
        sourceTypes: { enabled: true, pdf: 1.0, video: 0.9, audio: 0.85, web: 0.8, notes: 0.7 },
        confidence: { enabled: true, high: 1.2, medium: 1.0, low: 0.8 },
        verified: { enabled: true, weight: 1.5 }
      })
    } else if (preset === 'recent-focus') {
      setUserWeights({
        preset: 'recent-focus',
        departments: {},
        recency: { enabled: true, last_30_days: 2.0, last_year: 1.0, older: 0.3 },
        sourceTypes: { enabled: true, pdf: 1.0, video: 1.0, audio: 1.0, web: 1.0, notes: 1.0 },
        confidence: { enabled: true, high: 1.2, medium: 1.0, low: 0.8 },
        verified: { enabled: false, weight: 1.0 }
      })
    } else if (preset === 'verified-only') {
      setUserWeights({
        preset: 'verified-only',
        departments: {},
        recency: { enabled: false, last_30_days: 1.0, last_year: 1.0, older: 1.0 },
        sourceTypes: { enabled: false, pdf: 1.0, video: 1.0, audio: 1.0, web: 1.0, notes: 1.0 },
        confidence: { enabled: true, high: 2.0, medium: 1.0, low: 0.1 },
        verified: { enabled: true, weight: 2.0 }
      })
    } else {
      updateWeightPreset(preset)
    }
  }

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  return (
    <div className="p-4 space-y-4 overflow-y-auto max-h-full">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-empire-text">Data Weights</h3>
      </div>

      {/* Preset Selector */}
      <div className="space-y-2">
        <label className="text-xs text-empire-text-muted uppercase tracking-wider">Preset</label>
        <select
          value={userWeights.preset}
          onChange={(e) => handlePresetChange(e.target.value as typeof userWeights.preset)}
          className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
        >
          <option value="balanced">Balanced</option>
          <option value="recent-focus">Recent Focus</option>
          <option value="verified-only">Verified Only</option>
          <option value="custom">Custom</option>
        </select>
      </div>

      {/* Department Weights */}
      <div className="space-y-2 border border-empire-border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('departments')}
          className="w-full flex items-center justify-between p-3 bg-empire-card hover:bg-empire-border/50 transition-colors"
        >
          <span className="text-xs text-empire-text-muted uppercase tracking-wider">Department Priority</span>
          {expandedSection === 'departments' ? (
            <ChevronUp className="w-4 h-4 text-empire-text-muted" />
          ) : (
            <ChevronDown className="w-4 h-4 text-empire-text-muted" />
          )}
        </button>
        {expandedSection === 'departments' && (
          <div className="px-3 pb-3 space-y-2">
            {DEPARTMENTS.map((dept) => (
              <WeightSlider
                key={dept.id}
                label={dept.label}
                value={userWeights.departments[dept.id] || 1.0}
                onChange={(v) => updateDepartment(dept.id, v)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Recency Weights */}
      <div className="space-y-2 border border-empire-border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('recency')}
          className="w-full flex items-center justify-between p-3 bg-empire-card hover:bg-empire-border/50 transition-colors"
        >
          <span className="text-xs text-empire-text-muted uppercase tracking-wider">Recency</span>
          <div className="flex items-center gap-2">
            <span className={cn(
              'text-xs',
              userWeights.recency.enabled ? 'text-green-400' : 'text-empire-text-muted'
            )}>
              {userWeights.recency.enabled ? 'On' : 'Off'}
            </span>
            {expandedSection === 'recency' ? (
              <ChevronUp className="w-4 h-4 text-empire-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-empire-text-muted" />
            )}
          </div>
        </button>
        {expandedSection === 'recency' && (
          <div className="px-3 pb-3 space-y-3">
            <WeightToggle
              label="Enable"
              enabled={userWeights.recency.enabled}
              onChange={(v) => updateRecency('enabled', v)}
            />
            {userWeights.recency.enabled && (
              <>
                <WeightSlider
                  label="Last 30 days"
                  value={userWeights.recency.last_30_days}
                  onChange={(v) => updateRecency('last_30_days', v)}
                />
                <WeightSlider
                  label="Last year"
                  value={userWeights.recency.last_year}
                  onChange={(v) => updateRecency('last_year', v)}
                />
                <WeightSlider
                  label="Older"
                  value={userWeights.recency.older}
                  onChange={(v) => updateRecency('older', v)}
                />
              </>
            )}
          </div>
        )}
      </div>

      {/* Source Type Weights */}
      <div className="space-y-2 border border-empire-border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('sourceTypes')}
          className="w-full flex items-center justify-between p-3 bg-empire-card hover:bg-empire-border/50 transition-colors"
        >
          <span className="text-xs text-empire-text-muted uppercase tracking-wider">Source Types</span>
          <div className="flex items-center gap-2">
            <span className={cn(
              'text-xs',
              userWeights.sourceTypes.enabled ? 'text-green-400' : 'text-empire-text-muted'
            )}>
              {userWeights.sourceTypes.enabled ? 'On' : 'Off'}
            </span>
            {expandedSection === 'sourceTypes' ? (
              <ChevronUp className="w-4 h-4 text-empire-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-empire-text-muted" />
            )}
          </div>
        </button>
        {expandedSection === 'sourceTypes' && (
          <div className="px-3 pb-3 space-y-3">
            <WeightToggle
              label="Enable"
              enabled={userWeights.sourceTypes.enabled}
              onChange={(v) => updateSourceType('enabled', v)}
            />
            {userWeights.sourceTypes.enabled && (
              <>
                <WeightSlider
                  label="PDF"
                  value={userWeights.sourceTypes.pdf}
                  onChange={(v) => updateSourceType('pdf', v)}
                />
                <WeightSlider
                  label="Video"
                  value={userWeights.sourceTypes.video}
                  onChange={(v) => updateSourceType('video', v)}
                />
                <WeightSlider
                  label="Audio"
                  value={userWeights.sourceTypes.audio}
                  onChange={(v) => updateSourceType('audio', v)}
                />
                <WeightSlider
                  label="Web"
                  value={userWeights.sourceTypes.web}
                  onChange={(v) => updateSourceType('web', v)}
                />
                <WeightSlider
                  label="Notes"
                  value={userWeights.sourceTypes.notes}
                  onChange={(v) => updateSourceType('notes', v)}
                />
              </>
            )}
          </div>
        )}
      </div>

      {/* Confidence Weights */}
      <div className="space-y-2 border border-empire-border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('confidence')}
          className="w-full flex items-center justify-between p-3 bg-empire-card hover:bg-empire-border/50 transition-colors"
        >
          <span className="text-xs text-empire-text-muted uppercase tracking-wider">Confidence</span>
          <div className="flex items-center gap-2">
            <span className={cn(
              'text-xs',
              userWeights.confidence.enabled ? 'text-green-400' : 'text-empire-text-muted'
            )}>
              {userWeights.confidence.enabled ? 'On' : 'Off'}
            </span>
            {expandedSection === 'confidence' ? (
              <ChevronUp className="w-4 h-4 text-empire-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-empire-text-muted" />
            )}
          </div>
        </button>
        {expandedSection === 'confidence' && (
          <div className="px-3 pb-3 space-y-3">
            <WeightToggle
              label="Enable"
              enabled={userWeights.confidence.enabled}
              onChange={(v) => updateConfidence('enabled', v)}
            />
            {userWeights.confidence.enabled && (
              <>
                <WeightSlider
                  label="High confidence"
                  value={userWeights.confidence.high}
                  onChange={(v) => updateConfidence('high', v)}
                />
                <WeightSlider
                  label="Medium confidence"
                  value={userWeights.confidence.medium}
                  onChange={(v) => updateConfidence('medium', v)}
                />
                <WeightSlider
                  label="Low confidence"
                  value={userWeights.confidence.low}
                  onChange={(v) => updateConfidence('low', v)}
                />
              </>
            )}
          </div>
        )}
      </div>

      {/* Verified Documents Weight */}
      <div className="space-y-2 border border-empire-border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection('verified')}
          className="w-full flex items-center justify-between p-3 bg-empire-card hover:bg-empire-border/50 transition-colors"
        >
          <span className="text-xs text-empire-text-muted uppercase tracking-wider">Verified Docs</span>
          <div className="flex items-center gap-2">
            <span className={cn(
              'text-xs',
              userWeights.verified.enabled ? 'text-green-400' : 'text-empire-text-muted'
            )}>
              {userWeights.verified.enabled ? 'On' : 'Off'}
            </span>
            {expandedSection === 'verified' ? (
              <ChevronUp className="w-4 h-4 text-empire-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-empire-text-muted" />
            )}
          </div>
        </button>
        {expandedSection === 'verified' && (
          <div className="px-3 pb-3 space-y-3">
            <WeightToggle
              label="Enable"
              enabled={userWeights.verified.enabled}
              onChange={(v) => updateVerified('enabled', v)}
            />
            {userWeights.verified.enabled && (
              <WeightSlider
                label="Verified boost"
                value={userWeights.verified.weight}
                onChange={(v) => updateVerified('weight', v)}
              />
            )}
          </div>
        )}
      </div>

      {/* Tip */}
      <p className="text-xs text-empire-text-muted italic pt-2">
        Tip: Ask CKO to "prioritize recent documents" to adjust weights via conversation.
      </p>
    </div>
  )
}

// Feedback Submit Modal
function FeedbackSubmitModal({
  onClose,
  onSubmit
}: {
  onClose: () => void
  onSubmit: () => void
}) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('general_feedback')
  const [rating, setRating] = useState<number>(0)
  const [feedbackText, setFeedbackText] = useState('')
  const [improvementSuggestions, setImprovementSuggestions] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async () => {
    try {
      setIsSubmitting(true)
      await submitFeedback({
        feedbackType,
        rating: rating || undefined,
        feedbackText: feedbackText || undefined,
        improvementSuggestions: improvementSuggestions || undefined
      })
      onSubmit()
      onClose()
    } catch (err) {
      console.error('Failed to submit feedback:', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-empire-bg border border-empire-border rounded-xl w-full max-w-md overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-empire-border">
          <h2 className="text-lg font-semibold text-empire-text">Submit Feedback</h2>
          <button onClick={onClose} className="p-2 hover:bg-empire-card rounded-lg">
            <X className="w-5 h-5 text-empire-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Feedback Type */}
          <div>
            <label className="text-xs text-empire-text-muted uppercase tracking-wider">Feedback Type</label>
            <select
              value={feedbackType}
              onChange={(e) => setFeedbackType(e.target.value as FeedbackType)}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text"
            >
              {FEEDBACK_TYPES.map((type) => (
                <option key={type.id} value={type.id}>{type.label}</option>
              ))}
            </select>
          </div>

          {/* Rating */}
          <div>
            <label className="text-xs text-empire-text-muted uppercase tracking-wider">Rating</label>
            <div className="flex gap-2 mt-1">
              <button
                onClick={() => setRating(1)}
                className={cn(
                  'flex-1 p-2 rounded-lg border flex items-center justify-center gap-2 transition-colors',
                  rating === 1
                    ? 'bg-green-500/20 border-green-500/50 text-green-400'
                    : 'bg-empire-card border-empire-border text-empire-text-muted hover:border-green-500/30'
                )}
              >
                <ThumbsUp className="w-4 h-4" />
                <span className="text-sm">Positive</span>
              </button>
              <button
                onClick={() => setRating(0)}
                className={cn(
                  'flex-1 p-2 rounded-lg border flex items-center justify-center gap-2 transition-colors',
                  rating === 0
                    ? 'bg-gray-500/20 border-gray-500/50 text-gray-400'
                    : 'bg-empire-card border-empire-border text-empire-text-muted hover:border-gray-500/30'
                )}
              >
                <Minus className="w-4 h-4" />
                <span className="text-sm">Neutral</span>
              </button>
              <button
                onClick={() => setRating(-1)}
                className={cn(
                  'flex-1 p-2 rounded-lg border flex items-center justify-center gap-2 transition-colors',
                  rating === -1
                    ? 'bg-red-500/20 border-red-500/50 text-red-400'
                    : 'bg-empire-card border-empire-border text-empire-text-muted hover:border-red-500/30'
                )}
              >
                <ThumbsDown className="w-4 h-4" />
                <span className="text-sm">Negative</span>
              </button>
            </div>
          </div>

          {/* Feedback Text */}
          <div>
            <label className="text-xs text-empire-text-muted uppercase tracking-wider">Feedback</label>
            <textarea
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              placeholder="Share your feedback..."
              rows={3}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm resize-none placeholder:text-empire-text-muted"
            />
          </div>

          {/* Improvement Suggestions */}
          <div>
            <label className="text-xs text-empire-text-muted uppercase tracking-wider">Suggestions (optional)</label>
            <textarea
              value={improvementSuggestions}
              onChange={(e) => setImprovementSuggestions(e.target.value)}
              placeholder="How could we improve?"
              rows={2}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm resize-none placeholder:text-empire-text-muted"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 p-4 border-t border-empire-border">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-empire-card border border-empire-border text-empire-text rounded-lg hover:bg-empire-border"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="px-4 py-2 bg-empire-primary text-white rounded-lg hover:bg-empire-primary/90 disabled:opacity-50"
          >
            {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      </div>
    </div>
  )
}

function FeedbackPanel() {
  const [feedbackList, setFeedbackList] = useState<Feedback[]>([])
  const [stats, setStats] = useState<FeedbackStatsResponse | null>(null)
  const [summary, setSummary] = useState<FeedbackSummaryResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showSubmitModal, setShowSubmitModal] = useState(false)
  const [typeFilter, setTypeFilter] = useState<FeedbackType | ''>('')
  const [ratingFilter, setRatingFilter] = useState<'all' | 'positive' | 'neutral' | 'negative'>('all')

  // Load feedback data on mount and when filters change
  useEffect(() => {
    const loadFeedback = async () => {
      try {
        setIsLoading(true)
        const ratingValue = ratingFilter === 'positive' ? 1 :
                          ratingFilter === 'negative' ? -1 :
                          ratingFilter === 'neutral' ? 0 : undefined

        const response = await listFeedback({
          feedbackType: typeFilter || undefined,
          rating: ratingValue
        })
        setFeedbackList(response.feedback)
      } catch (err) {
        console.error('Failed to load feedback:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadFeedback()
  }, [typeFilter, ratingFilter])

  // Load stats and summary on mount
  useEffect(() => {
    const loadStatsAndSummary = async () => {
      try {
        const [statsData, summaryData] = await Promise.all([
          getFeedbackStats(),
          getFeedbackSummary(7)
        ])
        setStats(statsData)
        setSummary(summaryData)
      } catch (err) {
        console.error('Failed to load feedback stats:', err)
      }
    }
    loadStatsAndSummary()
  }, [])

  const handleFeedbackSubmitted = async () => {
    // Refresh data after submission
    try {
      const [feedbackData, statsData, summaryData] = await Promise.all([
        listFeedback({ feedbackType: typeFilter || undefined }),
        getFeedbackStats(),
        getFeedbackSummary(7)
      ])
      setFeedbackList(feedbackData.feedback)
      setStats(statsData)
      setSummary(summaryData)
    } catch (err) {
      console.error('Failed to refresh feedback data:', err)
    }
  }

  // Get trend icon component
  const TrendIcon = stats?.recentTrend === 'improving' ? TrendingUp :
                   stats?.recentTrend === 'declining' ? TrendingDown : Minus

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-empire-text">Feedback</h3>
        <button
          onClick={() => setShowSubmitModal(true)}
          className="flex items-center gap-1 px-2 py-1 rounded bg-empire-primary/10 text-empire-primary text-xs hover:bg-empire-primary/20 transition-colors"
        >
          <Plus className="w-3 h-3" />
          Add
        </button>
      </div>

      {/* Stats Summary */}
      {stats && (
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 rounded-lg bg-green-500/10 border border-green-500/20">
            <p className="text-lg font-semibold text-green-400">{stats.byRating.positive}</p>
            <p className="text-xs text-green-400/70">Positive</p>
          </div>
          <div className="p-2 rounded-lg bg-gray-500/10 border border-gray-500/20">
            <p className="text-lg font-semibold text-gray-400">{stats.byRating.neutral}</p>
            <p className="text-xs text-gray-400/70">Neutral</p>
          </div>
          <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
            <p className="text-lg font-semibold text-red-400">{stats.byRating.negative}</p>
            <p className="text-xs text-red-400/70">Negative</p>
          </div>
        </div>
      )}

      {/* Trend & Summary */}
      {stats && summary && (
        <div className="p-3 rounded-lg bg-empire-card border border-empire-border">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-empire-text-muted uppercase tracking-wider">7-Day Summary</span>
            <div className={cn('flex items-center gap-1 text-xs', getTrendColor(stats.recentTrend))}>
              <TrendIcon className="w-3 h-3" />
              <span className="capitalize">{stats.recentTrend}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-empire-text-muted">Total</span>
              <span className="text-empire-text">{summary.totalFeedback}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-empire-text-muted">Corrections</span>
              <span className="text-empire-text">{summary.correctionsCount}</span>
            </div>
          </div>
          {summary.mostCommonType && (
            <p className="mt-2 text-xs text-empire-text-muted">
              Most common: {getFeedbackTypeLabel(summary.mostCommonType as FeedbackType)}
            </p>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="space-y-2">
        <div className="flex items-center gap-1 text-xs text-empire-text-muted">
          <Filter className="w-3 h-3" />
          <span>Filters</span>
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as FeedbackType | '')}
          className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
        >
          <option value="">All Types</option>
          {FEEDBACK_TYPES.map((type) => (
            <option key={type.id} value={type.id}>{type.label}</option>
          ))}
        </select>
        <select
          value={ratingFilter}
          onChange={(e) => setRatingFilter(e.target.value as 'all' | 'positive' | 'neutral' | 'negative')}
          className="w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text text-sm"
        >
          <option value="all">All Ratings</option>
          <option value="positive">Positive</option>
          <option value="neutral">Neutral</option>
          <option value="negative">Negative</option>
        </select>
      </div>

      {/* Feedback List */}
      <div className="space-y-2">
        <label className="text-xs text-empire-text-muted uppercase tracking-wider">Recent Feedback</label>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-empire-primary" />
          </div>
        ) : feedbackList.length === 0 ? (
          <div className="text-center py-6 text-empire-text-muted">
            <MessageSquareHeart className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No feedback yet</p>
            <p className="text-xs mt-1">Submit feedback to help improve AI responses</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[250px] overflow-y-auto">
            {feedbackList.slice(0, 20).map((feedback) => (
              <div
                key={feedback.id}
                className="p-2 rounded-lg bg-empire-card border border-empire-border text-sm"
              >
                <div className="flex items-start gap-2">
                  {feedback.rating === 1 ? (
                    <ThumbsUp className="w-3 h-3 text-green-400 mt-1 flex-shrink-0" />
                  ) : feedback.rating === -1 ? (
                    <ThumbsDown className="w-3 h-3 text-red-400 mt-1 flex-shrink-0" />
                  ) : (
                    <Minus className="w-3 h-3 text-gray-400 mt-1 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn(
                        'px-1.5 py-0.5 rounded text-xs',
                        feedback.feedbackType === 'kb_chat_rating' && 'bg-blue-500/20 text-blue-400',
                        feedback.feedbackType === 'classification_correction' && 'bg-purple-500/20 text-purple-400',
                        feedback.feedbackType === 'asset_reclassification' && 'bg-yellow-500/20 text-yellow-400',
                        feedback.feedbackType === 'response_correction' && 'bg-orange-500/20 text-orange-400',
                        feedback.feedbackType === 'general_feedback' && 'bg-gray-500/20 text-gray-400'
                      )}>
                        {getFeedbackTypeLabel(feedback.feedbackType as FeedbackType)}
                      </span>
                    </div>
                    {feedback.feedbackText && (
                      <p className="text-empire-text-muted line-clamp-2">{feedback.feedbackText}</p>
                    )}
                    {feedback.queryText && !feedback.feedbackText && (
                      <p className="text-empire-text-muted line-clamp-2 italic">{feedback.queryText}</p>
                    )}
                    {feedback.createdAt && (
                      <p className="text-xs text-empire-text-muted/50 mt-1">
                        {new Date(feedback.createdAt).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Submit Modal */}
      {showSubmitModal && (
        <FeedbackSubmitModal
          onClose={() => setShowSubmitModal(false)}
          onSubmit={handleFeedbackSubmitted}
        />
      )}
    </div>
  )
}

// ============================================================================
// CKO Message Component
// ============================================================================

interface CKOMessageBubbleProps {
  message: CKOMessage
  onRate?: (messageId: string, rating: -1 | 1) => void
  onAnswerClarification?: (messageId: string, answer: string) => void
  onSkipClarification?: (messageId: string) => void
}

function CKOMessageBubble({
  message,
  onRate,
  onAnswerClarification,
  onSkipClarification
}: CKOMessageBubbleProps) {
  const [showSources, setShowSources] = useState(false)
  const [ratingSubmitted, setRatingSubmitted] = useState(message.rating !== undefined && message.rating !== 0)

  const handleRate = (rating: -1 | 1) => {
    if (ratingSubmitted || !onRate) return
    onRate(message.id, rating)
    setRatingSubmitted(true)
  }

  // Parse clarification options from clarification_type if present
  const clarificationOptions = message.clarificationType?.split(',').map(s => s.trim()) || []

  return (
    <div
      className={cn(
        'flex gap-3',
        message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
        message.role === 'user'
          ? 'bg-empire-primary/20'
          : message.isClarification
          ? 'bg-empire-warning/20'
          : 'bg-empire-accent/20'
      )}>
        {message.role === 'user' ? (
          <User className="w-4 h-4 text-empire-primary" />
        ) : (
          <Bot className={cn(
            'w-4 h-4',
            message.isClarification ? 'text-empire-warning' : 'text-empire-accent'
          )} />
        )}
      </div>

      {/* Message Content */}
      <div className={cn(
        'max-w-[70%] rounded-lg p-3',
        message.role === 'user'
          ? 'bg-empire-primary text-white'
          : message.isClarification
          ? 'bg-[#FEF3C7] text-gray-900'
          : 'bg-empire-card border border-empire-border text-empire-text'
      )}>
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>

        {/* Sources - Collapsible */}
        {message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-empire-border/50">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-2 text-xs text-empire-text-muted hover:text-empire-text transition-colors"
            >
              <FileText className="w-3 h-3" />
              <span>{message.sources.length} source{message.sources.length !== 1 ? 's' : ''}</span>
              {showSources ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>

            {showSources && (
              <div className="mt-2 space-y-2">
                {message.sources.map((source, i) => (
                  <div
                    key={i}
                    className="p-2 rounded bg-empire-bg/50 text-xs"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <ExternalLink className="w-3 h-3 text-empire-primary flex-shrink-0" />
                      <span className="font-medium text-empire-text truncate">{source.title}</span>
                      <span className="text-empire-text-muted ml-auto">
                        {Math.round(source.relevanceScore * 100)}%
                      </span>
                    </div>
                    <p className="text-empire-text-muted line-clamp-2">{source.snippet}</p>
                    {source.pageNumber && (
                      <p className="text-empire-text-muted mt-1">Page {source.pageNumber}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Rating */}
        {message.role === 'cko' && !message.isClarification && (
          <div className="mt-3 pt-3 border-t border-empire-border/50 flex items-center gap-2">
            <button
              onClick={() => handleRate(1)}
              disabled={ratingSubmitted}
              className={cn(
                'p-1.5 rounded transition-colors',
                message.rating === 1
                  ? 'bg-green-500/20 text-green-400'
                  : ratingSubmitted
                  ? 'opacity-50 cursor-not-allowed text-empire-text-muted'
                  : 'hover:bg-empire-border text-empire-text-muted hover:text-green-400'
              )}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => handleRate(-1)}
              disabled={ratingSubmitted}
              className={cn(
                'p-1.5 rounded transition-colors',
                message.rating === -1
                  ? 'bg-red-500/20 text-red-400'
                  : ratingSubmitted
                  ? 'opacity-50 cursor-not-allowed text-empire-text-muted'
                  : 'hover:bg-empire-border text-empire-text-muted hover:text-red-400'
              )}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Clarification buttons */}
        {message.isClarification && message.clarificationStatus === 'pending' && (
          <div className="mt-3 flex flex-wrap gap-2">
            {clarificationOptions.length > 0 ? (
              clarificationOptions.map((option) => (
                <button
                  key={option}
                  onClick={() => onAnswerClarification?.(message.id, option)}
                  className="px-3 py-1.5 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800 transition-colors"
                >
                  {option}
                </button>
              ))
            ) : (
              // Default department options for classification clarifications
              DEPARTMENTS.slice(0, 4).map((dept) => (
                <button
                  key={dept.id}
                  onClick={() => onAnswerClarification?.(message.id, dept.id)}
                  className="px-3 py-1.5 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800 transition-colors"
                >
                  {dept.label}
                </button>
              ))
            )}
            <button
              onClick={() => onSkipClarification?.(message.id)}
              className="px-3 py-1.5 rounded-lg bg-gray-200 text-gray-700 text-sm hover:bg-gray-300 transition-colors"
            >
              Skip
            </button>
          </div>
        )}

        {/* Clarification answered/skipped indicator */}
        {message.isClarification && message.clarificationStatus !== 'pending' && (
          <div className="mt-2 text-xs text-empire-text-muted">
            {message.clarificationStatus === 'answered' && (
              <span className="text-green-600">Answered: {message.clarificationAnswer}</span>
            )}
            {message.clarificationStatus === 'skipped' && (
              <span className="text-gray-500">Skipped</span>
            )}
            {message.clarificationStatus === 'auto_skipped' && (
              <span className="text-gray-500">Auto-skipped</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// CKO Conversation Component
// ============================================================================

function CKOConversation() {
  const {
    activeSessionId,
    sessions,
    messages,
    isStreaming,
    streamingContent,
    connectionStatus,
    degradationMessage,
    pendingClarificationsCount,
    setActiveSession,
    setSessions,
    addSession,
    deleteSession,
    setMessages,
    addMessage,
    updateMessage,
    setStreaming,
    setConnectionStatus,
    setPendingClarifications
  } = useAIStudioStore()

  const [inputValue, setInputValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showSessionList, setShowSessionList] = useState(true)
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const maxRetries = 3

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Load pending clarifications count on mount
  useEffect(() => {
    const loadClarifications = async () => {
      try {
        const result = await getPendingClarificationsCount()
        setPendingClarifications(result.count, result.has_overdue)
      } catch (err) {
        console.error('Failed to load clarifications:', err)
      }
    }
    loadClarifications()
  }, [setPendingClarifications])

  // Load sessions on mount
  useEffect(() => {
    const loadSessions = async () => {
      setConnectionStatus('connecting')
      try {
        const apiSessions = await listCKOSessions({ limit: 50 })
        // Transform API response to store format
        const transformedSessions = apiSessions.map(s => ({
          id: s.id,
          title: s.title,
          messageCount: s.message_count,
          pendingClarifications: s.pending_clarifications,
          contextSummary: s.context_summary,
          createdAt: s.created_at,
          updatedAt: s.updated_at,
          lastMessageAt: s.last_message_at
        }))
        setSessions(transformedSessions)
        setConnectionStatus('connected')
      } catch (err) {
        console.error('Failed to load sessions:', err)
        setConnectionStatus('disconnected')
      }
    }
    loadSessions()
  }, [setSessions, setConnectionStatus])

  // Load messages when session changes
  useEffect(() => {
    const loadMessages = async () => {
      if (!activeSessionId) {
        setMessages([])
        return
      }
      try {
        const msgs = await getCKOMessages(activeSessionId)
        // Transform API response to store format
        const transformedMessages: CKOMessage[] = msgs.map(msg => ({
          id: msg.id,
          sessionId: msg.session_id,
          role: msg.role,
          content: msg.content,
          isClarification: msg.is_clarification,
          clarificationType: msg.clarification_type,
          clarificationStatus: msg.clarification_status,
          clarificationAnswer: msg.clarification_answer,
          sources: msg.sources.map(s => ({
            docId: s.doc_id,
            title: s.title,
            snippet: s.snippet,
            relevanceScore: s.relevance_score,
            pageNumber: s.page_number
          })),
          actionsPerformed: msg.actions_performed.map(a => ({
            action: a.action,
            params: a.params,
            result: a.result
          })),
          rating: msg.rating,
          ratingFeedback: msg.rating_feedback,
          createdAt: msg.created_at
        }))
        setMessages(transformedMessages)
      } catch (err) {
        console.error('Failed to load messages:', err)
        setError('Failed to load conversation history')
      }
    }
    loadMessages()
  }, [activeSessionId, setMessages])

  // Create new chat
  const handleNewChat = useCallback(async () => {
    try {
      setError(null)
      const session = await createCKOSession()
      addSession({
        id: session.id,
        title: session.title,
        messageCount: session.message_count,
        pendingClarifications: session.pending_clarifications,
        contextSummary: session.context_summary,
        createdAt: session.created_at,
        updatedAt: session.updated_at,
        lastMessageAt: session.last_message_at
      })
      setActiveSession(session.id)
      setMessages([])
    } catch (err) {
      console.error('Failed to create session:', err)
      setError('Failed to create new chat')
    }
  }, [addSession, setActiveSession, setMessages])

  // Delete a session
  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      setDeletingSessionId(sessionId)
      await deleteCKOSession(sessionId)
      deleteSession(sessionId)
    } catch (err) {
      console.error('Failed to delete session:', err)
      setError('Failed to delete conversation')
    } finally {
      setDeletingSessionId(null)
    }
  }, [deleteSession])

  // Switch to a session
  const handleSwitchSession = useCallback((sessionId: string) => {
    if (sessionId !== activeSessionId) {
      setActiveSession(sessionId)
    }
  }, [activeSessionId, setActiveSession])

  // Send message with streaming
  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || isStreaming) return

    setError(null)
    const content = inputValue.trim()
    setInputValue('')

    try {
      // Create session if none exists
      let sessionId = activeSessionId
      if (!sessionId) {
        const session = await createCKOSession({ title: content.slice(0, 50) })
        sessionId = session.id
        addSession({
          id: session.id,
          title: session.title,
          messageCount: session.message_count,
          pendingClarifications: session.pending_clarifications,
          contextSummary: session.context_summary,
          createdAt: session.created_at,
          updatedAt: session.updated_at,
          lastMessageAt: session.last_message_at
        })
        setActiveSession(sessionId)
      }

      // Add user message
      const userMessage: CKOMessage = {
        id: crypto.randomUUID(),
        sessionId,
        role: 'user',
        content,
        isClarification: false,
        sources: [],
        actionsPerformed: [],
        createdAt: new Date().toISOString()
      }
      addMessage(userMessage)

      // Create placeholder for CKO response
      const ckoMessageId = crypto.randomUUID()
      const ckoMessage: CKOMessage = {
        id: ckoMessageId,
        sessionId,
        role: 'cko',
        content: '',
        isClarification: false,
        sources: [],
        actionsPerformed: [],
        createdAt: new Date().toISOString()
      }
      addMessage(ckoMessage)
      setStreaming(true, '')

      // Create abort controller
      abortControllerRef.current = new AbortController()

      // Stream response
      let fullContent = ''
      const sources: CKOMessage['sources'] = []
      const actions: CKOMessage['actionsPerformed'] = []
      let actualMessageId = ckoMessageId

      try {
        for await (const chunk of streamCKOMessage(sessionId, { content })) {
          // Check if aborted
          if (abortControllerRef.current?.signal.aborted) {
            break
          }

          if (chunk.type === 'token' && chunk.content) {
            fullContent += chunk.content
            setStreaming(true, fullContent)
          } else if (chunk.type === 'source' && chunk.source) {
            sources.push({
              docId: chunk.source.doc_id,
              title: chunk.source.title,
              snippet: chunk.source.snippet,
              relevanceScore: chunk.source.relevance_score,
              pageNumber: chunk.source.page_number
            })
          } else if (chunk.type === 'action' && chunk.action) {
            actions.push({
              action: chunk.action.action,
              params: chunk.action.params,
              result: chunk.action.result
            })
          } else if (chunk.type === 'done') {
            if (chunk.message_id) {
              actualMessageId = chunk.message_id as `${string}-${string}-${string}-${string}-${string}`
            }
            break
          } else if (chunk.type === 'error') {
            setError(chunk.error || 'Stream error occurred')
            break
          }
        }

        // Update message with final content
        updateMessage(ckoMessageId, {
          id: actualMessageId,
          content: fullContent,
          sources,
          actionsPerformed: actions
        })

        // Refresh clarifications count
        const clarifications = await getPendingClarificationsCount()
        setPendingClarifications(clarifications.count, clarifications.has_overdue)

      } catch (streamErr: unknown) {
        console.error('Stream error:', streamErr)
        const errorMessage = streamErr instanceof Error ? streamErr.message : 'Unknown error'

        // Determine error type and update connection status
        if (errorMessage.includes('network') || errorMessage.includes('fetch') || errorMessage.includes('Failed to fetch')) {
          setConnectionStatus('disconnected')
          setError('Connection lost. Please check your network and try again.')
        } else if (errorMessage.includes('timeout') || errorMessage.includes('503')) {
          setConnectionStatus('degraded', 'Server is experiencing high load')
          setError('Server is busy. Your request may take longer than usual.')
        } else {
          setError('Failed to get response. Please try again.')
        }

        setLastFailedMessage(content)
        updateMessage(ckoMessageId, {
          content: fullContent || 'Error: Failed to get response'
        })
      } finally {
        setStreaming(false, '')
        abortControllerRef.current = null
      }

    } catch (err: unknown) {
      console.error('Send error:', err)
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'

      // Determine error type and provide helpful message
      if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
        setConnectionStatus('disconnected')
        setError('Unable to connect. Please check your internet connection.')
      } else if (errorMessage.includes('session') || errorMessage.includes('401')) {
        setError('Session expired. Please refresh the page to continue.')
      } else {
        setError('Failed to send message. Please try again.')
      }

      setLastFailedMessage(content)
      setStreaming(false, '')
    }
  }, [
    inputValue,
    isStreaming,
    activeSessionId,
    addSession,
    setActiveSession,
    addMessage,
    updateMessage,
    setStreaming,
    setConnectionStatus,
    setPendingClarifications
  ])

  // Handle rating
  const handleRate = useCallback(async (messageId: string, rating: -1 | 1) => {
    try {
      await rateCKOMessage(messageId, rating)
      updateMessage(messageId, { rating })
    } catch (err) {
      console.error('Failed to rate message:', err)
      setError('Failed to submit rating')
    }
  }, [updateMessage])

  // Handle clarification answer
  const handleAnswerClarification = useCallback(async (messageId: string, answer: string) => {
    try {
      await answerCKOClarification(messageId, answer)
      updateMessage(messageId, {
        clarificationStatus: 'answered',
        clarificationAnswer: answer
      })
      // Refresh clarifications count
      const result = await getPendingClarificationsCount()
      setPendingClarifications(result.count, result.has_overdue)
    } catch (err) {
      console.error('Failed to answer clarification:', err)
      setError('Failed to submit answer')
    }
  }, [updateMessage, setPendingClarifications])

  // Handle skip clarification
  const handleSkipClarification = useCallback(async (messageId: string) => {
    try {
      await skipCKOClarification(messageId)
      updateMessage(messageId, { clarificationStatus: 'skipped' })
      // Refresh clarifications count
      const result = await getPendingClarificationsCount()
      setPendingClarifications(result.count, result.has_overdue)
    } catch (err) {
      console.error('Failed to skip clarification:', err)
      setError('Failed to skip clarification')
    }
  }, [updateMessage, setPendingClarifications])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Get display content for streaming message
  const getMessageContent = (message: CKOMessage) => {
    if (isStreaming && message === messages[messages.length - 1] && message.role === 'cko') {
      return streamingContent || message.content
    }
    return message.content
  }

  // Format date for display
  const formatSessionDate = (dateStr: string | null) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="flex h-full">
      {/* Session List Sidebar */}
      <div className={cn(
        "border-r border-empire-border bg-empire-sidebar flex flex-col transition-all duration-200",
        showSessionList ? "w-64" : "w-0"
      )}>
        {showSessionList && (
          <>
            {/* Sidebar Header */}
            <div className="p-3 border-b border-empire-border flex items-center justify-between">
              <h3 className="text-sm font-medium text-empire-text">Conversations</h3>
              <button
                onClick={() => setShowSessionList(false)}
                className="p-1 rounded hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors"
                title="Hide sidebar"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </div>

            {/* Session List */}
            <div className="flex-1 overflow-y-auto">
              {sessions.length === 0 ? (
                <div className="p-4 text-center text-empire-text-muted text-sm">
                  No conversations yet
                </div>
              ) : (
                <div className="py-1">
                  {sessions.map((session) => (
                    <div
                      key={session.id}
                      className={cn(
                        "group px-3 py-2 mx-1 rounded-lg cursor-pointer transition-colors flex items-center justify-between",
                        activeSessionId === session.id
                          ? "bg-empire-primary/10 border border-empire-primary/20"
                          : "hover:bg-empire-border/50"
                      )}
                      onClick={() => handleSwitchSession(session.id)}
                    >
                      <div className="flex-1 min-w-0 mr-2">
                        <div className="flex items-center gap-2">
                          <MessageSquare className="w-3.5 h-3.5 text-empire-text-muted flex-shrink-0" />
                          <span className={cn(
                            "text-sm truncate",
                            activeSessionId === session.id ? "text-empire-text font-medium" : "text-empire-text-muted"
                          )}>
                            {session.title || 'New Chat'}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5 ml-5">
                          <span className="text-xs text-empire-text-muted/70">
                            {formatSessionDate(session.lastMessageAt || session.createdAt)}
                          </span>
                          {session.messageCount > 0 && (
                            <span className="text-xs text-empire-text-muted/70">
                              {session.messageCount} msg{session.messageCount !== 1 ? 's' : ''}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Delete button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDeleteSession(session.id)
                        }}
                        disabled={deletingSessionId === session.id}
                        className={cn(
                          "p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity",
                          deletingSessionId === session.id
                            ? "text-empire-text-muted cursor-not-allowed"
                            : "text-empire-text-muted hover:text-red-400 hover:bg-red-500/10"
                        )}
                        title="Delete conversation"
                      >
                        {deletingSessionId === session.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-empire-border">
          <div className="flex items-center gap-3">
            {!showSessionList && (
              <button
                onClick={() => setShowSessionList(true)}
                className="p-2 rounded-lg hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors mr-1"
                title="Show conversations"
              >
                <PanelLeftOpen className="w-4 h-4" />
              </button>
            )}
            <div className="w-10 h-10 rounded-full bg-empire-accent/20 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-empire-accent" />
            </div>
            <div>
              <h2 className="font-semibold text-empire-text">Chief Knowledge Officer</h2>
              <p className="text-xs text-empire-text-muted">Your intelligent knowledge manager</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Connection Status Indicator */}
            <div className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
              connectionStatus === 'connected' && "bg-green-500/10 text-green-400",
              connectionStatus === 'connecting' && "bg-yellow-500/10 text-yellow-400",
              connectionStatus === 'disconnected' && "bg-red-500/10 text-red-400",
              connectionStatus === 'degraded' && "bg-orange-500/10 text-orange-400"
            )}>
              {connectionStatus === 'connected' && (
                <>
                  <Wifi className="w-3.5 h-3.5" />
                  <span>Connected</span>
                </>
              )}
              {connectionStatus === 'connecting' && (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Connecting...</span>
                </>
              )}
              {connectionStatus === 'disconnected' && (
                <>
                  <WifiOff className="w-3.5 h-3.5" />
                  <span>Disconnected</span>
                </>
              )}
              {connectionStatus === 'degraded' && (
                <>
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Degraded</span>
                </>
              )}
            </div>
            {pendingClarificationsCount > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-empire-warning/10 border border-empire-warning/20">
                <AlertCircle className="w-4 h-4 text-empire-warning" />
                <span className="text-sm text-empire-warning">
                  {pendingClarificationsCount} pending
                </span>
              </div>
            )}
            <button
              onClick={handleNewChat}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-empire-card border border-empire-border hover:border-empire-primary/50 text-empire-text text-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Chat
            </button>
          </div>
        </div>

      {/* Degradation Notice Banner */}
      {connectionStatus === 'degraded' && degradationMessage && (
        <div className="px-4 py-2 bg-orange-500/10 border-b border-orange-500/20 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0" />
          <p className="text-sm text-orange-400 flex-1">{degradationMessage}</p>
          <span className="text-xs text-orange-400/70">Some features may be limited</span>
        </div>
      )}

      {/* Disconnected Banner */}
      {connectionStatus === 'disconnected' && (
        <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 flex items-center gap-3">
          <WifiOff className="w-4 h-4 text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-400 flex-1">Unable to connect to the server. Please check your connection.</p>
          <button
            onClick={() => {
              setConnectionStatus('connecting')
              // Attempt to reconnect by reloading sessions
              listCKOSessions({ limit: 1 })
                .then(() => setConnectionStatus('connected'))
                .catch(() => setConnectionStatus('disconnected'))
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 text-xs transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Retry
          </button>
        </div>
      )}

      {/* Error Banner with Retry */}
      {error && (
        <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 flex items-center justify-between">
          <div className="flex items-center gap-2 flex-1">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-400">{error}</p>
          </div>
          <div className="flex items-center gap-2">
            {lastFailedMessage && retryCount < maxRetries && (
              <button
                onClick={() => {
                  setError(null)
                  setRetryCount(prev => prev + 1)
                  setInputValue(lastFailedMessage)
                  setLastFailedMessage(null)
                }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 text-xs transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Retry ({maxRetries - retryCount} left)
              </button>
            )}
            <button
              onClick={() => {
                setError(null)
                setLastFailedMessage(null)
                setRetryCount(0)
              }}
              className="text-red-400 hover:text-red-300"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-full bg-empire-accent/20 flex items-center justify-center mb-4">
              <Sparkles className="w-8 h-8 text-empire-accent" />
            </div>
            <h3 className="text-lg font-semibold text-empire-text mb-2">
              Welcome to AI Studio
            </h3>
            <p className="text-empire-text-muted max-w-md mb-6">
              I'm your Chief Knowledge Officer (CKO). I can help you search your knowledge base,
              explain classifications, manage assets, and answer questions about your content.
            </p>
            <div className="grid grid-cols-2 gap-3 max-w-md">
              <button
                onClick={() => setInputValue("What do you know about my documents?")}
                className="p-3 rounded-lg bg-empire-card border border-empire-border hover:border-empire-primary/50 text-left transition-colors"
              >
                <p className="text-sm text-empire-text">What do you know about my documents?</p>
              </button>
              <button
                onClick={() => setInputValue("Show me recent uploads")}
                className="p-3 rounded-lg bg-empire-card border border-empire-border hover:border-empire-primary/50 text-left transition-colors"
              >
                <p className="text-sm text-empire-text">Show me recent uploads</p>
              </button>
              <button
                onClick={() => setInputValue("What are you unsure about?")}
                className="p-3 rounded-lg bg-empire-card border border-empire-border hover:border-empire-primary/50 text-left transition-colors"
              >
                <p className="text-sm text-empire-text">What are you unsure about?</p>
              </button>
              <button
                onClick={() => setInputValue("Prioritize recent documents")}
                className="p-3 rounded-lg bg-empire-card border border-empire-border hover:border-empire-primary/50 text-left transition-colors"
              >
                <p className="text-sm text-empire-text">Prioritize recent documents</p>
              </button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <CKOMessageBubble
                key={message.id}
                message={{
                  ...message,
                  content: getMessageContent(message)
                }}
                onRate={handleRate}
                onAnswerClarification={handleAnswerClarification}
                onSkipClarification={handleSkipClarification}
              />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}

        {/* Streaming indicator */}
        {isStreaming && !streamingContent && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-empire-accent/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-empire-accent" />
            </div>
            <div className="bg-empire-card border border-empire-border rounded-lg p-3">
              <div className="flex items-center gap-2 text-empire-text-muted">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">CKO is thinking...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-empire-border">
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask CKO anything about your knowledge base..."
              rows={1}
              disabled={isStreaming}
              className={cn(
                "w-full px-4 py-3 rounded-lg bg-empire-card border border-empire-border text-empire-text placeholder:text-empire-text-muted resize-none focus:outline-none focus:border-empire-primary",
                isStreaming && "opacity-50 cursor-not-allowed"
              )}
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isStreaming}
            className={cn(
              'p-3 rounded-lg transition-colors',
              inputValue.trim() && !isStreaming
                ? 'bg-empire-primary hover:bg-empire-primary/80 text-white'
                : 'bg-empire-border text-empire-text-muted cursor-not-allowed'
            )}
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
      </div>
    </div>
  )
}

// ============================================================================
// Main AI Studio View Component
// ============================================================================

const SIDEBAR_PANELS: { id: SidebarPanel; icon: typeof Package; label: string }[] = [
  { id: 'assets', icon: Package, label: 'Assets' },
  { id: 'classifications', icon: Tags, label: 'Classifications' },
  { id: 'weights', icon: Scale, label: 'Weights' },
  { id: 'feedback', icon: MessageSquareHeart, label: 'Feedback' }
]

export function AIStudioView() {
  const { activeSidebarPanel, toggleSidebarPanel, setActiveSidebarPanel, setActiveSession } = useAIStudioStore()
  const [showGlobalSearch, setShowGlobalSearch] = useState(false)

  // Cmd+K keyboard shortcut for global search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setShowGlobalSearch(true)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Handle navigation from global search results
  const handleSearchNavigate = useCallback((result: GlobalSearchResult) => {
    setShowGlobalSearch(false)

    switch (result.type) {
      case 'session':
        // Navigate to conversation
        setActiveSession(result.id)
        break
      case 'asset':
        // Open assets panel and potentially select the asset
        setActiveSidebarPanel('assets')
        // Could dispatch an event to select specific asset in the panel
        window.dispatchEvent(new CustomEvent('ai-studio:select-asset', { detail: { assetId: result.id } }))
        break
      case 'classification':
        // Open classifications panel
        setActiveSidebarPanel('classifications')
        window.dispatchEvent(new CustomEvent('ai-studio:select-classification', { detail: { classificationId: result.id } }))
        break
      default:
        break
    }
  }, [setActiveSession, setActiveSidebarPanel])

  return (
    <div className="flex h-full bg-empire-bg">
      {/* Main Content - CKO Conversation */}
      <div className="flex-1 flex flex-col min-w-0">
        <CKOConversation />
      </div>

      {/* Collapsible Sidebar */}
      <div className="flex">
        {/* Panel Tabs */}
        <div className="w-12 border-l border-empire-border bg-empire-sidebar flex flex-col">
          {SIDEBAR_PANELS.map((panel) => (
            <button
              key={panel.id}
              onClick={() => toggleSidebarPanel(panel.id)}
              className={cn(
                'p-3 transition-colors relative group',
                activeSidebarPanel === panel.id
                  ? 'bg-empire-border text-empire-text'
                  : 'text-empire-text-muted hover:bg-empire-border hover:text-empire-text'
              )}
              title={panel.label}
            >
              <panel.icon className="w-5 h-5" />

              {/* Active indicator */}
              {activeSidebarPanel === panel.id && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-empire-primary rounded-r" />
              )}

              {/* Tooltip */}
              <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 px-2 py-1 rounded bg-empire-card border border-empire-border text-sm text-empire-text whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-10">
                {panel.label}
              </div>
            </button>
          ))}
        </div>

        {/* Panel Content */}
        {activeSidebarPanel && (
          <div className="w-72 border-l border-empire-border bg-empire-sidebar overflow-y-auto">
            <div className="flex items-center justify-between p-3 border-b border-empire-border">
              <span className="text-xs text-empire-text-muted uppercase tracking-wider">
                {SIDEBAR_PANELS.find((p) => p.id === activeSidebarPanel)?.label}
              </span>
              <button
                onClick={() => setActiveSidebarPanel(null)}
                className="p-1 rounded hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {activeSidebarPanel === 'assets' && <AssetsPanel />}
            {activeSidebarPanel === 'classifications' && <ClassificationsPanel />}
            {activeSidebarPanel === 'weights' && <WeightsPanel />}
            {activeSidebarPanel === 'feedback' && <FeedbackPanel />}
          </div>
        )}
      </div>

      {/* Global Search Modal */}
      <GlobalSearch
        isOpen={showGlobalSearch}
        onClose={() => setShowGlobalSearch(false)}
        onNavigate={handleSearchNavigate}
      />
    </div>
  )
}

export default AIStudioView
