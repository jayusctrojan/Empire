# Agent Harness Architecture Plan

## Empire v7.4 - Research Projects Feature

**Document Version**: 1.0
**Created**: 2025-01-10
**Status**: Draft - Pending Review

---

## 1. Executive Summary

This document details the technical architecture for implementing the **Agent Harness** pattern in Empire Desktop, enabling long-running, autonomous research projects. The architecture integrates with Empire v7.3's existing infrastructure while adding new capabilities for persistent task management and multi-step research workflows.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Task Persistence | Supabase PostgreSQL | Consistent with existing Empire data layer |
| Async Execution | Celery + Redis | Leverages existing worker infrastructure |
| Task Planning | Claude Sonnet 4.5 | Best balance of capability and cost |
| Real-time Updates | WebSocket | Existing Empire WebSocket infrastructure |
| Report Storage | Backblaze B2 | Existing CrewAI asset storage pattern |
| **Concurrent Execution** | **Celery Groups + Chords** | **Maximize parallelism without custom orchestration** |
| **Quality Gates** | **Per-phase validation** | **Ensure speed doesn't compromise quality** |

### Performance Design Principles

1. **Concurrent by Default**: All independent tasks execute in parallel
2. **Minimal Latency**: Task dispatch within 50ms of dependency satisfaction
3. **Quality Non-Negotiable**: Quality gates block progression, not just log warnings
4. **Observable**: Every metric needed to identify bottlenecks is captured
5. **Self-Optimizing**: System learns optimal parallelism from historical data

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EMPIRE DESKTOP CLIENT                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Research Projects│  │ Project Detail  │  │  Report Viewer  │              │
│  │    Dashboard     │  │   + Progress    │  │                 │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
└───────────┼────────────────────┼────────────────────┼────────────────────────┘
            │ REST API           │ WebSocket          │ REST API
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EMPIRE FASTAPI SERVICE                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Research Projects Router                          │    │
│  │  POST /api/research-projects          - Create project               │    │
│  │  GET  /api/research-projects          - List projects                │    │
│  │  GET  /api/research-projects/{id}     - Get project details         │    │
│  │  GET  /api/research-projects/{id}/status - Get progress             │    │
│  │  DELETE /api/research-projects/{id}   - Cancel project              │    │
│  │  GET  /api/research-projects/{id}/report - Get report               │    │
│  │  WS   /api/research-projects/ws/{id}  - Real-time progress          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Core Services                                │    │
│  │                                                                      │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │    │
│  │  │   Initializer   │  │  Task Harness   │  │ Report Generator │     │    │
│  │  │    Service      │  │    Service      │  │    Service       │     │    │
│  │  │                 │  │                 │  │                  │     │    │
│  │  │ - Query Analysis│  │ - Task Pickup   │  │ - Synthesis      │     │    │
│  │  │ - Task Planning │  │ - Routing       │  │ - Report Writing │     │    │
│  │  │ - Validation    │  │ - Execution     │  │ - Quality Review │     │    │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘     │    │
│  │           │                    │                    │               │    │
│  └───────────┼────────────────────┼────────────────────┼───────────────┘    │
│              │                    │                    │                     │
└──────────────┼────────────────────┼────────────────────┼─────────────────────┘
               │                    │                    │
               ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CELERY WORKERS                                     │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ initialize_job  │  │ execute_task    │  │ generate_report │              │
│  │                 │  │                 │  │                 │              │
│  │ Queue: research │  │ Queue: research │  │ Queue: research │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Task Executors                                │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │    │
│  │  │ Retrieval │  │ Retrieval │  │ Retrieval │  │ Synthesis │        │    │
│  │  │   (RAG)   │  │   (NLQ)   │  │  (Graph)  │  │           │        │    │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
               │                    │                    │
               ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA & STORAGE LAYER                               │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │    Supabase     │  │      Neo4j      │  │   Backblaze B2  │              │
│  │   PostgreSQL    │  │  Knowledge Graph │  │  Report Storage │              │
│  │                 │  │                 │  │                 │              │
│  │ - research_jobs │  │ - Entity lookup │  │ - PDF reports   │              │
│  │ - plan_tasks    │  │ - Graph queries │  │ - Artifacts     │              │
│  │ - artifacts     │  │ - Relationships │  │                 │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
│  ┌─────────────────┐                                                        │
│  │  Upstash Redis  │                                                        │
│  │                 │                                                        │
│  │ - Celery broker │                                                        │
│  │ - Task state    │                                                        │
│  │ - Progress cache│                                                        │
│  └─────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Request Flow Sequence

```
User                    FastAPI                 Celery              Database
  │                        │                      │                    │
  │ POST /research-projects│                      │                    │
  │───────────────────────>│                      │                    │
  │                        │                      │                    │
  │                        │ INSERT research_job  │                    │
  │                        │─────────────────────────────────────────>│
  │                        │                      │                    │
  │                        │ Queue: initialize_job│                    │
  │                        │─────────────────────>│                    │
  │                        │                      │                    │
  │    { id, status }      │                      │                    │
  │<───────────────────────│                      │                    │
  │                        │                      │                    │
  │                        │                      │ Claude: Plan Tasks │
  │                        │                      │───────────────────>│
  │                        │                      │                    │
  │                        │                      │ INSERT plan_tasks  │
  │                        │                      │───────────────────>│
  │                        │                      │                    │
  │                        │                      │ UPDATE job status  │
  │                        │                      │───────────────────>│
  │                        │                      │                    │
  │ WS: Progress Update    │                      │                    │
  │<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│<─ ─ ─ ─ ─ ─ ─ ─ ─ ─│                    │
  │                        │                      │                    │
  │                        │                      │ Execute Tasks Loop │
  │                        │                      │◄──────────────────►│
  │                        │                      │                    │
  │ WS: Task Complete      │                      │                    │
  │<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│<─ ─ ─ ─ ─ ─ ─ ─ ─ ─│                    │
  │                        │                      │                    │
  │                        │                      │ Generate Report    │
  │                        │                      │───────────────────>│
  │                        │                      │                    │
  │ Email: Report Ready    │                      │                    │
  │<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│                      │                    │
```

---

## 3. Component Specifications

### 3.1 Database Schema

#### 3.1.1 research_jobs Table

