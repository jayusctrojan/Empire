# Empire v7.2 Project Constitution

**Version**: 7.2
**Last Updated**: 2025-01-02
**Status**: Active

---

## 1. Project Core Principles

### 1.1 Hybrid Intelligence Architecture
- **Local-First Processing**: Maximize use of local compute (Mac Studio M3 Ultra) for embeddings (BGE-M3) and reranking (BGE-Reranker-v2) to reduce costs and increase privacy
- **Strategic Cloud Usage**: Leverage cloud APIs (Claude Sonnet 4.5, Claude Haiku) only for synthesis and complex reasoning where local models cannot match quality
- **Neo4j Free on Local**: Run production Neo4j graph database locally via Docker to eliminate expensive GraphDB costs (~$100+/month saved)
- **Dual-Interface Access**: Support both developer access (Neo4j MCP in Claude Desktop/Code) and end-user access (Chat UI via Gradio/Streamlit)

### 1.2 Cost Efficiency & Token Optimization
- **Monthly Budget Target**: $350-500/month (includes all cloud services and both interfaces)
- **Zero-Cost Components**: Neo4j (Docker), Ollama embeddings (BGE-M3), local reranking (BGE-Reranker-v2), Tailscale VPN
- **Query Expansion Strategy**: Use Claude Haiku (cheap) for 4-5 query variations instead of expensive embedding multiple times
- **Semantic Caching**: Maintain 60-80% cache hit rate via Redis to minimize API calls
- **Batch Processing**: Use Claude Batch API for 90% cost reduction on non-urgent tasks

### 1.3 Production-Grade Reliability
- **Uptime SLA**: 99.9% availability target
- **Async Processing**: Celery-based task queue with retry logic and graceful degradation
- **Full Observability**: Prometheus metrics, Grafana dashboards, OpenTelemetry tracing, automated alerting
- **Error Handling**: Retryable vs non-retryable error classification, exponential backoff, circuit breakers
- **Data Durability**: Multi-database persistence (PostgreSQL, Neo4j, Redis) with proper backup strategies

### 1.4 Multi-Modal & Multi-Department Support
- **Document Types**: 40+ formats via MarkItDown MCP (PDF, Word, Excel, images, audio, video, markdown, code)
- **Content Intelligence**:
  - Text extraction and chunking (LlamaIndex + LlamaParse)
  - Entity extraction and relationships (Neo4j graphs)
  - Image analysis (Claude Vision API)
  - Audio transcription (Soniox)
  - Structured data querying (Natural language → SQL)
- **Department Taxonomy**: 10 business departments with AI-powered content classification
- **Personalization**: Graph-based user memory with confidence scoring and temporal decay

### 1.5 Hybrid Database Strength
- **PostgreSQL (Supabase)**:
  - Primary user data, sessions, audit logs
  - pgvector (1024-dim) for semantic search with HNSW indexing
  - Full-text search (FTS) with BM25-like scoring
  - Structured tabular data from CSV/Excel
- **Neo4j (Mac Studio Docker)**:
  - Knowledge graphs and entity relationships
  - Multi-hop graph traversal (<100ms for 2-hop queries)
  - Advanced analytics (centrality, community detection, pathfinding)
  - Natural language → Cypher translation via Claude Sonnet
- **Redis (Upstash/Local)**:
  - Semantic caching with tiered thresholds
  - Celery task broker
  - Session storage

### 1.6 Open Standards & Extensibility
- **API-First Design**: FastAPI with OpenAPI/Swagger documentation
- **WebSocket Support**: Real-time streaming for chat interfaces
- **MCP Integration**: Natural language interfaces via Model Context Protocol
- **Standard Formats**: Cypher (Neo4j), SQL (PostgreSQL), REST/WebSocket (FastAPI)
- **GitHub OpenSpec**: Specification-driven development with Spec Kit

---

## 2. Primary Goals

### 2.1 Performance Targets
- **Query Latency**: <500ms for hybrid search (cached queries <100ms)
- **Document Processing**: <1s per document (with caching)
- **Search Quality**: 95%+ relevance, 40-60% improvement vs baseline
- **Cache Hit Rate**: 60-80% for semantic queries
- **Embedding Speed**: <100ms for 1024-dim vectors (local Ollama)
- **Graph Queries**: <100ms for 2-hop traversal, 10-100x faster than SQL joins

### 2.2 Scalability Targets
- **Document Throughput**: 1000+ documents/day (up from 500 in v7.1)
- **Query Volume**: 5000+ queries/day
- **Concurrent Users**: Support 100+ simultaneous chat sessions
- **Vector Storage**: Scale to millions of vectors with HNSW indexing
- **Graph Nodes**: Handle 100K+ entities with sub-100ms queries

### 2.3 Quality & Accuracy
- **AI Extraction Accuracy**: 97-99% (Claude Sonnet 4.5)
- **Entity Extraction**: >95% (LlamaIndex + LangExtract with cross-validation)
- **Embedding Quality**: BGE-M3 (MTEB benchmark leader for multi-lingual)
- **Reranking Improvement**: 25-35% better ordering (BGE-Reranker-v2)
- **Search Recall**: 30-50% improvement via query expansion (Claude Haiku)

### 2.4 Development Velocity
- **8 Milestone Structure**: Clear progression from intake to multi-agent workflows
- **Specification-Driven**: GitHub OpenSpec with Spec Kit for task management
- **AI-Assisted Development**: Claude Code (architecture), Cline (features), Continue.dev (completion)
- **Automated Testing**: pytest with >80% code coverage
- **CI/CD Pipeline**: GitHub Actions with Render auto-deployment

### 2.5 Auditability & Observability
- **Structured Logging**: JSON logs with correlation IDs across all services
- **Metrics Collection**: Prometheus scraping all endpoints (/monitoring/metrics)
- **Distributed Tracing**: OpenTelemetry for end-to-end request tracking
- **Alerting**: Automated alerts for critical errors, slow queries, resource exhaustion
- **Dashboards**: Grafana dashboards for real-time monitoring (Milestone 6)

---

## 3. Technology Stack Mandates

### 3.1 Core Backend Stack
- **Language**: Python 3.11+
- **Web Framework**: FastAPI (async REST + WebSocket APIs)
- **Task Queue**: Celery with Redis broker
- **API Documentation**: Auto-generated OpenAPI/Swagger
- **Deployment**: Render (web services, Celery workers, static sites)

### 3.2 Database & Storage Stack
- **Relational + Vectors**: Supabase (PostgreSQL 15+ with pgvector extension)
- **Graph Database**: Neo4j Community Edition (Docker on Mac Studio)
- **Cache & Broker**: Redis (Upstash for production, local for dev)
- **Object Storage**: Backblaze B2 (JB-Course-KB bucket)
- **Vector Indexing**: HNSW (pgvector) for <28x faster similarity search

### 3.3 AI & Embeddings Stack
- **Primary LLM**: Claude Sonnet 4.5 (synthesis, Cypher generation, vision)
- **Query Expansion**: Claude Haiku (4-5 variations per query)
- **Embeddings**: BGE-M3 (1024-dim) via Ollama on Mac Studio (local, $0)
- **Reranking**: BGE-Reranker-v2 via Ollama on Mac Studio (local, $0)
- **OCR**: LlamaParse (10K pages/month free) + Mistral OCR (complex PDFs)
- **Audio**: Soniox transcription API
- **Extraction**: LangExtract (Gemini-powered with schema validation)

### 3.4 Orchestration & Integration Stack
- **Document Parsing**: LlamaIndex service on Render (https://jb-llamaindex.onrender.com)
- **Multi-Agent**: CrewAI service on Render (https://jb-crewai.onrender.com)
- **Knowledge Graphs**: LightRAG API with Neo4j backend sync
- **Semantic Cache**: Redis with tiered similarity thresholds (0.98+, 0.93-0.97, 0.88-0.92)
- **Search**: Hybrid 4-method (dense, sparse, ILIKE, fuzzy) with RRF fusion

### 3.5 Monitoring & Observability Stack
- **Metrics**: Prometheus (port 9090)
- **Visualization**: Grafana (port 3000, admin/empiregrafana123)
- **Tracing**: OpenTelemetry with Jaeger
- **Alerting**: Alertmanager (port 9093)
- **Task Monitoring**: Flower (port 5555, admin/empireflower123)
- **Log Aggregation**: Structured JSON logs with ELK/Loki (future)

### 3.6 Frontend & Chat UI Stack
- **Chat Interface**: Gradio or Streamlit (Render deployment)
- **Real-time**: WebSocket connections for streaming responses
- **Framework**: React or SvelteKit for admin dashboards (future)
- **Styling**: Tailwind CSS or Material-UI
- **State Management**: React Context or Svelte stores

### 3.7 Development Tools Stack
- **Primary IDE**: Visual Studio Code
- **AI Assistants**:
  - **Claude Code** (CLI) - Architecture, schemas, complex refactoring
  - **Cline** (VS Code) - Rapid feature implementation
  - **Continue.dev** (VS Code) - Code completion, inline suggestions
- **MCPs Available**:
  - **Neo4j MCP** - Graph queries via natural language → Cypher
  - **Supabase MCP** - Direct SQL operations on PostgreSQL + pgvector
  - **Render MCP** - Deployment and service management
  - **Chrome DevTools MCP** - Frontend debugging
  - **Ref MCP** - Official documentation (FastAPI, Neo4j, Supabase, etc.)
  - **TaskMaster MCP** - AI-powered task management
  - **Claude Context MCP** - Conversation context across sessions
- **GitHub Operations**: Available via terminal using `gh` (GitHub CLI) and `git` commands
- **Tailscale VPN**: Available via terminal using `tailscale` command for remote access and networking

### 3.8 Version Control & Specifications
- **Source Control**: GitHub with branch protection
- **Specification Format**: GitHub OpenSpec (Spec Kit)
- **Task Management**: TaskMaster MCP + GitHub Issues
- **Documentation**: Markdown (IEEE 830-1998 compliant SRS)
- **Architecture Decisions**: ADR (Architecture Decision Records) in `/docs/architecture/`

---

## 4. Team Collaboration & Codebase Norms

### 4.1 Specification-Driven Development
- **OpenSpec Structure**: All specs under `/specs/` directory, version controlled
- **Entry Point**: `/specs/1-empire-v7.2/spec.md` references comprehensive docs
- **Detailed Requirements**: `/srs/*.md` (340+ requirements across 11 files)
- **Implementation Guides**: `/workflows/*.md` (8 milestone-based workflows)
- **Architecture**: `/empire-arch.txt` (1,352 lines complete specification)

### 4.2 Task Management Workflow
1. **Planning Phase**: Use `/speckit.specify` to create feature specifications
2. **Task Breakdown**: Use `/speckit.tasks` to generate actionable tasks
3. **Implementation**: Use `/speckit.implement` to execute with task tracking
4. **Validation**: Use `/speckit.checklist` to ensure quality before merge
5. **Analysis**: Use `/speckit.analyze` for cross-artifact consistency checks

### 4.3 AI Assistant Coordination

#### Primary Responsibilities
- **Claude Code (CLI)**:
  - System architecture design and planning
  - Database schema creation (Neo4j + Supabase)
  - MCP integration and testing
  - Complex multi-file refactoring
  - GitHub PR creation and management
  - Render deployment orchestration

- **Cline (VS Code Extension)**:
  - Rapid feature implementation within VS Code
  - File-by-file editing with visual diffs
  - Unit test generation
  - Code review and refactoring
  - Iterative development cycles

- **Continue.dev (VS Code Extension)**:
  - Real-time code completion
  - Function generation from comments
  - Type hint additions
  - Quick refactoring operations
  - Code explanation and documentation

#### MCP Server Coordination
1. **Context Sharing**:
   - **Claude Context MCP**: Maintains session memory across all assistants
   - **Supabase MCP**: Direct database operations shared across agents
   - **Neo4j MCP**: Graph queries accessible to all assistants

2. **Task Synchronization**:
   - **TaskMaster MCP**: Central task state, ownership, dependencies
   - All assistants query TaskMaster before starting new work
   - Avoid overlapping efforts through task locking

3. **Documentation Access**:
   - **Ref MCP**: All assistants access official docs for proper API usage
   - **Chrome DevTools MCP**: Shared frontend debugging context
   - **GitHub CLI (`gh`)**: GitHub operations via terminal commands
   - **Render MCP**: Coordinated deployment and service management

### 4.4 Code Quality Standards

#### Code Style & Structure
- **PEP 8 Compliance**: All Python code follows PEP 8 style guide
- **Type Hints**: Required for all function signatures (Python 3.11+ syntax)
- **Docstrings**: Google-style docstrings for all public functions/classes
- **Async/Await**: Use async patterns for I/O-bound operations
- **Error Handling**: Explicit exception handling with custom exception classes

#### Testing Requirements
- **Unit Tests**: pytest with >80% code coverage
- **Integration Tests**: Test database interactions (Supabase, Neo4j)
- **API Tests**: FastAPI TestClient for endpoint testing
- **E2E Tests**: Playwright or Selenium for frontend flows
- **Performance Tests**: Load testing with Locust or k6

#### Documentation Standards
- **Architecture Decisions**: ADR files in `/docs/architecture/`
- **API Documentation**: OpenAPI/Swagger auto-generated
- **Database Schemas**: Comprehensive schemas in `/workflows/database_setup.md`
- **Milestone Guides**: Step-by-step implementation in `/workflows/milestone_*.md`
- **Setup Instructions**: Clear checklists in `/docs/guides/PRE_DEV_CHECKLIST.md`

### 4.5 Git Workflow & Branching

#### Branch Strategy
- **main**: Production-ready code, protected branch
- **develop**: Integration branch for ongoing development
- **feature/N-feature-name**: Feature branches from GitHub OpenSpec
- **hotfix/description**: Critical production fixes

#### Commit Standards
- **Format**: `type(scope): description`
- **Types**: feat, fix, docs, refactor, test, chore
- **Examples**:
  - `feat(search): add hybrid 4-method search with RRF fusion`
  - `fix(neo4j): resolve connection timeout in graph queries`
  - `docs(milestone-3): update RAG implementation guide`

#### Pull Request Requirements
- **PR Template**: Include description, testing steps, linked issues
- **Code Review**: Minimum 1 approval required
- **CI/CD**: All tests must pass (GitHub Actions)
- **Documentation**: Update relevant docs if needed
- **Changelog**: Update CHANGELOG.md with notable changes

### 4.6 CI/CD & Deployment

#### Automated Testing Pipeline (GitHub Actions)
1. **Lint & Format**: black, isort, flake8, mypy
2. **Unit Tests**: pytest with coverage report
3. **Integration Tests**: Test database connections
4. **Security Scan**: bandit, safety for vulnerabilities
5. **Build Check**: Ensure Docker builds succeed

#### Deployment Strategy (Render)
- **Auto-Deploy**: Push to main triggers Render deployment
- **Health Checks**: FastAPI `/health` endpoint monitored
- **Rollback**: Automatic rollback on health check failures
- **Environment Variables**: Managed via Render dashboard
- **Service Dependencies**: Ensure Neo4j, Redis, Supabase are healthy

#### Monitoring & Alerting
- **Metrics**: All services expose `/monitoring/metrics` (Prometheus format)
- **Logs**: Structured JSON logs with correlation IDs
- **Alerts**: Critical errors trigger notifications (Alertmanager)
- **Dashboards**: Grafana for real-time monitoring (admin/empiregrafana123)

### 4.7 Session & Versioning Awareness

#### Conversation Context
- **Claude Context MCP**: Maintains session awareness across all AI assistants
- **Session IDs**: All API requests include correlation IDs for tracing
- **State Management**: Celery tasks track progress in Redis
- **User Sessions**: JWT tokens with 24-hour expiry

#### Version Tracking
- **Semantic Versioning**: Follow SemVer (MAJOR.MINOR.PATCH)
- **Current Version**: v7.2 (Dual-Interface Architecture)
- **Change Log**: CHANGELOG.md tracks all notable changes
- **Migration Scripts**: Database migrations in `/migrations/` directory
- **API Versioning**: `/api/v1/` endpoints for backward compatibility

---

## 5. Architectural Constraints & Trade-offs

### 5.1 Non-Negotiable Constraints
1. **Neo4j on Mac Studio**: Must run locally via Docker (FREE, production)
2. **Local Embeddings**: BGE-M3 via Ollama (no external embedding APIs)
3. **Cost Budget**: $350-500/month maximum (cloud services only)
4. **PostgreSQL**: Supabase for vectors, must use pgvector extension
5. **Dual Interfaces**: Both Neo4j MCP and Chat UI must be supported

### 5.2 Accepted Trade-offs
1. **Mac Studio Dependency**: Neo4j requires Mac Studio to be running 24/7
   - **Mitigation**: Tailscale VPN for remote access, UPS for power stability
2. **Network Latency**: Cloud services (Render) → Local Neo4j adds ~50-100ms
   - **Mitigation**: Aggressive caching, async processing, query optimization
3. **Ollama Performance**: Local embeddings slower than cloud APIs
   - **Mitigation**: Batch processing, caching, pre-computation for common queries
4. **Complexity**: Hybrid architecture (3 databases) increases operational overhead
   - **Mitigation**: Comprehensive monitoring, automated health checks, clear runbooks

### 5.3 Future-Proofing Considerations
1. **Neo4j Enterprise**: May upgrade if business scales beyond Community Edition limits
2. **Multi-Tenancy**: Design schemas with tenant_id for future SaaS conversion
3. **Horizontal Scaling**: Celery workers can scale horizontally on Render
4. **API Versioning**: Design APIs with `/v1/` prefix for backward compatibility
5. **Plugin Architecture**: Design for extensibility (custom extractors, processors)

---

## 6. Security & Privacy Principles

### 6.1 Data Privacy
- **Local-First**: 98% of document processing happens locally (Mac Studio)
- **Data Sovereignty**: User data stored in Supabase (US-based, SOC 2 compliant)
- **Encryption**: TLS 1.3 in transit, AES-256 at rest
- **Access Control**: Row-Level Security (RLS) in Supabase
- **PII Handling**: Redaction/masking for sensitive data before external API calls

### 6.2 Authentication & Authorization
- **User Auth**: Supabase Auth with JWT tokens
- **API Keys**: Rotate quarterly, store in environment variables (never commit)
- **RBAC**: Role-Based Access Control (admin, user, readonly)
- **MCP Auth**: Secure Neo4j credentials (stored in .env) for MCP connections
- **Session Management**: 24-hour token expiry, refresh token rotation

### 6.3 Security Best Practices
- **Dependency Scanning**: safety, bandit for vulnerability checks
- **SQL Injection**: Use parameterized queries exclusively
- **XSS Prevention**: Escape all user inputs in frontend
- **CORS**: Strict CORS policies (whitelist origins only)
- **Rate Limiting**: API rate limits (100 req/min per user)

---

## 7. Change Management & Evolution

### 7.1 Constitution Updates
- **Versioning**: Constitution follows semantic versioning
- **Review Process**: Major changes require team approval
- **History**: Track changes in git with clear commit messages
- **Effective Date**: Changes take effect immediately upon merge to main

### 7.2 Technology Evolution
- **Evaluation Criteria**: Performance, cost, maintainability, community support
- **Pilot Projects**: Test new tech in isolated features before adoption
- **Migration Plan**: Phased rollout with rollback strategy
- **Documentation**: Update all relevant docs when changing tech stack

### 7.3 Milestone Completion Criteria
Each milestone must meet these criteria before considered complete:
1. **Functionality**: All specified features implemented and tested
2. **Performance**: Meets latency, throughput, and quality targets
3. **Documentation**: Updated specs, guides, and API docs
4. **Monitoring**: Metrics, logs, alerts configured
5. **Testing**: >80% code coverage, all tests passing
6. **Deployment**: Successfully deployed to production (Render)

---

## 8. Success Metrics & KPIs

### 8.1 Technical Metrics
- **Availability**: 99.9% uptime (measured monthly)
- **Query Latency**: P95 < 500ms, P99 < 1000ms
- **Search Quality**: >95% relevance (user feedback)
- **Cost Efficiency**: <$500/month (cloud services)
- **Cache Hit Rate**: >60% (semantic caching)

### 8.2 Quality Metrics
- **AI Accuracy**: >97% extraction accuracy (sampled validation)
- **Entity Extraction**: >95% precision and recall
- **Test Coverage**: >80% code coverage
- **Bug Density**: <1 critical bug per 1000 LOC
- **Technical Debt**: <10% of sprint capacity for refactoring

### 8.3 Business Metrics
- **Document Throughput**: 1000+ docs/day processed
- **User Adoption**: 100+ daily active users (future)
- **Query Volume**: 5000+ queries/day
- **User Satisfaction**: >4.5/5 average rating (future)
- **Feature Velocity**: Complete 1 milestone per month

---

## Appendix A: Key Documentation References

- **Main Specification**: `/specs/1-empire-v7.2/spec.md`
- **Architecture**: `/empire-arch.txt` (1,352 lines)
- **Requirements**: `/srs/03_specific_requirements.md` (340+ requirements)
- **Milestones**: `/workflows/milestone_*.md` (8 detailed guides)
- **Database Schemas**: `/workflows/database_setup.md` (3,318 lines, 37+ tables)
- **AI Tools Guide**: `/claude.md` (Complete MCP and tooling reference)
- **Setup Checklist**: `/docs/guides/PRE_DEV_CHECKLIST.md`

---

**Adopted**: 2025-01-02
**Version**: 1.0
**Status**: Active
**Next Review**: 2025-04-01 (or upon major architectural changes)
