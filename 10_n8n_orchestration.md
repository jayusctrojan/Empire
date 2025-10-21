# 10. n8n Orchestration Implementation Guide

## 10.1 Overview

This section provides a practical, milestone-based approach to implementing the AI Empire v6.0 workflow orchestration using n8n. Each milestone represents a testable, independent component that builds upon the previous one, allowing for systematic validation before proceeding to the next stage.

### 10.1.1 Implementation Philosophy

**Core Principles:**
- **Incremental Development:** Build and test one component at a time
- **Milestone-Based:** Each milestone is independently functional
- **Test-First:** Validate each component before integration
- **API-First:** Leverage Claude Sonnet 4.5 API for all intelligent processing
- **Fail-Safe:** Include error handling from the beginning
- **Observable:** Add logging and monitoring at each step

### 10.1.2 n8n Architecture for v6.0

```
n8n Instance (Render - $15-30/month)
├── Webhook Endpoints (Entry Points)
├── Workflow Engine (Orchestration)
├── Node Types:
│   ├── Claude API Nodes (Primary Processing)
│   ├── CrewAI Nodes (ESSENTIAL - Content Analysis)
│   ├── Supabase Nodes (Unified Database + Vectors)
│   ├── Router Nodes (Intelligence)
│   └── Utility Nodes (Support)
└── Monitoring & Logging
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
        return {
          filename: file.name,
          size: file.size,
          mimeType: file.type,
          hash: calculateHash(file),
          timestamp: new Date().toISOString(),
          valid: validateFile(file)
        };
    
    3_duplicate_check:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      query: |
        SELECT id FROM documents 
        WHERE file_hash = '{{$node["file_validation"].json["hash"]}}'
    
    4_classification_router:
      type: "n8n-nodes-base.switch"
      rules:
        - fast_track:
            condition: "{{$json.mimeType in ['text/plain', 'text/markdown']}}"
        - complex_pdf:
            condition: "{{$json.mimeType === 'application/pdf' && $json.size > 10485760}}"
        - multimedia:
            condition: "{{$json.mimeType.startsWith('video/') || $json.mimeType.startsWith('audio/')}}"
        - standard:
            condition: "true"
    
    5_save_to_b2:
      type: "n8n-nodes-base.s3"
      parameters:
        bucketName: "ai-empire-documents"
        operation: "upload"
        additionalFields:
          storageClass: "STANDARD"
          serverSideEncryption: true
    
    6_log_intake:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "document_intake_log"
      columns:
        - document_id
        - intake_timestamp
        - classification
        - file_size
        - mime_type
```

### 10.2.3 Testing Checklist

- [ ] Upload single text file
- [ ] Upload PDF document
- [ ] Upload image file
- [ ] Upload video file
- [ ] Test duplicate detection
- [ ] Verify B2 storage
- [ ] Check database logging
- [ ] Test error handling
- [ ] Validate webhook response
- [ ] Monitor performance metrics

### 10.2.4 Success Criteria

- Files correctly classified by type
- Duplicates detected and skipped
- All files stored in B2
- Metadata logged to database
- Response time <2 seconds
- Error rate <1%

## 10.3 Milestone 2: Claude API Document Processing

### 10.3.1 Objectives
- Integrate Claude Sonnet 4.5 API
- Implement intelligent document processing
- Set up batch processing for cost optimization
- Enable prompt caching for efficiency
- Create fallback mechanisms

### 10.3.2 n8n Workflow Components