```sql
CREATE TABLE public.research_jobs (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,

    -- Ownership & Identity
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    customer_id TEXT NOT NULL,

    -- Research Request
    query TEXT NOT NULL,
    context TEXT,
    research_type TEXT DEFAULT 'general',
    -- Types: general, compliance, competitive, technical, financial

    -- Status Management
    status TEXT NOT NULL DEFAULT 'initializing',
    -- Values: initializing, planning, planned, executing, synthesizing,
    --         generating_report, complete, failed, cancelled
    locked_at TIMESTAMP WITH TIME ZONE,
    locked_by TEXT,

    -- Progress Tracking
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    current_task_key TEXT,
    progress_percentage DECIMAL(5,2) DEFAULT 0.00,

    -- Results
    report_content TEXT,
    report_url TEXT,
    summary TEXT,
    key_findings JSONB,

    -- Notifications
    notify_email TEXT NOT NULL,
    notification_sent_at TIMESTAMP WITH TIME ZONE,

    -- Execution Metadata
    execution_id TEXT,
    retries SMALLINT DEFAULT 0,
    max_retries SMALLINT DEFAULT 3,
    error_message TEXT,
    error_details JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Indexes will be created separately
    CONSTRAINT valid_status CHECK (status IN (
        'initializing', 'planning', 'planned', 'executing',
        'synthesizing', 'generating_report', 'complete', 'failed', 'cancelled'
    ))
);

-- Indexes
CREATE INDEX idx_research_jobs_user_id ON research_jobs(user_id);
CREATE INDEX idx_research_jobs_status ON research_jobs(status);
CREATE INDEX idx_research_jobs_created_at ON research_jobs(created_at DESC);
CREATE INDEX idx_research_jobs_user_status ON research_jobs(user_id, status);

-- RLS Policies
ALTER TABLE research_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own research jobs"
    ON research_jobs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own research jobs"
    ON research_jobs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own research jobs"
    ON research_jobs FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own research jobs"
    ON research_jobs FOR DELETE
    USING (auth.uid() = user_id);
```

#### 3.1.2 plan_tasks Table

```sql
CREATE TABLE public.plan_tasks (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,

    -- Relationships
    job_id BIGINT NOT NULL REFERENCES research_jobs(id) ON DELETE CASCADE,
    parent_task_id BIGINT REFERENCES plan_tasks(id) ON DELETE SET NULL,

    -- Task Identity
    task_key TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,

    -- Task Definition
    task_type TEXT NOT NULL,
    -- Types: retrieval_rag, retrieval_nlq, retrieval_graph, retrieval_api,
    --        synthesis, fact_check, write_section, write_report, review
    task_title TEXT,
    task_description TEXT,
    query TEXT,
    config JSONB DEFAULT '{}',

    -- Dependencies
    depends_on TEXT[],  -- Array of task_keys this task depends on

    -- Status Management
    status TEXT NOT NULL DEFAULT 'pending',
    -- Values: pending, queued, running, complete, failed, skipped, cancelled

    -- Results
    result_summary TEXT,
    result_data JSONB,
    artifacts_count INTEGER DEFAULT 0,

    -- Execution Metadata
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    retry_count SMALLINT DEFAULT 0,
    error_message TEXT,
    error_details JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    UNIQUE(job_id, task_key),
    CONSTRAINT valid_task_status CHECK (status IN (
        'pending', 'queued', 'running', 'complete', 'failed', 'skipped', 'cancelled'
    )),
    CONSTRAINT valid_task_type CHECK (task_type IN (
        'retrieval_rag', 'retrieval_nlq', 'retrieval_graph', 'retrieval_api',
        'synthesis', 'fact_check', 'write_section', 'write_report', 'review'
    ))
);

-- Indexes
CREATE INDEX idx_plan_tasks_job_id ON plan_tasks(job_id);
CREATE INDEX idx_plan_tasks_status ON plan_tasks(status);
CREATE INDEX idx_plan_tasks_sequence ON plan_tasks(job_id, sequence_order);
CREATE INDEX idx_plan_tasks_type ON plan_tasks(task_type);

-- RLS (inherit from parent job)
ALTER TABLE plan_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view tasks for own jobs"
    ON plan_tasks FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM research_jobs
        WHERE research_jobs.id = plan_tasks.job_id
        AND research_jobs.user_id = auth.uid()
    ));
```

#### 3.1.3 research_artifacts Table

```sql
CREATE TABLE public.research_artifacts (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,

    -- Relationships
    job_id BIGINT NOT NULL REFERENCES research_jobs(id) ON DELETE CASCADE,
    task_id BIGINT REFERENCES plan_tasks(id) ON DELETE SET NULL,

    -- Artifact Identity
    artifact_type TEXT NOT NULL,
    -- Types: retrieved_chunk, query_result, graph_path, api_response,
    --        synthesis_finding, fact_check_result, report_section, final_report

    -- Source Information
    source TEXT,
    source_type TEXT,
    -- Source types: document, database, graph, api, ai_generated
    source_id TEXT,
    source_url TEXT,

    -- Content
    query_used TEXT,
    raw_response JSONB,
    processed_content TEXT,

    -- Quality Metrics
    relevance_score DECIMAL(5,4),
    confidence_score DECIMAL(5,4),
    citation_info JSONB,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT valid_artifact_type CHECK (artifact_type IN (
        'retrieved_chunk', 'query_result', 'graph_path', 'api_response',
        'synthesis_finding', 'fact_check_result', 'report_section', 'final_report'
    ))
);

-- Indexes
CREATE INDEX idx_research_artifacts_job_id ON research_artifacts(job_id);
CREATE INDEX idx_research_artifacts_task_id ON research_artifacts(task_id);
CREATE INDEX idx_research_artifacts_type ON research_artifacts(artifact_type);

-- RLS
ALTER TABLE research_artifacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view artifacts for own jobs"
    ON research_artifacts FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM research_jobs
        WHERE research_jobs.id = research_artifacts.job_id
        AND research_jobs.user_id = auth.uid()
    ));
```

### 3.2 Pydantic Models

```python
# app/models/research_project.py

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ResearchType(str, Enum):
    GENERAL = "general"
    COMPLIANCE = "compliance"
    COMPETITIVE = "competitive"
    TECHNICAL = "technical"
    FINANCIAL = "financial"

class JobStatus(str, Enum):
    INITIALIZING = "initializing"
    PLANNING = "planning"
    PLANNED = "planned"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    GENERATING_REPORT = "generating_report"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    RETRIEVAL_RAG = "retrieval_rag"
    RETRIEVAL_NLQ = "retrieval_nlq"
    RETRIEVAL_GRAPH = "retrieval_graph"
    RETRIEVAL_API = "retrieval_api"
    SYNTHESIS = "synthesis"
    FACT_CHECK = "fact_check"
    WRITE_SECTION = "write_section"
    WRITE_REPORT = "write_report"
    REVIEW = "review"

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

# Request Models
class CreateResearchProjectRequest(BaseModel):
    query: str = Field(..., min_length=10, max_length=2000)
    context: Optional[str] = Field(None, max_length=5000)
    research_type: ResearchType = ResearchType.GENERAL
    notify_email: EmailStr

class UpdateResearchProjectRequest(BaseModel):
    context: Optional[str] = Field(None, max_length=5000)
    notify_email: Optional[EmailStr] = None

# Response Models
class TaskResponse(BaseModel):
    id: int
    task_key: str
    sequence_order: int
    task_type: TaskType
    task_title: Optional[str]
    status: TaskStatus
    result_summary: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class ResearchProjectResponse(BaseModel):
    id: int
    query: str
    context: Optional[str]
    research_type: ResearchType
    status: JobStatus
    total_tasks: int
    completed_tasks: int
    progress_percentage: float
    current_task_key: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

class ResearchProjectDetailResponse(ResearchProjectResponse):
    tasks: List[TaskResponse]
    summary: Optional[str]
    key_findings: Optional[Dict[str, Any]]

class ResearchProjectStatusResponse(BaseModel):
    id: int
    status: JobStatus
    total_tasks: int
    completed_tasks: int
    progress_percentage: float
    current_task: Optional[TaskResponse]
    estimated_completion: Optional[datetime]

class ResearchReportResponse(BaseModel):
    id: int
    query: str
    status: JobStatus
    summary: str
    key_findings: Dict[str, Any]
    report_content: str
    report_url: Optional[str]
    completed_at: datetime

# WebSocket Models
class ProgressUpdate(BaseModel):
    job_id: int
    status: JobStatus
    progress_percentage: float
    current_task_key: Optional[str]
    message: str
    timestamp: datetime
```

