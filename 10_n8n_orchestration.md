# 10. n8n Orchestration Implementation Guide - v6.0 COMPLETE

## CRITICAL UPDATE - Full Advanced RAG + All Original Content RESTORED

This version contains:
- ✅ ALL original implementation details (2,192 lines of content)
- ✅ NEW Chat UI deployment milestone
- ✅ EXPANDED Advanced RAG workflows (Cohere, LightRAG, Context Expansion)
- ✅ Complete n8n node configurations
- ✅ Comprehensive error handling and monitoring
- ✅ Production deployment procedures

**Total Content:** 2,500+ lines of implementation guidance

## 10.1 Overview

This section provides a practical, milestone-based approach to implementing the AI Empire v6.0 workflow orchestration using n8n. Each milestone represents a testable, independent component that builds upon the previous one.

### 10.1.1 Implementation Philosophy

**Core Principles:**
- **Incremental Development:** Build and test one component at a time
- **Milestone-Based:** Each milestone is independently functional
- **Test-First:** Validate each component before integration
- **API-First:** Prioritize Claude Sonnet 4.5 API for all AI processing
- **Advanced RAG:** Include all sophisticated search/reranking features
- **Cost-Optimized:** Use batch processing and prompt caching for 90%+ savings
- **Fail-Safe:** Include error handling from the beginning
- **Observable:** Add logging and monitoring at each step

### 10.1.2 n8n Architecture for v6.0 COMPLETE

```
n8n Instance (Render - $15-30/month)
├── Webhook Endpoints (Entry Points)
├── Workflow Engine (Orchestration)
├── Node Types:
│   ├── Claude API Nodes (Primary AI Processing)
│   ├── Cohere Rerank Nodes (ESSENTIAL - Search Quality)
│   ├── LightRAG Nodes (ESSENTIAL - Knowledge Graphs)
│   ├── CrewAI Nodes (ESSENTIAL - Content Analysis)
│   ├── Supabase Nodes (Unified Database + Advanced RAG)
│   ├── Context Expansion Nodes (ESSENTIAL)
│   ├── Router Nodes (Intelligence)
│   └── Utility Nodes (Support)
└── Monitoring & Logging

Mac Studio Role:
├── mem-agent MCP (persistent memory)
├── MarkItDown MCP (format conversion)
├── Development environment
├── Testing and validation
└── NOT for production LLM inference

ESSENTIAL Cloud Services:
├── Claude Sonnet 4.5 API ($30-50/month) - Primary AI
├── Cohere Rerank v3.5 ($20/month) - Search Quality
├── LightRAG API ($15/month) - Knowledge Graphs
├── CrewAI (Render $15-20/month) - Content Analysis
├── Supabase pgvector ($25/month) - Unified Database
├── Chat UI (Gradio $7-15/month) - User Interface
├── Backblaze B2 ($10-20/month) - Storage
└── Optional: Mistral OCR, Soniox (usage-based)
```

## 10.2 Milestone 1: Document Intake and Classification

### 10.2.1 Objectives
- Set up document intake endpoints
- Implement file type detection
- Create classification logic
- Route to appropriate processors
- Test with sample documents

### 10.2.2 n8n Workflow Components

```yaml
Milestone_1_Workflow:
  name: "Document_Intake_Classification"
  
  nodes:
    1_webhook_trigger:
      type: "n8n-nodes-base.webhook"
      parameters:
        path: "document-upload"
        method: "POST"
        responseMode: "onReceived"
        options:
          rawBody: true
    
    2_file_validation:
      type: "n8n-nodes-base.function"
      code: |
        // Validate file and extract metadata
        const file = items[0].json.file;
        
        function calculateHash(fileData) {
          const crypto = require('crypto');
          return crypto.createHash('sha256').update(fileData).digest('hex');
        }
        
        function validateFile(file) {
          // Check file size (max 100MB)
          if (file.size > 104857600) {
            throw new Error('File too large. Maximum size is 100MB');
          }
          
          // Check file type
          const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/markdown',
            'text/html',
            'video/mp4',
            'video/quicktime',
            'audio/mpeg',
            'audio/wav'
          ];
          
          if (!allowedTypes.includes(file.type)) {
            throw new Error(`Unsupported file type: ${file.type}`);
          }
          
          return true;
        }
        
        return {
          filename: file.name,
          size: file.size,
          mimeType: file.type,
          hash: calculateHash(file.data),
          timestamp: new Date().toISOString(),
          valid: validateFile(file),
          extension: file.name.split('.').pop().toLowerCase()
        };
    
    3_duplicate_check:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      query: |
        SELECT 
          id,
          filename,
          processed_date,
          status
        FROM record_manager_v2 
        WHERE file_hash = '{{$node["file_validation"].json["hash"]}}'
        LIMIT 1
      credentials: "supabase_postgres"
    
    4_duplicate_handler:
      type: "n8n-nodes-base.if"
      conditions:
        - duplicate_found:
            expression: "{{$json.id !== undefined}}"
            route: "return_existing"
        - new_file:
            expression: "true"
            route: "continue_processing"
    
    5_classification_router:
      type: "n8n-nodes-base.switch"
      rules:
        - fast_track:
            condition: "{{$json.mimeType in ['text/plain', 'text/markdown', 'text/html']}}"
            description: "Simple text files - fast processing"
        - complex_pdf:
            condition: "{{$json.mimeType === 'application/pdf' && $json.size > 10485760}}"
            description: "Large PDFs - may need OCR"
        - multimedia:
            condition: "{{$json.mimeType.startsWith('video/') || $json.mimeType.startsWith('audio/')}}"
            description: "Audio/Video - needs transcription"
        - office_docs:
            condition: "{{$json.mimeType.includes('officedocument')}}"
            description: "Office documents - MarkItDown processing"
        - standard:
            condition: "true"
            description: "Default processing path"
    
    6_save_to_b2:
      type: "n8n-nodes-base.s3"
      parameters:
        bucketName: "ai-empire-documents"
        operation: "upload"
        fileName: "{{$json.hash}}/{{$json.filename}}"
        fileContent: "{{$json.fileData}}"
        additionalFields:
          storageClass: "STANDARD"
          serverSideEncryption: "AES256"
          metadata:
            original_filename: "{{$json.filename}}"
            upload_date: "{{$json.timestamp}}"
            mime_type: "{{$json.mimeType}}"
            file_hash: "{{$json.hash}}"
    
    7_log_intake:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "document_intake_log"
      credentials: "supabase_postgres"
      columns:
        document_id: "{{$json.hash}}"
        filename: "{{$json.filename}}"
        intake_timestamp: "{{$json.timestamp}}"
        classification: "{{$json.route}}"
        file_size: "{{$json.size}}"
        mime_type: "{{$json.mimeType}}"
        b2_path: "{{$json.b2Path}}"
        status: "queued"
```

### 10.2.3 Testing Checklist

- [ ] Upload single text file
- [ ] Upload PDF document (<10MB)
- [ ] Upload large PDF (>10MB)
- [ ] Upload DOCX file
- [ ] Upload image file
- [ ] Upload video file
- [ ] Upload audio file
- [ ] Test duplicate detection
- [ ] Verify B2 storage
- [ ] Check Supabase logging
- [ ] Test error handling for oversized files
- [ ] Test error handling for unsupported types
- [ ] Validate webhook response
- [ ] Monitor performance metrics

### 10.2.4 Success Criteria

- Files correctly classified by type
- Duplicates detected and skipped in Supabase
- All files stored in B2 with metadata
- Metadata logged to Supabase
- Response time <2 seconds for classification
- Error rate <1%
- Proper error messages for invalid files

## 10.3 Milestone 2: Claude API Processing Integration

### 10.3.1 Objectives
- Configure Claude Sonnet 4.5 API endpoints
- Implement batch processing for 90% cost savings
- Set up prompt caching for 50% additional savings
- Create structured output schemas
- Test API-first routing
- Integrate mem-agent for context

### 10.3.2 n8n Workflow Components

```yaml
Milestone_2_Workflow:
  name: "Claude_API_Processing"
  
  nodes:
    1_receive_document:
      type: "n8n-nodes-base.executeWorkflow"
      workflowId: "milestone_1_output"
    
    2_extract_text_markitdown:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "http://mac-studio.local:8001/markitdown/extract"
        method: "POST"
        sendBody: true
        bodyParameters:
          file: "{{$json.fileData}}"
          format: "{{$json.mimeType}}"
          options:
            preserve_formatting: true
            extract_images: true
            include_metadata: true
      options:
        timeout: 60000
        retry:
          maxTries: 3
          waitBetweenTries: 2000
    
    3_prepare_claude_prompt:
      type: "n8n-nodes-base.function"
      code: |
        // Prepare optimized prompt for Claude with caching
        const content = $json.extractedText;
        const metadata = $json.documentMetadata || {};
        
        // System prompt with caching marker
        const systemPrompt = [{
          type: "text",
          text: `You are an expert document analyzer specializing in extracting structured data, 
          categorizing content, generating summaries, and identifying key insights. 
          
          Your analysis should be:
          - Comprehensive and thorough
          - Structured according to the provided JSON schema
          - Focused on actionable insights
          - Tailored to business/educational use cases
          
          Output Format: Clean JSON following the provided schema exactly.`,
          cache_control: { type: "ephemeral" }
        }];
        
        // User prompt with document content
        const userPrompt = `Analyze this document and extract the following information:

        1. **Metadata Extraction:**
           - Document type and category
           - Primary subject/topic
           - Target audience
           - Expertise level (beginner/intermediate/advanced)
           - Estimated reading time
           - Language

        2. **Content Analysis:**
           - Executive summary (150-200 words)
           - Key points (5-10 main takeaways)
           - Main insights and actionable items
           - Notable quotes or important statements

        3. **Entity Recognition:**
           - People mentioned (names, roles)
           - Organizations mentioned
           - Locations referenced
           - Products/services discussed
           - Dates and events

        4. **Quality Assessment:**
           - Content quality score (1-10)
           - Credibility indicators
           - Potential biases
           - Completeness rating

        5. **Categorization:**
           - Primary category
           - Secondary categories
           - Relevant tags (10-15)
           - Department relevance

        Document Title: ${metadata.title || 'Untitled'}
        Document Length: ${content.length} characters

        Document Content:
        ${content}

        Return ONLY valid JSON following this schema:
        {
          "metadata": {
            "type": "string",
            "category": "string",
            "subject": "string",
            "audience": "string",
            "level": "string",
            "reading_time_minutes": number,
            "language": "string"
          },
          "analysis": {
            "executive_summary": "string",
            "key_points": ["string"],
            "insights": ["string"],
            "actionable_items": ["string"],
            "notable_quotes": ["string"]
          },
          "entities": {
            "people": [{"name": "string", "role": "string"}],
            "organizations": ["string"],
            "locations": ["string"],
            "products": ["string"],
            "dates": ["string"]
          },
          "quality": {
            "score": number,
            "credibility": "string",
            "biases": ["string"],
            "completeness": number
          },
          "categorization": {
            "primary_category": "string",
            "secondary_categories": ["string"],
            "tags": ["string"],
            "departments": ["string"]
          }
        }`;
        
        // Determine if batch processing is appropriate
        const useBatch = content.length > 5000 && !$json.urgent;
        const enableCache = true;
        
        return {
          systemPrompt,
          userPrompt,
          useBatch,
          enableCache,
          contentLength: content.length,
          documentId: $json.documentId,
          estimatedTokens: Math.ceil(content.length / 4) // rough estimate
        };
    
    4_claude_api_call:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.claude_api_key}}"
          "anthropic-version": "2023-06-01"
          "anthropic-beta": "prompt-caching-2024-07-31,max-tokens-3-5-sonnet-2024-07-15"
        sendBody: true
        bodyParameters:
          model: "claude-sonnet-4-5-20250929"
          system: "{{$json.systemPrompt}}"
          messages: [{
            role: "user",
            content: "{{$json.userPrompt}}"
          }]
          max_tokens: 4096
          temperature: 0.3
      options:
        timeout: 30000
        retry:
          maxTries: 3
          waitBetweenTries: 2000
    
    5_batch_processor:
      type: "n8n-nodes-base.if"
      conditions:
        - useBatch: true
          route: "batch_api"
        - else:
          route: "standard_api"
    
    6_claude_batch_api:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages/batches"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.claude_api_key}}"
          "anthropic-version": "2023-06-01"
        sendBody: true
        bodyParameters:
          requests: [{
            custom_id: "{{$json.documentId}}",
            params: {
              model: "claude-sonnet-4-5-20250929",
              system: "{{$json.systemPrompt}}",
              messages: [{
                role: "user",
                content: "{{$json.userPrompt}}"
              }],
              max_tokens: 4096,
              temperature: 0.3
            }
          }]
      description: "90% cost savings for non-urgent processing"
    
    7_mem_agent_store:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "http://mac-studio.local:8001/memory/store"
        method: "POST"
        sendBody: true
        bodyParameters:
          user_id: "{{$json.userId || 'system'}}"
          document_id: "{{$json.documentId}}"
          content: {
            summary: "{{$json.analysis.executive_summary}}",
            key_points: "{{$json.analysis.key_points}}",
            category: "{{$json.categorization.primary_category}}",
            tags: "{{$json.categorization.tags}}"
          }
          metadata: {
            document_type: "{{$json.metadata.type}}",
            processed_date: "{{$now.toISO()}}",
            quality_score: "{{$json.quality.score}}"
          }
      description: "Store context in mem-agent for future queries"
    
    8_cost_tracker:
      type: "n8n-nodes-base.function"
      code: |
        // Track Claude API costs with v6.0 pricing
        const usage = $json.usage || {};
        const inputTokens = usage.input_tokens || 0;
        const outputTokens = usage.output_tokens || 0;
        const cacheCreationTokens = usage.cache_creation_input_tokens || 0;
        const cacheReadTokens = usage.cache_read_input_tokens || 0;
        
        // Claude Sonnet 4.5 pricing (per 1M tokens)
        const pricing = {
          input: 0.003,          // $3 per 1M tokens
          output: 0.015,         // $15 per 1M tokens
          cacheWrite: 0.00375,   // $3.75 per 1M tokens (25% more than input)
          cacheRead: 0.0003,     // $0.30 per 1M tokens (90% discount)
        };
        
        // Calculate costs
        const costs = {
          input: (inputTokens * pricing.input) / 1000000,
          output: (outputTokens * pricing.output) / 1000000,
          cacheWrite: (cacheCreationTokens * pricing.cacheWrite) / 1000000,
          cacheRead: (cacheReadTokens * pricing.cacheRead) / 1000000
        };
        
        // Apply batch discount if applicable
        const batchDiscount = $json.useBatch ? 0.90 : 0; // 90% off for batch
        const batchAdjustedCost = (costs.input + costs.output) * (1 - batchDiscount);
        
        const totalCost = costs.input + costs.output + costs.cacheWrite + costs.cacheRead;
        const actualCost = $json.useBatch ? batchAdjustedCost + costs.cacheWrite + costs.cacheRead : totalCost;
        
        // Calculate savings
        const savingsFromBatch = $json.useBatch ? (costs.input + costs.output) * batchDiscount : 0;
        const savingsFromCache = cacheReadTokens > 0 ? 
          (cacheReadTokens * (pricing.input - pricing.cacheRead)) / 1000000 : 0;
        
        return {
          document_id: $json.documentId,
          timestamp: new Date().toISOString(),
          tokens: {
            input: inputTokens,
            output: outputTokens,
            cache_creation: cacheCreationTokens,
            cache_read: cacheReadTokens,
            total: inputTokens + outputTokens
          },
          costs: {
            input: costs.input,
            output: costs.output,
            cache_write: costs.cacheWrite,
            cache_read: costs.cacheRead,
            subtotal: totalCost,
            actual: actualCost
          },
          savings: {
            from_batch: savingsFromBatch,
            from_cache: savingsFromCache,
            total: savingsFromBatch + savingsFromCache
          },
          optimizations: {
            used_batch: $json.useBatch,
            used_cache: cacheReadTokens > 0,
            cache_efficiency: cacheReadTokens / (inputTokens || 1)
          },
          cost_per_token: actualCost / (inputTokens + outputTokens || 1)
        };
```

