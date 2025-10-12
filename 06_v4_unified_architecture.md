# 6. Supporting Information & Appendices (Updated v5.0)

## 6.1 Appendix A: Business Rules

### Core Processing Rules (All Versions)

**BR-001:** Files must be processed in order of upload/detection
*Status: Active - All Versions*

**BR-002:** Vector storage must complete before analysis begins
*Status: Active - All Versions*

**BR-003:** Documents with matching hash SHALL skip reprocessing
*Status: Active - All Versions*

**BR-004:** MarkItDown SHALL be primary processor for all supported formats
*Status: Active - All Versions*

**BR-005:** Mistral OCR SHALL only process complex PDFs
*Note: v5.0 - Used sparingly, only when local processing fails*
*Status: Active - All Versions*

**BR-006:** Metadata enrichment SHALL occur before vector storage
*Status: Active - All Versions*

**BR-007:** Contextual embeddings SHALL be optional and configurable
*Note: v5.0 - Generated locally by Llama 70B*
*Status: Active - All Versions*

**BR-008:** SQL database SHALL be source of truth for record state
*Status: Active - All Versions*

**BR-009:** Audit trail SHALL be immutable once written
*Status: Active - All Versions*

**BR-010:** Processing SHALL respect data retention policies
*Status: Active - All Versions*

**BR-011:** Hybrid search SHALL combine vector and keyword results
*Status: Active - All Versions*

**BR-012:** Reranking SHALL be applied to all search results
*Note: v5.0 - Primary local BGE-reranker, Cohere as fallback*
*Status: Enhanced - v5.0*

**BR-013:** Memories SHALL be user-specific
*Note: v5.0 - mem-agent replaces Zep*
*Status: Updated - v5.0*

**BR-014:** Tabular data SHALL be queryable via SQL
*Status: Active - All Versions*

**BR-015:** Web scraping SHALL respect robots.txt
*Status: Active - All Versions*

**BR-016:** Multimodal content SHALL maintain relationships
*Status: Active - All Versions*

**BR-017:** Graph updates SHALL be incremental
*Status: Active - All Versions*

**BR-018:** Agent selection SHALL be explicit
*Status: Active - All Versions*

### Performance Rules (v3.0+)

**BR-019:** Fast track processing SHALL bypass AI calls for simple formats
*Status: Active - v3.1+*

**BR-020:** Cost tracking SHALL update in real-time for all API calls
*Note: v5.0 - Also tracks local processing value*
*Status: Enhanced - v5.0*

**BR-021:** Parallel processing SHALL respect priority queue order
*Note: v5.0 - Up to 10 concurrent workflows*
*Status: Enhanced - v5.0*

**BR-022:** Quality gates SHALL enforce minimum scores before completion
*Status: Active - v3.0+*

**BR-023:** Cache warming SHALL prioritize frequently accessed documents
*Note: v5.0 - 31GB memory cache available*
*Status: Enhanced - v5.0*

### Mac Studio Rules (NEW v5.0)

**BR-024:** Local processing SHALL be prioritized for all operations
*Priority: 98% local target*
*Status: New - v5.0*

**BR-025:** Sensitive documents SHALL NEVER leave Mac Studio
*Documents: Financial, healthcare, legal, PII*
*Status: New - v5.0*

**BR-026:** LLM inference SHALL maintain 32 tokens/second minimum
*Model: Llama 3.3 70B*
*Status: New - v5.0*

**BR-027:** Memory usage SHALL NOT exceed 65GB for models
*Reserve: 31GB for operations and caching*
*Status: New - v5.0*

**BR-028:** Cloud fallback SHALL only occur after local attempts
*Exception: Services with no local alternative (Soniox)*
*Status: New - v5.0*

**BR-029:** Backups SHALL be encrypted client-side before upload
*Encryption: AES-256, zero-knowledge*
*Status: New - v5.0*

**BR-030:** Mac Studio SHALL operate 24/7 with >99.5% uptime
*Monitoring: Continuous health checks*
*Status: New - v5.0*

## 6.2 Appendix B: Technical Stack Summary (v5.0)

### Local Infrastructure (PRIMARY - Mac Studio)

#### Hardware
- **Mac Studio M3 Ultra:** 28-core CPU, 60-core GPU, 32-core Neural Engine
- **Memory:** 96GB unified (800 GB/s bandwidth)
- **Storage:** 1TB+ SSD recommended
- **Network:** 10Gb Ethernet
- **Power:** ~65W average, UPS backup recommended
- **Delivery:** October 14, 2025

