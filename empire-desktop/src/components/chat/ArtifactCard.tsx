import { FileText, Table, Presentation, FileDown, ExternalLink, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Artifact, ArtifactFormat } from '@/types'

interface ArtifactCardProps {
  artifact: Artifact
  onOpen?: (artifact: Artifact) => void
  onDownload?: (artifact: Artifact) => void
}

const formatConfig: Record<ArtifactFormat, { icon: typeof FileText; color: string; label: string }> = {
  docx: { icon: FileText, color: 'border-blue-500/50 bg-blue-500/10', label: 'Word Document' },
  xlsx: { icon: Table, color: 'border-green-500/50 bg-green-500/10', label: 'Spreadsheet' },
  pptx: { icon: Presentation, color: 'border-orange-500/50 bg-orange-500/10', label: 'Presentation' },
  pdf: { icon: FileText, color: 'border-red-500/50 bg-red-500/10', label: 'PDF Document' },
  md: { icon: FileText, color: 'border-gray-500/50 bg-gray-500/10', label: 'Markdown' },
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ArtifactCard({ artifact, onOpen, onDownload }: ArtifactCardProps) {
  const config = formatConfig[artifact.format] || formatConfig.docx
  const Icon = config.icon
  const isUploading = artifact.status === 'uploading'

  return (
    <div
      className={cn(
        'mt-3 rounded-xl border-2 p-3 transition-colors',
        config.color,
        !isUploading && 'cursor-pointer hover:bg-white/5'
      )}
      onClick={() => !isUploading && onOpen?.(artifact)}
    >
      <div className="flex items-center gap-3">
        <div className="flex-shrink-0 p-2 rounded-lg bg-white/10">
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{artifact.title}</p>
          <div className="flex items-center gap-2 text-xs text-empire-text-muted">
            <span className="uppercase font-medium">{artifact.format}</span>
            <span>{formatFileSize(artifact.sizeBytes)}</span>
            {isUploading && (
              <span className="flex items-center gap-1 text-yellow-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                Uploading...
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onOpen?.(artifact)
            }}
            className="p-1.5 rounded-lg hover:bg-white/10 text-empire-text-muted hover:text-empire-text transition-colors"
            title="Preview"
            disabled={isUploading}
          >
            <ExternalLink className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDownload?.(artifact)
            }}
            className="p-1.5 rounded-lg hover:bg-white/10 text-empire-text-muted hover:text-empire-text transition-colors"
            title="Download"
            disabled={isUploading}
          >
            <FileDown className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