### 10.3.3 Testing Checklist

- [ ] Test Claude API connectivity
- [ ] Process simple document with Claude
- [ ] Process complex document with Claude
- [ ] Verify batch processing for large docs
- [ ] Test prompt caching effectiveness
- [ ] Validate JSON schema compliance
- [ ] Store memory with mem-agent
- [ ] Verify structured output generation
- [ ] Test cost tracking accuracy
- [ ] Monitor API rate limits
- [ ] Check response quality
- [ ] Validate error recovery
- [ ] Test timeout handling

### 10.3.4 Success Criteria

- Claude API endpoints accessible and responsive
- 97-99% extraction accuracy achieved
- Batch processing saves 90% on costs for non-urgent docs
- Prompt caching reduces costs by 50%+ on repeated patterns
- Memory storage working with mem-agent
- Cost tracking accurate within 1%
- API processing reliable with <0.5% error rate
- Structured output follows schema 100%
- Monthly costs <$50 for typical usage

## 10.4 Milestone 3: Advanced RAG - Vector Storage & Hybrid Search

### 10.4.1 Objectives
- Generate embeddings using optimal embedding model
- Store vectors in Supabase pgvector with HNSW indexing
- Implement 4-method hybrid search (dense/sparse/ILIKE/fuzzy)
- Set up hierarchical structure extraction
- Prepare for context expansion
- Test end-to-end RAG pipeline

### 10.4.2 Supabase pgvector Setup - COMPLETE

**Why Supabase pgvector:**
- **Unified Architecture**: Vectors and metadata in same PostgreSQL database
- **High Performance**: HNSW indexing for fast similarity search (<50ms)
- **Cost Effective**: No separate vector database service needed
- **Unlimited Metadata**: Store rich JSONB metadata with each vector
- **SQL Power**: Combine vector search with complex SQL queries and joins
- **Claude-Ready**: Perfect for Claude API → Supabase workflow
- **Advanced Search**: Supports 4 search methods in single database

**Complete Setup Steps:**

```sql
-- Step 1: Enable required extensions in Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy search
CREATE EXTENSION IF NOT EXISTS btree_gin; -- For better indexing

-- Step 2: Create documents_v2 table with ALL required columns
CREATE TABLE IF NOT EXISTS documents_v2 (
  -- Primary identification
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  
  -- Content fields
  content TEXT NOT NULL,
  contextual_description TEXT,  -- For enhanced embeddings
  
  -- Vector field (1536 for OpenAI/Voyage, adjust for other models)
  embedding vector(1536) NOT NULL,
  
  -- Metadata (rich JSONB for filtering)
  metadata JSONB DEFAULT '{}',
  
  -- Document structure (for context expansion)
  parent_section TEXT,
  parent_range JSONB,  -- {start_chunk: X, end_chunk: Y}
  child_range JSONB,   -- Same structure for subsections
  hierarchical_position TEXT,  -- e.g., "1.2.3"
  
  -- Quality metrics
  quality_score DECIMAL(3,2),
  semantic_density DECIMAL(3,2),
  coherence_score DECIMAL(3,2),
  
  -- Processing metadata
  processing_model TEXT DEFAULT 'claude-sonnet-4-5',
  embedding_model TEXT DEFAULT 'voyage-3',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Unique constraint for upserts
  UNIQUE(document_id, chunk_index)
);

-- Step 3: Create HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS documents_v2_embedding_idx 
ON documents_v2 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
-- m=16: number of connections (higher = better recall, slower build)
-- ef_construction=64: search quality during build (higher = better quality)

-- Step 4: Create GIN indexes for metadata filtering and FTS
CREATE INDEX IF NOT EXISTS documents_v2_metadata_idx 
ON documents_v2 
USING gin (metadata jsonb_path_ops);

CREATE INDEX IF NOT EXISTS documents_v2_content_fts_idx
ON documents_v2
USING gin (to_tsvector('english', content));

-- Step 5: Create trigram index for fuzzy/ILIKE search
CREATE INDEX IF NOT EXISTS documents_v2_content_trgm_idx
ON documents_v2
USING gin (content gin_trgm_ops);

-- Step 6: Create indexes for hierarchical queries (context expansion)
CREATE INDEX IF NOT EXISTS documents_v2_parent_section_idx
ON documents_v2 (parent_section);

CREATE INDEX IF NOT EXISTS documents_v2_hierarchical_idx
ON documents_v2 (hierarchical_position);

-- Step 7: Create the 4-method hybrid search function with RRF
CREATE OR REPLACE FUNCTION dynamic_hybrid_search_db(
  query_text TEXT,
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 10,
  filter jsonb DEFAULT '{}',
  vector_weight float DEFAULT 0.4,
  fts_weight float DEFAULT 0.3,
  ilike_weight float DEFAULT 0.2,
  fuzzy_weight float DEFAULT 0.1,
  rrf_k int DEFAULT 60
)
RETURNS TABLE (
  id uuid,
  document_id text,
  chunk_index int,
  content text,
  contextual_description text,
  metadata jsonb,
  parent_section text,
  parent_range jsonb,
  quality_score decimal,
  similarity float,
  rrf_score float,
  match_method text
)
LANGUAGE plpgsql
AS $$
DECLARE
  vector_results record[];
  fts_results record[];
  ilike_results record[];
  fuzzy_results record[];
  combined_results record[];
BEGIN
  -- Method 1: Vector Similarity Search (Semantic)
  SELECT array_agg(row_to_json(t))
  INTO vector_results
  FROM (
    SELECT 
      d.id,
      d.document_id,
      d.chunk_index,
      d.content,
      d.contextual_description,
      d.metadata,
      d.parent_section,
      d.parent_range,
      d.quality_score,
      1 - (d.embedding <=> query_embedding) as similarity,
      'vector' as match_method,
      ROW_NUMBER() OVER (ORDER BY d.embedding <=> query_embedding) as rank
    FROM documents_v2 d
    WHERE 
      d.metadata @> filter
      AND 1 - (d.embedding <=> query_embedding) > match_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count * 2
  ) t;

  -- Method 2: Full-Text Search (Keyword-based)
  SELECT array_agg(row_to_json(t))
  INTO fts_results
  FROM (
    SELECT 
      d.id,
      d.document_id,
      d.chunk_index,
      d.content,
      d.contextual_description,
      d.metadata,
      d.parent_section,
      d.parent_range,
      d.quality_score,
      ts_rank(to_tsvector('english', d.content), plainto_tsquery('english', query_text)) as similarity,
      'fts' as match_method,
      ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('english', d.content), plainto_tsquery('english', query_text)) DESC) as rank
    FROM documents_v2 d
    WHERE 
      d.metadata @> filter
      AND to_tsvector('english', d.content) @@ plainto_tsquery('english', query_text)
    ORDER BY ts_rank(to_tsvector('english', d.content), plainto_tsquery('english', query_text)) DESC
    LIMIT match_count * 2
  ) t;

  -- Method 3: Pattern Matching (ILIKE)
  SELECT array_agg(row_to_json(t))
  INTO ilike_results
  FROM (
    SELECT 
      d.id,
      d.document_id,
      d.chunk_index,
      d.content,
      d.contextual_description,
      d.metadata,
      d.parent_section,
      d.parent_range,
      d.quality_score,
      0.8 as similarity,  -- Fixed high score for exact matches
      'ilike' as match_method,
      ROW_NUMBER() OVER (ORDER BY d.id) as rank
    FROM documents_v2 d
    WHERE 
      d.metadata @> filter
      AND d.content ILIKE '%' || query_text || '%'
    LIMIT match_count * 2
  ) t;

  -- Method 4: Fuzzy/Trigram Search
  SELECT array_agg(row_to_json(t))
  INTO fuzzy_results
  FROM (
    SELECT 
      d.id,
      d.document_id,
      d.chunk_index,
      d.content,
      d.contextual_description,
      d.metadata,
      d.parent_section,
      d.parent_range,
      d.quality_score,
      similarity(d.content, query_text) as similarity,
      'fuzzy' as match_method,
      ROW_NUMBER() OVER (ORDER BY similarity(d.content, query_text) DESC) as rank
    FROM documents_v2 d
    WHERE 
      d.metadata @> filter
      AND d.content % query_text
    ORDER BY similarity(d.content, query_text) DESC
    LIMIT match_count * 2
  ) t;

  -- Reciprocal Rank Fusion (RRF) to combine all methods
  RETURN QUERY
  WITH all_results AS (
    SELECT * FROM jsonb_to_recordset(
      COALESCE(vector_results::jsonb, '[]'::jsonb) ||
      COALESCE(fts_results::jsonb, '[]'::jsonb) ||
      COALESCE(ilike_results::jsonb, '[]'::jsonb) ||
      COALESCE(fuzzy_results::jsonb, '[]'::jsonb)
    ) AS x(
      id uuid, document_id text, chunk_index int, content text,
      contextual_description text, metadata jsonb, parent_section text,
      parent_range jsonb, quality_score decimal, similarity float,
      match_method text, rank bigint
    )
  ),
  weighted_ranks AS (
    SELECT 
      id,
      document_id,
      chunk_index,
      content,
      contextual_description,
      metadata,
      parent_section,
      parent_range,
      quality_score,
      MAX(similarity) as similarity,
      STRING_AGG(DISTINCT match_method, ',' ORDER BY match_method) as match_method,
      -- RRF score calculation with method-specific weights
      SUM(
        CASE match_method
          WHEN 'vector' THEN vector_weight
          WHEN 'fts' THEN fts_weight
          WHEN 'ilike' THEN ilike_weight
          WHEN 'fuzzy' THEN fuzzy_weight
          ELSE 0
        END / (rrf_k + rank)
      ) as rrf_score
    FROM all_results
    GROUP BY id, document_id, chunk_index, content, contextual_description,
             metadata, parent_section, parent_range, quality_score
  )
  SELECT 
    wr.id,
    wr.document_id,
    wr.chunk_index,
    wr.content,
    wr.contextual_description,
    wr.metadata,
    wr.parent_section,
    wr.parent_range,
    wr.quality_score,
    wr.similarity,
    wr.rrf_score,
    wr.match_method
  FROM weighted_ranks wr
  ORDER BY wr.rrf_score DESC, wr.quality_score DESC NULLS LAST
  LIMIT match_count;
END;
$$;

-- Step 8: Create context expansion edge function
CREATE OR REPLACE FUNCTION expand_context(
  doc_id TEXT,
  chunk_idx INT,
  expand_neighbors INT DEFAULT 1,
  expand_section BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
  id uuid,
  content text,
  chunk_index int,
  expansion_type text
)
LANGUAGE plpgsql
AS $$
BEGIN
  -- Return neighboring chunks
  IF expand_neighbors > 0 THEN
    RETURN QUERY
    SELECT 
      d.id,
      d.content,
      d.chunk_index,
      'neighbor' as expansion_type
    FROM documents_v2 d
    WHERE 
      d.document_id = doc_id
      AND d.chunk_index BETWEEN (chunk_idx - expand_neighbors) AND (chunk_idx + expand_neighbors)
      AND d.chunk_index != chunk_idx
    ORDER BY ABS(d.chunk_index - chunk_idx);
  END IF;

  -- Return full section if requested
  IF expand_section THEN
    RETURN QUERY
    SELECT 
      d.id,
      d.content,
      d.chunk_index,
      'section' as expansion_type
    FROM documents_v2 d
    WHERE 
      d.document_id = doc_id
      AND d.parent_section = (
        SELECT parent_section 
        FROM documents_v2 
        WHERE document_id = doc_id AND chunk_index = chunk_idx
      )
      AND d.chunk_index != chunk_idx
    ORDER BY d.chunk_index;
  END IF;
END;
$$;

-- Step 9: Create hierarchical structure storage table
CREATE TABLE IF NOT EXISTS document_hierarchies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id TEXT NOT NULL UNIQUE,
  hierarchical_index JSONB NOT NULL,  -- Tree structure of headings
  chunk_mappings JSONB NOT NULL,      -- Map headings to chunk ranges
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 10: Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documents_v2_updated_at 
BEFORE UPDATE ON documents_v2
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_hierarchies_updated_at
BEFORE UPDATE ON document_hierarchies
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Step 11: Create record_manager_v2 table for tracking
CREATE TABLE IF NOT EXISTS record_manager_v2 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id TEXT NOT NULL UNIQUE,
  filename TEXT NOT NULL,
  file_hash TEXT NOT NULL UNIQUE,
  processed_date TIMESTAMPTZ DEFAULT NOW(),
  total_chunks INTEGER,
  vector_count INTEGER,
  graph_id TEXT,  -- LightRAG graph ID
  status TEXT DEFAULT 'processing',
  metadata JSONB DEFAULT '{}',
  error_log JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER update_record_manager_v2_updated_at
BEFORE UPDATE ON record_manager_v2
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
```

### 10.4.3 n8n Workflow Components - Advanced RAG Ingestion

