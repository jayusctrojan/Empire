import { cn } from '@/lib/utils'
import type { PipelinePhase } from '@/types/api'

interface PhaseIndicatorProps {
  phase: PipelinePhase
  label: string
}

const phaseConfig: Record<PipelinePhase, { color: string; icon: string }> = {
  analyzing: { color: 'text-blue-400', icon: 'bg-blue-400' },
  searching: { color: 'text-yellow-400', icon: 'bg-yellow-400' },
  reasoning: { color: 'text-purple-400', icon: 'bg-purple-400' },
  formatting: { color: 'text-green-400', icon: 'bg-green-400' },
}

export function PhaseIndicator({ phase, label }: PhaseIndicatorProps) {
  const config = phaseConfig[phase] || phaseConfig.analyzing

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <span className={cn('w-2 h-2 rounded-full animate-pulse', config.icon)} />
      <span className={cn('text-sm', config.color)}>{label}</span>
    </div>
  )
}
