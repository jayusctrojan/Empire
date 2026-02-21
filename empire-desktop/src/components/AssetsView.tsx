/**
 * AssetsView — Asset Manager + Test Sandbox
 *
 * Left panel: asset list with filters
 * Right panel: detail with Content + Test tabs
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Search,
  X,
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
  Send,
  Trash2,
  FileText,
  Table,
  Presentation,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  listAssets,
  getAssetStats,
  getAssetHistory,
  publishAsset,
  archiveAsset,
  testAssetStream,
  ASSET_TYPE_CONFIG,
  ASSET_STATUS_CONFIG,
  DEPARTMENTS,
} from '@/lib/api/assets'
import type {
  Asset,
  AssetType,
  AssetStatus,
  AssetFilters,
  AssetStatsResponse,
  AssetVersion,
  AssetTestStreamChunk,
} from '@/lib/api/assets'
import type { PipelinePhase } from '@/types/api'

// ============================================================================
// Helper Components
// ============================================================================

function StatusBadge({ status }: { status: AssetStatus }) {
  const config = ASSET_STATUS_CONFIG[status]
  const colorClasses: Record<string, string> = {
    amber: 'bg-amber-500/20 text-amber-400',
    green: 'bg-green-500/20 text-green-400',
    gray: 'bg-gray-500/20 text-gray-400',
  }
  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', colorClasses[config.color] || colorClasses.gray)}>
      {config.label}
    </span>
  )
}

function TypeBadge({ type }: { type: AssetType }) {
  const config = ASSET_TYPE_CONFIG[type]
  return (
    <span className="text-xs text-empire-text-muted">
      {config.icon} {config.label}
    </span>
  )
}

function PhaseIndicator({ phase, label }: { phase: PipelinePhase; label: string }) {
  const phaseConfig: Record<PipelinePhase, { color: string; icon: string }> = {
    analyzing: { color: 'text-blue-400', icon: 'bg-blue-400' },
    searching: { color: 'text-yellow-400', icon: 'bg-yellow-400' },
    reasoning: { color: 'text-purple-400', icon: 'bg-purple-400' },
    formatting: { color: 'text-green-400', icon: 'bg-green-400' },
  }
  const config = phaseConfig[phase] || phaseConfig.analyzing
  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      <span className={cn('w-2 h-2 rounded-full animate-pulse', config.icon)} />
      <span className={cn('text-sm', config.color)}>{label}</span>
    </div>
  )
}

const formatIcons: Record<string, typeof FileText> = {
  docx: FileText,
  xlsx: Table,
  pptx: Presentation,
  pdf: FileText,
  md: FileText,
}

function ArtifactCardInline({ chunk }: { chunk: AssetTestStreamChunk }) {
  const Icon = formatIcons[chunk.format || 'md'] || FileText
  const formatColors: Record<string, string> = {
    docx: 'border-blue-500/30 bg-blue-500/10',
    xlsx: 'border-green-500/30 bg-green-500/10',
    pptx: 'border-orange-500/30 bg-orange-500/10',
    pdf: 'border-red-500/30 bg-red-500/10',
    md: 'border-gray-500/30 bg-gray-500/10',
  }
  return (
    <div className={cn(
      'flex items-center gap-3 p-3 rounded-lg border',
      formatColors[chunk.format || 'md'] || formatColors.md
    )}>
      <Icon className="w-5 h-5 text-empire-text-muted flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{chunk.title || 'Generated Document'}</p>
        <p className="text-xs text-empire-text-muted">
          {(chunk.format || 'md').toUpperCase()}
          {chunk.sizeBytes ? ` \u00b7 ${(chunk.sizeBytes / 1024).toFixed(1)} KB` : ''}
        </p>
      </div>
    </div>
  )
}

// ============================================================================
// Test Message Types
// ============================================================================

interface TestMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  artifacts?: AssetTestStreamChunk[]
}

// ============================================================================
// Suggestion Chips
// ============================================================================

const SUGGESTION_CHIPS: Record<AssetType, string[]> = {
  skill: ['Generate a sample output', 'Show me an example DOCX'],
  prompt: ['Run this prompt with sample data', 'Explain what this prompt does'],
  workflow: ['Walk through this workflow step by step', 'Identify potential improvements'],
  command: ['Execute this command with example input', 'Explain the command parameters'],
  agent: ['Describe what this agent does', 'Generate a sample interaction'],
}

// ============================================================================
// Utilities
// ============================================================================

function relativeTime(dateStr?: string): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  if (Number.isNaN(diff)) return ''
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

// ============================================================================
// Main Component
// ============================================================================

export function AssetsView() {
  // List state
  const [assets, setAssets] = useState<Asset[]>([])
  const [stats, setStats] = useState<AssetStatsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter state
  const [filters, setFilters] = useState<AssetFilters>({})
  const [searchInput, setSearchInput] = useState('')
  const searchTimer = useRef<ReturnType<typeof setTimeout>>()

  // Detail panel state
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null)
  const [assetHistory, setAssetHistory] = useState<AssetVersion[]>([])
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'content' | 'test'>('content')
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false)

  // Action feedback
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [isActionLoading, setIsActionLoading] = useState(false)

  // Test chat state
  const [testMessages, setTestMessages] = useState<TestMessage[]>([])
  const [isTestStreaming, setIsTestStreaming] = useState(false)
  const [testStreamingContent, setTestStreamingContent] = useState('')
  const [testPhase, setTestPhase] = useState<{ phase: PipelinePhase; label: string } | null>(null)
  const [testInput, setTestInput] = useState('')
  const [testArtifacts, setTestArtifacts] = useState<AssetTestStreamChunk[]>([])
  const testMessagesEndRef = useRef<HTMLDivElement>(null)
  const testAbortRef = useRef<AbortController | null>(null)
  const isSearchInitialized = useRef(false)
  const fetchIdRef = useRef(0)
  const pendingHistoryRef = useRef<string | null>(null)

  // ============================================================================
  // Data Fetching
  // ============================================================================

  const fetchAssets = useCallback(async () => {
    const id = ++fetchIdRef.current
    setIsLoading(true)
    setError(null)
    try {
      const [listResult, statsResult] = await Promise.all([
        listAssets(filters, 0, 50),
        getAssetStats(),
      ])
      if (fetchIdRef.current !== id) return // stale response
      setAssets(listResult.assets)
      setStats(statsResult)
    } catch (err) {
      if (fetchIdRef.current !== id) return
      setError(err instanceof Error ? err.message : 'Failed to load assets')
    } finally {
      if (fetchIdRef.current === id) setIsLoading(false)
    }
  }, [filters])

  useEffect(() => {
    fetchAssets()
  }, [fetchAssets])

  // Debounced search (skip initial mount to avoid redundant fetch)
  useEffect(() => {
    if (!isSearchInitialized.current) {
      isSearchInitialized.current = true
      return
    }
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setFilters(prev => ({
        ...prev,
        search: searchInput || undefined,
      }))
    }, 300)
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current)
    }
  }, [searchInput])

  // Auto-dismiss action message
  useEffect(() => {
    if (!actionMessage) return
    const timer = setTimeout(() => setActionMessage(null), 3000)
    return () => clearTimeout(timer)
  }, [actionMessage])

  // Scroll test messages
  useEffect(() => {
    testMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [testMessages, testStreamingContent])

  // Abort in-flight test stream on unmount
  useEffect(() => {
    return () => {
      testAbortRef.current?.abort()
      testAbortRef.current = null
    }
  }, [])

  // ============================================================================
  // Handlers
  // ============================================================================

  const handleSelectAsset = async (asset: Asset) => {
    // Cancel any in-flight test stream
    testAbortRef.current?.abort()
    testAbortRef.current = null
    pendingHistoryRef.current = asset.id
    setSelectedAsset(asset)
    setIsDetailOpen(true)
    setActiveTab('content')
    setAssetHistory([])
    setIsHistoryExpanded(false)
    // Reset test chat when switching assets
    setTestMessages([])
    setTestStreamingContent('')
    setTestPhase(null)
    setTestArtifacts([])
    setIsTestStreaming(false)

    try {
      const historyResult = await getAssetHistory(asset.id)
      if (pendingHistoryRef.current === asset.id) {
        setAssetHistory(historyResult.history)
      }
    } catch {
      // Non-critical — history just won't show
    }
  }

  const handleCloseDetail = () => {
    testAbortRef.current?.abort()
    testAbortRef.current = null
    setIsDetailOpen(false)
    setSelectedAsset(null)
  }

  const handlePublish = async () => {
    if (!selectedAsset) return
    setIsActionLoading(true)
    try {
      const updated = await publishAsset(selectedAsset.id)
      setSelectedAsset(updated)
      setActionMessage({ type: 'success', text: 'Asset published successfully' })
      fetchAssets()
    } catch (err) {
      setActionMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to publish' })
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleArchive = async () => {
    if (!selectedAsset) return
    setIsActionLoading(true)
    try {
      const updated = await archiveAsset(selectedAsset.id)
      setSelectedAsset(updated)
      setActionMessage({ type: 'success', text: 'Asset archived successfully' })
      fetchAssets()
    } catch (err) {
      setActionMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to archive' })
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleSendTest = async (query: string) => {
    if (!selectedAsset || !query.trim() || isTestStreaming) return

    const controller = new AbortController()
    testAbortRef.current = controller

    const userMsg: TestMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query.trim(),
    }
    setTestMessages(prev => [...prev, userMsg])
    setTestInput('')
    setIsTestStreaming(true)
    setTestStreamingContent('')
    setTestPhase(null)
    setTestArtifacts([])

    try {
      let fullContent = ''
      const artifacts: AssetTestStreamChunk[] = []

      for await (const chunk of testAssetStream(selectedAsset.id, query.trim(), controller.signal)) {
        switch (chunk.type) {
          case 'phase':
            if (chunk.phase && chunk.label) {
              setTestPhase({ phase: chunk.phase, label: chunk.label })
            }
            break
          case 'token':
            if (chunk.content) {
              fullContent += chunk.content
              setTestStreamingContent(fullContent)
            }
            break
          case 'artifact':
            artifacts.push(chunk)
            setTestArtifacts([...artifacts])
            break
          case 'done':
            // Final message
            break
          case 'error':
            fullContent += `\n\n**Error:** ${chunk.error || 'Unknown error'}`
            break
        }
      }

      // Don't update state if stream was aborted (e.g., user switched assets)
      if (controller.signal.aborted) return

      // Skip empty responses (no content or artifacts)
      if (!fullContent && artifacts.length === 0) return

      const assistantMsg: TestMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: fullContent,
        artifacts: artifacts.length > 0 ? artifacts : undefined,
      }
      setTestMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      if (controller.signal.aborted) return // Silently ignore aborted streams
      const errorMsg: TestMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `**Error:** ${err instanceof Error ? err.message : 'Test failed'}`,
      }
      setTestMessages(prev => [...prev, errorMsg])
    } finally {
      setIsTestStreaming(false)
      setTestStreamingContent('')
      setTestPhase(null)
      setTestArtifacts([])
    }
  }

  const handleClearTest = () => {
    testAbortRef.current?.abort()
    testAbortRef.current = null
    setTestMessages([])
    setTestStreamingContent('')
    setTestPhase(null)
    setTestArtifacts([])
    setIsTestStreaming(false)
  }

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className="flex h-full">
      {/* Left Panel — Asset List */}
      <div className={cn(
        'flex flex-col h-full border-r border-empire-border bg-empire-bg transition-all',
        isDetailOpen ? 'w-[360px]' : 'flex-1'
      )}>
        {/* Stats Row */}
        {stats && (
          <div className="flex items-center gap-3 px-4 py-3 border-b border-empire-border">
            <span className="text-sm text-empire-text-muted">
              {stats.total} total
            </span>
            <StatusBadge status="draft" />
            <span className="text-xs text-empire-text-muted">{stats.byStatus.draft || 0}</span>
            <StatusBadge status="published" />
            <span className="text-xs text-empire-text-muted">{stats.byStatus.published || 0}</span>
            <StatusBadge status="archived" />
            <span className="text-xs text-empire-text-muted">{stats.byStatus.archived || 0}</span>
          </div>
        )}

        {/* Filter Bar */}
        <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-empire-border">
          <select
            aria-label="Filter by type"
            value={filters.assetType || ''}
            onChange={(e) => setFilters(prev => ({ ...prev, assetType: (e.target.value || undefined) as AssetType | undefined }))}
            className="px-2 py-1 rounded bg-empire-card border border-empire-border text-sm text-empire-text"
          >
            <option value="">All Types</option>
            {Object.entries(ASSET_TYPE_CONFIG).map(([key, cfg]) => (
              <option key={key} value={key}>{cfg.icon} {cfg.label}</option>
            ))}
          </select>

          <select
            aria-label="Filter by status"
            value={filters.status || ''}
            onChange={(e) => setFilters(prev => ({ ...prev, status: (e.target.value || undefined) as AssetStatus | undefined }))}
            className="px-2 py-1 rounded bg-empire-card border border-empire-border text-sm text-empire-text"
          >
            <option value="">All Statuses</option>
            {Object.entries(ASSET_STATUS_CONFIG).map(([key, cfg]) => (
              <option key={key} value={key}>{cfg.label}</option>
            ))}
          </select>

          <select
            aria-label="Filter by department"
            value={filters.department || ''}
            onChange={(e) => setFilters(prev => ({ ...prev, department: e.target.value || undefined }))}
            className="px-2 py-1 rounded bg-empire-card border border-empire-border text-sm text-empire-text"
          >
            <option value="">All Departments</option>
            {DEPARTMENTS.map(d => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>

          <div className="flex-1 min-w-[140px] relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-empire-text-muted" />
            <input
              type="text"
              aria-label="Search assets"
              placeholder="Search assets..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-8 pr-3 py-1 rounded bg-empire-card border border-empire-border text-sm text-empire-text placeholder-empire-text-muted"
            />
          </div>
        </div>

        {/* Asset List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 animate-spin text-empire-text-muted" />
            </div>
          ) : error ? (
            <div className="p-4 text-center text-empire-text-muted">
              <XCircle className="w-8 h-8 mx-auto mb-2 text-red-400" />
              <p className="text-sm">{error}</p>
              <button onClick={fetchAssets} className="mt-2 text-sm text-empire-primary hover:underline">
                Retry
              </button>
            </div>
          ) : assets.length === 0 ? (
            <div className="p-8 text-center text-empire-text-muted">
              <p className="text-sm">No assets found</p>
              <p className="text-xs mt-1">Upload documents to generate assets</p>
            </div>
          ) : (
            <ul className="divide-y divide-empire-border">
              {assets.map(asset => (
                <li key={asset.id}>
                  <button
                    onClick={() => handleSelectAsset(asset)}
                    className={cn(
                      'w-full text-left px-4 py-3 hover:bg-empire-card/50 transition-colors',
                      selectedAsset?.id === asset.id && 'bg-empire-card'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-empire-text truncate">
                          {asset.title}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <TypeBadge type={asset.assetType} />
                          <span className="text-xs text-empire-text-muted">\u00b7</span>
                          <span className="text-xs text-empire-text-muted">v{asset.version}</span>
                          <span className="text-xs text-empire-text-muted">\u00b7</span>
                          <span className="text-xs text-empire-text-muted">
                            {relativeTime(asset.updatedAt || asset.createdAt)}
                          </span>
                        </div>
                      </div>
                      <StatusBadge status={asset.status} />
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Right Panel — Detail */}
      {isDetailOpen && selectedAsset && (
        <div className="flex-1 flex flex-col h-full bg-empire-bg overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-empire-border">
            <div className="flex items-center gap-2 min-w-0">
              <TypeBadge type={selectedAsset.assetType} />
              <h2 className="text-sm font-semibold text-empire-text truncate">
                {selectedAsset.title}
              </h2>
              <StatusBadge status={selectedAsset.status} />
            </div>
            <button
              onClick={handleCloseDetail}
              aria-label="Close detail panel"
              className="p-1.5 rounded-lg hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Tabs */}
          <div role="tablist" className="flex border-b border-empire-border">
            <button
              id="tab-content"
              role="tab"
              aria-selected={activeTab === 'content'}
              aria-controls="tab-panel-content"
              onClick={() => setActiveTab('content')}
              className={cn(
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                activeTab === 'content'
                  ? 'border-empire-primary text-empire-primary'
                  : 'border-transparent text-empire-text-muted hover:text-empire-text'
              )}
            >
              Content
            </button>
            <button
              id="tab-test"
              role="tab"
              aria-selected={activeTab === 'test'}
              aria-controls="tab-panel-test"
              onClick={() => setActiveTab('test')}
              className={cn(
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                activeTab === 'test'
                  ? 'border-empire-primary text-empire-primary'
                  : 'border-transparent text-empire-text-muted hover:text-empire-text'
              )}
            >
              Test
            </button>
          </div>

          {/* Action Feedback */}
          {actionMessage && (
            <div className={cn(
              'flex items-center gap-2 px-4 py-2 text-sm',
              actionMessage.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
            )}>
              {actionMessage.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              {actionMessage.text}
            </div>
          )}

          {/* Tab Content */}
          {activeTab === 'content' ? (
            <div id="tab-panel-content" role="tabpanel" aria-labelledby="tab-content" className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Asset Content */}
              <div>
                <h3 className="text-xs uppercase tracking-wider text-empire-text-muted mb-2">Content</h3>
                <pre className="p-3 rounded-lg bg-empire-card border border-empire-border text-sm text-empire-text font-mono whitespace-pre-wrap break-words max-h-[400px] overflow-y-auto">
                  {selectedAsset.content}
                </pre>
              </div>

              {/* Metadata */}
              <div>
                <h3 className="text-xs uppercase tracking-wider text-empire-text-muted mb-2">Metadata</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="text-empire-text-muted">Department</div>
                  <div className="text-empire-text">
                    {DEPARTMENTS.find(d => d.value === selectedAsset.department)?.label || selectedAsset.department}
                  </div>
                  {selectedAsset.classificationConfidence != null && (
                    <>
                      <div className="text-empire-text-muted">Confidence</div>
                      <div className="text-empire-text">
                        {Math.round(selectedAsset.classificationConfidence * 100)}%
                      </div>
                    </>
                  )}
                  {selectedAsset.sourceDocumentTitle && (
                    <>
                      <div className="text-empire-text-muted">Source Document</div>
                      <div className="text-empire-text truncate">{selectedAsset.sourceDocumentTitle}</div>
                    </>
                  )}
                  <div className="text-empire-text-muted">Format</div>
                  <div className="text-empire-text">{selectedAsset.format.toUpperCase()}</div>
                  <div className="text-empire-text-muted">Version</div>
                  <div className="text-empire-text">v{selectedAsset.version}</div>
                  {selectedAsset.createdAt && (
                    <>
                      <div className="text-empire-text-muted">Created</div>
                      <div className="text-empire-text">{new Date(selectedAsset.createdAt).toLocaleDateString()}</div>
                    </>
                  )}
                  {selectedAsset.updatedAt && (
                    <>
                      <div className="text-empire-text-muted">Updated</div>
                      <div className="text-empire-text">{new Date(selectedAsset.updatedAt).toLocaleDateString()}</div>
                    </>
                  )}
                </div>
              </div>

              {/* Version History */}
              {assetHistory.length > 0 && (
                <div>
                  <button
                    onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
                    className="flex items-center gap-1 text-xs uppercase tracking-wider text-empire-text-muted hover:text-empire-text"
                  >
                    {isHistoryExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    Version History ({assetHistory.length})
                  </button>
                  {isHistoryExpanded && (
                    <ul className="mt-2 space-y-2">
                      {assetHistory.map(v => (
                        <li key={v.id} className="p-2 rounded bg-empire-card border border-empire-border text-sm">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-empire-text">v{v.version}</span>
                            <span className="text-xs text-empire-text-muted">
                              {v.createdAt ? new Date(v.createdAt).toLocaleDateString() : ''}
                            </span>
                          </div>
                          {v.isCurrent && (
                            <span className="text-xs text-green-400">Current</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2">
                {selectedAsset.status === 'draft' && (
                  <>
                    <button
                      onClick={handlePublish}
                      disabled={isActionLoading}
                      className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
                    >
                      {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Publish'}
                    </button>
                    <button
                      onClick={handleArchive}
                      disabled={isActionLoading}
                      className="px-4 py-2 rounded-lg bg-empire-card hover:bg-empire-border text-empire-text-muted text-sm font-medium transition-colors disabled:opacity-50"
                    >
                      {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Archive'}
                    </button>
                  </>
                )}
                {selectedAsset.status === 'published' && (
                  <button
                    onClick={handleArchive}
                    disabled={isActionLoading}
                    className="px-4 py-2 rounded-lg bg-empire-card hover:bg-empire-border text-empire-text-muted text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Archive'}
                  </button>
                )}
                {selectedAsset.status === 'archived' && (
                  <span className="text-sm text-empire-text-muted italic">This asset is archived (read-only)</span>
                )}
              </div>
            </div>
          ) : (
            /* Test Tab */
            <div id="tab-panel-test" role="tabpanel" aria-labelledby="tab-test" className="flex-1 flex flex-col overflow-hidden">
              {/* Test Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {testMessages.length === 0 && !isTestStreaming && (
                  <div className="text-center py-8">
                    <p className="text-sm text-empire-text-muted mb-4">
                      Test this {selectedAsset.assetType} asset with the CKO pipeline
                    </p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {(SUGGESTION_CHIPS[selectedAsset.assetType] || []).map(chip => (
                        <button
                          key={chip}
                          onClick={() => handleSendTest(chip)}
                          className="px-3 py-1.5 rounded-full bg-empire-card border border-empire-border text-sm text-empire-text-muted hover:text-empire-text hover:border-empire-primary/50 transition-colors"
                        >
                          {chip}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {testMessages.map(msg => (
                  <div
                    key={msg.id}
                    className={cn(
                      'max-w-[85%] rounded-lg px-3 py-2',
                      msg.role === 'user'
                        ? 'ml-auto bg-empire-primary text-white'
                        : 'bg-empire-card text-empire-text'
                    )}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    {msg.artifacts && msg.artifacts.length > 0 && (
                      <div className="mt-2 space-y-2">
                        {msg.artifacts.map((a, i) => (
                          <ArtifactCardInline key={i} chunk={a} />
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {/* Streaming state */}
                {isTestStreaming && (
                  <div className="max-w-[85%] rounded-lg px-3 py-2 bg-empire-card text-empire-text">
                    {testPhase && <PhaseIndicator phase={testPhase.phase} label={testPhase.label} />}
                    {testStreamingContent && (
                      <p className="text-sm whitespace-pre-wrap">
                        {testStreamingContent}
                        <span className="inline-block w-2 h-4 ml-0.5 bg-empire-primary animate-pulse" />
                      </p>
                    )}
                    {testArtifacts.length > 0 && (
                      <div className="mt-2 space-y-2">
                        {testArtifacts.map((a, i) => (
                          <ArtifactCardInline key={i} chunk={a} />
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div ref={testMessagesEndRef} />
              </div>

              {/* Test Controls */}
              <div className="border-t border-empire-border p-3">
                {testMessages.length > 0 && (
                  <div className="flex justify-end mb-2">
                    <button
                      onClick={handleClearTest}
                      className="flex items-center gap-1 text-xs text-empire-text-muted hover:text-empire-text"
                    >
                      <Trash2 className="w-3 h-3" /> Clear test
                    </button>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <input
                    aria-label="Test query input"
                    type="text"
                    placeholder="Type a test query..."
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSendTest(testInput)
                      }
                    }}
                    disabled={isTestStreaming}
                    className="flex-1 px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-sm text-empire-text placeholder-empire-text-muted disabled:opacity-50"
                  />
                  <button
                    onClick={() => handleSendTest(testInput)}
                    disabled={isTestStreaming || !testInput.trim()}
                    aria-label={isTestStreaming ? 'Sending test query' : 'Send test query'}
                    className="p-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white disabled:opacity-50 transition-colors"
                  >
                    {isTestStreaming ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AssetsView
