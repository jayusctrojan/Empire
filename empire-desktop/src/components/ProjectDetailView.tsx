import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ArrowLeft,
  MessageSquare,
  Plus,
  Trash2,
  MoreVertical,
  RefreshCw,
  Lock,
  Edit2,
  Check,
  X,
  Pencil,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProjectsStore } from '@/stores/projects'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import type { Project, Conversation, ProjectFile } from '@/types'
import { get, del, postFormData } from '@/lib/api'

// File type badge colors
const FILE_TYPE_COLORS: Record<string, string> = {
  md: 'bg-blue-500/20 text-blue-400',
  py: 'bg-yellow-500/20 text-yellow-400',
  js: 'bg-yellow-500/20 text-yellow-400',
  ts: 'bg-blue-500/20 text-blue-400',
  tsx: 'bg-blue-500/20 text-blue-400',
  jsx: 'bg-yellow-500/20 text-yellow-400',
  json: 'bg-green-500/20 text-green-400',
  txt: 'bg-gray-500/20 text-gray-400',
  pdf: 'bg-red-500/20 text-red-400',
  doc: 'bg-blue-500/20 text-blue-400',
  docx: 'bg-blue-500/20 text-blue-400',
  csv: 'bg-green-500/20 text-green-400',
  default: 'bg-gray-500/20 text-gray-400',
}

// Max project capacity in bytes (100MB)
const MAX_PROJECT_CAPACITY = 100 * 1024 * 1024

interface ProjectDetailViewProps {
  project: Project
  onBack: () => void
}

