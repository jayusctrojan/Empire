"""
Empire v7.3 - Exception Hierarchy
Task 154: Standardized Exception Handling Framework

This module provides a comprehensive exception hierarchy for the Empire application.
All exceptions inherit from BaseAppException and provide:
- Consistent error codes and HTTP status mapping
- Structured details for debugging
- Retriability hints for clients
- Severity levels for logging

Usage:
    from app.exceptions import (
        NotFoundException,
        ValidationException,
        DatabaseException,
        AgentProcessingException
    )

    # Raise a not found exception
    raise NotFoundException(
        resource_type="document",
        resource_id="doc-123"
    )

    # Raise a validation exception with field errors
    raise ValidationException(
        message="Invalid input",
        validation_errors=[
            {"field": "email", "message": "Invalid format", "type": "value_error"}
        ]
    )
"""

# Base exception
from .base import (
    BaseAppException,
    ConfigurationError,
    InitializationError,
)

# Client errors (4xx)
from .client_errors import (
    # 400 Bad Request
    BadRequestException,
    ValidationException,
    InvalidFormatException,
    MissingFieldException,
    # 401 Unauthorized
    UnauthorizedException,
    InvalidTokenException,
    TokenExpiredException,
    MissingAuthException,
    # 403 Forbidden
    ForbiddenException,
    InsufficientPermissionsException,
    AccessDeniedException,
    # 404 Not Found
    NotFoundException,
    DocumentNotFoundException,
    UserNotFoundException,
    ProjectNotFoundException,
    # 409 Conflict
    ConflictException,
    DuplicateResourceException,
    StateConflictException,
    # 422 Unprocessable Entity
    UnprocessableEntityException,
    BusinessRuleViolationException,
    # 429 Too Many Requests
    RateLimitException,
    QuotaExceededException,
)

# Server errors (5xx)
from .server_errors import (
    # 500 Internal Server Error
    InternalServerException,
    DatabaseException,
    Neo4jException,
    SupabaseException,
    RedisException,
    StorageException,
    B2StorageException,
    FileUploadException,
    FileDownloadException,
    # 502 Bad Gateway
    BadGatewayException,
    ExternalAPIException,
    AnthropicAPIException,
    LlamaParseException,
    # 503 Service Unavailable
    ServiceUnavailableException,
    MaintenanceModeException,
    CircuitBreakerOpenException,
    # 504 Gateway Timeout
    GatewayTimeoutException,
    OperationTimeoutException,
)

# Agent errors
from .agent_errors import (
    # Base agent exception
    AgentException,
    # Processing exceptions
    AgentProcessingException,
    AgentTimeoutException,
    AgentUnavailableException,
    AgentInitializationException,
    AgentCircuitOpenException,
    # LLM exceptions
    LLMException,
    LLMTimeoutException,
    LLMRateLimitException,
    LLMContextExceededException,
    LLMInvalidResponseException,
    # Workflow exceptions
    WorkflowException,
    OrchestrationException,
    WorkflowTimeoutException,
    WorkflowStepException,
    # Content processing exceptions
    ContentProcessingException,
    SummarizationException,
    ClassificationException,
    AnalysisException,
    # Graph exceptions
    GraphAgentException,
    GraphQueryException,
    GraphTraversalException,
)

# Export all exceptions
__all__ = [
    # Base
    "BaseAppException",
    "ConfigurationError",
    "InitializationError",
    # 400
    "BadRequestException",
    "ValidationException",
    "InvalidFormatException",
    "MissingFieldException",
    # 401
    "UnauthorizedException",
    "InvalidTokenException",
    "TokenExpiredException",
    "MissingAuthException",
    # 403
    "ForbiddenException",
    "InsufficientPermissionsException",
    "AccessDeniedException",
    # 404
    "NotFoundException",
    "DocumentNotFoundException",
    "UserNotFoundException",
    "ProjectNotFoundException",
    # 409
    "ConflictException",
    "DuplicateResourceException",
    "StateConflictException",
    # 422
    "UnprocessableEntityException",
    "BusinessRuleViolationException",
    # 429
    "RateLimitException",
    "QuotaExceededException",
    # 500
    "InternalServerException",
    "DatabaseException",
    "Neo4jException",
    "SupabaseException",
    "RedisException",
    "StorageException",
    "B2StorageException",
    "FileUploadException",
    "FileDownloadException",
    # 502
    "BadGatewayException",
    "ExternalAPIException",
    "AnthropicAPIException",
    "LlamaParseException",
    # 503
    "ServiceUnavailableException",
    "MaintenanceModeException",
    "CircuitBreakerOpenException",
    # 504
    "GatewayTimeoutException",
    "OperationTimeoutException",
    # Agent
    "AgentException",
    "AgentProcessingException",
    "AgentTimeoutException",
    "AgentUnavailableException",
    "AgentInitializationException",
    "AgentCircuitOpenException",
    # LLM
    "LLMException",
    "LLMTimeoutException",
    "LLMRateLimitException",
    "LLMContextExceededException",
    "LLMInvalidResponseException",
    # Workflow
    "WorkflowException",
    "OrchestrationException",
    "WorkflowTimeoutException",
    "WorkflowStepException",
    # Content
    "ContentProcessingException",
    "SummarizationException",
    "ClassificationException",
    "AnalysisException",
    # Graph
    "GraphAgentException",
    "GraphQueryException",
    "GraphTraversalException",
]
