# 2. Overall Description

## 2.1 Product Perspective

### 2.1.1 System Context

The AI Empire File Processing System operates as a comprehensive middleware platform within the enterprise architecture, now enhanced with hybrid cloud-local processing, mem-agent integration, and comprehensive backup capabilities:

```
┌──────────────────────────────────────────────────────────────────────┐
│                  AI Empire v4.0 Unified Architecture                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────┐         ┌────────────────────┐                │
│  │   Mac Mini M4    │◀──────▶│   Private Cloud    │                │
│  │  Local Hub       │         │   Infrastructure   │                │
│  │  • mem-agent     │         │   • n8n (Render)   │                │
│  │  • Local cache   │         │   • CrewAI         │                │
│  │  • Sensitive     │         │   • Supabase       │                │
│  │    processing    │         │   • Pinecone       │                │
│  └─────────┬───────┘         └────────┬───────────┘                │
│            │                           │                             │
│            └──────────┬────────────────┘                            │
│                       ▼                                              │
│            ┌─────────────────────┐                                  │
│            │   Smart Router      │                                  │
│            │  • Cost-based       │                                  │
│            │  • Privacy-aware    │                                  │
│            │  • Load balanced    │                                  │
│            └─────────┬───────────┘                                  │
│                      │                                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Cache Architecture                        │  │
│  │  L1: Mac Mini RAM (4GB) - <10ms - Hot data                  │  │
│  │  L2: Mac Mini SSD (100GB) - <100ms - Recent data            │  │
│  │  L3: Backblaze B2 - <500ms - Cold storage/backup            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Input Sources       ┌───────────────┐    Processing Services      │
│  ┌──────────────┐   │   Document    │    ┌──────────────┐        │
│  │ Web Upload   │──▶│   Processing  │───▶│ MarkItDown   │        │
│  │ Backblaze B2 │   │   Pipeline     │    │ Mistral OCR  │        │
│  │ YouTube URLs │   │               │    │ Voyage AI    │        │
│  │ Web Scraping │   └───────────────┘    │ Soniox       │        │
│  └──────────────┘                         └──────────────┘        │
│                                                                      │
│  Storage Layer      ┌───────────────────────────┐                  │
│  ┌──────────────┐  │   Hybrid RAG System       │                  │
│  │ Pinecone     │◀─│  • Vector Search          │                  │
│  │ Supabase     │  │  • Graph Traversal        │                  │
│  │ LightRAG     │  │  • SQL Queries            │                  │
│  │ Backblaze B2 │  │  • Cohere Reranking       │                  │
│  └──────────────┘  └───────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────────┘

```

### 2.1.2 System Interfaces

The system integrates with multiple external services and platforms:

**Cloud Services:**
- **Render:** Hosts n8n workflows and CrewAI agents
- **Supabase:** PostgreSQL database and real-time subscriptions
- **Pinecone:** Vector database for semantic search
- **Backblaze B2:** Primary storage and encrypted backup solution
- **Hyperbolic.ai:** LLM inference (DeepSeek-V3, Llama-3.3-70B, Qwen models)

**Local Infrastructure:**
- **Mac Mini M4:** Local processing hub with mem-agent MCP
- **Claude Desktop:** Primary user interface with MCP integration
- **Local file system:** Temporary cache and sensitive document processing

**API Services:**
- **MarkItDown MCP:** Document conversion (40+ formats)
- **Mistral API:** OCR and embeddings
- **Voyage AI:** Advanced embedding generation
- **Soniox API:** Audio/video transcription
- **Firecrawl:** Web content extraction
- **Cohere:** Search result reranking
- **LightRAG API:** Knowledge graph operations

### 2.1.3 Hardware Interfaces

**Mac Mini M4 Specifications:**
- Apple M4 chip with 10-core CPU, 10-core GPU
- 24GB unified memory
- 512GB SSD storage
- 10Gb Ethernet support
- 2x Thunderbolt 4, 2x USB-A, HDMI 2.1
- Power: 39W active, 7W idle
- macOS 15.0 (Sequoia) or later

**Network Requirements:**
- Minimum 100 Mbps symmetric internet connection
- Recommended 1 Gbps symmetric connection
- Low latency (<50ms) to cloud services
- VPN capability for secure cloud connections
- Automatic failover to offline mode

### 2.1.4 Software Interfaces

**Operating Systems:**
- macOS 15.0+ (Mac Mini)
- Ubuntu 24 LTS (Cloud services)

**Runtime Environments:**
- Python 3.11+
- Node.js 20 LTS
- Docker Desktop 24.0+

**Core Frameworks:**
- n8n 1.0+ for workflow automation
- CrewAI 0.5+ for multi-agent orchestration
- LangChain 0.1+ for LLM operations
- mem-agent for persistent memory management

**Database Interfaces:**
- PostgreSQL via Supabase (with connection pooling)
- Vector database via Pinecone API
- Knowledge graph via LightRAG API

### 2.1.5 Communications Interfaces

**Protocols:**
- HTTPS/TLS 1.3 for all API communications
- WebSocket for real-time updates
- gRPC for high-performance service communication
- SSH for secure administration
- MCP (Model Context Protocol) for mem-agent integration

**Data Formats:**
- JSON for API payloads
- Markdown for processed documents
- Protocol Buffers for binary data
- Encrypted blobs for backup storage

## 2.2 Product Functions

The AI Empire system provides the following major functional capabilities:

### 2.2.1 Document Processing Functions

- **Universal Format Conversion:** Convert 40+ document formats to standardized Markdown
- **Intelligent OCR:** Automatic fallback to Mistral OCR for complex PDFs
- **Multimedia Processing:** Extract and transcribe audio/video content
- **Web Content Extraction:** Scrape and process web pages and resources
- **Change Detection:** Hash-based identification of modified content
- **Local Sensitive Processing:** Process confidential documents on Mac Mini only

### 2.2.2 Intelligence Generation Functions

- **Semantic Chunking:** Context-aware document segmentation with quality scoring
- **Embedding Generation:** Create semantic vectors using Voyage AI
- **Metadata Enrichment:** AI-powered classification and tagging
- **Entity Extraction:** Identify and catalog key entities and relationships
- **Knowledge Graph Construction:** Build interconnected knowledge structures
- **Visual Analysis:** Process images and diagrams with Qwen2.5-VL-7B

### 2.2.3 Retrieval and Search Functions

- **Hybrid Search:** Combine vector, keyword, and graph search
- **Cohere Reranking:** Optimize search results for relevance
- **SQL Query Support:** Execute complex queries on structured data
- **Persistent Memory:** Maintain context through mem-agent (<100ms retrieval)
- **Graph Traversal:** Navigate knowledge relationships
- **Smart Caching:** 80%+ cache hit rate for frequent operations

### 2.2.4 Processing Optimization Functions

- **Parallel Processing:** Handle up to 5 documents simultaneously
- **Fast Track Pipeline:** 70% faster processing for simple documents
- **Smart Routing:** Cost, privacy, and complexity-based processing decisions
- **Adaptive Caching:** Dynamic TTL based on usage patterns
- **Query Result Caching:** Store and reuse frequent query results
- **Offline Capability:** Continue operations without cloud access

### 2.2.5 System Management Functions

- **Cost Tracking:** Real-time API usage and cost monitoring
- **Performance Analytics:** Detailed processing metrics and KPIs
- **Error Recovery:** Intelligent retry with circuit breakers
- **Security Monitoring:** Threat detection and audit logging
- **Backup Management:** Automated encrypted backups to B2 (continuous)
- **Disaster Recovery:** 4-hour RTO, 1-hour RPO guaranteed

### 2.2.6 Memory Management Functions (v4.0 NEW)

- **Persistent Context:** mem-agent maintains user-specific context
- **Local Memory Storage:** Markdown-based, human-readable format
- **Fast Retrieval:** <100ms access time for local queries
- **Automatic Backup:** Continuous sync to encrypted B2 storage
- **Context Optimization:** Automatic pruning and relevance scoring
- **Privacy Protection:** Sensitive memories never leave Mac Mini

### 2.2.7 Hybrid Processing Functions (v4.0 NEW)

- **Privacy-Based Routing:** Automatic detection of sensitive content
- **Local-First Processing:** Keep confidential data on Mac Mini
- **Cloud Burst:** Scale to cloud for heavy compute when needed
- **Intelligent Failover:** Automatic offline mode during connectivity loss
- **Cost Optimization:** Route to most cost-effective processing location
- **Performance Balancing:** Optimize for latency vs throughput

## 2.3 User Characteristics

### 2.3.1 Primary Users

**Solopreneurs / Knowledge Workers:**
- Technical Skill Level: Intermediate
- Domain Expertise: High in their specific field
- Usage Pattern: Daily document processing and retrieval
- Key Needs: Fast, accurate, private information extraction
- Budget Conscious: Value $125-230/month operational costs

**System Administrators:**
- Technical Skill Level: Advanced
- Domain Expertise: IT infrastructure and security
- Usage Pattern: System monitoring and maintenance
- Key Needs: Reliability, security, performance visibility
- Comfort with: Command-line tools, infrastructure management

**Data Analysts:**
- Technical Skill Level: Advanced in data tools
- Domain Expertise: Data analysis and visualization
- Usage Pattern: Complex queries and report generation
- Key Needs: SQL access, bulk processing, export capabilities
- Preference for: Structured data access and API integration

### 2.3.2 Secondary Users

**Privacy-Conscious Users:**
- Technical Skill Level: Varies
- Domain Expertise: Privacy and security awareness
- Usage Pattern: Sensitive document processing
- Key Needs: Complete data control, local processing, encryption
- Concern: Data sovereignty and zero-knowledge architecture

**Developers / Integrators:**
- Technical Skill Level: Advanced
- Domain Expertise: API integration and automation
- Usage Pattern: System integration via APIs and webhooks
- Key Needs: Comprehensive API documentation, reliability
- Focus: Building custom workflows and integrations

## 2.4 Constraints

### 2.4.1 Regulatory Constraints

- **GDPR Compliance:** Full data protection and privacy controls
- **SOC 2 Type II:** Security and availability requirements
- **HIPAA Ready:** Healthcare data handling capabilities (if configured)
- **Data Residency:** Support for regional data storage requirements
- **Privacy Regulations:** Compliance with local data protection laws

### 2.4.2 Technical Constraints

- **API Rate Limits:** Respect third-party service limitations
  - Hyperbolic.ai: Rate limits per plan tier
  - Mistral: Usage quotas and rate limiting
  - Cohere: Reranking request limits
  - Pinecone: Query per second limits
- **Storage Quotas:** Manage within Backblaze B2 limits
- **Processing Capacity:** Mac Mini memory constraints (24GB total)
- **Network Bandwidth:** Optimize for available connectivity
- **Model Size Limits:** Local models limited to 7B-13B parameters on M4

### 2.4.3 Business Constraints

- **Budget Limits:** Monthly operational cost target of <$230
  - Stretch up to $255 during peak usage
  - Alerts at 80% of budget threshold
- **Licensing:** Compliance with all third-party licenses
  - Open-source software licenses
  - Commercial service agreements
  - Data processing agreements
- **Support Hours:** 24/7 system availability requirement for critical operations
- **Training Requirements:** Minimal user training needed (Claude Desktop familiar interface)

### 2.4.4 Environmental Constraints

- **Power Requirements:** Reliable power supply for Mac Mini (24/7 operation)
- **Cooling:** Adequate ventilation for M4 chip operation
- **Physical Security:** Secure location for Mac Mini hardware
- **Network Reliability:** Backup connectivity options recommended
- **Space Requirements:** Minimal footprint for Mac Mini deployment

## 2.5 Assumptions and Dependencies

### 2.5.1 Assumptions

- Stable internet connectivity with minimum 100 Mbps bandwidth
- Continued availability of third-party API services at reasonable costs
- Mac Mini hardware reliability and 24/7 operation capability (>99% uptime)
- User compliance with data format requirements and guidelines
- Adequate cooling and power infrastructure for Mac Mini operation
- User has basic technical competency with macOS and command-line tools
- Backblaze B2 storage costs remain stable ($0.005/GB/month)
- Cloud service pricing remains within budget constraints

### 2.5.2 Dependencies

**External Service Dependencies:**
- **Render:** Platform availability for n8n and CrewAI hosting
- **Hyperbolic.ai:** API availability for LLM inference
- **Pinecone:** Service uptime for vector operations (>99.9% SLA)
- **Backblaze B2:** Availability for storage and backup (>99.9% SLA)
- **Supabase:** Database availability and performance
- **Mistral:** OCR and embedding API availability
- **Voyage AI:** Embedding generation service
- **Cohere:** Reranking API availability
- **Soniox:** Audio/video transcription service
- **Firecrawl:** Web scraping API availability
- **LightRAG:** Knowledge graph API availability

**Software Dependencies:**
- **Anthropic MCP:** Protocol stability for Claude Desktop integration
- **mem-agent:** Model availability and continued development
- **Python ecosystem:** Stability of required packages
- **Node.js ecosystem:** Stability for n8n and related tools
- **Docker:** Runtime compatibility and updates
- **macOS:** Continued support for M4 architecture

**Infrastructure Dependencies:**
- **Mac Mini M4:** Hardware availability and reliability
- **Network infrastructure:** ISP reliability and bandwidth
- **Power infrastructure:** Uninterruptible power supply (UPS) recommended
- **VPN services:** Secure connectivity to cloud resources (optional but recommended)

### 2.5.3 Risk Mitigation

**Service Availability Risks:**
- Multiple provider options for critical services
- Local caching reduces dependency on cloud services
- Offline mode for essential operations
- Documented failover procedures

**Cost Risks:**
- Budget monitoring and alerting at 80% threshold
- Free tier maximization strategies
- Local processing reduces API costs
- Cost optimization through smart routing

**Hardware Risks:**
- Regular backups ensure data recovery
- Documented rebuild procedures
- Alternative processing via cloud if Mac Mini fails
- Hardware warranty and support plans

**Security Risks:**
- Defense in depth architecture
- Zero-knowledge encryption for backups
- Regular security updates and audits
- Compliance with security frameworks