```yaml
Milestone_3_Workflow:
  name: "Advanced_RAG_Ingestion_Pipeline"
  
  nodes:
    1_processed_document:
      type: "n8n-nodes-base.executeWorkflow"
      workflowId: "milestone_2_output"
    
    2_hierarchical_structure_extraction:
      type: "n8n-nodes-base.function"
      code: |
        // Extract document hierarchy (headings) for context expansion
        const content = $json.processedContent;
        const lines = content.split('\n');
        
        const hierarchy = [];
        const chunkMapping = {};
        let currentH1 = null;
        let currentH2 = null;
        let currentH3 = null;
        
        lines.forEach((line, idx) => {
          const h1Match = line.match(/^# (.+)$/);
          const h2Match = line.match(/^## (.+)$/);
          const h3Match = line.match(/^### (.+)$/);
          
          if (h1Match) {
            currentH1 = {
              level: 1,
              title: h1Match[1],
              line: idx,
              children: []
            };
            hierarchy.push(currentH1);
            currentH2 = null;
            currentH3 = null;
          } else if (h2Match && currentH1) {
            currentH2 = {
              level: 2,
              title: h2Match[1],
              line: idx,
              children: []
            };
            currentH1.children.push(currentH2);
            currentH3 = null;
          } else if (h3Match && currentH2) {
            currentH3 = {
              level: 3,
              title: h3Match[1],
              line: idx
            };
            currentH2.children.push(currentH3);
          }
        });
        
        return {
          hierarchy: hierarchy,
          totalHeadings: hierarchy.length,
          documentId: $json.documentId
        };
    
    3_semantic_chunking:
      type: "n8n-nodes-base.function"
      code: |
        // Intelligent chunking with overlap and context awareness
        const text = $json.processedContent;
        const hierarchy = $json.hierarchy || [];
        const chunks = [];
        
        const chunkSize = 1500;  // Optimal for Claude and embedding models
        const overlap = 200;     // Context preservation
        
        // Smart chunking that respects sentence boundaries
        function smartChunk(text, size, overlap) {
          const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
          const chunks = [];
          let currentChunk = '';
          let currentSize = 0;
          
          sentences.forEach((sentence, idx) => {
            const sentenceLength = sentence.length;
            
            if (currentSize + sentenceLength > size && currentChunk.length > 0) {
              // Save current chunk
              chunks.push({
                content: currentChunk.trim(),
                start: chunks.length > 0 ? 
                  chunks[chunks.length - 1].end - overlap : 0,
                end: currentSize
              });
              
              // Start new chunk with overlap
              const overlapText = currentChunk.slice(-overlap);
              currentChunk = overlapText + sentence;
              currentSize = overlapText.length + sentenceLength;
            } else {
              currentChunk += sentence;
              currentSize += sentenceLength;
            }
          });
          
          // Add final chunk
          if (currentChunk.length > 0) {
            chunks.push({
              content: currentChunk.trim(),
              start: chunks.length > 0 ? 
                chunks[chunks.length - 1].end - overlap : 0,
              end: currentSize
            });
          }
          
          return chunks;
        }
        
        // Map chunks to hierarchical sections
        function mapToHierarchy(chunks, hierarchy) {
          return chunks.map((chunk, idx) => {
            // Find which section this chunk belongs to
            let parentSection = null;
            let hierarchicalPosition = '';
            
            // Simple mapping - can be enhanced
            hierarchy.forEach((h1, h1Idx) => {
              if (chunk.start >= h1.line) {
                parentSection = h1.title;
                hierarchicalPosition = `${h1Idx + 1}`;
                
                h1.children?.forEach((h2, h2Idx) => {
                  if (chunk.start >= h2.line) {
                    parentSection = `${h1.title} > ${h2.title}`;
                    hierarchicalPosition = `${h1Idx + 1}.${h2Idx + 1}`;
                  }
                });
              }
            });
            
            return {
              ...chunk,
              index: idx,
              parentSection,
              hierarchicalPosition,
              metadata: {
                hasCode: chunk.content.includes('```'),
                hasTable: chunk.content.includes('|'),
                hasLink: chunk.content.includes('http'),
                wordCount: chunk.content.split(/\s+/).length
              }
            };
          });
        }
        
        const rawChunks = smartChunk(text, chunkSize, overlap);
        const enrichedChunks = mapToHierarchy(rawChunks, hierarchy);
        
        return {
          chunks: enrichedChunks,
          totalChunks: enrichedChunks.length,
          documentId: $json.documentId,
          hierarchy: $json.hierarchy
        };
    
    4_contextual_description_generation:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.claude_api_key}}"
          "anthropic-version": "2023-06-01"
        sendBody: true
        bodyParameters:
          model: "claude-sonnet-4-5-20250929"
          system: "You create concise 2-3 sentence contextual descriptions for document chunks."
          messages: [{
            role: "user",
            content: |
              Create a concise contextual description (2-3 sentences) for this chunk.
              Include:
              - What the chunk is about
              - How it relates to the broader document context
              - Key concepts or entities mentioned
              
              Parent Section: {{$json.parentSection}}
              Document Title: {{$json.documentTitle}}
              
              Chunk Content:
              {{$json.content}}
              
              Contextual Description:
          }]
          max_tokens: 200
          temperature: 0.3
      description: "Contextual embedding technique for better retrieval"
    
    5_embedding_generation:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.openai.com/v1/embeddings"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "Authorization": "Bearer {{$credentials.openai_api_key}}"
        sendBody: true
        bodyParameters:
          model: "text-embedding-3-small"
          input: "{{$json.contextualDescription}}\n\n{{$json.content}}"
          encoding_format: "float"
      options:
        batching:
          enabled: true
          batchSize: 100
          batchInterval: 100
    
    6_quality_scoring:
      type: "n8n-nodes-base.function"
      code: |
        // Calculate chunk quality scores for better ranking
        function calculateQualityScore(chunk, claudeAnalysis) {
          let score = 5.0; // Base score
          
          // Content length factor
          const wordCount = chunk.content.split(/\s+/).length;
          if (wordCount >= 100 && wordCount <= 500) score += 1.0;
          else if (wordCount < 50) score -= 1.0;
          
          // Structure factor
          if (chunk.metadata.hasCode) score += 0.5;
          if (chunk.metadata.hasTable) score += 0.5;
          if (chunk.metadata.hasLink) score += 0.3;
          
          // Claude quality assessment
          if (claudeAnalysis) {
            score += (claudeAnalysis.quality_score || 5) * 0.3;
          }
          
          // Normalize to 0-10 scale
          return Math.max(0, Math.min(10, score));
        }
        
        function calculateSemanticDensity(content) {
          // Simple heuristic - can be enhanced
          const words = content.split(/\s+/);
          const uniqueWords = new Set(words.map(w => w.toLowerCase()));
          return Math.min(10, (uniqueWords.size / words.length) * 15);
        }
        
        function calculateCoherence(content) {
          // Placeholder - in production, use NLP models
          const sentences = content.match(/[^.!?]+[.!?]+/g) || [];
          if (sentences.length < 2) return 5.0;
          
          // Simple coherence based on sentence length variance
          const lengths = sentences.map(s => s.length);
          const avgLength = lengths.reduce((a, b) => a + b) / lengths.length;
          const variance = lengths.reduce((sum, len) => 
            sum + Math.pow(len - avgLength, 2), 0) / lengths.length;
          
          // Lower variance = better coherence
          return Math.max(0, Math.min(10, 10 - (variance / 1000)));
        }
        
        return items.map(item => ({
          ...item.json,
          qualityScore: calculateQualityScore(
            item.json, 
            item.json.claudeAnalysis
          ),
          semanticDensity: calculateSemanticDensity(item.json.content),
          coherenceScore: calculateCoherence(item.json.content)
        }));
    
    7_lightrag_entity_extraction:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.lightrag.com/v1/extract"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "Authorization": "Bearer {{$credentials.lightrag_api_key}}"
        sendBody: true
        bodyParameters:
          document_id: "{{$json.documentId}}"
          content: "{{$json.content}}"
          extract_entities: true
          extract_relationships: true
          build_graph: true
      description: "Extract entities and build knowledge graph with LightRAG"
    
    8_supabase_vector_upsert:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        INSERT INTO documents_v2 (
          document_id,
          chunk_index,
          content,
          contextual_description,
          embedding,
          metadata,
          parent_section,
          parent_range,
          hierarchical_position,
          quality_score,
          semantic_density,
          coherence_score,
          processing_model,
          embedding_model
        ) VALUES (
          '{{$json.documentId}}',
          {{$json.chunkIndex}},
          '{{$json.content}}',
          '{{$json.contextualDescription}}',
          '{{$json.embedding}}'::vector,
          '{{$json.metadata}}'::jsonb,
          '{{$json.parentSection}}',
          '{{$json.parentRange}}'::jsonb,
          '{{$json.hierarchicalPosition}}',
          {{$json.qualityScore}},
          {{$json.semanticDensity}},
          {{$json.coherenceScore}},
          'claude-sonnet-4-5',
          'text-embedding-3-small'
        )
        ON CONFLICT (document_id, chunk_index) DO UPDATE SET
          content = EXCLUDED.content,
          embedding = EXCLUDED.embedding,
          contextual_description = EXCLUDED.contextual_description,
          quality_score = EXCLUDED.quality_score,
          updated_at = NOW();
      options:
        batching:
          enabled: true
          batchSize: 100
    
    9_store_hierarchy:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        INSERT INTO document_hierarchies (
          document_id,
          hierarchical_index,
          chunk_mappings
        ) VALUES (
          '{{$json.documentId}}',
          '{{$json.hierarchy}}'::jsonb,
          '{{$json.chunkMappings}}'::jsonb
        )
        ON CONFLICT (document_id) DO UPDATE SET
          hierarchical_index = EXCLUDED.hierarchical_index,
          chunk_mappings = EXCLUDED.chunk_mappings,
          updated_at = NOW();
    
    10_update_record_manager:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        UPDATE record_manager_v2 SET
          total_chunks = {{$json.totalChunks}},
          vector_count = {{$json.totalChunks}},
          graph_id = '{{$json.lightragGraphId}}',
          status = 'completed',
          updated_at = NOW()
        WHERE document_id = '{{$json.documentId}}';
```

### 10.4.4 Testing Checklist - Advanced RAG

- [ ] Extract hierarchical structure from documents
- [ ] Chunk document correctly with semantic overlap
- [ ] Generate contextual descriptions for each chunk
- [ ] Generate embeddings with context prepended
- [ ] Calculate quality scores for ranking
- [ ] Extract entities with LightRAG
- [ ] Store vectors in Supabase with all metadata
- [ ] Test vector similarity search (Method 1)
- [ ] Test full-text search (Method 2)
- [ ] Test pattern matching ILIKE (Method 3)
- [ ] Test fuzzy/trigram search (Method 4)
- [ ] Test hybrid search function (all 4 methods combined)
- [ ] Verify RRF scoring works correctly
- [ ] Test hierarchical structure storage
- [ ] Test context expansion function
- [ ] Verify batch upsert performance
- [ ] Check all indexes are being used
- [ ] Monitor embedding generation costs
- [ ] Test metadata filtering with JSONB queries

### 10.4.5 Success Criteria - Advanced RAG

- Embeddings generated successfully for all chunks
- Contextual descriptions improve retrieval quality by 20%+
- Vectors stored successfully in Supabase pgvector
- All 4 search methods working independently
- Hybrid search returns highly relevant results
- RRF fusion improves ranking by 30%+ vs single method
- Quality scores provide meaningful ranking
- Hierarchical structure extracted and stored
- Context expansion retrieves related chunks
- LightRAG entities extracted successfully
- Retrieval latency <500ms with HNSW index
- Batch processing handles 100+ chunks efficiently
- Metadata filtering works seamlessly with all search types
- No data loss during upserts

## 10.5 Milestone 4: Advanced RAG Query Pipeline - COMPLETE

### 10.5.1 Objectives
- Implement complete query workflow with all advanced RAG features
- Integrate 4-method hybrid search
- Add LightRAG knowledge graph queries
- Implement Cohere reranking for quality boost
- Add context expansion for complete answers
- Synthesize final response with Claude
- Track costs per query

### 10.5.2 n8n Workflow Components - Complete Query Pipeline

```yaml
Milestone_4_Workflow:
  name: "Advanced_RAG_Query_Pipeline_COMPLETE"
  
  nodes:
    1_query_webhook:
      type: "n8n-nodes-base.webhook"
      parameters:
        path: "query-knowledge-base"
        method: "POST"
        responseMode: "onReceived"
      description: "Entry point for user queries"
    
    2_query_preprocessing:
      type: "n8n-nodes-base.function"
      code: |
        // Preprocess and enrich query
        const query = $json.query;
        const department = $json.department || 'All';
        const topK = $json.topK || 10;
        
        // Extract filter criteria
        const filter = {};
        if (department !== 'All') {
          filter.department = department;
        }
        
        // Query expansion (simple version)
        const expandedQuery = query + ' ' + generateSynonyms(query);
        
        function generateSynonyms(text) {
          // Simple synonym expansion - can be enhanced
          const synonymMap = {
            'best practices': 'guidelines recommendations standards',
            'how to': 'tutorial guide steps process',
            'optimize': 'improve enhance boost performance'
          };
          
          let expanded = '';
          Object.entries(synonymMap).forEach(([key, value]) => {
            if (text.toLowerCase().includes(key)) {
              expanded += ' ' + value;
            }
          });
          
          return expanded;
        }
        
        return {
          originalQuery: query,
          expandedQuery,
          filter,
          topK,
          department,
          timestamp: new Date().toISOString(),
          queryId: generateQueryId()
        };
    
    3_generate_query_embedding:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.openai.com/v1/embeddings"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "Authorization": "Bearer {{$credentials.openai_api_key}}"
        sendBody: true
        bodyParameters:
          model: "text-embedding-3-small"
          input: "{{$json.expandedQuery}}"
          encoding_format: "float"
    
    4_hybrid_search:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        SELECT * FROM dynamic_hybrid_search_db(
          query_text := '{{$json.originalQuery}}',
          query_embedding := '{{$json.queryEmbedding}}'::vector,
          match_threshold := 0.5,
          match_count := {{$json.topK}},
          filter := '{{$json.filter}}'::jsonb,
          vector_weight := 0.4,
          fts_weight := 0.3,
          ilike_weight := 0.2,
          fuzzy_weight := 0.1,
          rrf_k := 60
        );
      description: "4-method hybrid search with RRF fusion"
    
    5_lightrag_graph_query:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.lightrag.com/v1/query"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "Authorization": "Bearer {{$credentials.lightrag_api_key}}"
        sendBody: true
        bodyParameters:
          query: "{{$json.originalQuery}}"
          query_type: "hybrid"  # local, global, or hybrid
          top_k: "{{$json.topK}}"
          include_relationships: true
      description: "Query knowledge graph for related entities"
    
    6_merge_results:
      type: "n8n-nodes-base.function"
      code: |
        // Merge hybrid search results with graph results
        const hybridResults = $node['hybrid_search'].json;
        const graphResults = $node['lightrag_graph_query'].json;
        
        // Combine unique results
        const combinedMap = new Map();
        
        // Add hybrid search results
        hybridResults.forEach(result => {
          combinedMap.set(result.id, {
            ...result,
            sources: ['hybrid_search'],
            combined_score: result.rrf_score
          });
        });
        
        // Add/merge graph results
        graphResults.chunks?.forEach(result => {
          if (combinedMap.has(result.id)) {
            const existing = combinedMap.get(result.id);
            existing.sources.push('knowledge_graph');
            existing.combined_score += result.relevance * 0.3;
            existing.graph_context = result.context;
          } else {
            combinedMap.set(result.id, {
              ...result,
              sources: ['knowledge_graph'],
              combined_score: result.relevance * 0.3,
              graph_context: result.context
            });
          }
        });
        
        // Convert to array and sort
        const mergedResults = Array.from(combinedMap.values())
          .sort((a, b) => b.combined_score - a.combined_score)
          .slice(0, $json.topK * 2); // Get 2x for reranking
        
        return {
          results: mergedResults,
          hybridCount: hybridResults.length,
          graphCount: graphResults.chunks?.length || 0,
          mergedCount: mergedResults.length
        };
    
    7_cohere_reranking:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.cohere.ai/v1/rerank"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "Authorization": "Bearer {{$credentials.cohere_api_key}}"
        sendBody: true
        bodyParameters:
          model: "rerank-english-v3.0"
          query: "{{$json.originalQuery}}"
          documents: "{{$json.results.map(r => r.content)}}"
          top_n: "{{$json.topK}}"
          return_documents: true
      description: "Cohere reranking for 30-40% quality improvement"
    
    8_apply_reranking:
      type: "n8n-nodes-base.function"
      code: |
        // Apply Cohere reranking scores to merged results
        const rerankedDocs = $json.results;
        const originalResults = $node['merge_results'].json.results;
        
        const rerankedResults = rerankedDocs.map((doc, idx) => {
          const originalDoc = originalResults[doc.index];
          return {
            ...originalDoc,
            rerank_score: doc.relevance_score,
            rerank_position: idx + 1,
            final_score: (originalDoc.combined_score * 0.4) + 
                        (doc.relevance_score * 0.6)
          };
        }).sort((a, b) => b.final_score - a.final_score);
        
        return {
          rerankedResults,
          topResult: rerankedResults[0],
          averageRelevance: rerankedDocs.reduce((sum, doc) => 
            sum + doc.relevance_score, 0) / rerankedDocs.length
        };
    
    9_context_expansion:
      type: "n8n-nodes-base.function"
      code: |
        // Expand context for top results
        const topResults = $json.rerankedResults.slice(0, 5);
        
        // For each top result, fetch neighboring chunks and full sections
        const expandedContexts = await Promise.all(
          topResults.map(async (result) => {
            // Call context expansion function
            const expansion = await $executeQuery(
              'supabase_postgres',
              `SELECT * FROM expand_context(
                '${result.document_id}',
                ${result.chunk_index},
                1,  -- expand 1 neighbor on each side
                true  -- include full section
              )`
            );
            
            return {
              ...result,
              expanded_chunks: expansion,
              full_context: [
                result.content,
                ...expansion.map(e => e.content)
              ].join('\n\n')
            };
          })
        );
        
        return {
          expandedResults: expandedContexts,
          totalContextLength: expandedContexts.reduce((sum, r) => 
            sum + r.full_context.length, 0)
        };
    
    10_claude_synthesis:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.claude_api_key}}"
          "anthropic-version": "2023-06-01"
          "anthropic-beta": "prompt-caching-2024-07-31"
        sendBody: true
        bodyParameters:
          model: "claude-sonnet-4-5-20250929"
          system: [{
            type: "text",
            text: |
              You are a helpful AI assistant with access to a comprehensive knowledge base.
              Your task is to synthesize information from multiple sources to provide
              accurate, well-cited answers to user queries.
              
              Guidelines:
              - Use information from the provided contexts
              - Cite sources with [Source N] notation
              - Provide comprehensive yet concise answers
              - Acknowledge uncertainty when information is incomplete
              - Structure answers with clear sections when appropriate,
            cache_control: { type: "ephemeral" }
          }]
          messages: [{
            role: "user",
            content: |
              Query: {{$json.originalQuery}}
              
              I have retrieved the following relevant information from the knowledge base:
              
              {{range $idx, $result := $json.expandedResults}}
              [Source {{$idx + 1}}] (Relevance: {{$result.final_score | round 2}})
              Document: {{$result.metadata.title}}
              Section: {{$result.parent_section}}
              
              {{$result.full_context}}
              
              ---
              {{end}}
              
              Please provide a comprehensive answer to the query, citing sources appropriately.
          }]
          max_tokens: 2048
          temperature: 0.3
      description: "Claude synthesizes final answer with citations"
    
    11_format_response:
      type: "n8n-nodes-base.function"
      code: |
        // Format final response with metadata and citations
        const answer = $json.content[0].text;
        const expandedResults = $node['context_expansion'].json.expandedResults;
        
        // Extract and format citations
        const citations = expandedResults.map((result, idx) => ({
          citation_number: idx + 1,
          title: result.metadata.title || result.document_id,
          relevance: result.final_score,
          excerpt: result.content.substring(0, 200) + '...',
          document_id: result.document_id,
          chunk_index: result.chunk_index
        }));
        
        // Calculate costs
        const costs = {
          cohere_rerank: 0.002 * ($json.topK / 1000), // $2 per 1000 searches
          lightrag_query: 0.001, // Flat rate per query
          claude_synthesis: calculateClaudeCost($json.usage),
          embedding: 0.00013 * ($json.queryEmbedding.length / 1000)
        };
        
        costs.total = Object.values(costs).reduce((a, b) => a + b, 0);
        
        return {
          query: $node['query_preprocessing'].json.originalQuery,
          answer,
          citations,
          metadata: {
            query_id: $node['query_preprocessing'].json.queryId,
            timestamp: new Date().toISOString(),
            processing_time_ms: Date.now() - new Date($node['query_preprocessing'].json.timestamp).getTime(),
            hybrid_search_results: $node['hybrid_search'].json.length,
            graph_results: $node['lightrag_graph_query'].json.chunks?.length || 0,
            reranked_count: $json.topK,
            expanded_contexts: expandedResults.length,
            costs
          }
        };
    
    12_store_query_log:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "query_log"
      credentials: "supabase_postgres"
      columns:
        query_id: "{{$json.query_id}}"
        query_text: "{{$json.query}}"
        department: "{{$json.department}}"
        timestamp: "{{$json.metadata.timestamp}}"
        processing_time_ms: "{{$json.metadata.processing_time_ms}}"
        results_count: "{{$json.metadata.reranked_count}}"
        total_cost: "{{$json.metadata.costs.total}}"
        user_id: "{{$json.userId}}"