#### Local AI Models
- **Primary LLM:** Llama 3.3 70B (35GB, 32 tok/s)
- **Vision Model:** Qwen2.5-VL-7B (5GB)
- **Memory Model:** mem-agent MCP (3GB, <500ms retrieval)
- **Embeddings:** nomic-embed-text (2GB)
- **Reranker:** BGE-reranker (local)

#### Local Software
- **OS:** macOS 15.0+ (Sequoia)
- **Model Server:** Ollama
- **LLM Interface:** Open WebUI
- **API Layer:** LiteLLM
- **MCP Support:** Claude Desktop
- **VPN:** Tailscale
- **Package Manager:** Homebrew
- **Containers:** Docker Desktop

### Cloud Infrastructure (SECONDARY - Minimal)

#### Workflow Orchestration
- **Platform:** n8n (https://jb-n8n.onrender.com)
- **Host:** Render ($15-30/month)
- **Purpose:** Workflow automation, job scheduling
- **Nodes:** Document processing, queue management

#### Document Processing (Selective Cloud Use)
- **Primary:** MarkItDown MCP Server (local)
- **Complex PDFs:** Mistral OCR API (cloud fallback)
- **Audio/Video:** Soniox API (no local alternative)
- **Web Scraping:** Firecrawl API (cloud service)

#### Storage and Databases
- **Primary Storage:** Backblaze B2 (encrypted)
- **Vector Database:** Pinecone ($0-70/month)
- **Graph Database:** LightRAG API (cloud)
- **SQL Database:** Supabase PostgreSQL ($25/month)
- **Audit Trail:** Airtable (optional)
- **Cache L1:** Mac Studio Memory (31GB)
- **Cache L2:** Mac Studio SSD (100GB)

#### Intelligence Services
- **Multi-Agent:** CrewAI (Render, $15-20/month)
- **Backup LLM:** Hyperbolic.ai ($5-10/month, edge cases only)
- **Reranking Fallback:** Cohere API (rarely used)
- **Structured Extraction:** LangExtract (local with Llama)

#### Security and Monitoring
- **Metrics:** Prometheus (local + cloud)
- **Dashboards:** Grafana
- **ML Observability:** Arize Phoenix
- **Testing:** DeepEval
- **Encryption:** FileVault (local), AES-256 (cloud)
- **Authentication:** JWT tokens with RBAC

### Deprecated Services (Historical Reference)

- **Zep:** Replaced by local mem-agent in v5.0
- **OpenAI Embeddings:** Replaced by local nomic-embed
- **Mistral Pixtral:** Replaced by local Qwen2.5-VL
- **Redis Cache:** Replaced by local SSD cache in v5.0
- **Heavy Cloud LLM Usage:** Reduced to <2% in v5.0
- **Mac Mini M4 (v4.0):** Superseded by Mac Studio M3 Ultra

## 6.3 Appendix C: Migration Plans

### Phase 1: v4.0 to v5.0 Migration (October 14, 2025)

#### Day 1: Mac Studio Deployment
1. Unbox and connect Mac Studio M3 Ultra
2. Connect UPS and configure network
3. Enable SSH and Tailscale VPN
4. Install Homebrew and Docker Desktop
5. Install Ollama and pull Llama 3.3 70B
6. Setup Open WebUI and LiteLLM
7. Configure mem-agent MCP
8. Initial testing and validation

#### Week 1: Core Services
1. Pull Qwen2.5-VL-7B vision model
2. Install nomic-embed and BGE-reranker
3. Configure automated backups to B2
4. Setup Claude Desktop with MCP
5. Performance benchmarking (32 tok/s target)
6. Security hardening

#### Week 2: Integration
1. Update n8n workflows for Mac Studio
2. Configure smart routing (98% local)
3. Test privacy-based document routing
4. Integrate with minimal cloud services
5. Setup monitoring and alerting
6. Cost tracking implementation

#### Week 3-4: Optimization
1. Fine-tune model parameters
2. Optimize memory allocation (65GB/31GB split)
3. Cache strategy refinement
4. Performance optimization
5. Disaster recovery testing
6. Documentation and training
7. Go-live preparation

### Phase 2: Data Migration (v4.0 → v5.0)

#### Mac Mini to Mac Studio Migration
1. Export all data from Mac Mini M4
2. Transfer to Mac Studio M3 Ultra (4x memory)
3. Expand model capabilities (70B vs previous limits)
4. Optimize for 96GB memory architecture

#### Memory Migration
1. Export memories from existing system
2. Convert to Markdown format if needed
3. Import to local mem-agent
4. Validate memory retrieval (<100ms)
5. Test context preservation

#### Embedding Migration
1. Identify documents needing re-embedding
2. Batch process with local nomic-embed
3. Update vector database
4. Validate search quality
5. Remove old cloud-based embeddings

### Historical Migration Plans (Reference)

#### v2.9 to v3.0 (Completed)
- Infrastructure setup with parallel processing
- 3-tier cache implementation
- Quality monitoring deployment

#### v3.0 to v3.1 (Completed)
- Fast track implementation
- Cost management system
- Intelligent error recovery

## 6.4 Appendix D: Complete Glossary (v5.0)

### Core Terms

| Term | Definition |
|------|------------|
| **Agent** | Autonomous AI entity (CrewAI or dual architecture) |
| **Chunk** | Segment of document for processing |
| **Contextual Embedding** | Embedding with added context (generated locally in v5.0) |
| **Diarization** | Speaker identification in audio |
| **Embedding** | Vector representation of text |
| **Hash** | Unique fingerprint of content (SHA-256) |
| **Hybrid RAG** | Combined retrieval (vector + keyword + graph) |
| **Knowledge Graph** | Graph-based knowledge via LightRAG |
| **Namespace** | Logical grouping in vector database |
| **OCR** | Optical Character Recognition |
| **Pipeline** | Sequential processing workflow |
| **Reranking** | Re-ordering search results (local BGE primary) |
| **Session** | Correlated processing instance |
| **Vector** | Numerical representation for similarity |

### v5.0 Mac Studio Terms

| Term | Definition |
|------|------------|
| **Mac Studio** | Apple M3 Ultra workstation (96GB), primary engine |
| **Llama 3.3 70B** | Primary local LLM, GPT-4 quality, 32 tok/s |
| **Qwen2.5-VL** | Local vision-language model (7B) |
| **mem-agent** | Local memory management via MCP (3GB) |
| **nomic-embed** | Local embedding generation (2GB) |
| **BGE-reranker** | Local search reranking |
| **Ollama** | Local LLM serving platform |
| **Open WebUI** | Web interface for local LLMs |
| **LiteLLM** | API compatibility layer |
| **GGUF** | Efficient local model format |
| **Metal** | Apple GPU acceleration framework |
| **Unified Memory** | Shared CPU/GPU memory (96GB) |
| **Neural Engine** | Apple ML acceleration (32 cores) |
| **FileVault** | macOS full-disk encryption |
| **Tailscale** | Secure VPN for remote access |
| **tok/s** | Tokens per second (32 target) |
| **Local-First** | 98% processing on Mac Studio |
| **Zero-Knowledge** | Provider cannot decrypt backups |

### Performance Terms (v3.0+)

| Term | Definition |
|------|------------|
| **Fast Track** | Streamlined processing (70% faster) |
| **Circuit Breaker** | Failure prevention pattern |
| **Dead Letter Queue** | Failed message storage |
| **Semantic Chunking** | Context-aware segmentation |
| **Worker** | n8n processing node (v5.0) |
| **Cache Tier** | L1 (31GB RAM), L2 (SSD), L3 (B2) |
| **Quality Gate** | Automated validation (0.75 min) |

### Video Processing Terms (v3.4+)

| Term | Definition |
|------|------------|
| **FFmpeg** | Multimedia processing framework |
| **Frame Extraction** | Capturing images from video |
| **Multimodal Embedding** | Combined text/visual/audio vectors |
| **Temporal Query** | Time-based search in video |
| **Batch Processing** | Multiple files together (10+ parallel) |
| **Parent/Child Execution** | Batch job hierarchy |
| **Qwen-VL Analysis** | Local vision processing (v5.0) |

### Cost Terms (v5.0)

| Term | Definition |
|------|------------|
| **API Replacement Value** | Cloud cost saved (~$200-300/mo) |
| **Local Processing Ratio** | 98% target on Mac Studio |
| **ROI Period** | 20 months payback on $3,999 investment |
| **Edge Cases** | <2% requiring cloud processing |
| **Monthly Target** | $100-195 (down from $500) |

## 6.5 Appendix E: API Specifications

### 6.5.1 Core Processing Endpoints

```yaml
openapi: 3.1.0
info:
  title: AI Empire File Processing System API
  version: 5.0.0
  description: Local-first AI with Mac Studio M3 Ultra

paths:
  /api/v1/process/document:
    post:
      summary: Process document (98% local)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [file_content, filename]
              properties:
                file_content:
                  type: string
                  format: base64
                filename:
                  type: string
                processing_location:
                  type: string
                  enum: [local, cloud, auto]
                  default: auto
                sensitive:
                  type: boolean
                  default: false
                  description: Force Mac Studio only
      responses:
        200:
          description: Processing successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  document_id:
                    type: string
                  processing_location:
                    type: string
                    enum: [mac_studio, cloud]
                  processing_time_ms:
                    type: integer
                  cost_saved:
                    type: number
                  tokens_generated:
                    type: integer
```

### 6.5.2 Local AI Endpoints (v5.0)

```yaml
  /api/v1/local/inference:
    post:
      summary: Local Llama 70B inference (32 tok/s)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [prompt]
              properties:
                prompt:
                  type: string
                model:
                  type: string
                  enum: [llama-70b, qwen-vl-7b]
                  default: llama-70b
                max_tokens:
                  type: integer
                  default: 2000
      responses:
        200:
          description: Inference complete
          content:
            application/json:
              schema:
                type: object
                properties:
                  response:
                    type: string
                  tokens_per_second:
                    type: number
                    minimum: 32

  /api/v1/local/vision:
    post:
      summary: Local Qwen-VL vision analysis
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [image]
              properties:
                image:
                  type: string
                  format: base64
                query:
                  type: string

  /api/v1/local/embed:
    post:
      summary: Generate embeddings locally (nomic-embed)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [texts]
              properties:
                texts:
                  type: array
                  items:
                    type: string
```

### 6.5.3 Memory Management (mem-agent)

```yaml
  /api/v1/memory/store:
    post:
      summary: Store memory locally (<100ms)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [user_id, content]
              properties:
                user_id:
                  type: string
                content:
                  type: string
                  description: Markdown format

  /api/v1/memory/retrieve:
    post:
      summary: Retrieve memories (<100ms typical)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [user_id, query]
              properties:
                user_id:
                  type: string
                query:
                  type: string
                limit:
                  type: integer
                  default: 10
```

### 6.5.4 Monitoring & Cost Endpoints

```yaml
  /api/v1/monitor/health:
    get:
      summary: System health (Mac Studio + Cloud)
      responses:
        200:
          description: System healthy
          content:
            application/json:
              schema:
                type: object
                properties:
                  mac_studio:
                    type: object
                    properties:
                      cpu_usage:
                        type: number
                        maximum: 0.60
                      memory_used_gb:
                        type: number
                        maximum: 65
                      gpu_usage:
                        type: number
                        maximum: 0.70
                      tokens_per_second:
                        type: number
                        minimum: 32
                      models_loaded:
                        type: array

  /api/v1/cost/current:
    get:
      summary: Cost tracking & ROI
      responses:
        200:
          description: Cost data
          content:
            application/json:
              schema:
                type: object
                properties:
                  monthly_spend:
                    type: number
                    maximum: 195
                  local_processing_ratio:
                    type: number
                    minimum: 0.98
                  api_replacement_value:
                    type: number
                    description: Savings vs cloud
                  mac_studio_roi:
                    type: object
                    properties:
                      months_to_payback:
                        type: number
                      total_saved:
                        type: number
```

## 6.6 Appendix F: Testing Requirements (v5.0)

### Unit Testing
- **TR-001:** 80% code coverage minimum
- **TR-002:** All endpoints tested
- **TR-003:** Error paths validated
- **TR-004:** Mock external services

### Mac Studio Testing (v5.0)
- **TR-013:** Validate 32 tok/s for Llama 70B
- **TR-014:** Test Qwen-VL vision processing
- **TR-015:** Verify mem-agent <100ms retrieval
- **TR-016:** Test local embeddings generation
- **TR-017:** Validate 98% local processing ratio
- **TR-018:** Test model switching under load
- **TR-019:** Verify GPU utilization <70%
- **TR-020:** Test 24/7 operation stability

### Performance Testing
- **TR-021:** Load test 500 documents/day
- **TR-022:** Stress test with 300MB files
- **TR-023:** Validate response times
- **TR-024:** Test disaster recovery (4-hour RTO)
- **TR-025:** Verify 80% cache hit rate
- **TR-026:** Test concurrent workflows (10+)

### Security Testing
- **TR-027:** Validate zero-knowledge encryption
- **TR-028:** Test FileVault encryption
- **TR-029:** Verify Tailscale VPN security
- **TR-030:** Test sensitive document routing
- **TR-031:** Validate client-side encryption

## 6.7 Appendix G: Monitoring (v5.0)

### Metrics to Monitor

| Metric | Threshold | Alert | v5.0 Note |
|--------|-----------|-------|-----------|
| CPU (Mac Studio) | >60% | Warning | 28 cores |
| Memory Usage | >70% | Warning | 96GB total |
| GPU Usage | >70% | Warning | 60-core GPU |
| LLM Speed | <25 tok/s | Critical | Target: 32 |
| Local % | <95% | Warning | Target: 98% |
| Queue | >50 | Warning | 10 parallel |
| Cache Hit | <80% | Warning | 31GB cache |
| Daily Cost | >$6.50 | Warning | $195/mo max |
| Model Load | >30s | Warning | Ollama |

### Dashboards

1. **Mac Studio Dashboard**
   - Resource utilization
   - Model performance (tok/s)
   - Temperature/power
   - Network throughput

2. **Cost & ROI Dashboard**
   - Real-time costs
   - Savings generated
   - ROI progress (20 mo target)
   - Local vs cloud ratio

3. **Performance Dashboard**
   - Response times
   - Cache hit rates (80%+)
   - Token generation speed
   - Processing throughput

## 6.8 Appendix H: Configuration (v5.0)

```yaml
ai_empire_v5_config:
  # Mac Studio Configuration (PRIMARY)
  mac_studio:
    hardware:
      model: m3_ultra
      memory_gb: 96
      model_allocation_gb: 65
      cache_allocation_gb: 31
    
    models:
      llama_70b:
        path: /models/llama-3.3-70b.gguf
        memory_gb: 35
        target_speed: 32
      qwen_vl:
        path: /models/qwen2.5-vl-7b.gguf
        memory_gb: 5
      mem_agent:
        memory_gb: 3
        retrieval_target_ms: 100
      nomic_embed:
        memory_gb: 2
      bge_reranker:
        memory_gb: 1
    
    services:
      ollama:
        port: 11434
      open_webui:
        port: 3000
      litellm:
        port: 8000
      tailscale:
        enabled: true
    
    backup:
      provider: backblaze_b2
      encryption: aes256_client_side
      frequency: continuous
      zero_knowledge: true
  
  # Cloud Services (MINIMAL)
  cloud_services:
    render:
      n8n:
        cost_monthly: 15-30
      crewai:
        cost_monthly: 15-20
    
    databases:
      pinecone:
        cost_monthly: 0-70
      supabase:
        cost_monthly: 25
    
    ai_services:
      hyperbolic:
        usage: edge_cases_only
        max_monthly: 10
      mistral_ocr:
        usage: complex_pdfs
        cost_monthly: 20
      soniox:
        usage: transcription
        cost_monthly: 10-20
  
  # Cost Management
  cost_targets:
    monthly_budget: 195
    local_processing_target: 0.98
    alert_thresholds:
      - level: info
        amount: 100
      - level: warning
        amount: 150
      - level: critical
        amount: 180
      - level: maximum
        amount: 195
```

## 6.9 Appendix I: Disaster Recovery (v5.0)

### Mac Studio Failure
1. **Detection:** Health checks fail
2. **Response:** Switch to cloud-only (temporary)
3. **Recovery:**
   - Order replacement (1-2 days)
   - Restore from B2 backups
   - Pull models from Ollama
   - Restore mem-agent
   - Resume operations
4. **Timeline:** 4-6 hours post-hardware
5. **Data Loss:** Maximum 1 hour

### Backup Strategy
- **Real-time:** Document changes
- **5 minutes:** Memory updates
- **Hourly:** Database snapshots
- **Daily:** Full system backup
- **Weekly:** Archive creation

### Testing
- **Monthly:** Backup integrity
- **Quarterly:** Full DR drill
- **Annual:** Complete rebuild

## 6.10 Appendix J: Performance Benchmarks

| Metric | v4.0 | v5.0 | Change |
|--------|------|------|--------|
| Hardware | Mac Mini 24GB | Mac Studio 96GB | 4x RAM |
| LLM Speed | Variable | 32 tok/s | Consistent |
| Local % | 50% | 98% | 96% increase |
| Daily Docs | 200 | 500+ | 150% up |
| Workflows | 5 | 10 | 100% up |
| Cache | 8GB | 31GB | 287% up |
| Cost/mo | $125-255 | $100-195 | 40% down |
| Vision | Cloud | Local | 100% local |
| Embeddings | Cloud | Local | 100% local |
| Memory | 500ms | <100ms | 80% faster |
| ROI Period | N/A | 20 months | Quantified |

## 6.11 Historical Reference: v4.0 Architecture

The v4.0 architecture (superseded by v5.0) featured:
- Mac Mini M4 with 24GB RAM (replaced by Mac Studio 96GB)
- 50% local processing (now 98%)
- Higher cloud dependency (now minimal)
- $125-255/month costs (now $100-195)

Key lessons learned:
- Memory constraints limited local model capability
- Mac Studio investment enables true local-first approach
- 98% local processing achievable with proper hardware
- ROI justifiable at 20-month payback period

## 6.12 Video & Orchestration Configuration

### Video Processing (v3.4+)
```yaml
video_processing:
  enabled: true
  ffmpeg_path: /usr/bin/ffmpeg
  frame_extraction:
    interval_seconds: 10
    analyze_locally: true  # Qwen-VL
  audio_extraction:
    soniox_diarization: true
```

### Orchestrator (n8n)
```yaml
orchestrator:
  enabled: true
  n8n_url: https://jb-n8n.onrender.com
  b2_monitoring:
    poll_interval: 30s
    folders:
      - incoming/documents
      - incoming/videos
  execution_tracking:
    parent_table: queue_parent_executions
    child_table: queue_child_executions
```

### Queue Mode
```yaml
queue_mode:
  enabled: true
  activation_threshold: 10
  worker_pool:
    min_workers: 1
    max_workers: 10  # v5.0 increased
```

## 6.13 Interactive Testing Interface

### RAG Testing Interface Requirements

**ITR-001:** Interactive chat interface for testing
- Gradio/Streamlit web UI
- Document Q&A testing
- Multi-modal queries (Qwen-VL)
- Memory persistence testing (mem-agent)
- Performance benchmarking
- Cost tracking validation

**ITR-002:** Testing modes:
- Single document Q&A
- Cross-document synthesis  
- Visual content queries (local)
- SQL data queries
- Memory recall testing

**ITR-003:** Metrics display:
- Query processing time
- Chunks retrieved
- Reranking scores (BGE local)
- Cache hit status
- Tokens per second
- Local vs cloud routing

## 6.14 Compliance & Standards

### Data Protection
- **GDPR:** Full compliance
- **SOC 2:** Security controls
- **HIPAA:** Capable with configuration
- **Zero-Knowledge:** Complete encryption
- **Data Sovereignty:** 98% local

### Technical Standards
- **IEEE 830-1998:** Requirements spec
- **OpenAPI 3.1:** API documentation
- **ISO 8601:** Datetime formats
- **REST:** API architecture
- **OAuth 2.0:** Authentication

## 6.15 Known Limitations

### Mac Studio Limitations
| Limitation | Impact | Workaround |
|------------|--------|------------|
| Single point | Down if fails | Cloud fallback |
| 96GB ceiling | Model limits | Efficient selection |
| No local transcription | Soniox cost | Accept $10-20/mo |

### Cloud Dependencies
| Service | Why Needed | Monthly Cost |
|---------|------------|--------------|
| Soniox | No local alternative | $10-20 |
| Pinecone | Vector storage | $0-70 |
| n8n | Orchestration | $15-30 |
| CrewAI | Multi-agent | $15-20 |

## 6.16 Future Roadmap

### v5.1 Planned
- Local transcription evaluation
- Mac Studio cluster support
- Enhanced vision capabilities
- Streaming inference
- Mobile interface

### v5.2 Planned
- Distributed Mac Studios
- Local vector database
- Real-time collaboration
- Advanced video processing
- Custom model fine-tuning

### Under Consideration
- Apple Intelligence integration
- Multi-language expansion
- Federated learning
- Edge deployment
- Blockchain audit trail