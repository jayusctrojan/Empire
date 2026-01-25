import { useState } from 'react'
import {
  Settings,
  Sun,
  Moon,
  Monitor,
  Download,
  Keyboard,
  Database,
  Trash2,
  Check,
  ExternalLink,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useThemeContext } from '@/components/ThemeProvider'
import { KEYBOARD_SHORTCUTS } from '@/hooks'
import { getConversations, getMessages } from '@/lib/database'
import type { Theme } from '@/hooks'

type SettingsSection = 'appearance' | 'shortcuts' | 'data' | 'about'

export function SettingsView() {
  const [activeSection, setActiveSection] = useState<SettingsSection>('appearance')
  const [isExporting, setIsExporting] = useState(false)
  const [exportSuccess, setExportSuccess] = useState(false)

  const sections = [
    { id: 'appearance' as const, label: 'Appearance', icon: Sun },
    { id: 'shortcuts' as const, label: 'Keyboard Shortcuts', icon: Keyboard },
    { id: 'data' as const, label: 'Data & Export', icon: Database },
    { id: 'about' as const, label: 'About', icon: Settings },
  ]

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <nav className="w-56 border-r border-empire-border bg-empire-sidebar p-4">
        <h1 className="text-lg font-semibold text-empire-text mb-4 flex items-center gap-2">
          <Settings className="w-5 h-5" />
          Settings
        </h1>
        <ul className="space-y-1">
          {sections.map((section) => (
            <li key={section.id}>
              <button
                onClick={() => setActiveSection(section.id)}
                className={cn(
                  'flex items-center gap-3 w-full px-3 py-2 rounded-lg transition-colors',
                  activeSection === section.id
                    ? 'bg-empire-primary/20 text-empire-text'
                    : 'text-empire-text-muted hover:bg-empire-border hover:text-empire-text'
                )}
              >
                <section.icon className="w-4 h-4" />
                <span className="text-sm">{section.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-8">
        {activeSection === 'appearance' && <AppearanceSection />}
        {activeSection === 'shortcuts' && <ShortcutsSection />}
        {activeSection === 'data' && (
          <DataSection
            isExporting={isExporting}
            setIsExporting={setIsExporting}
            exportSuccess={exportSuccess}
            setExportSuccess={setExportSuccess}
          />
        )}
        {activeSection === 'about' && <AboutSection />}
      </main>
    </div>
  )
}

function AppearanceSection() {
  const { theme, setTheme } = useThemeContext()

  const themes: { id: Theme; label: string; icon: typeof Sun }[] = [
    { id: 'light', label: 'Light', icon: Sun },
    { id: 'dark', label: 'Dark', icon: Moon },
    { id: 'system', label: 'System', icon: Monitor },
  ]

  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-empire-text mb-6">Appearance</h2>

      <div className="space-y-6">
        <div>
          <h3 className="text-sm font-medium text-empire-text mb-3">Theme</h3>
          <div className="grid grid-cols-3 gap-3">
            {themes.map((t) => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className={cn(
                  'flex flex-col items-center gap-3 p-4 rounded-lg border transition-all',
                  theme === t.id
                    ? 'border-empire-primary bg-empire-primary/10'
                    : 'border-empire-border hover:border-empire-primary/50'
                )}
              >
                <t.icon
                  className={cn(
                    'w-6 h-6',
                    theme === t.id ? 'text-empire-primary' : 'text-empire-text-muted'
                  )}
                />
                <span
                  className={cn(
                    'text-sm',
                    theme === t.id ? 'text-empire-primary' : 'text-empire-text-muted'
                  )}
                >
                  {t.label}
                </span>
                {theme === t.id && (
                  <Check className="w-4 h-4 text-empire-primary" />
                )}
              </button>
            ))}
          </div>
          <p className="text-xs text-empire-text-muted mt-2">
            Choose how Empire Desktop looks. System mode follows your macOS appearance.
          </p>
        </div>
      </div>
    </div>
  )
}

function ShortcutsSection() {
  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-empire-text mb-6">
        Keyboard Shortcuts
      </h2>

      <div className="space-y-4">
        {KEYBOARD_SHORTCUTS.map((shortcut, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between py-3 border-b border-empire-border last:border-0"
          >
            <span className="text-sm text-empire-text">{shortcut.description}</span>
            <div className="flex items-center gap-1">
              {shortcut.keys.map((key, keyIdx) => (
                <kbd
                  key={keyIdx}
                  className="px-2 py-1 rounded bg-empire-border text-xs text-empire-text font-mono"
                >
                  {key}
                </kbd>
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-empire-text-muted mt-4">
        Tip: Use these shortcuts to navigate Empire Desktop faster.
      </p>
    </div>
  )
}

interface DataSectionProps {
  isExporting: boolean
  setIsExporting: (value: boolean) => void
  exportSuccess: boolean
  setExportSuccess: (value: boolean) => void
}

function DataSection({
  isExporting,
  setIsExporting,
  exportSuccess,
  setExportSuccess,
}: DataSectionProps) {
  const handleExportChats = async () => {
    setIsExporting(true)
    setExportSuccess(false)

    try {
      const conversations = await getConversations()
      const allData = await Promise.all(
        conversations.map(async (conv) => {
          const messages = await getMessages(conv.id)
          return {
            ...conv,
            messages,
          }
        })
      )

      const blob = new Blob([JSON.stringify(allData, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `empire-chats-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      setExportSuccess(true)
      setTimeout(() => setExportSuccess(false), 3000)
    } catch (err) {
      console.error('Export failed:', err)
    } finally {
      setIsExporting(false)
    }
  }


  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-empire-text mb-6">Data & Export</h2>

      <div className="space-y-6">
        {/* Export Chats */}
        <div className="p-4 rounded-lg border border-empire-border">
          <div className="flex items-start gap-4">
            <div className="p-2 rounded-lg bg-empire-primary/10">
              <Download className="w-5 h-5 text-empire-primary" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-empire-text mb-1">
                Export Conversations
              </h3>
              <p className="text-xs text-empire-text-muted mb-3">
                Download all your conversations and messages as a JSON file.
              </p>
              <button
                onClick={handleExportChats}
                disabled={isExporting}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                  'bg-empire-primary hover:bg-empire-primary/80 text-white disabled:opacity-50'
                )}
              >
                {isExporting ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : exportSuccess ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <Download className="w-4 h-4" />
                )}
                {exportSuccess ? 'Exported!' : 'Export JSON'}
              </button>
            </div>
          </div>
        </div>

        {/* Clear Data */}
        <div className="p-4 rounded-lg border border-red-500/30 bg-red-500/5">
          <div className="flex items-start gap-4">
            <div className="p-2 rounded-lg bg-red-500/10">
              <Trash2 className="w-5 h-5 text-red-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-empire-text mb-1">
                Clear Local Data
              </h3>
              <p className="text-xs text-empire-text-muted mb-3">
                Delete all local conversations and settings. This cannot be undone.
              </p>
              <button
                onClick={() => {
                  if (
                    confirm(
                      'Are you sure you want to delete all local data? This cannot be undone.'
                    )
                  ) {
                    // TODO: Implement clear data
                    console.log('Clear data')
                  }
                }}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm bg-red-500/20 hover:bg-red-500/30 text-red-400 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Clear Data
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AboutSection() {
  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-semibold text-empire-text mb-6">About</h2>

      <div className="space-y-6">
        {/* App Info */}
        <div className="p-6 rounded-lg border border-empire-border bg-empire-card/50">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-xl bg-empire-primary flex items-center justify-center">
              <span className="text-white text-xl font-bold">E</span>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-empire-text">Empire Desktop</h3>
              <p className="text-sm text-empire-text-muted">Version 0.1.0</p>
            </div>
          </div>
          <p className="text-sm text-empire-text-muted">
            Native macOS application for interacting with the Empire v7.3 knowledge
            base. Features streaming responses, source citations, and project
            management.
          </p>
        </div>

        {/* Links */}
        <div className="space-y-2">
          <a
            href="https://github.com/jaybajaj/empire"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between p-3 rounded-lg border border-empire-border hover:bg-empire-border/50 transition-colors"
          >
            <span className="text-sm text-empire-text">GitHub Repository</span>
            <ExternalLink className="w-4 h-4 text-empire-text-muted" />
          </a>
          <a
            href="https://docs.empire.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between p-3 rounded-lg border border-empire-border hover:bg-empire-border/50 transition-colors"
          >
            <span className="text-sm text-empire-text">Documentation</span>
            <ExternalLink className="w-4 h-4 text-empire-text-muted" />
          </a>
        </div>

        {/* Credits */}
        <div className="pt-4 border-t border-empire-border">
          <p className="text-xs text-empire-text-muted text-center">
            Built with Tauri 2.0 + React + TypeScript
          </p>
        </div>
      </div>
    </div>
  )
}

export default SettingsView
