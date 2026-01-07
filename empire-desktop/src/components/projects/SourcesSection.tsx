/**
 * SourcesSection Component
 * NotebookLM-style source management for projects
 * Supports files, URLs, and YouTube with real-time status updates
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Plus,
  Upload,
  Link,
  Youtube,
  FileText,
  Globe,
  Trash2,
  RefreshCw,
  Search,
  Filter,
  X,
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
  File,
  Image,
  Music,
  Video,
  Archive,
  Table,
  Presentation,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  listSources,
  addFileSources,
  addUrlSources,
  deleteSource,
  retrySource,
  isValidUrl,
  type SourceSortField,
  type SortOrder,
} from '@/lib/api'
import type { ProjectSource, SourceStatus, SourceType } from '@/types'

// Source type icons
const SOURCE_TYPE_ICONS: Record<SourceType, React.ElementType> = {
  file: FileText,
  url: Globe,
  youtube: Youtube,
}

// File type to icon mapping
const FILE_EXTENSION_ICONS: Record<string, React.ElementType> = {
  pdf: FileText,
  doc: FileText,
  docx: FileText,
  txt: FileText,
  md: FileText,
  rtf: FileText,
  xls: Table,
  xlsx: Table,
  csv: Table,
  ppt: Presentation,
  pptx: Presentation,
  key: Presentation,
  jpg: Image,
  jpeg: Image,
  png: Image,
  gif: Image,
  webp: Image,
  svg: Image,
  mp3: Music,
  wav: Music,
  m4a: Music,
  flac: Music,
  mp4: Video,
  mov: Video,
  avi: Video,
  mkv: Video,
  webm: Video,
  zip: Archive,
  tar: Archive,
  gz: Archive,
  '7z': Archive,
}

// File type colors
const FILE_TYPE_COLORS: Record<string, string> = {
  pdf: 'bg-red-500/20 text-red-400',
  doc: 'bg-blue-500/20 text-blue-400',
  docx: 'bg-blue-500/20 text-blue-400',
  txt: 'bg-gray-500/20 text-gray-400',
  md: 'bg-gray-500/20 text-gray-400',
  xls: 'bg-green-500/20 text-green-400',
  xlsx: 'bg-green-500/20 text-green-400',
  csv: 'bg-green-500/20 text-green-400',
  ppt: 'bg-orange-500/20 text-orange-400',
  pptx: 'bg-orange-500/20 text-orange-400',
  jpg: 'bg-purple-500/20 text-purple-400',
  png: 'bg-purple-500/20 text-purple-400',
  mp3: 'bg-pink-500/20 text-pink-400',
  wav: 'bg-pink-500/20 text-pink-400',
  mp4: 'bg-cyan-500/20 text-cyan-400',
  mov: 'bg-cyan-500/20 text-cyan-400',
  zip: 'bg-yellow-500/20 text-yellow-400',
  youtube: 'bg-red-500/20 text-red-400',
  url: 'bg-blue-500/20 text-blue-400',
  default: 'bg-gray-500/20 text-gray-400',
}

// Status badge configurations
const STATUS_CONFIG: Record<SourceStatus, { icon: React.ElementType; color: string; label: string }> = {
  pending: { icon: Clock, color: 'bg-gray-500/20 text-gray-400', label: 'Pending' },
  processing: { icon: Loader2, color: 'bg-blue-500/20 text-blue-400', label: 'Processing' },
  ready: { icon: CheckCircle, color: 'bg-green-500/20 text-green-400', label: 'Ready' },
  failed: { icon: AlertCircle, color: 'bg-red-500/20 text-red-400', label: 'Failed' },
}

interface SourcesSectionProps {
  projectId: string
}

interface SourceStats {
  ready: number
  processing: number
  pending: number
  failed: number
  totalSize: number
}

export function SourcesSection({ projectId }: SourcesSectionProps) {
  // Sources state
  const [sources, setSources] = useState<ProjectSource[]>([])
  const [stats, setStats] = useState<SourceStats>({ ready: 0, processing: 0, pending: 0, failed: 0, totalSize: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Input state
  const [showAddPanel, setShowAddPanel] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  // Filter/sort state
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<SourceStatus | 'all'>('all')
  const [typeFilter, setTypeFilter] = useState<SourceType | 'all'>('all')
  const [sortBy, setSortBy] = useState<SourceSortField>('createdAt')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [showFilters, setShowFilters] = useState(false)

  // Delete confirmation state
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const addPanelRef = useRef<HTMLDivElement>(null)

  // Load sources
  const loadSources = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await listSources(projectId, {
        status: statusFilter !== 'all' ? statusFilter : undefined,
        sourceType: typeFilter !== 'all' ? typeFilter : undefined,
        search: searchQuery || undefined,
        sortBy,
        sortOrder,
      })
      setSources(response.data || [])
      setStats(response.stats || { ready: 0, processing: 0, pending: 0, failed: 0, totalSize: 0 })
    } catch (err) {
      console.error('Failed to load sources:', err)
      setError('Failed to load sources')
      setSources([])
    } finally {
      setIsLoading(false)
    }
  }, [projectId, statusFilter, typeFilter, searchQuery, sortBy, sortOrder])

  // Initial load and refresh on filter changes
  useEffect(() => {
    loadSources()
  }, [loadSources])

  // Poll for updates when there are processing sources
  useEffect(() => {
    const hasProcessing = sources.some(s => s.status === 'processing' || s.status === 'pending')
    if (!hasProcessing) return

    const interval = setInterval(loadSources, 5000)
    return () => clearInterval(interval)
  }, [sources, loadSources])

  // Close add panel when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (addPanelRef.current && !addPanelRef.current.contains(event.target as Node)) {
        setShowAddPanel(false)
      }
    }
    if (showAddPanel) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showAddPanel])

  // Handle file selection
  const handleFileSelect = async (fileList: FileList) => {
    const files = Array.from(fileList)
    if (files.length === 0) return

    setIsUploading(true)
    try {
      await addFileSources(projectId, files)
      await loadSources()
      setShowAddPanel(false)
    } catch (err) {
      console.error('Failed to upload files:', err)
      setError('Failed to upload files')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  // Handle URL submission
  const handleAddUrls = async () => {
    const input = urlInput.trim()
    if (!input) return

    const urlStrings = input.split(/[\s\n\r]+/).filter(Boolean)
    const validUrls = urlStrings.filter(isValidUrl)

    if (validUrls.length === 0) {
      setError('No valid URLs found')
      return
    }

    setIsUploading(true)
    try {
      await addUrlSources(projectId, validUrls)
      await loadSources()
      setUrlInput('')
      setShowAddPanel(false)
    } catch (err) {
      console.error('Failed to add URLs:', err)
      setError('Failed to add URLs')
    } finally {
      setIsUploading(false)
    }
  }

  // Handle source deletion
  const handleDelete = async (sourceId: string) => {
    try {
      await deleteSource(projectId, sourceId)
      setSources(prev => prev.filter(s => s.id !== sourceId))
      setDeleteConfirm(null)
    } catch (err) {
      console.error('Failed to delete source:', err)
      setError('Failed to delete source')
    }
  }

  // Handle retry
  const handleRetry = async (sourceId: string) => {
    try {
      await retrySource(projectId, sourceId)
      await loadSources()
    } catch (err) {
      console.error('Failed to retry source:', err)
      setError('Failed to retry source')
    }
  }

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files)
    }
  }

  // Helper functions
  const getFileExtension = (filename: string): string => {
    const parts = filename.split('.')
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : ''
  }

  const getSourceIcon = (source: ProjectSource): React.ElementType => {
    if (source.sourceType === 'youtube') return Youtube
    if (source.sourceType === 'url') return Globe
    if (source.fileName) {
      const ext = getFileExtension(source.fileName)
      return FILE_EXTENSION_ICONS[ext] || File
    }
    return SOURCE_TYPE_ICONS[source.sourceType] || File
  }

  const getSourceColor = (source: ProjectSource): string => {
    if (source.sourceType === 'youtube') return FILE_TYPE_COLORS.youtube
    if (source.sourceType === 'url') return FILE_TYPE_COLORS.url
    if (source.fileName) {
      const ext = getFileExtension(source.fileName)
      return FILE_TYPE_COLORS[ext] || FILE_TYPE_COLORS.default
    }
    return FILE_TYPE_COLORS.default
  }

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return ''
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`
  }

  const totalCount = sources.length
  const readyCount = stats.ready
  const processingCount = stats.processing + stats.pending
  const progressPercentage = totalCount > 0 ? (readyCount / totalCount) * 100 : 0

  return (
    <div className="rounded-xl border border-empire-border bg-empire-card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-medium text-empire-text">Sources</h2>
        <div className="relative" ref={addPanelRef}>
          <button
            onClick={() => setShowAddPanel(!showAddPanel)}
            className="p-1.5 rounded hover:bg-empire-border transition-colors"
            aria-label="Add sources"
          >
            <Plus className="w-5 h-5 text-empire-text-muted" />
          </button>

          {/* Add Sources Panel */}
          {showAddPanel && (
            <div className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-empire-border bg-empire-card shadow-xl z-50 p-4">
              <h3 className="text-sm font-medium text-empire-text mb-3">Add Sources</h3>

              {/* File Drop Zone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                  'border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all mb-3',
                  isDragging
                    ? 'border-empire-primary bg-empire-primary/10'
                    : 'border-empire-border hover:border-empire-primary/50'
                )}
              >
                <Upload className="w-6 h-6 mx-auto mb-2 text-empire-text-muted" />
                <p className="text-sm text-empire-text">Drop files here</p>
                <p className="text-xs text-empire-text-muted">or click to browse</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  onChange={(e) => e.target.files && handleFileSelect(e.target.files)}
                  className="hidden"
                />
              </div>

              {/* URL Input */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs text-empire-text-muted">
                  <Link className="w-3 h-3" />
                  <span>Add URLs or YouTube links</span>
                </div>
                <textarea
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleAddUrls()
                    }
                  }}
                  placeholder="Paste URLs here (one per line)..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm placeholder:text-empire-text-muted focus:outline-none focus:ring-2 focus:ring-empire-primary/50 resize-none"
                />
                <button
                  onClick={handleAddUrls}
                  disabled={!urlInput.trim() || isUploading}
                  className="w-full py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isUploading ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Adding...
                    </span>
                  ) : (
                    'Add Sources'
                  )}
                </button>
              </div>

              <p className="text-xs text-empire-text-muted mt-2">
                Supports: PDF, DOCX, YouTube, web articles, and 40+ file types
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Search and Filters */}
      {sources.length > 0 && (
        <div className="mb-4 space-y-2">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-empire-text-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search sources..."
                className="w-full pl-9 pr-3 py-2 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm placeholder:text-empire-text-muted focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
              />
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={cn(
                'px-3 py-2 rounded-lg border transition-colors',
                showFilters
                  ? 'border-empire-primary bg-empire-primary/10 text-empire-primary'
                  : 'border-empire-border text-empire-text-muted hover:text-empire-text'
              )}
            >
              <Filter className="w-4 h-4" />
            </button>
          </div>

          {/* Filter Options */}
          {showFilters && (
            <div className="flex flex-wrap gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as SourceStatus | 'all')}
                className="px-3 py-1.5 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
              >
                <option value="all">All Status</option>
                <option value="ready">Ready</option>
                <option value="processing">Processing</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>

              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as SourceType | 'all')}
                className="px-3 py-1.5 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
              >
                <option value="all">All Types</option>
                <option value="file">Files</option>
                <option value="url">Web Articles</option>
                <option value="youtube">YouTube</option>
              </select>

              <select
                value={`${sortBy}-${sortOrder}`}
                onChange={(e) => {
                  const [field, order] = e.target.value.split('-') as [SourceSortField, SortOrder]
                  setSortBy(field)
                  setSortOrder(order)
                }}
                className="px-3 py-1.5 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
              >
                <option value="createdAt-desc">Newest First</option>
                <option value="createdAt-asc">Oldest First</option>
                <option value="title-asc">Name A-Z</option>
                <option value="title-desc">Name Z-A</option>
                <option value="status-asc">Status</option>
              </select>
            </div>
          )}
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-auto p-1 hover:bg-red-500/20 rounded"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Sources Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <RefreshCw className="w-5 h-5 text-empire-text-muted animate-spin" />
        </div>
      ) : sources.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-32 text-empire-text-muted">
          <FileText className="w-8 h-8 mb-2 opacity-50" />
          <p className="text-sm">No sources added</p>
          <button
            onClick={() => setShowAddPanel(true)}
            className="mt-1 text-sm text-empire-primary hover:text-empire-primary/80"
          >
            Add your first source
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto">
          {sources.map((source) => {
            const StatusIcon = STATUS_CONFIG[source.status].icon
            const SourceIcon = getSourceIcon(source)
            const statusConfig = STATUS_CONFIG[source.status]

            return (
              <div
                key={source.id}
                className="group relative rounded-lg border border-empire-border bg-empire-sidebar p-3 hover:border-empire-primary/50 transition-colors"
              >
                {/* Actions */}
                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {source.status === 'failed' && (
                    <button
                      onClick={() => handleRetry(source.id)}
                      className="p-1 rounded hover:bg-empire-primary/20 text-empire-primary"
                      title="Retry"
                    >
                      <RefreshCw className="w-3 h-3" />
                    </button>
                  )}
                  <button
                    onClick={() => setDeleteConfirm(source.id)}
                    className="p-1 rounded hover:bg-red-500/20 text-empire-text-muted hover:text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>

                {/* Delete Confirmation */}
                {deleteConfirm === source.id && (
                  <div className="absolute inset-0 rounded-lg bg-empire-card border border-empire-border flex flex-col items-center justify-center p-2 z-10">
                    <p className="text-xs text-empire-text mb-2">Delete this source?</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-2 py-1 text-xs rounded border border-empire-border hover:bg-empire-border"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleDelete(source.id)}
                        className="px-2 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                )}

                {/* Type Icon Badge */}
                <div className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase mb-2', getSourceColor(source))}>
                  <SourceIcon className="w-3 h-3" />
                  {source.sourceType === 'youtube' ? 'YT' : source.sourceType === 'url' ? 'URL' : getFileExtension(source.fileName || '') || 'FILE'}
                </div>

                {/* Title */}
                <p className="text-xs font-medium text-empire-text truncate pr-6 mb-1" title={source.title}>
                  {source.title}
                </p>

                {/* Metadata */}
                <div className="text-xs text-empire-text-muted mb-2">
                  {source.fileSize && <span>{formatFileSize(source.fileSize)}</span>}
                  {source.metadata?.pageCount && <span> • {source.metadata.pageCount} pages</span>}
                  {source.metadata?.duration && <span> • {source.metadata.duration}</span>}
                  {source.metadata?.channel && <span className="block truncate">{source.metadata.channel}</span>}
                </div>

                {/* Status Badge */}
                <div className="flex items-center gap-1.5">
                  <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px]', statusConfig.color)}>
                    <StatusIcon className={cn('w-3 h-3', source.status === 'processing' && 'animate-spin')} />
                    {statusConfig.label}
                    {source.status === 'processing' && source.processingProgress > 0 && (
                      <span>{source.processingProgress}%</span>
                    )}
                  </span>
                </div>

                {/* Error Message */}
                {source.status === 'failed' && source.processingError && (
                  <p className="text-[10px] text-red-400 mt-1 truncate" title={source.processingError}>
                    {source.processingError}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Summary Footer */}
      {sources.length > 0 && (
        <div className="mt-4 pt-4 border-t border-empire-border">
          {/* Progress Bar */}
          <div className="h-1.5 bg-empire-border rounded-full overflow-hidden mb-2">
            <div
              className="h-full bg-empire-primary rounded-full transition-all duration-300"
              style={{ width: `${Math.max(1, progressPercentage)}%` }}
            />
          </div>

          {/* Stats */}
          <div className="flex items-center justify-between text-xs text-empire-text-muted">
            <span>
              {totalCount} source{totalCount !== 1 ? 's' : ''}
              {' • '}
              <span className="text-green-400">{readyCount} ready</span>
              {processingCount > 0 && (
                <>
                  {' • '}
                  <span className="text-blue-400">{processingCount} processing</span>
                </>
              )}
              {stats.failed > 0 && (
                <>
                  {' • '}
                  <span className="text-red-400">{stats.failed} failed</span>
                </>
              )}
            </span>
            {stats.totalSize > 0 && (
              <span>{formatFileSize(stats.totalSize)}</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default SourcesSection