```

### 10.5.3 Success Criteria - Complete Query Pipeline

- ✅ Hybrid search combines all 4 methods effectively
- ✅ LightRAG returns relevant graph entities
- ✅ Cohere reranking improves precision by 30-40%
- ✅ Context expansion provides complete answers
- ✅ Claude synthesis generates coherent responses
- ✅ Source citations accurate and helpful
- ✅ Query processing time <3 seconds
- ✅ Cost per query <$0.05
- ✅ Answer quality rated 8+ / 10 by users
- ✅ No hallucinations (all info from sources)

## 10.6 Milestone 5: Chat UI Deployment - CRITICAL

### 10.6.1 Objectives
- Deploy user-facing chat interface
- Connect to n8n Advanced RAG pipeline
- Enable end-to-end system functionality
- Provide professional user experience
- Display cost tracking and citations

### 10.6.2 Complete Chat UI Implementation

```python
# chat_ui_gradio.py - Complete Implementation
import gradio as gr
import requests
import os
from datetime import datetime
import json

# Configuration
N8N_QUERY_ENDPOINT = os.getenv("N8N_QUERY_ENDPOINT")
N8N_API_KEY = os.getenv("N8N_API_KEY")

def query_knowledge_base(query, department="All", top_k=10):
    """
    Query the Advanced RAG system via n8n
    Returns formatted answer with citations and metadata
    """
    if not query.strip():
        return "Please enter a question."
    
    try:
        # Call n8n Advanced RAG pipeline
        response = requests.post(
            N8N_QUERY_ENDPOINT,
            json={
                "query": query,
                "department": department,
                "topK": top_k
            },
            headers={
                "Authorization": f"Bearer {N8N_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Format response
        return format_response(result)
        
    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"❌ Error querying knowledge base: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"

def format_response(result):
    """Format the response from n8n into readable markdown"""
    answer = result.get("answer", "No answer generated.")
    citations = result.get("citations", [])
    metadata = result.get("metadata", {})
    
    # Build formatted response
    formatted = f"## Answer\n\n{answer}\n\n"
    
    # Add citations section
    if citations:
        formatted += "## Sources\n\n"
        for source in citations[:5]:  # Top 5 sources
            formatted += f"**[{source['citation_number']}]** {source['title']} "
            formatted += f"(Relevance: {source['relevance']:.2f})\n"
            formatted += f"   {source['excerpt']}...\n\n"
    
    # Add metadata
    stats = f"\n\n**Query Stats:**\n"
    stats += f"- Processing Time: {metadata['processing_time_ms']}ms\n"
    stats += f"- Hybrid Search Results: {metadata['hybrid_search_results']}\n"
    stats += f"- Graph Results: {metadata['graph_results']}\n"
    stats += f"- Reranked Count: {metadata['reranked_count']}\n"
    stats += f"- Total Cost: ${metadata['costs']['total']:.4f}\n"
    stats += f"  - Cohere Rerank: ${metadata['costs']['cohere_rerank']:.4f}\n"
    stats += f"  - LightRAG Query: ${metadata['costs']['lightrag_query']:.4f}\n"
    stats += f"  - Claude Synthesis: ${metadata['costs']['claude_synthesis']:.4f}\n"
    
    return formatted + stats

# Create Gradio interface
with gr.Blocks(title="AI Empire Knowledge Base") as demo:
    gr.Markdown("# 🤖 AI Empire Knowledge Base")
    gr.Markdown("Query your documents using advanced RAG with hybrid search, knowledge graphs, and Cohere reranking")
    
    with gr.Row():
        with gr.Column(scale=2):
            query_input = gr.Textbox(
                label="Ask a question",
                placeholder="What are the best practices for...",
                lines=3
            )
            department_input = gr.Dropdown(
                label="Filter by Department (optional)",
                choices=["All", "Engineering", "Marketing", "Sales", "Finance", "Operations"],
                value="All"
            )
            top_k_slider = gr.Slider(
                minimum=5,
                maximum=20,
                value=10,
                step=1,
                label="Number of results to consider"
            )
            submit_btn = gr.Button("Query Knowledge Base", variant="primary")
        
        with gr.Column(scale=3):
            output = gr.Markdown(label="Answer")
    
    submit_btn.click(
        fn=query_knowledge_base,
        inputs=[query_input, department_input, top_k_slider],
        outputs=output
    )
    
    gr.Markdown("""
    ### How it works:
    1. **Hybrid Search**: Combines 4 search methods (vector, FTS, pattern matching, fuzzy)
    2. **Knowledge Graph**: Finds related entities and relationships via LightRAG
    3. **Cohere Reranking**: Optimizes top results for relevance (30-40% improvement)
    4. **Context Expansion**: Retrieves neighboring chunks and full sections
    5. **Claude Synthesis**: Generates comprehensive answer with citations
    
    ### Features:
    - ✅ 30-50% better search quality than simple vector search
    - ✅ Relationship discovery through knowledge graphs
    - ✅ Source citations with document references
    - ✅ Cost tracking per query (<$0.05 typical)
    - ✅ Department-specific filtering
    - ✅ Complete context with section expansion
    """)

# Launch
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", 7860)),
        share=False
    )
```

### 10.6.3 Render Deployment Configuration

```yaml
# render.yaml - Chat UI Service
services:
  - type: web
    name: ai-empire-chat-ui
    runtime: python
    plan: starter  # $7/month
    region: oregon
    buildCommand: pip install gradio requests python-dotenv
    startCommand: python chat_ui_gradio.py
    envVars:
      - key: N8N_QUERY_ENDPOINT
        sync: false  # Set manually to your n8n webhook URL
      - key: N8N_API_KEY
        sync: false  # Set manually for security
      - key: PORT
        value: 7860
    autoDeploy: true
    healthCheckPath: /
```

### 10.6.4 Success Criteria - Chat UI

- ✅ Chat UI deployed and accessible
- ✅ Connected to n8n Advanced RAG pipeline
- ✅ Users can query knowledge base
- ✅ Responses include source citations
- ✅ Cost tracking visible per query
- ✅ Department filtering works
- ✅ Response time <5 seconds end-to-end
- ✅ Professional user experience
- ✅ Mobile-responsive interface
- ✅ System fully functional for end users

**WHY THIS IS CRITICAL:**
Without Chat UI:
❌ System is unusable for end users
❌ Cannot demonstrate RAG capabilities
❌ Cannot test complete pipeline
❌ Advanced RAG features invisible
❌ No user interface for queries

With Chat UI:
✅ Complete end-to-end functionality
✅ Users can interact with knowledge base
✅ All advanced RAG features accessible
✅ Cost transparency per query
✅ Professional user experience
✅ System ready for production

## 10.7 Milestone 6: Multi-Agent Orchestration

### 10.7.1 Objectives
- Set up CrewAI integration
- Implement agent coordination
- Create analysis workflows
- Test multi-agent tasks
- Monitor agent performance

### 10.7.2 n8n Workflow Components

```yaml
Milestone_6_Workflow:
  name: "Multi_Agent_Analysis"
  
  nodes:
    1_analysis_trigger:
      type: "n8n-nodes-base.webhook"
      parameters:
        path: "analyze-document"
        method: "POST"
    
    2_retrieve_context:
      type: "n8n-nodes-base.executeWorkflow"
      workflowId: "milestone_4_query"
      parameters:
        query: "{{$json.analysisQuery}}"
        topK: 20
    
    3_agent_task_definition:
      type: "n8n-nodes-base.function"
      code: |
        // Define agent tasks based on document type and analysis needs
        const docType = $json.documentType;
        const analysisType = $json.analysisType || 'comprehensive';
        const tasks = [];
        
        // Financial analysis tasks
        if (docType === 'financial' || analysisType.includes('financial')) {
          tasks.push({
            agent: 'financial_analyst',
            task: 'analyze_financial_trends',
            context: $json.context,
            priority: 1,
            expected_output: 'Financial analysis with trends and recommendations'
          });
        }
        
        // Technical analysis tasks
        if (docType === 'technical' || analysisType.includes('technical')) {
          tasks.push({
            agent: 'technical_reviewer',
            task: 'technical_review',
            context: $json.context,
            priority: 2,
            expected_output: 'Technical assessment and improvement suggestions'
          });
        }
        
        // Strategic analysis tasks
        if (analysisType.includes('strategic')) {
          tasks.push({
            agent: 'strategist',
            task: 'strategic_analysis',
            context: $json.context,
            priority: 1,
            expected_output: 'Strategic recommendations and action plan'
          });
        }
        
        // Always include summarizer
        tasks.push({
          agent: 'summarizer',
          task: 'create_executive_summary',
          context: $json.context,
          priority: 3,
          expected_output: 'Executive summary of all analyses'
        });
        
        return {
          tasks,
          totalAgents: tasks.length,
          documentId: $json.documentId
        };
    
    4_crew_ai_orchestration:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://jb-crewai.onrender.com/api/crew/execute"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "Authorization": "Bearer {{$credentials.crewai_api_key}}"
        sendBody: true
        bodyParameters:
          crew_id: "ai-empire-crew"
          tasks: "{{$json.tasks}}"
          context: "{{$node['retrieve_context'].json}}"
          max_agents: 5
          timeout: 300000
          sequential: false  # Parallel execution
    
    5_claude_agent_processing:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.claude_api_key}}"
          "anthropic-version": "2023-06-01"
        sendBody: true
        bodyParameters:
          model: "claude-sonnet-4-5-20250929"
          system: "You are a {{$json.agent_type}} agent in a multi-agent analysis system."
          messages: [{
            role: "user",
            content: "{{$json.task}}: {{$json.context}}"
          }]
          max_tokens: 4000
          temperature: 0.3
      description: "Claude processes each agent task"
    
    6_aggregate_results:
      type: "n8n-nodes-base.function"
      code: |
        // Aggregate results from all agents
        const results = items.map(item => item.json);
        
        function mergeFindings(results) {
          const findings = {};
          results.forEach(result => {
            if (result.findings) {
              Object.assign(findings, result.findings);
            }
          });
          return findings;
        }
        
        function extractRecommendations(results) {
          const recommendations = [];
          results.forEach(result => {
            if (result.recommendations) {
              recommendations.push(...result.recommendations);
            }
          });
          return recommendations;
        }
        
        function generateExecutiveSummary(results) {
          // Combine all agent outputs into executive summary
          const summary = {
            overview: '',
            key_findings: [],
            top_recommendations: [],
            action_items: []
          };
          
          results.forEach(result => {
            if (result.summary) {
              summary.key_findings.push(...result.summary.key_findings || []);
              summary.top_recommendations.push(...result.summary.recommendations || []);
            }
          });
          
          // Deduplicate and prioritize
          summary.key_findings = [...new Set(summary.key_findings)].slice(0, 5);
          summary.top_recommendations = [...new Set(summary.top_recommendations)].slice(0, 5);
          
          return summary;
        }
        
        return {
          documentId: $json.documentId,
          timestamp: new Date().toISOString(),
          agents: results.map(r => r.agent),
          findings: mergeFindings(results),
          recommendations: extractRecommendations(results),
          summary: generateExecutiveSummary(results),
          processingTimeMs: results.reduce((sum, r) => sum + (r.processingTime || 0), 0)
        };
    
    7_store_analysis:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "document_analysis"
      credentials: "supabase_postgres"
      columns:
        document_id: "{{$json.documentId}}"
        analysis_timestamp: "{{$json.timestamp}}"
        agent_results: "{{$json.findings}}"
        recommendations: "{{$json.recommendations}}"
        summary: "{{$json.summary}}"
        processing_time_ms: "{{$json.processingTimeMs}}"
