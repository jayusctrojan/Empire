# Empire v7.3 - AI Agent System

**Version:** v7.3.0
**Last Updated:** 2025-12-30
**AI Model:** Claude Sonnet 4.5 (Anthropic API)

---

## Overview

Empire v7.3 features a **17-agent AI system** where all agents are powered by **Claude Sonnet 4.5** via Anthropic's cloud API. This is NOT local processing - all AI reasoning happens through Anthropic's API.

---

## Agent Registry

### Content Processing Agents

| Agent ID | Name | Purpose |
|----------|------|---------|
| **AGENT-002** | Content Summarizer | Generates PDF summaries with key points, main themes, and actionable insights |
| **AGENT-008** | Department Classifier | Classifies content into 12 business departments with confidence scores |

### Document Analysis Agents (Task 45)

| Agent ID | Name | Purpose |
|----------|------|---------|
| **AGENT-009** | Senior Research Analyst | Extracts topics, entities, facts, and quality assessments |
| **AGENT-010** | Content Strategist | Generates executive summaries, key findings, and recommendations |
| **AGENT-011** | Fact Checker | Verifies claims, assigns confidence scores, provides citations |

### Multi-Agent Orchestration (Task 46)

| Agent ID | Name | Purpose |
|----------|------|---------|
| **AGENT-012** | Research Agent | Web/academic search, query expansion, source credibility assessment |
| **AGENT-013** | Analysis Agent | Pattern detection, statistical analysis, correlation identification |
| **AGENT-014** | Writing Agent | Report generation, multi-format output, citation formatting |
| **AGENT-015** | Review Agent | Quality assurance, fact verification, revision recommendations |

### Content Preparation & Knowledge Graph

| Agent ID | Name | Purpose |
|----------|------|---------|
| **AGENT-016** | Content Prep Agent | Content set detection, file grouping, preparation workflows |
| **AGENT-017** | Graph Agent | Customer 360 views, document structure navigation, graph-enhanced RAG |

---

## How Agents Work

### All Agents Use Claude Sonnet 4.5

Every agent makes API calls to Anthropic's Claude Sonnet 4.5:

```python
# Example: Content Summarizer Agent
async def summarize(document: str) -> Summary:
    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        messages=[{
            "role": "user",
            "content": f"Summarize this document: {document}"
        }],
        system="You are a content summarization expert..."
    )
    return parse_summary(response)
```

### Agent Workflows

**Document Analysis Pipeline:**
```
Document → AGENT-009 (Research) → AGENT-010 (Strategy) → AGENT-011 (Fact-Check) → Final Analysis
```

**Multi-Agent Orchestration:**
```
Task → AGENT-012 (Research) → AGENT-013 (Analysis) → AGENT-014 (Writing) → AGENT-015 (Review)
                                                                              ↓
                                                                     [Revision Loop if needed]
                                                                              ↓
                                                                    Back to AGENT-014 (Writing)
```

---

## API Endpoints

### Content Summarizer (AGENT-002)
- `POST /api/summarizer/summarize` - Generate document summary
- `GET /api/summarizer/health` - Service health
- `GET /api/summarizer/stats` - Usage statistics

### Department Classifier (AGENT-008)
- `POST /api/classifier/classify` - Classify content
- `POST /api/classifier/batch` - Batch classification
- `GET /api/classifier/departments` - List departments
- `GET /api/classifier/health` - Service health

### Document Analysis (AGENT-009/010/011)
- `POST /api/document-analysis/analyze` - Full 3-agent analysis
- `POST /api/document-analysis/research` - AGENT-009 only
- `POST /api/document-analysis/strategy` - AGENT-010 only
- `POST /api/document-analysis/fact-check` - AGENT-011 only
- `GET /api/document-analysis/agents` - List agents
- `GET /api/document-analysis/health` - Service health

### Multi-Agent Orchestration (AGENT-012/013/014/015)
- `POST /api/orchestration/workflow` - Full 4-agent workflow
- `POST /api/orchestration/research` - AGENT-012 only
- `POST /api/orchestration/analyze` - AGENT-013 only
- `POST /api/orchestration/write` - AGENT-014 only
- `POST /api/orchestration/review` - AGENT-015 only
- `GET /api/orchestration/agents` - List agents
- `GET /api/orchestration/health` - Service health

---

## 12 Business Departments

AGENT-008 classifies content into these departments:

| # | Department | Examples |
|---|------------|----------|
| 1 | **IT & Engineering** | Software, infrastructure, APIs, DevOps, cloud |
| 2 | **Sales & Marketing** | Campaigns, leads, CRM, revenue, conversion |
| 3 | **Customer Support** | Tickets, help desk, SLA, satisfaction |
| 4 | **Operations & HR & Supply Chain** | Hiring, logistics, procurement, workforce |
| 5 | **Finance & Accounting** | Budgets, auditing, tax, reporting, compliance |
| 6 | **Project Management** | Agile/Scrum, milestones, planning, delivery |
| 7 | **Real Estate** | Property, leases, mortgages, tenant relations |
| 8 | **Private Equity & M&A** | Investments, acquisitions, due diligence, valuations |
| 9 | **Consulting** | Strategy, advisory, frameworks, client engagements |
| 10 | **Personal & Continuing Education** | Training, courses, certifications, skill building |
| 11 | **Research & Development (R&D)** | Innovation, prototyping, experiments, patents |
| 12 | **Global (_global)** | Cross-department content for multiple areas |

---

## Implementation Details

### Service Files

| File | Agents |
|------|--------|
| `app/services/content_summarizer_agent.py` | AGENT-002 |
| `app/services/department_classifier_agent.py` | AGENT-008 |
| `app/services/document_analysis_agents.py` | AGENT-009, 010, 011 |
| `app/services/multi_agent_orchestration.py` | AGENT-012, 013, 014, 015 |

### Route Files

| File | Endpoints |
|------|-----------|
| `app/routes/content_summarizer.py` | /api/summarizer/* |
| `app/routes/department_classifier.py` | /api/classifier/* |
| `app/routes/document_analysis.py` | /api/document-analysis/* |
| `app/routes/multi_agent_orchestration.py` | /api/orchestration/* |

### Test Coverage

| Test File | Tests |
|-----------|-------|
| `tests/test_content_summarizer.py` | 15 tests |
| `tests/test_department_classifier.py` | 18 tests |
| `tests/test_document_analysis_agents.py` | 45 tests |
| `tests/test_multi_agent_orchestration.py` | 62 tests |

---

## Key Points

1. **ALL AI processing uses Claude Sonnet 4.5** via Anthropic's cloud API
2. **No local LLM inference** - agents make API calls to Anthropic
3. **Cost is usage-based** - pay per token through Anthropic API
4. **17 specialized agents** for different document processing tasks
5. **Multi-agent workflows** coordinate multiple agents for complex analysis
6. **Graph Agent (AGENT-017)** provides Customer 360 views and graph-enhanced RAG
7. **Content Prep Agent (AGENT-016)** handles content set detection and file grouping

---

**Empire v7.3** - AI agents powered by Claude Sonnet 4.5 (Anthropic Cloud API)
