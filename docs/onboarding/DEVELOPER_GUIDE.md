# Empire v7.5 - Developer Onboarding Guide

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
| **Python** | 3.11+ | Backend runtime |
| **Node.js** | 18+ | Frontend tooling |
| **Rust** | Latest stable | Tauri desktop app |
| **Docker** | 24+ | Neo4j database |
| **Git** | Latest | Version control |
| **VS Code** | Latest | Recommended IDE |

### Optional But Recommended

| Software | Purpose |
|----------|---------|
| **GitHub CLI** (`gh`) | PR management |
| **Ollama** | Local vision model (Qwen2.5-VL-32B) |
| **Tailscale** | Remote access to Mac Studio services |
| **Postman** / **Insomnia** | API testing |

### System Requirements

- **OS**: macOS, Linux, or Windows (WSL2)
- **RAM**: 8GB minimum, 16GB recommended (32GB+ for local Ollama models)
- **Disk Space**: 10GB free (20GB+ if running Ollama models locally)

---

## Quick Start (5 Minutes)

### 1. Clone the Repository

```bash
# Clone from GitHub
git clone https://github.com/jayusctrojan/Empire.git
cd Empire

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
ANTHROPIC_API_KEY=sk-ant-...           # Sonnet 4.5 (prompt/output pipeline)
TOGETHER_API_KEY=...                    # Kimi K2.5 Thinking (reasoning engine)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
NEO4J_PASSWORD=your-secure-password

# Optional for full functionality
GOOGLE_API_KEY=...                      # Gemini 3 Flash (vision/video fallback)
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434  # Local Qwen2.5-VL-32B
B2_APPLICATION_KEY_ID=...               # Backblaze B2 storage
B2_APPLICATION_KEY=...
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
# {"status": "healthy", "version": "7.5.0"}
```

### 6. Run the Desktop App (Optional)

