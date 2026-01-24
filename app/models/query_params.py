"""
Empire v7.3 - Query Parameter Validation Models (Task 177 - Production Readiness)

Centralized Pydantic models for query parameter validation and sanitization.
These models ensure proper validation of user input across all API endpoints.

Features:
- Input sanitization against injection patterns
- Field constraints (min/max lengths, ranges)
- Reusable pagination and filter models
- Custom validators for common patterns

Author: Claude Code
Date: 2025-01-16
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Patterns that should be rejected in query strings to prevent injection
DANGEROUS_SQL_PATTERNS = [
    r"--",           # SQL comment
    r";(?!\s*$)",    # SQL statement terminator (except at end)
    r"'(?:\s*OR\s+|\s*AND\s+)",  # SQL injection patterns
    r"UNION\s+SELECT",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"INSERT\s+INTO",
    r"UPDATE\s+.*\s+SET",
    r"EXEC\s*\(",
    r"EXECUTE\s*\(",
    r"xp_",          # SQL Server extended stored procedures
]

# Allowed sort fields across different resources
ALLOWED_DOCUMENT_SORT_FIELDS = ["created_at", "updated_at", "title", "size", "relevance"]
ALLOWED_SEARCH_SORT_FIELDS = ["relevance", "date", "title"]
ALLOWED_AUDIT_SORT_FIELDS = ["timestamp", "event_type", "severity", "user_id"]


# =============================================================================
# ENUMS
# =============================================================================

class SortOrder(str, Enum):
    """Sort order enum."""
    ASC = "asc"
    DESC = "desc"


class ContentType(str, Enum):
    """Content type enum for filtering."""
    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"
    PDF = "pdf"
    SPREADSHEET = "spreadsheet"


# =============================================================================
# BASE QUERY MODELS
# =============================================================================

class BaseQueryModel(BaseModel):
    """Base model with common query sanitization methods."""

    @staticmethod
    def _sanitize_query_string(value: str) -> str:
        """
        Sanitize a query string to prevent SQL injection.

        Args:
            value: The raw query string

        Returns:
            Sanitized query string

        Raises:
            ValueError: If dangerous patterns are detected
        """
        if not value:
            return value

        # Strip whitespace
        value = value.strip()

        # Check for dangerous patterns
        for pattern in DANGEROUS_SQL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(
                    "Dangerous pattern detected in query",
                    pattern=pattern,
                    query_preview=value[:50]
                )
                raise ValueError("Query contains disallowed pattern")

        return value

    @staticmethod
    def _sanitize_field_name(value: str, allowed_fields: List[str]) -> str:
        """
        Validate and sanitize a field name.

        Args:
            value: The field name
            allowed_fields: List of allowed field names

        Returns:
            Validated field name

        Raises:
            ValueError: If field is not allowed
        """
        if value not in allowed_fields:
            raise ValueError(f"Invalid field. Must be one of: {', '.join(allowed_fields)}")
        return value


# =============================================================================
# PAGINATION MODELS
# =============================================================================

class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    page: int = Field(default=1, ge=1, le=10000, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Alias for page_size for database queries."""
        return self.page_size


class OffsetPaginationParams(BaseModel):
    """Offset-based pagination parameters."""
    limit: int = Field(default=50, ge=1, le=500, description="Maximum items to return")
    offset: int = Field(default=0, ge=0, le=100000, description="Number of items to skip")


# =============================================================================
# SEARCH QUERY MODELS
# =============================================================================

class SearchQueryParams(BaseQueryModel):
    """Parameters for general search queries."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Search query string"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum relevance score")
    namespace: Optional[str] = Field(default=None, max_length=100, description="Search namespace")

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize the search query."""
        return cls._sanitize_query_string(v)


class VectorSearchParams(SearchQueryParams):
    """Parameters for vector similarity search."""
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold"
    )
    include_metadata: bool = Field(default=True, description="Include document metadata")
    include_embeddings: bool = Field(default=False, description="Include embedding vectors")