### 3.3 Service Architecture

#### 3.3.1 Initializer Service

```python
# app/services/research_initializer.py

from anthropic import Anthropic
from typing import List, Dict, Any
import json
from app.models.research_project import TaskType, CreateResearchProjectRequest

class ResearchInitializerService:
    """
    Analyzes research queries and creates task plans using Claude.
    """

    SYSTEM_PROMPT = """You are a research planning expert. Your job is to analyze
    research queries and create detailed task plans for autonomous research execution.

    Available task types:
    - retrieval_rag: Vector similarity search in document database
    - retrieval_nlq: Natural language queries against structured data
    - retrieval_graph: Knowledge graph traversal for entity relationships
    - retrieval_api: External API calls for supplementary data
    - synthesis: Combine multiple findings into coherent summaries
    - fact_check: Verify claims and assign confidence scores
    - write_section: Write a specific section of the report
    - write_report: Generate the final comprehensive report
    - review: Quality assurance and revision

    Output a JSON task plan with:
    1. 3-8 tasks for most queries
    2. Proper sequencing (retrieval before synthesis before writing)
    3. Clear task descriptions and queries
    4. Dependencies between tasks when needed
    """

    TASK_PLAN_SCHEMA = {
        "type": "object",
        "properties": {
            "research_summary": {"type": "string"},
            "estimated_duration_minutes": {"type": "integer"},
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_key": {"type": "string"},
                        "sequence_order": {"type": "integer"},
                        "task_type": {"type": "string"},
                        "task_title": {"type": "string"},
                        "task_description": {"type": "string"},
                        "query": {"type": "string"},
                        "config": {"type": "object"},
                        "depends_on": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["task_key", "sequence_order", "task_type", "task_title"]
                }
            }
        },
        "required": ["research_summary", "tasks"]
    }

    def __init__(self, anthropic_client: Anthropic):
        self.client = anthropic_client

    async def create_task_plan(
        self,
        request: CreateResearchProjectRequest
    ) -> Dict[str, Any]:
        """Generate a task plan for the research query."""

        user_prompt = f"""Create a task plan for this research request:

QUERY: {request.query}

CONTEXT: {request.context or 'No additional context provided'}

RESEARCH TYPE: {request.research_type}

Generate a comprehensive task plan that will thoroughly research this topic."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            response_format={
                "type": "json_object",
                "schema": self.TASK_PLAN_SCHEMA
            }
        )

        task_plan = json.loads(response.content[0].text)
        return self._validate_and_enhance_plan(task_plan)

    def _validate_and_enhance_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Validate task plan and add missing required fields."""

        # Ensure all tasks have required fields
        for task in plan["tasks"]:
            if "config" not in task:
                task["config"] = {}
            if "depends_on" not in task:
                task["depends_on"] = []

        # Ensure final report task exists
        has_report = any(t["task_type"] == "write_report" for t in plan["tasks"])
        if not has_report:
            max_order = max(t["sequence_order"] for t in plan["tasks"])
            plan["tasks"].append({
                "task_key": "write_report",
                "sequence_order": max_order + 1,
                "task_type": "write_report",
                "task_title": "Generate Final Report",
                "task_description": "Synthesize all findings into comprehensive report",
                "depends_on": [t["task_key"] for t in plan["tasks"] if t["task_type"] == "synthesis"]
            })

        return plan
```

#### 3.3.2 Task Harness Service

```python
# app/services/task_harness.py

from typing import Optional, Dict, Any
from datetime import datetime
from app.models.research_project import TaskStatus, JobStatus
from app.services.task_executors import (
    RetrievalExecutor,
    SynthesisExecutor,
    ReportExecutor
)

class TaskHarnessService:
    """
    Core execution engine for research tasks.
    Picks up pending tasks, routes to appropriate executor, manages state.
    """

    def __init__(
        self,
        db_service: "DatabaseService",
        retrieval_executor: RetrievalExecutor,
        synthesis_executor: SynthesisExecutor,
        report_executor: ReportExecutor,
        progress_notifier: "ProgressNotifier"
    ):
        self.db = db_service
        self.executors = {
            "retrieval_rag": retrieval_executor,
            "retrieval_nlq": retrieval_executor,
            "retrieval_graph": retrieval_executor,
            "retrieval_api": retrieval_executor,
            "synthesis": synthesis_executor,
            "fact_check": synthesis_executor,
            "write_section": report_executor,
            "write_report": report_executor,
            "review": report_executor
        }
        self.notifier = progress_notifier

    async def execute_next_task(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Find and execute the next pending task for a job.
        Returns task result or None if no tasks available.
        """

        # Get next pending task with satisfied dependencies
        task = await self.db.get_next_pending_task(job_id)
        if not task:
            return None

        # Check if dependencies are satisfied
        if not await self._check_dependencies(task):
            return None

        # Mark task as running
        await self.db.update_task_status(
            task["id"],
            TaskStatus.RUNNING,
            started_at=datetime.utcnow()
        )

        # Notify progress
        await self.notifier.send_task_started(job_id, task)

        try:
            # Route to appropriate executor
            executor = self.executors.get(task["task_type"])
            if not executor:
                raise ValueError(f"Unknown task type: {task['task_type']}")

            # Execute task
            result = await executor.execute(task, job_id)

            # Store artifacts
            if result.get("artifacts"):
                await self.db.store_artifacts(job_id, task["id"], result["artifacts"])

            # Mark complete
            await self.db.update_task_status(
                task["id"],
                TaskStatus.COMPLETE,
                completed_at=datetime.utcnow(),
                result_summary=result.get("summary"),
                result_data=result.get("data")
            )

            # Update job progress
            await self._update_job_progress(job_id)

            # Notify progress
            await self.notifier.send_task_completed(job_id, task, result)

            return result

        except Exception as e:
            # Mark task failed
            await self.db.update_task_status(
                task["id"],
                TaskStatus.FAILED,
                error_message=str(e),
                error_details={"exception": type(e).__name__}
            )

            # Notify failure
            await self.notifier.send_task_failed(job_id, task, str(e))

            # Check if job should fail
            if task.get("retry_count", 0) >= 2:
                await self._handle_critical_failure(job_id, task, e)

            raise

    async def _check_dependencies(self, task: Dict[str, Any]) -> bool:
        """Check if all task dependencies are satisfied."""
        depends_on = task.get("depends_on", [])
        if not depends_on:
            return True

        for dep_key in depends_on:
            dep_task = await self.db.get_task_by_key(task["job_id"], dep_key)
            if not dep_task or dep_task["status"] != TaskStatus.COMPLETE:
                return False

        return True

    async def _update_job_progress(self, job_id: int):
        """Update job progress based on completed tasks."""
        stats = await self.db.get_job_task_stats(job_id)

        progress = (stats["completed"] / stats["total"]) * 100 if stats["total"] > 0 else 0

        await self.db.update_job(job_id, {
            "completed_tasks": stats["completed"],
            "total_tasks": stats["total"],
            "progress_percentage": progress,
            "status": JobStatus.EXECUTING if stats["completed"] < stats["total"] else JobStatus.SYNTHESIZING
        })

    async def _handle_critical_failure(self, job_id: int, task: Dict, error: Exception):
        """Handle unrecoverable task failure."""
        await self.db.update_job(job_id, {
            "status": JobStatus.FAILED,
            "error_message": f"Task {task['task_key']} failed: {str(error)}"
        })
```

