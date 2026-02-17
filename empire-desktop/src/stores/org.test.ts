import { describe, it, expect, beforeEach } from 'vitest'
import { useOrgStore } from './org'
import type { Organization } from './org'

function makeOrg(overrides: Partial<Organization> = {}): Organization {
  return {
    id: 'org-1',
    name: 'Acme Corp',
    slug: 'acme-corp',
    settings: {},
    memberCount: 5,
    ...overrides,
  }
}

describe('useOrgStore', () => {
  beforeEach(() => {
    // Reset store between tests — direct setState, no act() needed for non-rendered hooks
    useOrgStore.setState({
      currentOrg: null,
      userOrgs: [],
      isLoading: false,
      error: null,
    })
  })

  it('starts with null currentOrg', () => {
    expect(useOrgStore.getState().currentOrg).toBeNull()
  })

  it('sets current org', () => {
    const org = makeOrg()
    useOrgStore.getState().setCurrentOrg(org)
    expect(useOrgStore.getState().currentOrg).toEqual(org)
  })

  it('sets user orgs list', () => {
    const orgs = [makeOrg(), makeOrg({ id: 'org-2', name: 'Beta Inc', slug: 'beta' })]
    useOrgStore.getState().setUserOrgs(orgs)
    expect(useOrgStore.getState().userOrgs).toHaveLength(2)
  })

  it('selects org by id', () => {
    const org1 = makeOrg()
    const org2 = makeOrg({ id: 'org-2', name: 'Beta Inc', slug: 'beta' })
    useOrgStore.getState().setUserOrgs([org1, org2])
    useOrgStore.getState().selectOrg('org-2')
    expect(useOrgStore.getState().currentOrg?.name).toBe('Beta Inc')
  })

  it('selectOrg sets null for unknown id', () => {
    useOrgStore.getState().setUserOrgs([makeOrg()])
    useOrgStore.getState().selectOrg('nonexistent')
    expect(useOrgStore.getState().currentOrg).toBeNull()
  })

  it('sets loading state', () => {
    useOrgStore.getState().setLoading(true)
    expect(useOrgStore.getState().isLoading).toBe(true)
    useOrgStore.getState().setLoading(false)
    expect(useOrgStore.getState().isLoading).toBe(false)
  })

  it('sets error state', () => {
    useOrgStore.getState().setError('Something went wrong')
    expect(useOrgStore.getState().error).toBe('Something went wrong')
  })

  it('clearOrg resets state', () => {
    useOrgStore.getState().setCurrentOrg(makeOrg())
    useOrgStore.getState().setUserOrgs([makeOrg()])
    useOrgStore.getState().setError('error')
    useOrgStore.getState().clearOrg()

    const state = useOrgStore.getState()
    expect(state.currentOrg).toBeNull()
    expect(state.userOrgs).toEqual([])
    expect(state.error).toBeNull()
  })
})
