import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Building2, Check, LogOut } from 'lucide-react'
import { useOrgStore } from '@/stores/org'
import type { Organization } from '@/stores/org'

export function OrgSwitcher() {
  const { currentOrg, userOrgs, setCurrentOrg, clearOrg } = useOrgStore()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click or Escape
  useEffect(() => {
    if (!isOpen) return
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  if (!currentOrg) return null

  const handleSwitch = (org: Organization) => {
    setCurrentOrg(org)
    setIsOpen(false)
  }

  const handleChangeOrg = () => {
    clearOrg()
    setIsOpen(false)
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-empire-surface-hover transition-colors"
      >
        {currentOrg.logoUrl ? (
          <img
            src={currentOrg.logoUrl}
            alt={currentOrg.name}
            className="w-6 h-6 rounded object-cover"
          />
        ) : (
          <div className="w-6 h-6 rounded bg-empire-primary/20 flex items-center justify-center text-empire-primary text-xs font-semibold">
            {currentOrg.name.charAt(0).toUpperCase()}
          </div>
        )}
        <span className="flex-1 text-left text-sm font-medium text-empire-text truncate">
          {currentOrg.name}
        </span>
        <ChevronDown className={`w-4 h-4 text-empire-text-muted transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-empire-surface border border-empire-border rounded-lg shadow-xl overflow-hidden">
          {/* Org list */}
          <div className="max-h-60 overflow-y-auto py-1">
            {userOrgs.map((org) => (
              <button
                key={org.id}
                onClick={() => handleSwitch(org)}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-empire-surface-hover transition-colors"
              >
                {org.logoUrl ? (
                  <img src={org.logoUrl} alt={org.name} className="w-5 h-5 rounded object-cover" />
                ) : (
                  <div className="w-5 h-5 rounded bg-empire-primary/20 flex items-center justify-center text-empire-primary text-[10px] font-semibold">
                    {org.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <span className="flex-1 text-left text-sm text-empire-text truncate">{org.name}</span>
                {org.id === currentOrg.id && (
                  <Check className="w-4 h-4 text-empire-primary" />
                )}
              </button>
            ))}
          </div>

          {/* Separator + Switch option */}
          <div className="border-t border-empire-border">
            <button
              onClick={handleChangeOrg}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-empire-surface-hover transition-colors text-empire-text-muted hover:text-empire-text"
            >
              <Building2 className="w-4 h-4" />
              <span className="text-sm">Switch Organization</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
