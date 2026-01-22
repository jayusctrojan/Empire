import { useEffect, useState } from 'react'
import { Plus, Search, FolderOpen, MoreVertical, Edit2, Trash2, MessageSquare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProjectsStore, DEPARTMENTS } from '@/stores/projects'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import { ProjectForm } from './projects/ProjectForm'
import { ProjectDetailView } from './ProjectDetailView'
import type { Project, Department } from '@/types'

export function ProjectsView() {
  const {
    isLoading,
    error,
    departmentFilter,
    searchQuery,
    loadProjects,
    filteredProjects,
    setDepartmentFilter,
    setSearchQuery,
    deleteProject,
  } = useProjectsStore()

  const { setActiveProject } = useChatStore()
  const { setActiveView } = useAppStore()

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)

  // Load projects on mount
  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  const projects = filteredProjects()

  // Show detail view if a project is selected
  if (selectedProject) {
    return (
      <ProjectDetailView
        project={selectedProject}
        onBack={() => setSelectedProject(null)}
      />
    )
  }

  const handleOpenProject = (project: Project) => {
    setSelectedProject(project)
  }

  const handleOpenChat = (project: Project) => {
    setActiveProject(project.id)
    setActiveView('chats')
  }

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this project? All associated conversations will be kept.')) {
      await deleteProject(id)
    }
    setMenuOpenId(null)
  }

  const getDepartmentColor = (dept: Department): string => {
    const colors: Record<string, string> = {
      'IT & Engineering': 'bg-blue-500/20 text-blue-400',
      'Sales & Marketing': 'bg-green-500/20 text-green-400',
      'Customer Support': 'bg-yellow-500/20 text-yellow-400',
      'Operations & HR & Supply Chain': 'bg-orange-500/20 text-orange-400',
      'Finance & Accounting': 'bg-emerald-500/20 text-emerald-400',
      'Project Management': 'bg-purple-500/20 text-purple-400',
      'Real Estate': 'bg-rose-500/20 text-rose-400',
      'Private Equity & M&A': 'bg-indigo-500/20 text-indigo-400',
      'Consulting': 'bg-cyan-500/20 text-cyan-400',
      'Personal & Continuing Education': 'bg-pink-500/20 text-pink-400',
    }
    return colors[dept] || 'bg-gray-500/20 text-gray-400'
  }

  return (
    <div className="flex flex-col h-full bg-empire-bg">
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b border-empire-border">
        <div>
          <h1 className="text-2xl font-semibold text-empire-text">Projects</h1>
          <p className="text-sm text-empire-text-muted mt-1">
            Organize your knowledge base by project
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 p-4 border-b border-empire-border">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-empire-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search projects..."
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text placeholder:text-empire-text-muted focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
          />
        </div>

        {/* Department filter */}
        <select
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value as Department | 'all')}
          className="px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
        >
          <option value="all">All Departments</option>
          {DEPARTMENTS.map((dept) => (
            <option key={dept} value={dept}>
              {dept}
            </option>
          ))}
        </select>
      </div>

      {/* Error message */}
      {error && (
        <div className="px-6 py-3 bg-red-500/10 border-b border-red-500/20">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Projects Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin w-8 h-8 border-2 border-empire-primary border-t-transparent rounded-full" />
          </div>
        ) : projects.length === 0 ? (
          <EmptyState
            hasFilter={departmentFilter !== 'all' || searchQuery.length > 0}
            onCreateClick={() => setShowCreateModal(true)}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                departmentColor={getDepartmentColor(project.department)}
                isMenuOpen={menuOpenId === project.id}
                onMenuToggle={() => setMenuOpenId(menuOpenId === project.id ? null : project.id)}
                onEdit={() => {
                  setEditingProject(project)
                  setMenuOpenId(null)
                }}
                onDelete={() => handleDelete(project.id)}
                onOpenChat={() => handleOpenChat(project)}
                onOpenProject={() => handleOpenProject(project)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingProject) && (
        <ProjectForm
          project={editingProject}
          onClose={() => {
            setShowCreateModal(false)
            setEditingProject(null)
          }}
        />
      )}
    </div>
  )
}

interface ProjectCardProps {
  project: Project
  departmentColor: string
  isMenuOpen: boolean
  onMenuToggle: () => void
  onEdit: () => void
  onDelete: () => void
  onOpenChat: () => void
  onOpenProject: () => void
}

function ProjectCard({
  project,
  departmentColor,
  isMenuOpen,
  onMenuToggle,
  onEdit,
  onDelete,
  onOpenChat,
  onOpenProject,
}: ProjectCardProps) {
  return (
    <div
      className="group relative rounded-xl border border-empire-border bg-empire-card p-4 hover:border-empire-primary/50 transition-colors cursor-pointer"
      onClick={onOpenProject}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-empire-primary/20 flex items-center justify-center">
            <FolderOpen className="w-5 h-5 text-empire-primary" />
          </div>
          <div>
            <h3 className="font-medium text-empire-text">{project.name}</h3>
            <span className={cn('text-xs px-2 py-0.5 rounded-full', departmentColor)}>
              {project.department}
            </span>
          </div>
        </div>

        {/* Menu */}
        <div className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onMenuToggle()
            }}
            className="p-1 rounded hover:bg-empire-border text-empire-text-muted"
          >
            <MoreVertical className="w-4 h-4" />
          </button>

          {isMenuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={(e) => {
                e.stopPropagation()
                onMenuToggle()
              }} />
              <div className="absolute right-0 top-8 z-20 w-36 rounded-lg border border-empire-border bg-empire-sidebar shadow-xl">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onEdit()
                  }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-empire-text hover:bg-empire-border"
                >
                  <Edit2 className="w-3 h-3" />
                  Edit
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete()
                  }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
                >
                  <Trash2 className="w-3 h-3" />
                  Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Description */}
      {project.description && (
        <p className="text-sm text-empire-text-muted mb-4 line-clamp-2">
          {project.description}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-empire-border">
        <span className="text-xs text-empire-text-muted">
          {project.conversationCount} conversation{project.conversationCount !== 1 ? 's' : ''}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onOpenChat()
          }}
          className="flex items-center gap-1 text-xs text-empire-primary hover:text-empire-primary/80"
        >
          <MessageSquare className="w-3 h-3" />
          Open Chat
        </button>
      </div>
    </div>
  )
}

interface EmptyStateProps {
  hasFilter: boolean
  onCreateClick: () => void
}

function EmptyState({ hasFilter, onCreateClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center">
      <FolderOpen className="w-12 h-12 text-empire-text-muted mb-4" />
      <h3 className="text-lg font-medium text-empire-text mb-2">
        {hasFilter ? 'No matching projects' : 'No projects yet'}
      </h3>
      <p className="text-sm text-empire-text-muted mb-4 max-w-sm">
        {hasFilter
          ? 'Try adjusting your filters or search terms.'
          : 'Create your first project to organize your knowledge base.'}
      </p>
      {!hasFilter && (
        <button
          onClick={onCreateClick}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white transition-colors"
        >
          <Plus className="w-4 h-4" />
          Create Project
        </button>
      )}
    </div>
  )
}

export default ProjectsView
