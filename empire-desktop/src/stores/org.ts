import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Organization {
  id: string
  name: string
  slug: string
  logoUrl?: string | null
  settings: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
  memberCount: number
  userRole?: string | null
}

interface OrgState {
  // State
  currentOrg: Organization | null
  userOrgs: Organization[]
  isLoading: boolean
  error: string | null

  // Actions
  setCurrentOrg: (org: Organization | null) => void
  setUserOrgs: (orgs: Organization[]) => void
  selectOrg: (orgId: string) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearOrg: () => void
}

export const useOrgStore = create<OrgState>()(
  persist(
    (set, get) => ({
      currentOrg: null,
      userOrgs: [],
      isLoading: false,
      error: null,

      setCurrentOrg: (org) => set({ currentOrg: org }),

      setUserOrgs: (orgs) => set({ userOrgs: orgs }),

      selectOrg: (orgId) => {
        const org = get().userOrgs.find((o) => o.id === orgId) || null
        set({ currentOrg: org })
      },

      setLoading: (loading) => set({ isLoading: loading }),

      setError: (error) => set({ error }),

      clearOrg: () => set({ currentOrg: null, userOrgs: [], error: null }),
    }),
    {
      name: 'empire-org-storage',
      partialize: (state) => ({
        currentOrg: state.currentOrg,
      }),
    }
  )
)
