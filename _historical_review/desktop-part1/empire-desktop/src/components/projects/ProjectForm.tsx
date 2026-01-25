import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X } from 'lucide-react'
import { useProjectsStore, DEPARTMENTS } from '@/stores/projects'
import type { Project, Department } from '@/types'

const projectSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name too long'),
  department: z.enum(DEPARTMENTS as [Department, ...Department[]]),
  description: z.string().max(500, 'Description too long').optional(),
  instructions: z.string().max(2000, 'Instructions too long').optional(),
})

type ProjectFormData = z.infer<typeof projectSchema>

interface ProjectFormProps {
  project?: Project | null
  onClose: () => void
}

export function ProjectForm({ project, onClose }: ProjectFormProps) {
  const { createProject, updateProject } = useProjectsStore()
  const isEditing = !!project

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: project?.name || '',
      department: project?.department || 'IT & Engineering',
      description: project?.description || '',
      instructions: project?.instructions || '',
    },
  })

  // Reset form when project changes
  useEffect(() => {
    if (project) {
      reset({
        name: project.name,
        department: project.department,
        description: project.description || '',
        instructions: project.instructions || '',
      })
    }
  }, [project, reset])

  const onSubmit = async (data: ProjectFormData) => {
    try {
      if (isEditing && project) {
        await updateProject(project.id, {
          name: data.name,
          description: data.description,
          instructions: data.instructions,
        })
      } else {
        await createProject(data.name, data.department, data.description)
      }
      onClose()
    } catch (err) {
      console.error('Failed to save project:', err)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      {/* Backdrop */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 rounded-xl border border-empire-border bg-empire-sidebar shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-empire-border">
          <h2 className="text-lg font-semibold text-empire-text">
            {isEditing ? 'Edit Project' : 'New Project'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-empire-border text-empire-text-muted"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-empire-text mb-1">
              Project Name <span className="text-red-400">*</span>
            </label>
            <input
              {...register('name')}
              type="text"
              placeholder="Enter project name"
              className="w-full px-3 py-2 rounded-lg bg-empire-bg border border-empire-border text-empire-text placeholder:text-empire-text-muted focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
            />
            {errors.name && (
              <p className="mt-1 text-xs text-red-400">{errors.name.message}</p>
            )}
          </div>

          {/* Department */}
          <div>
            <label className="block text-sm font-medium text-empire-text mb-1">
              Department <span className="text-red-400">*</span>
            </label>
            <select
              {...register('department')}
              disabled={isEditing} // Can't change department after creation
              className="w-full px-3 py-2 rounded-lg bg-empire-bg border border-empire-border text-empire-text focus:outline-none focus:ring-2 focus:ring-empire-primary/50 disabled:opacity-50"
            >
              {DEPARTMENTS.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>
            {isEditing && (
              <p className="mt-1 text-xs text-empire-text-muted">
                Department cannot be changed after creation
              </p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-empire-text mb-1">
              Description
            </label>
            <textarea
              {...register('description')}
              rows={2}
              placeholder="Brief description of the project"
              className="w-full px-3 py-2 rounded-lg bg-empire-bg border border-empire-border text-empire-text placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
            />
            {errors.description && (
              <p className="mt-1 text-xs text-red-400">{errors.description.message}</p>
            )}
          </div>

          {/* Instructions */}
          <div>
            <label className="block text-sm font-medium text-empire-text mb-1">
              AI Instructions
            </label>
            <textarea
              {...register('instructions')}
              rows={3}
              placeholder="Custom instructions for the AI when answering questions about this project..."
              className="w-full px-3 py-2 rounded-lg bg-empire-bg border border-empire-border text-empire-text placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
            />
            <p className="mt-1 text-xs text-empire-text-muted">
              These instructions will be included when the AI responds to questions in this project.
            </p>
            {errors.instructions && (
              <p className="mt-1 text-xs text-red-400">{errors.instructions.message}</p>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-empire-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-empire-border text-empire-text hover:bg-empire-border transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white transition-colors disabled:opacity-50"
            >
              {isSubmitting ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default ProjectForm