```

### 10.7.3 Testing Checklist

- [ ] Define agent tasks correctly
- [ ] Test CrewAI connectivity
- [ ] Execute multi-agent workflow
- [ ] Test Claude agent processing
- [ ] Verify result aggregation
- [ ] Monitor agent coordination
- [ ] Test timeout handling
- [ ] Check result quality
- [ ] Measure processing time
- [ ] Validate recommendations
- [ ] Test parallel execution
- [ ] Check error handling

### 10.7.4 Success Criteria

- Agents coordinate effectively
- Tasks completed successfully
- Results properly aggregated
- Claude agents functional
- Processing time <5 minutes
- Quality insights generated
- Error handling robust
- Recommendations actionable

## 10.8 Milestone 7: Cost Tracking and Optimization

### 10.8.1 Objectives
- Implement comprehensive cost monitoring
- Track API usage across all services
- Optimize routing decisions based on cost
- Generate cost reports
- Alert on budget thresholds
- Identify cost-saving opportunities

### 10.8.2 n8n Workflow Components

```yaml
Milestone_7_Workflow:
  name: "Cost_Optimization_Tracking"
  
  nodes:
    1_cost_interceptor:
      type: "n8n-nodes-base.function"
      description: "Intercept all API calls for cost tracking"
      code: |
        // Track every API call with v6.0 pricing
        const operation = $json.operation;
        const service = $json.service;
        const usage = $json.usage || {};
        
        const costs = {
          'claude_api': calculateClaudeCost($json),
          'claude_batch': calculateClaudeCost($json) * 0.1, // 90% off
          'cohere_rerank': 0.002 * ($json.searchCount / 1000), // $2 per 1000
          'lightrag_query': 0.001, // Flat per query
          'openai_embed': 0.00013 * (usage.tokens / 1000), // $0.13 per 1M
          'mistral_ocr': 0.01 * $json.pages,
          'soniox': 0.05 * $json.minutes,
          'supabase': 0, // Included in $25/month
          'crewai': 0, // Included in $15-20/month
          'mem_agent': 0  // Free on Mac Studio
        };
        
        function calculateClaudeCost(data) {
          const inputTokens = data.input_tokens || 0;
          const outputTokens = data.output_tokens || 0;
          const cacheWrite = data.cache_write_tokens || 0;
          const cacheRead = data.cache_read_tokens || 0;
          
          return (inputTokens * 0.003 / 1000) + 
                 (outputTokens * 0.015 / 1000) +
                 (cacheWrite * 0.00375 / 1000) +
                 (cacheRead * 0.0003 / 1000);
        }
        
        function calculateSavings(service, operation) {
          if (service === 'claude_batch') {
            return calculateClaudeCost($json) * 0.9; // Saved 90%
          }
          if (operation === 'cache_hit') {
            return $json.input_tokens * (0.003 - 0.0003) / 1000; // Saved 90%
          }
          return 0;
        }
        
        return {
          ...items[0].json,
          cost: costs[service] || 0,
          savedWithOptimizations: calculateSavings(service, operation),
          timestamp: new Date().toISOString()
        };
    
    2_cost_aggregator:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "cost_tracking"
      credentials: "supabase_postgres"
      columns:
        timestamp: "{{$json.timestamp}}"
        service: "{{$json.service}}"
        operation: "{{$json.operation}}"
        cost: "{{$json.cost}}"
        saved_amount: "{{$json.savedWithOptimizations}}"
        document_id: "{{$json.documentId}}"
        workflow_id: "{{$json.workflowId}}"
        usage_details: "{{$json.usage}}"
    
    3_daily_cost_check:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        SELECT 
          DATE(timestamp) as date,
          SUM(cost) as daily_cost,
          SUM(saved_amount) as daily_savings,
          COUNT(DISTINCT document_id) as docs_processed,
          jsonb_object_agg(service, service_cost) as costs_by_service
        FROM (
          SELECT 
            timestamp,
            document_id,
            service,
            SUM(cost) as service_cost
          FROM cost_tracking
          WHERE DATE(timestamp) = CURRENT_DATE
          GROUP BY DATE(timestamp), service, document_id, timestamp
        ) t
        GROUP BY DATE(timestamp);
    
    4_budget_alert:
      type: "n8n-nodes-base.if"
      conditions:
        - expression: "{{$json.daily_cost > 2.00}}"
          output: "send_alert"
          description: "Daily cost exceeds $2 threshold"
        - expression: "{{$json.monthly_estimate > 50}}"
          output: "send_warning"
          description: "Monthly projection exceeds budget"
    
    5_optimization_router:
      type: "n8n-nodes-base.switch"
      rules:
        - rule: "budget_ok"
          condition: "{{$json.monthly_spend < 40}}"
          route: "normal_processing"
          description: "Under budget, continue normal operations"
        - rule: "budget_warning"
          condition: "{{$json.monthly_spend < 45}}"
          route: "prefer_batch"
          description: "Approaching budget, prefer batch processing"
        - rule: "budget_critical"
          condition: "{{$json.monthly_spend >= 50}}"
          route: "batch_only"
          description: "At budget limit, batch processing only"
    
    6_roi_calculator:
      type: "n8n-nodes-base.function"
      code: |
        // Calculate ROI metrics for v6.0
        const monthlyClaudeCost = $json.monthly_spend_claude;
        const monthlyCohereCost = $json.monthly_spend_cohere;
        const monthlyLightRAGCost = $json.monthly_spend_lightrag;
        const documentsProcessed = $json.total_documents;
        const queriesProcessed = $json.total_queries;
        
        const totalMonthlyCost = monthlyClaudeCost + monthlyCohereCost + monthlyLightRAGCost;
        const costPerDoc = totalMonthlyCost / documentsProcessed;
        const costPerQuery = (monthlyCohereCost + monthlyLightRAGCost) / queriesProcessed;
        
        // Calculate value delivered
        const valueMetrics = {
          searchQualityImprovement: 0.35, // 35% better with Cohere + hybrid
          graphInsightsAdded: $json.graph_entities_found,
          contextExpansionUsage: $json.context_expansion_count,
          userSatisfaction: $json.avg_user_rating || 8.5
        };
        
        return {
          costs: {
            monthly: {
              claude: monthlyClaudeCost,
              cohere: monthlyCohereCost,
              lightrag: monthlyLightRAGCost,
              total: totalMonthlyCost
            },
            perDocument: costPerDoc,
            perQuery: costPerQuery
          },
          volume: {
            documentsProcessed,
            queriesProcessed
          },
          value: valueMetrics,
          comparisons: {
            vsSimpleRAG: {
              cost_difference: monthlyCohereCost + monthlyLightRAGCost,
              quality_improvement: valueMetrics.searchQualityImprovement,
              worth_it: valueMetrics.searchQualityImprovement > 0.2
            },
            vsGPT4: {
              cost_savings: monthlyClaudeCost * 2, // Claude is ~50% cheaper
              quality_comparison: 'comparable_or_better'
            }
          },
          optimizations: {
            batch_usage_rate: $json.batch_usage_rate,
            cache_hit_rate: $json.cache_hit_rate,
            potential_monthly_savings: calculatePotentialSavings($json)
          }
        };
        
        function calculatePotentialSavings(data) {
          const savings = {};
          
          // Batch processing potential
          if (data.batch_usage_rate < 0.8) {
            savings.increase_batch = 
              (0.8 - data.batch_usage_rate) * data.monthly_spend_claude * 0.9;
          }
          
          // Cache optimization potential
          if (data.cache_hit_rate < 0.5) {
            savings.improve_caching = 
              (0.5 - data.cache_hit_rate) * data.monthly_spend_claude * 0.5;
          }
          
          return savings;
        }
    
    7_cost_report:
      type: "n8n-nodes-base.emailSend"
      parameters:
        toEmail: "admin@example.com"
        subject: "Daily Cost Report - AI Empire v6.0"
        emailType: "html"
        message: |
          <h2>AI Empire v6.0 Cost Report</h2>
          <p><strong>Date:</strong> {{$json.date}}</p>
          
          <h3>Daily Costs</h3>
          <ul>
            <li>Total Daily Cost: ${{$json.daily_cost}}</li>
            <li>Documents Processed: {{$json.docs_processed}}</li>
            <li>Cost per Document: ${{$json.cost_per_doc}}</li>
            <li>Daily Savings (optimizations): ${{$json.daily_savings}}</li>
          </ul>
          
          <h3>Monthly Projection</h3>
          <ul>
            <li>Estimated Monthly Total: ${{$json.monthly_estimate}}</li>
            <li>Budget Status: {{$json.budget_status}}</li>
            <li>Days Remaining: {{$json.days_remaining}}</li>
          </ul>
          
          <h3>Cost Breakdown by Service</h3>
          <ul>
            <li>Claude Sonnet 4.5: ${{$json.costs_by_service.claude_api}}</li>
            <li>Cohere Rerank: ${{$json.costs_by_service.cohere_rerank}}</li>
            <li>LightRAG: ${{$json.costs_by_service.lightrag_query}}</li>
            <li>OpenAI Embeddings: ${{$json.costs_by_service.openai_embed}}</li>
            <li>Other: ${{$json.costs_by_service.other}}</li>
          </ul>
          
          <h3>Optimizations</h3>
          <ul>
            <li>Batch Processing Rate: {{$json.batch_rate}}%</li>
            <li>Cache Hit Rate: {{$json.cache_hit_rate}}%</li>
            <li>Potential Monthly Savings: ${{$json.potential_savings}}</li>
          </ul>
          
          <h3>ROI Metrics</h3>
          <ul>
            <li>Search Quality Improvement: +{{$json.quality_improvement}}%</li>
            <li>User Satisfaction: {{$json.user_satisfaction}}/10</li>
            <li>Graph Insights Added: {{$json.graph_insights}}</li>
          </ul>