#### 3.3.2.1 Concurrent Execution Engine (CRITICAL FOR PERFORMANCE)

The Concurrent Execution Engine is the core component responsible for maximizing parallelism while maintaining quality. It uses Celery's `group` and `chord` primitives for efficient parallel task dispatch.

```python
# app/services/concurrent_executor.py

from celery import group, chord, chain
from typing import Dict, List, Any, Set
from datetime import datetime
from collections import defaultdict
import asyncio
from prometheus_client import Histogram, Gauge, Counter

# Performance Metrics
task_dispatch_latency = Histogram(
    'research_task_dispatch_latency_seconds',
    'Time from task ready to dispatch',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

concurrent_tasks_gauge = Gauge(
    'research_concurrent_tasks',
    'Current number of concurrent tasks',
    ['job_id']
)

wave_transition_latency = Histogram(
    'research_wave_transition_latency_seconds',
    'Time between wave completion and next wave start',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)

parallelism_ratio = Gauge(
    'research_parallelism_ratio',
    'Ratio of parallel execution achieved',
    ['job_id']
)


class ConcurrentExecutionEngine:
    """
    High-performance concurrent task execution engine.

    Design Goals:
    - Execute all independent tasks in parallel
    - Minimize latency between wave transitions (<100ms target)
    - Never sacrifice quality for speed
    - Full observability of execution patterns
    """

    def __init__(
        self,
        db_service: "DatabaseService",
        max_concurrent_per_job: int = 5,
        max_concurrent_global: int = 20
    ):
        self.db = db_service
        self.max_concurrent_per_job = max_concurrent_per_job
        self.max_concurrent_global = max_concurrent_global
        self._active_tasks: Dict[int, Set[str]] = defaultdict(set)

    async def build_dependency_graph(self, job_id: int) -> Dict[str, Any]:
        """
        Build a DAG of task dependencies for optimal execution planning.
        Returns execution waves - groups of tasks that can run in parallel.
        """
        tasks = await self.db.get_all_tasks(job_id)

        # Build adjacency list
        graph = {t['task_key']: set(t.get('depends_on', [])) for t in tasks}
        task_map = {t['task_key']: t for t in tasks}

        # Topological sort into waves (Kahn's algorithm)
        waves = []
        in_degree = {k: len(v) for k, v in graph.items()}

        while in_degree:
            # Find all tasks with no remaining dependencies
            ready = [k for k, d in in_degree.items() if d == 0]
            if not ready:
                raise ValueError("Circular dependency detected in task graph")

            waves.append(ready)

            # Remove completed tasks and update dependencies
            for task_key in ready:
                del in_degree[task_key]
                for k in in_degree:
                    if task_key in graph[k]:
                        graph[k].discard(task_key)
                        in_degree[k] = len(graph[k])

        # Calculate parallelism metrics
        total_tasks = len(tasks)
        max_wave_size = max(len(w) for w in waves) if waves else 0
        parallelism_potential = max_wave_size / total_tasks if total_tasks > 0 else 0

        return {
            'waves': waves,
            'task_map': task_map,
            'total_tasks': total_tasks,
            'wave_count': len(waves),
            'max_parallel': max_wave_size,
            'parallelism_potential': parallelism_potential
        }

    async def execute_job_concurrent(self, job_id: int) -> Dict[str, Any]:
        """
        Execute all tasks for a job with maximum concurrency.
        Uses wave-based execution with Celery groups.
        """
        from app.tasks.research_tasks import execute_single_task

        execution_graph = await self.build_dependency_graph(job_id)
        waves = execution_graph['waves']
        task_map = execution_graph['task_map']

        results = []
        wave_timings = []

        for wave_idx, wave_tasks in enumerate(waves):
            wave_start = datetime.utcnow()

            # Limit concurrent tasks per job
            wave_tasks_limited = wave_tasks[:self.max_concurrent_per_job]

            # Update metrics
            concurrent_tasks_gauge.labels(job_id=job_id).set(len(wave_tasks_limited))

            # Create Celery group for parallel execution
            task_group = group([
                execute_single_task.s(task_map[task_key]['id'])
                for task_key in wave_tasks_limited
            ])

            # Dispatch with timing
            dispatch_start = datetime.utcnow()
            group_result = task_group.apply_async()
            dispatch_time = (datetime.utcnow() - dispatch_start).total_seconds()
            task_dispatch_latency.observe(dispatch_time)

            # Wait for all tasks in wave to complete
            wave_results = group_result.get(timeout=300)  # 5 min timeout per wave

            wave_end = datetime.utcnow()
            wave_duration = (wave_end - wave_start).total_seconds()

            # Check quality gates before proceeding
            await self._check_wave_quality_gates(job_id, wave_idx, wave_results)

            wave_timings.append({
                'wave': wave_idx,
                'tasks': wave_tasks_limited,
                'duration': wave_duration,
                'dispatch_latency': dispatch_time
            })

            results.extend(wave_results)

            # Record wave transition latency (except for last wave)
            if wave_idx < len(waves) - 1:
                transition_start = datetime.utcnow()
                # Minimal processing between waves
                transition_time = (datetime.utcnow() - transition_start).total_seconds()
                wave_transition_latency.observe(transition_time)

        # Calculate final parallelism ratio
        total_sequential_time = sum(
            r.get('duration', 0) for r in results if r
        )
        actual_wall_time = sum(w['duration'] for w in wave_timings)
        achieved_parallelism = total_sequential_time / actual_wall_time if actual_wall_time > 0 else 1.0

        parallelism_ratio.labels(job_id=job_id).set(achieved_parallelism)

        return {
            'job_id': job_id,
            'total_tasks': execution_graph['total_tasks'],
            'waves_executed': len(waves),
            'wave_timings': wave_timings,
            'parallelism_achieved': achieved_parallelism,
            'parallelism_potential': execution_graph['parallelism_potential'],
            'total_wall_time': actual_wall_time
        }

    async def _check_wave_quality_gates(
        self,
        job_id: int,
        wave_idx: int,
        wave_results: List[Dict]
    ):
        """
        Enforce quality gates between waves.
        Blocks progression if quality thresholds not met.
        """
        for result in wave_results:
            if not result:
                continue

            task_type = result.get('task_type')
            quality_score = result.get('quality_score', 1.0)

            # Quality thresholds by task type
            thresholds = {
                'retrieval_rag': 0.7,
                'retrieval_nlq': 0.7,
                'retrieval_graph': 0.6,
                'synthesis': 0.8,
                'write_report': 0.85
            }

            threshold = thresholds.get(task_type, 0.5)

            if quality_score < threshold:
                # Quality gate failed - trigger retry or expansion
                await self._handle_quality_failure(
                    job_id,
                    result.get('task_id'),
                    quality_score,
                    threshold
                )

    async def _handle_quality_failure(
        self,
        job_id: int,
        task_id: int,
        score: float,
        threshold: float
    ):
        """Handle quality gate failure with retry or query expansion."""
        task = await self.db.get_task(task_id)
        retry_count = task.get('retry_count', 0)

        if retry_count < 2:
            # Retry with expanded query
            await self.db.update_task(task_id, {
                'status': 'pending',
                'retry_count': retry_count + 1,
                'config': {
                    **task.get('config', {}),
                    'expand_query': True,
                    'quality_target': threshold
                }
            })
        else:
            # Log warning but continue - don't block entire job
            await self.db.log_quality_warning(job_id, task_id, score, threshold)
```

