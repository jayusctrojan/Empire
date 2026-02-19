import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PhaseIndicator } from './PhaseIndicator'

describe('PhaseIndicator', () => {
  it('renders the label text', () => {
    render(<PhaseIndicator phase="analyzing" label="Analyzing your query..." />)
    expect(screen.getByText('Analyzing your query...')).toBeInTheDocument()
  })

  it('renders with analyzing phase styles', () => {
    const { container } = render(<PhaseIndicator phase="analyzing" label="Analyzing..." />)
    const dot = container.querySelector('.animate-pulse')
    expect(dot).not.toBeNull()
    expect(dot).toHaveClass('bg-blue-400')
  })

  it('renders with searching phase styles', () => {
    const { container } = render(<PhaseIndicator phase="searching" label="Searching..." />)
    const dot = container.querySelector('.animate-pulse')
    expect(dot).not.toBeNull()
    expect(dot).toHaveClass('bg-yellow-400')
  })

  it('renders with reasoning phase styles', () => {
    const { container } = render(<PhaseIndicator phase="reasoning" label="Reasoning..." />)
    const dot = container.querySelector('.animate-pulse')
    expect(dot).not.toBeNull()
    expect(dot).toHaveClass('bg-purple-400')
  })

  it('renders with formatting phase styles', () => {
    const { container } = render(<PhaseIndicator phase="formatting" label="Formatting..." />)
    const dot = container.querySelector('.animate-pulse')
    expect(dot).not.toBeNull()
    expect(dot).toHaveClass('bg-green-400')
  })

  it('falls back to analyzing style for unknown phase', () => {
    const { container } = render(
      <PhaseIndicator phase={'unknown' as never} label="Processing..." />
    )
    const dot = container.querySelector('.animate-pulse')
    expect(dot).not.toBeNull()
    expect(dot).toHaveClass('bg-blue-400')
  })
})
