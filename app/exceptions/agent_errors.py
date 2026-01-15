"""
Empire v7.3 - Agent-Specific Exceptions
Task 154: Standardized Exception Handling Framework

Provides exception classes for AI agent-related errors.
"""

from typing import Optional, Dict, Any, List
from .base import BaseAppException


# =============================================================================
# BASE AGENT EXCEPTION
# =============================================================================

class AgentException(BaseAppException):
    """
    Base exception for all agent-related errors.

    Provides agent_id tracking for error attribution.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AGENT_ERROR",
        agent_id: str = "unknown",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "error",
        retriable: bool = True,
        retry_after: Optional[int] = None
    ):
        details = details or {}
        details["agent_id"] = agent_id

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
            severity=severity,
            retriable=retriable,
            retry_after=retry_after
        )
        self.agent_id = agent_id


# =============================================================================
# AGENT PROCESSING EXCEPTIONS
# =============================================================================

class AgentProcessingException(AgentException):
    """
    Exception for agent processing errors.

    Raised when an agent fails to process a request.
    """

    def __init__(
        self,
        message: str = "Agent processing failed",
        agent_id: str = "unknown",
        task_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if task_type:
            details["task_type"] = task_type

        super().__init__(
            message=message,
            error_code="AGENT_PROCESSING_ERROR",
            agent_id=agent_id,
            status_code=500,
            details=details,
            retriable=True
        )


class AgentTimeoutException(AgentException):
    """
    Exception for agent timeout errors.

    Raised when an agent operation exceeds the time limit.
    """

    def __init__(
        self,
        message: str = "Agent operation timed out",
        agent_id: str = "unknown",
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            error_code="AGENT_TIMEOUT",
            agent_id=agent_id,
            status_code=504,
            details=details,
            retriable=True,
            retry_after=30
        )


class AgentUnavailableException(AgentException):
    """
    Exception for agent unavailability.

    Raised when an agent is not available to process requests.
    """

    def __init__(
        self,
        message: str = "Agent is not available",
        agent_id: str = "unknown",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if reason:
            details["unavailable_reason"] = reason

        super().__init__(
            message=message,
            error_code="AGENT_UNAVAILABLE",
            agent_id=agent_id,
            status_code=503,
            details=details,
            retriable=True,
            retry_after=60
        )


class AgentInitializationException(AgentException):
    """
    Exception for agent initialization failures.

    Raised when an agent fails to initialize properly.
    """

    def __init__(
        self,
        message: str = "Agent initialization failed",
        agent_id: str = "unknown",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="AGENT_INITIALIZATION_ERROR",
            agent_id=agent_id,
            status_code=500,
            details=details,
            retriable=False,
            severity="critical"
        )


class AgentCircuitOpenException(AgentException):
    """
    Exception for agent circuit breaker open state.

    Raised when the agent's circuit breaker is open due to failures.
    """

    def __init__(
        self,
        message: str = "Agent circuit breaker is open",
        agent_id: str = "unknown",
        reset_time: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if reset_time:
            details["reset_time_seconds"] = reset_time

        super().__init__(
            message=message,
            error_code="AGENT_CIRCUIT_OPEN",
            agent_id=agent_id,
            status_code=503,
            details=details,
            retriable=True,
            retry_after=reset_time or 30
        )


# =============================================================================
# LLM EXCEPTIONS
# =============================================================================

class LLMException(AgentException):
    """
    Base exception for LLM-related errors.

    Raised when LLM operations fail.
    """

    def __init__(
        self,
        message: str = "LLM error",
        agent_id: str = "unknown",
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "LLM_ERROR",
        status_code: int = 502
    ):
        details = details or {}
        if model:
            details["model"] = model

        super().__init__(
            message=message,
            error_code=error_code,
            agent_id=agent_id,
            status_code=status_code,
            details=details,
            retriable=True
        )


class LLMTimeoutException(LLMException):
    """Exception for LLM timeout errors."""

    def __init__(
        self,
        message: str = "LLM request timed out",
        agent_id: str = "unknown",
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            agent_id=agent_id,
            model=model,
            details=details,
            error_code="LLM_TIMEOUT",
            status_code=504
        )
        self.retry_after = 30


class LLMRateLimitException(LLMException):
    """Exception for LLM rate limit errors."""

    def __init__(
        self,
        message: str = "LLM rate limit exceeded",
        agent_id: str = "unknown",
        model: Optional[str] = None,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            agent_id=agent_id,
            model=model,
            details=details,
            error_code="LLM_RATE_LIMIT",
            status_code=429
        )
        self.retry_after = retry_after or 60


class LLMContextExceededException(LLMException):
    """Exception for LLM context limit exceeded."""

    def __init__(
        self,
        message: str = "LLM context limit exceeded",
        agent_id: str = "unknown",
        model: Optional[str] = None,
        context_size: Optional[int] = None,
        max_context: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if context_size is not None:
            details["context_size"] = context_size
        if max_context is not None:
            details["max_context"] = max_context

        super().__init__(
            message=message,
            agent_id=agent_id,
            model=model,
            details=details,
            error_code="LLM_CONTEXT_EXCEEDED",
            status_code=422
        )
        self.retriable = False


class LLMInvalidResponseException(LLMException):
    """Exception for invalid LLM responses."""

    def __init__(
        self,
        message: str = "Invalid LLM response",
        agent_id: str = "unknown",
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            agent_id=agent_id,
            model=model,
            details=details,
            error_code="LLM_INVALID_RESPONSE",
            status_code=502
        )


# =============================================================================
# WORKFLOW EXCEPTIONS
# =============================================================================

class WorkflowException(AgentException):
    """
    Base exception for workflow-related errors.

    Raised when multi-agent workflows fail.
    """

    def __init__(
        self,
        message: str = "Workflow error",
        agent_id: str = "unknown",
        workflow_id: Optional[str] = None,
        step: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "WORKFLOW_ERROR"
    ):
        details = details or {}
        if workflow_id:
            details["workflow_id"] = workflow_id
        if step:
            details["failed_step"] = step

        super().__init__(
            message=message,
            error_code=error_code,
            agent_id=agent_id,
            status_code=500,
            details=details,
            retriable=True
        )


class OrchestrationException(WorkflowException):
    """Exception for orchestration failures."""

    def __init__(
        self,
        message: str = "Orchestration failed",
        agent_id: str = "unknown",
        workflow_id: Optional[str] = None,
        failed_agents: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if failed_agents:
            details["failed_agents"] = failed_agents

        super().__init__(
            message=message,
            agent_id=agent_id,
            workflow_id=workflow_id,
            details=details,
            error_code="ORCHESTRATION_FAILED"
        )


class WorkflowTimeoutException(WorkflowException):
    """Exception for workflow timeout errors."""

    def __init__(
        self,
        message: str = "Workflow timed out",
        agent_id: str = "unknown",
        workflow_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            agent_id=agent_id,
            workflow_id=workflow_id,
            details=details,
            error_code="WORKFLOW_TIMEOUT"
        )
        self.status_code = 504
        self.retry_after = 60


class WorkflowStepException(WorkflowException):
    """Exception for workflow step failures."""

    def __init__(
        self,
        message: str = "Workflow step failed",
        agent_id: str = "unknown",
        workflow_id: Optional[str] = None,
        step: Optional[str] = None,
        step_number: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if step_number is not None:
            details["step_number"] = step_number

        super().__init__(
            message=message,
            agent_id=agent_id,
            workflow_id=workflow_id,
            step=step,
            details=details,
            error_code="WORKFLOW_STEP_FAILED"
        )


# =============================================================================
# CONTENT PROCESSING EXCEPTIONS
# =============================================================================

class ContentProcessingException(AgentException):
    """
    Base exception for content processing errors.

    Raised when agents fail to process content.
    """

    def __init__(
        self,
        message: str = "Content processing failed",
        agent_id: str = "unknown",
        content_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "CONTENT_PROCESSING_ERROR"
    ):
        details = details or {}
        if content_type:
            details["content_type"] = content_type

        super().__init__(
            message=message,
            error_code=error_code,
            agent_id=agent_id,
            status_code=500,
            details=details,
            retriable=True
        )


class SummarizationException(ContentProcessingException):
    """Exception for summarization failures."""

    def __init__(
        self,
        message: str = "Summarization failed",
        agent_id: str = "AGENT-002",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            agent_id=agent_id,
            content_type="summarization",
            details=details,
            error_code="SUMMARIZATION_FAILED"
        )


class ClassificationException(ContentProcessingException):
    """Exception for classification failures."""

    def __init__(
        self,
        message: str = "Classification failed",
        agent_id: str = "AGENT-008",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            agent_id=agent_id,
            content_type="classification",
            details=details,
            error_code="CLASSIFICATION_FAILED"
        )


class AnalysisException(ContentProcessingException):
    """Exception for analysis failures."""

    def __init__(
        self,
        message: str = "Analysis failed",
        agent_id: str = "unknown",
        analysis_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if analysis_type:
            details["analysis_type"] = analysis_type

        super().__init__(
            message=message,
            agent_id=agent_id,
            content_type="analysis",
            details=details,
            error_code="ANALYSIS_FAILED"
        )


# =============================================================================
# GRAPH AGENT EXCEPTIONS
# =============================================================================

class GraphAgentException(AgentException):
    """
    Base exception for knowledge graph agent errors.

    Raised when graph operations fail.
    """

    def __init__(
        self,
        message: str = "Graph operation failed",
        agent_id: str = "unknown",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "GRAPH_ERROR"
    ):
        details = details or {}
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code=error_code,
            agent_id=agent_id,
            status_code=500,
            details=details,
            retriable=True
        )


class GraphQueryException(GraphAgentException):
    """Exception for graph query failures."""

    def __init__(
        self,
        message: str = "Graph query failed",
        agent_id: str = "unknown",
        query: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if query:
            details["query"] = query[:200]  # Truncate long queries

        super().__init__(
            message=message,
            agent_id=agent_id,
            operation="query",
            details=details,
            error_code="GRAPH_QUERY_FAILED"
        )


class GraphTraversalException(GraphAgentException):
    """Exception for graph traversal failures."""

    def __init__(
        self,
        message: str = "Graph traversal failed",
        agent_id: str = "unknown",
        start_node: Optional[str] = None,
        max_depth: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if start_node:
            details["start_node"] = start_node
        if max_depth is not None:
            details["max_depth"] = max_depth

        super().__init__(
            message=message,
            agent_id=agent_id,
            operation="traversal",
            details=details,
            error_code="GRAPH_TRAVERSAL_ERROR"
        )
