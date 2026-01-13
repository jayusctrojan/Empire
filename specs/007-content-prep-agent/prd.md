# PRD: Content Prep Agent (AGENT-016)

**Feature**: 007-content-prep-agent
**Date**: 2026-01-13
**Status**: Draft
**Priority**: P1 - High

---

## Executive Summary

Add a **Content Prep Agent** (AGENT-016) to Empire's document processing pipeline that validates, orders, and prepares content before ingestion into the knowledge base. This agent ensures that multi-file content (courses, documentation sets, book chapters) is processed in the correct logical/chronological order, maintaining semantic coherence in the knowledge graph.

---

## Problem Statement

### Current Gap

When users upload course materials or multi-file content sets to B2:
1. Files are processed in **arbitrary order** (typically alphabetical or upload timestamp)
2. No validation of **content completeness** (missing chapters, broken references)
3. No **chronological awareness** - Chapter 10 might be processed before Chapter 1
4. Knowledge base learns content **out of sequence**, leading to fragmented understanding

### Impact

- RAG retrieval returns chunks without proper prerequisite context
- Knowledge graph relationships may reference entities not yet ingested
- Course progression is lost - "build on previous concept" references break
- User queries about "next steps" or "prerequisites" return incorrect information

### Example Scenario

User uploads a 12-module Python course:
```
uploads/
├── module-01-introduction.pdf
├── module-02-variables.pdf
├── module-10-classes.pdf      # Processed BEFORE module-03!
├── module-03-functions.pdf
└── ...
```

Current system processes `module-10-classes.pdf` early (alphabetical), so the knowledge base learns about Python classes before understanding functions, variables, or basic syntax.

---

## Proposed Solution

### New Agent: Content Prep Agent (AGENT-016)

Insert a new CrewAI agent between B2 file retrieval and document processing:

```
B2 Pending/ → [AGENT-016: Content Prep] → Source Processing → Chunking → Embedding
                      ↓
              - Detect content sets
              - Validate completeness
              - Order chronologically
              - Generate processing manifest
```

### Key Responsibilities

1. **Content Set Detection**
   - Identify related files (courses, documentation, book series)
   - Group by naming patterns, metadata, or explicit manifest
   - Detect standalone vs. sequential content

2. **Completeness Validation**
   - Check for missing files in sequence (gap detection)
   - Validate cross-references between files
   - Report incomplete sets before processing

3. **Chronological Ordering**
   - Parse file names for sequence indicators (01, 02, chapter-1, etc.)
   - Use metadata (creation date, explicit order field)
   - LLM-assisted ordering for ambiguous cases

4. **Processing Manifest Generation**
   - Create ordered processing queue
   - Add dependency metadata (file X depends on file Y)
   - Include content set context for downstream agents

5. **Quality Pre-Check**
   - Verify file integrity (not corrupted)
   - Check encoding compatibility
   - Estimate processing complexity

---

## User Stories

### US-001: Course Upload Ordering
**As a** course creator uploading training materials,
**I want** the system to process my modules in the correct order,
**So that** the knowledge base understands prerequisite relationships.

**Acceptance Criteria:**
- System detects numbered modules (01, 02, 03...)
- Processes in ascending order regardless of upload sequence
- Knowledge graph reflects "builds on" relationships

### US-002: Completeness Warning
**As a** content administrator,
**I want** to be warned if my upload set is incomplete,
**So that** I can add missing files before processing.

**Acceptance Criteria:**
- System detects gaps in sequence (1, 2, 4 → missing 3)
- Warning surfaced before processing begins
- **Processing blocked until user explicitly acknowledges the warning**
- User can choose to: (a) add missing files, or (b) acknowledge and proceed anyway
- Acknowledgment logged for audit trail

### US-003: Documentation Set Grouping
**As a** developer uploading API documentation,
**I want** related documentation files to be grouped and processed together,
**So that** cross-references resolve correctly.

**Acceptance Criteria:**
- Files with shared prefix/naming convention are grouped
- Processing order respects logical dependencies
- Cross-file references validated before storage