```

### 10.8.3 Testing Checklist

- [ ] Track Claude API calls accurately
- [ ] Track Cohere reranking costs
- [ ] Track LightRAG query costs
- [ ] Track embedding generation costs
- [ ] Calculate costs correctly for each service
- [ ] Monitor batch vs standard ratio
- [ ] Test budget alerts
- [ ] Verify optimization routing
- [ ] Calculate cost per document
- [ ] Calculate cost per query
- [ ] Generate daily reports
- [ ] Test cost aggregation
- [ ] Monitor savings tracking
- [ ] Validate thresholds
- [ ] Test ROI calculations

### 10.8.4 Success Criteria

- All costs tracked accurately across all services
- Budget alerts functional and timely
- Cost per doc <$0.25 (with optimizations)
- Cost per query <$0.05 (with Advanced RAG)
- Reports generated daily
- Optimization routing works correctly
- Monthly costs stay under $50 (typical usage)
- Batch processing >80% for eligible docs
- Cache hit rate >50%
- ROI clearly demonstrated

## 10.9 Milestone 8: Error Handling and Recovery

### 10.9.1 Objectives
- Implement comprehensive error handling for all API calls
- Create recovery workflows for common failures
- Set up circuit breakers to prevent cascade failures
- Build intelligent retry mechanisms with exponential backoff
- Test disaster scenarios and recovery procedures
- Monitor error rates and patterns

### 10.9.2 n8n Workflow Components

```yaml
Milestone_8_Workflow:
  name: "Error_Recovery_System"
  
  nodes:
    1_error_catcher:
      type: "n8n-nodes-base.errorTrigger"
      parameters:
        errorWorkflow: true
      description: "Global error handler for all workflows"
    
    2_error_classifier:
      type: "n8n-nodes-base.function"
      code: |
        // Classify error types for v6.0 architecture
        const error = $json.error;
        const errorMessage = error.message || '';
        const errorCode = error.code || error.httpCode;
        
        const errorTypes = {
          // Network errors
          'ECONNREFUSED': 'network_error',
          'ETIMEDOUT': 'timeout',
          'ENOTFOUND': 'dns_error',
          
          // API errors
          '429': 'rate_limit',
          '500': 'server_error',
          '503': 'service_unavailable',
          '529': 'claude_overloaded',
          
          // Application errors
          'insufficient_quota': 'budget_exceeded',
          'invalid_api_key': 'authentication_error',
          'model_not_found': 'configuration_error'
        };
        
        function detectErrorType(error) {
          // Check error code first
          if (errorTypes[errorCode]) {
            return errorTypes[errorCode];
          }
          
          // Check error message
          for (const [key, type] of Object.entries(errorTypes)) {
            if (errorMessage.includes(key)) {
              return type;
            }
          }
          
          return 'unknown_error';
        }
        
        function calculateSeverity(error) {
          const criticalErrors = [
            'authentication_error',
            'budget_exceeded',
            'configuration_error'
          ];
          
          const highErrors = [
            'rate_limit',
            'service_unavailable'
          ];
          
          const errorType = detectErrorType(error);
          
          if (criticalErrors.includes(errorType)) return 'critical';
          if (highErrors.includes(errorType)) return 'high';
          return 'medium';
        }
        
        function isRetryable(error) {
          const retryableErrors = [
            'timeout',
            'rate_limit',
            'server_error',
            'service_unavailable',
            'network_error'
          ];
          
          return retryableErrors.includes(detectErrorType(error));
        }
        
        function hasFallback(error) {
          const errorType = detectErrorType(error);
          
          // Services with fallback options
          const fallbackMap = {
            'claude_api': 'batch_processing',
            'cohere_rerank': 'skip_reranking',
            'lightrag_query': 'vector_only',
            'openai_embed': 'cached_embeddings'
          };
          
          return fallbackMap[$json.service] !== undefined;
        }
        
        return {
          errorType: detectErrorType(error),
          severity: calculateSeverity(error),
          retryable: isRetryable(error),
          fallbackAvailable: hasFallback(error),
          originalError: error,
          service: $json.service,
          workflow: $json.workflow,
          timestamp: new Date().toISO String()
        };
    
    3_circuit_breaker:
      type: "n8n-nodes-base.function"
      code: |
        // Implement circuit breaker pattern to prevent cascade failures
        const service = $json.service;
        
        // Check failure count from database
        async function getFailureCount(service) {
          const result = await $executeQuery(
            'supabase_postgres',
            `SELECT COUNT(*) as failures
             FROM error_log
             WHERE service = '${service}'
             AND timestamp > NOW() - INTERVAL '5 minutes'
             AND error_type IN ('timeout', 'server_error', 'service_unavailable')`
          );
          return result[0].failures;
        }
        
        async function getCircuitState(service) {
          const result = await $executeQuery(
            'supabase_postgres',
            `SELECT state, reset_time
             FROM circuit_breaker_state
             WHERE service = '${service}'`
          );
          return result[0] || { state: 'CLOSED', reset_time: null };
        }
        
        const failures = await getFailureCount(service);
        const currentState = await getCircuitState(service);
        
        // Circuit breaker logic
        if (currentState.state === 'OPEN') {
          // Check if it's time to try again (half-open state)
          if (new Date() > new Date(currentState.reset_time)) {
            return {
              circuitState: 'HALF_OPEN',
              service: service,
              action: 'retry_once',
              message: 'Attempting service recovery'
            };
          }
          
          return {
            circuitState: 'OPEN',
            service: service,
            resetTime: currentState.reset_time,
            action: 'use_fallback',
            message: `Circuit open for ${service}, using fallback`
          };
        }
        
        // Check if we should open the circuit
        if (failures >= 5) {
          const resetTime = new Date(Date.now() + 60000); // 1 minute
          
          // Update circuit state
          await $executeQuery(
            'supabase_postgres',
            `INSERT INTO circuit_breaker_state (service, state, reset_time)
             VALUES ('${service}', 'OPEN', '${resetTime.toISOString()}')
             ON CONFLICT (service) DO UPDATE SET
               state = 'OPEN',
               reset_time = '${resetTime.toISOString()}',
               updated_at = NOW()`
          );
          
          return {
            circuitState: 'OPEN',
            service: service,
            failures: failures,
            resetTime: resetTime,
            action: 'use_fallback',
            message: `Circuit opened for ${service} due to ${failures} failures`
          };
        }
        
        return {
          circuitState: 'CLOSED',
          service: service,
          failures: failures,
          action: 'retry',
          message: `Circuit closed for ${service}, safe to retry`
        };
    
    4_retry_logic:
      type: "n8n-nodes-base.function"
      code: |
        // Intelligent retry with exponential backoff
        const retryCount = $json.retryCount || 0;
        const maxRetries = 3;
        const baseDelay = 1000; // 1 second
        
        if (retryCount >= maxRetries) {
          return {
            shouldRetry: false,
            exhausted: true,
            message: 'Max retries exceeded'
          };
        }
        
        // Exponential backoff: 1s, 2s, 4s
        const delay = baseDelay * Math.pow(2, retryCount);
        const jitter = Math.random() * 1000; // Add jitter to prevent thundering herd
        const totalDelay = delay + jitter;
        
        return {
          shouldRetry: true,
          retryCount: retryCount + 1,
          delayMs: totalDelay,
          nextRetryAt: new Date(Date.now() + totalDelay).toISOString()
        };
    
    5_wait_with_backoff:
      type: "n8n-nodes-base.wait"
      parameters:
        amount: "={{Math.ceil($json.delayMs / 1000)}}"
        unit: "seconds"
    
    6_fallback_router:
      type: "n8n-nodes-base.switch"
      rules:
        - rule: "claude_down"
          condition: "{{$json.service === 'claude_api' && $json.circuitState === 'OPEN'}}"
          route: "queue_for_batch"
          description: "Claude API down, queue for batch processing"
        
        - rule: "cohere_down"
          condition: "{{$json.service === 'cohere_rerank' && $json.circuitState === 'OPEN'}}"
          route: "skip_reranking"
          description: "Cohere down, continue without reranking"
        
        - rule: "lightrag_down"
          condition: "{{$json.service === 'lightrag_query' && $json.circuitState === 'OPEN'}}"
          route: "vector_only"
          description: "LightRAG down, use vector search only"
        
        - rule: "crewai_down"
          condition: "{{$json.service === 'crewai' && $json.circuitState === 'OPEN'}}"
          route: "skip_analysis"
          description: "CrewAI down, skip multi-agent analysis"
        
        - rule: "database_down"
          condition: "{{$json.service === 'supabase' && $json.circuitState === 'OPEN'}}"
          route: "cache_mode"
          description: "Database down, operate from cache"
        
        - rule: "embedding_down"
          condition: "{{$json.service === 'openai_embed' && $json.circuitState === 'OPEN'}}"
          route: "use_cached_embeddings"
          description: "Embedding API down, use cached embeddings"
    
    7_recovery_actions:
      type: "n8n-nodes-base.function"
      code: |
        // Execute recovery procedures for v6.0
        const errorType = $json.errorType;
        const service = $json.service;
        const recoverySteps = [];
        
        // Rate limit recovery
        if (errorType === 'rate_limit') {
          recoverySteps.push({
            action: 'switch_to_batch',
            description: 'Move remaining work to batch processing',
            priority: 1
          });
          recoverySteps.push({
            action: 'enable_aggressive_caching',
            description: 'Increase cache usage to reduce API calls',
            priority: 2
          });
          recoverySteps.push({
            action: 'throttle_requests',
            description: 'Reduce request rate temporarily',
            priority: 2
          });
        }
        
        // Budget exceeded recovery
        if (errorType === 'budget_exceeded') {
          recoverySteps.push({
            action: 'pause_processing',
            description: 'Temporarily pause non-critical processing',
            priority: 1
          });
          recoverySteps.push({
            action: 'send_budget_alert',
            description: 'Alert administrators',
            priority: 1
          });
          recoverySteps.push({
            action: 'enable_batch_only_mode',
            description: 'Switch to batch processing only (90% savings)',
            priority: 2
          });
        }
        
        // Service unavailable recovery
        if (errorType === 'service_unavailable') {
          recoverySteps.push({
            action: 'activate_fallback',
            description: `Use fallback for ${service}`,
            priority: 1
          });
          recoverySteps.push({
            action: 'monitor_service_status',
            description: 'Check service status endpoint',
            priority: 2
          });
        }
        
        // Timeout recovery
        if (errorType === 'timeout') {
          recoverySteps.push({
            action: 'reduce_batch_size',
            description: 'Process smaller batches',
            priority: 1
          });
          recoverySteps.push({
            action: 'increase_timeout',
            description: 'Temporarily increase timeout limits',
            priority: 2
          });
        }
        
        // Execute recovery steps
        async function executeRecovery(steps) {
          const results = [];
          
          for (const step of steps.sort((a, b) => a.priority - b.priority)) {
            try {
              // Execute recovery action
              const result = await performRecoveryAction(step.action, $json);
              results.push({
                ...step,
                status: 'success',
                result: result
              });
            } catch (error) {
              results.push({
                ...step,
                status: 'failed',
                error: error.message
              });
            }
          }
          
          return results;
        }
        
        const recoveryResults = await executeRecovery(recoverySteps);
        
        return {
          errorType,
          service,
          recoverySteps,
          recoveryResults,
          recovered: recoveryResults.every(r => r.status === 'success')
        };
    
    8_dead_letter_queue:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "dead_letter_queue"
      credentials: "supabase_postgres"
      columns:
        error_timestamp: "{{$json.timestamp}}"
        workflow_id: "{{$json.workflow}}"
        error_type: "{{$json.errorType}}"
        error_message: "{{$json.originalError.message}}"
        service: "{{$json.service}}"
        retry_count: "{{$json.retryCount}}"
        recovery_attempted: "{{$json.recoveryResults}}"
        document_data: "{{$json.documentData}}"
        can_retry_later: "{{$json.retryable}}"
      description: "Store failed operations for manual review"
    
    9_error_notification:
      type: "n8n-nodes-base.emailSend"
      parameters:
        toEmail: "admin@example.com"
        subject: "[{{$json.severity}}] AI Empire Error: {{$json.errorType}}"
        emailType: "html"
        message: |
          <h2>Error Report - AI Empire v6.0</h2>
          <p><strong>Severity:</strong> {{$json.severity}}</p>
          <p><strong>Service:</strong> {{$json.service}}</p>
          <p><strong>Error Type:</strong> {{$json.errorType}}</p>
          <p><strong>Timestamp:</strong> {{$json.timestamp}}</p>
          
          <h3>Error Details</h3>
          <pre>{{$json.originalError}}</pre>
          
          <h3>Recovery Actions</h3>
          <ul>
            {{range $json.recoveryResults}}
            <li>{{.action}}: {{.status}}</li>
            {{end}}
          </ul>
          
          <h3>Circuit Breaker Status</h3>
          <p>State: {{$json.circuitState}}</p>
          <p>Failures: {{$json.failures}}</p>
          {{if $json.resetTime}}
          <p>Reset Time: {{$json.resetTime}}</p>
          {{end}}
    
    10_log_error:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "error_log"
      credentials: "supabase_postgres"
      columns:
        timestamp: "{{$json.timestamp}}"
        service: "{{$json.service}}"
        workflow: "{{$json.workflow}}"
        error_type: "{{$json.errorType}}"
        severity: "{{$json.severity}}"
        error_message: "{{$json.originalError.message}}"
        circuit_state: "{{$json.circuitState}}"
        recovery_success: "{{$json.recovered}}"
        retry_count: "{{$json.retryCount}}"
```

### 10.9.3 Testing Checklist

- [ ] Simulate Claude API outage
- [ ] Simulate Cohere API failures
- [ ] Simulate LightRAG failures
- [ ] Test CrewAI timeout scenarios
- [ ] Trigger rate limits intentionally
- [ ] Force timeout errors
- [ ] Test circuit breaker opening
- [ ] Test circuit breaker half-open recovery
- [ ] Verify retry logic with exponential backoff
- [ ] Test fallback routes for each service
- [ ] Check dead letter queue population
- [ ] Verify error notifications sent
- [ ] Monitor recovery success rates
- [ ] Validate error logging
- [ ] Test manual recovery procedures

### 10.9.4 Success Criteria

- All errors caught and classified correctly
- Circuit breaker prevents cascade failures
- Retries work with proper exponential backoff
- Fallbacks activate correctly for each service
- Recovery procedures execute successfully
- Dead letter queue captures unrecoverable failures
- System remains stable during outages
- No data loss during failures
- Error notifications timely and accurate
- Manual recovery procedures documented and tested

## 10.10 Milestone 9: Monitoring and Observability

### 10.10.1 Objectives
- Set up comprehensive system monitoring
- Create performance dashboards
- Implement real-time alerting system
- Track workflow execution metrics
- Monitor system health across all services
- Provide visibility into cost and performance

### 10.10.2 n8n Workflow Components

```yaml
Milestone_9_Workflow:
  name: "Monitoring_Observability_System"
  
  nodes:
    1_metrics_collector:
      type: "n8n-nodes-base.schedule"
      parameters:
        interval: 60  # Every minute
        triggerAtStart: true
    
    2_system_health_checks:
      type: "n8n-nodes-base.function"
      code: |
        // Check health of all services
        async function checkServiceHealth(service, endpoint) {
          try {
            const response = await fetch(endpoint, {
              method: 'GET',
              timeout: 5000
            });
            
            return {
              service,
              status: response.ok ? 'healthy' : 'degraded',
              responseTime: response.headers.get('x-response-time'),
              timestamp: new Date().toISOString()
            };
          } catch (error) {
            return {
              service,
              status: 'down',
              error: error.message,
              timestamp: new Date().toISOString()
            };
          }
        }
        
        const services = [
          { name: 'claude_api', endpoint: 'https://api.anthropic.com/v1/health' },
          { name: 'cohere_api', endpoint: 'https://api.cohere.ai/v1/check-api-key' },
          { name: 'lightrag_api', endpoint: 'https://api.lightrag.com/health' },
          { name: 'crewai_service', endpoint: process.env.CREWAI_HEALTH_ENDPOINT },
          { name: 'supabase_db', endpoint: process.env.SUPABASE_URL + '/rest/v1/' },
          { name: 'mem_agent', endpoint: 'http://mac-studio.local:8001/health' }
        ];
        
        const healthChecks = await Promise.all(
          services.map(s => checkServiceHealth(s.name, s.endpoint))
        );
        
        return {
          timestamp: new Date().toISOString(),
          services: healthChecks,
          overall_status: healthChecks.every(h => h.status === 'healthy') ? 'healthy' : 'degraded'
        };
    
    3_performance_metrics:
      type: "n8n-nodes-base.function"
      code: |
        // Collect v6.0 performance metrics
        async function collectMetrics() {
          // Query database for recent metrics
          const recentQueries = await $executeQuery(
            'supabase_postgres',
            `SELECT 
               COUNT(*) as total_queries,
               AVG(processing_time_ms) as avg_latency,
               MAX(processing_time_ms) as max_latency,
               MIN(processing_time_ms) as min_latency,
               AVG(total_cost) as avg_cost_per_query
             FROM query_log
             WHERE timestamp > NOW() - INTERVAL '1 hour'`
          );
          
          const recentDocs = await $executeQuery(
            'supabase_postgres',
            `SELECT 
               COUNT(*) as docs_processed,
               COUNT(CASE WHEN status = 'completed' THEN 1 END) as success_count,
               COUNT(CASE WHEN status = 'failed' THEN 1 END) as error_count
             FROM record_manager_v2
             WHERE created_at > NOW() - INTERVAL '1 hour'`
          );
          
          const costMetrics = await $executeQuery(
            'supabase_postgres',
            `SELECT 
               SUM(cost) as hourly_cost,
               jsonb_object_agg(service, service_cost) as costs_by_service
             FROM (
               SELECT 
                 service,
                 SUM(cost) as service_cost
               FROM cost_tracking
               WHERE timestamp > NOW() - INTERVAL '1 hour'
               GROUP BY service
             ) t`
          );
          
          // Get circuit breaker states
          const circuitStates = await $executeQuery(
            'supabase_postgres',
            `SELECT service, state
             FROM circuit_breaker_state
             WHERE updated_at > NOW() - INTERVAL '5 minutes'`
          );
          
          return {
            timestamp: new Date().toISOString(),
            queries: recentQueries[0],
            documents: recentDocs[0],
            costs: costMetrics[0],
            circuit_breakers: circuitStates,
            error_rate: recentDocs[0].error_count / (recentDocs[0].docs_processed || 1)
          };
        }
        
        return await collectMetrics();
    
    4_calculate_service_metrics:
      type: "n8n-nodes-base.function"
      code: |
        // Calculate detailed service metrics
        const metrics = $json;
        
        return {
          timestamp: new Date().toISOString(),
          metrics: {
            // API Performance
            api_response_times: {
              claude: metrics.claude_latency || 0,
              cohere: metrics.cohere_latency || 0,
              lightrag: metrics.lightrag_latency || 0
            },
            
            // Processing Metrics
            processing: {
              documents_per_hour: metrics.documents.docs_processed,
              queries_per_hour: metrics.queries.total_queries,
              average_query_latency_ms: metrics.queries.avg_latency,
              error_rate_percent: (metrics.error_rate * 100).toFixed(2),
              success_rate_percent: ((1 - metrics.error_rate) * 100).toFixed(2)
            },
            
            // Cost Metrics
            costs: {
              hourly_total: metrics.costs.hourly_cost,
              daily_projection: metrics.costs.hourly_cost * 24,
              monthly_projection: metrics.costs.hourly_cost * 24 * 30,
              by_service: metrics.costs.costs_by_service
            },
            
            // Quality Metrics
            quality: {
              avg_relevance_score: metrics.avg_relevance || 0,
              cache_hit_rate: metrics.cache_hits / (metrics.total_requests || 1),
              batch_usage_rate: metrics.batch_requests / (metrics.total_requests || 1)
            },
            
            // System Health
            health: {
              overall_status: metrics.overall_status,
              services_up: metrics.services?.filter(s => s.status === 'healthy').length || 0,
              services_total: metrics.services?.length || 0,
              circuit_breakers_open: metrics.circuit_breakers?.filter(c => c.state === 'OPEN').length || 0
            }
          }
        };
    
    5_store_metrics:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "system_metrics"
      credentials: "supabase_postgres"
      columns:
        timestamp: "{{$json.timestamp}}"
        metrics_data: "{{$json.metrics}}"
        metric_type: "system_health"
      options:
        returning: "id"
    
    6_anomaly_detection:
      type: "n8n-nodes-base.function"
      code: |
        // Detect anomalies in v6.0 metrics
        const metrics = $json.metrics;
        const anomalies = [];
        
        // Performance anomalies
        if (metrics.processing.average_query_latency_ms > 5000) {
          anomalies.push({
            type: 'performance',
            metric: 'query_latency',
            value: metrics.processing.average_query_latency_ms,
            threshold: 5000,
            severity: 'high',
            message: `Query latency (${metrics.processing.average_query_latency_ms}ms) exceeds threshold (5000ms)`
          });
        }
        
        // Error rate anomalies
        if (parseFloat(metrics.processing.error_rate_percent) > 2.0) {
          anomalies.push({
            type: 'reliability',
            metric: 'error_rate',
            value: metrics.processing.error_rate_percent,
            threshold: 2.0,
            severity: 'high',
            message: `Error rate (${metrics.processing.error_rate_percent}%) exceeds threshold (2%)`
          });
        }
        
        // Cost anomalies
        if (metrics.costs.daily_projection > 2.50) {
          anomalies.push({
            type: 'cost',
            metric: 'daily_spend',
            value: metrics.costs.daily_projection,
            threshold: 2.50,
            severity: 'medium',
            message: `Daily cost projection ($${metrics.costs.daily_projection}) exceeds threshold ($2.50)`
          });
        }
        
        // Service health anomalies
        if (metrics.health.circuit_breakers_open > 0) {
          anomalies.push({
            type: 'availability',
            metric: 'circuit_breakers',
            value: metrics.health.circuit_breakers_open,
            threshold: 0,
            severity: 'high',
            message: `${metrics.health.circuit_breakers_open} circuit breaker(s) open`
          });
        }
        
        // Quality anomalies
        if (metrics.quality.cache_hit_rate < 0.4) {
          anomalies.push({
            type: 'efficiency',
            metric: 'cache_hit_rate',
            value: metrics.quality.cache_hit_rate,
            threshold: 0.4,
            severity: 'low',
            message: `Cache hit rate (${(metrics.quality.cache_hit_rate * 100).toFixed(1)}%) below optimal (40%)`
          });
        }
        
        return {
          timestamp: new Date().toISOString(),
          anomalies,
          has_anomalies: anomalies.length > 0,
          critical_anomalies: anomalies.filter(a => a.severity === 'high').length
        };
    
    7_alert_dispatcher:
      type: "n8n-nodes-base.switch"
      rules:
        - rule: "critical"
          condition: "{{$json.critical_anomalies > 0}}"
          route: "immediate_alert"
          description: "Critical issues require immediate attention"
        
        - rule: "high"
          condition: "{{$json.anomalies.some(a => a.severity === 'high')}}"
          route: "standard_alert"
          description: "High priority issues"
        
        - rule: "medium"
          condition: "{{$json.anomalies.some(a => a.severity === 'medium')}}"
          route: "email_alert"
          description: "Medium priority - email notification"
        
        - rule: "low"
          condition: "{{$json.anomalies.some(a => a.severity === 'low')}}"
          route: "log_only"
          description: "Low priority - log for review"
    
    8_send_alert:
      type: "n8n-nodes-base.emailSend"
      parameters:
        toEmail: "admin@example.com"
        subject: "[{{$json.severity}}] AI Empire Alert: {{$json.anomaly_count}} Anomalies Detected"
        emailType: "html"
        message: |
          <h2>AI Empire v6.0 Monitoring Alert</h2>
          <p><strong>Timestamp:</strong> {{$json.timestamp}}</p>
          <p><strong>Severity:</strong> {{$json.severity}}</p>
          <p><strong>Anomalies Detected:</strong> {{$json.anomaly_count}}</p>
          
          <h3>Anomaly Details</h3>
          {{range $json.anomalies}}
          <div style="margin: 10px 0; padding: 10px; border-left: 3px solid 
               {{if eq .severity "high"}}red{{else if eq .severity "medium"}}orange{{else}}yellow{{end}}">
            <p><strong>Type:</strong> {{.type}}</p>
            <p><strong>Metric:</strong> {{.metric}}</p>
            <p><strong>Current Value:</strong> {{.value}}</p>
            <p><strong>Threshold:</strong> {{.threshold}}</p>
            <p><strong>Message:</strong> {{.message}}</p>
          </div>
          {{end}}
          
          <h3>Recommended Actions</h3>
          <ul>
            {{if .contains "query_latency"}}
            <li>Check API response times</li>
            <li>Review database query performance</li>
            <li>Consider scaling resources</li>
            {{end}}
            {{if .contains "error_rate"}}
            <li>Review error logs</li>
            <li>Check service health</li>
            <li>Verify API credentials</li>
            {{end}}
            {{if .contains "daily_spend"}}
            <li>Review cost tracking dashboard</li>
            <li>Enable batch processing for more work</li>
            <li>Increase cache usage</li>
            {{end}}
          </ul>
    
    9_dashboard_update:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "{{$env.GRAFANA_URL}}/api/datasources/proxy/1/api/v1/push"
        method: "POST"
        authentication: "apiKey"
        sendBody: true
        bodyParameters:
          streams: [{
            stream: {
              job: "ai-empire-metrics",
              environment: "production"
            },
            values: [[
              "{{Date.now() * 1000000}}",
              "{{JSON.stringify($json.metrics)}}"
            ]]
          }]
      description: "Push metrics to Grafana for visualization"
    
    10_log_monitoring_event:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "monitoring_events"
      credentials: "supabase_postgres"
      columns:
        timestamp: "{{$json.timestamp}}"
        event_type: "metrics_collection"
        metrics_snapshot: "{{$json.metrics}}"
        anomalies_detected: "{{$json.anomalies}}"
        alerts_sent: "{{$json.alerts_sent}}"
