# 9. Orchestrator and Scheduler Requirements

## V7.2 Production Orchestration Architecture

**Version 7.2 implements production-grade orchestration with FastAPI + Celery:**

### V7.2 NEW - Production Orchestration (8 Milestones)
- **FastAPI Backend:** Async REST + WebSocket API for document intake and queries
- **Celery Task Queue:** Distributed async processing with Redis broker
- **Query Type Detection:** Classify queries as semantic, relational, or hybrid
- **Vector → Graph Router:** Route relational queries to Neo4j (dev) or PostgreSQL graph (production)
- **Interface Selector:** WebSocket Chat UI for end-users, Neo4j MCP for developers
- **Bi-directional Sync Orchestration:** Automatic Supabase ↔ Neo4j synchronization (dev environment)
- **Cypher Generation:** Natural language → Cypher via Claude Sonnet (Neo4j MCP)
- **Hybrid Result Merging:** Combine vector semantic results with graph relationship results
- **Production Memory:** PostgreSQL graph tables (user_memory_nodes/edges) NOT Graphiti MCP
- **Development Memory:** Graphiti MCP with Neo4j for testing only

### V7.3 Orchestration Improvements (ENHANCED)
- **Local Embedding Generation:** BGE-M3 via Ollama with <10ms latency, zero API costs
- **Query Expansion Sub-Workflow:** Claude Haiku generates 4-5 variations in parallel
- **Hybrid Search Orchestration:** Dynamic switching between dense, sparse, ILIKE, fuzzy search
- **BGE-Reranker Integration:** 10-20ms local reranking in orchestration flow
- **Adaptive Chunking Workflow:** Document-type detection and routing
- **Semantic Cache Checking:** Tiered threshold evaluation (0.98+/0.93-0.97/0.88-0.92)
- **LightRAG Graph Integration:** Knowledge graph queries enhanced with Neo4j
- **Error Recovery:** Automatic fallback to LlamaCloud/LlamaParse if OCR needed

---

## 9.0 Orchestration Architecture (v7.2 - Production + Development)

### 9.0.1 Dual-Environment Orchestration

**Production Environment (Cloud Services):**
- **FastAPI Backend:** Async REST + WebSocket APIs on Render
- **Celery Workers:** Distributed task processing with Redis broker
- **PostgreSQL Graph Memory:** Production user memory (user_memory_nodes/edges in Supabase)
- **WebSocket Chat:** Real-time streaming with token-by-token responses
- **Prometheus + Grafana:** Production monitoring and alerting
- **Horizontal Scaling:** Multiple Celery workers for high throughput

**Development Environment (Mac Studio):**
- **Local Testing:** Ollama BGE-M3 embeddings (zero cost)
- **Neo4j Graph DB:** PRODUCTION graph database (self-hosted on Mac Studio Docker, saves $100+/month vs cloud)
- **Graphiti MCP:** Development-only memory testing (NOT production)
- **Neo4j MCP Server:** PRODUCTION access via Claude Desktop/Code (natural language graph queries)
- **Local Models:** BGE-M3, BGE-Reranker-v2 for development testing
- **Offline Capability:** Complete cloud independence for development

### 9.0.2 Mac Studio Resource Orchestration (Development Only)

**Resource Allocation:**
- **60-core GPU** scheduling for parallel development tasks
- **32-core Neural Engine** for ML-accelerated testing
- **96GB memory** allocation management
- **800 GB/s bandwidth** optimization
- **Development models:** BGE-M3, BGE-Reranker-v2 via Ollama
- **Neo4j (PRODUCTION):** Graph database for knowledge graphs (~10GB)
- **Graphiti MCP (DEV ONLY):** Development/testing memory tool (NOT production, uses Neo4j for testing)

## 9.1 Workflow Orchestration

### 9.1.1 Production Task Processing (v7.2)

**OCR-001: Celery Task Queue (Production)**
- **Distributed async processing** with Celery workers on Render
- **Redis broker** for task queue management
- **Result backend** for task status tracking
- **Parallel processing** of documents and queries
- **Horizontal scaling** with multiple workers
- **Retry mechanisms** for failed tasks
- **Task prioritization** and routing
- **Infrastructure as Code** deployment

