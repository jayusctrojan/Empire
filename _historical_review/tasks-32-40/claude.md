# Claude Code Development Guide for Empire v7.2

## ⚠️ CRITICAL SECURITY POLICY - READ FIRST ⚠️

**ABSOLUTE RULE: NEVER PUT CREDENTIALS IN ANY DOCUMENTATION FILES**

**FORBIDDEN - The following MUST NEVER appear in .md, .txt, or ANY committed files:**
- ❌ API Keys (Anthropic, OpenAI, Supabase, B2, Soniox, etc.)
- ❌ Passwords (Neo4j, databases, services)
- ❌ Project IDs (Supabase project IDs, service IDs)
- ❌ Connection strings with real credentials
- ❌ Authentication tokens or secrets
- ❌ Private URLs or endpoints with sensitive data

**REQUIRED - ALL credentials MUST be:**
- ✅ Stored ONLY in `.env` file (which is gitignored)
- ✅ Referenced in docs as `<from .env>` or `<your-password>`
- ✅ Used as environment variables in code
- ✅ Never hardcoded anywhere

**REQUIRED - ALL documentation examples MUST use:**
- ✅ Placeholders: `<from .env>`, `<your-password>`, `<your-api-key>`
- ✅ Generic examples: `your-project-id`, `your-service-name`
- ✅ Clear references directing to `.env` file for actual values

**IF YOU FIND REAL CREDENTIALS IN DOCS:**
1. STOP immediately
2. Alert the user
3. Replace with placeholders
4. Add reference to `.env` file

**This is a ZERO-TOLERANCE policy. Security incidents have consequences.**

---

## 🚀 Quick Reference: AI Development Tools Available

**Primary IDE:** Visual Studio Code with Claude Code, Cline, and Continue.dev extensions

**AI Assistants:**
- **Claude Code** (CLI) - Primary architect for complex tasks
- **Cline** (VS Code) - Rapid feature implementation
- **Continue.dev** (VS Code) - Code completion and inline suggestions

**MCP Servers (Model Context Protocol) Available:**
1. **Claude Context MCP** - Maintains conversation context and project memory across sessions
2. **Chrome DevTools MCP** - Browser debugging, DOM inspection, network analysis, performance monitoring
3. **Ref MCP** - Official documentation reference (FastAPI, Neo4j, Supabase, Anthropic, LlamaIndex, Pydantic)
4. **TaskMaster MCP** - AI-powered task management, project planning, complexity analysis
5. **Render MCP** - Deployment and service management (web services, databases, logs, metrics, environment variables)
6. **Supabase MCP** - Direct PostgreSQL + pgvector operations (tables, queries, indexes, RLS policies)
7. **neo4j MCP** - Graph database queries via natural language → Cypher translation

**GitHub Operations:** Available directly via terminal/CLI using `gh` (GitHub CLI) and `git` commands - no MCP needed.

**Tailscale VPN:** Available via terminal/CLI using `tailscale` command for remote access, funnel exposure, and exit node management.

**Key Integration:** All MCPs work seamlessly with Claude Code CLI, providing direct access to databases, documentation, and deployment platforms.

---

## Overview
This document outlines all tools, MCPs, and development environments available for building Empire v7.2 with production-grade FastAPI + Celery architecture. Read this file at the start of each development session to understand your capabilities.

**Architecture Note**: Empire v7.2 uses a hybrid database production architecture:
- **Production Databases**:
  - PostgreSQL (Supabase) - Vector search, user data, sessions
  - Neo4j (Mac Studio Docker) - Knowledge graphs, entity relationships
  - Redis (Upstash/Local) - Caching and Celery broker
- **Production Services**: FastAPI + Celery on Render
- **Multi-Modal Access**:
  - REST/WebSocket APIs (FastAPI)
  - Neo4j MCP (Claude Desktop/Code for natural language graph queries)

---

## 1. Development Environment

### Primary IDE: Visual Studio Code
- **Location**: Main development workspace
- **AI Assistants Available**:
  - **Claude Code** (CLI) - Primary for architecture and complex tasks
  - **Cline** (VS Code extension) - Secondary for rapid iteration
  - **Continue.dev** (VS Code extension) - Code completion and refactoring

### Workflow:
1. **Claude Code**: Plan architecture, create schemas, set up infrastructure
2. **Cline**: Implement features rapidly within VS Code
3. **Continue.dev**: Code completion, refactoring, inline suggestions

---

## 2. MCP Servers Available

### 2.1 Claude Context MCP
**Purpose**: Maintain conversation context and project memory across sessions

**Capabilities**:
- Remember project decisions and architecture choices
- Track progress across multiple sessions
- Reference previous conversations and decisions
- Recall "why" behind implementation choices
- Maintain project history and evolution

**When to Use**:
- ✅ Starting a new Claude Code session
- ✅ Need to recall what was decided previously
- ✅ Continuing work from days/weeks ago
- ✅ Asking "what did we decide about X?"
- ✅ Understanding why a specific approach was chosen
- ✅ Tracking long-term project evolution

**Usage Examples**:
```
"Refer to our previous discussion about the dual-interface architecture"
"What did we decide about the embedding model?"
"Why did we choose LangGraph over just using CrewAI?"
"What was the reasoning behind the three-layer orchestration?"
"Remind me what we implemented in Task 46"
"What were the key decisions from last week's session?"
```

**Best Practices**:
- Use at the START of each session to recall context
- Reference when making architectural decisions
- Query when you need to understand historical choices
- Helps maintain consistency across long projects

---

### 2.2 Render MCP (Deployment & Service Management)
**Purpose**: Manage Render deployments, services, and infrastructure

**Capabilities**:
- **Web Services**:
  - Create and deploy FastAPI services
  - Configure environment variables
  - View logs and metrics
  - Scale services
  - Monitor service health

- **Databases**:
  - Create PostgreSQL instances
  - Manage Redis/KeyValue stores
  - Monitor database metrics
  - View connection strings