```yaml
Milestone_2_Workflow:
  name: "Claude_API_Processing"
  
  nodes:
    1_receive_document:
      type: "n8n-nodes-base.executeWorkflow"
      workflowId: "milestone_1_output"
    
    2_privacy_check:
      type: "n8n-nodes-base.function"
      code: |
        // Detect PII and sensitive content
        const content = $json.content;
        const hasPII = detectPII(content);
        const hasFinancial = detectFinancialData(content);
        const hasHealthcare = detectHealthcareData(content);
        
        return {
          ...items[0].json,
          requiresHighPrivacy: hasPII || hasFinancial || hasHealthcare,
          privacyLevel: calculatePrivacyLevel(content)
        };
    
    3_processing_router:
      type: "n8n-nodes-base.if"
      conditions:
        - requiresBatch: "{{$json.documents.length > 10}}"
          route: "batch_processing"
        - else:
          route: "real_time_processing"
    
    4_claude_api_processing:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.anthropicApi.apiKey}}"
          "anthropic-version": "2023-06-01"
          "anthropic-beta": "prompt-caching-2024-07-31"
        sendBody: true
        bodyParameters:
          model: "claude-3-5-sonnet-20241022"
          max_tokens: 4096
          temperature: 0.3
          system: "You are an expert document analyst. Extract structured data, categorize content, and generate summaries."
          messages: [{
            role: "user",
            content: "{{$json.content}}"
          }]
      options:
        timeout: 30000
        retry:
          maxTries: 3
          waitBetweenTries: 2000
    
    5_claude_batch_processing:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages/batches"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.anthropicApi.apiKey}}"
          "anthropic-version": "2023-06-01"
        sendBody: true
        bodyParameters:
          requests: "{{$json.batchRequests}}"
      options:
        note: "Batch processing provides 90% cost savings"
    
    6_mem_agent_store:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "http://mac-studio.local:8001/memory/store"
        method: "POST"
        bodyParameters:
          user_id: "{{$json.userId}}"
          content: "{{$json.processedContent}}"
          metadata: "{{$json.metadata}}"
    
    7_cost_tracking:
      type: "n8n-nodes-base.function"
      code: |
        // Track API costs with optimizations
        const inputTokens = $json.usage.input_tokens;
        const outputTokens = $json.usage.output_tokens;
        const isBatch = $json.processing_type === 'batch';
        const hasCaching = $json.cache_creation_input_tokens > 0;
        
        // Claude Sonnet 4.5 pricing (per million tokens)
        const inputPrice = 3.00;   // $3/M tokens
        const outputPrice = 15.00;  // $15/M tokens
        
        // Apply discounts
        const batchDiscount = isBatch ? 0.1 : 1.0;  // 90% off for batch
        const cacheDiscount = hasCaching ? 0.5 : 1.0; // 50% off for cached
        
        const cost = (
          (inputTokens * inputPrice / 1000000) +
          (outputTokens * outputPrice / 1000000)
        ) * batchDiscount * cacheDiscount;
        
        return {
          ...items[0].json,
          cost_usd: cost,
          savings: {
            batch: isBatch ? cost * 9 : 0,  // Amount saved
            cache: hasCaching ? cost : 0
          }
        };
```

### 10.3.3 Testing Checklist

- [ ] Test Claude API connectivity
- [ ] Process document with Claude Sonnet 4.5
- [ ] Verify batch processing for multiple documents
- [ ] Test prompt caching effectiveness
- [ ] Store memory with mem-agent
- [ ] Test PII detection routing
- [ ] Verify cost tracking accuracy
- [ ] Monitor API response times
- [ ] Check structured output generation
- [ ] Validate error recovery

### 10.3.4 Success Criteria

- Claude API integration working
- Response time <3 seconds for single docs
- Batch processing reduces costs by 90%
- Prompt caching reduces costs by 50%
- Structured JSON output consistent
- Memory storage functional
- Error handling robust
- Monthly costs <$50 for AI processing

## 10.4 Milestone 3: Vector Storage and RAG Pipeline

### 10.4.1 Objectives
- Generate embeddings with Claude or nomic-embed-text
- Store vectors in Supabase pgvector (unified database architecture)
- Implement semantic search with HNSW indexing
- Set up hybrid retrieval combining vector similarity with metadata filtering
- Test end-to-end RAG pipeline

### 10.4.2 Supabase pgvector Setup

**Why Supabase pgvector:**
- **Unified Architecture**: Vectors and metadata in the same PostgreSQL database
- **High Performance**: HNSW indexing for fast similarity search
- **Cost Effective**: No separate vector database service needed
- **Unlimited Metadata**: Store rich JSONB metadata with each vector
- **SQL Power**: Combine vector search with complex SQL queries and joins
- **Perfect Integration**: Works seamlessly with n8n Postgres nodes

**Setup Steps:**

```sql
-- Step 1: Enable pgvector extension in Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Create documents table with vector column
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  embedding vector(768),  -- nomic-embed-text dimensions
  quality_score DECIMAL(3,2),
  semantic_density DECIMAL(3,2),
  coherence_score DECIMAL(3,2),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 3: Create HNSW index for fast similarity search
CREATE INDEX ON documents 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Step 4: Create GIN index for metadata filtering  
CREATE INDEX ON documents USING gin (metadata);

-- Step 5: Create hybrid search function
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding vector(768),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 10,
  filter jsonb DEFAULT '{}'
)
RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  quality_score decimal,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    documents.id,
    documents.content,
    documents.metadata,
    documents.quality_score,
    1 - (documents.embedding <=> query_embedding) as similarity
  FROM documents
  WHERE 
    documents.metadata @> filter
    AND 1 - (documents.embedding <=> query_embedding) > match_threshold
  ORDER BY documents.embedding <=> query_embedding
  LIMIT match_count;
$$;
```

