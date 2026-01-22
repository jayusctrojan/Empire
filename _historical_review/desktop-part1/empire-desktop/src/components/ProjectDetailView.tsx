import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ArrowLeft,
  MessageSquare,
  FileText,
  BookOpen,
  Brain,
  Upload,
  Trash2,
  File,
  Image,
  FileCode,
  MoreVertical,
  RefreshCw,
  Save,
  Check,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProjectsStore } from '@/stores/projects'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import type { Project, Conversation } from '@/types'
import { get, post, del, postFormData } from '@/lib/api'

type Tab = 'conversations' | 'files' | 'instructions' | 'memory'

interface ProjectDetailViewProps {
  project: Project
  onBack: () => void
}

interface ProjectFile {
  id: string
  name: string
  size: number
  type: string
  uploadedAt: Date
}

export function ProjectDetailView({ project, onBack }: ProjectDetailViewProps) {
  const [activeTab, setActiveTab] = useState<Tab>('conversations')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [files, setFiles] = useState<ProjectFile[]>([])
  const [instructions, setInstructions] = useState(project.instructions || '')
  const [memoryContext, setMemoryContext] = useState(project.memoryContext || '')
  const [isLoadingConversations, setIsLoadingConversations] = useState(false)
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [isSavingInstructions, setIsSavingInstructions] = useState(false)
  const [instructionsSaved, setInstructionsSaved] = useState(false)
  const [isGeneratingMemory, setIsGeneratingMemory] = useState(false)

  const { updateProject } = useProjectsStore()
  const { setActiveConversation } = useChatStore()
  const { setActiveView } = useAppStore()

  const fileInputRef = useRef<HTMLInputElement>(null)
  const instructionsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const tabs: { id: Tab; label: string; icon: typeof MessageSquare }[] = [
    { id: 'conversations', label: 'Conversations', icon: MessageSquare },
    { id: 'files', label: 'Files', icon: FileText },
    { id: 'instructions', label: 'Instructions', icon: BookOpen },
    { id: 'memory', label: 'Memory', icon: Brain },
  ]

  // Load conversations for this project
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

  // Load files for this project
  const loadFiles = useCallback(async () => {
    setIsLoadingFiles(true)
    try {
      const response = await get<{ data: ProjectFile[] }>(
        `/api/projects/${project.id}/files`
      )
      if (response?.data) {
        setFiles(response.data)
      }
    } catch (err) {
      console.error('Failed to load files:', err)
      // Mock data for now
      setFiles([])
    } finally {
      setIsLoadingFiles(false)
    }
  }, [project.id])

  // Auto-save instructions with debounce
  const saveInstructions = useCallback(
    async (newInstructions: string) => {
      setIsSavingInstructions(true)
      try {
        await updateProject(project.id, { instructions: newInstructions })
        setInstructionsSaved(true)
        setTimeout(() => setInstructionsSaved(false), 2000)
      } catch (err) {
        console.error('Failed to save instructions:', err)
      } finally {
        setIsSavingInstructions(false)
      }
    },
    [project.id, updateProject]
  )

  const handleInstructionsChange = (value: string) => {
    setInstructions(value)
    setInstructionsSaved(false)

    // Debounce auto-save
    if (instructionsTimeoutRef.current) {
      clearTimeout(instructionsTimeoutRef.current)
    }
    instructionsTimeoutRef.current = setTimeout(() => {
      saveInstructions(value)
    }, 1000)
  }

  // Generate memory summary
  const generateMemorySummary = async () => {
    setIsGeneratingMemory(true)
    try {
      const response = await post<{ summary: string }>(
        `/api/projects/${project.id}/generate-memory`
      )
      if (response?.summary) {
        setMemoryContext(response.summary)
        await updateProject(project.id, { memoryContext: response.summary })
      }
    } catch (err) {
      console.error('Failed to generate memory:', err)
      // Generate a placeholder summary
      const placeholder = `Project "${project.name}" in ${project.department} department. ${conversations.length} conversations recorded. Last updated: ${new Date().toLocaleDateString()}`
      setMemoryContext(placeholder)
    } finally {
      setIsGeneratingMemory(false)
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

  // Get file icon based on type
  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) return Image
    if (type.includes('code') || type.includes('javascript') || type.includes('typescript'))
      return FileCode
    return File
  }

  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Load data on mount and tab change
  useEffect(() => {
    if (activeTab === 'conversations') {
      loadConversations()
    } else if (activeTab === 'files') {
      loadFiles()
    }
  }, [activeTab, loadConversations, loadFiles])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (instructionsTimeoutRef.current) {
        clearTimeout(instructionsTimeoutRef.current)
      }
    }
  }, [])

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
          <h1 className="text-lg font-semibold text-empire-text truncate">
            {project.name}
          </h1>
          <p className="text-sm text-empire-text-muted truncate">
            {project.department} {project.description && `• ${project.description}`}
          </p>
        </div>
        <button className="p-2 rounded-lg hover:bg-empire-border transition-colors">
          <MoreVertical className="w-5 h-5 text-empire-text-muted" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-empire-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors relative',
              activeTab === tab.id
                ? 'text-empire-primary'
                : 'text-empire-text-muted hover:text-empire-text'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-empire-primary" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {/* Conversations Tab */}
        {activeTab === 'conversations' && (
          <div className="h-full overflow-y-auto p-4">
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
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-empire-text truncate">
                          {conversation.title}
                        </p>
                        <p className="text-sm text-empire-text-muted truncate mt-1">
                          {conversation.messageCount} message{conversation.messageCount !== 1 ? 's' : ''}
                        </p>
                      </div>
                      <span className="text-xs text-empire-text-muted whitespace-nowrap">
                        {new Date(conversation.updatedAt).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Files Tab */}
        {activeTab === 'files' && (
          <div className="h-full overflow-y-auto p-4">
            <div className="mb-4">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-empire-primary text-white hover:bg-empire-primary/90 transition-colors"
              >
                <Upload className="w-4 h-4" />
                Upload Files
              </button>
            </div>

            {isLoadingFiles ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="w-5 h-5 text-empire-text-muted animate-spin" />
              </div>
            ) : files.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-empire-text-muted">
                <FileText className="w-8 h-8 mb-2 opacity-50" />
                <p>No files uploaded</p>
                <p className="text-sm">Upload documents to add context to this project</p>
              </div>
            ) : (
              <div className="space-y-2">
                {files.map((file) => {
                  const FileIcon = getFileIcon(file.type)
                  return (
                    <div
                      key={file.id}
                      className="flex items-center gap-3 p-3 rounded-lg border border-empire-border bg-empire-sidebar"
                    >
                      <FileIcon className="w-5 h-5 text-empire-text-muted flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-empire-text truncate">
                          {file.name}
                        </p>
                        <p className="text-xs text-empire-text-muted">
                          {formatFileSize(file.size)} •{' '}
                          {new Date(file.uploadedAt).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDeleteFile(file.id)}
                        className="p-2 rounded hover:bg-empire-border transition-colors"
                        aria-label="Delete file"
                      >
                        <Trash2 className="w-4 h-4 text-empire-text-muted hover:text-red-500" />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Instructions Tab */}
        {activeTab === 'instructions' && (
          <div className="h-full flex flex-col p-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-empire-text">
                Project Instructions
              </label>
              <div className="flex items-center gap-2 text-sm">
                {isSavingInstructions ? (
                  <span className="flex items-center gap-1 text-empire-text-muted">
                    <Save className="w-3 h-3" />
                    Saving...
                  </span>
                ) : instructionsSaved ? (
                  <span className="flex items-center gap-1 text-green-500">
                    <Check className="w-3 h-3" />
                    Saved
                  </span>
                ) : null}
              </div>
            </div>
            <p className="text-xs text-empire-text-muted mb-3">
              These instructions will be included as context in all conversations within this
              project.
            </p>
            <textarea
              value={instructions}
              onChange={(e) => handleInstructionsChange(e.target.value)}
              placeholder="Enter instructions for the AI assistant when working in this project..."
              className="flex-1 w-full p-3 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
            />
          </div>
        )}

        {/* Memory Tab */}
        {activeTab === 'memory' && (
          <div className="h-full flex flex-col p-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-medium text-empire-text">Project Memory</h3>
                <p className="text-xs text-empire-text-muted mt-1">
                  Auto-generated summary of key information from this project
                </p>
              </div>
              <button
                onClick={generateMemorySummary}
                disabled={isGeneratingMemory}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-empire-border text-empire-text hover:bg-empire-primary hover:text-white transition-colors disabled:opacity-50"
              >
                <RefreshCw
                  className={cn('w-4 h-4', isGeneratingMemory && 'animate-spin')}
                />
                {isGeneratingMemory ? 'Generating...' : 'Regenerate'}
              </button>
            </div>

            <div className="flex-1 rounded-lg border border-empire-border bg-empire-sidebar p-4 overflow-y-auto">
              {memoryContext ? (
                <div className="prose prose-sm prose-invert max-w-none">
                  <p className="text-empire-text whitespace-pre-wrap">{memoryContext}</p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-empire-text-muted">
                  <Brain className="w-8 h-8 mb-2 opacity-50" />
                  <p>No memory generated yet</p>
                  <p className="text-sm">Click "Regenerate" to create a summary</p>
                </div>
              )}
            </div>

            <div className="mt-4 p-3 rounded-lg bg-empire-border/50">
              <h4 className="text-xs font-medium text-empire-text-muted uppercase tracking-wider mb-2">
                Project Stats
              </h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-empire-text-muted">Conversations:</span>{' '}
                  <span className="text-empire-text font-medium">
                    {project.conversationCount}
                  </span>
                </div>
                <div>
                  <span className="text-empire-text-muted">Files:</span>{' '}
                  <span className="text-empire-text font-medium">{files.length}</span>
                </div>
                <div>
                  <span className="text-empire-text-muted">Created:</span>{' '}
                  <span className="text-empire-text font-medium">
                    {new Date(project.createdAt).toLocaleDateString()}
                  </span>
                </div>
                <div>
                  <span className="text-empire-text-muted">Updated:</span>{' '}
                  <span className="text-empire-text font-medium">
                    {new Date(project.updatedAt).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ProjectDetailView