### US-004: Standalone File Pass-Through
**As a** user uploading a single PDF,
**I want** the system to process it immediately without waiting,
**So that** simple uploads aren't delayed by ordering logic.

**Acceptance Criteria:**
- Single files bypass set detection
- Processing begins within normal latency
- No unnecessary overhead for simple uploads

### US-005: Chat-Based Ordering Clarification
**As a** user uploading files with ambiguous naming,
**I want** the Content Prep Agent to ask me ordering questions via CKO Chat,
**So that** I can confirm the correct sequence without leaving my workflow.

**Acceptance Criteria:**
- Agent detects when ordering confidence is below threshold (<80%)
- Agent sends clarification message to CKO Chat with specific question
- Message includes file names and proposed options (e.g., "Should X come before Y?")
- User responds in natural language via chat
- Agent parses response and updates ordering
- Processing resumes automatically after clarification
- Conversation logged for audit trail

---

## Technical Architecture

### Agent Position in Pipeline

```
                          ┌─────────────────────────────────┐
                          │      B2 Workflow Service        │
                          │  (pending/ → processing/)       │
                          └──────────────┬──────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    AGENT-016: Content Prep Agent                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐│
│  │ Set Detector    │→ │ Order Resolver  │→ │ Manifest Generator      ││
│  │ - Pattern match │  │ - Sequence parse│  │ - Ordered queue         ││
│  │ - Metadata scan │  │ - LLM fallback  │  │ - Dependencies          ││
│  │ - Grouping      │  │ - Gap detection │  │ - Context metadata      ││
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘│
└───────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────┐
                          │     Source Processing Task      │
                          │  (Celery: process_source)       │
                          └─────────────────────────────────┘
```

### CrewAI Agent Definition

**Agent ID**: AGENT-016
**Name**: Content Prep Agent
**Role**: Content Preparation Specialist
**Model**: claude-3-5-haiku-20241022 (fast, cost-effective for ordering)

**Goal**: Validate, order, and prepare content sets for optimal knowledge base ingestion

**Tools**:
- file_metadata_reader
- sequence_pattern_detector
- b2_file_lister
- manifest_generator

*See `architecture.md` for full implementation.*

### Data Model

**ContentSet** - A group of related files to be processed together:
- `id`: UUID identifier
- `name`: Detected or assigned name
- `detection_method`: "pattern", "metadata", "manual", or "llm"
- `files`: Ordered list of ContentFile objects
- `is_complete`: Whether all expected files are present
- `missing_files`: Gap detection results
- `processing_status`: "pending", "processing", "complete"

**ContentFile** - A single file within a content set:
- `b2_path`: Full B2 storage path
- `filename`: Original filename
- `sequence_number`: Detected sequence position (nullable)
- `dependencies`: Files this one depends on
- `estimated_complexity`: "low", "medium", "high"

**ProcessingManifest** - Generated processing order with context:
- `content_set_id`: Reference to parent set
- `ordered_files`: Files in processing order
- `estimated_processing_time`: Seconds
- `warnings`: Completeness warnings
- `context`: Shared context for downstream agents

*See `architecture.md` for full Pydantic model implementations.*

### Sequence Detection Patterns

The agent detects sequence ordering from common file naming conventions:

**Numeric Patterns** (e.g., `01-intro.pdf`, `module-05.pdf`, `chapter12.pdf`):
- Numeric prefixes: `01-`, `1_`, `001-`
- Named sequences: `module-1`, `chapter-2`, `lesson-3`, `part-4`, `week-5`, `unit-6`

**Alpha Patterns** (e.g., `a-intro.pdf`, `b-basics.pdf`)

**Roman Numerals** (e.g., `i-intro.pdf`, `ii-basics.pdf`, `iii-advanced.pdf`)

**Content Set Indicators** - Keywords that suggest files belong together:
- course, tutorial, training, documentation, manual, series, book, guide, curriculum

*See `architecture.md` for implementation details.*

---

## API Endpoints