### 10.4.3 n8n Workflow Components

```yaml
Milestone_3_Workflow:
  name: "Vector_RAG_Pipeline"
  
  nodes:
    1_processed_document:
      type: "n8n-nodes-base.executeWorkflow"
      workflowId: "milestone_2_output"
    
    2_semantic_chunking:
      type: "n8n-nodes-base.function"
      code: |
        // Intelligent chunking with overlap
        const chunks = [];
        const text = $json.processedContent;
        const chunkSize = 1000;
        const overlap = 200;
        
        for (let i = 0; i < text.length; i += chunkSize - overlap) {
          chunks.push({
            content: text.slice(i, i + chunkSize),
            index: chunks.length,
            start: i,
            end: Math.min(i + chunkSize, text.length)
          });
        }
        
        return chunks;
    
    3_generate_embeddings:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.nomic.ai/v1/embeddings"
        method: "POST"
        sendBody: true
        bodyParameters:
          model: "nomic-embed-text-v1.5"
          input: "{{$json.chunks}}"
          task_type: "search_document"
        options:
          batchSize: 100
          batchInterval: 100
          note: "Can also use Claude embeddings if preferred"
    
    4_quality_scoring:
      type: "n8n-nodes-base.function"
      code: |
        // Calculate chunk quality scores
        return items.map(item => ({
          ...item.json,
          qualityScore: calculateQualityScore(item.json.content),
          semanticDensity: calculateSemanticDensity(item.json.content),
          coherenceScore: calculateCoherence(item.json.content)
        }));
    
    5_supabase_vector_upsert:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        INSERT INTO documents (
          content,
          metadata,
          embedding,
          quality_score,
          semantic_density,
          coherence_score
        ) VALUES (
          '{{$json.content}}',
          '{{$json.metadata}}'::jsonb,
          '{{$json.embedding}}'::vector,
          {{$json.qualityScore}},
          {{$json.semanticDensity}},
          {{$json.coherenceScore}}
        )
        ON CONFLICT (id) DO UPDATE SET
          embedding = EXCLUDED.embedding,
          quality_score = EXCLUDED.quality_score,
          updated_at = NOW();
      options:
        batching:
          enabled: true
          batchSize: 100
    
    6_cache_hot_data:
      type: "n8n-nodes-base.redis"
      parameters:
        operation: "set"
        key: "vector_{{$json.documentId}}"
        value: "{{$json.vectors}}"
        ttl: 3600
    
    7_test_retrieval:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        SELECT * FROM match_documents(
          query_embedding := '{{$json.queryEmbedding}}'::vector,
          match_threshold := 0.7,
          match_count := 10,
          filter := '{{$json.metadataFilter}}'::jsonb
        );
```

### 10.4.4 Testing Checklist

- [ ] Chunk document correctly with semantic overlap
- [ ] Generate embeddings (768 dims)
- [ ] Calculate quality scores for each chunk
- [ ] Store vectors in Supabase with metadata
- [ ] Cache frequently accessed vectors
- [ ] Test semantic search with cosine similarity
- [ ] Verify retrieval accuracy with test queries
- [ ] Monitor embedding generation speed
- [ ] Test metadata filtering with JSONB queries
- [ ] Verify batch upsert performance

### 10.4.5 Success Criteria

- Embeddings generated successfully
- Vectors stored in Supabase pgvector
- Semantic search returns relevant results
- Quality scores provide meaningful ranking
- Cache hit rate >60%
- Retrieval latency <500ms (with HNSW index)
- Batch processing handles 100+ vectors efficiently
- Metadata filtering works seamlessly

## 10.5 Milestone 4: Chat UI for Knowledge Base Query

### 10.5.1 Objectives
- Deploy conversational chat interface
- Connect to Supabase pgvector for RAG queries
- Enable department agent selection
- Implement streaming responses
- Show source citations
- Track costs and performance

### 10.5.2 Chat UI Architecture

```yaml
Chat_UI_Components:
  Frontend:
    - Framework: Gradio or Streamlit
    - Features:
      - Conversational interface
      - Department selector
      - File upload support
      - Citation display
      - Cost tracking
      - Response metrics
  
  Backend:
    - Framework: FastAPI
    - Endpoints:
      - /api/chat/query
      - /api/chat/history
      - /api/agents/list
      - /api/metrics
    
  Integration:
    - Supabase pgvector for retrieval
    - Claude API for generation
    - CrewAI for agent personas
    - mem-agent for context
```