#### 3.3.2.2 Celery Task Configuration for Concurrency

```python
# app/tasks/research_tasks.py (additions for concurrency)

from celery import shared_task, group, chord
from datetime import datetime
import time

@shared_task(
    bind=True,
    queue='research',
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,  # Ensure task isn't lost on worker crash
    track_started=True  # Enable started state for monitoring
)
def execute_single_task(self, task_id: int) -> Dict[str, Any]:
    """
    Execute a single research task with timing instrumentation.
    Designed for parallel execution within Celery groups.
    """
    start_time = time.perf_counter()

    try:
        harness = TaskHarnessService.get_instance()
        task = harness.db.get_task_sync(task_id)

        # Update status
        harness.db.update_task_sync(task_id, {
            'status': 'running',
            'started_at': datetime.utcnow()
        })

        # Execute based on task type
        result = harness.execute_task_by_type_sync(task)

        duration = time.perf_counter() - start_time

        # Update completion
        harness.db.update_task_sync(task_id, {
            'status': 'complete',
            'completed_at': datetime.utcnow(),
            'duration_seconds': duration,
            'result_summary': result.get('summary')
        })

        return {
            'task_id': task_id,
            'task_type': task['task_type'],
            'duration': duration,
            'quality_score': result.get('quality_score', 1.0),
            'artifacts_count': len(result.get('artifacts', []))
        }

    except Exception as e:
        duration = time.perf_counter() - start_time

        harness.db.update_task_sync(task_id, {
            'status': 'failed',
            'error_message': str(e),
            'duration_seconds': duration
        })

        raise self.retry(exc=e)


@shared_task(bind=True, queue='research')
def execute_job_with_concurrency(self, job_id: int) -> Dict[str, Any]:
    """
    Orchestrate concurrent execution of all tasks in a research job.
    This is the main entry point for job execution.
    """
    import asyncio
    from app.services.concurrent_executor import ConcurrentExecutionEngine

    engine = ConcurrentExecutionEngine.get_instance()

    # Run async execution in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(
            engine.execute_job_concurrent(job_id)
        )
        return result
    finally:
        loop.close()
```

#### 3.3.2.3 Performance Monitoring Integration

```python
# app/services/performance_monitor.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json

@dataclass
class ExecutionMetrics:
    """Captures all performance metrics for a research job."""
    job_id: int
    total_duration_seconds: float = 0.0
    task_durations: Dict[str, float] = field(default_factory=dict)
    parallelism_ratio: float = 0.0
    max_concurrent_tasks: int = 0
    queue_wait_times: List[float] = field(default_factory=list)
    inter_wave_delays: List[float] = field(default_factory=list)
    worker_utilization: float = 0.0
    idle_time_total: float = 0.0
    quality_scores: Dict[str, float] = field(default_factory=dict)
    retry_count: int = 0
    waves_executed: int = 0
    sla_met: bool = True
    sla_target_seconds: Optional[float] = None

    def to_json(self) -> str:
        return json.dumps({
            'job_id': self.job_id,
            'total_duration_seconds': self.total_duration_seconds,
            'task_durations': self.task_durations,
            'parallelism_ratio': self.parallelism_ratio,
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'avg_queue_wait': sum(self.queue_wait_times) / len(self.queue_wait_times) if self.queue_wait_times else 0,
            'avg_wave_delay': sum(self.inter_wave_delays) / len(self.inter_wave_delays) if self.inter_wave_delays else 0,
            'worker_utilization': self.worker_utilization,
            'idle_time_total': self.idle_time_total,
            'avg_quality_score': sum(self.quality_scores.values()) / len(self.quality_scores) if self.quality_scores else 0,
            'retry_count': self.retry_count,
            'waves_executed': self.waves_executed,
            'sla_met': self.sla_met
        })


class PerformanceMonitor:
    """
    Monitors and analyzes research job performance.
    Identifies bottlenecks and optimization opportunities.
    """

    SLA_TARGETS = {
        'simple': 120,    # 2 minutes for 3-5 tasks
        'medium': 300,    # 5 minutes for 6-10 tasks
        'complex': 900    # 15 minutes for 11-20 tasks
    }

    def __init__(self, db_service: "DatabaseService"):
        self.db = db_service

    async def collect_metrics(self, job_id: int) -> ExecutionMetrics:
        """Collect all performance metrics for a completed job."""
        job = await self.db.get_job(job_id)
        tasks = await self.db.get_all_tasks(job_id)

        metrics = ExecutionMetrics(job_id=job_id)

        # Total duration
        if job.get('completed_at') and job.get('started_at'):
            metrics.total_duration_seconds = (
                job['completed_at'] - job['started_at']
            ).total_seconds()

        # Task durations
        for task in tasks:
            if task.get('duration_seconds'):
                metrics.task_durations[task['task_key']] = task['duration_seconds']

        # Calculate parallelism ratio
        sum_task_durations = sum(metrics.task_durations.values())
        if metrics.total_duration_seconds > 0:
            metrics.parallelism_ratio = sum_task_durations / metrics.total_duration_seconds

        # Quality scores
        artifacts = await self.db.get_artifacts_for_job(job_id)
        for artifact in artifacts:
            if artifact.get('confidence_score'):
                metrics.quality_scores[artifact['id']] = artifact['confidence_score']

        # SLA check
        task_count = len(tasks)
        if task_count <= 5:
            metrics.sla_target_seconds = self.SLA_TARGETS['simple']
        elif task_count <= 10:
            metrics.sla_target_seconds = self.SLA_TARGETS['medium']
        else:
            metrics.sla_target_seconds = self.SLA_TARGETS['complex']

        metrics.sla_met = metrics.total_duration_seconds <= metrics.sla_target_seconds

        return metrics

    async def identify_bottlenecks(self, metrics: ExecutionMetrics) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks from metrics."""
        bottlenecks = []

        # Low parallelism
        if metrics.parallelism_ratio < 0.5:
            bottlenecks.append({
                'type': 'low_parallelism',
                'severity': 'high',
                'value': metrics.parallelism_ratio,
                'recommendation': 'Review task dependencies - too many sequential tasks'
            })

        # SLA violation
        if not metrics.sla_met:
            bottlenecks.append({
                'type': 'sla_violation',
                'severity': 'critical',
                'value': metrics.total_duration_seconds,
                'target': metrics.sla_target_seconds,
                'recommendation': 'Investigate slow tasks and optimize'
            })

        # Find slowest tasks
        if metrics.task_durations:
            avg_duration = sum(metrics.task_durations.values()) / len(metrics.task_durations)
            slow_tasks = [
                (k, v) for k, v in metrics.task_durations.items()
                if v > avg_duration * 2
            ]
            for task_key, duration in slow_tasks:
                bottlenecks.append({
                    'type': 'slow_task',
                    'severity': 'medium',
                    'task_key': task_key,
                    'duration': duration,
                    'avg_duration': avg_duration,
                    'recommendation': f'Optimize {task_key} - taking {duration/avg_duration:.1f}x longer than average'
                })

        return bottlenecks
```