**OCR-001B: Development Workflow Testing**
- Local workflow testing on Mac Studio
- Integration testing with Graphiti MCP (dev only)
- Model performance testing with local embeddings
- Neo4j query testing via MCP server

**OCR-002: Execution Control (v7.2 Production)**
- **FastAPI endpoints** for manual triggers
- **Celery beat** for scheduled execution
- **Event-based triggers** via Redis pub/sub
- **Webhook triggers** through FastAPI
- **WebSocket connections** for real-time updates
- **Production API** authentication and authorization
- **Development testing** on Mac Studio with local models

### 9.1.2 Process Orchestration

**OCR-003: Complex Workflows**
- Multi-step processing pipelines
- Conditional branching
- Parallel execution paths (10+ on Mac Studio)
- Error handling flows
- Retry mechanisms
- **Local fallback** for cloud failures

**OCR-004: Data Flow Management (v7.2)**
- Data transformation between Celery tasks
- Variable passing via Redis backend
- **Production:** State management in PostgreSQL graph tables (user_memory_nodes/edges)
- **Development:** State management in Graphiti MCP (testing only)
- Result aggregation across distributed workers
- Stream processing via WebSocket
- **Production memory:** PostgreSQL NOT Graphiti MCP

### 9.1.3 Hybrid Orchestration Architecture (NEW)

**OCR-017: Mac Studio Local Orchestration (NEW)**
- Local workflow engine on Mac Studio
- Direct model invocation (Llama 3.3, Qwen2.5-VL)
- File system monitoring for triggers
- Local API endpoints via LiteLLM
- **Complete offline capability**
- **<100ms workflow initiation**

**OCR-018: Privacy-Based Workflow Routing (NEW)**
- **Automatic PII detection** in workflow data
- **Sensitive data stays local** on Mac Studio
- **Healthcare workflows** never leave hardware
- **Financial data** processed locally only
- **Audit trail** for compliance
- **HIPAA/GDPR compliant** routing

## 9.2 Task Scheduling

### 9.2.1 Intelligent Scheduling

**SCR-001: Priority-Based Scheduling**
- Task priority levels (1-5)
- SLA-aware scheduling
- Deadline-based ordering
- Fair scheduling algorithm
- Starvation prevention
- **Local task preference** for privacy

**SCR-002: Resource-Aware Scheduling (Mac Studio Enhanced)**
- **GPU availability** checking (60 cores)
- **Neural Engine** load monitoring
- **Memory availability** (96GB total)
- API rate limit awareness
- Cost-optimized scheduling
- Load balancing between local and cloud
- **Model loading optimization**

### 9.2.2 Advanced Scheduling Features

**SCR-003: Cron-Based Scheduling**
- Standard cron expressions
- Extended cron syntax
- Timezone support
- Holiday calendars
- Business hours awareness
- **Local-only schedules** for sensitive tasks

**SCR-004: Dynamic Scheduling**
- Event-driven scheduling
- Dependency-based execution
- Conditional scheduling
- Adaptive scheduling
- Predictive scheduling
- **Cost-aware scheduling** based on budget

### 9.2.3 Mac Studio Resource Scheduling (NEW)

**SCR-005: GPU Task Scheduling (NEW)**
- 60-core GPU allocation
- Parallel task distribution
- GPU memory management
- Priority-based GPU access
- **10+ concurrent GPU tasks**
- **Real-time GPU monitoring**

**SCR-006: Neural Engine Scheduling (NEW)**
- 32-core Neural Engine allocation
- ML task prioritization
- Power-efficient scheduling
- CoreML optimization
- **50% power savings** for ML tasks
- **Automatic task migration** to Neural Engine

**SCR-007: Cost-Aware Scheduling (NEW)**
- **Real-time cost tracking** per workflow
- **Budget enforcement** ($100-195/month target)
- **Local-first preference** to minimize costs
- **API cost predictions** before execution
- **Cost alerts** at 80% threshold
- **Monthly cost reports** per workflow type

## 9.3 Multi-Agent Coordination

### 9.3.1 CrewAI Integration (Hybrid Mode)

**OCR-005: Agent Management (Local and Cloud)**
- Agent pool management (cloud via Render)
- **Local agent execution** on Mac Studio
- Dynamic agent creation
- Agent lifecycle management
- Resource allocation
- Performance monitoring
- **Offline agent capability**

**OCR-006: Task Distribution (v7.2)**
- Capability-based routing in Celery
- Load-balanced distribution across workers
- Task priority and affinity-based assignment
- Worker specialization (document processing, embeddings, queries)
- **Production:** Context preservation in PostgreSQL graph
- **Development:** Context in Graphiti MCP (testing only)
- **Memory architecture:** PostgreSQL for production, Graphiti for dev only

### 9.3.2 Agent Communication

**OCR-007: Inter-Agent Messaging**
- Direct agent communication
- Broadcast messaging
- Event publication
- State synchronization
- Result sharing
- **Local-only messaging** for sensitive data

**OCR-008: Coordination Patterns**
- Sequential processing
- Parallel processing (10+ agents locally)
- Pipeline patterns
- Map-reduce patterns
- Consensus protocols
- **Hybrid execution** patterns

### 9.3.3 Local Model Coordination (NEW)

**OCR-019: Graph Memory Workflow State (v7.2)**
- **Production:** PostgreSQL graph tables for persistent workflow context
- **Development:** Graphiti MCP for testing workflow memory (NOT production)
- Cross-workflow memory sharing via graph relationships
- User preference learning in user_memory_nodes
- Historical execution patterns in user_memory_edges
- **<500ms state retrieval** from PostgreSQL
- **Production memory:** PostgreSQL user_memory_nodes/edges ONLY

**OCR-020: Local Model Orchestration (Mac Studio)**
- **BGE-M3** embedding generation via Ollama (development testing)
- **BGE-Reranker-v2** local reranking (development testing)
- **Neo4j** graph queries (PRODUCTION - knowledge graphs, entity relationships)
- **Graphiti MCP** memory testing (development only, NOT production)
- **Zero-cost** local model inference for development
- **Production architecture:** Neo4j for graphs, PostgreSQL for vectors/data, both work together

## 9.4 Monitoring and Management

### 9.4.1 Execution Monitoring

**OCR-009: Real-Time Monitoring (Enhanced)**
- Workflow execution status
- Task progress tracking
- **Mac Studio resource utilization**
- Performance metrics
- Error tracking
- **Local vs cloud execution** metrics
- **Cost per workflow** tracking

**OCR-010: Historical Analysis**
- Execution history
- Performance trends
- Success/failure rates
- Resource consumption
- Cost analysis
- **API savings tracking** ($200-300/month)
- **Local processing percentage** (target: 98%)

### 9.4.2 Management Features

**OCR-011: Workflow Control**
- Start/stop/pause workflows
- Dynamic reconfiguration
- Hot deployment
- Rollback capability
- A/B testing support
- **Offline mode toggle**
- **Privacy mode activation**

**OCR-012: Debugging and Testing**
- Step-through debugging
- Breakpoint support
- Test data injection
- Simulation mode
- Performance profiling
- **Local execution testing**
- **Cost simulation** before execution

## 9.5 Integration Requirements

### 9.5.1 External System Integration

**OCR-013: API Integration (Local-First)**
- REST API support
- GraphQL support
- WebSocket support
- gRPC support
- Custom protocol support
- **Local API server** via LiteLLM
- **Offline API mocking**

**OCR-014: Database Integration (Enhanced)**
- PostgreSQL native support (Supabase)
- Vector database integration (Pinecone)
- **Local SQLite** for offline mode
- Cache integration (Redis)
- Queue integration
- Stream processing
- **Local-first data access**

### 9.5.2 Event Processing

**OCR-015: Event Handling**
- Event ingestion
- Event filtering
- Event transformation
- Event routing
- Event replay
- **Privacy-aware event routing**
- **Local event processing**

**OCR-016: Stream Processing**
- Real-time stream processing
- Windowing operations
- Stream aggregation
- Stream joins
- Backpressure handling
- **GPU-accelerated streams**
- **Local stream processing**

## 9.6 Cost and Performance Optimization (NEW)

### 9.6.1 Cost Management

**OCR-021: Workflow Cost Optimization (NEW)**
- **Real-time cost tracking** per workflow
- **Budget allocation** by workflow type
- **Cost predictions** before execution
- **Local execution preference** (saves $200-300/month)
- **API usage minimization**
- **Monthly cost reports**
- **ROI tracking** for Mac Studio investment

### 9.6.2 Performance Optimization

**OCR-022: Performance Enhancement (NEW)**
- **Local execution:** <100ms latency
- **Cloud execution:** 1-5 second latency
- **Intelligent caching** in 31GB buffer
- **GPU acceleration** for parallel tasks
- **Neural Engine** for ML operations
- **Memory bandwidth** optimization (800 GB/s)
- **10x performance** vs cloud-only

## 9.7 Disaster Recovery Orchestration (NEW)

### 9.7.1 Failover Workflows

**OCR-023: Disaster Recovery Workflows (NEW)**
- **Automatic failover** to local execution
- **Cloud service failure** detection
- **Offline mode** activation
- **Data recovery** workflows
- **Backup triggering** to B2 (v7.2 with intelligent course organization)
- **4-hour RTO** compliance
- **1-hour RPO** maintenance

### 9.7.2 Backup and Recovery

**OCR-024: Backup Orchestration (NEW)**
- **Continuous backup** workflows
- **Zero-knowledge encryption** before upload
- **Incremental backup** scheduling
- **Recovery testing** workflows
- **Quarterly drill** automation
- **GitHub LFS** model backup
- **Infrastructure as Code** deployment

## 9.8 Implementation Requirements

### 9.8.1 Software Dependencies

**Production Orchestration Stack (v7.2):**
- FastAPI backend (Render, $20-30/month)
- Celery workers (Render, $20-30/month)
- Redis broker + cache (Upstash, $10-15/month)
- PostgreSQL with pgvector (Supabase, included in base)
- Prometheus metrics (Render, included)
- Grafana dashboards (Render, included)
- WebSocket support for real-time chat

**Development Stack (Mac Studio):**
- Ollama (BGE-M3, BGE-Reranker-v2)
- Neo4j Docker (FREE)
- Graphiti MCP (development testing only)
- Local testing infrastructure

### 9.8.2 Hardware Utilization (Development Environment)

**Mac Studio M3 Ultra (Development Only):**
- 28-core CPU for development testing
- 60-core GPU for embedding generation testing
- 32-core Neural Engine for ML acceleration
- 96GB RAM allocation (~8GB Graphiti, ~10GB Ollama, ~10GB Neo4j)
- 800 GB/s memory bandwidth
- Used for local testing and development ONLY

## 9.9 Orchestration Metrics (v7.2 Production)

### 9.9.1 Performance Targets

| Metric | v7.2 Target | Production Capability |
|--------|-------------|----------------------|
| API Request Latency | <100ms | 50-100ms (FastAPI) |
| Concurrent Celery Tasks | 10+ | 20+ with scaling |
| Document Processing | <60s | 30-55s typical |
| WebSocket Latency | <50ms | 30ms typical |
| Query Response Time | <1s | 500-900ms |
| PostgreSQL Graph Retrieval | <500ms | 200-400ms |
| Cache Hit Rate | 80% | 82% achieved |

### 9.9.2 Cost Comparison (v7.2)

| Service | Cloud-Only | v7.2 Production |
|---------|------------|-----------------|
| Backend API | $50-100/mo | $20-30/mo (FastAPI on Render) |
| Task Processing | $50-100/mo | $20-30/mo (Celery on Render) |
| Message Broker | $30-50/mo | $10-15/mo (Redis Upstash) |
| Database | $50-100/mo | $25/mo (Supabase Pro) |
| Embeddings API | $50-100/mo | $0 (Ollama local dev) |
| Graph Database | $100+/mo | $0 (Neo4j Docker local dev) |
| **Total** | **$330-550/mo** | **$75-100/mo + $0 dev costs** |
| **Savings** | - | **$230-450/month (58-82%)** |

## 9.10 Privacy and Compliance

### 9.10.1 Compliance Features

**Privacy Orchestration:**
- GDPR workflow compliance
- HIPAA data handling
- SOC 2 audit trails
- Zero-knowledge processing
- Client-side encryption
- Local-only sensitive workflows

### 9.10.2 Audit and Monitoring

**Compliance Tracking:**
- Workflow audit logs
- Data lineage tracking
- Access control logs
- Privacy violation detection
- Compliance reporting
- Quarterly audit support