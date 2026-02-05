"""
Empire v7.3 - Research Initializer Service (Task 93)

AI-powered task planning service that analyzes research queries
and creates structured task plans for the Agent Harness.

Uses Claude Sonnet to:
1. Analyze research queries
2. Determine required task types
3. Create dependency-aware task plans
4. Estimate execution complexity

Author: Claude Code
Date: 2025-01-10
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from collections import deque

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field
from supabase import Client

from app.core.supabase_client import get_supabase_client
from app.models.research_project import (
    JobStatus,
    TaskType,
    TaskStatus,
    ResearchType,
)

logger = structlog.get_logger(__name__)


# ==============================================================================
# Pydantic Models for Claude Response
# ==============================================================================

class PlannedTask(BaseModel):
    """A single planned task from Claude's analysis"""
    task_key: str = Field(..., description="Unique identifier for this task")
    task_type: str = Field(..., description="Type of task: retrieval_rag, retrieval_nlq, etc.")
    task_title: str = Field(..., description="Human-readable title")
    task_description: str = Field(..., description="What this task will do")
    query: str = Field(..., description="The specific query or action for this task")
    depends_on: List[str] = Field(default_factory=list, description="Task keys this depends on")
    config: Dict[str, Any] = Field(default_factory=dict, description="Task-specific configuration")


class TaskPlanResponse(BaseModel):
    """Claude's complete task plan response"""
    summary: str = Field(..., description="Brief summary of the research approach")
    estimated_complexity: str = Field(..., description="simple, medium, or complex")
    tasks: List[PlannedTask] = Field(..., description="Ordered list of tasks")
    rationale: str = Field(..., description="Why this approach was chosen")


# ==============================================================================
# Prompts
# ==============================================================================

TASK_PLANNING_SYSTEM_PROMPT = """You are a research planning expert. Your job is to analyze research queries and break them down into discrete, executable tasks.

Available task types:
- retrieval_rag: Vector similarity search in the document knowledge base
- retrieval_nlq: Natural language query to structured database
- retrieval_graph: Knowledge graph traversal for entity relationships
- retrieval_api: External API call for supplementary data
- synthesis: Combine and analyze findings from retrieval tasks
- fact_check: Verify claims and assess confidence
- write_section: Write a specific section of the report
- write_report: Generate the final comprehensive report
- review: Quality assurance and revision

Guidelines:
1. Start with retrieval tasks (they have no dependencies)
2. Synthesis tasks depend on retrieval tasks
3. Write tasks depend on synthesis
4. Review depends on write tasks
5. Keep task count reasonable: 3-5 for simple, 6-10 for medium, 11-20 for complex
6. Each task should be atomic and well-defined
7. Use meaningful task_key values (e.g., "retrieve_contracts", "synthesize_findings")

Respond with valid JSON matching this schema:
{
  "summary": "Brief summary of research approach",
  "estimated_complexity": "simple|medium|complex",
  "tasks": [
    {
      "task_key": "unique_key",
      "task_type": "retrieval_rag|retrieval_nlq|...",
      "task_title": "Human-readable title",
      "task_description": "What this task does",
      "query": "Specific query or action",
      "depends_on": ["dependent_task_keys"],
      "config": {}
    }
  ],
  "rationale": "Why this approach was chosen"
}"""


def get_task_planning_prompt(query: str, context: Optional[str], research_type: str) -> str:
    """Generate the user prompt for task planning"""
    context_section = f"\nAdditional Context: {context}" if context else ""

    return f"""Analyze this research query and create a task plan.

Research Query: {query}
Research Type: {research_type}{context_section}

Create a comprehensive task plan that will:
1. Retrieve all relevant information from available sources
2. Synthesize findings into actionable insights
3. Generate a well-structured research report

Respond with the JSON task plan."""


# ==============================================================================
# Research Initializer Service
# ==============================================================================