- **Static Sites**:
  - Deploy frontend applications
  - Configure build settings
  - Manage deployments

**Existing Render Deployments (IMPORTANT!):
**Workspace ID**: `tea-d1vtdtre5dus73a4rb4g`

**LlamaIndex Service** (Already Running):
- **Service ID**: `srv-d2nl1lre5dus73atm9u0`
- **URL**: https://jb-llamaindex.onrender.com
- **Purpose**: Document parsing, indexing, and retrieval
- **Status**: ACTIVE - Use this for document processing
- **Integration**:
  ```python
  LLAMAINDEX_SERVICE_URL = "https://jb-llamaindex.onrender.com"
  # Use for document parsing and indexing
  ```

**CrewAI Service** (CRITICAL - Milestone 8):
- **Service ID**: `srv-d2n0hh3uibrs73buafo0`
- **URL**: https://jb-crewai.onrender.com
- **Purpose**: Multi-agent AI orchestration and content analysis workflows
- **Status**: ACTIVE - REQUIRED for Milestone 8 implementation
- **Workflows**:
  - Multi-agent task coordination
  - Content analysis automation
  - Multi-document processing
  - Framework extraction
  - Long-running async tasks via Celery
- **Integration**:
  ```python
  CREWAI_SERVICE_URL = "https://jb-crewai.onrender.com"
  # Use for multi-agent task coordination
  # Milestone 8: Multi-agent workflows for content analysis
  ```

**Usage Examples**:
```python
# Existing Services
"Show me the status of jb-llamaindex service"
"Show me the logs for jb-crewai service"
"List all services in workspace tea-d1vtdtre5dus73a4rb4g"
"What's the health status of srv-d2nl1lre5dus73atm9u0?"
"Show me the environment variables for the llamaindex service"

# New Services
"Deploy the FastAPI app to Render"
"Create a PostgreSQL database on Render"
"Update the environment variables for service srv-xyz"
```

**Configuration**: Added via `claude mcp add --transport http` command with bearer token

---

### 2.3 Neo4j MCP (PRODUCTION)
**Purpose**: Production knowledge graph queries via natural language (essential for multi-modal access)

**Role in Production**:
- Primary interface for knowledge graph queries via Claude Desktop/Code
- Enables natural language to Cypher translation
- Provides graph traversal and relationship analysis
- Works alongside PostgreSQL for comprehensive data access

**Capabilities**:
- **Schema Management**:
  - Create nodes and relationships
  - Define indexes and constraints
  - View database schema

- **Data Operations**:
  - Insert entities and relationships
  - Query graph patterns
  - Update properties
  - Delete nodes/relationships

- **Natural Language Queries**:
  - "Show me all policies related to employee benefits"
  - "Find documents mentioning both contracts and compliance"
  - "What entities are connected to John Smith?"

**Connection Details**:
- **URI (TLS Enabled)**: `bolt+ssc://localhost:7687` (local) or `bolt+ssc://100.119.86.6:7687` (via Tailscale)
- **Legacy URI**: `bolt://localhost:7687` (still supported, OPTIONAL mode)
- **Username**: `neo4j`
- **Password**: `<from .env>`  *(See .env file for actual password)*
- **Web Interface**: http://localhost:7474
- **TLS**: Enabled with self-signed certificates (365-day validity)
- **Certificates**: Mounted at `/certificates/bolt/` in container

**Usage Examples**:
```cypher
# Schema Creation
"Create a Document node with properties: id, title, content, embedding"
"Create a MENTIONS relationship between Document and Entity nodes"
"Add a vector index on Document.embedding for similarity search"

# Data Queries
"Find all documents related to 'compliance' within 2 hops"
"Show me the subgraph around entity 'Acme Corp'"
"What's the shortest path between Policy A and Contract B?"

# Analytics
"Count the number of entities by type"
"Find the most connected documents"
"Show me orphaned nodes with no relationships"
```

**Configuration**:
```json
{
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
```

---

### 2.4 Supabase MCP
**Purpose**: Direct SQL operations on Supabase PostgreSQL + pgvector

**Capabilities**:
- **Schema Management**:
  - Create tables with pgvector columns
  - Define foreign keys and constraints
  - Create indexes (B-tree, GiST, HNSW)
  - Manage RLS policies

- **Data Operations**:
  - INSERT, UPDATE, DELETE operations
  - Complex SQL queries with JOINs
  - Vector similarity search
  - Aggregate queries

- **Database Administration**:
  - View table schemas
  - Check table sizes and stats
  - Manage extensions (pgvector, uuid-ossp)
  - Create functions and triggers

**Connection Details**:
- **URL**: `https://[project-id].supabase.co`
- **Keys**: In `.env` file (see PRE_DEV_CHECKLIST.md)

**Usage Examples**:
```sql
-- Schema Creation
"Create a table called 'documents' with columns: id, title, content, embedding (vector 1024)"
"Add an HNSW index on documents.embedding for fast similarity search"
"Create RLS policy for documents table"

-- Data Operations
"Insert a new document with title 'Policy A' and content '...'"
"Find the top 10 most similar documents to vector [0.1, 0.2, ...]"
"Update document ID 123 to set status = 'processed'"

-- Analytics
"Show me the table sizes for all tables"
"Count documents by type"
"Find documents with null embeddings"
```

**Schema Reference**:
- Full schemas in `SRS/Workflows/database_setup.md` (3,318 lines, 37+ tables)
- Can be referenced during development

**Configuration**:
```json
{
  "supabase": {
    "command": "npx",
    "args": ["-y", "@upstash/mcp-server-supabase"],
    "env": {
      "SUPABASE_URL": "https://xxxxx.supabase.co",
      "SUPABASE_SERVICE_KEY": "your-service-key"
    }
  }
}
```

---

### 2.5 Chrome DevTools MCP
**Purpose**: Frontend UI troubleshooting and debugging

**Capabilities**:
- **DOM Inspection**:
  - View page structure
  - Inspect element styles
  - Debug CSS issues