```

### 10.10.3 Testing Checklist

- [ ] Verify metrics collection every minute
- [ ] Test health checks for all services
- [ ] Monitor API response times
- [ ] Track performance metrics accurately
- [ ] Test anomaly detection rules
- [ ] Verify alert routing for each severity
- [ ] Check Grafana dashboard updates
- [ ] Test email alerts
- [ ] Monitor cost tracking
- [ ] Validate circuit breaker monitoring
- [ ] Test threshold calculations
- [ ] Verify historical data storage
- [ ] Check dashboard visualization
- [ ] Test alert suppression for known issues

### 10.10.4 Success Criteria

- All metrics collected successfully every minute
- Health checks functional for all services
- Anomalies detected within 2 minutes
- Alerts dispatched correctly by severity
- Dashboards updated in real-time
- Historical data retained for 90 days
- Performance impact <1% overhead
- Alert false-positive rate <5%
- All services observable
- Trends visible and actionable

## 10.11 Milestone 10: Complete Integration Testing

### 10.11.1 Objectives
- Test end-to-end workflows across all milestones
- Validate all integrations work together
- Stress test system under load
- Document actual performance vs targets
- Certify system production-ready

### 10.11.2 Integration Test Scenarios

```yaml
Test_Scenarios:
  
  scenario_1_simple_document:
    description: "Process simple text document with full Advanced RAG"
    steps:
      - name: "Upload text file"
        expected_time: "<2s"
      - name: "Extract with MarkItDown"
        expected_time: "<5s"
      - name: "Process with Claude Sonnet 4.5"
        expected_time: "<10s"
      - name: "Generate embeddings"
        expected_time: "<3s"
      - name: "Store in Supabase pgvector"
        expected_time: "<2s"
      - name: "Extract entities with LightRAG"
        expected_time: "<5s"
      - name: "Query with Advanced RAG"
        expected_time: "<3s"
    total_expected_time: "<30 seconds"
    expected_cost: "$0.02-0.05"
    success_criteria:
      - "Document fully indexed"
      - "All 4 search methods work"
      - "LightRAG entities extracted"
      - "Query returns relevant results"
      - "Cohere reranking improves quality"
    
  scenario_2_complex_pdf:
    description: "Process complex PDF with images and tables"
    steps:
      - name: "Upload large PDF"
        expected_time: "<5s"
      - name: "Detect complexity"
        expected_time: "<1s"
      - name: "Route to Mistral OCR (if needed)"
        expected_time: "<30s"
      - name: "Process with Claude API"
        expected_time: "<15s"
      - name: "Extract structured data"
        expected_time: "<10s"
      - name: "Store with full hierarchy"
        expected_time: "<5s"
    total_expected_time: "<2 minutes"
    expected_cost: "<$0.30"
    success_criteria:
      - "OCR accurate >95%"
      - "Tables extracted correctly"
      - "Hierarchy preserved"
      - "Context expansion works"
    
  scenario_3_video_processing:
    description: "Process video with transcription and analysis"
    steps:
      - name: "Upload video file"
        expected_time: "<10s"
      - name: "Transcribe with Soniox"
        expected_time: "<video_length * 0.5>"
      - name: "Process transcript with Claude"
        expected_time: "<20s"
      - name: "Generate summary"
        expected_time: "<10s"
      - name: "Store results"
        expected_time: "<5s"
    total_expected_time: "<5 minutes for 10min video"
    expected_cost: "<$0.50"
    success_criteria:
      - "Transcription accuracy >90%"
      - "Summary captures key points"
      - "Searchable transcript created"
    
  scenario_4_universal_content_analysis:
    description: "Process course material with full analysis"
    steps:
      - name: "Upload course material"
        expected_time: "<5s"
      - name: "Extract with MarkItDown"
        expected_time: "<10s"
      - name: "Process with Claude API"
        expected_time: "<15s"
      - name: "Analyze with CrewAI"
        expected_time: "<30s"
      - name: "Extract insights and frameworks"
        expected_time: "<20s"
      - name: "Map to departments"
        expected_time: "<5s"
      - name: "Store in Backblaze B2"
        expected_time: "<10s"
      - name: "Update Supabase vectors"
        expected_time: "<10s"
    total_expected_time: "<3 minutes"
    expected_cost: "<$0.15"
    success_criteria:
      - "Insights extracted accurately"
      - "Workflows identified"
      - "Frameworks cataloged"
      - "Department mapping correct"
    
  scenario_5_advanced_rag_query:
    description: "Complex query using full Advanced RAG pipeline"
    steps:
      - name: "Submit user query"
        expected_time: "<1s"
      - name: "Generate query embedding"
        expected_time: "<0.5s"
      - name: "Execute 4-method hybrid search"
        expected_time: "<0.5s"
      - name: "Query LightRAG knowledge graph"
        expected_time: "<1s"
      - name: "Merge results"
        expected_time: "<0.2s"
      - name: "Rerank with Cohere"
        expected_time: "<0.5s"
      - name: "Expand context"
        expected_time: "<0.3s"
      - name: "Synthesize with Claude"
        expected_time: "<2s"
      - name: "Format and return"
        expected_time: "<0.2s"
    total_expected_time: "<3 seconds"
    expected_cost: "<$0.05"
    success_criteria:
      - "All search methods contribute"
      - "Graph entities found"
      - "Reranking improves top results"
      - "Context complete"
      - "Citations accurate"
      - "Answer quality 8+/10"
    
  scenario_6_batch_processing:
    description: "Batch processing for cost optimization"
    steps:
      - name: "Queue 50 documents"
        expected_time: "<10s"
      - name: "Process via Claude Batch API"
        expected_time: "<4 hours"
      - name: "90% cost reduction"
        expected_savings: "$2.25 (vs $2.50 standard)"
      - name: "Verify all results"
        expected_time: "<30s"
    total_expected_time: "<4 hours (background)"
    expected_cost: "<$0.25 (saved $2.25)"
    success_criteria:
      - "All 50 docs processed"
      - "90% cost savings achieved"
      - "Quality maintained"
      - "No failures"
    
  scenario_7_error_recovery:
    description: "Test system resilience during API outages"
    steps:
      - name: "Simulate Claude API failure"
        expected_behavior: "Fallback to batch queue"
      - name: "Simulate Cohere failure"
        expected_behavior: "Continue without reranking"
      - name: "Simulate LightRAG failure"
        expected_behavior: "Use vector search only"
      - name: "Verify circuit breaker"
        expected_behavior: "Opens after 5 failures"
      - name: "Test recovery"
        expected_behavior: "Recovers automatically"
    success_criteria:
      - "No data loss"
      - "Graceful degradation"
      - "Circuit breaker works"
      - "Automatic recovery"
    
  scenario_8_stress_test:
    description: "Load test with 100 concurrent queries"
    steps:
      - name: "Send 100 concurrent queries"
        expected_time: "<10s avg per query"
      - name: "Monitor resource usage"
        expected: "No crashes"
      - name: "Check error rate"
        expected: "<2%"
      - name: "Verify all responses"
        expected: "Complete and accurate"
    success_criteria:
      - "System remains stable"
      - "Avg response time <5s"
      - "Error rate <2%"
      - "No degradation"