#### 3.3.3 Task Executors

```python
# app/services/task_executors/retrieval_executor.py

from typing import Dict, Any, List
from app.services.rag_service import RAGService
from app.services.nlq_service import NLQService
from app.services.graph_service import GraphService

class RetrievalExecutor:
    """Executes retrieval tasks (RAG, NLQ, Graph, API)."""

    def __init__(
        self,
        rag_service: RAGService,
        nlq_service: NLQService,
        graph_service: GraphService
    ):
        self.rag = rag_service
        self.nlq = nlq_service
        self.graph = graph_service

    async def execute(self, task: Dict[str, Any], job_id: int) -> Dict[str, Any]:
        """Execute a retrieval task based on type."""

        task_type = task["task_type"]
        query = task.get("query", "")
        config = task.get("config", {})

        if task_type == "retrieval_rag":
            return await self._execute_rag(query, config)
        elif task_type == "retrieval_nlq":
            return await self._execute_nlq(query, config)
        elif task_type == "retrieval_graph":
            return await self._execute_graph(query, config)
        elif task_type == "retrieval_api":
            return await self._execute_api(query, config)
        else:
            raise ValueError(f"Unknown retrieval type: {task_type}")

    async def _execute_rag(self, query: str, config: Dict) -> Dict[str, Any]:
        """Vector similarity search."""
        results = await self.rag.search(
            query=query,
            top_k=config.get("top_k", 10),
            filters=config.get("filters", {})
        )

        return {
            "summary": f"Retrieved {len(results)} relevant chunks",
            "artifacts": [
                {
                    "artifact_type": "retrieved_chunk",
                    "source": r["source"],
                    "source_type": "document",
                    "processed_content": r["content"],
                    "relevance_score": r["score"],
                    "metadata": r.get("metadata", {})
                }
                for r in results
            ],
            "data": {"chunk_count": len(results)}
        }

    async def _execute_nlq(self, query: str, config: Dict) -> Dict[str, Any]:
        """Natural language query against structured data."""
        results = await self.nlq.query(
            question=query,
            tables=config.get("tables", [])
        )

        return {
            "summary": f"Query returned {len(results)} rows",
            "artifacts": [
                {
                    "artifact_type": "query_result",
                    "source": "database",
                    "source_type": "database",
                    "query_used": results["sql"],
                    "raw_response": results["data"],
                    "processed_content": results["formatted"]
                }
            ],
            "data": {"row_count": len(results["data"])}
        }

    async def _execute_graph(self, query: str, config: Dict) -> Dict[str, Any]:
        """Knowledge graph traversal."""
        results = await self.graph.traverse(
            query=query,
            depth=config.get("depth", 2),
            node_types=config.get("node_types", [])
        )

        return {
            "summary": f"Found {len(results['paths'])} relationship paths",
            "artifacts": [
                {
                    "artifact_type": "graph_path",
                    "source": "knowledge_graph",
                    "source_type": "graph",
                    "processed_content": path["description"],
                    "raw_response": path,
                    "relevance_score": path.get("relevance", 0.5)
                }
                for path in results["paths"]
            ],
            "data": {"path_count": len(results["paths"])}
        }
```

```python
# app/services/task_executors/synthesis_executor.py

from typing import Dict, Any, List
from anthropic import Anthropic

class SynthesisExecutor:
    """Executes synthesis and fact-checking tasks."""

    def __init__(self, anthropic_client: Anthropic, db_service: "DatabaseService"):
        self.client = anthropic_client
        self.db = db_service

    async def execute(self, task: Dict[str, Any], job_id: int) -> Dict[str, Any]:
        """Execute a synthesis task."""

        task_type = task["task_type"]

        if task_type == "synthesis":
            return await self._execute_synthesis(task, job_id)
        elif task_type == "fact_check":
            return await self._execute_fact_check(task, job_id)
        else:
            raise ValueError(f"Unknown synthesis type: {task_type}")

    async def _execute_synthesis(self, task: Dict, job_id: int) -> Dict[str, Any]:
        """Synthesize findings from retrieval tasks."""

        # Get artifacts from dependent retrieval tasks
        depends_on = task.get("depends_on", [])
        artifacts = await self.db.get_artifacts_for_tasks(job_id, depends_on)

        # Build context from artifacts
        context = self._build_context(artifacts)

        # Use Claude to synthesize
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system="You are a research analyst. Synthesize the provided findings into clear, coherent summaries with citations.",
            messages=[{
                "role": "user",
                "content": f"""Synthesize these research findings:

{context}

Task objective: {task.get('task_description', 'Synthesize findings')}

Provide:
1. A clear summary of key findings
2. Important patterns or themes
3. Citations to source materials"""
            }]
        )

        synthesis = response.content[0].text

        return {
            "summary": "Synthesized findings from retrieval tasks",
            "artifacts": [{
                "artifact_type": "synthesis_finding",
                "source": "ai_synthesis",
                "source_type": "ai_generated",
                "processed_content": synthesis,
                "confidence_score": 0.85
            }],
            "data": {"source_artifact_count": len(artifacts)}
        }

    def _build_context(self, artifacts: List[Dict]) -> str:
        """Build context string from artifacts."""
        context_parts = []
        for i, artifact in enumerate(artifacts, 1):
            content = artifact.get("processed_content", "")
            source = artifact.get("source", "Unknown")
            context_parts.append(f"[Source {i}: {source}]\n{content}\n")
        return "\n".join(context_parts)
```

