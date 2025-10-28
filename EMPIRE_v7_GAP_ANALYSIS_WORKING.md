# Empire v7.0 Gap Analysis - WORKING DOCUMENT
**Created:** October 28, 2025
**Purpose:** Track implementation of gaps identified in Total RAG comparison
**Status:** 🔴 IN PROGRESS - 34 gaps to address

---

## Quick Reference - Implementation Status

### Summary
- 🔴 **Critical Gaps:** 14 (0 completed)
- 🟡 **High-Priority Gaps:** 8 (0 completed)
- 🟢 **Medium-Priority Gaps:** 12 (0 completed)
- **Total Progress:** 0/34 (0%)

### Legend
- ❌ Not Started
- 🚧 In Progress
- ✅ Completed
- 📝 SRS Updated
- 🧪 Testing Required

---

## PART 1: CRITICAL GAPS - Immediate Action Required (Weeks 1-2)

### 🔴 Gap 1.1: Context Expansion Database Function
**Status:** ❌ Not Started
**SRS Section to Update:** 10.3.5 (Context Expansion)
**Implementation Files:**
- [ ] Create SQL function in Supabase
- [ ] Add to Section 10.3.5 in 10_n8n_orchestration.md
- [ ] Create edge function wrapper
- [ ] Test with sample data

**SQL Implementation Required:**
```sql
-- Add to Section 10.3.5
CREATE OR REPLACE FUNCTION get_chunks_by_ranges(input_data jsonb)
RETURNS TABLE(
  doc_id text,
  chunk_index integer,
  content text,
  metadata jsonb,
  id bigint,
  hierarchical_context jsonb -- Empire enhancement
)
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
-- Implementation needed
$$;
```

---

### 🔴 Gap 1.2: Supabase Edge Function for Hybrid Search
**Status:** ❌ Not Started
**SRS Section to Update:** 10.3.3 (Hybrid Search Edge Functions)
**Implementation Files:**
- [ ] Create edge function in Supabase
- [ ] Add to Section 10.3.3
- [ ] Update empire-arch.txt with edge function details
- [ ] Test HTTP endpoint

**Edge Function Required:**
```typescript
// supabase/functions/dynamic-hybrid-search/index.ts
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

Deno.serve(async (req) => {
  // Implementation needed
})
```

---

### 🔴 Gap 1.3: Tabular Data Storage Implementation
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.4 (NEW - Tabular Data Processing)
**Implementation Files:**
- [ ] Add table to database schema
- [ ] Create new Section 10.2.4
- [ ] Update Section 3.1.6 requirements
- [ ] Add n8n workflow nodes

**SQL Schema Required:**
```sql
CREATE TABLE IF NOT EXISTS public.tabular_document_rows (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  record_manager_id BIGINT REFERENCES documents(id),
  row_data JSONB NOT NULL,
  schema_metadata JSONB, -- Empire enhancement
  inferred_relationships JSONB -- Empire enhancement
);
```

---

### 🔴 Gap 1.4: n8n Chat History Table
**Status:** ❌ Not Started
**SRS Section to Update:** 10.6.4 (Chat History Storage)
**Implementation Files:**
- [ ] Add table to database schema
- [ ] Update Section 10.6.4
- [ ] Add to empire-arch.txt
- [ ] Create n8n nodes for chat storage

**SQL Schema Required:**
```sql
CREATE TABLE IF NOT EXISTS public.n8n_chat_histories (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL,
  user_id VARCHAR(255), -- Empire enhancement
  message JSONB NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_history_session ON n8n_chat_histories(session_id);
CREATE INDEX idx_chat_history_user ON n8n_chat_histories(user_id);
```

---

### 🔴 Gap 1.5: Metadata Fields Management Table
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.5 (NEW - Metadata Management)
**Implementation Files:**
- [ ] Add table to database schema
- [ ] Create Section 10.2.5
- [ ] Update filter extraction workflow
- [ ] Add sample metadata configuration