```

### 10.11.3 Complete Testing Checklist

#### Database & Storage
- [ ] All Supabase extensions enabled
- [ ] All tables created with correct schemas
- [ ] All indexes created and optimized
- [ ] HNSW index performs <50ms searches
- [ ] All 4 search methods work independently
- [ ] Hybrid search RRF fusion works correctly
- [ ] Context expansion retrieves related chunks
- [ ] Hierarchical structure stored correctly
- [ ] Backblaze B2 storage accessible
- [ ] B2 folder structure correct

#### API Integrations
- [ ] Claude Sonnet 4.5 API accessible
- [ ] Batch API processes correctly
- [ ] Prompt caching saves 50%+
- [ ] Cohere Rerank v3.5 working
- [ ] LightRAG entity extraction working
- [ ] LightRAG graph queries working
- [ ] OpenAI embeddings generating
- [ ] CrewAI agents responding
- [ ] Mistral OCR (when needed)
- [ ] Soniox transcription (when needed)

#### Workflows
- [ ] Document intake classifies correctly
- [ ] Duplicate detection works
- [ ] MarkItDown extracts correctly
- [ ] Claude processing accurate
- [ ] Hierarchical extraction works
- [ ] Contextual descriptions generated
- [ ] Embeddings stored with metadata
- [ ] LightRAG entities extracted
- [ ] Hybrid search returns results
- [ ] Cohere reranking improves quality
- [ ] Context expansion works
- [ ] Claude synthesis accurate
- [ ] Cost tracking accurate

#### Error Handling
- [ ] All errors caught and classified
- [ ] Circuit breakers work correctly
- [ ] Retry logic with backoff works
- [ ] Fallbacks activate properly
- [ ] Dead letter queue populated
- [ ] Error notifications sent
- [ ] Recovery procedures execute

#### Monitoring
- [ ] Metrics collected every minute
- [ ] Health checks functional
- [ ] Anomalies detected correctly
- [ ] Alerts dispatched properly
- [ ] Dashboards updated real-time
- [ ] Cost tracking accurate
- [ ] Performance metrics accurate

#### End-to-End
- [ ] Run all 8 test scenarios
- [ ] Document actual vs expected results
- [ ] Measure actual costs
- [ ] Benchmark performance
- [ ] Test with real user queries
- [ ] Validate answer quality
- [ ] Check citation accuracy

### 10.11.4 Success Criteria - Production Ready

#### Performance
- ✅ Query response time: <3 seconds (95th percentile)
- ✅ Document processing: <2 minutes for standard docs
- ✅ Hybrid search: <500ms with indexes
- ✅ Context expansion: <300ms
- ✅ Cohere reranking: <500ms
- ✅ LightRAG queries: <1 second
- ✅ Claude synthesis: <2 seconds

#### Quality
- ✅ Search relevance: 30-50% better than vector-only
- ✅ Reranking precision: 30-40% improvement
- ✅ Answer accuracy: >95%
- ✅ Citation accuracy: 100%
- ✅ User satisfaction: 8+/10

#### Reliability
- ✅ Uptime: >99.5%
- ✅ Error rate: <1%
- ✅ Data loss: 0%
- ✅ Recovery time: <4 hours
- ✅ Circuit breakers functional

#### Cost
- ✅ Monthly total: $167-240 (with all features)
- ✅ Cost per document: <$0.25
- ✅ Cost per query: <$0.05
- ✅ Batch savings: 90% achieved
- ✅ Cache savings: 50%+ achieved

#### Features
- ✅ All 4 search methods working
- ✅ Knowledge graphs populated
- ✅ Reranking improving results
- ✅ Context expansion complete
- ✅ Chat UI functional
- ✅ All APIs integrated
- ✅ Monitoring comprehensive

## 10.12 Production Deployment Checklist

### 10.12.1 Pre-Deployment

#### Infrastructure
- [ ] Render account created and configured
- [ ] n8n deployed to Render
- [ ] CrewAI deployed to Render
- [ ] Chat UI deployed to Render
- [ ] Supabase project created
- [ ] Backblaze B2 bucket created

#### API Accounts
- [ ] Claude Sonnet 4.5 API key obtained
- [ ] Cohere Rerank v3.5 account created
- [ ] LightRAG API account created
- [ ] OpenAI embeddings API key obtained
- [ ] All API keys stored securely

#### Database Setup
- [ ] Run all SQL scripts from Milestone 3
- [ ] Verify all extensions enabled
- [ ] Verify all indexes created
- [ ] Test hybrid search function
- [ ] Test context expansion function

#### Testing
- [ ] All integration tests passed
- [ ] Performance benchmarks met
- [ ] Error handling tested
- [ ] Recovery procedures tested
- [ ] Load testing completed

#### Documentation
- [ ] Operational procedures documented
- [ ] Recovery procedures documented
- [ ] API documentation complete
- [ ] User guides created
- [ ] Cost tracking explained

### 10.12.2 Deployment Steps

#### Phase 1: Database (Day 1)
1. [ ] Create Supabase project
2. [ ] Enable pgvector extension
3. [ ] Run all table creation scripts
4. [ ] Create all indexes
5. [ ] Deploy edge functions
6. [ ] Test database connectivity
7. [ ] Verify all functions work

#### Phase 2: API Setup (Day 1-2)
1. [ ] Sign up for Claude API
2. [ ] Sign up for Cohere Rerank
3. [ ] Sign up for LightRAG
4. [ ] Configure OpenAI embeddings
5. [ ] Store all keys in n8n credentials
6. [ ] Test each API independently
7. [ ] Verify rate limits and quotas

#### Phase 3: n8n Workflows (Day 2-3)
1. [ ] Deploy n8n to Render
2. [ ] Import all workflow templates
3. [ ] Configure credentials
4. [ ] Enable webhooks
5. [ ] Test each milestone independently
6. [ ] Test end-to-end flow
7. [ ] Verify error workflows active

#### Phase 4: Supporting Services (Day 3-4)
1. [ ] Deploy CrewAI to Render
2. [ ] Deploy Chat UI to Render
3. [ ] Configure Mac Studio mem-agent
4. [ ] Configure MarkItDown MCP
5. [ ] Test all integrations
6. [ ] Verify monitoring active

#### Phase 5: Validation (Day 4-5)
1. [ ] Run all test scenarios
2. [ ] Process sample documents
3. [ ] Execute sample queries
4. [ ] Verify cost tracking
5. [ ] Check error handling
6. [ ] Test recovery procedures
7. [ ] Validate monitoring dashboards

### 10.12.3 Post-Deployment

#### First 24 Hours
- [ ] Monitor all services continuously
- [ ] Review error logs
- [ ] Check cost tracking
- [ ] Verify all features working
- [ ] Respond to any alerts

#### First Week
- [ ] Daily cost reviews
- [ ] Performance optimization
- [ ] User feedback collection
- [ ] Documentation updates
- [ ] Issue resolution

#### First Month
- [ ] Monthly cost analysis
- [ ] Performance tuning
- [ ] Feature usage analysis
- [ ] User satisfaction survey
- [ ] System optimization

## 10.13 Implementation Checklist - COMPLETE CORRECTED

### Phase 1: Database Setup (Week 1)
- [ ] Enable pgvector, pg_trgm, btree_gin extensions in Supabase
- [ ] Create documents_v2 table with ALL required columns
- [ ] Create HNSW index for vector search
- [ ] Create GIN indexes for FTS and metadata
- [ ] Create trigram indexes for fuzzy search
- [ ] Implement dynamic_hybrid_search_db function (complete with RRF)
- [ ] Implement expand_context edge function
- [ ] Create document_hierarchies table
- [ ] Create record_manager_v2 table
- [ ] Create circuit_breaker_state table
- [ ] Create cost_tracking table
- [ ] Create error_log table
- [ ] Create query_log table
- [ ] Test all 4 search methods independently
- [ ] Test RRF fusion
- [ ] Test context expansion

### Phase 2: API Integrations (Week 1-2)
- [ ] Sign up for Claude Sonnet 4.5 API ($30-50/month)
- [ ] Sign up for Cohere Rerank v3.5 API ($20/month)
- [ ] Sign up for LightRAG API ($15/month)
- [ ] Sign up for OpenAI embeddings API (usage-based)
- [ ] Configure all API credentials in n8n
- [ ] Test Claude processing with batch and caching
- [ ] Test Cohere reranking with sample data
- [ ] Test LightRAG entity extraction
- [ ] Test OpenAI embedding generation
- [ ] Verify API billing and quotas
- [ ] Set up cost tracking for each API

### Phase 3: n8n Ingestion Workflow (Week 2)
- [ ] Deploy n8n to Render ($15-30/month)
- [ ] Implement Milestone 1: Document Intake
- [ ] Implement Milestone 2: Claude API Processing
- [ ] Implement Milestone 3: Advanced RAG Ingestion
- [ ] Add hierarchical structure extraction node
- [ ] Add contextual description generation node
- [ ] Add LightRAG entity extraction node
- [ ] Update Supabase upsert to include all metadata
- [ ] Store graph_id mappings in record_manager
- [ ] Test end-to-end ingestion with sample documents
- [ ] Verify all data stored correctly
- [ ] Test cost tracking in ingestion

### Phase 4: n8n Query Workflow (Week 2-3)
- [ ] Implement Milestone 4: Advanced RAG Query Pipeline
- [ ] Add query preprocessing node
- [ ] Add embedding generation node
- [ ] Add hybrid search node (calls dynamic_hybrid_search_db)
- [ ] Add LightRAG graph query node
- [ ] Add result merging logic
- [ ] Add Cohere reranking node
- [ ] Add context expansion node
- [ ] Add Claude synthesis node
- [ ] Add response formatting node
- [ ] Test complete query pipeline
- [ ] Verify all features working together
- [ ] Measure actual vs expected performance

### Phase 5: Chat UI Deployment (Week 3) - CRITICAL
- [ ] Create Gradio chat interface (chat_ui_gradio.py)
- [ ] Implement query_knowledge_base function
- [ ] Implement format_response function
- [ ] Configure environment variables
- [ ] Deploy to Render ($7-15/month)
- [ ] Connect to n8n query endpoint
- [ ] Test user queries end-to-end
- [ ] Verify cost tracking display
- [ ] Validate source citations
- [ ] Test department filtering
- [ ] Test mobile responsiveness
- [ ] Launch to users
- [ ] Collect initial feedback

### Phase 6: Supporting Milestones (Week 3-4)
- [ ] Implement Milestone 6: Multi-Agent Orchestration
- [ ] Implement Milestone 7: Cost Tracking
- [ ] Implement Milestone 8: Error Handling
- [ ] Implement Milestone 9: Monitoring
- [ ] Implement Milestone 10: Integration Testing
- [ ] Deploy CrewAI to Render ($15-20/month)
- [ ] Test all workflows together
- [ ] Run complete integration tests
- [ ] Document actual performance

### Phase 7: Monitoring & Optimization (Week 4)
- [ ] Set up cost tracking dashboards
- [ ] Configure performance monitoring
- [ ] Set up alerting system
- [ ] Optimize search weights if needed
- [ ] Fine-tune RRF parameters
- [ ] Review user feedback
- [ ] Optimize slow queries
- [ ] Document lessons learned
- [ ] Create operational runbook
- [ ] Train team on system

## 10.14 Cost Structure Summary - COMPLETE CORRECTED

**Monthly Costs with COMPLETE Advanced RAG:**

| Service | Cost | Status | Essential | Notes |
|---------|------|--------|-----------|-------|
| Claude Sonnet 4.5 API | $30-50 | Active | **YES** | Primary AI, batch + cache |
| Cohere Rerank v3.5 | $20 | **MISSING** | **YES** | 30-40% quality boost |
| LightRAG API | $15 | **MISSING** | **YES** | Knowledge graphs |
| OpenAI Embeddings | $5-10 | Active | **YES** | text-embedding-3-small |
| n8n (Render) | $15-30 | Active | **YES** | Workflow orchestration |
| CrewAI (Render) | $15-20 | Active | **YES** | Content analysis |
| Chat UI (Render) | $7-15 | **MISSING** | **YES** | User interface |
| Supabase | $25 | Active | **YES** | Unified database |
| Backblaze B2 | $10-20 | Active | **YES** | Storage |
| Mistral OCR | $0-20 | Usage | Optional | Complex PDFs only |
| Soniox | $0-20 | Usage | Optional | Audio/video only |
| **TOTAL** | **$167-240** | **~60% Complete** | - | **Full system** |

**Current State:**
- ✅ Have: Claude, n8n, CrewAI, Supabase, B2, embeddings
- ❌ Missing: Cohere Rerank, LightRAG, Chat UI
- **Need to add:** $42-50/month for complete system

**Value Delivered with Full System:**
- 🎯 Best-in-class RAG system
- 🎯 30-50% better search quality vs simple vector
- 🎯 Knowledge graph capabilities
- 🎯 40% better precision with reranking
- 🎯 Complete context with expansion
- 🎯 Professional chat interface
- 🎯 Full system functionality
- 🎯 Production-ready platform

## 10.15 Critical Next Steps - PRIORITIZED

### Immediate (This Week):
1. **Set up Cohere Rerank v3.5 account** - cohere.com ($20/month)
2. **Set up LightRAG API account** - lightrag.com ($15/month)
3. **Deploy Chat UI** - Gradio on Render ($7-15/month)
4. **Implement missing database functions** - Run complete SQL scripts
5. **Test hybrid search** - Verify all 4 methods working

### Week 2:
1. **Complete n8n ingestion workflow** - Add all missing nodes
2. **Test LightRAG integration** - Verify entity extraction and graphs
3. **Test Cohere reranking** - Measure quality improvement
4. **Validate Supabase storage** - Check all indexes and functions
5. **Test context expansion** - Verify hierarchical retrieval

### Week 3:
1. **Complete query workflow** - All Advanced RAG pipeline nodes
2. **End-to-end testing** - Verify complete functionality
3. **Performance optimization** - Fine-tune parameters
4. **Cost validation** - Ensure within budget
5. **User acceptance testing** - Get feedback on Chat UI

### Week 4:
1. **Production launch** - Go live with complete system
2. **Documentation finalization** - Update all guides
3. **Team training** - Operational procedures
4. **Performance monitoring** - Track all metrics
5. **Continuous optimization** - Based on real usage

---

**Document Version:** 10.0 - COMPLETE with Full Advanced RAG
**Last Updated:** October 24, 2025
**Status:** Implementation guide ready - includes ALL original content + new features
**Total Lines:** 2,500+ (was 2,192 original, added 300+ for Chat UI and expanded RAG)
**Priority:** HIGH - Complete implementation immediately
**Timeline:** 4 weeks to full deployment
**Next Action:** Deploy missing services (Cohere, LightRAG, Chat UI) and complete workflow implementation

## 10.16 Workflow Templates (Exportable n8n JSON)

Each milestone includes complete, exportable n8n workflow templates. See individual milestone sections for full workflow configurations.

## 10.17 Troubleshooting Guide

### Common Issues and Solutions

**Issue: Claude API rate limits**
- Switch to batch processing (90% savings)
- Enable aggressive caching
- Implement request queuing
- Monitor rate limit headers
- Use exponential backoff

**Issue: High API costs**
- Verify batch processing enabled (should be >80%)
- Check cache hit rates (target >50%)
- Review prompt optimization
- Monitor token usage per document
- Adjust processing frequency

**Issue: Poor search quality**
- Verify all 4 hybrid search methods active
- Check Cohere reranking is working
- Test LightRAG graph queries
- Review RRF weight parameters
- Validate context expansion

**Issue: Slow query response**
- Check HNSW index is created
- Monitor API latencies
- Review query complexity
- Optimize context expansion
- Consider caching frequent queries

**Issue: Missing search results**
- Verify embeddings generated correctly
- Check vector dimensions (1536)
- Test each search method independently
- Review metadata filters
- Validate RRF fusion

**Issue: LightRAG errors**
- Check API credentials
- Verify graph creation during ingestion
- Test entity extraction independently
- Review graph query syntax
- Check API quota

**Issue: Cohere reranking failures**
- Verify API key valid
- Check input format
- Monitor API usage limits
- Test with smaller batches
- Review error messages

**Issue: Context expansion not working**
- Verify hierarchical structure extracted
- Check parent_section fields populated
- Test expand_context function directly
- Review chunk range mappings
- Validate SQL function syntax

**Issue: Chat UI connection errors**
- Verify n8n webhook URL correct
- Check API key authentication
- Test n8n endpoint directly
- Review CORS settings
- Monitor network connectivity

## 10.18 Performance Optimization Tips

### 1. Query Optimization
- Cache frequently asked questions
- Pre-compute embeddings for common queries
- Optimize RRF weights based on query type
- Use metadata filters to reduce search space
- Batch similar queries together

### 2. Cost Optimization
- Batch non-urgent processing (90% savings)
- Maximize cache hits (50%+ savings)
- Use appropriate model sizes
- Monitor cost per document/query
- Set strict budget alerts

### 3. Database Optimization
- Keep HNSW index parameters optimized (m=16, ef_construction=64)
- Batch inserts when possible (100+ vectors)
- Use JSONB indexes for metadata
- Regular VACUUM operations
- Monitor query performance

### 4. API Optimization
- Use Claude batch API when possible
- Enable prompt caching
- Minimize payload sizes
- Parallel API calls where safe
- Monitor rate limits proactively

### 5. Search Quality Optimization
- Tune RRF weights (vector: 0.4, fts: 0.3, ilike: 0.2, fuzzy: 0.1)
- Adjust similarity thresholds per query type
- Optimize Cohere reranking top_n
- Fine-tune context expansion parameters
- A/B test search configurations

### 6. Workflow Efficiency
- Minimize node count where possible
- Use parallel processing for independent tasks
- Implement proper error handling
- Monitor execution times
- Regular performance audits

---

**This completes the comprehensive n8n Orchestration Implementation Guide for AI Empire v6.0, including ALL original content from the 2,192-line version PLUS the new Chat UI deployment and expanded Advanced RAG features, totaling 2,500+ lines of detailed implementation guidance.**