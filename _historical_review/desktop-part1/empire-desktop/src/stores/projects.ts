import { create } from 'zustand'
import type { Project, Department } from '@/types'
import {
  getProjects,
  createProject as dbCreateProject,
  updateProject as dbUpdateProject,
  deleteProject as dbDeleteProject,
} from '@/lib/database'

interface ProjectsState {
  // State
  projects: Project[]
  selectedProjectId: string | null
  isLoading: boolean
  error: string | null

  // Filters
  departmentFilter: Department | 'all'
  searchQuery: string

  // Actions
  loadProjects: () => Promise<void>
  createProject: (name: string, department: Department, description?: string) => Promise<Project>
  updateProject: (id: string, updates: Partial<Pick<Project, 'name' | 'description' | 'instructions' | 'memoryContext'>>) => Promise<void>
  deleteProject: (id: string) => Promise<void>
  selectProject: (id: string | null) => void

  // Filter actions
  setDepartmentFilter: (department: Department | 'all') => void
  setSearchQuery: (query: string) => void

  // Computed
  filteredProjects: () => Project[]
}

export const DEPARTMENTS: Department[] = [
  'IT & Engineering',
  'Sales & Marketing',
  'Customer Support',
  'Operations & HR & Supply Chain',
  'Finance & Accounting',
  'Project Management',
  'Real Estate',
  'Private Equity & M&A',
  'Consulting',
  'Personal & Continuing Education',
]

export const useProjectsStore = create<ProjectsState>((set, get) => ({
  // Initial state
  projects: [],
  selectedProjectId: null,
  isLoading: false,
  error: null,
  departmentFilter: 'all',
  searchQuery: '',

  // Load projects from SQLite
  loadProjects: async () => {
    set({ isLoading: true, error: null })

    try {
      const projects = await getProjects()
      set({ projects, isLoading: false })
    } catch (err) {
      console.error('Failed to load projects:', err)
      set({
        error: 'Failed to load projects',
        isLoading: false,
      })
    }
  },

  // Create new project
  createProject: async (name, department, description) => {
    try {
      const project = await dbCreateProject(name, department, description)

      set((state) => ({
        projects: [project, ...state.projects],
        error: null,
      }))

      return project
    } catch (err) {
      console.error('Failed to create project:', err)
      set({ error: 'Failed to create project' })
      throw err
    }
  },

  // Update project
  updateProject: async (id, updates) => {
    const originalProjects = get().projects

    // Optimistic update
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === id ? { ...p, ...updates, updatedAt: new Date() } : p
      ),
      error: null,
    }))

    try {
      await dbUpdateProject(id, updates)
    } catch (err) {
      console.error('Failed to update project:', err)
      // Rollback on error
      set({
        projects: originalProjects,
        error: 'Failed to update project',
      })
      throw err
    }
  },

  // Delete project
  deleteProject: async (id) => {
    const originalProjects = get().projects

    // Optimistic delete
    set((state) => ({
      projects: state.projects.filter((p) => p.id !== id),
      selectedProjectId:
        state.selectedProjectId === id ? null : state.selectedProjectId,
      error: null,
    }))

    try {
      await dbDeleteProject(id)
    } catch (err) {
      console.error('Failed to delete project:', err)
      // Rollback on error
      set({
        projects: originalProjects,
        error: 'Failed to delete project',
      })
      throw err
    }
  },

  // Select project
  selectProject: (id) => set({ selectedProjectId: id }),

  // Filter actions
  setDepartmentFilter: (department) => set({ departmentFilter: department }),
  setSearchQuery: (query) => set({ searchQuery: query }),

  // Computed: filtered projects
  filteredProjects: () => {
    const { projects, departmentFilter, searchQuery } = get()

    return projects.filter((project) => {
      // Department filter
      if (departmentFilter !== 'all' && project.department !== departmentFilter) {
        return false
      }

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const matchesName = project.name.toLowerCase().includes(query)
        const matchesDescription = project.description?.toLowerCase().includes(query)
        if (!matchesName && !matchesDescription) {
          return false
        }
      }

      return true
    })
  },
}))

// Initialize projects on app load
export function initializeProjects() {
  useProjectsStore.getState().loadProjects()
}