class ResearchInitializerService:
    """Service for analyzing queries and creating task plans"""

    def __init__(self, supabase: Client, anthropic: AsyncAnthropic):
        self.supabase = supabase
        self.anthropic = anthropic
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    async def initialize_job(self, job_id: int) -> bool:
        """
        Main entry point: Initialize a research job by creating its task plan.

        Args:
            job_id: The research job ID to initialize

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            logger.info("Initializing research job", job_id=job_id)

            # Update status to planning
            await self._update_job_status(job_id, JobStatus.PLANNING)

            # Get job details
            job = await self._get_job(job_id)
            if not job:
                logger.error("Job not found", job_id=job_id)
                await self._fail_job(job_id, "Job not found")
                return False

            # Analyze query and create task plan
            task_plan = await self.analyze_query(
                query=job["query"],
                context=job.get("context"),
                research_type=job.get("research_type", "general")
            )

            if not task_plan:
                logger.error("Failed to create task plan", job_id=job_id)
                await self._fail_job(job_id, "Failed to analyze query and create task plan")
                return False

            # Validate dependencies
            if not self._validate_dependencies(task_plan.tasks):
                logger.error("Invalid task dependencies", job_id=job_id)
                await self._fail_job(job_id, "Task plan has invalid dependencies")
                return False

            # Create task records in database
            await self._create_tasks(job_id, task_plan)

            # Update job status to planned
            await self._update_job_status(
                job_id,
                JobStatus.PLANNED,
                total_tasks=len(task_plan.tasks),
                summary=task_plan.summary
            )

            logger.info(
                "Job initialized successfully",
                job_id=job_id,
                task_count=len(task_plan.tasks),
                complexity=task_plan.estimated_complexity
            )

            return True

        except Exception as e:
            logger.error("Error initializing job", job_id=job_id, error=str(e))
            await self._fail_job(job_id, f"Initialization error: {str(e)}")
            return False

    async def analyze_query(
        self,
        query: str,
        context: Optional[str],
        research_type: str
    ) -> Optional[TaskPlanResponse]:
        """
        Use Claude to analyze a research query and generate a task plan.

        Args:
            query: The research query
            context: Optional additional context
            research_type: Type of research (general, compliance, etc.)

        Returns:
            TaskPlanResponse with the task plan, or None on failure
        """
        try:
            user_prompt = get_task_planning_prompt(query, context, research_type)

            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=4096,
                system=TASK_PLANNING_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Extract text response
            response_text = response.content[0].text

            # Parse JSON from response (handle potential markdown code blocks)
            json_text = self._extract_json(response_text)
            plan_data = json.loads(json_text)

            # Validate and create TaskPlanResponse
            task_plan = TaskPlanResponse(**plan_data)

            # Validate task types
            valid_types = {t.value for t in TaskType}
            for task in task_plan.tasks:
                if task.task_type not in valid_types:
                    logger.warning(
                        "Invalid task type, defaulting to retrieval_rag",
                        task_key=task.task_key,
                        invalid_type=task.task_type
                    )
                    task.task_type = TaskType.RETRIEVAL_RAG.value

            logger.info(
                "Query analyzed successfully",
                task_count=len(task_plan.tasks),
                complexity=task_plan.estimated_complexity
            )

            return task_plan

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON", error=str(e))
            return None
        except Exception as e:
            logger.error("Error analyzing query", error=str(e))
            return None

    def _extract_json(self, text: str) -> str:
        """Extract JSON from Claude response (handles markdown code blocks)"""
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        # Assume the whole response is JSON
        return text.strip()

    def _validate_dependencies(self, tasks: List[PlannedTask]) -> bool:
        """
        Validate that task dependencies form a valid DAG (no cycles).

        Args:
            tasks: List of planned tasks

        Returns:
            True if dependencies are valid, False if cycles detected
        """
        # Build adjacency list
        task_keys = {t.task_key for t in tasks}
        graph: Dict[str, List[str]] = {t.task_key: [] for t in tasks}
        in_degree: Dict[str, int] = {t.task_key: 0 for t in tasks}

        for task in tasks:
            for dep in task.depends_on:
                if dep not in task_keys:
                    logger.warning(
                        "Dependency references unknown task",
                        task_key=task.task_key,
                        unknown_dep=dep
                    )
                    continue
                graph[dep].append(task.task_key)
                in_degree[task.task_key] += 1

        # Kahn's algorithm for cycle detection
        queue = deque([k for k, v in in_degree.items() if v == 0])
        visited = 0

        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited == len(tasks)

    def build_execution_waves(self, tasks: List[PlannedTask]) -> List[List[str]]:
        """
        Organize tasks into waves for parallel execution.

        Tasks in the same wave have no dependencies on each other
        and can be executed concurrently.

        Args:
            tasks: List of planned tasks

        Returns:
            List of waves, each wave is a list of task_keys
        """
        task_map = {t.task_key: t for t in tasks}
        completed: set = set()
        waves: List[List[str]] = []

        remaining = set(task_map.keys())

        while remaining:
            # Find tasks whose dependencies are all completed
            wave = []
            for task_key in remaining:
                task = task_map[task_key]
                deps = set(task.depends_on) & set(task_map.keys())  # Only valid deps
                if deps.issubset(completed):
                    wave.append(task_key)

            if not wave:
                # No progress possible - circular dependency
                logger.error("Cannot make progress - possible circular dependency")
                break

            waves.append(wave)
            completed.update(wave)
            remaining -= set(wave)

        return waves

    async def _get_job(self, job_id: int) -> Optional[Dict]:
        """Get job details from database"""
        result = self.supabase.table("research_jobs").select(
            "id, query, context, research_type, user_id"
        ).eq("id", job_id).single().execute()
        return result.data if result.data else None

    async def _update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        total_tasks: Optional[int] = None,
        summary: Optional[str] = None
    ):
        """Update job status in database"""
        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }

        if status == JobStatus.PLANNING:
            update_data["started_at"] = datetime.utcnow().isoformat()

        if total_tasks is not None:
            update_data["total_tasks"] = total_tasks

        if summary is not None:
            update_data["summary"] = summary

        self.supabase.table("research_jobs").update(update_data).eq("id", job_id).execute()

    async def _fail_job(self, job_id: int, error_message: str):
        """Mark job as failed"""
        self.supabase.table("research_jobs").update({
            "status": JobStatus.FAILED.value,
            "error_message": error_message,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", job_id).execute()

    async def _create_tasks(self, job_id: int, task_plan: TaskPlanResponse):
        """Create task records in database"""
        for i, task in enumerate(task_plan.tasks):
            self.supabase.table("plan_tasks").insert({
                "job_id": job_id,
                "task_key": task.task_key,
                "sequence_order": i + 1,
                "task_type": task.task_type,
                "task_title": task.task_title,
                "task_description": task.task_description,
                "query": task.query,
                "depends_on": task.depends_on,
                "config": task.config,
                "status": TaskStatus.PENDING.value,
            }).execute()

        logger.info("Tasks created", job_id=job_id, count=len(task_plan.tasks))


# ==============================================================================
# Service Factory
# ==============================================================================

_service_instance: Optional[ResearchInitializerService] = None


def get_research_initializer_service() -> ResearchInitializerService:
    """Get or create research initializer service singleton"""
    global _service_instance
    if _service_instance is None:
        supabase = get_supabase_client()
        anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        _service_instance = ResearchInitializerService(supabase, anthropic)
    return _service_instance
