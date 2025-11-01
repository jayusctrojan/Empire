# Claude Code Development Guide for Empire v7.2

## Overview
This document outlines all tools, MCPs, and development environments available for building Empire v7.2. Read this file at the start of each development session to understand your capabilities.

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
- Remember project decisions and architecture
- Track progress across multiple sessions
- Reference previous conversations

**Usage**:
```
"Refer to our previous discussion about the dual-interface architecture"
"What did we decide about the embedding model?"
```

---

### 2.2 MCP_Docker (GitHub + Render Integration)
**Purpose**: GitHub repository management and Render deployment

#### GitHub Operations:
- **Repository Management**:
  - Clone, create, fork repositories
  - Branch management (create, merge, delete)
  - Commit and push changes

- **Pull Requests**:
  - Create PRs with detailed descriptions
  - Review PR diffs
  - Merge PRs
  - Comment on PRs

- **Issues**:
  - Create, update, close issues
  - Assign issues
  - Add labels and milestones
  - Track sub-issues

- **Code Search**:
  - Search across repositories
  - Find functions, classes, patterns
  - Search by file type or language

#### Render Operations:
- **Web Services**:
  - Create and deploy FastAPI services
  - Configure environment variables
  - View logs and metrics
  - Scale services

- **Databases**:
  - Create PostgreSQL instances
  - Manage Redis/KeyValue stores
  - Monitor database metrics

- **Static Sites**:
  - Deploy frontend applications
  - Configure build settings
  - Manage deployments

#### Existing Render Deployments (IMPORTANT!):
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

**CrewAI Service** (Already Running):
- **Service ID**: `srv-d2n0hh3uibrs73buafo0`
- **URL**: https://jb-crewai.onrender.com
- **Purpose**: Multi-agent AI orchestration
- **Status**: ACTIVE - Use this for complex multi-step workflows
- **Integration**:
  ```python
  CREWAI_SERVICE_URL = "https://jb-crewai.onrender.com"
  # Use for multi-agent task coordination
  ```

**Usage Examples**:
```python
# GitHub
"Create a new branch called feature/graph-sync"
"Search the codebase for BGE-M3 embedding usage"
"Create a PR from feature/graph-sync to main"

# Render - Existing Services
"Show me the status of jb-llamaindex service"
"Show me the logs for jb-crewai service"
"List all services in workspace tea-d1vtdtre5dus73a4rb4g"
"What's the health status of srv-d2nl1lre5dus73atm9u0?"

# Render - New Services
"Deploy the FastAPI app to Render"
"Create a PostgreSQL database on Render"
```

**Configuration**: Already configured in `mcp_settings.json`

---

### 2.3 Neo4j MCP
**Purpose**: Direct natural language queries to Neo4j graph database

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
- **URI**: `bolt://localhost:7687`
- **Username**: `neo4j`
- **Password**: `empiresecure123`
- **Web Interface**: http://localhost:7474

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
      "-e", "NEO4J_PASSWORD=empiresecure123",
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

### 3.1 Claude Code (CLI)
**Role**: Primary architect and infrastructure setup

**Best For**:
- System architecture design
- Database schema creation
- MCP integration and testing
- Complex multi-file refactoring
- Git operations and PR management

**Strengths**:
- Access to all MCPs
- Can read entire codebase
- Long-form planning and documentation
- Direct terminal access

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

---

### 3.2 Cline (VS Code Extension)
**Role**: Rapid feature implementation within VS Code

**Best For**:
- Quick feature additions
- File-by-file editing
- Inline code generation
- Testing and debugging
- Iterative development

**Strengths**:
- Native VS Code integration
- Fast context switching
- Visual diff previews
- Direct file manipulation

**Usage Pattern**:
1. Open VS Code to the file you want to edit
2. Activate Cline sidebar
3. Describe the change needed
4. Review and accept the diff

**Example Prompts**:
```
"Add error handling to the embedding service"
"Create a new route for document upload"
"Refactor this function to use async/await"
"Add type hints to all functions in this file"
```

---

### 3.3 Continue.dev (VS Code Extension)
**Role**: Code completion and inline suggestions

**Best For**:
- Autocomplete while typing
- Function generation from comments
- Quick refactoring
- Code explanation
- Unit test generation

