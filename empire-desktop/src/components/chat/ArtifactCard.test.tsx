import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ArtifactCard } from './ArtifactCard'
import type { Artifact } from '@/types'

function makeArtifact(overrides: Partial<Artifact> = {}): Artifact {
  return {
    id: 'art-1',
    sessionId: 'sess-1',
    title: 'Q4 Revenue Report',
    format: 'docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    sizeBytes: 25600,
    status: 'ready',
    createdAt: '2026-02-15T10:00:00Z',
    ...overrides,
  }
}

describe('ArtifactCard', () => {
  it('renders artifact title and format', () => {
    render(<ArtifactCard artifact={makeArtifact()} />)
    expect(screen.getByText('Q4 Revenue Report')).toBeInTheDocument()
    expect(screen.getByText('docx')).toBeInTheDocument()
  })

  it('formats file size correctly', () => {
    render(<ArtifactCard artifact={makeArtifact({ sizeBytes: 25600 })} />)
    expect(screen.getByText('25.0 KB')).toBeInTheDocument()
  })

  it('formats MB sizes', () => {
    render(<ArtifactCard artifact={makeArtifact({ sizeBytes: 2_500_000 })} />)
    expect(screen.getByText('2.4 MB')).toBeInTheDocument()
  })

  it('shows uploading state', () => {
    render(<ArtifactCard artifact={makeArtifact({ status: 'uploading' })} />)
    expect(screen.getByText('Uploading...')).toBeInTheDocument()
  })

  it('calls onOpen when card is clicked', () => {
    const onOpen = vi.fn()
    const artifact = makeArtifact()
    render(<ArtifactCard artifact={artifact} onOpen={onOpen} />)

    // Click the card area (the outer div)
    fireEvent.click(screen.getByText('Q4 Revenue Report'))
    expect(onOpen).toHaveBeenCalledWith(artifact)
  })

  it('calls onDownload when download button is clicked', () => {
    const onDownload = vi.fn()
    const onOpen = vi.fn()
    const artifact = makeArtifact()
    render(<ArtifactCard artifact={artifact} onOpen={onOpen} onDownload={onDownload} />)

    const downloadBtn = screen.getByTitle('Download')
    fireEvent.click(downloadBtn)
    expect(onDownload).toHaveBeenCalledWith(artifact)
    // onOpen should NOT be called (stopPropagation)
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('disables buttons when uploading', () => {
    render(<ArtifactCard artifact={makeArtifact({ status: 'uploading' })} />)
    expect(screen.getByTitle('Preview')).toBeDisabled()
    expect(screen.getByTitle('Download')).toBeDisabled()
  })

  it('renders different format styles', () => {
    const { rerender } = render(<ArtifactCard artifact={makeArtifact({ format: 'xlsx' })} />)
    expect(screen.getByText('xlsx')).toBeInTheDocument()

    rerender(<ArtifactCard artifact={makeArtifact({ format: 'pptx' })} />)
    expect(screen.getByText('pptx')).toBeInTheDocument()

    rerender(<ArtifactCard artifact={makeArtifact({ format: 'pdf' })} />)
    expect(screen.getByText('pdf')).toBeInTheDocument()
  })
})