```bash
# Install frontend dependencies
cd empire-desktop
npm install

# Start in development mode
npm run tauri dev
```

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
code --install-extension bradlc.vscode-tailwindcss
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
  },
  "[typescript]": {
    "editor.defaultFormatter": "dbaeumer.vscode-eslint"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "dbaeumer.vscode-eslint"
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
Empire/
├── app/                          # FastAPI backend
│   ├── routes/                   # 57 API route modules (300+ endpoints)
│   │   ├── unified_search.py     # Cross-type search with asyncio.gather
│   │   ├── organizations.py      # Multi-tenant org management
│   │   ├── artifacts.py          # Artifact CRUD + download
│   │   ├── studio_cko.py         # CKO chat with multi-model pipeline
│   │   ├── kb_submissions.py     # Knowledge base submissions
│   │   └── ...
│   ├── services/                 # 139 service files
│   │   ├── llm_client.py         # Unified LLM provider abstraction (4 impls)
│   │   ├── prompt_engineer_service.py    # Sonnet 4.5 prompt enrichment
│   │   ├── output_architect_service.py   # Sonnet 4.5 output formatting
│   │   ├── document_generator_service.py # DOCX/XLSX/PPTX/PDF generation
│   │   ├── organization_service.py       # Org CRUD + membership
│   │   ├── vision_service.py             # Multi-provider image analysis
│   │   ├── whisper_stt_service.py        # Local audio transcription
│   │   ├── audio_video_processor.py      # Video frame extraction + analysis
│   │   ├── studio_cko_conversation_service.py  # CKO chat orchestration
│   │   ├── cost_tracking_service.py      # Per-query cost tracking
│   │   └── ...
│   ├── core/
│   │   ├── database.py           # Supabase client initialization
│   │   └── config.py             # Environment configuration
│   ├── middleware/                # Auth, rate limiting, org context
│   ├── main.py                   # FastAPI application entry
│   └── celery_app.py             # Celery configuration
├── empire-desktop/               # Tauri desktop application
│   ├── src/
│   │   ├── components/           # React components (31 files)
│   │   │   ├── auth/             # Authentication (Clerk)
│   │   │   ├── chat/             # Chat UI, artifacts, phase indicators
│   │   │   └── projects/         # Project management
│   │   ├── stores/               # Zustand state management
│   │   │   ├── chat.ts           # Conversations, messages, artifacts, phases
│   │   │   ├── app.ts            # View state, sidebar
│   │   │   ├── org.ts            # Organization selection, switching
│   │   │   └── projects.ts       # Project list
│   │   ├── lib/
│   │   │   ├── api/              # Backend API client
│   │   │   │   ├── client.ts     # Fetch wrapper with X-Org-Id header
│   │   │   │   ├── search.ts     # Unified search API
│   │   │   │   ├── artifacts.ts  # Artifact download/metadata
│   │   │   │   └── index.ts      # Core API functions
│   │   │   └── database.ts       # Local IndexedDB for offline data
│   │   └── test/
│   │       └── setup.ts          # vitest + jsdom + localStorage mock
│   ├── src-tauri/                # Rust backend for Tauri
│   └── package.json
├── tests/                        # Backend test suite (170+ test files)
├── migrations/                   # Database migrations
├── docs/                         # Documentation
│   ├── onboarding/               # Onboarding guides
│   └── API_REFERENCE.md
├── notebooklm/                   # NotebookLM source documents
├── requirements.txt              # Python dependencies
├── requirements-dev.txt          # Development dependencies
├── docker-compose.yml            # Docker services
└── README.md                     # Project overview
```

---

## Key Architecture Concepts

### Multi-Model Pipeline

Every CKO query flows through 3 stages:
1. **Prompt Engineer** (Sonnet 4.5): Detects intent, output format, enriches query
2. **Reasoning Engine** (Kimi K2.5 Thinking): Deep reasoning with citations
3. **Output Architect** (Sonnet 4.5): Formats response, detects artifacts, streams to user

### LLM Client Abstraction

All AI providers implement a unified `LLMClient` interface (`app/services/llm_client.py`):

```python
class LLMClient(ABC):
    async def generate(prompt, system_prompt, ...) -> str
    async def generate_with_images(prompt, images, ...) -> str
    def is_retryable(error) -> bool

# Implementations:
# TogetherAILLMClient  → Kimi K2.5 Thinking
# AnthropicLLMClient   → Claude Sonnet 4.5
# GeminiLLMClient      → Gemini 3 Flash
# OpenAICompatibleClient → Ollama/Qwen2.5-VL (any OpenAI-compatible API)
```

### Organization Layer

All data is scoped to organizations. The `X-Org-Id` header is sent with every API request from the desktop app. Middleware extracts it and sets `request.state.org_id` for route handlers.

---

## Making Your First Change

Let's add a simple feature: a new health check endpoint that includes database status.

### Step 1: Create a Feature Branch

```bash
git checkout -b feature/enhanced-health-check
```

### Step 2: Write the Code

Edit `app/routes/monitoring.py`:

```python
@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including database status"""
    health_status = {
        "status": "healthy",
        "version": "7.5.0",
        "services": {}
    }

    # Check Neo4j
    try:
        neo4j_status = await check_database_connection("neo4j")
        health_status["services"]["neo4j"] = "healthy"
    except Exception:
        health_status["services"]["neo4j"] = "unhealthy"
        health_status["status"] = "degraded"

    # Check Supabase
    try:
        supabase_status = await check_database_connection("supabase")
        health_status["services"]["supabase"] = "healthy"
    except Exception:
        health_status["services"]["supabase"] = "unhealthy"
        health_status["status"] = "degraded"

    return health_status
```

### Step 3: Write Tests

Create `tests/test_health_check.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
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
```

### Step 4: Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_health_check.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### Step 5: Commit and Push

```bash
git add app/routes/monitoring.py tests/test_health_check.py
git commit -m "feat: add detailed health check endpoint"
git push origin feature/enhanced-health-check
```

---

## Testing

### Backend Tests (pytest)

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
pytest tests/test_unified_search.py -v

# Run in parallel (faster)
pytest -n auto
```

### Frontend Tests (vitest)

```bash
cd empire-desktop

# Run all frontend tests
npx vitest run

# Run in watch mode
npx vitest

# Run specific test file
npx vitest run src/test/stores/chat.test.ts

# Type checking
npx tsc --noEmit
```

### Writing Tests

#### Backend Unit Test Example

```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.prompt_engineer_service import PromptEngineerService

@pytest.fixture
def service():
    return PromptEngineerService()

@pytest.mark.asyncio
async def test_intent_detection(service):
    """Test that prompt engineer detects query intent"""
    with patch.object(service, '_call_sonnet') as mock_call:
        mock_call.return_value = '{"intent": "analytical", "format": "text"}'
        result = await service.engineer_prompt("Compare our sales across regions")
        assert result.intent == "analytical"
```

#### Frontend Test Example

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useChatStore } from '@/stores/chat'

describe('Chat Store', () => {
  beforeEach(() => {
    useChatStore.getState().reset()
  })

  it('sets active conversation', () => {
    useChatStore.getState().setActiveConversation('session-123')
    expect(useChatStore.getState().activeConversationId).toBe('session-123')
  })
})
```

---

## Submitting a Pull Request

### PR Checklist

Before submitting, ensure:

- [ ] All backend tests pass (`pytest`)
- [ ] All frontend tests pass (`npx vitest run` in empire-desktop/)
- [ ] TypeScript compiles (`npx tsc --noEmit` in empire-desktop/)
- [ ] Code is formatted (`black app/` and `ruff check app/`)
- [ ] Documentation is updated (if adding new features)
- [ ] Commit messages follow conventional commits format

### Create the PR

```bash
gh pr create --title "feat: add detailed health check endpoint" \
  --body "## Summary
- Added /api/monitoring/health/detailed endpoint
- Returns status for Neo4j, Supabase, and Redis

## Test plan
- [ ] Unit tests pass
- [ ] Manual testing completed" \
  --base main
```

### PR Review Process

1. **CodeRabbit**: Automated AI code review runs on every PR
2. **CI/CD**: Automated tests and linters
3. **Code Review**: Team members review your code
4. **Revisions**: Address CodeRabbit + reviewer feedback and push updates
5. **Approval**: Get required approvals
6. **Merge**: Maintainer merges to main branch (squash merge preferred)

**Important**: Never merge to main without explicit approval from Jay.

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
pytest
git commit -m "feat: description"

# 5. Push and create PR
git push origin feature/my-new-feature
gh pr create
```

### Working with the Desktop App

```bash
# Terminal 1: API Server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Desktop App (hot-reloads)
cd empire-desktop && npm run tauri dev

# Terminal 3: Run frontend tests in watch mode
cd empire-desktop && npx vitest
```

---

## Common Tasks

### Adding a New API Route Module

1. **Create route file** (`app/routes/your_feature.py`):
```python
from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/api/your-feature", tags=["Your Feature"])

@router.get("/")
async def list_items(request: Request):
    org_id = getattr(request.state, "org_id", None)
    user_id = getattr(request.state, "user_id", None)
    # Implementation scoped to org
    return {"items": []}
```

2. **Register router** (`app/main.py`):
```python
from app.routes import your_feature
app.include_router(your_feature.router)
```

3. **Write tests** (`tests/test_your_feature.py`)

### Adding a New LLM Provider

1. Create a new class extending `LLMClient` in `app/services/llm_client.py`
2. Implement `generate()`, `generate_with_images()`, and `is_retryable()`
3. Add to `get_llm_client()` factory function
4. Add cost tracking in `cost_tracking_service.py`

### Adding a Desktop Component

1. Create component in `empire-desktop/src/components/`
2. Use Zustand stores for state management
3. Follow the Empire dark theme (Tailwind classes: `bg-empire-*`, `text-empire-*`)
4. Add tests in `empire-desktop/src/test/`

### Adding Database Migrations

**Supabase**:
```bash
supabase migration new add_your_table
# Edit migration file, then:
supabase db push
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

#### Frontend Build Errors

```bash
cd empire-desktop

# Clear node_modules and reinstall
rm -rf node_modules
npm install

# Check TypeScript errors
npx tsc --noEmit
```

#### Tauri Build Issues

```bash
# Ensure Rust is installed and up to date
rustup update

# Check Tauri prerequisites
cargo install tauri-cli
```

#### Test Failures

```bash
# Run tests with verbose output
pytest -vv

# Run specific failing test
pytest tests/test_file.py::test_function -vv

# Check test logs
pytest --log-cli-level=DEBUG
```

---

## Code Style Guidelines

### Python (PEP 8 + Black)

```bash
# Use Black formatter (88 character line length)
black app/

# Check with Ruff
ruff check app/
```

### TypeScript/React

- Use functional components with hooks
- Zustand for state management (not Redux)
- Tailwind CSS for styling (Empire dark theme)
- `vitest` + `@testing-library/react` for tests

### Naming Conventions

- **Files**: `snake_case.py` (backend), `PascalCase.tsx` (components), `camelCase.ts` (utils)
- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case` (Python), `camelCase` (TypeScript)
- **Constants**: `UPPER_SNAKE_CASE`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add detailed health check endpoint
fix: resolve cache key collision in Redis
docs: update API reference for query endpoints
test: add unit tests for semantic similarity
refactor: extract caching logic into service
```

---

## Resources

### Documentation
- [API Reference](../API_REFERENCE.md)
- [NotebookLM Docs](../../notebooklm/) (Architecture, Features, AI Agents)

### External Resources
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Docs](https://supabase.com/docs)
- [Tauri Documentation](https://tauri.app/v2/)
- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [Neo4j Developer Guide](https://neo4j.com/developer/)

---

**Last Updated**: 2026-02-19
**Version**: 7.5
**Maintainer**: Empire Development Team
