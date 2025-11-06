# Empire v7.2 - Pre-Development Checklist

## Overview
This checklist ensures all API keys, credentials, and MCPs are configured before FastAPI development begins. Complete each section and mark items as done.

### Production Architecture - Hybrid Database System
Empire v7.2 uses a **dual database production architecture**:
- **PostgreSQL (Supabase)**: User data, vector embeddings, sessions, authentication
- **Neo4j (Mac Studio)**: Knowledge graphs, entity relationships, graph traversal
- **Both are PRODUCTION databases** working together
- **Multi-modal access**: REST/WebSocket APIs + Neo4j MCP for natural language queries

---

## 1. Core Database & Storage

### ✅ Neo4j Graph Database (PRODUCTION - Local Docker)
- **Status**: ✅ Configured in docker-compose.yml
- **Role**: PRODUCTION knowledge graph database (works alongside PostgreSQL)
- **Purpose**: Entity relationships, graph traversal, multi-hop queries, natural language access via MCP
- **Connection**: `bolt://localhost:7687`
- **Credentials**:
  - Username: `neo4j`
  - Password: `<your-password>`  *(Set in docker-compose.yml and .env)*
- **Web Interface**: http://localhost:7474
- **Location**: Environment variables in docker-compose.yml
- **Access from cloud**: Via Tailscale VPN to Mac Studio