### 10.5.3 n8n Workflow Components

```yaml
Milestone_4_Workflow:
  name: "Chat_UI_RAG_Pipeline"
  
  nodes:
    1_chat_webhook:
      type: "n8n-nodes-base.webhook"
      parameters:
        path: "chat-query"
        method: "POST"
        responseMode: "lastNode"
        rawBody: false
    
    2_retrieve_context:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "http://mac-studio.local:8001/memory/retrieve"
        method: "POST"
        bodyParameters:
          query: "{{$json.question}}"
          conversation_id: "{{$json.conversation_id}}"
          max_tokens: 500
    
    3_vector_search:
      type: "n8n-nodes-base.postgres"
      operation: "executeQuery"
      credentials: "supabase_postgres"
      query: |
        SELECT * FROM match_documents(
          query_embedding := (
            SELECT embedding FROM generate_embedding('{{$json.question}}')
          ),
          match_threshold := 0.7,
          match_count := 5,
          filter := '{"department": "{{$json.department}}"}'::jsonb
        );
    
    4_prepare_prompt:
      type: "n8n-nodes-base.function"
      code: |
        const context = $json.retrieved_chunks.map(chunk => 
          `[Source: ${chunk.metadata.source}]\n${chunk.content}`
        ).join('\n\n');
        
        const systemPrompt = getDepartmentPrompt($json.department);
        
        return {
          system: systemPrompt,
          messages: [
            {
              role: "user",
              content: `Context from knowledge base:\n${context}\n\nUser question: ${$json.question}`
            }
          ]
        };
    
    5_claude_chat_response:
      type: "n8n-nodes-base.httpRequest"
      parameters:
        url: "https://api.anthropic.com/v1/messages"
        method: "POST"
        authentication: "apiKey"
        sendHeaders: true
        headerParameters:
          "x-api-key": "{{$credentials.anthropicApi.apiKey}}"
          "anthropic-version": "2023-06-01"
        sendBody: true
        bodyParameters:
          model: "claude-3-5-sonnet-20241022"
          max_tokens: 2048
          temperature: 0.7
          system: "{{$json.system}}"
          messages: "{{$json.messages}}"
          stream: true
    
    6_format_response:
      type: "n8n-nodes-base.function"
      code: |
        // Format response with citations
        const response = $json.content;
        const citations = $json.retrieved_chunks.map(chunk => ({
          source: chunk.metadata.source,
          page: chunk.metadata.page,
          relevance: chunk.similarity
        }));
        
        return {
          answer: response,
          citations: citations,
          tokens_used: $json.usage,
          cost_usd: calculateCost($json.usage),
          response_time_ms: Date.now() - $json.start_time
        };
    
    7_store_conversation:
      type: "n8n-nodes-base.postgres"
      operation: "insert"
      table: "conversations"
      columns:
        - conversation_id
        - user_id
        - question
        - answer
        - department
        - citations
        - cost_usd
        - created_at
```

### 10.5.4 Implementation Code

