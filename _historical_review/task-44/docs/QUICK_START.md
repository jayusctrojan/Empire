# Empire Quick Start Guide

**Get up and running with Empire in minutes!**

Choose your path:
- 👤 [**End User** (2 minutes)](#end-user-quick-start-2-minutes) - Start chatting with Empire
- 💻 [**Developer** (5 minutes)](#developer-quick-start-5-minutes) - Set up local development

---

## End User Quick Start (2 Minutes)

### Step 1: Access Empire (30 seconds)

Visit: **https://jb-empire-chat.onrender.com**

### Step 2: Sign In (1 minute)

1. Click **"Sign In"**
2. Enter your work email and password
3. First time? Click **"Sign Up"** instead

### Step 3: Ask Your First Question (30 seconds)

Try these examples:

```
What is our refund policy?
```

```
How do our California requirements compare to state law?
```

```
Summarize the Q4 2024 financial report
```

**Response Time**:
- Simple queries: ~2-5 seconds
- Research queries: ~10-15 seconds
- Cached queries: ~0.3 seconds (instant!)

### Quick Tips

**✅ Do This**:
- Be specific: "What are the insurance requirements for California employees?"
- Use natural language: "Can I work from home on Fridays?"
- Check sources: Click **[View Document →]** to verify information

**❌ Avoid This**:
- Too vague: "Tell me about insurance"
- Keyword stuffing: "insurance california requirements policy 2025"

### Common Features

**Keyboard Shortcuts**:
- `Enter` → Send message
- `Shift + Enter` → New line
- `Ctrl/Cmd + K` → Clear chat

**Source Citations**: Every answer includes documents used
**Real-time Streaming**: Watch answers appear word-by-word
**Intelligent Caching**: Similar questions get instant responses

**Need Help?**
- 📖 Full Guide: [END_USER_GUIDE.md](./onboarding/END_USER_GUIDE.md)
- 📧 Support: support@empire.ai

---

## Developer Quick Start (5 Minutes)

### Prerequisites

- Python 3.9+
- Docker
- Git

### Step 1: Clone & Setup (2 minutes)

```bash
# Clone repository
git clone https://github.com/your-org/empire.git
cd empire

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment (1 minute)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# See PRE_DEV_CHECKLIST.md for where to get keys
```

**Minimal Required Variables**:
```bash
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-key
NEO4J_PASSWORD=your-password
```

### Step 3: Start Services (1 minute)

```bash
# Start Neo4j database
docker-compose up -d neo4j

# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Verify it's running
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "7.3.0"}
```

### Step 4: Make Your First Change (1 minute)

1. **Create branch**:
```bash
git checkout -b feature/my-first-change
```

2. **Edit code**: Add print statement to `app/main.py`
```python
@app.on_event("startup")
async def startup_event():
    print("🚀 Empire is starting up!")
```

3. **Test it**: Restart server and see your message

4. **Commit**:
```bash
git add app/main.py
git commit -m "feat: add startup message"
```

### Common Commands

```bash
# Run tests
pytest

# Format code
black app/

# Start Celery worker
celery -A app.celery_app worker --loglevel=info

# Access Neo4j browser
open http://localhost:7474
```

### Next Steps

- 📖 Full Guide: [DEVELOPER_GUIDE.md](./onboarding/DEVELOPER_GUIDE.md)
- 📝 API Docs: [API_REFERENCE.md](./API_REFERENCE.md)
- 🏗️ Architecture: [WORKFLOW_DIAGRAMS.md](./WORKFLOW_DIAGRAMS.md)

### Troubleshooting

**Port already in use**:
```bash
# Find what's using the port
lsof -i :8000

# Kill the process
kill -9 <PID>
```

**Module not found**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**Database connection failed**:
```bash
# Check Docker is running
docker ps

# Restart Neo4j
docker-compose restart neo4j
```

---

## Quick Reference

### Architecture Overview

```
User → Chat UI → FastAPI → [LangGraph / CrewAI / Simple RAG]
                    ↓
        [Neo4j + Supabase + Redis] → AI Models
```

### Key URLs (Production)

| Service | URL |
|---------|-----|
| **Chat UI** | https://jb-empire-chat.onrender.com |
| **API** | https://jb-empire-api.onrender.com |
| **API Docs** | https://jb-empire-api.onrender.com/docs |
| **Metrics** | https://jb-empire-api.onrender.com/monitoring/metrics |

### Key URLs (Local Development)

| Service | URL |
|---------|-----|
| **API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |
| **Neo4j Browser** | http://localhost:7474 |
| **Flower (Celery)** | http://localhost:5555 |

### Performance Benchmarks

| Query Type | Uncached | Cached | Speedup |
|------------|----------|--------|---------|
| Simple RAG | ~5.6s | ~0.36s | **93.5%** |
| Adaptive (LangGraph) | ~11.2s | ~0.36s | **96.7%** |
| Exact Match | - | ~0.3s | **Instant** |

### API Key Examples

**Query (No Caching)**:
```bash
curl https://jb-empire-api.onrender.com/api/query/adaptive \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are California insurance requirements?",
    "max_iterations": 3
  }'
```

**Response**:
```json
{
  "answer": "California requires minimum liability insurance...",
  "sources": [
    {
      "document_id": "doc_123",
      "title": "California Insurance Requirements 2025",
      "relevance_score": 0.95
    }
  ],
  "from_cache": false,
  "processing_time_ms": 11223
}
```

---

## Feature Highlights

### For End Users

**Semantic Caching (Task 43.3)**:
- 96.7% faster for repeat questions
- Works for similar questions (not just exact matches)
- 30-minute cache lifetime

**Intelligent Routing**:
- Simple queries → Fast RAG (~5s)
- Complex queries → LangGraph with research (~11s)
- Multi-document → CrewAI orchestration (~30s-2min)

**Source Citations**:
- Every answer includes document sources
- Clickable links to original documents
- Relevance scores for transparency

### For Developers

**LangGraph Integration (Task 46)**:
- 5-node adaptive workflow with iterative refinement
- External tool support via Arcade.dev (Google Search, etc.)
- Configurable max iterations (default: 3)

**Security Hardening (Task 41)**:
- Clerk JWT authentication
- Row-level security (RLS) in Supabase
- API key lifecycle management with bcrypt hashing
- Rate limiting (Redis-backed)
- HTTP security headers (HSTS, CSP, X-Frame-Options)

**CrewAI Asset Storage (Task 40)**:
- Organized B2 storage: `crewai/assets/{department}/{type}/`
- 10 departments, 5 asset types
- Metadata tracking and confidence scores

**Monitoring (Milestone 6)**:
- Prometheus metrics at `/monitoring/metrics`
- Grafana dashboards (local: http://localhost:3000)
- Flower for Celery task monitoring
- Comprehensive alerting

---

## FAQs

### End Users

**Q: How accurate are the answers?**
A: Empire provides answers based on your organization's documents. Always verify critical information using the source citations provided.

**Q: Can I upload my own documents?**
A: Contact your IT team. Document upload is currently admin-only.

**Q: What happens if Empire doesn't know the answer?**
A: Empire will let you know if no relevant information was found and suggest rephrasing your question.

### Developers

**Q: Which Python version should I use?**
A: Python 3.9 or later. We recommend 3.11 for best performance.

**Q: Do I need all the external services to develop locally?**
A: Minimum required: Neo4j (Docker). Optional: Redis (recommended), Ollama (for local embeddings).

**Q: How do I run only specific tests?**
A: `pytest tests/unit/test_file.py::test_function -v`

**Q: Where do I find API credentials?**
A: See `PRE_DEV_CHECKLIST.md` for links to each service's credential page.

---

## Getting Help

### Support Channels

**End Users**:
- Email: support@empire.ai
- Response Time: Within 24 hours

**Developers**:
- Slack: #empire-dev-support
- Email: dev-support@empire.ai
- Office Hours: Wednesdays 2-3 PM PST

### Documentation

| Audience | Document | Description |
|----------|----------|-------------|
| **End Users** | [END_USER_GUIDE.md](./onboarding/END_USER_GUIDE.md) | Complete user guide (10 min read) |
| **Developers** | [DEVELOPER_GUIDE.md](./onboarding/DEVELOPER_GUIDE.md) | Full dev setup (30 min read) |
| **API Users** | [API_REFERENCE.md](./API_REFERENCE.md) | Complete API documentation |
| **Architects** | [WORKFLOW_DIAGRAMS.md](./WORKFLOW_DIAGRAMS.md) | System architecture & flows |

---

## What's New in v7.3

### End User Features

- **96.7% faster queries** with semantic caching
- **Real-time streaming** responses
- **Enhanced source citations** with clickable document links
- **Intelligent query routing** automatically selects best workflow

### Developer Features

- **LangGraph workflows** with 5-node adaptive processing
- **Arcade.dev integration** for external tools (50+ tools available)
- **Security hardening** (JWT auth, RLS, rate limiting, API keys)
- **CrewAI asset storage** with organized B2 structure
- **Comprehensive monitoring** (Prometheus, Grafana, Flower)
- **Load testing** tools and performance benchmarks

---

**Ready to get started? Choose your path above!** 🚀

---

**Last Updated**: 2025-01-17
**Version**: 7.3
**For**: End Users & Developers