### ⬜ Supabase PostgreSQL + pgvector
- **Status**: ⬜ Needs setup
- **Tier**: SMALL ($15/month, 2GB RAM)
- **Required Credentials**:
  - `SUPABASE_URL`: [Your project URL - format: https://xxxxx.supabase.co]
  - `SUPABASE_ANON_KEY`: [Public anon key for client access]
  - `SUPABASE_SERVICE_KEY`: [Service role key for server access - KEEP SECRET]
  - `SUPABASE_DB_PASSWORD`: [Direct PostgreSQL password]
- **Where to put them**: `.env` file (see section 9)
- **How to get**:
  1. Go to https://app.supabase.com/project/YOUR_PROJECT/settings/api
  2. Copy Project URL → `SUPABASE_URL`
  3. Copy anon/public key → `SUPABASE_ANON_KEY`
  4. Copy service_role key → `SUPABASE_SERVICE_KEY`
  5. Go to Settings → Database → Copy password → `SUPABASE_DB_PASSWORD`

---

## 2. AI/ML Services

### ⬜ Anthropic Claude API
- **Status**: ⬜ Needs key
- **Required for**: Query expansion (Haiku), conversational interface (Sonnet 3.5)
- **Credentials**:
  - `ANTHROPIC_API_KEY`: [Your Claude API key]
- **Where to put**: `.env` file
- **How to get**:
  1. Go to https://console.anthropic.com/settings/keys
  2. Create new API key
  3. Copy to `ANTHROPIC_API_KEY`
- **Monthly Cost**: ~$250-300 (40K queries/month)

### ⬜ LlamaCloud / LlamaParse
- **Status**: ⬜ Needs key
- **Required for**: Document parsing (PDFs, contracts, policies)
- **Credentials**:
  - `LLAMA_CLOUD_API_KEY`: [Your LlamaCloud API key]
- **Where to put**: `.env` file
- **How to get**:
  1. Go to https://cloud.llamaindex.ai/
  2. Sign up / Log in
  3. Go to API Keys section
  4. Create new key → Copy to `LLAMA_CLOUD_API_KEY`
- **Monthly Cost**: ~$50 (1,000 docs/month)

### ⬜ BGE-M3 Embeddings (Local via Ollama)
- **Status**: ⬜ Needs setup
- **Required for**: 1024-dim vector embeddings with sparse vectors
- **Installation**:
  ```bash
  # Install Ollama on Mac Studio
  brew install ollama

  # Pull BGE-M3 model
  ollama pull bge-m3

  # Test it
  ollama run bge-m3 "test embedding"
  ```
- **Configuration**:
  - `OLLAMA_BASE_URL`: `http://localhost:11434` (default)
  - `EMBEDDING_MODEL`: `bge-m3`
- **Where to put**: `.env` file
- **Monthly Cost**: FREE (runs locally on Mac Studio)

### ⬜ BGE-Reranker-v2 (Local via Ollama)
- **Status**: ⬜ Needs setup
- **Required for**: Local reranking (saves $30-50/month vs Cohere)
- **Installation**:
  ```bash
  # Pull reranker model
  ollama pull bge-reranker-v2-m3

  # Test it
  ollama run bge-reranker-v2-m3
  ```
- **Configuration**:
  - `RERANKER_MODEL`: `bge-reranker-v2-m3`
- **Where to put**: `.env` file
- **Monthly Cost**: FREE (runs locally on Mac Studio)

---

## 3. Existing Render Deployments (IMPORTANT!)

### ✅ Render Workspace
- **Workspace ID**: `tea-d1vtdtre5dus73a4rb4g`
- **Access**: Already configured, deployments are live

### ✅ LlamaIndex Service (Already Deployed)
- **Service ID**: `srv-d2nl1lre5dus73atm9u0`
- **URL**: https://jb-llamaindex.onrender.com
- **Purpose**: Document parsing, indexing, and retrieval
- **Status**: ACTIVE - Already running
- **Integration**:
  ```python
  # Connect to LlamaIndex service
  LLAMAINDEX_BASE_URL = "https://jb-llamaindex.onrender.com"

  # Use for document processing
  import requests
  response = requests.post(
      f"{LLAMAINDEX_BASE_URL}/parse",
      json={"file_url": "...", "parse_instructions": "..."}
  )
  ```
- **Environment Variables**:
  - `LLAMAINDEX_SERVICE_URL`: `https://jb-llamaindex.onrender.com`
  - `LLAMAINDEX_API_KEY`: [If authentication is configured]
- **Where to put**: `.env` file

### ✅ CrewAI Service (Already Deployed)
- **Service ID**: `srv-d2n0hh3uibrs73buafo0`
- **URL**: https://jb-crewai.onrender.com
- **Purpose**: Multi-agent AI orchestration for complex workflows
- **Status**: ACTIVE - Already running
- **Integration**:
  ```python
  # Connect to CrewAI service
  CREWAI_BASE_URL = "https://jb-crewai.onrender.com"

  # Use for multi-agent tasks
  import requests
  response = requests.post(
      f"{CREWAI_BASE_URL}/run-crew",
      json={
          "task": "...",
          "agents": ["researcher", "writer", "reviewer"]
      }
  )
  ```
- **Environment Variables**:
  - `CREWAI_SERVICE_URL`: `https://jb-crewai.onrender.com`
  - `CREWAI_API_KEY`: [If authentication is configured]
- **Where to put**: `.env` file

### How LlamaIndex & CrewAI Work Together in Empire:

1. **Document Intake Flow**:
   - Upload document → **LlamaIndex** parses and indexes
   - **LlamaIndex** creates chunks with metadata
   - Chunks sent to BGE-M3 for embeddings
   - Stored in Supabase + Neo4j

2. **Complex Query Flow**:
   - User query → **CrewAI** coordinates multiple agents:
     - **Researcher Agent**: Queries Neo4j graph for entities
     - **Retriever Agent**: Uses LlamaIndex to find relevant docs
     - **Synthesizer Agent**: Combines results with Claude
   - Final response generated

3. **Multi-Document Analysis**:
   - **CrewAI** orchestrates parallel document processing
   - Each agent uses **LlamaIndex** for document-specific retrieval
   - Results aggregated and synthesized

### Checking Render Service Status:
```bash
# Using MCP_Docker Render integration via Claude Code:
"List all services in workspace tea-d1vtdtre5dus73a4rb4g"
"Show me the logs for jb-llamaindex service"
"Show me the logs for jb-crewai service"
"What's the health status of both services?"
```

---

## 4. Remote Access & Networking

### ⬜ Tailscale VPN
- **Status**: ⬜ Needs setup
- **Required for**: Secure remote access to Mac Studio services (BGE models, Neo4j)
- **Installation**:
  ```bash
  # Install Tailscale on Mac Studio
  brew install --cask tailscale

  # Start and authenticate
  sudo tailscale up
  ```
- **Configuration**:
  - `TAILSCALE_MACHINE_NAME`: [Your Mac Studio Tailscale name]
  - `TAILSCALE_IP`: [Your Mac Studio Tailscale IP - format: 100.x.x.x]
- **Where to put**: `.env` file
- **How to get**:
  1. Go to https://login.tailscale.com/admin/machines
  2. Find your Mac Studio machine
  3. Copy the Tailscale IP (100.x.x.x)
- **Monthly Cost**: FREE (Personal plan for up to 20 devices)

---

## 5. Caching & Performance

### ⬜ Redis (Optional - for caching)
- **Status**: ⬜ Optional but recommended
- **Required for**: Tiered semantic caching (0.98+ similarity hits)
- **Options**:

  **Option A: Local Docker (FREE)**
  ```bash
  # Add to docker-compose.yml
  redis:
    image: redis:7-alpine
    container_name: empire-redis
    ports:
      - "6379:6379"
    volumes:
      - ./redis/data:/data
  ```
  - `REDIS_URL`: `redis://localhost:6379`

  **Option B: Upstash Redis (Serverless)**
  - Go to https://upstash.com/
  - Create Redis database
  - Copy connection string → `REDIS_URL`
  - **Cost**: FREE tier (10K commands/day) or $0.20/100K commands

- **Where to put**: `.env` file

---

## 6. Monitoring & Observability Stack

### ✅ Monitoring Services
- **Status**: ✅ Fully configured and ready
- **Required for**: Production observability, metrics, alerts
- **Services Included**:
  - **Prometheus** (Port 9090) - Metrics collection
  - **Grafana** (Port 3000) - Dashboards (admin/empiregrafana123)
  - **Alertmanager** (Port 9093) - Alert routing
  - **Redis** (Port 6379) - Celery broker (if not using above)
  - **Flower** (Port 5555) - Celery monitoring (admin/empireflower123)

### ✅ Quick Start
```bash
# Start all monitoring services
./start-monitoring.sh

# Verify services are running
docker ps | grep -E "prometheus|grafana|redis|flower"

# Test monitoring integration
python test_monitoring.py

# Run example app to see metrics
python example_app_with_monitoring.py
```

### ✅ Python Dependencies
```bash
# Install monitoring requirements
pip install -r requirements-monitoring.txt
# OR manually:
pip install prometheus-client celery redis flower
```

### ✅ FastAPI Integration Required
Add this minimum code to your FastAPI app:
```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

@app.get("/monitoring/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### ✅ Access URLs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/empiregrafana123)
- **Flower**: http://localhost:5555 (admin/empireflower123)
- **Alertmanager**: http://localhost:9093

### ✅ Environment Variables (Already in .env)
```bash
PROMETHEUS_ENABLED=true
GRAFANA_PORT=3000
CELERY_BROKER_URL=redis://localhost:6379/0
FLOWER_PORT=5555
```

### ✅ Documentation
- `monitoring/INTEGRATION_GUIDE.md` - Complete integration guide
- `monitoring/README.md` - Detailed monitoring docs
- `example_app_with_monitoring.py` - Working example
- `docker-compose.monitoring.yml` - Services config

---

## 7. File Security Scanning

### ⬜ VirusTotal API (File Upload Security)
- **Status**: ⬜ Needs API key
- **Purpose**: Malware scanning with 70+ antivirus engines for uploaded files
- **Required for**: Production file upload security (Layer 3 validation)
- **Free Tier**: 500 file uploads/day (effectively unlimited with hash-first approach)
- **Smart Hash-First Strategy**:
  1. Calculate SHA256 hash of file (instant, free)
  2. Check hash in VirusTotal database (FREE, unlimited lookups)
  3. Only upload if hash is unknown (saves 95% of quota)
  - **Result**: 500 uploads/day → ~10,000+ effective scans/day

**Required Credential**:
- `VIRUSTOTAL_API_KEY`: `<your-virustotal-api-key>`
- **Where to put**: `.env` file (see section 9)
- **How to get**:
  1. Go to https://www.virustotal.com/gui/home/upload
  2. Sign up for a free account
  3. Go to https://www.virustotal.com/gui/my-apikey
  4. Copy API key → Add to `.env` as `VIRUSTOTAL_API_KEY`

**Integration**:
```python
from app.services.virus_scanner import get_virus_scanner

# Scan a file for malware
virus_scanner = get_virus_scanner()
is_clean, error_msg, scan_results = await virus_scanner.scan_file(file_path)

if not is_clean:
    # File is malicious - reject upload
    raise HTTPException(status_code=400, detail=f"Malware detected: {error_msg}")
```

**Features**:
- **Multi-layer validation**: Works alongside basic validation (Layer 1) and MIME validation (Layer 2)
- **Production-ready**: Hash lookups are unlimited and free
- **Graceful degradation**: If API unavailable, uploads continue with warning
- **Detailed results**: Get scan stats from 70+ antivirus engines

**Monthly Cost**: FREE (hash lookups unlimited, 500 new file uploads/day on free tier)

---

## 8. MCP Servers to Configure

### ⬜ Supabase MCP
- **Status**: ⬜ Needs configuration
- **Purpose**: Direct SQL table creation, schema management, data queries
- **Configuration File**: `~/.config/claude-code/mcp_settings.json`
- **Setup**:
  ```json
  {
    "mcpServers": {
      "supabase": {
        "command": "npx",
        "args": ["-y", "@upstash/mcp-server-supabase"],
        "env": {
          "SUPABASE_URL": "https://xxxxx.supabase.co",
          "SUPABASE_SERVICE_KEY": "your-service-key-here"
        }
      }
    }
  }
  ```
- **How to test**:
  1. Restart Claude Desktop/Code
  2. Run: `/mcp list` to verify Supabase MCP is loaded
  3. Test with: "List all tables in Supabase"

### ⬜ Neo4j MCP (PRODUCTION)
- **Status**: ⬜ Needs configuration
- **Purpose**: PRODUCTION - Natural language graph queries via Claude Desktop/Code
- **Critical for**: Multi-modal access pattern (developers use Claude for graph queries)
- **Configuration File**: `~/.config/claude-code/mcp_settings.json`
- **Setup**:
  ```json
  {
    "mcpServers": {
      "neo4j": {
        "command": "docker",
        "args": ["run", "-i", "--rm",
                 "-e", "NEO4J_URI=bolt://host.docker.internal:7687",
                 "-e", "NEO4J_USERNAME=neo4j",
                 "-e", "NEO4J_PASSWORD=<your-password>",  # From .env
                 "neo4j/mcp-server-neo4j:latest"
        ]
      }
    }
  }
  ```
- **How to test**:
  1. Ensure Neo4j container is running: `docker ps | grep neo4j`
  2. Restart Claude Desktop/Code
  3. Test with: "Show me the Neo4j database schema"

### ⬜ n8n MCP (Optional)
- **Status**: ⬜ Optional (we're moving to FastAPI instead)
- **Note**: We decided to build a FastAPI web app instead of n8n workflows
- **Can skip** unless you want to keep n8n for other automation tasks

---

## 9. Environment Variables File Template

Create a `.env` file in the Empire directory with this template:

```bash
# ==========================================
# EMPIRE v7.2 - ENVIRONMENT VARIABLES
# ==========================================

# ----- Database & Storage -----
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-secure-password>  # Set in docker-compose.yml NEO4J_AUTH

SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_DB_PASSWORD=your-db-password-here

# ----- AI/ML Services -----
ANTHROPIC_API_KEY=sk-ant-api03-...
LLAMA_CLOUD_API_KEY=llx-...

# ----- Existing Render Services -----
RENDER_WORKSPACE_ID=tea-d1vtdtre5dus73a4rb4g

# LlamaIndex Service (Already Deployed)
LLAMAINDEX_SERVICE_URL=https://jb-llamaindex.onrender.com
LLAMAINDEX_SERVICE_ID=srv-d2nl1lre5dus73atm9u0
LLAMAINDEX_API_KEY=your-llamaindex-api-key-if-any

# CrewAI Service (Already Deployed)
CREWAI_SERVICE_URL=https://jb-crewai.onrender.com
CREWAI_SERVICE_ID=srv-d2n0hh3uibrs73buafo0
CREWAI_API_KEY=your-crewai-api-key-if-any

# ----- Local AI Models (Ollama) -----
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=bge-m3
RERANKER_MODEL=bge-reranker-v2-m3

# ----- Networking -----
TAILSCALE_IP=100.x.x.x
TAILSCALE_MACHINE_NAME=mac-studio

# ----- Caching (Optional) -----
REDIS_URL=redis://localhost:6379

# ----- Application Settings -----
APP_ENV=development
APP_PORT=8000
LOG_LEVEL=INFO

# ----- Security -----
SECRET_KEY=your-secret-key-for-jwt-signing
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,https://jb-llamaindex.onrender.com,https://jb-crewai.onrender.com

# ----- Feature Flags -----
ENABLE_QUERY_EXPANSION=true
ENABLE_RERANKING=true
ENABLE_SEMANTIC_CACHING=true
ENABLE_ADAPTIVE_CHUNKING=true
ENABLE_CREWAI_ORCHESTRATION=true
ENABLE_LLAMAINDEX_INTEGRATION=true
```

### Security Notes:
- **NEVER commit `.env` to git**
- Add `.env` to `.gitignore`
- Create `.env.example` with dummy values for team reference
- Use different keys for development vs production

---

## 10. Claude Desktop MCP Configuration

### Combined MCP Configuration File
**Location**: `~/.config/claude-code/mcp_settings.json`

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@upstash/mcp-server-supabase"],
      "env": {
        "SUPABASE_URL": "https://xxxxx.supabase.co",
        "SUPABASE_SERVICE_KEY": "your-service-key-here"
      }
    },
    "neo4j": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "NEO4J_URI=bolt://host.docker.internal:7687",
        "-e", "NEO4J_USERNAME=neo4j",
        "-e", "NEO4J_PASSWORD=<your-password>",  # From .env
        "neo4j/mcp-server-neo4j:latest"
      ]
    }
  }
}
```

---

## 11. Database Schema Setup (Via Supabase MCP)

Once Supabase MCP is configured, Claude can directly create these tables:

### Core Tables to Create:
1. **documents** - Parsed document metadata
2. **chunks** - Adaptive chunks with embeddings
3. **entities** - Extracted entities (synced to Neo4j)
4. **relationships** - Entity relationships (synced to Neo4j)
5. **queries** - Query history and analytics
6. **cache** - Semantic cache entries
7. **feedback** - User feedback on responses

### SQL Schemas Available:
- Full schemas documented in `SRS/Workflows/database_setup.md` (3,318 lines)
- Can be executed via Supabase MCP by Claude directly

### Neo4j Graph Schema:
- **Nodes**: Document, Entity, Policy, Contract, Person, Organization
- **Relationships**: MENTIONS, RELATED_TO, GOVERNS, SIGNED_BY
- Can be created via Neo4j MCP by Claude directly

---

## 12. FastAPI Development Setup

### Python Environment
```bash
# Create virtual environment
cd /path/to/Empire
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies (will be created during dev)
pip install fastapi uvicorn python-dotenv
pip install anthropic supabase neo4j redis
pip install llama-index llama-parse
pip install crewai requests  # For CrewAI integration
```

### Project Structure (To Be Created)
```
Empire/
├── .env                    # Environment variables (YOU create this)
├── .env.example            # Template (Claude will create)
├── .gitignore              # Add .env here
├── docker-compose.yml      # ✅ Already created
├── pyproject.toml          # Python dependencies
├── app/
│   ├── main.py            # FastAPI app
│   ├── config.py          # Load .env variables
│   ├── routers/           # API endpoints
│   ├── services/          # Business logic
│   │   ├── llamaindex.py  # LlamaIndex integration
│   │   ├── crewai.py      # CrewAI integration
│   │   ├── embeddings.py  # BGE-M3 embeddings
│   │   └── sync.py        # Neo4j ↔ Supabase sync
│   ├── models/            # Pydantic models
│   └── utils/             # Helper functions
├── tests/                 # Test suite
└── docs/                  # API documentation
```

---

## 13. Integration Patterns

### Pattern 1: Document Processing with LlamaIndex
```python
import requests
from app.config import settings

async def process_document(file_url: str):
    # Send to LlamaIndex service for parsing
    response = requests.post(
        f"{settings.LLAMAINDEX_SERVICE_URL}/parse",
        json={
            "file_url": file_url,
            "parse_instructions": "Extract structured data"
        }
    )
    parsed_doc = response.json()

    # Generate embeddings with local BGE-M3
    embeddings = await generate_embeddings(parsed_doc["chunks"])

    # Store in Supabase
    await store_in_supabase(parsed_doc, embeddings)

    # Sync entities to Neo4j
    await sync_to_neo4j(parsed_doc["entities"])
```

### Pattern 2: Complex Queries with CrewAI
```python
async def complex_query(user_query: str):
    # Use CrewAI to orchestrate multi-agent search
    response = requests.post(
        f"{settings.CREWAI_SERVICE_URL}/run-crew",
        json={
            "task": user_query,
            "agents": [
                {
                    "role": "researcher",
                    "goal": "Find relevant entities in Neo4j"
                },
                {
                    "role": "retriever",
                    "goal": "Get similar documents from Supabase"
                },
                {
                    "role": "synthesizer",
                    "goal": "Combine results with Claude"
                }
            ]
        }
    )
    return response.json()
```

### Pattern 3: Hybrid Search
```python
async def hybrid_search(query: str):
    # 1. Query expansion with Claude Haiku
    expanded = await expand_query(query)

    # 2. Vector search in Supabase
    vector_results = await supabase_vector_search(expanded)

    # 3. Graph search in Neo4j
    graph_results = await neo4j_graph_search(expanded)

    # 4. Rerank with BGE-Reranker (local)
    reranked = await rerank_results(vector_results + graph_results)

    return reranked
```

---

## 14. Pre-Development Checklist Summary

### Must Complete Before Development:
- [ ] Neo4j running: `docker-compose up -d`
- [ ] Neo4j accessible: http://localhost:7474
- [ ] Supabase project created (SMALL tier)
- [ ] Supabase credentials in `.env` file
- [ ] Anthropic API key obtained
- [ ] LlamaCloud API key obtained
- [ ] Ollama installed with BGE-M3 model
- [ ] Ollama installed with BGE-Reranker-v2
- [ ] Tailscale VPN setup on Mac Studio
- [ ] **Verify LlamaIndex service is running**: https://jb-llamaindex.onrender.com
- [ ] **Verify CrewAI service is running**: https://jb-crewai.onrender.com
- [ ] **Test LlamaIndex API** with sample document
- [ ] **Test CrewAI API** with sample task
- [ ] `.env` file created with all variables (including Render services)
- [ ] `.gitignore` includes `.env`
- [ ] Supabase MCP configured in Claude Desktop/Code
- [ ] Neo4j MCP configured in Claude Desktop/Code
- [ ] Test MCP connections work

### Optional But Recommended:
- [ ] Redis for caching (local Docker or Upstash)
- [ ] Test Tailscale remote access to Mac Studio

### Ready for Development When:
✅ All "Must Complete" items are checked
✅ Claude can access Supabase via MCP
✅ Claude can access Neo4j via MCP
✅ LlamaIndex and CrewAI services respond to health checks
✅ All API keys are in `.env` file
✅ Neo4j and Ollama are running

---

## 15. Testing Checklist

### Before Starting Development:
```bash
# 1. Test Neo4j connection
curl http://localhost:7474

# 2. Test Ollama embeddings
ollama run bge-m3 "test"

# 3. Test Ollama reranker
ollama run bge-reranker-v2-m3

# 4. Test Supabase connection (after setup)
curl https://xxxxx.supabase.co/rest/v1/ \
  -H "apikey: YOUR_ANON_KEY"

# 5. Test Claude API (after getting key)
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":1024,"messages":[{"role":"user","content":"Hello"}]}'

# 6. Test LlamaIndex service
curl https://jb-llamaindex.onrender.com/health

# 7. Test CrewAI service
curl https://jb-crewai.onrender.com/health

# 8. Test MCP connections in Claude Desktop
# Open Claude Desktop → Settings → MCP Servers
# Verify Supabase and Neo4j appear in list
```

### Using MCP_Docker to Check Render Services:
```
In Claude Code session:
"Show me the status of service srv-d2nl1lre5dus73atm9u0"  # LlamaIndex
"Show me the status of service srv-d2n0hh3uibrs73buafo0"  # CrewAI
"Show me the logs for jb-llamaindex service"
"Show me the logs for jb-crewai service"
"List all services in workspace tea-d1vtdtre5dus73a4rb4g"
```

---

## 16. Estimated Monthly Costs

| Service | Tier | Cost |
|---------|------|------|
| Supabase | SMALL (2GB) | $15 |
| Anthropic Claude API | Pay-as-you-go | $250-300 |
| LlamaCloud/Parse | 1K docs/month | $50 |
| **LlamaIndex (Render)** | **Already deployed** | **~$7-21** |
| **CrewAI (Render)** | **Already deployed** | **~$7-21** |
| Neo4j | Local Docker | FREE |
| BGE-M3 Embeddings | Local Ollama | FREE |
| BGE-Reranker | Local Ollama | FREE |
| Tailscale VPN | Personal | FREE |
| Redis | Local Docker | FREE |
| **TOTAL** | | **~$329-407/month** |

**Note**:
- Costs are within the $350-500/month budget from empire-arch.txt v7.2
- LlamaIndex and CrewAI costs depend on Render tier (Starter=$7, Standard=$21)
- Use MCP_Docker to check current Render plan: "Show me service details for srv-d2nl1lre5dus73atm9u0"

---

## 17. Next Steps After Checklist Complete

1. Run: `docker-compose up -d` to start Neo4j
2. Create Supabase project and get credentials
3. Verify LlamaIndex service: `curl https://jb-llamaindex.onrender.com/health`
4. Verify CrewAI service: `curl https://jb-crewai.onrender.com/health`
5. Create `.env` file with all credentials (including Render service URLs)
6. Configure Supabase and Neo4j MCPs
7. Test all connections
8. Start FastAPI development session with Claude Code

---

## Questions or Issues?

If you encounter any issues:
1. Check this file for troubleshooting steps
2. Verify all credentials are correct in `.env`
3. Test each service individually
4. Use MCP_Docker to check Render service health
5. Share error messages with Claude for debugging

---

**Last Updated**: 2025-01-01
**Empire Version**: v7.2 (Dual-Interface Architecture)
**Status**: Ready for credential setup phase
**Render Workspace**: tea-d1vtdtre5dus73a4rb4g
