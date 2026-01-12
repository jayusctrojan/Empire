# Quickstart: Markdown-Aware Document Splitting

**Feature**: 006-markdown-chunking
**Date**: 2026-01-11

## Overview

This guide shows how to use the new `MarkdownChunkerStrategy` for header-aware document splitting in Empire's RAG pipeline.

---

## Basic Usage

### 1. Direct Chunking

```python
from app.services.chunking_service import MarkdownChunkerStrategy

# Create chunker with defaults (1024 tokens, 200 overlap)
chunker = MarkdownChunkerStrategy()

# Chunk markdown content
markdown_text = """
# Chapter 1: Introduction

This is the introduction section.

## Overview

The overview provides context.

## Goals

Our main goals are...

# Chapter 2: Methods

This chapter covers methods.
"""

nodes = chunker.chunk(markdown_text)

# Each node has header-aware metadata
for node in nodes:
    print(f"Header: {node.metadata['section_header']}")
    print(f"Level: {node.metadata['header_level']}")
    print(f"Hierarchy: {node.metadata['header_hierarchy']}")
    print(f"Content preview: {node.text[:100]}...")
    print("---")
```

**Output:**
```
Header: # Chapter 1: Introduction
Level: 1
Hierarchy: {'h1': 'Chapter 1: Introduction'}
Content preview: # Chapter 1: Introduction

This is the introduction section....
---
Header: ## Overview
Level: 2
Hierarchy: {'h1': 'Chapter 1: Introduction', 'h2': 'Overview'}
Content preview: ## Overview

The overview provides context....
---
...
```

---

### 2. With Custom Configuration

```python
from app.services.chunking_service import (
    MarkdownChunkerStrategy,
    MarkdownChunkerConfig
)

config = MarkdownChunkerConfig(
    max_chunk_size=512,        # Smaller chunks
    chunk_overlap=100,         # Less overlap
    min_headers_threshold=3,   # Require more headers to trigger
    include_header_in_chunk=True,
)

chunker = MarkdownChunkerStrategy(config=config)
nodes = chunker.chunk(markdown_text)
```

---

### 3. Checking if Content is Markdown

```python
chunker = MarkdownChunkerStrategy()

# Check before chunking
if chunker.is_markdown_content(text):
    nodes = chunker.chunk(text)
else:
    # Use fallback strategy
    nodes = sentence_splitter.chunk(text)
```

---

## Integration with Document Processing

### Automatic Detection in Pipeline

The document processor automatically detects markdown and routes to the appropriate chunker:

```python
from app.services.document_processor import process_document

# Markdown is auto-detected
result = await process_document(
    source_id="abc-123",
    file_path="/path/to/document.pdf"
)

# LlamaParse outputs markdown → MarkdownChunkerStrategy used
# Plain text → SentenceSplitter fallback
```

---

### Manual Strategy Selection

```python
from app.services.chunking_service import ChunkingStrategyType

result = await process_document(
    source_id="abc-123",
    file_path="/path/to/document.pdf",
    chunking_strategy=ChunkingStrategyType.MARKDOWN  # Force markdown
)
```

---

## Working with Chunk Metadata

### Filtering by Section

```python
# Filter chunks by header level
h2_chunks = [
    node for node in nodes
    if node.metadata.get('header_level') == 2
]

# Find chunks under a specific parent
intro_chunks = [
    node for node in nodes
    if 'Introduction' in node.metadata.get('header_hierarchy', {}).get('h1', '')
]
```

### Checking Split Type

```python
for node in nodes:
    if node.metadata.get('is_header_split'):
        print(f"Header-split chunk: {node.metadata['section_header']}")
    else:
        # This chunk was sentence-split from a large section
        idx = node.metadata['chunk_index']
        total = node.metadata['total_section_chunks']
        print(f"Sentence-split chunk {idx+1}/{total} from: {node.metadata['section_header']}")
```

---

## Handling Large Sections

When a section exceeds `max_chunk_size`, it's automatically subdivided:

```python
# Large section (>1024 tokens) → multiple chunks
nodes = chunker.chunk(document_with_large_section)

for node in nodes:
    if not node.metadata.get('is_header_split'):
        print(f"Large section '{node.metadata['section_header']}' was split into "
              f"{node.metadata['total_section_chunks']} chunks")
```

Each sub-chunk retains the section header in metadata for context.

---

## Example: Processing a PDF

```python
from llama_parse import LlamaParse
from app.services.chunking_service import MarkdownChunkerStrategy

# Parse PDF to markdown
parser = LlamaParse(
    api_key=settings.LLAMA_CLOUD_API_KEY,
    result_type="markdown"
)
documents = parser.load_data("policy.pdf")

# Chunk with header awareness
chunker = MarkdownChunkerStrategy()
all_nodes = []

for doc in documents:
    if chunker.is_markdown_content(doc.text):
        nodes = chunker.chunk(
            doc.text,
            metadata={"source_file": "policy.pdf"}
        )
    else:
        # Fallback for non-markdown content
        nodes = fallback_chunker.chunk(doc.text)

    all_nodes.extend(nodes)

# Store in vector database
await vector_store.add_nodes(all_nodes)
```

---

## Metadata Schema Reference

Each chunk includes:

| Field | Type | Description |
|-------|------|-------------|
| `section_header` | str | Header text (e.g., "## Methods") |
| `header_level` | int | Level 1-6 |
| `header_hierarchy` | dict | Parent headers by level |
| `is_header_split` | bool | True if boundary is header |
| `chunk_index` | int | Position in section |
| `total_section_chunks` | int | Total chunks in section |

---

## Troubleshooting

### Markdown Not Detected

```python
# Check header count
import re
headers = re.findall(r'^#{1,6}\s+.+$', text, re.MULTILINE)
print(f"Found {len(headers)} headers")

# Default threshold is 2
# Adjust if needed:
config = MarkdownChunkerConfig(min_headers_threshold=1)
```

### Chunks Too Large

```python
# Reduce max_chunk_size
config = MarkdownChunkerConfig(max_chunk_size=512)
chunker = MarkdownChunkerStrategy(config=config)
```

### Missing Header Hierarchy

```python
# Ensure preserve_hierarchy is True (default)
config = MarkdownChunkerConfig(preserve_hierarchy=True)
```

---

## Next Steps

- See [data-model.md](./data-model.md) for full entity definitions
- See [contracts/](./contracts/) for interface specifications
- See [research.md](./research.md) for design decisions
