# Research: Markdown-Aware Document Splitting

**Feature**: 006-markdown-chunking
**Date**: 2026-01-11
**Status**: Complete

## Research Summary

This document consolidates findings from codebase exploration and best practices research for implementing markdown-aware document splitting in Empire's RAG pipeline.

---

## 1. Existing Chunking Infrastructure

### Current Implementation

**File**: `app/services/chunking_service.py` (770 lines)

**Existing Strategies**:
| Strategy | Purpose | Splitter Used |
|----------|---------|---------------|
| SemanticChunker | Content-aware splitting | SemanticSplitterNodeParser |
| CodeChunker | Source code files | CodeSplitter |
| TranscriptChunker | Audio/video transcripts | SentenceSplitter with custom separators |
| Generic | Default fallback | SentenceSplitter |

**Current Configuration**:
```python
SentenceSplitter(
    chunk_size=1024,      # tokens
    chunk_overlap=200,    # tokens
    paragraph_separator="\n\n",
)
```

**Key Observation**: No existing strategy uses `MarkdownNodeParser` despite LlamaParse outputting markdown.

### ChunkingStrategy Interface

```python
class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, text: str, metadata: dict = None) -> list[TextNode]:
        """Split text into nodes."""
        pass
```

All strategies return `list[TextNode]` from LlamaIndex, which is already compatible with the vector store pipeline.

---

## 2. LlamaIndex Markdown Parsers

### Option A: MarkdownNodeParser (Recommended)

**Import**: `from llama_index.core.node_parser import MarkdownNodeParser`

**Behavior**:
- Splits on markdown headers (h1-h6)
- Preserves header text in node content
- Sets `header_path` in metadata automatically
- Handles nested headers correctly

**Pros**:
- Native LlamaIndex support
- Produces TextNode objects (compatible with existing pipeline)
- Well-tested, maintained

**Cons**:
- May not respect max chunk size (large sections stay as-is)
- Limited customization for metadata format

### Option B: MarkdownElementNodeParser

**Import**: `from llama_index.core.node_parser import MarkdownElementNodeParser`

**Behavior**:
- Extracts structured elements (tables, code blocks)
- Creates separate nodes for different element types
- More granular parsing

**Pros**:
- Better for complex documents with tables/code
- Element-type metadata

**Cons**:
- More complex output to handle
- May over-fragment simple text sections

### Decision: Hybrid Custom Approach

Use custom `MarkdownChunkerStrategy` that:
1. Uses regex header detection for splitting
2. Leverages `SentenceSplitter` for oversized sections
3. Builds custom metadata format matching spec requirements

**Rationale**: More control over chunk size limits and metadata schema while still using LlamaIndex primitives.

---

## 3. LlamaParse Integration

### Current Flow

**File**: `app/tasks/source_processing.py` (~line 380)

```python
parser = LlamaParse(
    api_key=settings.LLAMA_CLOUD_API_KEY,
    result_type="markdown",  # Already outputs markdown!
    parsing_instruction="...",
)
documents = parser.load_data(file_path)
```

**Gap Identified**: The markdown output from LlamaParse goes directly to `SentenceSplitter`, which ignores header structure.

### Integration Point

After LlamaParse returns markdown:
1. Detect if content contains markdown headers
2. Route to `MarkdownChunkerStrategy` if headers found
3. Fall back to existing strategy if no headers

---

## 4. Header Detection Algorithm

### Regex Pattern

```python
HEADER_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
```

**Matches**:
- `# Header 1` → level 1
- `## Header 2` → level 2
- `### Header 3` → level 3
- etc.

**Does NOT Match** (intentional):
- `#NoSpace` → not valid markdown header
- `####### TooMany` → only h1-h6 valid
- `Code with # comment` → inline text

### Markdown Detection Heuristic

```python
def is_markdown_content(text: str, min_headers: int = 2) -> bool:
    """Returns True if text appears to be markdown with headers."""
    headers = HEADER_PATTERN.findall(text)
    return len(headers) >= min_headers
```

**Threshold**: Require at least 2 headers to trigger markdown splitting. Single header could be coincidental.

---

## 5. Header Hierarchy Algorithm

### Building Parent Chain

```python
def build_hierarchy(headers: list[tuple[int, str]]) -> dict:
    """
    Input: [(1, "Chapter 1"), (2, "Intro"), (3, "Overview"), (2, "Methods")]

    For index 2 ("Overview"):
    Output: {"h1": "Chapter 1", "h2": "Intro", "h3": "Overview"}

    For index 3 ("Methods"):
    Output: {"h1": "Chapter 1", "h2": "Methods"}
    """
    hierarchy = {}
    stack = []  # (level, text)

    for level, text in headers[:current_index + 1]:
        # Pop headers at same or deeper level
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))

    for level, text in stack:
        hierarchy[f"h{level}"] = text

    return hierarchy
```

---

## 6. Large Section Handling

### Problem

Some markdown sections exceed 1024 tokens. Can't return as single chunk.

### Solution: Hybrid Splitting

```python
def chunk_section(section: MarkdownSection) -> list[TextNode]:
    token_count = count_tokens(section.content)

    if token_count <= self.max_chunk_size:
        # Section fits in one chunk
        return [create_node(section)]
    else:
        # Subdivide using SentenceSplitter
        sub_chunks = sentence_splitter.split_text(section.content)
        nodes = []
        for i, chunk in enumerate(sub_chunks):
            node = TextNode(
                text=chunk,
                metadata={
                    "section_header": section.header,
                    "header_level": section.level,
                    "header_hierarchy": section.hierarchy,
                    "is_header_split": False,  # Was sentence-split
                    "chunk_index": i,
                }
            )
            nodes.append(node)
        return nodes
```

---

## 7. Performance Considerations

### Token Counting

Use `tiktoken` (already in dependencies) for accurate token counts:

```python
import tiktoken

encoder = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(encoder.encode(text))
```

### Caching

For documents processed multiple times (re-indexing):
- Cache parsed markdown structure
- Only re-split if content hash changes

### Benchmarks (Estimated)

| Operation | Time (per doc) |
|-----------|----------------|
| Header detection | ~1ms |
| Section extraction | ~5ms |
| Hierarchy building | ~2ms |
| Token counting | ~10ms |
| **Total overhead** | ~18ms |

Within SC-004 target (<10% overhead on typical 200ms processing).

---

## 8. Edge Cases Documented

| Edge Case | Handling |
|-----------|----------|
| No headers in document | Fall back to SentenceSplitter |
| Single header only | Fall back (below min_headers threshold) |
| Header with no content | Skip empty section |
| Inconsistent levels (h1 → h4) | Build hierarchy with gaps |
| Code blocks with # | Regex anchors to line start, won't match |
| Very long header text | Truncate in metadata if >200 chars |

---

## Decisions Summary

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| Custom strategy vs MarkdownNodeParser | More control over chunk size and metadata | MarkdownNodeParser (no size limits) |
| Regex-based header detection | Simple, fast, accurate for standard markdown | AST parsing (overkill) |
| Minimum 2 headers threshold | Avoids false positives | 1 header (too sensitive) |
| SentenceSplitter fallback | Maintains chunk size guarantees | Strict header-only (loses content) |
| Metadata extension only | No schema migrations needed | New table (complexity) |

---

## References

- LlamaIndex MarkdownNodeParser: https://docs.llamaindex.ai/en/stable/api_reference/node_parsers/
- Markdown Spec (CommonMark): https://spec.commonmark.org/
- Empire chunking_service.py: `app/services/chunking_service.py`
- Empire source_processing.py: `app/tasks/source_processing.py`
