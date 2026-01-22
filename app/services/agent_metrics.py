"""
Empire v7.3 - Agent Metrics Service
Task 132: Standardized Prometheus metrics for all agent services (AGENT-001 through AGENT-015)

Provides centralized Prometheus metrics for tracking:
- Request counts (success/failure)
- Request duration (histograms)
- Active executions (gauges)
- Token usage
- Error rates

Usage:
    from app.services.agent_metrics import (
        track_agent_request,
        track_agent_duration,
        track_agent_error,
        AgentMetricsContext
    )

    # Using context manager
    async with AgentMetricsContext("AGENT-002", "summarize") as ctx:
        result = await do_work()
        ctx.set_success()

    # Or manually
    with track_agent_duration("AGENT-002", "summarize"):
        result = await do_work()
    track_agent_request("AGENT-002", "summarize", "success")
"""

import time
from typing import Optional, Dict, Any
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
from prometheus_client import Counter, Histogram, Gauge, Summary

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Agent Request Metrics
# =============================================================================

AGENT_REQUESTS_TOTAL = Counter(
    'empire_agent_requests_total',
    'Total number of requests processed by agents',
    ['agent_id', 'operation', 'status']
)

AGENT_REQUEST_DURATION = Histogram(
    'empire_agent_request_duration_seconds',
    'Time spent processing agent requests',
    ['agent_id', 'operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
)

AGENT_ACTIVE_EXECUTIONS = Gauge(
    'empire_agent_active_executions',
    'Number of currently active agent executions',
    ['agent_id', 'operation']
)

AGENT_ERRORS_TOTAL = Counter(
    'empire_agent_errors_total',
    'Total number of agent errors by type',
    ['agent_id', 'operation', 'error_type']
)


# =============================================================================
# LLM/Token Metrics for Agents
# =============================================================================

AGENT_LLM_CALLS_TOTAL = Counter(
    'empire_agent_llm_calls_total',
    'Total LLM API calls made by agents',
    ['agent_id', 'model', 'status']
)

AGENT_LLM_TOKENS_TOTAL = Counter(
    'empire_agent_llm_tokens_total',
    'Total tokens used by agents',
    ['agent_id', 'model', 'token_type']  # token_type: input, output
)

AGENT_LLM_DURATION = Histogram(
    'empire_agent_llm_duration_seconds',
    'LLM call duration for agents',
    ['agent_id', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0]
)


# =============================================================================
# Workflow/Orchestration Metrics
# =============================================================================

AGENT_WORKFLOW_TOTAL = Counter(
    'empire_agent_workflow_total',
    'Total workflows executed',
    ['workflow_type', 'status']
)

AGENT_WORKFLOW_DURATION = Histogram(
    'empire_agent_workflow_duration_seconds',
    'Workflow execution duration',
    ['workflow_type'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0]
)

AGENT_REVISION_TOTAL = Counter(
    'empire_agent_revision_total',
    'Total revision loops triggered',
    ['agent_id', 'outcome']  # outcome: approved, rejected, max_revisions
)


# =============================================================================
# Quality Metrics
# =============================================================================

AGENT_QUALITY_SCORE = Summary(
    'empire_agent_quality_score',
    'Quality scores from agent outputs',
    ['agent_id', 'operation']
)

AGENT_CONFIDENCE_SCORE = Summary(
    'empire_agent_confidence_score',
    'Confidence scores from agent classifications',
    ['agent_id', 'operation']
)


# =============================================================================
# Helper Functions
# =============================================================================

def track_agent_request(
    agent_id: str,
    operation: str,
    status: str = "success"
) -> None:
    """
    Track an agent request.

    Args:
        agent_id: Agent identifier (e.g., "AGENT-002")
        operation: Operation name (e.g., "summarize", "classify")
        status: Request status ("success" or "failure")
    """
    AGENT_REQUESTS_TOTAL.labels(
        agent_id=agent_id,
        operation=operation,
        status=status
    ).inc()


def track_agent_error(
    agent_id: str,
    operation: str,
    error_type: str
) -> None:
    """
    Track an agent error.

    Args:
        agent_id: Agent identifier
        operation: Operation that failed
        error_type: Type of error (e.g., "validation", "timeout", "llm_error")
    """
    AGENT_ERRORS_TOTAL.labels(
        agent_id=agent_id,
        operation=operation,
        error_type=error_type
    ).inc()


def track_llm_call(
    agent_id: str,
    model: str,
    status: str = "success",
    input_tokens: int = 0,
    output_tokens: int = 0
) -> None:
    """
    Track an LLM API call.

    Args:
        agent_id: Agent identifier
        model: LLM model used
        status: Call status
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    """
    AGENT_LLM_CALLS_TOTAL.labels(
        agent_id=agent_id,
        model=model,
        status=status
    ).inc()

    if input_tokens > 0:
        AGENT_LLM_TOKENS_TOTAL.labels(
            agent_id=agent_id,
            model=model,
            token_type="input"
        ).inc(input_tokens)

    if output_tokens > 0:
        AGENT_LLM_TOKENS_TOTAL.labels(
            agent_id=agent_id,
            model=model,
            token_type="output"
        ).inc(output_tokens)


def track_quality_score(
    agent_id: str,
    operation: str,
    score: float
) -> None:
    """Track a quality score from an agent output."""
    AGENT_QUALITY_SCORE.labels(
        agent_id=agent_id,
        operation=operation
    ).observe(score)


def track_confidence_score(
    agent_id: str,
    operation: str,
    score: float
) -> None:
    """Track a confidence score from an agent classification."""
    AGENT_CONFIDENCE_SCORE.labels(
        agent_id=agent_id,
        operation=operation
    ).observe(score)


def track_workflow(
    workflow_type: str,
    status: str = "success",
    duration_seconds: Optional[float] = None
) -> None:
    """Track a workflow execution."""
    AGENT_WORKFLOW_TOTAL.labels(
        workflow_type=workflow_type,
        status=status
    ).inc()

    if duration_seconds is not None:
        AGENT_WORKFLOW_DURATION.labels(
            workflow_type=workflow_type
        ).observe(duration_seconds)


def track_revision(
    agent_id: str,
    outcome: str
) -> None:
    """Track a revision loop outcome."""
    AGENT_REVISION_TOTAL.labels(
        agent_id=agent_id,
        outcome=outcome
    ).inc()


# =============================================================================
# Context Managers
# =============================================================================

@contextmanager
def track_agent_duration(agent_id: str, operation: str):
    """
    Context manager to track agent operation duration.

    Usage:
        with track_agent_duration("AGENT-002", "summarize"):
            result = do_work()
    """
    start_time = time.perf_counter()
    AGENT_ACTIVE_EXECUTIONS.labels(
        agent_id=agent_id,
        operation=operation
    ).inc()

    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        AGENT_REQUEST_DURATION.labels(
            agent_id=agent_id,
            operation=operation
        ).observe(duration)
        AGENT_ACTIVE_EXECUTIONS.labels(
            agent_id=agent_id,
            operation=operation
        ).dec()


class AgentMetricsContext:
    """
    Context manager for comprehensive agent metrics tracking.

    Usage:
        async with AgentMetricsContext("AGENT-002", "summarize") as ctx:
            result = await do_work()
            ctx.set_success()
            ctx.track_tokens(input_tokens=100, output_tokens=50)
    """

    def __init__(
        self,
        agent_id: str,
        operation: str,
        model: Optional[str] = None
    ):
        self.agent_id = agent_id
        self.operation = operation
        self.model = model or "claude-sonnet-4-5"
        self.start_time: Optional[float] = None
        self.status = "failure"  # Default to failure, must explicitly set success
        self._input_tokens = 0
        self._output_tokens = 0
        self._error_type: Optional[str] = None

    async def __aenter__(self):
        self.start_time = time.perf_counter()
        AGENT_ACTIVE_EXECUTIONS.labels(
            agent_id=self.agent_id,
            operation=self.operation
        ).inc()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time

        # Record duration
        AGENT_REQUEST_DURATION.labels(
            agent_id=self.agent_id,
            operation=self.operation
        ).observe(duration)

        # Decrement active executions
        AGENT_ACTIVE_EXECUTIONS.labels(
            agent_id=self.agent_id,
            operation=self.operation
        ).dec()

        # If exception occurred, track as failure
        if exc_type is not None:
            self.status = "failure"
            error_type = self._error_type or exc_type.__name__
            track_agent_error(self.agent_id, self.operation, error_type)

        # Record request
        track_agent_request(self.agent_id, self.operation, self.status)

        # Track LLM metrics if tokens were recorded
        if self._input_tokens > 0 or self._output_tokens > 0:
            track_llm_call(
                self.agent_id,
                self.model,
                self.status,
                self._input_tokens,
                self._output_tokens
            )
            AGENT_LLM_DURATION.labels(
                agent_id=self.agent_id,
                model=self.model
            ).observe(duration)

        # Don't suppress exceptions
        return False

    def set_success(self):
        """Mark the operation as successful."""
        self.status = "success"

    def set_failure(self, error_type: Optional[str] = None):
        """Mark the operation as failed."""
        self.status = "failure"
        self._error_type = error_type

    def track_tokens(self, input_tokens: int = 0, output_tokens: int = 0):
        """Track token usage."""
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    def track_quality(self, score: float):
        """Track a quality score."""
        track_quality_score(self.agent_id, self.operation, score)

    def track_confidence(self, score: float):
        """Track a confidence score."""
        track_confidence_score(self.agent_id, self.operation, score)


# =============================================================================
# Decorators
# =============================================================================

def with_agent_metrics(agent_id: str, operation: str, model: Optional[str] = None):
    """
    Decorator to automatically track metrics for an async agent method.

    Usage:
        @with_agent_metrics("AGENT-002", "summarize")
        async def summarize(self, content: str) -> str:
            return await self._do_summarize(content)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with AgentMetricsContext(agent_id, operation, model) as ctx:
                try:
                    result = await func(*args, **kwargs)
                    ctx.set_success()
                    return result
                except Exception as e:
                    ctx.set_failure(type(e).__name__)
                    raise
        return wrapper
    return decorator


def with_sync_agent_metrics(agent_id: str, operation: str):
    """
    Decorator for sync agent methods.

    Usage:
        @with_sync_agent_metrics("AGENT-002", "parse")
        def parse_document(self, doc: str) -> dict:
            return self._do_parse(doc)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with track_agent_duration(agent_id, operation):
                try:
                    result = func(*args, **kwargs)
                    track_agent_request(agent_id, operation, "success")
                    return result
                except Exception as e:
                    track_agent_request(agent_id, operation, "failure")
                    track_agent_error(agent_id, operation, type(e).__name__)
                    raise
        return wrapper
    return decorator


# =============================================================================
# Agent ID Constants (for consistency)
# =============================================================================

class AgentID:
    """Standard agent identifiers for metrics labeling."""
    AGENT_001 = "AGENT-001"  # Reserved
    CONTENT_SUMMARIZER = "AGENT-002"
    SKILL_GENERATOR = "AGENT-003"
    COMMAND_GENERATOR = "AGENT-004"
    AGENT_GENERATOR = "AGENT-005"
    PROMPT_GENERATOR = "AGENT-006"
    WORKFLOW_GENERATOR = "AGENT-007"
    DEPARTMENT_CLASSIFIER = "AGENT-008"
    RESEARCH_ANALYST = "AGENT-009"
    CONTENT_STRATEGIST = "AGENT-010"
    FACT_CHECKER = "AGENT-011"
    RESEARCH_AGENT = "AGENT-012"
    ANALYSIS_AGENT = "AGENT-013"
    WRITING_AGENT = "AGENT-014"
    REVIEW_AGENT = "AGENT-015"
    CONTENT_PREP = "AGENT-016"
