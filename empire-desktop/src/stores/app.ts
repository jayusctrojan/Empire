import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Settings, User } from '@/types'

interface AppState {
  // User state
  user: User | null
  isAuthenticated: boolean

  // UI state
  sidebarOpen: boolean
  activeView: 'chats' | 'projects' | 'settings'

  // Settings
  settings: Settings

  // Actions
  setUser: (user: User | null) => void
  toggleSidebar: () => void
  setActiveView: (view: 'chats' | 'projects' | 'settings') => void
  updateSettings: (settings: Partial<Settings>) => void
  logout: () => void
}

const defaultSettings: Settings = {
  theme: 'dark',
  fontSize: 'medium',
  keyboardShortcutsEnabled: true,
  apiEndpoint: 'https://jb-empire-api.onrender.com',
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Initial state
      user: null,
      isAuthenticated: false,
      sidebarOpen: true,
      activeView: 'chats',
      settings: defaultSettings,

      // Actions
      setUser: (user) => set({ user, isAuthenticated: !!user }),

      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      setActiveView: (activeView) => set({ activeView }),

      updateSettings: (newSettings) =>
        set((state) => ({
          settings: { ...state.settings, ...newSettings },
        })),

      logout: () => set({ user: null, isAuthenticated: false }),
    }),
    {
      name: 'empire-app-storage',
      partialize: (state) => ({
        settings: state.settings,
        sidebarOpen: state.sidebarOpen,
      }),
    }
  )
)
