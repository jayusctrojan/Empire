# Data Model: Markdown-Aware Document Splitting

**Feature**: 006-markdown-chunking
**Date**: 2026-01-11
**Status**: Complete

## Overview

This document defines the data structures for markdown-aware document splitting. The design extends existing chunking infrastructure with minimal changes to support header-based splitting.

---

## Entities

### 1. MarkdownSection

Represents a document section defined by a markdown header.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class MarkdownSection:
    """A document section extracted from markdown content."""

    header: str
    """The full header text including # markers (e.g., '## Methods')"""

    header_text: str
    """The header text without # markers (e.g., 'Methods')"""

    level: int
    """Header level 1-6 (h1=1, h2=2, etc.)"""

    content: str
    """Section content including the header line"""

    start_line: int
    """Line number where section starts (0-indexed)"""

    end_line: int
    """Line number where section ends (exclusive)"""

    parent_headers: list[str]
    """Parent header chain, e.g., ['# Chapter 1', '## Introduction']"""

    @property
    def content_only(self) -> str:
        """Content without the header line."""
        lines = self.content.split('\n')
        return '\n'.join(lines[1:]).strip()

    @property
    def token_count(self) -> int:
        """Approximate token count (set by chunker)."""
        return getattr(self, '_token_count', 0)
```

**Validation Rules**:
- `level` must be 1-6
- `header` must match pattern `^#{level}\s+.+$`
- `content` must start with `header`
- `start_line` < `end_line`

---

### 2. ChunkMetadata (Extended)

Extended metadata schema for chunks produced by markdown splitting.

```python
from typing import TypedDict, Optional

class MarkdownChunkMetadata(TypedDict, total=False):
    """Extended metadata for markdown-aware chunks."""

    # Standard chunk metadata (existing)
    source_id: str
    """UUID of the source document"""

    file_name: str
    """Original file name"""

    file_type: str
    """MIME type or extension"""

    # Markdown-specific metadata (new)
    section_header: str
    """The header text for this section (e.g., '## Methods')"""

    header_level: int
    """Header level 1-6"""

    header_hierarchy: dict[str, str]
    """Parent headers by level, e.g., {'h1': 'Chapter 1', 'h2': 'Methods'}"""

    is_header_split: bool
    """True if chunk boundary is a header, False if sentence-split fallback"""

    chunk_index: int
    """Position within section (0 for header-split, 0-N for sentence-split)"""

    total_section_chunks: int
    """Total chunks in this section (1 for header-split, N for sentence-split)"""
```

**Metadata Examples**:

```python
# Chunk from header-split section
{
    "source_id": "abc-123",
    "file_name": "policy.pdf",
    "section_header": "## Claims Process",
    "header_level": 2,
    "header_hierarchy": {
        "h1": "Insurance Guidelines",
        "h2": "Claims Process"
    },
    "is_header_split": True,
    "chunk_index": 0,
    "total_section_chunks": 1
}

# Chunk from sentence-split large section (2nd of 3)
{
    "source_id": "abc-123",
    "file_name": "policy.pdf",
    "section_header": "## Detailed Procedures",
    "header_level": 2,
    "header_hierarchy": {
        "h1": "Insurance Guidelines",
        "h2": "Detailed Procedures"
    },
    "is_header_split": False,
    "chunk_index": 1,
    "total_section_chunks": 3
}
```

---

### 3. MarkdownChunkerConfig

Configuration for the markdown chunking strategy.

```python
from dataclasses import dataclass, field

@dataclass
class MarkdownChunkerConfig:
    """Configuration for MarkdownChunkerStrategy."""

    max_chunk_size: int = 1024
    """Maximum tokens per chunk"""

    chunk_overlap: int = 200
    """Token overlap between sentence-split chunks"""

    min_headers_threshold: int = 2
    """Minimum headers required to trigger markdown splitting"""

    include_header_in_chunk: bool = True
    """Whether to include header text in chunk content"""

    preserve_hierarchy: bool = True
    """Whether to build and store header hierarchy"""

    headers_to_split_on: list[tuple[str, str]] = field(default_factory=lambda: [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
        ("####", "h4"),
        ("#####", "h5"),
        ("######", "h6"),
    ])
    """Header patterns to split on (marker, name)"""

    max_header_length: int = 200
    """Maximum header text length in metadata (truncate if longer)"""
```

---

## Relationships

```
┌─────────────────┐     ┌──────────────────┐
│   Source        │     │  MarkdownSection │
│   Document      │────▶│  (intermediate)  │
└─────────────────┘     └──────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │    TextNode      │
                        │  (with extended  │
                        │   metadata)      │
                        └──────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  Vector Store    │
                        │  (Supabase)      │
                        └──────────────────┘
```

**Flow**:
1. Source document → LlamaParse → Markdown text
2. Markdown text → MarkdownChunkerStrategy → list[MarkdownSection]
3. MarkdownSection → TextNode with MarkdownChunkMetadata
4. TextNode → Vector store (existing pipeline)

---

## State Transitions

### Document Processing States

```
[Raw Document]
      │
      ▼ (LlamaParse)
[Markdown Text]
      │
      ▼ (detect headers)
      ├── Has headers ──▶ [Markdown Splitting]
      │                         │
      │                         ▼
      │                   [Sections Extracted]
      │                         │
      │                         ▼ (per section)
      │                   ┌─────┴─────┐
      │                   │           │
      │              ≤1024 tokens  >1024 tokens
      │                   │           │
      │                   ▼           ▼
      │            [Header Split] [Sentence Split]
      │                   │           │
      │                   └─────┬─────┘
      │                         │
      └── No headers ──────────▶│
                                ▼
                         [TextNodes with Metadata]
                                │
                                ▼
                         [Vector Store]
```

---

## Validation Rules

### MarkdownSection Validation

| Field | Rule | Error |
|-------|------|-------|
| level | 1-6 | "Invalid header level: {level}" |
| header | Matches `^#{level}\s+` | "Header format mismatch" |
| content | Non-empty | "Section content cannot be empty" |
| start_line | >= 0 | "Invalid start line" |
| end_line | > start_line | "End line must be after start line" |

### Metadata Validation

| Field | Rule | Error |
|-------|------|-------|
| header_level | 1-6 | "Invalid header level" |
| chunk_index | >= 0 | "Chunk index must be non-negative" |
| total_section_chunks | >= 1 | "Total chunks must be positive" |
| chunk_index | < total_section_chunks | "Chunk index exceeds total" |

---

## Storage Considerations

### Vector Store Impact

**No schema changes required.** The extended metadata fields are stored in the existing `metadata` JSONB column.

```sql
-- Existing schema (unchanged)
CREATE TABLE documents_v2 (
    id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(1024),
    metadata JSONB,  -- Stores MarkdownChunkMetadata
    ...
);
```

### Querying by Header

To filter by section header:

```sql
SELECT * FROM documents_v2
WHERE metadata->>'section_header' ILIKE '%Methods%'
  AND (metadata->>'header_level')::int = 2;
```

### Index Recommendation (Optional, Future)

```sql
-- Only if header filtering becomes common
CREATE INDEX idx_section_header ON documents_v2
  USING gin ((metadata->'section_header'));
```

---

## Backward Compatibility

| Existing Chunk | New Chunk |
|----------------|-----------|
| No `section_header` | Has `section_header` |
| No `header_level` | Has `header_level` |
| No `is_header_split` | Has `is_header_split` |

**Handling**: Queries checking these fields should use `COALESCE` or null-safe checks:

```python
# In retrieval code
header = chunk.metadata.get("section_header", "")
is_header_split = chunk.metadata.get("is_header_split", False)
```
