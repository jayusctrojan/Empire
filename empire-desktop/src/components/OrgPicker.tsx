import { useEffect, useState, useCallback } from 'react'
import { Building2, Plus, Users, ChevronRight, Loader2 } from 'lucide-react'
import { useOrgStore } from '@/stores/org'
import type { Organization } from '@/stores/org'
import { listOrganizations, createOrganization } from '@/lib/api/organizations'

interface OrgPickerProps {
  onOrgSelected: (org: Organization) => void
}

export function OrgPicker({ onOrgSelected }: OrgPickerProps) {
  const { userOrgs, setUserOrgs, setCurrentOrg, setLoading, isLoading } = useOrgStore()
  const [showCreate, setShowCreate] = useState(false)
  const [newOrgName, setNewOrgName] = useState('')
  const [createError, setCreateError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  // Load organizations
  useEffect(() => {
    async function loadOrgs() {
      setLoading(true)
      try {
        const orgs = await listOrganizations()
        setUserOrgs(orgs)
      } catch (err) {
        console.error('Failed to load organizations:', err)
      } finally {
        setLoading(false)
      }
    }
    loadOrgs()
  }, [setUserOrgs, setLoading])

  const handleSelectOrg = useCallback((org: Organization) => {
    setCurrentOrg(org)
    onOrgSelected(org)
  }, [setCurrentOrg, onOrgSelected])

  const handleCreateOrg = useCallback(async () => {
    if (!newOrgName.trim()) return

    setIsCreating(true)
    setCreateError(null)
    try {
      const org = await createOrganization({ name: newOrgName.trim() })
      setUserOrgs([...useOrgStore.getState().userOrgs, org])
      handleSelectOrg(org)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create organization')
    } finally {
      setIsCreating(false)
    }
  }, [newOrgName, setUserOrgs, handleSelectOrg])

  // Auto-select if only one org
  useEffect(() => {
    if (userOrgs.length === 1 && !isLoading) {
      handleSelectOrg(userOrgs[0])
    }
  }, [userOrgs, isLoading, handleSelectOrg])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-empire-bg">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-empire-primary mx-auto mb-4" />
          <p className="text-empire-text-muted">Loading organizations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen items-center justify-center bg-empire-bg">
      <div className="w-full max-w-lg px-6">
        {/* Greeting */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-empire-primary/20 flex items-center justify-center">
            <Building2 className="w-8 h-8 text-empire-primary" />
          </div>
          <h1 className="text-2xl font-semibold text-empire-text mb-2">
            Welcome to Empire
          </h1>
          <p className="text-empire-text-muted">
            Which company are you working on today?
          </p>
        </div>

        {/* Organization List */}
        <div className="space-y-2 mb-6">
          {userOrgs.map((org) => (
            <button
              key={org.id}
              onClick={() => handleSelectOrg(org)}
              className="w-full flex items-center gap-4 px-4 py-3 rounded-xl bg-empire-surface hover:bg-empire-surface-hover border border-empire-border hover:border-empire-primary/50 transition-all group"
            >
              {/* Logo or Initial */}
              {org.logoUrl ? (
                <img
                  src={org.logoUrl}
                  alt={org.name}
                  className="w-10 h-10 rounded-lg object-cover"
                />
              ) : (
                <div className="w-10 h-10 rounded-lg bg-empire-primary/20 flex items-center justify-center text-empire-primary font-semibold text-lg">
                  {org.name.charAt(0).toUpperCase()}
                </div>
              )}

              {/* Name + Meta */}
              <div className="flex-1 text-left">
                <div className="font-medium text-empire-text">{org.name}</div>
                <div className="text-sm text-empire-text-muted flex items-center gap-2">
                  <Users className="w-3.5 h-3.5" />
                  {org.memberCount} {org.memberCount === 1 ? 'member' : 'members'}
                  {org.userRole && (
                    <span className="px-1.5 py-0.5 text-xs rounded bg-empire-primary/10 text-empire-primary capitalize">
                      {org.userRole}
                    </span>
                  )}
                </div>
              </div>

              <ChevronRight className="w-5 h-5 text-empire-text-muted group-hover:text-empire-primary transition-colors" />
            </button>
          ))}
        </div>

        {/* Create New Organization */}
        {!showCreate ? (
          <button
            onClick={() => setShowCreate(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-dashed border-empire-border hover:border-empire-primary/50 text-empire-text-muted hover:text-empire-primary transition-all"
          >
            <Plus className="w-4 h-4" />
            Add Organization
          </button>
        ) : (
          <div className="p-4 rounded-xl bg-empire-surface border border-empire-border">
            <label className="block text-sm font-medium text-empire-text mb-2">
              Organization Name
            </label>
            <input
              type="text"
              value={newOrgName}
              onChange={(e) => setNewOrgName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateOrg()}
              placeholder="e.g. Acme Corp"
              autoFocus
              className="w-full px-3 py-2 rounded-lg bg-empire-bg border border-empire-border text-empire-text placeholder-empire-text-muted focus:outline-none focus:ring-2 focus:ring-empire-primary/50 mb-3"
            />
            {createError && (
              <p className="text-sm text-red-400 mb-3">{createError}</p>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => { setShowCreate(false); setNewOrgName(''); setCreateError(null) }}
                className="flex-1 px-3 py-2 rounded-lg border border-empire-border text-empire-text-muted hover:bg-empire-surface-hover transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateOrg}
                disabled={!newOrgName.trim() || isCreating}
                className="flex-1 px-3 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isCreating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  'Create'
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