**Strengths**:
- Real-time suggestions
- Minimal context switching
- Tab completion
- Comment-to-code generation

**Usage Pattern**:
1. Write a comment describing what you need
2. Press Tab to accept suggestion
3. Use Cmd+I for inline chat

**Example Usage**:
```python
# Generate embeddings using BGE-M3 and store in Supabase
# [Press Tab - Continue.dev generates the function]

def generate_embeddings(text: str) -> list[float]:
    # [Continue.dev suggests implementation]
    pass
```

---

## 4. Recommended Development Workflow

### Phase 1: Architecture & Planning (Claude Code)
1. Use **Claude Code** to design system architecture
2. Create database schemas via **Neo4j MCP** and **Supabase MCP**
3. Set up project structure and dependencies
4. Create initial boilerplate code

### Phase 2: Core Implementation (Cline)
1. Use **Cline** in VS Code for feature implementation
2. Implement services (embedding, query, sync)
3. Create API routes in FastAPI
4. Add business logic

### Phase 3: Refinement (Continue.dev)
1. Use **Continue.dev** for code completion
2. Add type hints and documentation
3. Refactor for clarity
4. Generate unit tests

### Phase 4: Testing & Debugging
1. Use **Chrome DevTools MCP** for frontend debugging
2. Use **Neo4j MCP** to verify graph data
3. Use **Supabase MCP** to check vector storage
4. Use **Ref MCP** to verify API usage

### Phase 5: Deployment (Claude Code + MCP_Docker)
1. Use **Claude Code** with **MCP_Docker** to deploy to Render
2. Create PR and merge to main
3. Monitor logs and metrics
4. Set up environment variables

---

## 5. Empire v7.2 Specific Tools

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

## 6. Development Checklist for Each Session

### Before Starting:
- [ ] Read this claude.md file
- [ ] Check PRE_DEV_CHECKLIST.md for credentials
- [ ] Verify Neo4j is running: `docker ps | grep neo4j`
- [ ] Verify Ollama is running: `ollama list`
- [ ] **Verify LlamaIndex service**: `curl https://jb-llamaindex.onrender.com/health`
- [ ] **Verify CrewAI service**: `curl https://jb-crewai.onrender.com/health`
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

## 7. Common MCP Workflows

### Create Database Schema
```
Claude Code � Use Supabase MCP:
"Create the documents table with vector embeddings as defined in database_setup.md"

Claude Code � Use Neo4j MCP:
"Create the Entity and Document nodes with relationships"
```

### Deploy to Render
```
Claude Code � Use MCP_Docker:
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
```
Claude Code � Use MCP_Docker GitHub:
"Search the repo for all instances of BGE-M3 usage"
"Find the function that handles document parsing"
```

---

## 8. Environment Variables Reference

All credentials should be in `.env` file (see PRE_DEV_CHECKLIST.md):

```bash
# Databases
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=empiresecure123

SUPABASE_URL=https://xxxxx.supabase.co
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

## 9. Key Architecture Files to Reference

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

## 10. MCP Testing Commands

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

### Test MCP_Docker (GitHub):
```
"Show me the latest commit on the Empire repo"
"List all open issues"
"Search for 'embedding' in the codebase"
```

### Test MCP_Docker (Render):
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

## 11. Troubleshooting

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

## 12. Best Practices

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

**Use MCP_Docker When**:
- GitHub operations (PR, issues, search)
- Deploying to Render
- Managing cloud services

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

## 13. Quick Reference Commands

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

## 14. Summary: Your Tools

| Tool | Purpose | Access Method |
|------|---------|---------------|
| **Claude Code** | CLI AI assistant | Terminal |
| **Cline** | VS Code AI coding | VS Code sidebar |
| **Continue.dev** | Code completion | VS Code inline |
| **Neo4j MCP** | Graph database ops | Natural language in Claude |
| **Supabase MCP** | SQL database ops | Natural language in Claude |
| **MCP_Docker** | GitHub + Render | Natural language in Claude |
| **Chrome DevTools MCP** | Frontend debugging | Natural language in Claude |
| **Ref MCP** | Documentation | Natural language in Claude |
| **Claude Context MCP** | Session context | Natural language in Claude |

---

## 15. Next Steps

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