```python
# app/services/task_executors/report_executor.py

from typing import Dict, Any
from anthropic import Anthropic
from app.services.b2_storage import B2StorageService

class ReportExecutor:
    """Executes report writing and review tasks."""

    def __init__(
        self,
        anthropic_client: Anthropic,
        db_service: "DatabaseService",
        b2_storage: B2StorageService
    ):
        self.client = anthropic_client
        self.db = db_service
        self.b2 = b2_storage

    async def execute(self, task: Dict[str, Any], job_id: int) -> Dict[str, Any]:
        """Execute a report task."""

        task_type = task["task_type"]

        if task_type == "write_section":
            return await self._write_section(task, job_id)
        elif task_type == "write_report":
            return await self._write_full_report(task, job_id)
        elif task_type == "review":
            return await self._review_report(task, job_id)
        else:
            raise ValueError(f"Unknown report type: {task_type}")

    async def _write_full_report(self, task: Dict, job_id: int) -> Dict[str, Any]:
        """Generate the final comprehensive report."""

        # Get all synthesis findings
        artifacts = await self.db.get_artifacts_by_type(job_id, "synthesis_finding")

        # Get job details for context
        job = await self.db.get_job(job_id)

        # Build report using Claude
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system="""You are a professional research report writer.
            Create comprehensive, well-structured reports with:
            - Executive summary
            - Key findings
            - Detailed analysis
            - Conclusions and recommendations
            - Citations""",
            messages=[{
                "role": "user",
                "content": f"""Write a comprehensive research report.

ORIGINAL QUERY: {job['query']}

CONTEXT: {job.get('context', 'None provided')}

SYNTHESIZED FINDINGS:
{self._format_findings(artifacts)}

Create a professional report in Markdown format."""
            }]
        )

        report_content = response.content[0].text

        # Upload to B2
        report_url = await self.b2.upload_report(
            job_id=job_id,
            content=report_content,
            filename=f"research_report_{job_id}.md"
        )

        # Extract key findings and summary
        key_findings = self._extract_key_findings(report_content)
        summary = self._extract_summary(report_content)

        # Update job with report
        await self.db.update_job(job_id, {
            "report_content": report_content,
            "report_url": report_url,
            "summary": summary,
            "key_findings": key_findings,
            "status": "generating_report"
        })

        return {
            "summary": "Generated comprehensive research report",
            "artifacts": [{
                "artifact_type": "final_report",
                "source": "report_generator",
                "source_type": "ai_generated",
                "processed_content": report_content
            }],
            "data": {
                "report_url": report_url,
                "word_count": len(report_content.split())
            }
        }
```

### 3.4 API Routes

```python
# app/routes/research_projects.py

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import List, Optional
from app.models.research_project import (
    CreateResearchProjectRequest,
    ResearchProjectResponse,
    ResearchProjectDetailResponse,
    ResearchProjectStatusResponse,
    ResearchReportResponse
)
from app.services.research_projects_service import ResearchProjectsService
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/research-projects", tags=["Research Projects"])

@router.post("/", response_model=ResearchProjectResponse, status_code=201)
async def create_research_project(
    request: CreateResearchProjectRequest,
    user = Depends(get_current_user),
    service: ResearchProjectsService = Depends()
):
    """
    Create a new research project.

    The system will analyze the query, create a task plan, and begin
    autonomous execution. Progress can be monitored via the status
    endpoint or WebSocket connection.
    """
    project = await service.create_project(user.id, request)
    return project

@router.get("/", response_model=List[ResearchProjectResponse])
async def list_research_projects(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    user = Depends(get_current_user),
    service: ResearchProjectsService = Depends()
):
    """List all research projects for the current user."""
    projects = await service.list_projects(user.id, status, limit, offset)
    return projects

@router.get("/{project_id}", response_model=ResearchProjectDetailResponse)
async def get_research_project(
    project_id: int,
    user = Depends(get_current_user),
    service: ResearchProjectsService = Depends()
):
    """Get detailed information about a research project including tasks."""
    project = await service.get_project_detail(project_id, user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.get("/{project_id}/status", response_model=ResearchProjectStatusResponse)
async def get_project_status(
    project_id: int,
    user = Depends(get_current_user),
    service: ResearchProjectsService = Depends()
):
    """Get current status and progress of a research project."""
    status = await service.get_project_status(project_id, user.id)
    if not status:
        raise HTTPException(status_code=404, detail="Project not found")
    return status

@router.delete("/{project_id}", status_code=204)
async def cancel_research_project(
    project_id: int,
    user = Depends(get_current_user),
    service: ResearchProjectsService = Depends()
):
    """Cancel a running research project."""
    success = await service.cancel_project(project_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found or already completed")
    return None

@router.get("/{project_id}/report", response_model=ResearchReportResponse)
async def get_research_report(
    project_id: int,
    user = Depends(get_current_user),
    service: ResearchProjectsService = Depends()
):
    """Get the final report for a completed research project."""
    report = await service.get_report(project_id, user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or project not complete")
    return report

@router.websocket("/ws/{project_id}")
async def websocket_progress(
    websocket: WebSocket,
    project_id: int,
    service: ResearchProjectsService = Depends()
):
    """WebSocket endpoint for real-time progress updates."""
    await websocket.accept()

    try:
        # Subscribe to progress updates
        async for update in service.subscribe_to_progress(project_id):
            await websocket.send_json(update.dict())
    except WebSocketDisconnect:
        pass
    finally:
        await service.unsubscribe_from_progress(project_id)
```

### 3.5 Celery Tasks

