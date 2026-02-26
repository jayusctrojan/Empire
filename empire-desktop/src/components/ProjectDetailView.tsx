import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ArrowLeft,
  MessageSquare,
  Plus,
  MoreVertical,
  RefreshCw,
  Edit2,
  Check,
  X,
  Pencil,
  Trash2,
} from 'lucide-react'
import { useProjectsStore } from '@/stores/projects'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import type { Project, Conversation } from '@/types'
import { get } from '@/lib/api'
import { SourcesSection, ProjectMemoryPanel } from './projects'

interface ProjectDetailViewProps {
  project: Project
  onBack: () => void
}

export function ProjectDetailView({ project, onBack }: ProjectDetailViewProps) {
  // Conversations state
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoadingConversations, setIsLoadingConversations] = useState(false)

  // Instructions state
  const [instructions, setInstructions] = useState(project.instructions || '')
  const [isEditingInstructions, setIsEditingInstructions] = useState(false)
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

  // Load data on mount
  useEffect(() => {
    loadConversations()
  }, [loadConversations])

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
          {/* Project Memory Panel (Pinned Context + Accumulated Knowledge) */}
          <ProjectMemoryPanel
            projectId={project.id}
            memoryContext={project.memoryContext || ''}
            onSaveMemoryContext={async (ctx) => {
              await updateProject(project.id, { memoryContext: ctx })
            }}
          />

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

          {/* Sources Section */}
          <SourcesSection projectId={project.id} />
        </div>
      </div>
    </div>
  )
}

export default ProjectDetailView
