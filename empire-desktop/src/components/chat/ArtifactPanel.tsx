import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { X, FileDown, FileText, Table, Presentation, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Artifact, ArtifactFormat } from '@/types'

interface ArtifactPanelProps {
  artifact: Artifact
  onClose: () => void
  onDownload?: (artifact: Artifact, format?: ArtifactFormat) => void
}

const formatLabels: Record<ArtifactFormat, string> = {
  docx: 'Word Document',
  xlsx: 'Spreadsheet',
  pptx: 'Presentation',
  pdf: 'PDF Document',
  md: 'Markdown',
}

const formatIcons: Record<ArtifactFormat, typeof FileText> = {
  docx: FileText,
  xlsx: Table,
  pptx: Presentation,
  pdf: FileText,
  md: FileText,
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ArtifactPanel({ artifact, onClose, onDownload }: ArtifactPanelProps) {
  const [showDownloadMenu, setShowDownloadMenu] = useState(false)
  const downloadMenuRef = useRef<HTMLDivElement>(null)
  const Icon = formatIcons[artifact.format] || FileText

  // Close download menu on outside click
  useEffect(() => {
    if (!showDownloadMenu) return
    function handleClick(e: MouseEvent) {
      if (downloadMenuRef.current && !downloadMenuRef.current.contains(e.target as Node)) {
        setShowDownloadMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showDownloadMenu])

  // Close panel or dropdown on Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (showDownloadMenu) {
          setShowDownloadMenu(false)
        } else {
          onClose()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [showDownloadMenu, onClose])

  return (
    <div className="w-[40%] min-w-[320px] max-w-[600px] h-full border-l border-empire-border bg-empire-sidebar flex flex-col animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-empire-border">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="w-5 h-5 flex-shrink-0 text-empire-text-muted" />
          <div className="min-w-0">
            <h3 className="text-sm font-medium truncate">{artifact.title}</h3>
            <p className="text-xs text-empire-text-muted">
              {formatLabels[artifact.format]} &middot; {formatFileSize(artifact.sizeBytes)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {/* Download button with dropdown */}
          <div className="relative" ref={downloadMenuRef}>
            <button
              onClick={() => setShowDownloadMenu(!showDownloadMenu)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white text-sm transition-colors"
            >
              <FileDown className="w-4 h-4" />
              Download
              <ChevronDown className="w-3 h-3" />
            </button>
            {showDownloadMenu && (
              <div className="absolute right-0 top-full mt-1 w-48 rounded-lg bg-empire-card border border-empire-border shadow-xl z-10">
                <button
                  onClick={() => {
                    onDownload?.(artifact)
                    setShowDownloadMenu(false)
                  }}
                  className="w-full px-3 py-2 text-sm text-left hover:bg-empire-border transition-colors rounded-t-lg"
                >
                  Original ({artifact.format.toUpperCase()})
                </button>
                {artifact.format !== 'md' && (
                  <button
                    onClick={() => {
                      onDownload?.(artifact, 'md')
                      setShowDownloadMenu(false)
                    }}
                    className="w-full px-3 py-2 text-sm text-left hover:bg-empire-border transition-colors rounded-b-lg"
                  >
                    Markdown
                  </button>
                )}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Preview content */}
      <div className="flex-1 overflow-y-auto p-4">
        {artifact.previewMarkdown ? (
          <div className="prose dark:prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {artifact.previewMarkdown}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-empire-text-muted">
            <Icon className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm">Preview not available</p>
            <p className="text-xs mt-1">Download to view the full document</p>
          </div>
        )}
      </div>
    </div>
  )
}