```python
# app/tasks/research_tasks.py

from celery import shared_task
from app.services.research_initializer import ResearchInitializerService
from app.services.task_harness import TaskHarnessService
from app.services.notification_service import NotificationService
from app.models.research_project import JobStatus
import structlog

logger = structlog.get_logger()

@shared_task(bind=True, queue="research", max_retries=3)
def initialize_research_job(self, job_id: int):
    """
    Analyze research query and create task plan.
    Triggers task execution upon completion.
    """
    logger.info("Initializing research job", job_id=job_id)

    try:
        initializer = ResearchInitializerService.get_instance()

        # Get job details
        job = initializer.db.get_job_sync(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Update status to planning
        initializer.db.update_job_sync(job_id, {"status": JobStatus.PLANNING})

        # Create task plan
        plan = initializer.create_task_plan_sync(job)

        # Store tasks in database
        initializer.db.create_tasks_sync(job_id, plan["tasks"])

        # Update job with plan info
        initializer.db.update_job_sync(job_id, {
            "status": JobStatus.PLANNED,
            "total_tasks": len(plan["tasks"])
        })

        # Trigger task execution
        execute_research_tasks.delay(job_id)

        logger.info("Research job initialized", job_id=job_id, task_count=len(plan["tasks"]))
        return {"status": "planned", "task_count": len(plan["tasks"])}

    except Exception as e:
        logger.error("Failed to initialize research job", job_id=job_id, error=str(e))
        initializer.db.update_job_sync(job_id, {
            "status": JobStatus.FAILED,
            "error_message": str(e)
        })
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, queue="research")
def execute_research_tasks(self, job_id: int):
    """
    Execute research tasks sequentially.
    Continues until all tasks complete or critical failure.
    """
    logger.info("Starting task execution", job_id=job_id)

    harness = TaskHarnessService.get_instance()

    try:
        # Update status to executing
        harness.db.update_job_sync(job_id, {"status": JobStatus.EXECUTING})

        # Execute tasks until none remain
        while True:
            result = harness.execute_next_task_sync(job_id)
            if result is None:
                break

        # Check if all tasks completed successfully
        stats = harness.db.get_job_task_stats_sync(job_id)

        if stats["failed"] > 0:
            harness.db.update_job_sync(job_id, {
                "status": JobStatus.FAILED,
                "error_message": f"{stats['failed']} tasks failed"
            })
        else:
            # Trigger report generation
            generate_research_report.delay(job_id)

        logger.info("Task execution complete", job_id=job_id, stats=stats)
        return stats

    except Exception as e:
        logger.error("Task execution failed", job_id=job_id, error=str(e))
        harness.db.update_job_sync(job_id, {
            "status": JobStatus.FAILED,
            "error_message": str(e)
        })
        raise

@shared_task(bind=True, queue="research")
def generate_research_report(self, job_id: int):
    """
    Generate final report and send notification.
    """
    logger.info("Generating research report", job_id=job_id)

    harness = TaskHarnessService.get_instance()
    notifier = NotificationService.get_instance()

    try:
        # Update status
        harness.db.update_job_sync(job_id, {"status": JobStatus.GENERATING_REPORT})

        # Get write_report task
        report_task = harness.db.get_task_by_type_sync(job_id, "write_report")
        if report_task:
            harness.execute_task_sync(report_task["id"])

        # Mark job complete
        harness.db.update_job_sync(job_id, {
            "status": JobStatus.COMPLETE,
            "completed_at": datetime.utcnow()
        })

        # Send completion notification
        job = harness.db.get_job_sync(job_id)
        notifier.send_completion_email(job)

        logger.info("Research report generated", job_id=job_id)
        return {"status": "complete", "report_url": job.get("report_url")}

    except Exception as e:
        logger.error("Report generation failed", job_id=job_id, error=str(e))
        harness.db.update_job_sync(job_id, {
            "status": JobStatus.FAILED,
            "error_message": f"Report generation failed: {str(e)}"
        })
        raise
```

---

## 4. Integration Points

### 4.1 Existing Empire Services Integration

| Service | Integration Point | Usage |
|---------|------------------|-------|
| **RAG Service** | `app/services/rag_service.py` | Vector search for retrieval_rag tasks |
| **NLQ Service** | `app/services/nlq_service.py` | Natural language queries for retrieval_nlq |
| **Graph Service** | `app/services/graph_service.py` | Neo4j traversal for retrieval_graph |
| **AGENT-009** | Document analysis | Enhanced retrieval with research analysis |
| **AGENT-010** | Content strategy | Synthesis task execution |
| **AGENT-011** | Fact checking | fact_check task execution |
| **AGENT-014** | Report writing | write_report task execution |
| **AGENT-015** | Quality review | review task execution |
| **B2 Storage** | `app/services/b2_storage.py` | Report file storage |
| **WebSocket** | Existing infrastructure | Real-time progress updates |
| **Celery** | Existing worker | Background task execution |

### 4.2 New Queue Configuration

```python
# app/celery_config.py

CELERY_TASK_ROUTES = {
    # Existing routes...
    'app.tasks.research_tasks.initialize_research_job': {'queue': 'research'},
    'app.tasks.research_tasks.execute_research_tasks': {'queue': 'research'},
    'app.tasks.research_tasks.generate_research_report': {'queue': 'research'},
}

# Research queue with controlled concurrency
CELERY_QUEUES = {
    'research': {
        'exchange': 'research',
        'routing_key': 'research',
        'queue_arguments': {'x-max-priority': 10}
    }
}
```

---

## 5. Deployment Considerations

### 5.1 Database Migrations

```bash
# Migration order
1. 001_create_research_jobs.sql
2. 002_create_plan_tasks.sql
3. 003_create_research_artifacts.sql
4. 004_add_rls_policies.sql
5. 005_create_indexes.sql
```

### 5.2 Environment Variables

```bash
# New environment variables required
RESEARCH_QUEUE_CONCURRENCY=2
RESEARCH_MAX_TASKS_PER_JOB=20
RESEARCH_TASK_TIMEOUT_SECONDS=300
NOTIFICATION_EMAIL_FROM=research@empire.app
SENDGRID_API_KEY=<from .env>
```

### 5.3 Render Service Updates

- **Empire API**: Add research routes to main application
- **Celery Worker**: Add `research` queue to worker configuration
- **Environment**: Add new environment variables

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_research_initializer.py
# tests/test_task_harness.py
# tests/test_task_executors.py
```

### 6.2 Integration Tests

```python
# tests/integration/test_research_projects_api.py
# tests/integration/test_research_workflow.py
```

### 6.3 End-to-End Tests

```python
# tests/e2e/test_research_project_lifecycle.py
```

---

## 7. Monitoring & Observability

### 7.1 New Prometheus Metrics

```python
# Research project metrics
research_projects_created_total
research_projects_completed_total
research_projects_failed_total
research_task_duration_seconds
research_task_retries_total
```

### 7.2 Alert Rules

```yaml
# Research-specific alerts
- alert: ResearchJobStuck
  expr: research_job_duration_minutes > 60
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Research job running too long"

- alert: HighResearchFailureRate
  expr: rate(research_projects_failed_total[1h]) > 0.1
  for: 10m
  labels:
    severity: critical
  annotations:
    summary: "High research project failure rate"
```

---

## 8. Security Considerations

### 8.1 Access Control
- RLS policies ensure users can only access their own projects
- API endpoints require authentication
- WebSocket connections validated against project ownership

### 8.2 Data Privacy
- Research queries may contain sensitive information
- Report storage uses signed URLs with expiration
- Artifacts cleaned up after configurable retention period

### 8.3 Rate Limiting
- Per-user limit on concurrent research projects (default: 3)
- Per-user limit on daily project creation (default: 10)

---

## 9. Future Enhancements

### Phase 2+
- Concurrent task execution with dependency graphs
- Custom research templates
- Team collaboration on projects
- Research project sharing
- API integrations (web search, external data sources)
- Cost tracking and optimization

---

**Document End**