```python
# Gradio Chat Interface (chat_ui.py)
import gradio as gr
import requests
from typing import List, Tuple
import json

class ChatInterface:
    def __init__(self, n8n_webhook_url: str):
        self.webhook_url = n8n_webhook_url
        self.conversation_history = []
    
    def query_knowledge_base(
        self, 
        question: str, 
        department: str, 
        history: List[Tuple[str, str]]
    ) -> Tuple[List[Tuple[str, str]], str]:
        """Query the knowledge base via n8n webhook"""
        
        # Call n8n webhook
        response = requests.post(
            self.webhook_url,
            json={
                "question": question,
                "department": department,
                "conversation_id": self.get_conversation_id(),
                "history": history
            }
        )
        
        result = response.json()
        
        # Format response with citations
        answer = result['answer']
        citations = "\n\n**Sources:**\n"
        for cite in result.get('citations', []):
            citations += f"- {cite['source']} (relevance: {cite['relevance']:.2f})\n"
        
        full_response = answer + citations
        
        # Update history
        history.append((question, full_response))
        
        # Format metrics
        metrics = f"""
        **Metrics:**
        - Response time: {result['response_time_ms']}ms
        - Tokens used: {result['tokens_used']}
        - Cost: ${result['cost_usd']:.4f}
        """
        
        return history, metrics
    
    def get_conversation_id(self):
        """Generate or retrieve conversation ID"""
        import uuid
        return str(uuid.uuid4())
    
    def launch(self):
        """Launch Gradio interface"""
        with gr.Blocks(title="Empire Knowledge Base Chat") as interface:
            gr.Markdown("# AI Empire Knowledge Base Query System")
            gr.Markdown("Query your ingested documents with department-specific context")
            
            with gr.Row():
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        value=[],
                        height=500,
                        label="Conversation"
                    )
                    
                    with gr.Row():
                        msg = gr.Textbox(
                            label="Your Question",
                            placeholder="Ask about your documents...",
                            scale=4
                        )
                        department = gr.Dropdown(
                            choices=["General", "Sales", "Marketing", "Finance", "Operations"],
                            value="General",
                            label="Department",
                            scale=1
                        )
                    
                    with gr.Row():
                        submit = gr.Button("Submit", variant="primary")
                        clear = gr.Button("Clear")
                
                with gr.Column(scale=1):
                    metrics = gr.Markdown("**Metrics will appear here**")
                    
                    gr.Markdown("### Quick Actions")
                    example_queries = gr.Examples(
                        examples=[
                            ["What are our key sales strategies?", "Sales"],
                            ["Show me marketing frameworks", "Marketing"],
                            ["What are the financial best practices?", "Finance"],
                            ["List operational workflows", "Operations"]
                        ],
                        inputs=[msg, department]
                    )
            
            # Event handlers
            submit.click(
                fn=self.query_knowledge_base,
                inputs=[msg, department, chatbot],
                outputs=[chatbot, metrics]
            )
            
            msg.submit(
                fn=self.query_knowledge_base,
                inputs=[msg, department, chatbot],
                outputs=[chatbot, metrics]
            )
            
            clear.click(
                fn=lambda: ([], "**Metrics will appear here**"),
                outputs=[chatbot, metrics]
            )
        
        interface.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False
        )

# Deploy on Render
if __name__ == "__main__":
    n8n_webhook = "https://your-n8n-instance.onrender.com/webhook/chat-query"
    chat = ChatInterface(n8n_webhook)
    chat.launch()
```

### 10.5.5 Testing Checklist

- [ ] Deploy Chat UI on Render
- [ ] Test connection to n8n webhook
- [ ] Query single document successfully
- [ ] Test department agent selection
- [ ] Verify source citations display
- [ ] Check response streaming
- [ ] Monitor cost tracking
- [ ] Test conversation history
- [ ] Verify multi-turn conversations
- [ ] Load test with concurrent users

### 10.5.6 Success Criteria

- Chat UI accessible and responsive
- Questions answered accurately from knowledge base
- Citations provided for all answers
- Department context working correctly
- Response time <3 seconds
- Cost tracking accurate
- Conversation history maintained
- Supports 10+ concurrent users

## 10.6 Milestone 5: Universal Content Analysis with CrewAI (ESSENTIAL)

### 10.6.1 Objectives
- Implement CrewAI Content Analyzer Agent (NOT OPTIONAL)
- Extract insights, workflows, and frameworks from courses
- Map content to department applications
- Generate comprehensive documentation
- Build knowledge graph relationships

### 10.6.2 Why CrewAI is ESSENTIAL

**CrewAI is the intelligence layer that:**
- Analyzes ALL ingested content
- Generates course documentation
- Identifies department-specific applications
- Creates implementation roadmaps
- Extracts frameworks and best practices
- **Without it, documents are just stored, not understood**

### 10.6.3 CrewAI Content Analyzer Components

```yaml
CrewAI_Content_Analyzer:
  status: ESSENTIAL
  cost: "$15-20/month"
  deployment: "https://jb-crewai.onrender.com"
  
  primary_agent:
    name: "Content Analyzer"
    role: "Universal content analysis and documentation"
    capabilities:
      - Module-by-module summaries
      - Framework extraction
      - Workflow identification
      - Department mapping
      - Implementation guides
      - Insight extraction
    
  future_agents_v2:
    - Sales Department Agent
    - Marketing Department Agent
    - Finance Department Agent
    - Operations Department Agent
```

#### Node 9: CrewAI Universal Content Analysis