### New Routes: `/api/content-prep`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/content-prep/analyze` | Analyze pending files, detect sets |
| POST | `/api/content-prep/validate/{set_id}` | Validate completeness of content set |
| GET | `/api/content-prep/sets` | List detected content sets |
| GET | `/api/content-prep/sets/{set_id}` | Get content set details |
| POST | `/api/content-prep/manifest` | Generate processing manifest |
| GET | `/api/content-prep/health` | Service health check |

### Request/Response Examples

**Analyze Pending Files:**
```json
POST /api/content-prep/analyze
{
    "b2_folder": "pending/courses/",
    "detection_mode": "auto"  // "auto", "pattern", "metadata", "llm"
}

Response:
{
    "content_sets": [
        {
            "id": "cs-uuid-1234",
            "name": "Python Fundamentals Course",
            "files_count": 12,
            "is_complete": false,
            "missing": ["module-07-exceptions.pdf"],
            "detection_method": "pattern",
            "confidence": 0.95
        }
    ],
    "standalone_files": [
        {"filename": "random-notes.pdf", "path": "pending/random-notes.pdf"}
    ]
}
```

**Generate Processing Manifest:**
```json
POST /api/content-prep/manifest
{
    "content_set_id": "cs-uuid-1234",
    "proceed_incomplete": true,  // Process despite gaps
    "add_context": true          // Include set context in processing
}

Response:
{
    "manifest_id": "manifest-uuid-5678",
    "content_set": "Python Fundamentals Course",
    "ordered_files": [
        {"sequence": 1, "file": "module-01-introduction.pdf", "dependencies": []},
        {"sequence": 2, "file": "module-02-variables.pdf", "dependencies": ["module-01"]},
        {"sequence": 3, "file": "module-03-functions.pdf", "dependencies": ["module-02"]}
    ],
    "warnings": ["Missing: module-07-exceptions.pdf"],
    "estimated_time_seconds": 480
}
```

---

## Integration Points

### 1. B2 Workflow Service
- Hook into `pending/` folder monitoring
- Trigger content prep analysis on new uploads
- Move processed files to `processing/` via manifest order

### 2. Source Processing Task (Celery)
- Accept manifest as processing input
- Process files in manifest order
- Pass content set context to chunking service

### 3. Chunking Service (Feature 006)
- Receive content set metadata
- Use set context for enhanced chunking decisions
- Preserve cross-file references

### 4. Knowledge Graph (Neo4j)
- Create `PART_OF` relationships for content sets
- Establish `PRECEDES`/`FOLLOWS` relationships between files
- Store sequence metadata on document nodes

---

## Database Schema Updates

### Supabase: `content_sets` Table

```sql
CREATE TABLE content_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    detection_method VARCHAR(50) NOT NULL,
    is_complete BOOLEAN DEFAULT FALSE,
    missing_files JSONB DEFAULT '[]',
    file_count INTEGER NOT NULL,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE content_set_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_set_id UUID REFERENCES content_sets(id) ON DELETE CASCADE,
    b2_path VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sequence_number INTEGER,
    dependencies JSONB DEFAULT '[]',
    estimated_complexity VARCHAR(20),
    file_type VARCHAR(50),
    size_bytes BIGINT,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_content_sets_status ON content_sets(processing_status);
CREATE INDEX idx_content_set_files_set ON content_set_files(content_set_id);
CREATE INDEX idx_content_set_files_sequence ON content_set_files(content_set_id, sequence_number);

-- Retention policy: Delete content set metadata 90 days after processing complete
-- Implemented via scheduled Celery task or pg_cron
CREATE INDEX idx_content_sets_updated ON content_sets(updated_at);
```

**Retention Policy**: Content set metadata is automatically deleted 90 days after `processing_status` changes to `complete`. A scheduled cleanup task runs daily to enforce this policy.

### Neo4j: Graph Schema

