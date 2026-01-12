# Implementation Plan: Markdown-Aware Document Splitting

**Branch**: `006-markdown-chunking` | **Date**: 2026-01-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-markdown-chunking/spec.md`

## Summary

Add a `MarkdownChunkerStrategy` to Empire's RAG pipeline that splits documents by markdown headers instead of character counts. This preserves semantic context in chunks, improving retrieval quality. The strategy will use LlamaIndex's `MarkdownNodeParser` as the foundation, with fallback to `SentenceSplitter` for oversized sections.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, LlamaIndex (core), Pydantic v2, structlog
**Storage**: Supabase PostgreSQL (pgvector for embeddings), existing vector store
**Testing**: pytest with existing test infrastructure
**Target Platform**: Linux server (Render deployment)
**Project Type**: Web application (FastAPI backend)
**Performance Goals**: <10% overhead vs current SentenceSplitter (per SC-004)
**Constraints**: Handle documents up to 100,000 tokens (SC-005), maintain backward compatibility
**Scale/Scope**: Existing Empire v7.3 document processing pipeline

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Library-First | PASS | New strategy is self-contained, independently testable |
| Test-First | PASS | Unit tests will be written for markdown splitting |
| Integration Testing | PASS | Contract tests for chunking service interface |
| Simplicity | PASS | Extends existing ChunkingStrategy pattern, no new dependencies |

## Project Structure

### Documentation (this feature)

```text
specs/006-markdown-chunking/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 output (LlamaIndex patterns)
├── data-model.md        # Phase 1 output (MarkdownSection, metadata schema)
├── quickstart.md        # Phase 1 output (usage examples)
├── contracts/           # Phase 1 output (chunking interface)
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
app/
├── services/
│   ├── chunking_service.py      # MODIFY: Add MarkdownChunkerStrategy
│   └── document_processor.py    # MODIFY: Add markdown detection
├── tasks/
│   └── source_processing.py     # MODIFY: Wire up new chunker
└── models/
    └── sources.py               # OPTIONAL: Add chunking strategy enum

tests/
├── unit/
│   └── test_chunking_service.py # CREATE: Markdown splitting tests
└── integration/
    └── test_document_processing.py # UPDATE: Add markdown chunking tests
```

**Structure Decision**: Backend-only modification within existing FastAPI structure. No new packages or services required.

## Complexity Tracking

No violations to justify - feature follows existing patterns.

---

## Phase 0: Research

### Research Tasks Completed

Based on codebase exploration:

1. **Existing Chunking Infrastructure**
   - `app/services/chunking_service.py` (770 lines) has 4 strategies: SemanticChunker, CodeChunker, TranscriptChunker, Generic
   - Uses LlamaIndex `SentenceSplitter` with 1024 tokens, 200 overlap
   - `ChunkingStrategy` abstract base class exists

2. **LlamaIndex Markdown Support**
   - `MarkdownNodeParser` available in `llama_index.core.node_parser`
   - `MarkdownElementNodeParser` for complex docs with tables/code
   - Both produce `TextNode` objects compatible with existing pipeline

3. **LlamaParse Integration**
   - `app/tasks/source_processing.py` uses LlamaParse with `result_type="markdown"`
   - Markdown output is already being generated but not leveraged for splitting

### Decisions

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| Use `MarkdownNodeParser` | Native LlamaIndex support, produces TextNodes | Custom regex parsing (more maintenance) |
| Hybrid approach for large sections | Maintains chunk size limits while preserving headers | Strict header-only (loses long content) |
| Metadata extension only | No vector store schema changes needed | New table (unnecessary complexity) |
| Auto-detect markdown | Seamless integration with LlamaParse flow | Manual strategy selection (breaks UX) |

---

## Phase 1: Design & Contracts

### 1.1 Data Model

See [data-model.md](./data-model.md) for full entity definitions.

**Key Entities:**

```python
@dataclass
class MarkdownSection:
    header: str           # e.g., "## Methods"
    level: int            # 1-6
    content: str          # Section content including header
    start_line: int       # Line number in original document
    parent_headers: list  # ["# Chapter 1", "## Introduction"]

