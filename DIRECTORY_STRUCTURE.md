# Empire v7.3 - Directory Structure

**Last Updated:** 2025-11-30
**Version:** v7.3.0

This document describes the organized directory structure for the Empire AI project.

## Root Level

```
Empire/
├── README.md                       # Main project documentation
├── CLAUDE.md                       # AI assistant reference guide
├── empire-arch.txt                 # Core architecture specification
├── DIRECTORY_STRUCTURE.md          # This file
└── notebooklm/                     # Documentation for NotebookLM presentations
```

**Key files kept at root for easy AI/developer access:**
- `README.md` - Primary entry point for project
- `CLAUDE.md` - Complete guide for AI assistants and MCPs
- `empire-arch.txt` - Architecture specifications

---

## Documentation (`docs/`)

All project documentation organized by category:

```
docs/
├── architecture/
│   └── PRODUCTION_ARCHITECTURE.md      # Production deployment architecture
├── guides/
│   ├── PRE_DEV_CHECKLIST.md           # Development setup checklist
│   ├── SETUP_STATUS.md                 # Setup progress tracking
│   └── NEO4J_SETUP_COMPLETE.md        # Neo4j setup guide
├── services/
│   ├── B2_FOLDER_STRUCTURE.md         # Backblaze B2 organization
│   ├── DOCUMENT_PROCESSING_SERVICES.md # Document processing specs
│   └── CREWAI_OUTPUT_GUIDELINES.md    # CrewAI output standards
├── analysis/
│   └── EMPIRE_v7_GAP_ANALYSIS_WORKING.md # Gap analysis
└── crewai/
    └── CREWAI_readme.md                # CrewAI documentation
```

---

## Requirements (`srs/`)

Software Requirements Specification documents:

```
srs/
├── 01_introduction.md               # Project introduction
├── 02_overall_description.md        # System overview
├── 03_specific_requirements.md      # Detailed requirements
├── 04_v3_enhancements.md           # Version 3 features
├── 05_v3_1_optimizations.md        # Version 3.1 optimizations
├── 06_v4_unified_architecture.md   # Version 4 architecture
├── 07_performance_scaling.md       # Performance specifications
├── 08_video_processing.md          # Video processing features
└── 09_orchestrator_requirements.md # Orchestration specs
```

---

## Workflows (`workflows/`)

Complete milestone-based workflow documentation:

```
workflows/
├── README.md                        # Workflows overview
├── INDEX.md                         # Navigation index
├── STATUS.md                        # Implementation status
├── MILESTONE_MAP.md                 # n8n to Python mapping
├── COMPLETION_STATUS.md             # Completion tracking
├── 00_overview.md                   # Architecture overview
├── milestone_1_document_intake.md   # Document upload & validation
├── milestone_2_universal_processing.md # Text extraction & chunking
├── milestone_3_advanced_rag.md      # Embeddings & vector storage
├── milestone_4_query_processing.md  # Hybrid search (Supabase + Neo4j)
├── milestone_5_chat_ui.md           # WebSocket chat & memory
├── milestone_6_monitoring.md        # Prometheus & Grafana
├── milestone_7_admin_tools.md       # Admin API endpoints
├── milestone_8_crewai_integration.md # Multi-agent workflows
├── database_setup.md                # Complete PostgreSQL schemas
├── integration_services.md          # External service configs
├── service_patterns.md              # Python service patterns
├── deployment_configuration.md      # Production deployment
├── testing_validation.md            # Testing procedures
└── create_milestones.sh            # Milestone file generator
```

**Key Integrations Documented:**
- BGE-Reranker-v2 (local, $0 cost - replaces Cohere)
- Neo4j (production graph database)
- Supabase (PostgreSQL + pgvector)
- Ollama (BGE-M3 embeddings)

---

## Configuration (`config/`)

All configuration files organized by purpose:

```
config/
├── docker/
│   ├── docker-compose.yml           # Main services (Neo4j + Redis)
│   └── docker-compose.monitoring.yml # Monitoring stack
├── monitoring/
│   ├── prometheus.yml               # Prometheus configuration
│   ├── alert_rules.yml              # Alert definitions
│   ├── alertmanager.yml             # Alert routing
│   ├── README.md                    # Monitoring documentation
│   ├── INTEGRATION_GUIDE.md         # Integration instructions
│   ├── example_app_with_monitoring.py # Example implementation
│   └── grafana/                     # Grafana configurations
│       ├── dashboards/              # Dashboard JSONs
│       └── provisioning/            # Datasource configs
├── schemas/
│   └── neo4j_schema.cypher          # Neo4j graph schema
└── requirements/
    └── requirements-monitoring.txt   # Monitoring dependencies
```

**Configuration Updates:**
- All docker-compose files use relative paths to `../../data/`
- Monitoring configs reference `../monitoring/`

---

## Scripts (`scripts/`)

Executable scripts organized by function:

```
scripts/
├── README.md                        # Scripts documentation
├── setup/
│   └── setup_neo4j.sh              # Neo4j schema initialization
├── monitoring/
│   ├── start-monitoring.sh         # Start monitoring stack
│   └── test_monitoring.py          # Monitoring verification
└── deployment/
    ├── promote_to_production.py    # Production promotion
    └── setup_b2_production_structure.py # B2 setup
```

**Script Updates:**
- All scripts navigate to project root: `cd "$(dirname "$0")/../.."`
- Reference new config/docker paths
- Updated to work from any location

---

## Application Code (`app/`)

FastAPI application code with 26 API routes and 15 AI agents:

```
app/
├── __init__.py
├── main.py                              # FastAPI app with 26 routers
├── celery_app.py                        # Celery configuration
├── api/
│   ├── __init__.py
│   ├── notifications.py                 # Notification endpoints
│   ├── upload.py                        # File upload endpoints
│   └── routes/
│       ├── __init__.py
│       └── query.py                     # Query processing endpoints
├── core/
│   ├── __init__.py
│   ├── connections.py                   # Database connection manager
│   ├── database.py                      # Database utilities
│   ├── database_optimized.py            # Optimized DB operations
│   ├── feature_flags.py                 # Feature flag management
│   ├── langfuse_config.py               # Langfuse observability
│   ├── supabase_client.py               # Supabase client
│   └── websockets.py                    # WebSocket utilities
├── middleware/
│   ├── audit.py                         # Audit logging middleware
│   ├── auth.py                          # Authentication middleware
│   ├── clerk_auth.py                    # Clerk authentication
│   ├── compression.py                   # Response compression
│   ├── input_validation.py              # Input validation
│   ├── rate_limit.py                    # Rate limiting
│   ├── rls_context.py                   # Row-level security context
│   └── security.py                      # Security headers
├── models/
│   ├── __init__.py
│   ├── agent_interactions.py            # Agent interaction models
│   ├── agent_router.py                  # Agent router models
│   ├── crewai_asset.py                  # CrewAI asset models
│   ├── documents.py                     # Document models
│   ├── notifications.py                 # Notification models
│   ├── processing_logs.py               # Processing log models
│   ├── rbac.py                          # RBAC models
│   ├── task_status.py                   # Task status models
│   └── users.py                         # User models
├── routes/                              # 20 API route modules
│   ├── agent_interactions.py            # Inter-agent messaging
│   ├── agent_router.py                  # Intelligent query routing
│   ├── audit.py                         # Audit log queries
│   ├── chat_files.py                    # Chat file upload
│   ├── content_summarizer.py            # AGENT-002 routes
│   ├── costs.py                         # Cost tracking
│   ├── crewai_assets.py                 # CrewAI asset storage
│   ├── crewai.py                        # CrewAI workflows
│   ├── department_classifier.py         # AGENT-008 routes
│   ├── document_analysis.py             # AGENT-009/010/011 routes
│   ├── documents.py                     # Document management
│   ├── feature_flags.py                 # Feature flag management
│   ├── monitoring.py                    # Analytics dashboard
│   ├── multi_agent_orchestration.py     # AGENT-012/013/014/015 routes
│   ├── preferences.py                   # User preferences
│   ├── rbac.py                          # Role-based access control
│   ├── sessions.py                      # Session management
│   ├── status.py                        # REST status polling
│   ├── users.py                         # User management
│   └── websocket.py                     # WebSocket endpoints
├── services/                            # 50+ service modules
│   ├── agent_interaction_service.py     # Agent messaging service
│   ├── agent_router_service.py          # Query routing service
│   ├── content_summarizer_agent.py      # AGENT-002: Content Summarizer
│   ├── department_classifier_agent.py   # AGENT-008: Department Classifier
│   ├── document_analysis_agents.py      # AGENT-009/010/011: Analysis Agents
│   ├── multi_agent_orchestration.py     # AGENT-012/013/014/015: Orchestration
│   ├── orchestrator_agent_service.py    # LangGraph orchestrator
│   ├── arcade_service.py                # Arcade.dev integration
│   ├── b2_storage.py                    # Backblaze B2 storage
│   ├── chat_service.py                  # Chat functionality
│   ├── chunking_service.py              # Document chunking
│   ├── citation_service.py              # Source citations
│   ├── crewai_service.py                # CrewAI integration
│   ├── embedding_service.py             # BGE-M3 embeddings
│   ├── hybrid_search_service.py         # Hybrid search
│   ├── metadata_extractor.py            # Source metadata extraction
│   ├── neo4j_entity_service.py          # Neo4j entity operations
│   ├── query_expansion_service.py       # Query expansion
│   ├── reranking_service.py             # BGE-Reranker-v2
│   ├── supabase_storage.py              # Supabase operations
│   ├── tiered_cache_service.py          # Tiered caching
│   ├── url_processing.py                # URL/YouTube processing
│   ├── vision_service.py                # Claude Vision API
│   ├── websocket_manager.py             # WebSocket management
│   └── (40+ more services...)
├── tasks/                               # Celery tasks
│   ├── __init__.py
│   ├── bulk_operations.py               # Batch processing
│   ├── crewai_workflows.py              # CrewAI async tasks
│   ├── document_processing.py           # Document processing
│   ├── embedding_generation.py          # Embedding generation
│   ├── graph_sync.py                    # Neo4j sync
│   └── query_tasks.py                   # Query processing
├── ui/                                  # Gradio UI components
│   ├── chat_with_files.py               # Chat interface
│   └── components/
│       ├── citation_cards.py            # Citation display
│       └── processing_status.py         # Progress indicators
├── utils/
│   ├── celery_retry.py                  # Retry utilities
│   └── websocket_notifications.py       # WebSocket utilities
├── validators/
│   ├── __init__.py
│   └── security.py                      # Security validators
└── workflows/
    ├── __init__.py
    ├── langgraph_workflows.py           # LangGraph workflows
    └── workflow_router.py               # Workflow routing
```

---

## CrewAI (`crewai/`)

Multi-agent workflow configurations:

```
crewai/
├── ASSET_TYPE_DECISION_LOGIC.md    # Asset type logic
├── CREWAI_QUICK_REFERENCE.md       # Quick reference
├── empire_crew_config.py           # Crew configuration
├── orchestrator_enhanced.py        # Enhanced orchestrator
└── WORKFLOW_EXAMPLES.md            # Workflow examples
```

---

## Data (`data/`)

Runtime data directories (not tracked in git):

```
data/
├── neo4j/                          # Neo4j database files
│   ├── data/                       # Graph database data
│   ├── logs/                       # Neo4j logs
│   ├── import/                     # Import directory
│   └── plugins/                    # Neo4j plugins
└── redis/                          # Redis data
    └── data/                       # Redis persistence
```

**Important:** These directories are created by Docker and contain runtime data.

---

## Resources (`Resources/`)

Reference materials and PDFs:

```
Resources/
├── Agentic_Design_Patterns.pdf
├── Dynamic Hybrid Search for RAG Agents.pdf
├── State-of-the-Art n8n Modular RAG System.pdf
└── (other reference materials)
```

---

## Review (`Review/`)

Review and temporary files.

---

## Key Path Changes

### Docker Compose
**From:** `./neo4j/data` and `./redis/data`
**To:** `../../data/neo4j/data` and `../../data/redis/data`
**Location:** `config/docker/docker-compose.yml`

### Monitoring Configs
**From:** `./monitoring/prometheus.yml`
**To:** `../monitoring/prometheus.yml`
**Location:** `config/docker/docker-compose.monitoring.yml`

### Scripts
**All scripts now:**
1. Navigate to project root: `cd "$(dirname "$0")/../.."`
2. Use absolute paths from root
3. Reference `config/docker/` for docker-compose files
4. Reference `config/monitoring/` for monitoring configs

---

## Running Commands

### Start Services
```bash
# From project root
docker-compose -f config/docker/docker-compose.yml up -d

# Or from anywhere
cd /path/to/Empire
docker-compose -f config/docker/docker-compose.yml up -d
```

### Start Monitoring
```bash
# From project root
./scripts/monitoring/start-monitoring.sh

# Or
bash scripts/monitoring/start-monitoring.sh
```

### Setup Neo4j
```bash
# From project root
./scripts/setup/setup_neo4j.sh

# Or
bash scripts/setup/setup_neo4j.sh
```

---

## Benefits of New Structure

1. **Logical Organization**: Files grouped by purpose (docs, config, scripts, data)
2. **Scalability**: Easy to add new documentation, scripts, or configs
3. **Clarity**: Clear separation between code, config, and data
4. **Maintainability**: Easier to find and update specific files
5. **Git-Friendly**: Data directories separate from tracked files
6. **AI-Friendly**: Key files (README, claude.md, empire-arch.txt) at root

---

## Tests (`tests/`)

Comprehensive test suite with 75+ test files:

```
tests/
├── __init__.py
├── conftest.py                          # Pytest configuration
├── load_testing/                        # Performance tests
│   ├── locustfile.py
│   └── query_load_test.py
├── test_agent_interactions.py           # Agent messaging tests
├── test_agent_router_service.py         # Query routing tests
├── test_content_summarizer.py           # AGENT-002 tests (15 tests)
├── test_department_classifier.py        # AGENT-008 tests (18 tests)
├── test_document_analysis_agents.py     # AGENT-009/010/011 tests (45 tests)
├── test_multi_agent_orchestration.py    # AGENT-012/013/014/015 tests (62 tests)
├── test_chat_file_upload.py             # Chat file tests
├── test_citation_service.py             # Citation tests
├── test_crewai_integration.py           # CrewAI tests
├── test_embedding_service.py            # Embedding tests
├── test_hybrid_search_service.py        # Search tests
├── test_metadata_extraction_e2e.py      # Metadata extraction tests
├── test_neo4j_*.py                      # Neo4j tests
├── test_url_processing.py               # URL processing tests
├── test_websocket_*.py                  # WebSocket tests
└── (50+ more test files...)
```

---

**Last Updated:** 2025-11-30
**Version:** v7.3.0
**Status:** Production-ready with 46 completed tasks
