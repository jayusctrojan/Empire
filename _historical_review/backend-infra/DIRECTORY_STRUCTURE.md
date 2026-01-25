# Empire v7.2 - Directory Structure

This document describes the organized directory structure for the Empire AI project.

## Root Level

```
Empire/
├── README.md                       # Main project documentation
├── claude.md                       # AI assistant reference guide
├── empire-arch.txt                 # Core architecture specification
└── DIRECTORY_STRUCTURE.md         # This file
```

**Key files kept at root for easy AI/developer access:**
- `README.md` - Primary entry point for project
- `claude.md` - Complete guide for AI assistants and MCPs
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

FastAPI application code:

```
app/
└── services/
    └── (application services)
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

**Last Updated:** 2025-01-02
**Version:** v7.2
**Status:** Reorganized and ready for development