```cypher
// Content Set node
CREATE CONSTRAINT content_set_id IF NOT EXISTS
FOR (cs:ContentSet) REQUIRE cs.id IS UNIQUE;

// Relationships
// (Document)-[:PART_OF]->(ContentSet)
// (Document)-[:PRECEDES]->(Document)
// (Document)-[:FOLLOWS]->(Document)
// (Document)-[:DEPENDS_ON]->(Document)
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| SC-001 | 95% of numbered files correctly sequenced | Automated test suite |
| SC-002 | Gap detection accuracy >99% | Manual validation |
| SC-003 | <5 second analysis time for <50 files | Performance benchmark |
| SC-004 | Single file pass-through <100ms overhead | Latency monitoring |
| SC-005 | LLM ordering agreement >90% with manual | Human evaluation |
| SC-006 | Zero regression in existing processing | CI/CD test suite |
| SC-007 | Support up to 100 files per content set | Load testing |
| SC-008 | Batched analysis (>100 files) maintains chronological order | Integration test |

---

## Implementation Phases

### Phase 1: Core Infrastructure (P1)
- Create AGENT-016 service file
- Implement sequence pattern detection
- Build content set grouping logic
- Add API routes

### Phase 2: B2 Integration (P1)
- Hook into B2 workflow service
- Implement manifest-based processing
- Add Celery task integration

### Phase 3: Knowledge Graph (P2)
- Add Neo4j relationships for content sets
- Store sequence metadata
- Enable cross-file reference queries

### Phase 4: Advanced Detection (P3)
- LLM-assisted ordering for ambiguous cases
- Metadata-based detection (PDF properties)
- User-defined manifest upload

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `app/services/content_prep_agent.py` | CREATE | AGENT-016 implementation |
| `app/routes/content_prep.py` | CREATE | API routes |
| `app/tasks/content_prep_tasks.py` | CREATE | Celery tasks |
| `app/models/content_sets.py` | CREATE | Pydantic models |
| `app/services/b2_workflow.py` | MODIFY | Hook content prep |
| `app/tasks/source_processing.py` | MODIFY | Accept manifests |
| `tests/test_content_prep_agent.py` | CREATE | Unit tests |
| `migrations/create_content_sets.sql` | CREATE | Database schema |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pattern detection false positives | Medium | Confidence threshold, manual override |
| LLM ordering costs | Low | Use Haiku, cache results |
| Large file sets timeout | Medium | Async processing, chunked analysis |
| User uploads without naming convention | Medium | LLM fallback, manual ordering UI |

---

## Dependencies

- **Existing**: CrewAI service, B2 workflow, Celery, Supabase, Neo4j
- **New packages**: None required (uses existing infrastructure)

---

## Clarifications

### Session 2026-01-13
- Q: Should incomplete sets block processing entirely or proceed with warning? → A: Warn then require explicit user acknowledgment before proceeding
- Q: Maximum content set size before requiring batched analysis? → A: 100 files max; larger sets auto-batch in chunks of 50 with chronological ordering preserved across all batches
- Q: User UI for manual ordering override? → A: Chat-based clarification via Chief Knowledge Officer (CKO) Chat interface; agent asks ordering questions when ambiguous, user responds in chat to confirm
- Q: Retention policy for content set metadata? → A: 90 days after last file processed, then deleted

---

## Open Questions

1. ~~Should incomplete sets block processing entirely or proceed with warning?~~ **RESOLVED**: Require explicit acknowledgment
2. ~~Maximum content set size before requiring batched analysis?~~ **RESOLVED**: 100 files, auto-batch with chronological merge
3. ~~User UI for manual ordering override?~~ **RESOLVED**: Chat-based clarification via CKO Chat
4. ~~Retention policy for content set metadata?~~ **RESOLVED**: 90 days after processing

**All open questions resolved.**

---

## Appendix: Agent Registry Update

```python
# Add to app/services/crewai_service.py AGENT_REGISTRY

"AGENT-016": {
    "id": "AGENT-016",
    "name": "Content Prep Agent",
    "category": "orchestration",
    "purpose": "Content set detection, ordering, and preparation",
    "model": "claude-3-5-haiku-20241022",
    "task": "Task 47"
}
```