export function ProjectDetailView({ project, onBack }: ProjectDetailViewProps) {
  // Conversations state
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoadingConversations, setIsLoadingConversations] = useState(false)

  // Files state
  const [files, setFiles] = useState<ProjectFile[]>([])
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [totalFileSize, setTotalFileSize] = useState(0)

  // Memory & Instructions state
  const [instructions, setInstructions] = useState(project.instructions || '')
  const [memoryContext, setMemoryContext] = useState(project.memoryContext || '')
  const [isEditingInstructions, setIsEditingInstructions] = useState(false)
  const [isEditingMemory, setIsEditingMemory] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Menu state
  const [showMenu, setShowMenu] = useState(false)
  const [isRenaming, setIsRenaming] = useState(false)
  const [newName, setNewName] = useState(project.name)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const { updateProject, deleteProject } = useProjectsStore()
  const { setActiveConversation, setActiveProject } = useChatStore()
  const { setActiveView } = useAppStore()

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load conversations
  const loadConversations = useCallback(async () => {
    setIsLoadingConversations(true)
    try {
      const response = await get<{ data: Conversation[] }>(
        `/api/conversations?project_id=${project.id}`
      )
      if (response?.data) {
        setConversations(response.data)
      }
    } catch (err) {
      console.error('Failed to load conversations:', err)
    } finally {
      setIsLoadingConversations(false)
    }
  }, [project.id])

  // Load files
  const loadFiles = useCallback(async () => {
    setIsLoadingFiles(true)
    try {
      const response = await get<{ data: ProjectFile[] }>(
        `/api/projects/${project.id}/files`
      )
      if (response?.data) {
        setFiles(response.data)
        const total = response.data.reduce((sum, f) => sum + f.size, 0)
        setTotalFileSize(total)
      }
    } catch (err) {
      console.error('Failed to load files:', err)
      setFiles([])
    } finally {
      setIsLoadingFiles(false)
    }
  }, [project.id])

  // Save instructions
  const saveInstructions = async () => {
    setIsSaving(true)
    try {
      await updateProject(project.id, { instructions })
      setIsEditingInstructions(false)
    } catch (err) {
      console.error('Failed to save instructions:', err)
    } finally {
      setIsSaving(false)
    }
  }

  // Save memory
  const saveMemory = async () => {
    setIsSaving(true)
    try {
      await updateProject(project.id, { memoryContext })
      setIsEditingMemory(false)
    } catch (err) {
      console.error('Failed to save memory:', err)
    } finally {
      setIsSaving(false)
    }
  }

  // Handle file upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFiles = e.target.files
    if (!uploadedFiles?.length) return

    const formData = new FormData()
    formData.append('project_id', project.id)
    for (const file of uploadedFiles) {
      formData.append('files', file)
    }

    try {
      await postFormData('/api/documents/upload', formData)
      loadFiles()
    } catch (err) {
      console.error('Failed to upload files:', err)
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // Delete file
  const handleDeleteFile = async (fileId: string) => {
    try {
      await del(`/api/projects/${project.id}/files/${fileId}`)
      setFiles((prev) => prev.filter((f) => f.id !== fileId))
    } catch (err) {
      console.error('Failed to delete file:', err)
    }
  }

  // Open conversation
  const openConversation = (conversation: Conversation) => {
    setActiveConversation(conversation.id)
    setActiveView('chats')
  }

  // Start new chat in project
  const startNewChat = () => {
    setActiveProject(project.id)
    setActiveView('chats')
  }

  // Handle rename
  const handleRename = async () => {
    if (newName.trim() && newName !== project.name) {
      await updateProject(project.id, { name: newName.trim() })
    }
    setIsRenaming(false)
    setShowMenu(false)
  }

  // Handle delete
  const handleDelete = async () => {
    await deleteProject(project.id)
    onBack()
  }

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false)
      }
    }
    if (showMenu) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showMenu])

  // Get file extension
  const getFileExtension = (filename: string): string => {
    const parts = filename.split('.')
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : ''
  }

  // Get file type color
  const getFileTypeColor = (filename: string): string => {
    const ext = getFileExtension(filename)
    return FILE_TYPE_COLORS[ext] || FILE_TYPE_COLORS.default
  }

  // Estimate line count
  const estimateLineCount = (bytes: number): number => {
    return Math.max(1, Math.round(bytes / 50))
  }

  // Calculate capacity percentage
  const capacityPercentage = Math.min(100, (totalFileSize / MAX_PROJECT_CAPACITY) * 100)

  // Load data on mount
  useEffect(() => {
    loadConversations()
    loadFiles()
  }, [loadConversations, loadFiles])

  return (
    <div className="flex flex-col h-full bg-empire-bg">
      {/* Header */}
      <div className="flex items-center gap-4 p-4 border-b border-empire-border">
        <button
          onClick={onBack}
          className="p-2 rounded-lg hover:bg-empire-border transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="w-5 h-5 text-empire-text-muted" />
        </button>
        <div className="flex-1 min-w-0">
          {isRenaming ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRename()
                  if (e.key === 'Escape') {
                    setNewName(project.name)
                    setIsRenaming(false)
                  }
                }}
                className="flex-1 px-2 py-1 rounded border border-empire-border bg-empire-sidebar text-empire-text focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
                autoFocus
              />
              <button
                onClick={handleRename}
                className="p-1.5 rounded hover:bg-green-500/20 transition-colors"
              >
                <Check className="w-4 h-4 text-green-500" />
              </button>
              <button
                onClick={() => {
                  setNewName(project.name)
                  setIsRenaming(false)
                }}
                className="p-1.5 rounded hover:bg-red-500/20 transition-colors"
              >
                <X className="w-4 h-4 text-red-500" />
              </button>
            </div>
          ) : (
            <>
              <h1 className="text-lg font-semibold text-empire-text truncate">
                {project.name}
              </h1>
              <p className="text-sm text-empire-text-muted">
                Last message {new Date(project.updatedAt).toLocaleDateString()}
              </p>
            </>
          )}
        </div>
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-2 rounded-lg hover:bg-empire-border transition-colors"
          >
            <MoreVertical className="w-5 h-5 text-empire-text-muted" />
          </button>
          {showMenu && (
            <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border border-empire-border bg-empire-card shadow-lg z-50 overflow-hidden">
              <button
                onClick={() => {
                  setIsRenaming(true)
                  setShowMenu(false)
                }}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-empire-text hover:bg-empire-border transition-colors"
              >
                <Pencil className="w-4 h-4" />
                Rename Project
              </button>
              <button
                onClick={() => {
                  setShowDeleteConfirm(true)
                  setShowMenu(false)
                }}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Delete Project
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-empire-card border border-empire-border rounded-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold text-empire-text mb-2">Delete Project?</h3>
            <p className="text-sm text-empire-text-muted mb-4">
              This will permanently delete "{project.name}" and all its conversations. This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 rounded-lg border border-empire-border text-empire-text hover:bg-empire-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Split View: Conversations (left) + Knowledge Panel (right) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Conversations */}
        <div className="flex-1 flex flex-col border-r border-empire-border">
          {/* New Chat Button */}
          <div className="p-4 border-b border-empire-border">
            <button
              onClick={startNewChat}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-empire-primary text-white hover:bg-empire-primary/90 transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Chat
            </button>
          </div>

          {/* Conversations List */}
          <div className="flex-1 overflow-y-auto p-4">
            {isLoadingConversations ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="w-5 h-5 text-empire-text-muted animate-spin" />
              </div>
            ) : conversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-empire-text-muted">
                <MessageSquare className="w-8 h-8 mb-2 opacity-50" />
                <p>No conversations yet</p>
                <p className="text-sm">Start a new chat in this project</p>
              </div>
            ) : (
              <div className="space-y-2">
                {conversations.map((conversation) => (
                  <button
                    key={conversation.id}
                    onClick={() => openConversation(conversation)}
                    className="w-full p-4 rounded-lg border border-empire-border bg-empire-sidebar hover:bg-empire-border transition-colors text-left"
                  >
                    <p className="font-medium text-empire-text truncate">
                      {conversation.title}
                    </p>
                    <p className="text-sm text-empire-text-muted mt-1">
                      {conversation.messageCount} messages
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Project Knowledge Panel (like Claude Desktop) */}
        <div className="w-96 flex-shrink-0 overflow-y-auto p-4 space-y-4 bg-empire-bg">
          {/* Memory Section */}
          <div className="rounded-xl border border-empire-border bg-empire-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-medium text-empire-text">Memory</h2>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-xs text-empire-text-muted px-2 py-1 rounded-full bg-empire-border">
                  <Lock className="w-3 h-3" />
                  Only you
                </span>
                {!isEditingMemory ? (
                  <button
                    onClick={() => setIsEditingMemory(true)}
                    className="p-1.5 rounded hover:bg-empire-border transition-colors"
                  >
                    <Edit2 className="w-4 h-4 text-empire-text-muted" />
                  </button>
                ) : (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={saveMemory}
                      disabled={isSaving}
                      className="p-1.5 rounded hover:bg-green-500/20 transition-colors"
                    >
                      <Check className="w-4 h-4 text-green-500" />
                    </button>
                    <button
                      onClick={() => {
                        setMemoryContext(project.memoryContext || '')
                        setIsEditingMemory(false)
                      }}
                      className="p-1.5 rounded hover:bg-red-500/20 transition-colors"
                    >
                      <X className="w-4 h-4 text-red-500" />
                    </button>
                  </div>
                )}
              </div>
            </div>
            {isEditingMemory ? (
              <textarea
                value={memoryContext}
                onChange={(e) => setMemoryContext(e.target.value)}
                placeholder="Add context about this project..."
                className="w-full min-h-[80px] p-3 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
              />
            ) : (
              <p className="text-sm text-empire-text-muted leading-relaxed">
                {memoryContext || 'Purpose & context not set. Click edit to add.'}
              </p>
            )}
            {memoryContext && !isEditingMemory && (
              <p className="text-xs text-empire-text-muted mt-2">
                Last updated {new Date(project.updatedAt).toLocaleDateString()}
              </p>
            )}
          </div>

          {/* Instructions Section */}
          <div className="rounded-xl border border-empire-border bg-empire-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-medium text-empire-text">Instructions</h2>
              {!isEditingInstructions ? (
                <button
                  onClick={() => setIsEditingInstructions(true)}
                  className="p-1.5 rounded hover:bg-empire-border transition-colors"
                >
                  <Edit2 className="w-4 h-4 text-empire-text-muted" />
                </button>
              ) : (
                <div className="flex items-center gap-1">
                  <button
                    onClick={saveInstructions}
                    disabled={isSaving}
                    className="p-1.5 rounded hover:bg-green-500/20 transition-colors"
                  >
                    <Check className="w-4 h-4 text-green-500" />
                  </button>
                  <button
                    onClick={() => {
                      setInstructions(project.instructions || '')
                      setIsEditingInstructions(false)
                    }}
                    className="p-1.5 rounded hover:bg-red-500/20 transition-colors"
                  >
                    <X className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              )}
            </div>
            {isEditingInstructions ? (
              <textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                placeholder="Enter instructions for the AI..."
                className="w-full min-h-[80px] p-3 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
              />
            ) : (
              <p className="text-sm text-empire-text-muted leading-relaxed whitespace-pre-wrap">
                {instructions || 'No instructions set. Click edit to add.'}
              </p>
            )}
          </div>

          {/* Files Section */}
          <div className="rounded-xl border border-empire-border bg-empire-card p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-medium text-empire-text">Files</h2>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-1.5 rounded hover:bg-empire-border transition-colors"
                aria-label="Add files"
              >
                <Plus className="w-5 h-5 text-empire-text-muted" />
              </button>
            </div>

            {/* Capacity Progress Bar */}
            <div className="mb-4">
              <div className="h-1.5 bg-empire-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-empire-primary rounded-full transition-all duration-300"
                  style={{ width: `${Math.max(1, capacityPercentage)}%` }}
                />
              </div>
              <p className="text-xs text-empire-text-muted mt-2">
                {capacityPercentage.toFixed(0)}% of project capacity used
              </p>
            </div>

            {/* Files Grid */}
            {isLoadingFiles ? (
              <div className="flex items-center justify-center h-20">
                <RefreshCw className="w-5 h-5 text-empire-text-muted animate-spin" />
              </div>
            ) : files.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-20 text-empire-text-muted">
                <p className="text-sm">No files uploaded</p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-1 text-sm text-empire-primary hover:text-empire-primary/80"
                >
                  Add files
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {files.map((file) => {
                  const ext = getFileExtension(file.name)
                  const lineCount = estimateLineCount(file.size)
                  return (
                    <div
                      key={file.id}
                      className="group relative rounded-lg border border-empire-border bg-empire-sidebar p-3 hover:border-empire-primary/50 transition-colors"
                    >
                      <button
                        onClick={() => handleDeleteFile(file.id)}
                        className="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 transition-all"
                        aria-label="Delete file"
                      >
                        <Trash2 className="w-3 h-3 text-red-500" />
                      </button>
                      <p className="text-xs font-medium text-empire-text truncate pr-5 mb-1">
                        {file.name}
                      </p>
                      <p className="text-xs text-empire-text-muted mb-2">
                        {lineCount} lines
                      </p>
                      <span
                        className={cn(
                          'inline-block px-1.5 py-0.5 rounded text-[10px] font-medium uppercase',
                          getFileTypeColor(file.name)
                        )}
                      >
                        {ext || 'FILE'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProjectDetailView
