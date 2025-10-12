# 6. Version 4.0 - Unified Private Cloud + Mac Mini Enhancement

## 6.1 Architecture Overview

### 6.1.1 Unified Infrastructure Design

**UAR-001: Hybrid Architecture Paradigm**
- **Priority:** Critical
- **Description:** System shall implement a hybrid cloud-local processing model combining private cloud services with local Mac Mini processing
- **Benefits:** Optimized privacy, reduced latency for memory operations, offline capability
- **Dependencies:** FR-001 through FR-012, PFR-001, CMR-003

The Version 4.0 architecture represents a paradigm shift to a hybrid cloud-local processing model, combining the power of private cloud services with the immediacy and privacy of local Mac Mini processing.

**Core Infrastructure Components:**
```
┌─────────────────────────────────────────────────────────────┐
│                   AI Empire v4.0 Architecture                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐        ┌──────────────────┐         │
│  │   Mac Mini M4     │◀──────│  Claude Desktop   │         │
│  │   Local Hub       │        │  with MCP         │         │
│  │                   │        └──────────────────┘         │
│  │  • mem-agent      │                                      │
│  │  • Local cache    │        ┌──────────────────┐         │
│  │  • Sensitive docs │◀──────│  Private Cloud    │         │
│  │  • Offline mode   │        │  Infrastructure   │         │
│  └──────────────────┘        └──────────────────┘         │
│           ▲                            ▲                    │
│           │                            │                    │
│           └──────────┬─────────────────┘                   │
│                      │                                      │
│              ┌───────▼────────┐                            │
│              │  Smart Router  │                            │
│              │  • Cost-based  │                            │
│              │  • Privacy     │                            │
│              │  • Performance │                            │
│              └────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

**UAR-002: Private Cloud Infrastructure**
- **Priority:** Critical
- **Description:** System shall utilize fully private cloud infrastructure components
- **Components:**
  - n8n (Render) - Workflow orchestration
  - CrewAI (Render) - Multi-agent system
  - Supabase - Private PostgreSQL database
  - Pinecone - Private vector database
  - Backblaze B2 - Private storage (primary + backups)
  - LightRAG API - Knowledge graph
  - Hyperbolic.ai - LLM inference
- **Security:** All services SOC 2 compliant with private VPC networks where available

### 6.1.2 Mac Mini Integration Requirements

**MAC-001: Local Processing Hub**
- **Priority:** Critical
- **Description:** Mac Mini M4 shall serve as the primary local processing hub
- **Primary Purpose:** Run mem-agent MCP for memory management
- **Secondary Uses:**
  - Local model hosting (4B-13B parameters)
  - Caching frequently accessed data
  - Processing sensitive documents locally
  - Offline operation capability
- **Backup:** All data backed up to encrypted Backblaze B2

**MAC-002: Hardware Specifications**
- **Priority:** Critical
- **Description:** Mac Mini shall meet minimum hardware requirements
- **Specifications:**
  - Mac Mini M4 with 24GB unified memory
  - 512GB SSD for local storage
  - 10Gb Ethernet for cloud connectivity
  - 24/7 operational capability
  - Power: 39W active, 7W idle
- **Cooling:** Adequate ventilation and environmental controls

**MAC-003: Software Stack**
- **Priority:** Critical
- **Description:** Mac Mini shall run required software stack
- **Operating System:** macOS 15.0 (Sequoia) or later
- **Runtime Environments:**
  - Python 3.11+ environment
  - Node.js 20.x LTS
  - Docker Desktop 24.0+
- **Core Services:**
  - mem-agent MCP Server
  - Claude Desktop with MCP
  - Local cache management

**MAC-004: Network Requirements**
- **Priority:** High
- **Description:** Mac Mini shall maintain reliable network connectivity
- **Minimum:** 100 Mbps symmetric internet connection
- **Recommended:** 1 Gbps symmetric connection
- **Latency:** <50ms to cloud services
- **VPN:** Capability for secure cloud connections
- **Failover:** Automatic offline mode when connectivity lost

## 6.2 Data Architecture

### 6.2.1 Privacy-First Data Strategy

**UFR-001: Data Classification**
- **Priority:** Critical
- **Description:** System shall classify all data by privacy level
- **Classifications:**
  - **Public Data:** Can be processed in cloud
  - **Sensitive Data:** Must be processed locally first
  - **Confidential Data:** Never leaves Mac Mini
  - **Cached Data:** Encrypted and distributed based on access patterns
- **Routing:** Automatic classification and routing based on content analysis

**UFR-002: Processing Location Strategy**
- **Priority:** Critical
- **Description:** System shall route processing to optimal location
- **Decision Matrix:**
```
Primary Processing Locations:
├── Mac Mini Processing
│   ├── mem-agent context retrieval (<100ms)
│   ├── Sensitive document analysis
│   ├── Real-time memory management
│   ├── Personal financial documents
│   ├── Client confidential data
│   └── Offline capability operations
│
└── Cloud Processing
    ├── Heavy compute tasks (parallel processing)
    ├── Parallel document processing (5x concurrent)
    ├── Team collaboration features
    ├── Large-scale embedding generation
    └── Public API integrations
```

### 6.2.2 Storage Architecture

**UFR-003: Multi-Tier Storage**
- **Priority:** Critical
- **Description:** System shall implement multi-tier storage strategy
- **Storage Matrix:**

| Storage Type | Location | Purpose | Backup | Encryption |
|--------------|----------|---------|--------|------------|
| Markdown Knowledge | Mac Mini | mem-agent access | Backblaze B2 | FileVault + Client-side |
| Vector Embeddings | Pinecone | Semantic search | Export snapshots to B2 | AES-256 at rest |
| Structured Data | Supabase | Relational queries | Built-in + B2 | TLS + AES-256 |
| Raw Files | Backblaze B2 | Primary storage | Cross-region replication | Client-side + AES-256 |
| Cache Layer | Mac Mini | Fast access | Temporary (regenerable) | FileVault |
| Configurations | Mac Mini + Git | System settings | GitHub private repo | Encrypted repository |

**BKP-001: Everything Backed Up Principle**
- **Priority:** Critical
- **Description:** System shall backup all data without exception
- **Backup Scope:**
  - Mac Mini → Backblaze B2 (encrypted)
  - Cloud services → B2 + service backups
  - Configurations → Git repositories
  - Databases → Automated snapshots
- **Verification:** Regular backup integrity checks

## 6.3 Document Processing Pipeline

### 6.3.1 Intelligent Routing

**HYB-001: Smart Document Router**
- **Priority:** Critical
- **Description:** System shall intelligently route documents based on requirements
- **Routing Logic:**
```python
def route_document(document):
    # Priority 1: Security/Privacy
    if document.is_sensitive() or document.contains_pii():
        return "mac_mini_processing_only"
    
    # Priority 2: mem-agent Requirements
    elif document.requires_mem_agent():
        return "mac_mini_first_then_cloud"
    
    # Priority 3: Performance/Cost
    elif document.is_heavy_compute():
        return "cloud_processing_with_cache"
    
    # Priority 4: Offline Capability
    elif not network_available():
        return "mac_mini_queue_for_sync"
    
    # Default: Cost-optimized
    else:
        return "cost_optimized_route"
```

**HYB-002: Processing Pipeline Stages**
- **Priority:** Critical
- **Description:** System shall implement multi-stage processing pipeline
- **Pipeline Stages:**
  1. Document arrives via upload/trigger
  2. Router analyzes requirements (privacy, complexity, format)
  3. Route Sensitive → Mac Mini only, no cloud transmission
  4. Route Complex → Cloud with local caching of results
  5. Route Standard → Cost-optimized path (fast track if eligible)
  6. Results cached appropriately based on access patterns
  7. Backup to B2 with encryption

### 6.3.2 Processing Services Integration

**UFR-006: Service Distribution**
- **Priority:** Critical
- **Description:** System shall distribute processing across local and cloud services

**Local Services (Mac Mini):**
- mem-agent context management (always running)
- MarkItDown MCP for local document conversion
- Sensitive document OCR (Mistral local instance)
- Local model inference (4B-7B models)
- Cache management and cleanup
- Offline operation queue

**Cloud Services (Render/API):**
- n8n workflow orchestration
- CrewAI multi-agent system
- Hyperbolic.ai LLM inference (DeepSeek-V3, Llama-3.3-70B, Qwen2.5-VL-7B, Qwen2.5-3B)
- Mistral OCR for complex PDFs
- Soniox audio/video transcription
- Voyage AI embeddings
- Cohere reranking

## 6.4 Memory Management System

### 6.4.1 mem-agent Integration

**MEM-001: Persistent Memory System**
- **Priority:** Critical
- **Description:** System shall implement mem-agent for persistent memory
- **Specifications:**
  - 4B parameter model running locally on Mac Mini
  - Human-readable memory format (Markdown-based)
  - Context window management (automatic pruning)
  - Real-time memory updates
- **Performance:** <100ms retrieval time, 0-100 relevance scoring
- **Storage:** Local SSD with encrypted backup to B2

**MEM-002: Memory Operations**
- **Priority:** Critical
- **Description:** System shall support full CRUD operations on memory
- **Operations:**
  - **Create:** New memories from processed documents
  - **Read:** Context retrieval for user queries (<100ms)
  - **Update:** Refresh existing memories with new information
  - **Delete:** Remove outdated or incorrect information
- **Validation:** Memory consistency checks and conflict resolution

**MEM-003: Context Optimization**
- **Priority:** High
- **Description:** System shall optimize memory for retrieval efficiency
- **Features:**
  - Local retrieval: <100ms target
  - Relevance scoring: 0-100 scale with threshold filtering
  - Context pruning: Keep most relevant memories within context window
  - Memory compression: Efficient storage without losing context
  - Automatic summarization: Condense long-form memories

**MMR-004: Memory Backup and Sync**
- **Priority:** Critical
- **Description:** System shall continuously backup memory to B2
- **Schedule:**
  - Real-time: Changes synced within 5 minutes
  - Hourly: Incremental backups
  - Daily: Full memory snapshots
- **Encryption:** Client-side encryption before upload

## 6.5 Backup and Recovery

### 6.5.1 Comprehensive Backup Strategy

**BKP-002: Backup Scope Definition**
- **Priority:** Critical
- **Description:** System shall backup all system components
- **Backup Items:**
  - Mac Mini markdown knowledge base
  - mem-agent memories and configuration
  - Local cache (optional, regenerable)
  - System configurations and secrets (encrypted)
  - Cloud service configurations
  - Database snapshots (Supabase)
  - Vector database exports (Pinecone)
  - Workflow definitions (n8n)

**BKP-003: Backup Schedule**
- **Priority:** Critical
- **Description:** System shall follow automated backup schedule
- **Schedule:**
  - **Continuous:** Document changes (real-time sync)
  - **Every 5 min:** Memory updates
  - **Hourly:** Database snapshots
  - **Daily:** Full system backup (all components)
  - **Weekly:** Archive creation for long-term storage
- **Retention:** 30 days rolling, 12 monthly archives

**BKP-004: Encryption Requirements**
- **Priority:** Critical
- **Description:** All backups shall be encrypted before transmission
- **Encryption:**
  - Client-side encryption on Mac Mini before upload
  - User-controlled encryption keys (never transmitted)
  - AES-256 encryption standard
  - Zero-knowledge architecture (Backblaze cannot decrypt)
- **Key Management:** Secure key storage with automated rotation

### 6.5.2 Disaster Recovery

**DRR-001: Recovery Scenarios**
- **Priority:** Critical
- **Description:** System shall support multiple recovery scenarios
- **Scenarios:**

```
Mac Mini Failure:
├── Restore from Backblaze B2
├── Reinstall mem-agent MCP
├── Restore configurations from Git
├── Verify memory integrity
└── Resume operations (4-hour RTO)

Cloud Service Failure:
├── Failover to cached data on Mac Mini
├── Queue operations for retry
├── Use alternative cloud services if available
└── Alert for manual intervention

Complete Disaster Recovery:
├── All data recoverable from Backblaze B2
├── Infrastructure as Code (IaC) for rebuild
├── Documented step-by-step procedures
└── Tested recovery process quarterly
```

**DRR-002: Recovery Metrics**
- **Priority:** Critical
- **Description:** System shall meet recovery objectives
- **RTO (Recovery Time Objective):** 4 hours for Mac Mini failure
- **RPO (Recovery Point Objective):** 1 hour maximum data loss
- **Success Rate:** 99.9% recovery success target
- **Data Integrity:** Zero data loss guarantee for committed data
- **Testing:** Quarterly disaster recovery drills

**DRR-003: Backup Verification**
- **Priority:** High
- **Description:** System shall regularly verify backup integrity
- **Verification:**
  - Daily: Automated integrity checks
  - Weekly: Sample restore tests
  - Monthly: Full restore validation
  - Quarterly: Complete disaster recovery simulation
- **Reporting:** Backup status dashboard with alerting

## 6.6 Security Architecture

### 6.6.1 Defense in Depth

**SR-005: Mac Mini Security**
- **Priority:** Critical
- **Description:** Mac Mini shall implement comprehensive security measures
- **Security Layers:**
  - FileVault encryption enabled (full disk)
  - API key vault implementation (macOS Keychain)
  - mem-agent privacy filters (PII detection and masking)
  - Network isolation options (firewall rules)
  - Regular security updates (automated patching)
  - Physical security (locked location)

**SR-006: Cloud Security**
- **Priority:** Critical
- **Description:** Cloud services shall meet security requirements
- **Security Measures:**
  - TLS 1.3 encryption in transit
  - AES-256 encryption at rest
  - API key authentication with rotation
  - Private VPC networks where available
  - SOC 2 compliant vendors only
  - Regular security audits
  - Intrusion detection and prevention

### 6.6.2 Zero-Knowledge Backup

**SR-007: Encryption Strategy**
- **Priority:** Critical
- **Description:** Backup system shall implement zero-knowledge encryption
- **Implementation:**
  - Client-side encryption before upload
  - User-controlled encryption keys (never leaves Mac Mini)
  - No vendor access to data (true zero-knowledge)
  - Encrypted metadata (filenames, paths, timestamps)
  - Key derivation from user passphrase + hardware binding

**SR-008: Access Control**
- **Priority:** High
- **Description:** System shall implement strict access controls
- **Controls:**
  - Multi-factor authentication for all services
  - Role-based access control (RBAC)
  - Principle of least privilege
  - Regular access reviews and audits
  - Automatic session timeouts
  - IP whitelisting where appropriate

## 6.7 AI Model Distribution

### 6.7.1 Local Models (Mac Mini)

**MMR-007: Model Deployment**
- **Priority:** High
- **Description:** Mac Mini shall host appropriate local models
- **Models:**
  - **mem-agent (4B):** Always running for memory management
  - **Future capacity:** Support for 7B-13B models as needed
  - **Optimization:** Metal Performance Shaders for M4 acceleration
  - **Fallback:** Cloud models when local capacity exceeded

**MMR-008: Model Performance**
- **Priority:** High
- **Description:** Local models shall meet performance requirements
- **Requirements:**
  - Memory retrieval: <100ms (mem-agent)
  - Inference latency: <500ms for 4B models
  - Context window: Up to 8K tokens efficiently
  - GPU utilization: Optimized for M4 Neural Engine
  - Power efficiency: <10W average for model serving

### 6.7.2 Cloud Models (Hyperbolic.ai)

**UFR-007: Model Selection**
- **Priority:** Critical
- **Description:** System shall utilize appropriate cloud models for tasks
- **Model Assignments:**
  - **DeepSeek-V3:** Complex reasoning, multi-step analysis
  - **Llama-3.3-70B:** General analysis tasks, content generation
  - **Qwen2.5-VL-7B:** Visual processing, image understanding
  - **Qwen2.5-3B:** Fast responses, simple queries
- **Routing:** Automatic model selection based on query complexity

**HYB-003: Model Failover**
- **Priority:** High
- **Description:** System shall implement model failover strategy
- **Failover Logic:**
  - Local model unavailable → Use cloud equivalent
  - Cloud API down → Queue for retry, use cached results
  - Rate limit reached → Switch to alternative provider
  - Cost limit approaching → Use smaller/cheaper models

## 6.8 Cost Structure

### 6.8.1 One-Time Costs

**CMR-006: Initial Investment**
- **Priority:** Medium
- **Description:** System requires one-time hardware and setup costs
- **Cost Breakdown:**

| Item | Cost |
|------|------|
| Mac Mini M4 24GB | $899 |
| Initial setup time | 4-6 hours (free/DIY) |
| Software licenses | $0 (all open-source or included) |
| **Total** | **~$899** |

### 6.8.2 Monthly Recurring Costs

**CMR-007: Operating Expenses**
- **Priority:** Critical
- **Description:** System shall maintain monthly costs under $230
- **Cost Matrix:**

| Service | Cost Range | Notes |
|---------|------------|-------|
| Hyperbolic.ai | $20-50 | LLM inference, usage-based |
| Render (n8n + CrewAI) | $30-50 | Two services, always-on |
| Supabase | $25 | Pro plan for production use |
| Pinecone | $0-70 | $0 on free tier, scales with usage |
| Backblaze B2 | $10-20 | Including backup storage |
| Mistral OCR | ~$20 | Usage-based for complex PDFs |
| Soniox | ~$10 | Audio/video transcription |
| Voyage AI | ~$10 | Embedding generation |
| **Total** | **$125-255/month** | Target: <$230/month |

**CMR-008: Cost Optimization**
- **Priority:** High
- **Description:** System shall actively optimize costs
- **Strategies:**
  - Use local processing when possible (reduces API calls)
  - Aggressive caching (40% API cost reduction target)
  - Fast track for simple documents (70% faster, cheaper)
  - Free tier maximization (Pinecone, GitHub, etc.)
  - Monthly cost monitoring and alerts at 80% budget

## 6.9 Implementation Roadmap

### Phase 1: Mac Mini Setup (Week 1)

**UAR-003: Mac Mini Deployment**
- **Priority:** Critical
- **Tasks:**
  1. Hardware installation and configuration
  2. macOS 15.0 setup with FileVault encryption
  3. mem-agent MCP deployment and testing
  4. Local storage setup and organization
  5. Backup automation to B2 configuration
  6. Claude Desktop MCP integration
  7. Initial memory structure creation
- **Success Criteria:** mem-agent responding <100ms, backups working

### Phase 2: Integration (Week 2)

**UAR-004: Cloud Integration**
- **Priority:** Critical
- **Tasks:**
  1. VPN/secure tunnel to cloud services
  2. Update n8n workflows for hybrid routing
  3. Smart routing logic implementation
  4. Test privacy-based routing (sensitive docs stay local)
  5. Failover testing (network disconnection scenarios)
  6. Monitoring and alerting setup
  7. Cost tracking integration
- **Success Criteria:** Seamless hybrid operation, <1% routing errors

### Phase 3: Migration (Week 3)

**UAR-005: Data Migration**
- **Priority:** High
- **Tasks:**
  1. Migrate sensitive documents to Mac Mini
  2. Build local knowledge base with mem-agent
  3. Train mem-agent with historical context
  4. Optimize caching strategies
  5. Performance testing and tuning
  6. Backup verification tests
  7. Documentation updates
- **Success Criteria:** All sensitive data local, backups verified

### Phase 4: Optimization (Week 4)

**UAR-006: Performance Optimization**
- **Priority:** High
- **Tasks:**
  1. Tune performance parameters
  2. Cost routing optimization
  3. Cache hit rate improvements
  4. Backup procedure enhancements
  5. Security hardening
  6. Load testing
  7. Documentation completion
  8. User training (if applicable)
- **Success Criteria:** All performance targets met, <$230/month costs

## 6.10 Key Principles

**UAR-007: Architectural Principles**
- **Priority:** Critical
- **Description:** System shall adhere to core architectural principles

1. **Everything is private** - User owns all data
   - No vendor lock-in
   - Complete data portability
   - Transparent data handling

2. **Everything is backed up** - No single point of failure
   - Continuous backup sync
   - Multiple recovery options
   - Tested recovery procedures

3. **Process where optimal** - Smart routing decisions
   - Mac Mini for memory/sensitive data
   - Cloud for scale and heavy compute
   - Cost-performance balance

4. **Cache intelligently** - Keep frequently used data close
   - >80% cache hit rate target
   - Adaptive TTL based on patterns
   - Tiered caching strategy

5. **Encrypt comprehensively** - Security at all levels
   - At rest: FileVault + AES-256
   - In transit: TLS 1.3
   - Backups: Client-side encryption

## 6.11 Success Metrics

### Technical Metrics

**UAR-008: Performance Targets**
- **Priority:** Critical
- **Metrics:**
  - **Uptime:** >99.5% availability
  - **Performance:** <2s query response (95th percentile)
  - **Memory Retrieval:** <100ms local access
  - **Throughput:** 200+ documents per day
  - **Cache Hit Rate:** >80% for frequent operations
  - **Backup Success:** 100% completion rate

### Business Metrics

**UAR-009: Business Objectives**
- **Priority:** High
- **Metrics:**
  - **Cost Reduction:** 40% vs cloud-only baseline
  - **Processing Speed:** 50% improvement over v2.9
  - **User Satisfaction:** >90% positive feedback
  - **Error Rate:** <1% processing errors
  - **Recovery Time:** <4 hours actual RTO

### Quality Metrics

**UAR-010: Quality Standards**
- **Priority:** High
- **Metrics:**
  - **Processing Accuracy:** >95% correct extraction
  - **Search Relevance:** >85% user satisfaction
  - **Memory Recall:** >90% relevant context retrieval
  - **Context Preservation:** >95% semantic accuracy
  - **Security Compliance:** 100% policy adherence

## 6.12 Integration with Previous Versions

### 6.12.1 Compatibility Requirements

**UAR-011: Backward Compatibility**
- **Priority:** Critical
- **Description:** v4.0 shall maintain compatibility with v2.9-3.1 features
- **Compatibility:**
  - All FR-XXX requirements from v2.9 supported
  - All PFR/QFR/MFR requirements from v3.0 supported
  - All FTR/CMR/ECR/ACR requirements from v3.1 supported
  - No breaking changes to existing workflows
  - Migration path for existing data

### 6.12.2 Feature Enhancement

**UAR-012: Enhanced Capabilities**
- **Priority:** High
- **Description:** v4.0 shall enhance previous features with hybrid capabilities
- **Enhancements:**
  - FR-001 (Document Processing): Now includes local-first routing
  - FR-011 (Memory): Enhanced with mem-agent persistent memory
  - PFR-001 (Parallel Processing): Can use Mac Mini for coordination
  - CMR-003 (Cost Optimization): Enhanced with local processing savings
  - All security requirements: Enhanced with zero-knowledge backup

## 6.13 Operational Procedures

### 6.13.1 Daily Operations

**UAR-013: Daily Operational Tasks**
- **Priority:** Medium
- **Tasks:**
  - Monitor backup completion status
  - Review cost dashboard for anomalies
  - Check mem-agent health metrics
  - Verify cache hit rates
  - Review error logs
  - Monitor disk space usage

### 6.13.2 Weekly Maintenance

**UAR-014: Weekly Maintenance Tasks**
- **Priority:** Medium
- **Tasks:**
  - Backup verification tests
  - Performance metric reviews
  - Security update application
  - Cache cleanup and optimization
  - Log rotation and archival
  - Cost optimization review

### 6.13.3 Monthly Reviews

**UAR-015: Monthly Review Process**
- **Priority:** Medium
- **Tasks:**
  - Comprehensive performance review
  - Cost analysis and optimization
  - Security audit
  - Backup restore testing
  - Capacity planning
  - Documentation updates
  - Roadmap review

## 6.14 Future Enhancements

**UAR-016: Planned Enhancements**
- **Priority:** Low
- **Future Features:**
  - Multiple Mac Mini support for scaling
  - Enhanced AI model hosting (13B+ models)
  - Real-time collaboration features
  - Advanced analytics dashboard
  - Mobile app integration
  - Voice interface for memory retrieval
  - Automated knowledge graph visualization