- **Console Debugging**:
  - View JavaScript errors
  - Run console commands
  - Monitor network requests

- **Performance Monitoring**:
  - Measure page load times
  - Identify bottlenecks
  - Analyze rendering performance

- **Network Analysis**:
  - View API requests/responses
  - Check payload sizes
  - Debug CORS issues

**Usage Examples**:
```
"Inspect the search button element and show me its styles"
"What JavaScript errors are showing in the console?"
"Show me the network requests when I click 'Search'"
"Why is the page loading slowly? Run a performance audit"
```

**Best For**:
- Debugging Gradio/Streamlit chat UI
- Testing FastAPI responses in browser
- Troubleshooting CSS layout issues
- Monitoring API call performance

---

### 2.6 Ref MCP (Documentation Reference)
**Purpose**: Check official documentation for proper schemas, formats, and best practices

**Capabilities**:
- **API Documentation**:
  - FastAPI schemas and patterns
  - Supabase client usage
  - Neo4j Cypher syntax
  - Anthropic Claude API

- **Library References**:
  - LangChain/LlamaIndex patterns
  - Pydantic model definitions
  - SQLAlchemy ORM usage

- **Best Practices**:
  - Error handling patterns
  - Async/await usage
  - Type hints and validation
  - Security considerations

**Usage Examples**:
```
"Check the FastAPI docs for proper CORS configuration"
"What's the correct Neo4j Cypher syntax for vector similarity search?"
"Show me the Supabase Python client authentication pattern"
"What's the proper way to handle Anthropic API rate limits?"
```

**Supported Documentation**:
- **FastAPI**: https://fastapi.tiangolo.com/
- **Neo4j**: https://neo4j.com/docs/
- **Supabase**: https://supabase.com/docs
- **Anthropic**: https://docs.anthropic.com/
- **LlamaIndex**: https://docs.llamaindex.ai/
- **Pydantic**: https://docs.pydantic.dev/

---

## 3. AI Coding Assistants in VS Code

### 3.1 Claude Code (CLI) - **YOU ARE HERE**
**Role**: Primary architect, orchestrator, and task delegator

**Best For**:
- System architecture design
- Database schema creation
- MCP integration and testing
- Complex multi-file refactoring
- Git operations and PR management
- **DELEGATING TO OTHER TOOLS**

**Strengths**:
- Access to all MCPs
- Can read entire codebase
- Long-form planning and documentation
- Direct terminal access
- **Can instruct user to switch to Cline or Continue.dev**

**Usage Pattern**:
```bash
# Start Claude Code session
claude-code

# Example prompts:
"Create the Neo4j graph schema for Empire entities"
"Set up the Supabase tables using the Supabase MCP"
"Review the codebase and suggest performance optimizations"
"Create a PR with the new graph sync feature"
```

**CRITICAL - When to Delegate**:
- **Delegate to Cline**: When implementing a complete feature in 1-3 files
- **Delegate to Continue.dev**: When user is actively writing code and needs inline help
- See section 4 below for explicit handoff triggers

---

### 3.2 Cline (VS Code Extension)
**Role**: Rapid feature implementation within VS Code with visual feedback

**Best For**:
- Implementing a single complete feature (1-3 files)
- File-by-file editing with visual diffs
- Inline code generation with immediate preview
- Testing and debugging specific functions
- Iterative development with quick feedback

**Strengths**:
- Native VS Code integration
- Fast context switching
- **Visual diff previews** - see changes before accepting
- Direct file manipulation
- Can run tests and see results inline

**When Claude Code Should Delegate to Cline**:
- ✅ User says: "implement X feature"
- ✅ User says: "add error handling to Y service"
- ✅ User says: "create a new endpoint for Z"
- ✅ Task involves 1-3 specific files
- ✅ User wants to see visual diffs

**How to Delegate**:
```
Claude Code should respond:
"I've planned the implementation. Now I recommend using Cline in VS Code for the actual coding:

1. Open VS Code to the Empire project
2. Click the Cline icon in the sidebar (chat bubble)
3. Copy this prompt to Cline:

'Implement [feature] in [file]. Here's the plan:
- [Step 1]
- [Step 2]
- [Step 3]

Use the patterns from [reference file].'

4. Review the visual diff before accepting
5. Come back here when done and I'll help test it."
```

**Example Prompts for Cline**:
```
"Add error handling to app/services/embedding_service.py"
"Create a new route /api/documents/upload in app/routes/documents.py"
"Refactor the query_expansion function to use async/await"
"Add type hints to all functions in app/services/graph_sync.py"
```

---

### 3.3 Continue.dev (VS Code Extension)
**Role**: Real-time code completion and inline suggestions while coding

**Best For**:
- Autocomplete while typing (Tab completion)
- Function generation from comments
- Quick inline refactoring (Cmd+I)
- Code explanation for specific lines
- Unit test generation from existing functions

**Strengths**:
- Real-time suggestions as you type
- Minimal context switching
- Tab completion (no interruption)
- Comment-to-code generation
- Works alongside your active coding

**When Claude Code Should Recommend Continue.dev**:
- ✅ User is actively writing code in VS Code
- ✅ User needs autocomplete suggestions
- ✅ User wants to write comments and generate code
- ✅ User needs quick inline explanations
- ❌ NOT for full feature implementation (use Cline)

**How to Recommend**:
```
Claude Code should respond:
"For this type of incremental coding, I recommend using Continue.dev:

1. Open the file in VS Code: [filename]
2. Press Cmd+L to open Continue.dev chat
3. Or write a comment describing what you need and press Tab

Example:
# Calculate similarity score between query and document embeddings
# [Press Tab - Continue.dev generates the function]

Continue.dev will provide real-time suggestions as you type."
```

**Keyboard Shortcuts**:
- `Cmd+L` - Open Continue chat
- `Cmd+I` - Inline edit at cursor
- `Tab` - Accept suggestion

**Example Usage**:
```python
# Generate embeddings using BGE-M3 and store in Supabase
# [Press Tab - Continue.dev generates the function]

def generate_embeddings(text: str) -> list[float]:
    # [Continue.dev suggests implementation]
    pass
```