**SQL Schema Required:**
```sql
CREATE TABLE IF NOT EXISTS public.metadata_fields (
  id BIGSERIAL PRIMARY KEY,
  field_name TEXT NOT NULL UNIQUE,
  field_type VARCHAR(50) NOT NULL, -- 'string', 'number', 'date', 'enum'
  allowed_values TEXT[], -- For enum types
  validation_regex TEXT,
  description TEXT,
  is_required BOOLEAN DEFAULT FALSE,
  display_order INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 🔴 Gap 1.6: LlamaIndex + LangExtract Implementation
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.6 (NEW - Precision Extraction)
**Implementation Files:**
- [ ] Create Section 10.2.6 with implementation details
- [ ] Add n8n workflow nodes
- [ ] Define extraction schemas
- [ ] Set up cross-validation logic

**Note:** This is an Empire ADVANTAGE - implement to exceed Total RAG

---

### 🔴 Gap 1.7: Multimodal Sub-Workflow Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.7 (NEW - Sub-Workflows)
**Implementation Files:**
- [ ] Create Section 10.7.1 - Multimodal Processing
- [ ] Design n8n sub-workflow JSON
- [ ] Add Claude Vision integration nodes
- [ ] Add Soniox transcription nodes

---

### 🔴 Gap 1.8: Knowledge Graph Sub-Workflow Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.7.2 (NEW - KG Sub-Workflow)
**Implementation Files:**
- [ ] Create Section 10.7.2
- [ ] Design n8n sub-workflow JSON
- [ ] Add retry logic for LightRAG
- [ ] Add status polling pattern

---

### 🔴 Gap 1.9: Memory Management Workflow
**Status:** ❌ Not Started
**SRS Section to Update:** 10.6.6 (NEW - Memory Maintenance)
**Implementation Files:**
- [ ] Create Section 10.6.6
- [ ] Design scheduled workflow
- [ ] Add memory pruning logic
- [ ] Add export/backup to B2

---

### 🔴 Gap 1.10: Hash-Based Deduplication
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.2 (Document Ingestion)
**Implementation Files:**
- [ ] Update Section 10.2.2 with hash generation
- [ ] Add n8n crypto node configuration
- [ ] Add hash checking before processing
- [ ] Update database schema with hash field

**n8n Node Configuration:**
```json
{
  "name": "Generate Content Hash",
  "type": "n8n-nodes-base.crypto",
  "parameters": {
    "type": "SHA256",
    "value": "={{ $json.content }}",
    "dataPropertyName": "content_hash"
  }
}
```

---

### 🔴 Gap 1.11: Record Manager Status Field Usage
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.2 (Status Tracking)
**Implementation Files:**
- [ ] Update workflow to use status field
- [ ] Add status transitions documentation
- [ ] Create status monitoring dashboard

---

### 🔴 Gap 1.12: File Update Trigger Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.1 (Document Triggers)
**Implementation Files:**
- [ ] Add B2 update monitoring
- [ ] Create update detection workflow
- [ ] Add version tracking

---

### 🔴 Gap 1.13: Delete Document Workflow
**Status:** ❌ Not Started
**SRS Section to Update:** 10.8 (NEW - Document Lifecycle)
**Implementation Files:**
- [ ] Create Section 10.8
- [ ] Design deletion workflow
- [ ] Add cascade deletion logic
- [ ] Add audit trail updates

---

### 🔴 Gap 1.14: Batch Processing Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.3 (Batch Processing)
**Implementation Files:**
- [ ] Update all workflows with splitInBatches
- [ ] Add batch size configuration
- [ ] Add progress tracking

**n8n Node Configuration:**
```json
{
  "name": "Process in Batches",
  "type": "n8n-nodes-base.splitInBatches",
  "parameters": {
    "batchSize": 10,
    "options": {"reset": false}
  }
}
```

---

## PART 2: HIGH-PRIORITY GAPS (Weeks 2-4)

### 🟡 Gap 2.1: Advanced Metadata Filtering
**Status:** ❌ Not Started
**SRS Section to Update:** 10.3.6 (NEW - Filter Extraction)
**Implementation Files:**
- [ ] Create Section 10.3.6
- [ ] Add LLM-powered filter extraction
- [ ] Create UI generation logic

---

### 🟡 Gap 2.2: Wait/Polling Pattern for Async
**Status:** ❌ Not Started
**SRS Section to Update:** 10.9 (NEW - Async Patterns)
**Implementation Files:**
- [ ] Create Section 10.9
- [ ] Document wait node usage
- [ ] Add polling patterns

---

### 🟡 Gap 2.3: Structured Output Parser
**Status:** ❌ Not Started
**SRS Section to Update:** 10.3.7 (NEW - Output Parsing)
**Implementation Files:**
- [ ] Create Section 10.3.7
- [ ] Add structured output schemas
- [ ] Configure parser nodes

---

### 🟡 Gap 2.4: Aggregate Node Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.3 (Batch Processing)
**Implementation Files:**
- [ ] Add aggregate patterns to workflows
- [ ] Document result collection

---

### 🟡 Gap 2.5: Retry Configuration
**Status:** ❌ Not Started
**SRS Section to Update:** 10.10 (NEW - Error Handling)
**Implementation Files:**
- [ ] Create Section 10.10
- [ ] Add retry configuration to all API nodes
- [ ] Document exponential backoff

---

### 🟡 Gap 2.6: AlwaysOutputData Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.10.1 (Empty Result Handling)
**Implementation Files:**
- [ ] Add to Section 10.10
- [ ] Configure nodes for empty results

---

### 🟡 Gap 2.7: Execute Workflow Trigger
**Status:** ❌ Not Started
**SRS Section to Update:** 10.7 (Sub-Workflows)
**Implementation Files:**
- [ ] Document workflow execution patterns
- [ ] Add trigger configurations

---

### 🟡 Gap 2.8: Switch Node Routing
**Status:** ❌ Not Started
**SRS Section to Update:** 10.3.2 (Query Routing)
**Implementation Files:**
- [ ] Add switch node patterns
- [ ] Document routing logic

---

## PART 3: MEDIUM-PRIORITY GAPS (Weeks 4-9)

### 🟢 Gap 3.1: Google Drive Integration (Optional)
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.7 (NEW - Alternative Sources)
**Note:** May not be needed with B2

---

### 🟢 Gap 3.2: Extract From File Node
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.2 (File Extraction)

---

### 🟢 Gap 3.3: Pipeline Status Endpoint
**Status:** ❌ Not Started
**SRS Section to Update:** 10.4 (LightRAG Integration)

---

### 🟢 Gap 3.4: Mistral OCR Upload Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.6 (OCR Processing)

---

### 🟢 Gap 3.5: Chat Memory Manager Node
**Status:** ❌ Not Started
**SRS Section to Update:** 10.6.4 (Memory Management)

---

### 🟢 Gap 3.6: Webhook Response Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.11 (NEW - API Responses)

---

### 🟢 Gap 3.7: Cohere Reranking Node
**Status:** ❌ Not Started
**SRS Section to Update:** 10.3.4 (Reranking)

---

### 🟢 Gap 3.8: Document ID Generation
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.2 (ID Management)

---

### 🟢 Gap 3.9: Execute Command Node
**Status:** ❌ Not Started
**SRS Section to Update:** 10.12 (NEW - System Commands)

---

### 🟢 Gap 3.10: Loop Node Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.2.3 (Iteration Patterns)

---

### 🟢 Gap 3.11: Set Node Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.13 (NEW - Data Transformation)

---

### 🟢 Gap 3.12: Merge Node Pattern
**Status:** ❌ Not Started
**SRS Section to Update:** 10.13.1 (Data Merging)

---

## PART 4: SRS SECTIONS REQUIRING UPDATES

### Priority 1 - Create New Sections (Critical)
1. **Section 10.2.4** - Tabular Data Processing
2. **Section 10.2.5** - Metadata Management
3. **Section 10.2.6** - Precision Extraction (LlamaIndex/LangExtract)
4. **Section 10.7** - Sub-Workflows (with 10.7.1 and 10.7.2)
5. **Section 10.8** - Document Lifecycle Management
6. **Section 10.9** - Async Patterns
7. **Section 10.10** - Error Handling & Retry Logic

### Priority 2 - Update Existing Sections (Critical)
1. **Section 10.2.2** - Add hash deduplication
2. **Section 10.3.5** - Add context expansion function
3. **Section 10.3.3** - Add edge function details
4. **Section 10.6.4** - Add chat history table
5. **Section 10.6.6** - Add memory maintenance workflow

### Priority 3 - Minor Updates (High/Medium)
1. **Section 10.2.1** - Add update triggers
2. **Section 10.2.3** - Add batch processing patterns
3. **Section 10.3.4** - Enhance reranking details
4. **Section 10.4** - Add KG status checking

---

## PART 5: IMPLEMENTATION TIMELINE

### Week 1 (Critical Infrastructure)
- [ ] Gap 1.1: Context Expansion Function
- [ ] Gap 1.2: Edge Function for Hybrid Search
- [ ] Gap 1.3: Tabular Data Table
- [ ] Gap 1.4: Chat History Table
- [ ] Gap 1.10: Hash Deduplication

### Week 2 (Critical Workflows)
- [ ] Gap 1.5: Metadata Fields Table
- [ ] Gap 1.7: Multimodal Sub-Workflow
- [ ] Gap 1.8: Knowledge Graph Sub-Workflow
- [ ] Gap 1.14: Batch Processing
- [ ] Gap 1.11: Status Tracking

### Week 3-4 (High Priority)
- [ ] Gap 2.1-2.8: All high-priority items
- [ ] Gap 1.6: LlamaIndex/LangExtract (Empire advantage)
- [ ] Gap 1.9: Memory Management
- [ ] Gap 1.12-1.13: Update/Delete workflows

### Week 5-9 (Medium Priority & Polish)
- [ ] Gap 3.1-3.12: All medium-priority items
- [ ] Testing and optimization
- [ ] Documentation updates
- [ ] Performance tuning

---

## PART 6: QUICK WINS (Can Do Today)

These can be implemented immediately with minimal effort:

1. **Hash Field Addition** (30 minutes)
```sql
ALTER TABLE documents ADD COLUMN content_hash TEXT;
CREATE INDEX idx_document_hash ON documents(content_hash);
```

2. **Chat History Table** (30 minutes)
```sql
-- Run the SQL from Gap 1.4 above
```

3. **Metadata Fields Table** (30 minutes)
```sql
-- Run the SQL from Gap 1.5 above
```

4. **Status Field Usage** (1 hour)
- Update existing workflows to set status='processing' and 'complete'

5. **Basic Retry Configuration** (1 hour)
- Add `"retryOnFail": true` to all HTTP request nodes

---

## PART 7: TESTING CHECKLIST

### After Each Implementation:
- [ ] SQL function executes without errors
- [ ] n8n workflow runs successfully
- [ ] Edge functions return expected data
- [ ] Performance meets requirements (<300ms)
- [ ] Error handling works correctly
- [ ] Documentation updated in SRS

---

## PART 8: NOTES & DECISIONS

### Architecture Decisions:
- Keep mem-agent MCP for developer memory (not production)
- Use graph-based user memory for production users
- Maintain 768-dim embeddings (more efficient than 1536)
- Keep Claude Sonnet 3.5 as primary LLM

### Implementation Notes:
- [Add notes here as implementation progresses]

### Blockers:
- [Track any blockers encountered]

### Questions for Team:
- [Add questions that need team input]

---

## APPENDIX: Quick SQL Scripts

### A. Create All Missing Tables at Once
```sql
-- Run this to create all missing tables
BEGIN;

-- Chat History
CREATE TABLE IF NOT EXISTS public.n8n_chat_histories (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL,
  user_id VARCHAR(255),
  message JSONB NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabular Data
CREATE TABLE IF NOT EXISTS public.tabular_document_rows (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  record_manager_id BIGINT REFERENCES documents(id),
  row_data JSONB NOT NULL,
  schema_metadata JSONB,
  inferred_relationships JSONB
);

-- Metadata Fields
CREATE TABLE IF NOT EXISTS public.metadata_fields (
  id BIGSERIAL PRIMARY KEY,
  field_name TEXT NOT NULL UNIQUE,
  field_type VARCHAR(50) NOT NULL,
  allowed_values TEXT[],
  validation_regex TEXT,
  description TEXT,
  is_required BOOLEAN DEFAULT FALSE,
  display_order INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add hash to documents if not exists
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON n8n_chat_histories(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user ON n8n_chat_histories(user_id);
CREATE INDEX IF NOT EXISTS idx_document_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_tabular_rows_data ON tabular_document_rows USING gin(row_data);

COMMIT;
```

---

**END OF WORKING DOCUMENT**

Last Updated: October 28, 2025
Next Review: [After Week 1 Implementation]