# Extended chunk metadata
ChunkMetadata = {
    "section_header": str,      # "## Methods"
    "header_level": int,        # 2
    "header_hierarchy": dict,   # {"h1": "Chapter 1", "h2": "Methods"}
    "is_header_split": bool,    # True if split by header, False if sentence fallback
    "chunk_index": int,         # Position in section (for large section splits)
}
```

### 1.2 API Contracts

See [contracts/](./contracts/) for interface definitions.

**MarkdownChunkerStrategy Interface:**

```python
class MarkdownChunkerStrategy(ChunkingStrategy):
    def __init__(
        self,
        max_chunk_size: int = 1024,
        chunk_overlap: int = 200,
        include_header_in_chunk: bool = True,
    ): ...

    def chunk(self, text: str, metadata: dict = None) -> list[TextNode]:
        """Split markdown text into nodes by headers."""
        ...

    def _detect_markdown(self, text: str) -> bool:
        """Returns True if text contains markdown headers."""
        ...

    def _split_by_headers(self, text: str) -> list[MarkdownSection]:
        """Extract sections with their headers."""
        ...

    def _get_header_hierarchy(self, sections: list, index: int) -> dict:
        """Build parent header chain for a section."""
        ...
```

### 1.3 Integration Points

1. **chunking_service.py**
   - Add `MarkdownChunkerStrategy` class
   - Register in strategy factory/selector

2. **document_processor.py**
   - Add `is_markdown_content(text: str) -> bool` function
   - Route markdown content to new strategy

3. **source_processing.py**
   - Update LlamaParse flow to use markdown chunking
   - Maintain fallback to existing strategies

---

## Implementation Phases

### Phase 1: Core Infrastructure (P1 - High Priority)

**Goal**: Implement MarkdownChunkerStrategy with full test coverage

**Files:**
- `app/services/chunking_service.py` - Add new strategy class
- `tests/unit/test_chunking_service.py` - Create comprehensive tests

**Tasks:**
1. Add `MarkdownSection` dataclass
2. Implement `MarkdownChunkerStrategy` class
3. Add header detection regex: `^(#{1,6})\s+(.+)$`
4. Implement `_split_by_headers()` method
5. Implement `_get_header_hierarchy()` method
6. Add fallback to `SentenceSplitter` for oversized sections
7. Write unit tests for all scenarios

### Phase 2: Document Processor Integration (P1 - High Priority)

**Goal**: Wire up markdown detection and routing

**Files:**
- `app/services/document_processor.py` - Add markdown detection
- `app/tasks/source_processing.py` - Route to new chunker

**Tasks:**
1. Add `is_markdown_content()` helper function
2. Update chunking strategy selection logic
3. Integrate with LlamaParse output flow
4. Add integration tests

### Phase 3: Metadata Enhancement (P2 - Medium Priority)

**Goal**: Enrich chunks with header hierarchy

**Tasks:**
1. Populate `header_hierarchy` metadata field
2. Add `is_header_split` flag
3. Add `chunk_index` for large section splits
4. Update logging for observability (FR-009)

### Phase 4: Configuration & Polish (P3 - Low Priority)

**Goal**: Optional configurability and documentation

**Tasks:**
1. Add `chunking_strategy` enum to sources model (optional)
2. Document new chunking behavior
3. Add API docs if strategy selection exposed

---

## Verification

### Test Strategy

1. **Unit Tests** (Phase 1)
   - Header detection regex accuracy
   - Section extraction with various header levels
   - Header hierarchy building
   - Large section fallback behavior
   - Edge cases (empty sections, malformed headers)

2. **Integration Tests** (Phase 2)
   - End-to-end document processing with markdown
   - LlamaParse output handling
   - Backward compatibility with non-markdown docs

3. **Acceptance Tests** (Per User Stories)
   - Query returns contextually complete answers
   - Documents without headers still process
   - Large sections properly subdivided
   - Header metadata enables filtered search

### Success Metrics Verification

| Metric | Target | How to Verify |
|--------|--------|---------------|
| SC-001 | 80% chunks start with header | Analyze chunk statistics from test corpus |
| SC-002 | 70% queries answered without extra context | Manual evaluation on test queries |
| SC-003 | 100% backward compatibility | Run existing test suite |
| SC-004 | <10% performance overhead | Benchmark before/after |
| SC-005 | Handle 100K tokens | Load test with large document |
| SC-006 | No test regressions | CI/CD pipeline passes |

---

## Artifacts Generated

- [x] plan.md (this file)
- [x] research.md (complete)
- [x] data-model.md (complete)
- [x] contracts/chunking_interface.py (complete)
- [x] quickstart.md (complete)
- [x] tasks.md (complete - 40 tasks)