---

## 4. Recommended Development Workflow with Tool Delegation

### 🎯 DECISION TREE: Which Tool to Use?

**Question 1: What type of work is this?**

```
┌─ Architecture/Planning/Multiple Files?
│  └─> Use Claude Code (stay in CLI)
│
├─ Implementing 1-3 file feature with visual feedback?
│  └─> DELEGATE TO CLINE (tell user to open VS Code)
│
├─ User is actively coding and needs autocomplete?
│  └─> RECOMMEND CONTINUE.DEV (Cmd+L or Tab)
│
└─ Database operations/MCP tasks?
   └─> Use Claude Code (stay in CLI)
```

### Phase 1: Architecture & Planning (Claude Code - YOU)

**What YOU (Claude Code) Do**:
1. Design system architecture using knowledge of codebase
2. Create database schemas via **Neo4j MCP** and **Supabase MCP**
3. Set up project structure and dependencies
4. Create initial boilerplate code
5. **THEN DELEGATE to Cline for implementation**

**Example Session**:
```
User: "I need to add a new document upload feature"

Claude Code Response:
"I'll plan this feature for you:

ARCHITECTURE PLAN:
1. New route: POST /api/documents/upload
2. Service: app/services/upload_service.py
3. Validation: Pydantic model for upload request
4. Storage: B2 via existing client

Now let's implement this with Cline for visual feedback:

🔧 SWITCH TO CLINE:
1. Open VS Code
2. Click Cline icon (sidebar)
3. Paste this prompt:

'Create document upload endpoint in app/routes/documents.py:
- POST /api/documents/upload
- Accept multipart file upload
- Validate file type (PDF, DOCX, TXT)
- Use UploadService from app/services/upload_service.py
- Return upload ID and status
- Follow patterns from app/routes/query.py'

Come back when Cline is done and I'll help you test it."
```

### Phase 2: Feature Implementation (DELEGATE TO CLINE)

**EXPLICIT HANDOFF TRIGGERS** - When Claude Code should stop and delegate:

**Trigger 1: "Implement [feature]"**
```
User: "Implement user authentication"

Claude Code MUST respond:
"I recommend using Cline for this implementation:

📱 OPEN CLINE IN VS CODE:
1. Click Cline icon in sidebar
2. Use this prompt:

'Implement JWT authentication in app/auth/:
- Create auth_service.py with login/register functions
- Use bcrypt for password hashing
- Generate JWT tokens with 24hr expiry
- Add authentication middleware
- Follow FastAPI security patterns'

Review the diffs carefully before accepting."
```

**Trigger 2: "Add [specific functionality] to [file]"**
```
User: "Add error handling to the embedding service"

Claude Code MUST respond:
"This is perfect for Cline's visual diff feature:

📱 SWITCH TO CLINE:
'Add comprehensive error handling to app/services/embedding_service.py:
- Wrap Ollama calls in try/except
- Handle connection errors
- Log errors with structlog
- Return meaningful error messages
- Add retry logic (max 3 attempts)'

You'll see exactly what's changing before accepting."
```

**Trigger 3: "Create new [file/route/service]"**
```
User: "Create a new analytics service"

Claude Code MUST respond:
"Let's use Cline to create this new service:

📱 USE CLINE:
'Create app/services/analytics_service.py:
- Track query metrics (count, latency, errors)
- Store metrics in Supabase analytics table
- Export metrics to Prometheus
- Use singleton pattern
- Follow structure of app/services/arcade_service.py'

Cline will create the file and show you a preview."
```

### Phase 3: Active Coding (RECOMMEND CONTINUE.DEV)

**When to Recommend Continue.dev**:

**Scenario 1: User is writing code in VS Code**
```
User: "I'm writing a function but need help with the implementation"

Claude Code MUST respond:
"Since you're actively coding, use Continue.dev for real-time help:

⌨️ IN VS CODE:
1. Write a comment describing what you need:
   # Calculate cosine similarity between embeddings
2. Press Tab to accept the suggestion
3. Or press Cmd+I for inline edit

Continue.dev will autocomplete as you type."
```

**Scenario 2: User needs autocomplete/suggestions**
```
User: "Can you help me write this function?"

Claude Code MUST respond:
"For autocomplete while coding, use Continue.dev:

⌨️ CONTINUE.DEV (Cmd+L):
1. Open your file in VS Code
2. Press Cmd+L to open Continue chat
3. Describe what you're building
4. Get suggestions as you type

Or write comments and press Tab for instant code generation."
```

### Phase 4: Testing & Debugging

**Claude Code Stays Active For**:
1. Use **Chrome DevTools MCP** for frontend debugging
2. Use **Neo4j MCP** to verify graph data
3. Use **Supabase MCP** to check vector storage
4. Use **Ref MCP** to verify API usage
5. Run pytest and analyze failures

**BUT DELEGATE TO CLINE for fixes**:
```
User: "The test is failing, can you fix it?"

Claude Code:
"I see the issue in the test. Let's fix it with Cline:

📱 USE CLINE:
'Fix the failing test in tests/test_upload.py:
- The mock is not properly configured
- Add missing return_value for B2 client
- Update assertion to match actual response format'

You'll see the exact changes in the diff."
```

### Phase 5: Deployment (Claude Code)

**YOU Stay Active**:
1. Use **Claude Code** with **Render MCP** to deploy to Render
2. Use **GitHub CLI** (`gh`) to create PR and merge to main via terminal
3. Monitor logs and metrics via **Render MCP**
4. Set up environment variables via **Render MCP**

---

### 🔄 COMPLETE WORKFLOW EXAMPLE

**User Request**: "Add rate limiting to the API"

**Step 1: Claude Code Plans (YOU)**
```
"I'll plan the rate limiting implementation:

ARCHITECTURE:
1. Install slowapi: pip install slowapi
2. Add middleware in app/main.py
3. Configure limits: 100 requests/minute per IP
4. Store state in Redis

Now let's implement with Cline..."
```