class HybridSearchParams(SearchQueryParams):
    """Parameters for hybrid (vector + keyword) search."""
    vector_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for vector search (0-1)"
    )
    keyword_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for keyword search (0-1)"
    )
    use_reranking: bool = Field(default=True, description="Apply reranking to results")

    @model_validator(mode="after")
    def validate_weights(self) -> "HybridSearchParams":
        """Ensure weights sum to approximately 1.0."""
        total = self.vector_weight + self.keyword_weight
        if abs(total - 1.0) > 0.01:
            # Normalize weights
            self.vector_weight = self.vector_weight / total
            self.keyword_weight = self.keyword_weight / total
        return self


# =============================================================================
# DOCUMENT LIST MODELS
# =============================================================================

class DocumentListParams(BaseQueryModel):
    """Parameters for listing documents."""
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at")
    sort_order: SortOrder = Field(default=SortOrder.DESC)
    filter_tag: Optional[str] = Field(default=None, max_length=100)
    filter_status: Optional[str] = Field(default=None, max_length=50)
    filter_content_type: Optional[ContentType] = None
    search: Optional[str] = Field(default=None, max_length=500)

    @field_validator("sort_by")
    @classmethod
    def validate_sort_field(cls, v: str) -> str:
        """Validate sort field is allowed."""
        return cls._sanitize_field_name(v, ALLOWED_DOCUMENT_SORT_FIELDS)

    @field_validator("search")
    @classmethod
    def sanitize_search(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize optional search field."""
        if v is None:
            return v
        return cls._sanitize_query_string(v)


# =============================================================================
# GRAPH QUERY MODELS
# =============================================================================

class GraphQueryParams(BaseQueryModel):
    """Parameters for graph traversal queries."""
    entity_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Starting entity ID",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    traversal_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum traversal depth"
    )
    relationship_types: Optional[List[str]] = Field(
        default=None,
        max_length=10,
        description="Filter by relationship types"
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum nodes to return")
    include_properties: bool = Field(default=True, description="Include node properties")

    @field_validator("relationship_types")
    @classmethod
    def validate_relationship_types(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate relationship type names."""
        if v is None:
            return v

        # Only allow alphanumeric and underscores
        pattern = re.compile(r"^[A-Z_]+$")
        for rel_type in v:
            if not pattern.match(rel_type):
                raise ValueError(
                    f"Invalid relationship type: {rel_type}. "
                    "Must be uppercase letters and underscores only."
                )
        return v


# =============================================================================
# DATE RANGE FILTER MODELS
# =============================================================================

class DateRangeParams(BaseModel):
    """Parameters for date range filtering."""
    date_from: Optional[datetime] = Field(default=None, description="Start date (inclusive)")
    date_to: Optional[datetime] = Field(default=None, description="End date (inclusive)")

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeParams":
        """Ensure date_from is before date_to."""
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValueError("date_from must be before or equal to date_to")
        return self


# =============================================================================
# AUDIT LOG QUERY MODELS
# =============================================================================

class AuditLogParams(DateRangeParams, PaginationParams):
    """Parameters for querying audit logs."""
    user_id: Optional[str] = Field(default=None, max_length=100)
    event_type: Optional[str] = Field(default=None, max_length=50)
    severity: Optional[str] = Field(default=None, pattern=r"^(info|warning|error|critical)$")
    resource_type: Optional[str] = Field(default=None, max_length=50)
    resource_id: Optional[str] = Field(default=None, max_length=100)
    sort_by: str = Field(default="timestamp")
    sort_order: SortOrder = Field(default=SortOrder.DESC)

    @field_validator("sort_by")
    @classmethod
    def validate_sort_field(cls, v: str) -> str:
        """Validate sort field is allowed."""
        if v not in ALLOWED_AUDIT_SORT_FIELDS:
            raise ValueError(f"Invalid sort field. Must be one of: {', '.join(ALLOWED_AUDIT_SORT_FIELDS)}")
        return v


# =============================================================================
# FILTER MODELS
# =============================================================================

class FilterOperator(str, Enum):
    """Filter operators for advanced filtering."""
    EQ = "eq"       # Equal
    NE = "ne"       # Not equal
    GT = "gt"       # Greater than
    GTE = "gte"     # Greater than or equal
    LT = "lt"       # Less than
    LTE = "lte"     # Less than or equal
    IN = "in"       # In list
    CONTAINS = "contains"  # Contains substring
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class FilterCondition(BaseModel):
    """A single filter condition."""
    field: str = Field(..., min_length=1, max_length=100)
    operator: FilterOperator = Field(default=FilterOperator.EQ)
    value: Union[str, int, float, bool, List[Any]] = Field(...)

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Ensure field name is safe."""
        # Only allow alphanumeric, underscores, and dots (for nested fields)
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", v):
            raise ValueError("Invalid field name format")
        return v


class AdvancedFilterParams(BaseModel):
    """Advanced filtering with multiple conditions."""
    filters: Optional[List[FilterCondition]] = Field(
        default=None,
        max_length=20,
        description="List of filter conditions"
    )
    filter_logic: str = Field(
        default="AND",
        pattern=r"^(AND|OR)$",
        description="Logic to combine filters (AND/OR)"
    )


# =============================================================================
# ADAPTIVE QUERY MODELS (Enhanced from existing)
# =============================================================================

class AdaptiveQueryParams(SearchQueryParams):
    """
    Parameters for adaptive query processing.

    Extended from SearchQueryParams with additional LangGraph options.
    """
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum refinement iterations"
    )
    use_external_tools: bool = Field(
        default=True,
        description="Allow external API calls via Arcade"
    )
    use_graph_context: bool = Field(
        default=True,
        description="Include Neo4j graph context"
    )
    enable_query_expansion: bool = Field(
        default=True,
        description="Use Claude Haiku for query expansion"
    )
    num_query_variations: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of query variations"
    )
    expansion_strategy: str = Field(
        default="balanced",
        pattern=r"^(synonyms|reformulate|specific|broad|balanced|question)$",
        description="Query expansion strategy"
    )


# =============================================================================
# BATCH QUERY MODELS
# =============================================================================

class BatchQueryParams(BaseModel):
    """Parameters for batch query processing."""
    queries: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of queries to process"
    )
    max_iterations: int = Field(default=2, ge=1, le=3)
    use_auto_routing: bool = Field(default=True)

    @field_validator("queries")
    @classmethod
    def validate_queries(cls, v: List[str]) -> List[str]:
        """Validate and sanitize all queries."""
        sanitized = []
        for query in v:
            if not query or not query.strip():
                raise ValueError("Empty queries are not allowed")
            sanitized_query = BaseQueryModel._sanitize_query_string(query.strip())
            sanitized.append(sanitized_query)
        return sanitized


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def validate_query_string(query: str) -> str:
    """
    Standalone function to validate and sanitize a query string.

    Args:
        query: The query string to validate

    Returns:
        Sanitized query string

    Raises:
        ValueError: If query contains dangerous patterns
    """
    return BaseQueryModel._sanitize_query_string(query)


def create_pagination_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int
) -> Dict[str, Any]:
    """
    Create a standardized pagination response.

    Args:
        items: List of items for current page
        total: Total number of items
        page: Current page number
        page_size: Items per page

    Returns:
        Dictionary with pagination metadata
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        }
    }


__all__ = [
    # Enums
    "SortOrder",
    "ContentType",
    "FilterOperator",
    # Base models
    "BaseQueryModel",
    "PaginationParams",
    "OffsetPaginationParams",
    # Search models
    "SearchQueryParams",
    "VectorSearchParams",
    "HybridSearchParams",
    # Document models
    "DocumentListParams",
    # Graph models
    "GraphQueryParams",
    # Date/filter models
    "DateRangeParams",
    "AuditLogParams",
    "FilterCondition",
    "AdvancedFilterParams",
    # Query processing models
    "AdaptiveQueryParams",
    "BatchQueryParams",
    # Helper functions
    "validate_query_string",
    "create_pagination_response",
    # Constants
    "ALLOWED_DOCUMENT_SORT_FIELDS",
    "ALLOWED_SEARCH_SORT_FIELDS",
    "ALLOWED_AUDIT_SORT_FIELDS",
]
