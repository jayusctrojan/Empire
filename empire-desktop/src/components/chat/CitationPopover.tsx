import { useState } from 'react'
import { FileText, ExternalLink, X } from 'lucide-react'
import type { Source } from '@/types'

interface CitationPopoverProps {
  source: Source
  index: number
}

export function CitationPopover({ source, index }: CitationPopoverProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <span className="relative inline-block">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1 mx-0.5 text-xs font-medium rounded bg-empire-accent/30 text-empire-accent hover:bg-empire-accent/50 transition-colors"
      >
        [{index}]
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Popover */}
          <div className="absolute bottom-full left-0 z-50 mb-2 w-80 p-3 rounded-lg border border-empire-border bg-empire-sidebar shadow-xl">
            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-empire-primary/20 flex items-center justify-center">
                  <FileText className="w-4 h-4 text-empire-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-empire-text truncate">
                    {source.documentTitle}
                  </p>
                  {source.pageNumber && (
                    <p className="text-xs text-empire-text-muted">
                      Page {source.pageNumber}
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded hover:bg-empire-border text-empire-text-muted"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Excerpt */}
            <div className="p-2 rounded bg-empire-bg text-sm text-empire-text-muted leading-relaxed max-h-32 overflow-y-auto">
              "{source.excerpt}"
            </div>

            {/* Relevance score */}
            <div className="mt-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-24 rounded-full bg-empire-border overflow-hidden">
                  <div
                    className="h-full bg-empire-primary rounded-full"
                    style={{ width: `${Math.round(source.relevanceScore * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-empire-text-muted">
                  {Math.round(source.relevanceScore * 100)}% match
                </span>
              </div>
              <button
                className="flex items-center gap-1 text-xs text-empire-primary hover:text-empire-primary/80"
                title="Open document"
              >
                <ExternalLink className="w-3 h-3" />
                View
              </button>
            </div>
          </div>
        </>
      )}
    </span>
  )
}

export default CitationPopover