**Step 2: Delegate to Cline**
```
"📱 SWITCH TO CLINE IN VS CODE:

Prompt for Cline:
'Add rate limiting to app/main.py:
- Import slowapi and configure limiter
- Add middleware with 100/minute limit
- Use Redis for state storage
- Add rate limit headers to responses
- Handle 429 errors gracefully'

Review the changes, then come back here."
```

**Step 3: User Returns to Claude Code**
```
User: "Done with Cline, what's next?"

Claude Code:
"Great! Now let's test the rate limiting:
1. I'll update the requirements.txt
2. We'll deploy to Render with the Render MCP
3. Monitor the logs to verify it's working

Let me handle the deployment..."
```

---

### 📋 QUICK REFERENCE: When to Use Each Tool

| Scenario | Tool | Why |
|----------|------|-----|
| Plan architecture | Claude Code | Full codebase access, MCP integration |
| Implement feature (1-3 files) | **Cline** | Visual diffs, focused implementation |
| Active coding with autocomplete | **Continue.dev** | Real-time suggestions, Tab completion |
| Multi-file refactoring | Claude Code | See all dependencies |
| Create database schema | Claude Code | Neo4j/Supabase MCP access |
| Add error handling to service | **Cline** | See exact changes in diff |
| Write function with autocomplete | **Continue.dev** | Comment-to-code generation |
| Deploy to production | Claude Code | Render MCP integration |
| Debug with browser tools | Claude Code | Chrome DevTools MCP |
| Fix failing test | **Cline** | Visual diff of test changes |
| Generate unit tests | **Continue.dev** | Quick test generation from code |
| Git operations | Claude Code | Full git integration |
| Recall previous decisions | Claude Code | Claude Context MCP for session memory |

---

### ⚠️ IMPORTANT RULES FOR CLAUDE CODE

**When user requests implementation work, YOU MUST**:
1. ✅ Plan the architecture first
2. ✅ Identify which files will change
3. ✅ If 1-3 files → **DELEGATE TO CLINE**
4. ✅ If active coding → **RECOMMEND CONTINUE.DEV**
5. ✅ Provide specific prompts for the other tools
6. ✅ Tell user to come back after they're done

**DO NOT**:
- ❌ Implement features directly when Cline would be better
- ❌ Write code inline when user is in VS Code (recommend Continue.dev)
- ❌ Skip the delegation step
- ❌ Assume user knows when to switch tools

---

## 5. Monitoring and Observability Stack (Milestone 6)

### Overview
Empire v7.2 includes comprehensive monitoring using Prometheus, Grafana, and supporting services for metrics, alerting, and visualization.

### Monitoring Services Available

#### **Prometheus** (Port 9090)
- Metrics collection and storage
- Time-series database
- Alert evaluation
- Scrapes metrics from all Empire services

#### **Grafana** (Port 3000)
- Visualization dashboards
- Custom Empire dashboard pre-configured
- Credentials: admin/empiregrafana123

#### **Redis** (Port 6379)
- Celery task broker
- Cache backend
- Session storage

#### **Flower** (Port 5555)
- Celery task monitoring UI
- Worker status and task history
- Credentials: admin/empireflower123

#### **Alertmanager** (Port 9093)
- Alert routing and notifications
- Email/Slack integration ready
- Grouped and silenced alerts

### Quick Start Monitoring
```bash
# Start all monitoring services
./start-monitoring.sh

# Test monitoring integration
python test_monitoring.py

# Run example app with full metrics
python example_app_with_monitoring.py
```

### Required for Your FastAPI App
**Minimum integration** - Add this to your FastAPI app:
```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

@app.get("/monitoring/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### Monitoring Files
- `docker-compose.monitoring.yml` - Docker services configuration
- `monitoring/prometheus.yml` - Prometheus config
- `monitoring/alert_rules.yml` - Alert definitions
- `monitoring/INTEGRATION_GUIDE.md` - Complete integration guide
- `example_app_with_monitoring.py` - Working example
- `test_monitoring.py` - Verification script

### Access URLs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/empiregrafana123)
- **Flower**: http://localhost:5555 (admin/empireflower123)
- **Alertmanager**: http://localhost:9093

### Environment Variables (Already in .env)
```bash
PROMETHEUS_ENABLED=true
GRAFANA_PORT=3000
CELERY_BROKER_URL=redis://localhost:6379/0
FLOWER_PORT=5555
```

---

## 7. Empire v7.2 Specific Tools

### Local Services (Running on Mac Studio via Tailscale)

#### Ollama (BGE-M3 Embeddings)
```bash
# Generate embeddings
curl http://localhost:11434/api/embeddings -d '{
  "model": "bge-m3",
  "prompt": "California insurance policy"
}'
```

**Integration**:
```python
from langchain.embeddings import OllamaEmbeddings

embeddings = OllamaEmbeddings(
    base_url="http://localhost:11434",
    model="bge-m3"
)
```

#### Ollama (BGE-Reranker-v2)
```bash
# Rerank results
curl http://localhost:11434/api/generate -d '{
  "model": "bge-reranker-v2-m3",
  "prompt": "query: California insurance\ndoc: ...",
  "stream": false
}'
```

**Integration**:
```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainCompressor

# Use BGE-Reranker for compression
compressor = LLMChainCompressor.from_llm(
    OllamaLLM(model="bge-reranker-v2-m3")
)
```

---

### Tailscale CLI (Remote Access & Networking)

Tailscale provides secure remote access to Mac Studio services and exit node functionality for traveling.

#### Common Tailscale Commands
```bash
# Check Tailscale status
tailscale status

# Enable exit node (route all traffic through Mac Studio)
tailscale up --advertise-exit-node --accept-routes

# Expose local service via public HTTPS (Funnel)
tailscale funnel 8081

# Check current funnel status
tailscale funnel status

# Set custom hostname (optional)
tailscale set --hostname jb-studio

