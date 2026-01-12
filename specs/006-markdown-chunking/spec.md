# Feature Specification: Markdown-Aware Document Splitting

**Feature Branch**: `006-markdown-chunking`
**Created**: 2026-01-11
**Status**: Draft
**Input**: User description: "Markdown-Aware Document Splitting for Empire RAG Pipeline - Add MarkdownChunkerStrategy to split documents by headers instead of character counts, improving RAG retrieval context"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query Returns Contextually Complete Answers (Priority: P1)

As a user querying the RAG system, I want retrieved document chunks to contain complete sections with their headers, so that my questions are answered with full context rather than mid-paragraph fragments.

**Why this priority**: This is the core value proposition. Without header-aware splitting, users receive fragmented responses that lack context, reducing the usefulness of the entire RAG system.

**Independent Test**: Can be fully tested by uploading a structured PDF document (e.g., a policy document with clear headers), querying for information within a specific section, and verifying the retrieved chunk starts with the relevant header.

**Acceptance Scenarios**:

1. **Given** a document with markdown headers has been processed, **When** a user queries about a topic covered under "## Section Title", **Then** the retrieved chunk contains the full "## Section Title" header and its content.
2. **Given** a document has nested headers (h1 > h2 > h3), **When** a chunk is retrieved, **Then** the chunk metadata includes the full header hierarchy (e.g., "Chapter 1 > Introduction > Overview").
3. **Given** a query matches content in multiple sections, **When** results are returned, **Then** each chunk is self-contained with its own header context.

---

### User Story 2 - Documents Without Headers Are Still Processed (Priority: P2)

As a system administrator, I want documents without markdown headers to still be processed correctly, so that the system handles all document types gracefully without errors.

**Why this priority**: Ensures backward compatibility and prevents system failures when processing legacy or unstructured documents.

**Independent Test**: Can be fully tested by uploading a plain text document with no headers and verifying it is chunked using the existing sentence-based approach without errors.

**Acceptance Scenarios**:

1. **Given** a document contains no markdown headers (plain text), **When** the document is processed, **Then** the system falls back to sentence-based chunking and completes successfully.
2. **Given** a document has only malformed headers (e.g., "#Invalid" without space), **When** processed, **Then** the system treats these as regular text and uses fallback chunking.

---

### User Story 3 - Large Sections Are Properly Subdivided (Priority: P2)

As a user, I want very long document sections (exceeding the chunk size limit) to be subdivided while preserving the header context, so that I can still retrieve relevant portions of lengthy sections.

**Why this priority**: Prevents memory issues and ensures all content is searchable, even in documents with unusually long sections.

**Independent Test**: Can be tested by uploading a document with a single section containing 5000+ tokens and verifying it produces multiple chunks, each retaining the section header in metadata.

**Acceptance Scenarios**:

1. **Given** a markdown section exceeds 1024 tokens, **When** the section is processed, **Then** it is subdivided into smaller chunks using sentence-aware splitting.
2. **Given** a large section is subdivided, **When** the resulting chunks are examined, **Then** each sub-chunk includes metadata referencing the original section header.
3. **Given** a section is subdivided, **When** chunks are stored, **Then** they maintain sequential ordering for potential reconstruction.

---

### User Story 4 - Header Metadata Enables Filtered Search (Priority: P3)

As an advanced user, I want to filter my queries by section type (e.g., "only search in Methods sections"), so that I can narrow down results to specific document areas.

**Why this priority**: Adds value for power users but is not essential for basic functionality.

**Independent Test**: Can be tested by querying with a section filter and verifying only chunks from matching sections are returned.

**Acceptance Scenarios**:

1. **Given** chunks have header metadata stored, **When** a query includes a section filter, **Then** only chunks matching that header level or name are searched.
2. **Given** a user filters by "h2" sections only, **When** results are returned, **Then** all results have header_level = 2 in their metadata.

---

### Edge Cases

- What happens when a document has inconsistent header levels (e.g., jumps from h1 to h4)?
  - System processes available headers and builds hierarchy based on actual structure
- What happens when a header has no content before the next header?
  - Empty sections are skipped or merged with the next section
- How does the system handle special markdown elements within sections (code blocks, tables)?
  - These are included as part of the section content and preserved in the chunk
- What happens when markdown comes from LlamaParse with formatting inconsistencies?
  - System applies basic markdown normalization before parsing headers

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST split documents containing markdown headers by those headers (h1-h6) as the primary splitting method
- **FR-002**: System MUST preserve the header text within each resulting chunk
- **FR-003**: System MUST store header hierarchy metadata (parent headers) with each chunk
- **FR-004**: System MUST fall back to sentence-based chunking when a document contains no recognizable markdown headers
- **FR-005**: System MUST subdivide sections exceeding 1024 tokens using sentence-aware splitting while retaining header metadata
- **FR-006**: System MUST maintain backward compatibility with existing chunking strategies (semantic, code, transcript)
- **FR-007**: System MUST automatically detect markdown content from LlamaParse output and apply markdown chunking
- **FR-008**: System MUST include chunk overlap (200 tokens) when subdividing large sections
- **FR-009**: System MUST log chunking strategy used and chunk statistics for observability

### Key Entities

- **MarkdownSection**: Represents a document section defined by a header; includes header text, level (1-6), content, and parent header chain
- **Chunk**: Extended to include header_level, section_header, header_hierarchy, and is_header_split metadata fields
- **ChunkingStrategy**: Abstract interface that MarkdownChunkerStrategy implements alongside existing strategies

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 80% or more of chunks from markdown documents start with a header or contain complete section content
- **SC-002**: Retrieved chunks answer user queries without requiring additional context 70% of the time (vs. current baseline measurement)
- **SC-003**: Documents without headers are processed successfully with zero errors (100% backward compatibility)
- **SC-004**: Processing time per document increases by no more than 10% compared to current sentence-based chunking
- **SC-005**: System handles documents up to 100,000 tokens without memory issues or timeouts
- **SC-006**: All existing tests continue to pass after feature implementation (no regressions)

## Assumptions

- LlamaParse is already configured to output markdown format (`result_type="markdown"`)
- Standard markdown header syntax is used (# for h1, ## for h2, etc.)
- Chunk size limit of 1024 tokens and overlap of 200 tokens are acceptable defaults
- The existing `ChunkingStrategy` interface pattern will be extended for the new strategy
- Header detection uses the regex pattern `^(#{1,6})\s+(.+)$`

## Scope Boundaries

**In Scope**:
- Adding MarkdownChunkerStrategy to the chunking service
- Automatic markdown detection for LlamaParse output
- Header hierarchy preservation in chunk metadata
- Fallback to sentence splitting for large sections

**Out of Scope**:
- User-configurable chunking strategy selection via API (deferred to future enhancement)
- Custom header patterns beyond standard markdown
- Retroactive re-chunking of existing documents
- Changes to the vector store schema (metadata extension only)