```yaml
CrewAI_Universal_Analysis:
  type: "n8n-nodes-base.httpRequest"
  name: "CrewAI Universal Content Analysis"
  method: "POST"
  url: "https://jb-crewai.onrender.com/run-crew"
  
  body:
    task_type: "universal_content_analysis"
    
    content:
      original_text: "{{ $node['LlamaIndex Response Processor'].json.langExtractPayload.original_content }}"
      chunks: "{{ JSON.stringify($node['LlamaIndex Response Processor'].json.langExtractPayload.chunks) }}"
      metadata: "{{ JSON.stringify($node['LlamaIndex Response Processor'].json.langExtractPayload.document_metadata) }}"
      content_type: "{{ $node['File Type Detection & Routing'].json.contentCategory }}"
      source_url: "{{ $json.source_url || 'direct_upload' }}"
    
    analysis_requirements:
      extract_key_insights: true
      identify_frameworks: true
      extract_workflows: true
      identify_best_practices: true
      map_to_departments: true
      extract_quotes: true
      identify_experts: true
      extract_data_points: true
      generate_implementation_guide: true
    
    agents:
      - role: "insight_extractor"
        goal: "Extract key insights, innovative ideas, and breakthrough concepts from any content"
        backstory: "Expert at identifying valuable nuggets of wisdom from diverse sources"
      
      - role: "workflow_architect"
        goal: "Identify and design implementable workflows and processes from the content"
        backstory: "Specializes in translating ideas into actionable workflows"
      
      - role: "framework_specialist"
        goal: "Extract mental models, frameworks, and methodologies that can be applied"
        backstory: "Deep expertise in identifying reusable patterns across domains"
      
      - role: "knowledge_synthesizer"
        goal: "Connect ideas to existing knowledge and identify relationships"
        backstory: "Expert at building knowledge graphs and identifying connections"
      
      - role: "implementation_strategist"
        goal: "Create practical implementation plans for extracted insights"
        backstory: "Translates theoretical knowledge into executable strategies"
```

[Continue with remaining Universal Content Analysis nodes from original Section 10...]

## 10.7 Milestone 6: Multi-Agent Orchestration

[Keep existing content but ensure CrewAI is marked as ESSENTIAL throughout]

## 10.8 Milestone 7: Cost Tracking and Optimization

### 10.8.1 Objectives
- Implement cost monitoring
- Track API usage
- Optimize routing decisions
- Generate cost reports
- Alert on budget thresholds

### 10.8.2 Updated Cost Tracking for v6.0

```yaml
Milestone_7_Workflow:
  name: "Cost_Optimization_Tracking"
  
  nodes:
    1_cost_interceptor:
      type: "n8n-nodes-base.function"
      description: "Track all API calls for cost tracking"
      code: |
        // Track every API call
        const operation = $json.operation;
        const service = $json.service;
        
        const costs = {
          'claude_api': 0.003 * $json.input_tokens / 1000 + 0.015 * $json.output_tokens / 1000,
          'claude_batch': 0.0003 * $json.input_tokens / 1000 + 0.0015 * $json.output_tokens / 1000,
          'mistral_ocr': 0.01 * $json.pages,
          'soniox': 0.05 * $json.minutes,
          'supabase_vector': 0, // Included in $25/month
          'crewai': 0, // Fixed $15-20/month
          'mem_agent': 0  // Local on Mac Studio
        };
        
        return {
          ...items[0].json,
          cost: costs[service] || 0,
          optimizations: {
            batch_savings: $json.is_batch ? costs['claude_api'] * 0.9 : 0,
            cache_savings: $json.cached_tokens * 0.0015 / 1000
          }
        };
```

### 10.8.3 Success Criteria

- All costs tracked accurately
- Budget alerts functional
- Monthly costs <$165 (updated for v6.0)
- Batch processing achieving 90% savings
- Cache effectiveness >50%

[Continue with remaining milestones 8-14 from original, keeping all content but ensuring no Llama references remain]

## 10.15 Next Steps

After completing all milestones:

1. **Deploy Chat UI** (URGENT)
   - Choose Gradio for quick deployment
   - Connect to existing infrastructure
   - Enable department agent queries

2. **Verify CrewAI Integration**
   - Ensure Content Analyzer is active
   - Test course documentation generation
   - Validate department mapping

3. **Documentation Updates**
   - Update all sections to v6.0
   - Remove outdated references
   - Clarify CrewAI as essential

4. **Performance Optimization**
   - Monitor Claude API usage
   - Optimize batch processing
   - Maximize prompt caching

---

This milestone-based approach ensures systematic implementation and testing of the AI Empire v6.0 system, with the ESSENTIAL Chat UI and CrewAI components properly integrated for a complete, functional knowledge base system.