# Get Tailscale IP
tailscale ip -4

# SSH to machine via Tailscale
ssh user@machine-name

# Stop Tailscale
tailscale down
```

**Note**: Tailscale configuration details (machine name, IP, funnel URL) are stored in `.env` file and should not be committed to GitHub.

---

### Cloud Services (API Keys Required)

#### Anthropic Claude API
```python
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Query expansion with Claude Haiku
response = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=150,
    messages=[{
        "role": "user",
        "content": f"Generate 4-5 query variations for: {query}"
    }]
)
```

#### LlamaCloud / LlamaParse
```python
from llama_parse import LlamaParse

parser = LlamaParse(
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    result_type="markdown",
    parsing_instruction="Focus on structured data"
)

documents = parser.load_data("./contract.pdf")
```

---

### Existing Render Services (Already Deployed)

#### Empire FastAPI Service (Production) - Task 46: LangGraph + Arcade.dev Integration
**URL**: https://jb-empire-api.onrender.com
**Service ID**: `srv-d44o2dq4d50c73elgupg`
**Plan**: Starter ($7/month)
**Region**: Oregon

**Purpose**: Main FastAPI REST API for Empire v7.3
**Health Check**: https://jb-empire-api.onrender.com/health
**Docs**: https://jb-empire-api.onrender.com/docs

#### Empire Chat UI (Production) - Task 26: Chat UI Implementation
**URL**: https://jb-empire-chat.onrender.com
**Service ID**: `srv-d47ptdmr433s739ljolg`
**Plan**: Starter ($7/month)
**Region**: Oregon

**Purpose**: Gradio-based chat interface for end users
**Features**: Real-time streaming, auto-routing, error handling with retry logic
**Integration**: Direct connection to Task 46 LangGraph + Arcade.dev endpoints

**Task 46 - Query Endpoints (LangGraph + Arcade.dev):**
- **Health**: GET `/api/query/health` - Service health and component status
- **Auto-routed Query**: POST `/api/query/auto` - Intelligent workflow routing (LangGraph/CrewAI/Simple)
- **Adaptive Query (Sync)**: POST `/api/query/adaptive` - LangGraph 5-node adaptive workflow
- **Adaptive Query (Async)**: POST `/api/query/adaptive/async` - Celery background task
- **Auto-routed Query (Async)**: POST `/api/query/auto/async` - Async auto-routing
- **Batch Processing**: POST `/api/query/batch` - Multiple queries in parallel
- **Task Status**: GET `/api/query/status/{task_id}` - Check async task progress
- **Available Tools**: GET `/api/query/tools` - List Arcade.dev + internal tools

**Environment Variables (Configured on Render):**
```bash
ARCADE_API_KEY=<from .env>  # See .env file for actual value
ARCADE_ENABLED=true
LANGGRAPH_DEFAULT_MODEL=claude-3-5-haiku-20241022
```

**Workflow Router:**
The system intelligently routes queries to the appropriate workflow:
- **LangGraph**: Adaptive queries needing refinement, external data, iterative research
- **CrewAI**: Multi-agent document processing, complex analysis workflows
- **Simple RAG**: Direct knowledge base lookups, straightforward queries

**Integration Example**:
```python
import requests

# Auto-routed query (system chooses best workflow)
response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/auto",
    json={
        "query": "What are California insurance requirements?",
        "max_iterations": 3
    }
)

# Returns workflow type + results
result = response.json()
# {"answer": "...", "workflow_type": "langgraph", "iterations": 2, ...}

# Async query for long-running tasks
response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/adaptive/async",
    json={"query": "Complex research task", "max_iterations": 3}
)
task_id = response.json()["task_id"]

# Poll for results
status = requests.get(
    f"https://jb-empire-api.onrender.com/api/query/status/{task_id}"
)
```

#### Empire Celery Worker (Production)
**Service ID**: `srv-d44oclodl3ps73bg8rmg`
**Plan**: Starter ($7/month)
**Region**: Oregon

**Purpose**: Background task processing with Celery
**Tasks**: Document processing, embeddings, graph sync, CrewAI workflows

#### Empire Redis (Production)
**Service ID**: `red-d44og3n5r7bs73b2ctbg`
**Plan**: Free tier
**Region**: Oregon

**Purpose**: Caching and Celery message broker
**Internal URL**: redis://red-d44og3n5r7bs73b2ctbg

#### LlamaIndex Service
**URL**: https://jb-llamaindex.onrender.com
**Service ID**: `srv-d2nl1lre5dus73atm9u0`

**Purpose**: Document parsing, indexing, and vector retrieval

**Integration**:
```python
import requests
import os

LLAMAINDEX_BASE_URL = os.getenv("LLAMAINDEX_SERVICE_URL")

# Parse a document
def parse_document(file_url: str):
    response = requests.post(
        f"{LLAMAINDEX_BASE_URL}/parse",
        json={
            "file_url": file_url,
            "parse_instructions": "Extract structured data"
        },
        headers={"Authorization": f"Bearer {os.getenv('LLAMAINDEX_API_KEY')}"}
    )
    return response.json()

# Create an index
def create_index(documents: list):
    response = requests.post(
        f"{LLAMAINDEX_BASE_URL}/index/create",
        json={"documents": documents}
    )
    return response.json()

# Query the index
def query_index(index_id: str, query: str):
    response = requests.post(
        f"{LLAMAINDEX_BASE_URL}/index/{index_id}/query",
        json={"query": query, "top_k": 10}
    )
    return response.json()
```

**Common Use Cases**:
- Parse PDFs, Word docs, contracts
- Create searchable indexes
- Retrieve relevant chunks for RAG
- Extract structured data from documents

---

#### CrewAI Service
**URL**: https://jb-crewai.onrender.com
**Service ID**: `srv-d2n0hh3uibrs73buafo0`

**Purpose**: Multi-agent AI orchestration for complex workflows

**Integration**:
```python
import requests
import os

CREWAI_BASE_URL = os.getenv("CREWAI_SERVICE_URL")

