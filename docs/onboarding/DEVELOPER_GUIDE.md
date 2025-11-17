# Empire v7.3 - Developer Onboarding Guide

**From Zero to First Contribution in 30 Minutes**

This guide will take you from a fresh checkout to your first successful contribution to Empire.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Development Environment Setup](#development-environment-setup)
4. [Project Structure](#project-structure)
5. [Making Your First Change](#making-your-first-change)
6. [Testing](#testing)
7. [Submitting a Pull Request](#submitting-a-pull-request)
8. [Development Workflows](#development-workflows)
9. [Common Tasks](#common-tasks)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

Before you begin, ensure you have:

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.9+ | Backend runtime |
| **Node.js** | 18+ | Frontend tooling |
| **Docker** | 24+ | Neo4j database |
| **Git** | Latest | Version control |
| **VS Code** | Latest | Recommended IDE |

### Optional But Recommended

| Software | Purpose |
|----------|---------|
| **GitHub CLI** (`gh`) | PR management |
| **Ollama** | Local embedding models (BGE-M3) |
| **Tailscale** | Remote access to Mac Studio services |
| **Postman** / **Insomnia** | API testing |

### System Requirements

- **OS**: macOS, Linux, or Windows (WSL2)
- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 10GB free

---

## Quick Start (5 Minutes)

### 1. Clone the Repository

```bash
# Clone from GitHub
git clone https://github.com/your-org/empire.git
cd empire

# Create a feature branch
git checkout -b feature/your-feature-name
```

### 2. Set Up Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# See PRE_DEV_CHECKLIST.md for where to get API keys
```

**Essential Variables**:
```bash
# Required for basic functionality
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
NEO4J_PASSWORD=your-secure-password

# Optional for full functionality
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install development tools
pip install -r requirements-dev.txt
```

### 4. Start Neo4j Database

```bash
# Start Neo4j with Docker
docker-compose up -d neo4j

# Verify it's running
docker ps | grep neo4j

# Access Neo4j Browser
open http://localhost:7474
# Login: neo4j / your-password-from-.env
```

### 5. Run the Application

```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# In another terminal, start Celery worker
celery -A app.celery_app worker --loglevel=info
```

**Verify Setup**:
```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "7.3.0"}
```

**🎉 Congratulations!** You're ready to start developing.

---

## Development Environment Setup

### IDE Configuration (VS Code Recommended)

#### 1. Install Extensions

```bash
# Install recommended extensions
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-python.black-formatter
code --install-extension charliermarsh.ruff
code --install-extension dbaeumer.vscode-eslint
```

#### 2. Configure VS Code Settings

Create `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.rulers": [88]
  }
}
```

#### 3. Set Up Debugging

Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--port",
        "8000"
      ],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": [
        "-v",
        "tests/"
      ],
      "console": "integratedTerminal"
    }
  ]
}
```

---

### Database Setup

#### Neo4j (Docker)

```bash
# Start Neo4j
docker-compose up -d neo4j

# Access browser
open http://localhost:7474

# First-time setup:
# 1. Login with: neo4j/neo4j
# 2. Change password to match .env
# 3. Run schema initialization:
python scripts/init_neo4j_schema.py
```

#### Supabase (Cloud)

1. Visit https://app.supabase.com
2. Create a new project (or use existing)
3. Copy credentials to `.env`:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_KEY`

4. Run migrations:
```bash
# Install Supabase CLI
brew install supabase/tap/supabase

# Link to project
supabase link --project-ref your-project-id

# Run migrations
supabase db push
```

#### Redis (Local)

```bash
# Option 1: Docker (Recommended)
docker run -d -p 6379:6379 redis:7-alpine

# Option 2: Homebrew (macOS)
brew install redis
brew services start redis

# Verify connection
redis-cli ping
# Expected: PONG
```

---

## Project Structure

```
empire/
├── app/                          # Main application code
│   ├── api/                      # API endpoints
│   │   └── routes/               # Route handlers
│   │       ├── query.py          # Query endpoints (Task 46)
│   │       ├── documents.py      # Document management
│   │       └── crewai.py         # CrewAI orchestration
│   ├── services/                 # Business logic
│   │   ├── query_cache.py        # Semantic caching (Task 43.3)
│   │   ├── embedding_service.py  # BGE-M3 embeddings
│   │   ├── langgraph_service.py  # LangGraph workflows
│   │   └── arcade_service.py     # Arcade.dev integration
│   ├── models/                   # Pydantic models
│   │   ├── query.py              # Query request/response models
│   │   └── document.py           # Document models
│   ├── middleware/               # FastAPI middleware
│   │   ├── security.py           # Security headers (Task 41.1)
│   │   ├── rate_limit.py         # Rate limiting
│   │   └── rls_context.py        # RLS context setting
│   ├── utils/                    # Utility functions
│   ├── main.py                   # FastAPI application entry
│   └── celery_app.py             # Celery configuration
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── load_testing/             # Load tests (Task 43.3)
├── migrations/                   # Database migrations
│   ├── supabase/                 # Supabase migrations
│   └── neo4j/                    # Neo4j schema updates
├── docs/                         # Documentation
│   ├── API_REFERENCE.md          # Complete API docs
│   ├── WORKFLOW_DIAGRAMS.md      # System diagrams
│   └── onboarding/               # Onboarding guides
├── scripts/                      # Utility scripts
│   ├── init_neo4j_schema.py      # Neo4j setup
│   └── seed_test_data.py         # Test data generation
├── .env                          # Environment variables (DO NOT COMMIT)
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
├── requirements-dev.txt          # Development dependencies
├── docker-compose.yml            # Docker services
└── README.md                     # Project overview
```

---

## Making Your First Change

Let's add a simple feature: a new health check endpoint that includes database status.

### Step 1: Create a Feature Branch

```bash
git checkout -b feature/enhanced-health-check
```

### Step 2: Write the Code

Edit `app/api/routes/monitoring.py`:

```python
# Add this import at the top
from app.services.database import check_database_connection

# Add this new endpoint
@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check including database status
    """
    health_status = {
        "status": "healthy",
        "version": "7.3.0",
        "services": {}
    }

    # Check Neo4j
    try:
        neo4j_status = await check_database_connection("neo4j")
        health_status["services"]["neo4j"] = "healthy"
    except Exception as e:
        health_status["services"]["neo4j"] = "unhealthy"
        health_status["status"] = "degraded"

    # Check Supabase
    try:
        supabase_status = await check_database_connection("supabase")
        health_status["services"]["supabase"] = "healthy"
    except Exception as e:
        health_status["services"]["supabase"] = "unhealthy"
        health_status["status"] = "degraded"

    # Check Redis
    try:
        redis_status = await check_database_connection("redis")
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = "unhealthy"
        health_status["status"] = "degraded"

    return health_status
```

### Step 3: Write Tests

Create `tests/unit/test_health_check.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_detailed_health_check():
    """Test detailed health check endpoint"""
    response = client.get("/api/monitoring/health/detailed")

    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "services" in data

    # Check required services
    assert "neo4j" in data["services"]
    assert "supabase" in data["services"]
    assert "redis" in data["services"]

def test_health_check_with_db_failure(monkeypatch):
    """Test health check when database is down"""
    # Mock database connection failure
    def mock_check_db(*args, **kwargs):
        raise ConnectionError("Database unavailable")

    monkeypatch.setattr(
        "app.services.database.check_database_connection",
        mock_check_db
    )

    response = client.get("/api/monitoring/health/detailed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
```

### Step 4: Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_health_check.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### Step 5: Manual Testing

```bash
# Start the server
uvicorn app.main:app --reload

# Test the endpoint
curl http://localhost:8000/api/monitoring/health/detailed

# Expected response:
{
  "status": "healthy",
  "version": "7.3.0",
  "services": {
    "neo4j": "healthy",
    "supabase": "healthy",
    "redis": "healthy"
  }
}
```

### Step 6: Commit Your Changes

```bash
# Stage changes
git add app/api/routes/monitoring.py tests/unit/test_health_check.py

# Commit with descriptive message
git commit -m "feat: add detailed health check endpoint

- Added /api/monitoring/health/detailed endpoint
- Includes status for Neo4j, Supabase, and Redis
- Returns 'degraded' status if any service is unhealthy
- Added unit tests with mocking for failure scenarios
- Closes #123"

# Push to your fork
git push origin feature/enhanced-health-check
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/         # Unit tests only
pytest tests/integration/  # Integration tests only

# Run with coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest tests/unit/test_query_cache.py -v

# Run specific test function
pytest tests/unit/test_query_cache.py::test_semantic_similarity -v

# Run with verbose output
pytest -vv

# Run in parallel (faster)
pytest -n auto
```

### Writing Tests

#### Unit Test Example

```python
# tests/unit/test_embedding_service.py
import pytest
from app.services.embedding_service import EmbeddingService

@pytest.fixture
def embedding_service():
    """Fixture to create embedding service instance"""
    return EmbeddingService()

def test_generate_embedding(embedding_service):
    """Test embedding generation"""
    text = "What are California insurance requirements?"

    result = embedding_service.generate_embedding(text)

    assert result is not None
    assert len(result.embedding) == 1024  # BGE-M3 dimension
    assert all(isinstance(x, float) for x in result.embedding)

def test_embedding_caching(embedding_service):
    """Test that identical queries use cached embeddings"""
    text = "Test query"

    # First call
    result1 = embedding_service.generate_embedding(text)

    # Second call (should hit cache)
    result2 = embedding_service.generate_embedding(text)

    assert result1.embedding == result2.embedding
    assert result2.from_cache is True
```

#### Integration Test Example

```python
# tests/integration/test_query_endpoint.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def auth_token():
    """Fixture to get authentication token"""
    # In real tests, use actual authentication
    return "test-jwt-token"

def test_adaptive_query_endpoint(auth_token):
    """Test adaptive query endpoint"""
    response = client.post(
        "/api/query/adaptive",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "query": "What are California insurance requirements?",
            "max_iterations": 3
        }
    )

    assert response.status_code == 200

    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "processing_time_ms" in data
```

---

## Submitting a Pull Request

### PR Checklist

Before submitting, ensure:

- [ ] All tests pass (`pytest`)
- [ ] Code is formatted (`black app/` and `ruff check app/`)
- [ ] Type hints are added (check with `mypy app/`)
- [ ] Documentation is updated (if adding new features)
- [ ] Commit messages follow conventional commits format
- [ ] PR description explains the change

### Create the PR

```bash
# Using GitHub CLI (recommended)
gh pr create --title "feat: add detailed health check endpoint" \
  --body "## Summary
This PR adds a new detailed health check endpoint that includes database status.

## Changes
- Added `/api/monitoring/health/detailed` endpoint
- Returns status for Neo4j, Supabase, and Redis
- Added unit tests with failure scenario mocking

## Testing
- [x] Unit tests pass
- [x] Manual testing completed
- [x] Integration tests pass

## Closes
Closes #123" \
  --base main

# Or manually via GitHub web interface
# 1. Push your branch
# 2. Visit https://github.com/your-org/empire
# 3. Click "Compare & pull request"
```

### PR Review Process

1. **Automated Checks**: CI/CD runs tests and linters
2. **Code Review**: Team members review your code
3. **Revisions**: Address feedback and push updates
4. **Approval**: Get required approvals (usually 1-2 reviewers)
5. **Merge**: Maintainer merges to main branch

### After Merge

```bash
# Update your local main branch
git checkout main
git pull origin main

# Delete your feature branch
git branch -d feature/enhanced-health-check
git push origin --delete feature/enhanced-health-check
```

---

## Development Workflows

### Daily Development Workflow

```bash
# 1. Start your day
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/my-new-feature

# 3. Start services
docker-compose up -d         # Databases
uvicorn app.main:app --reload  # API server
# In another terminal:
celery -A app.celery_app worker --loglevel=info  # Worker

# 4. Make changes, test, commit
# ... coding ...
pytest
git commit -m "feat: description"

# 5. End of day
git push origin feature/my-new-feature
# Open draft PR for visibility
```

---

### Working with Multiple Services

```bash
# Terminal 1: API Server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery Worker
celery -A app.celery_app worker --loglevel=info

# Terminal 3: Celery Beat (scheduled tasks)
celery -A app.celery_app beat --loglevel=info

# Terminal 4: Monitoring (Flower)
celery -A app.celery_app flower --port=5555

# Terminal 5: Your development work
# Run tests, make changes, etc.
```

**Pro Tip**: Use `tmux` or VS Code's integrated terminal to manage multiple terminals.

---

### Debugging

#### FastAPI Debugging (VS Code)

1. Set breakpoints in VS Code
2. Press `F5` to start debugging
3. Send requests to `http://localhost:8000`
4. Execution pauses at breakpoints

#### Celery Task Debugging

```python
# Add breakpoint in task
@celery_app.task
def process_document(document_id: str):
    import pdb; pdb.set_trace()  # Breakpoint
    # ... task code ...
```

Run Celery with single worker:
```bash
celery -A app.celery_app worker --loglevel=debug --pool=solo
```

#### Database Query Debugging

**Neo4j**:
```python
# Enable query logging
import logging
logging.getLogger("neo4j").setLevel(logging.DEBUG)
```

**Supabase**:
```python
# Log SQL queries
from supabase import create_client

supabase = create_client(url, key)
supabase.postgrest.schema("public").from_("table").select("*").execute()
# Check logs in Supabase dashboard
```

---

## Common Tasks

### Adding a New API Endpoint

1. **Define Pydantic models** (`app/models/your_feature.py`):
```python
from pydantic import BaseModel

class YourRequest(BaseModel):
    field1: str
    field2: int

class YourResponse(BaseModel):
    result: str
    status: str
```

2. **Create route handler** (`app/api/routes/your_feature.py`):
```python
from fastapi import APIRouter, Depends
from app.middleware.auth import verify_clerk_token

router = APIRouter()

@router.post("/your-endpoint", response_model=YourResponse)
async def your_endpoint(
    request: YourRequest,
    user: dict = Depends(verify_clerk_token)
):
    # Implementation
    return YourResponse(result="success", status="ok")
```

3. **Register router** (`app/main.py`):
```python
from app.api.routes import your_feature

app.include_router(
    your_feature.router,
    prefix="/api/your-feature",
    tags=["Your Feature"]
)
```

4. **Write tests** (`tests/unit/test_your_feature.py`)
5. **Update documentation** (`docs/API_REFERENCE.md`)

---

### Adding a New Celery Task

1. **Define task** (`app/tasks/your_task.py`):
```python
from app.celery_app import celery_app

@celery_app.task
def your_background_task(param1: str, param2: int):
    # Long-running operation
    result = process_something(param1, param2)
    return result
```

2. **Call task from endpoint**:
```python
from app.tasks.your_task import your_background_task

@router.post("/submit")
async def submit_task(request: TaskRequest):
    task = your_background_task.apply_async(
        args=[request.param1, request.param2]
    )
    return {"task_id": task.id, "status": "queued"}
```

3. **Check task status**:
```python
from celery.result import AsyncResult

@router.get("/status/{task_id}")
async def check_status(task_id: str):
    result = AsyncResult(task_id)
    return {
        "status": result.status,
        "result": result.result if result.ready() else None
    }
```

---

### Adding Database Migrations

**Supabase**:
```bash
# Create migration
supabase migration new add_your_table

# Edit migration file in migrations/supabase/
# Add SQL commands

# Apply migration locally
supabase db reset

# Apply to production
supabase db push
```

**Neo4j**:
```python
# Create migration script in migrations/neo4j/
# Add to scripts/init_neo4j_schema.py
def create_new_index():
    with driver.session() as session:
        session.run("""
            CREATE INDEX your_index_name IF NOT EXISTS
            FOR (n:YourLabel)
            ON (n.property)
        """)
```

---

## Troubleshooting

### Common Issues

#### "Module not found" Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### Docker Services Not Starting

```bash
# Check what's using the port
lsof -i :7687  # Neo4j
lsof -i :6379  # Redis

# Stop conflicting services
docker-compose down
docker-compose up -d
```

#### Import Errors

```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run from project root
cd /path/to/empire
python -m app.main
```

#### Test Failures

```bash
# Run tests with verbose output
pytest -vv

# Run specific failing test
pytest tests/unit/test_file.py::test_function -vv

# Check test logs
pytest --log-cli-level=DEBUG
```

---

## Code Style Guidelines

### Python (PEP 8 + Black)

```python
# Use Black formatter (88 character line length)
black app/

# Check with Ruff
ruff check app/

# Type hints required
def process_query(query: str, max_iterations: int = 3) -> dict:
    """
    Process query with adaptive workflow

    Args:
        query: User query string
        max_iterations: Max refinement iterations

    Returns:
        Query result dictionary
    """
    pass
```

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add detailed health check endpoint
fix: resolve cache key collision in Redis
docs: update API reference for query endpoints
test: add unit tests for semantic similarity
refactor: extract caching logic into service
perf: optimize vector search query
chore: update dependencies to latest versions
```

---

## Resources

### Documentation
- [API Reference](../API_REFERENCE.md)
- [Workflow Diagrams](../WORKFLOW_DIAGRAMS.md)
- [Security Guide](../SECURITY.md)

### External Resources
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Docs](https://supabase.com/docs)
- [Neo4j Developer Guide](https://neo4j.com/developer/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

### Getting Help
- **Slack**: #empire-dev-support
- **Email**: dev-support@empire.ai
- **Office Hours**: Wednesdays 2-3 PM PST

---

## Next Steps

Now that you're set up, try:

1. **Explore the codebase**: Read through existing endpoints and services
2. **Pick a good first issue**: Look for issues tagged "good-first-issue"
3. **Join the community**: Introduce yourself in #empire-dev
4. **Review PRs**: Learn from others by reviewing open pull requests
5. **Ask questions**: Don't hesitate to ask in Slack or office hours

**Welcome to the Empire development team!** 🚀

---

**Last Updated**: 2025-01-17
**Version**: 7.3
**Maintainer**: Empire Development Team