# Run a crew of agents
def run_crew(task: str, agents_config: list):
    response = requests.post(
        f"{CREWAI_BASE_URL}/run-crew",
        json={
            "task": task,
            "agents": agents_config
        },
        headers={"Authorization": f"Bearer {os.getenv('CREWAI_API_KEY')}"}
    )
    return response.json()

# Example: Multi-document analysis
def analyze_multiple_docs(doc_ids: list, analysis_type: str):
    crew_config = [
        {
            "role": "document_parser",
            "goal": "Parse all documents and extract key information",
            "tools": ["llamaindex"],
            "doc_ids": doc_ids
        },
        {
            "role": "entity_extractor",
            "goal": "Extract entities and relationships",
            "tools": ["neo4j"]
        },
        {
            "role": "synthesizer",
            "goal": f"Synthesize findings for {analysis_type}",
            "tools": ["claude"]
        }
    ]
    return run_crew(
        task=f"Perform {analysis_type} on documents: {doc_ids}",
        agents_config=crew_config
    )
```

**Common Use Cases**:
- Complex multi-step research tasks
- Coordinated document analysis
- Multi-agent information synthesis
- Workflow orchestration with multiple AI services

---

### How LlamaIndex & CrewAI Work Together

**Document Processing Pipeline**:
```python
async def process_document_with_crew(file_url: str):
    # 1. LlamaIndex: Parse and chunk document
    parsed = parse_document(file_url)

    # 2. CrewAI: Coordinate multi-agent processing
    result = run_crew(
        task="Process document and extract insights",
        agents_config=[
            {
                "role": "parser",
                "goal": "Use LlamaIndex to create searchable chunks",
                "service": "llamaindex"
            },
            {
                "role": "embedder",
                "goal": "Generate embeddings with BGE-M3",
                "service": "ollama"
            },
            {
                "role": "storer",
                "goal": "Store in Supabase and sync to Neo4j",
                "service": "supabase"
            }
        ]
    )
    return result

# Complex Query Flow
async def complex_query(user_query: str):
    # Use CrewAI to orchestrate:
    # 1. Query expansion (Claude Haiku)
    # 2. Vector search (Supabase via LlamaIndex)
    # 3. Graph traversal (Neo4j)
    # 4. Synthesis (Claude Sonnet)

    result = run_crew(
        task=user_query,
        agents_config=[
            {"role": "expander", "tool": "claude-haiku"},
            {"role": "retriever", "tool": "llamaindex"},
            {"role": "graph_searcher", "tool": "neo4j"},
            {"role": "synthesizer", "tool": "claude-sonnet"}
        ]
    )
    return result
```

---

## 8. Development Checklist for Each Session

### Before Starting:
- [ ] Read this claude.md file
- [ ] Check PRE_DEV_CHECKLIST.md for credentials
- [ ] Verify Neo4j is running: `docker ps | grep neo4j`
- [ ] Verify Ollama is running: `ollama list`
- [ ] **Verify LlamaIndex service**: `curl https://jb-llamaindex.onrender.com/health`
- [ ] **Verify CrewAI service**: `curl https://jb-crewai.onrender.com/health`
- [ ] **Check monitoring stack** (if needed): `./start-monitoring.sh` and verify at http://localhost:3000
- [ ] Check MCP connections: Run test queries on Neo4j and Supabase MCPs
- [ ] Load `.env` variables

### During Development:
- [ ] Use appropriate tool for the task (Claude Code vs Cline vs Continue.dev)
- [ ] Reference Ref MCP for API documentation
- [ ] Test changes with Neo4j/Supabase MCPs
- [ ] Use Chrome DevTools MCP for frontend issues
- [ ] Commit frequently with clear messages

### Before Ending Session:
- [ ] Test all changes locally
- [ ] Commit and push to GitHub
- [ ] Update documentation if needed
- [ ] Note any blockers or next steps

---

## 9. Common MCP Workflows

### Create Database Schema
```
Claude Code � Use Supabase MCP:
"Create the documents table with vector embeddings as defined in database_setup.md"

Claude Code � Use Neo4j MCP:
"Create the Entity and Document nodes with relationships"
```

### Deploy to Render
```
Claude Code � Use Render MCP:
"Deploy the FastAPI app to Render with these environment variables..."
"Show me the deployment logs"
```

### Debug Frontend
```
Claude Code � Use Chrome DevTools MCP:
"The search button isn't working. Inspect the console for errors"
"Show me the network request when I submit the form"
```

### Check API Documentation
```
Claude Code � Use Ref MCP:
"What's the correct way to create a vector index in Supabase?"
"Show me the FastAPI pattern for file upload endpoints"
```

### Search Codebase
```bash
# Use grep/ripgrep directly via terminal
grep -r "BGE-M3" .
rg "document.*pars" --type python

# Use GitHub CLI for repo-wide search
gh search code "BGE-M3" --repo owner/repo
```

---

## 10. Environment Variables Reference

All credentials should be in `.env` file (see PRE_DEV_CHECKLIST.md):

```bash
# Databases
NEO4J_URI=bolt+ssc://localhost:7687  # TLS-enabled (local)
# NEO4J_URI=bolt+ssc://100.119.86.6:7687  # TLS-enabled (via Tailscale)
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-secure-password>

SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_SERVICE_KEY=...

# AI Services
ANTHROPIC_API_KEY=sk-ant-...
LLAMA_CLOUD_API_KEY=llx-...

# Local Models
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=bge-m3
RERANKER_MODEL=bge-reranker-v2-m3

# Networking
TAILSCALE_IP=100.x.x.x
```

**Loading in Python**:
```python
from dotenv import load_dotenv
import os

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
```

---

## 11. Key Architecture Files to Reference

### Documentation:
1. **empire-arch.txt** - Core architecture specification (v7.2)
2. **README.md** - Project overview and quick start
3. **PRE_DEV_CHECKLIST.md** - All credentials and setup steps
4. **claude.md** - This file (tools and MCPs available)

### SRS Sections:
1. **01_introduction.md** - Project objectives and scope
2. **02_overall_description.md** - System overview and context
3. **03_specific_requirements.md** - Functional requirements
4. **04_external_interface.md** - API and integration specs
5. **05_system_features.md** - Feature descriptions
6. **06_nonfunctional_requirements.md** - Performance, security
7. **07_data_model.md** - Database schemas and models
8. **08_architecture.md** - Technical architecture
9. **09_security.md** - Security requirements
10. **SRS/Workflows/** - Detailed workflow implementations (19 files)

### Schema References:
- **SRS/Workflows/database_setup.md** - All SQL schemas (3,318 lines)
- **SRS/Workflows/integration_services.md** - External service configs
- **SRS/Workflows/node_patterns.md** - Implementation patterns

---

## 12. MCP Testing Commands

### Test Neo4j MCP:
```
"Show me the Neo4j database schema"
"Create a test Document node with title 'Test'"
"Query for all nodes in the database"
```

### Test Supabase MCP:
```
"List all tables in Supabase"
"Show me the schema for the documents table"
"Count the number of rows in the documents table"
```

### Test GitHub CLI:
```bash
# Use gh CLI directly
gh repo view
gh issue list
gh pr list
gh search code "embedding"
```

### Test Render MCP:
```
"List all my Render services"
"Show me the logs for the empire-api service"
"What's the current status of the empire-api deployment?"
```

### Test Chrome DevTools MCP:
```
"Open http://localhost:8000 and show me the console errors"
"Inspect the network requests on the search page"
```

### Test Ref MCP:
```
"Check the FastAPI docs for WebSocket implementation"
"What's the Neo4j Cypher syntax for creating a relationship?"
```

---

## 13. Troubleshooting

### MCP Not Responding:
1. Check `~/.config/claude-code/mcp_settings.json`
2. Restart Claude Desktop/Code
3. Verify service is running (Neo4j, Supabase)
4. Check environment variables

### Neo4j Connection Issues:
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Restart Neo4j
docker-compose restart neo4j

# Check logs
docker logs empire-neo4j
```

### Supabase Connection Issues:
1. Verify credentials in `.env`
2. Check Supabase project status
3. Test with curl:
```bash
curl https://xxxxx.supabase.co/rest/v1/ \
  -H "apikey: YOUR_KEY"
```

### Ollama Connection Issues:
```bash
# Check if Ollama is running
ollama list

# Restart Ollama
brew services restart ollama

# Test embedding
ollama run bge-m3 "test"
```

---

## 14. Best Practices

### When to Use Each Tool:

**Use Claude Code When**:
- Planning architecture
- Creating database schemas
- Managing GitHub PRs
- Deploying to production
- Complex multi-file operations

**Use Cline When**:
- Implementing specific features
- Editing individual files
- Quick iterations
- Testing changes

**Use Continue.dev When**:
- Writing new functions
- Adding type hints
- Generating tests
- Getting inline suggestions

**Use Neo4j MCP When**:
- Creating graph schemas
- Querying relationships
- Testing graph data
- Debugging entity connections

**Use Supabase MCP When**:
- Creating SQL tables
- Testing vector search
- Managing data
- Checking table stats

**Use Claude Context MCP When**:
- Starting a new session and need to recall previous decisions
- Need to reference architecture decisions from earlier conversations
- Want to track project progress across multiple sessions
- Need to recall "what we decided" about a specific feature
- Continuing work from a previous day/session

**Use GitHub CLI (`gh`) When**:
- GitHub operations (PR, issues, search) - use via terminal
- Creating and managing branches - `gh pr create`, `gh issue list`, etc.
- Code search across repositories - `gh search code`

**Use Render MCP When**:
- Deploying to Render
- Managing cloud services
- Viewing logs and metrics
- Configuring environment variables

**Use Chrome DevTools MCP When**:
- Frontend is not working
- CSS issues
- JavaScript errors
- API debugging in browser

**Use Ref MCP When**:
- Unsure about API usage
- Need syntax reference
- Checking best practices
- Verifying schema formats

---

## 15. Quick Reference Commands

### Start Development:
```bash
# Start Neo4j
docker-compose up -d

# Activate Python environment
source venv/bin/activate

# Start FastAPI dev server
uvicorn app.main:app --reload --port 8000

# In another terminal: Start Claude Code
claude-code
```

### Check Services:
```bash
# Neo4j
curl http://localhost:7474

# Ollama
ollama list

# FastAPI
curl http://localhost:8000/docs
```

### Run Tests:
```bash
pytest tests/ -v
```

---

## 16. Summary: Your Tools

| Tool | Purpose | Access Method |
|------|---------|---------------|
| **Claude Code** | CLI AI assistant | Terminal |
| **Cline** | VS Code AI coding | VS Code sidebar |
| **Continue.dev** | Code completion | VS Code inline |
| **GitHub CLI (`gh`)** | GitHub operations | Terminal commands |
| **Tailscale CLI** | VPN & remote access | Terminal commands |
| **Neo4j MCP** | Graph database ops | Natural language in Claude |
| **Supabase MCP** | SQL database ops | Natural language in Claude |
| **Render MCP** | Deployment & services | Natural language in Claude |
| **Chrome DevTools MCP** | Frontend debugging | Natural language in Claude |
| **Ref MCP** | Documentation | Natural language in Claude |
| **Claude Context MCP** | Session context | Natural language in Claude |

---

## 17. Next Steps

After reading this file:
1. Check PRE_DEV_CHECKLIST.md for credentials
2. Verify all MCPs are configured
3. Test each MCP with a simple query
4. Choose the right tool for your current task
5. Start coding!

---

**Version**: 1.0
**Last Updated**: 2025-01-01
**Empire Version**: v7.2
**Status**: Ready for development

---

## Questions?

If you're unsure which tool to use:
- Ask Claude Code: "Which tool should I use to [task]?"
- Reference section 12 "Best Practices" above
- Test each MCP to understand its capabilities

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
