"""
Empire v7.3 - Query Parameter Validation Tests (Task 177 - Production Readiness)

Tests for query parameter validation and sanitization models.
Ensures proper input validation across all API endpoints.

Author: Claude Code
Date: 2025-01-16
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError


# =============================================================================
# BASE QUERY MODEL TESTS
# =============================================================================


class TestBaseQueryModel:
    """Tests for BaseQueryModel sanitization methods."""

    def test_sanitize_strips_whitespace(self):
        """Test that sanitization strips whitespace."""
        from app.models.query_params import BaseQueryModel

        result = BaseQueryModel._sanitize_query_string("  test query  ")
        assert result == "test query"

    def test_sanitize_rejects_sql_comment(self):
        """Test that SQL comments are rejected."""
        from app.models.query_params import BaseQueryModel

        with pytest.raises(ValueError, match="disallowed pattern"):
            BaseQueryModel._sanitize_query_string("SELECT * FROM users -- comment")

    def test_sanitize_rejects_union_select(self):
        """Test that UNION SELECT is rejected."""
        from app.models.query_params import BaseQueryModel

        with pytest.raises(ValueError, match="disallowed pattern"):
            BaseQueryModel._sanitize_query_string("1 UNION SELECT * FROM passwords")

    def test_sanitize_rejects_drop_table(self):
        """Test that DROP TABLE is rejected."""
        from app.models.query_params import BaseQueryModel

        with pytest.raises(ValueError, match="disallowed pattern"):
            BaseQueryModel._sanitize_query_string("query; DROP TABLE users;")

    def test_sanitize_rejects_delete_from(self):
        """Test that DELETE FROM is rejected."""
        from app.models.query_params import BaseQueryModel

        with pytest.raises(ValueError, match="disallowed pattern"):
            BaseQueryModel._sanitize_query_string("DELETE FROM users WHERE 1=1")

    def test_sanitize_allows_normal_query(self):
        """Test that normal queries pass sanitization."""
        from app.models.query_params import BaseQueryModel

        result = BaseQueryModel._sanitize_query_string("California insurance policy requirements")
        assert result == "California insurance policy requirements"

    def test_sanitize_allows_special_characters_in_normal_use(self):
        """Test that normal special characters are allowed."""
        from app.models.query_params import BaseQueryModel

        # Quotes, hyphens (not SQL comments), colons are normal
        result = BaseQueryModel._sanitize_query_string('What is "policy coverage" for auto?')
        assert result == 'What is "policy coverage" for auto?'

    def test_sanitize_field_name_valid(self):
        """Test valid field name passes."""
        from app.models.query_params import BaseQueryModel

        allowed = ["created_at", "updated_at", "title"]
        result = BaseQueryModel._sanitize_field_name("created_at", allowed)
        assert result == "created_at"

    def test_sanitize_field_name_invalid(self):
        """Test invalid field name is rejected."""
        from app.models.query_params import BaseQueryModel

        allowed = ["created_at", "updated_at", "title"]
        with pytest.raises(ValueError, match="Invalid field"):
            BaseQueryModel._sanitize_field_name("hacked_field", allowed)


# =============================================================================
# PAGINATION TESTS
# =============================================================================


class TestPaginationParams:
    """Tests for pagination parameter models."""

    def test_default_values(self):
        """Test default pagination values."""
        from app.models.query_params import PaginationParams

        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20

    def test_offset_calculation(self):
        """Test offset is calculated correctly."""
        from app.models.query_params import PaginationParams

        params = PaginationParams(page=3, page_size=25)
        assert params.offset == 50  # (3-1) * 25

    def test_limit_alias(self):
        """Test limit is alias for page_size."""
        from app.models.query_params import PaginationParams

        params = PaginationParams(page_size=30)
        assert params.limit == 30

    def test_page_minimum(self):
        """Test page cannot be less than 1."""
        from app.models.query_params import PaginationParams

        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_page_size_maximum(self):
        """Test page_size cannot exceed 100."""
        from app.models.query_params import PaginationParams

        with pytest.raises(ValidationError):
            PaginationParams(page_size=101)

    def test_page_size_minimum(self):
        """Test page_size cannot be less than 1."""
        from app.models.query_params import PaginationParams

        with pytest.raises(ValidationError):
            PaginationParams(page_size=0)


class TestOffsetPaginationParams:
    """Tests for offset-based pagination."""

    def test_default_values(self):
        """Test default offset pagination values."""
        from app.models.query_params import OffsetPaginationParams

        params = OffsetPaginationParams()
        assert params.limit == 50
        assert params.offset == 0

    def test_custom_values(self):
        """Test custom offset pagination values."""
        from app.models.query_params import OffsetPaginationParams

        params = OffsetPaginationParams(limit=100, offset=50)
        assert params.limit == 100
        assert params.offset == 50

    def test_limit_maximum(self):
        """Test limit cannot exceed 500."""
        from app.models.query_params import OffsetPaginationParams

        with pytest.raises(ValidationError):
            OffsetPaginationParams(limit=501)


# =============================================================================
# SEARCH QUERY TESTS
# =============================================================================


class TestSearchQueryParams:
    """Tests for search query parameters."""

    def test_valid_query(self):
        """Test valid search query."""
        from app.models.query_params import SearchQueryParams

        params = SearchQueryParams(query="insurance policy requirements")
        assert params.query == "insurance policy requirements"
        assert params.top_k == 10
        assert params.min_score == 0.0

    def test_query_sanitization(self):
        """Test query is sanitized."""
        from app.models.query_params import SearchQueryParams

        params = SearchQueryParams(query="  trimmed query  ")
        assert params.query == "trimmed query"

    def test_query_rejects_injection(self):
        """Test query rejects SQL injection."""
        from app.models.query_params import SearchQueryParams

        with pytest.raises(ValidationError):
            SearchQueryParams(query="test; DROP TABLE users;")

    def test_query_minimum_length(self):
        """Test query minimum length."""
        from app.models.query_params import SearchQueryParams

        with pytest.raises(ValidationError):
            SearchQueryParams(query="")

    def test_top_k_range(self):
        """Test top_k is within valid range."""
        from app.models.query_params import SearchQueryParams

        # Valid
        params = SearchQueryParams(query="test", top_k=50)
        assert params.top_k == 50

        # Too high
        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", top_k=101)

        # Too low
        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", top_k=0)

    def test_min_score_range(self):
        """Test min_score is within valid range."""
        from app.models.query_params import SearchQueryParams

        params = SearchQueryParams(query="test", min_score=0.5)
        assert params.min_score == 0.5

        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", min_score=1.5)


class TestHybridSearchParams:
    """Tests for hybrid search parameters."""

    def test_weight_normalization(self):
        """Test weights are normalized to sum to 1.0."""
        from app.models.query_params import HybridSearchParams

        params = HybridSearchParams(
            query="test",
            vector_weight=0.3,
            keyword_weight=0.3
        )
        # Should be normalized
        assert abs(params.vector_weight + params.keyword_weight - 1.0) < 0.01

    def test_default_weights(self):
        """Test default weight values."""
        from app.models.query_params import HybridSearchParams

        params = HybridSearchParams(query="test")
        assert params.vector_weight == 0.5
        assert params.keyword_weight == 0.5


class TestVectorSearchParams:
    """Tests for vector search parameters."""

    def test_similarity_threshold(self):
        """Test similarity threshold validation."""
        from app.models.query_params import VectorSearchParams

        params = VectorSearchParams(query="test", similarity_threshold=0.8)
        assert params.similarity_threshold == 0.8

        with pytest.raises(ValidationError):
            VectorSearchParams(query="test", similarity_threshold=1.5)


# =============================================================================
# DOCUMENT LIST TESTS
# =============================================================================


class TestDocumentListParams:
    """Tests for document listing parameters."""

    def test_default_values(self):
        """Test default document list values."""
        from app.models.query_params import DocumentListParams

        params = DocumentListParams()
        assert params.page == 1
        assert params.page_size == 20
        assert params.sort_by == "created_at"
        assert params.sort_order.value == "desc"

    def test_valid_sort_field(self):
        """Test valid sort field is accepted."""
        from app.models.query_params import DocumentListParams

        params = DocumentListParams(sort_by="updated_at")
        assert params.sort_by == "updated_at"

    def test_invalid_sort_field(self):
        """Test invalid sort field is rejected."""
        from app.models.query_params import DocumentListParams

        with pytest.raises(ValidationError):
            DocumentListParams(sort_by="hacked_field")

    def test_search_sanitization(self):
        """Test search field is sanitized."""
        from app.models.query_params import DocumentListParams

        params = DocumentListParams(search="  test search  ")
        assert params.search == "test search"

    def test_search_injection_rejected(self):
        """Test search field rejects injection."""
        from app.models.query_params import DocumentListParams

        with pytest.raises(ValidationError):
            DocumentListParams(search="test; DROP TABLE docs;")


# =============================================================================
# GRAPH QUERY TESTS
# =============================================================================


class TestGraphQueryParams:
    """Tests for graph query parameters."""

    def test_valid_params(self):
        """Test valid graph query params."""
        from app.models.query_params import GraphQueryParams

        params = GraphQueryParams(
            entity_id="entity-123",
            traversal_depth=3,
            limit=100
        )
        assert params.entity_id == "entity-123"
        assert params.traversal_depth == 3
        assert params.limit == 100

    def test_entity_id_pattern(self):
        """Test entity_id matches required pattern."""
        from app.models.query_params import GraphQueryParams

        # Valid patterns
        params = GraphQueryParams(entity_id="abc_123-xyz")
        assert params.entity_id == "abc_123-xyz"

        # Invalid patterns (spaces, special chars)
        with pytest.raises(ValidationError):
            GraphQueryParams(entity_id="entity id with spaces")

    def test_traversal_depth_limits(self):
        """Test traversal depth is within limits."""
        from app.models.query_params import GraphQueryParams

        with pytest.raises(ValidationError):
            GraphQueryParams(entity_id="test", traversal_depth=0)

        with pytest.raises(ValidationError):
            GraphQueryParams(entity_id="test", traversal_depth=6)

    def test_relationship_types_validation(self):
        """Test relationship types validation."""
        from app.models.query_params import GraphQueryParams

        # Valid uppercase relationship types
        params = GraphQueryParams(
            entity_id="test",
            relationship_types=["RELATES_TO", "MENTIONS"]
        )
        assert params.relationship_types == ["RELATES_TO", "MENTIONS"]

        # Invalid lowercase
        with pytest.raises(ValidationError):
            GraphQueryParams(
                entity_id="test",
                relationship_types=["relates_to"]
            )


# =============================================================================
# DATE RANGE TESTS
# =============================================================================


class TestDateRangeParams:
    """Tests for date range parameters."""

    def test_valid_date_range(self):
        """Test valid date range."""
        from app.models.query_params import DateRangeParams

        now = datetime.now()
        params = DateRangeParams(
            date_from=now - timedelta(days=7),
            date_to=now
        )
        assert params.date_from < params.date_to

    def test_invalid_date_range(self):
        """Test invalid date range is rejected."""
        from app.models.query_params import DateRangeParams

        now = datetime.now()
        with pytest.raises(ValidationError, match="date_from must be before"):
            DateRangeParams(
                date_from=now,
                date_to=now - timedelta(days=7)
            )

    def test_optional_dates(self):
        """Test dates are optional."""
        from app.models.query_params import DateRangeParams

        params = DateRangeParams()
        assert params.date_from is None
        assert params.date_to is None


# =============================================================================
# AUDIT LOG TESTS
# =============================================================================


class TestAuditLogParams:
    """Tests for audit log query parameters."""

    def test_default_values(self):
        """Test default audit log params."""
        from app.models.query_params import AuditLogParams

        params = AuditLogParams()
        assert params.page == 1
        assert params.sort_by == "timestamp"

    def test_severity_pattern(self):
        """Test severity matches allowed patterns."""
        from app.models.query_params import AuditLogParams

        # Valid severities
        for severity in ["info", "warning", "error", "critical"]:
            params = AuditLogParams(severity=severity)
            assert params.severity == severity

        # Invalid severity
        with pytest.raises(ValidationError):
            AuditLogParams(severity="invalid")

    def test_valid_sort_fields(self):
        """Test valid audit sort fields."""
        from app.models.query_params import AuditLogParams

        params = AuditLogParams(sort_by="event_type")
        assert params.sort_by == "event_type"

        with pytest.raises(ValidationError):
            AuditLogParams(sort_by="invalid_field")


# =============================================================================
# FILTER TESTS
# =============================================================================


class TestFilterCondition:
    """Tests for filter condition model."""

    def test_valid_filter(self):
        """Test valid filter condition."""
        from app.models.query_params import FilterCondition, FilterOperator

        filter_cond = FilterCondition(
            field="status",
            operator=FilterOperator.EQ,
            value="active"
        )
        assert filter_cond.field == "status"
        assert filter_cond.operator == FilterOperator.EQ
        assert filter_cond.value == "active"

    def test_field_name_validation(self):
        """Test field name is validated."""
        from app.models.query_params import FilterCondition

        # Valid field names
        FilterCondition(field="user_name", value="test")
        FilterCondition(field="user.profile.name", value="test")  # Nested

        # Invalid field names
        with pytest.raises(ValidationError):
            FilterCondition(field="123invalid", value="test")

        with pytest.raises(ValidationError):
            FilterCondition(field="field with spaces", value="test")


class TestAdvancedFilterParams:
    """Tests for advanced filter parameters."""

    def test_valid_filters(self):
        """Test valid filter list."""
        from app.models.query_params import AdvancedFilterParams, FilterCondition

        params = AdvancedFilterParams(
            filters=[
                FilterCondition(field="status", value="active"),
                FilterCondition(field="type", value="document")
            ],
            filter_logic="AND"
        )
        assert len(params.filters) == 2
        assert params.filter_logic == "AND"

    def test_filter_logic_validation(self):
        """Test filter logic is validated."""
        from app.models.query_params import AdvancedFilterParams

        # Valid
        AdvancedFilterParams(filter_logic="AND")
        AdvancedFilterParams(filter_logic="OR")

        # Invalid
        with pytest.raises(ValidationError):
            AdvancedFilterParams(filter_logic="INVALID")


# =============================================================================
# BATCH QUERY TESTS
# =============================================================================


class TestBatchQueryParams:
    """Tests for batch query parameters."""

    def test_valid_batch(self):
        """Test valid batch queries."""
        from app.models.query_params import BatchQueryParams

        params = BatchQueryParams(
            queries=["query 1", "query 2", "query 3"]
        )
        assert len(params.queries) == 3

    def test_queries_sanitized(self):
        """Test all queries are sanitized."""
        from app.models.query_params import BatchQueryParams

        params = BatchQueryParams(
            queries=["  trimmed  ", "another query"]
        )
        assert params.queries[0] == "trimmed"

    def test_empty_query_rejected(self):
        """Test empty queries are rejected."""
        from app.models.query_params import BatchQueryParams

        with pytest.raises(ValidationError):
            BatchQueryParams(queries=["valid", "", "another"])

    def test_injection_rejected_in_batch(self):
        """Test injection is rejected in batch."""
        from app.models.query_params import BatchQueryParams

        with pytest.raises(ValidationError):
            BatchQueryParams(queries=["valid", "test; DROP TABLE x;"])

    def test_max_queries(self):
        """Test maximum queries limit."""
        from app.models.query_params import BatchQueryParams

        with pytest.raises(ValidationError):
            BatchQueryParams(queries=["q"] * 51)


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestValidateQueryString:
    """Tests for validate_query_string helper."""

    def test_validates_and_returns(self):
        """Test function validates and returns sanitized string."""
        from app.models.query_params import validate_query_string

        result = validate_query_string("  test query  ")
        assert result == "test query"

    def test_raises_on_injection(self):
        """Test function raises on injection attempt."""
        from app.models.query_params import validate_query_string

        with pytest.raises(ValueError):
            validate_query_string("SELECT * FROM users; DROP TABLE users;")


class TestCreatePaginationResponse:
    """Tests for pagination response helper."""

    def test_creates_response(self):
        """Test pagination response creation."""
        from app.models.query_params import create_pagination_response

        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        response = create_pagination_response(
            items=items,
            total=100,
            page=2,
            page_size=20
        )

        assert response["items"] == items
        assert response["pagination"]["page"] == 2
        assert response["pagination"]["page_size"] == 20
        assert response["pagination"]["total_items"] == 100
        assert response["pagination"]["total_pages"] == 5
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_previous"] is True

    def test_first_page(self):
        """Test first page has no previous."""
        from app.models.query_params import create_pagination_response

        response = create_pagination_response(
            items=[],
            total=100,
            page=1,
            page_size=20
        )

        assert response["pagination"]["has_previous"] is False
        assert response["pagination"]["has_next"] is True

    def test_last_page(self):
        """Test last page has no next."""
        from app.models.query_params import create_pagination_response

        response = create_pagination_response(
            items=[],
            total=100,
            page=5,
            page_size=20
        )

        assert response["pagination"]["has_previous"] is True
        assert response["pagination"]["has_next"] is False


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Tests for enum types."""

    def test_sort_order_values(self):
        """Test SortOrder enum values."""
        from app.models.query_params import SortOrder

        assert SortOrder.ASC.value == "asc"
        assert SortOrder.DESC.value == "desc"

    def test_content_type_values(self):
        """Test ContentType enum values."""
        from app.models.query_params import ContentType

        assert ContentType.DOCUMENT.value == "document"
        assert ContentType.PDF.value == "pdf"

    def test_filter_operator_values(self):
        """Test FilterOperator enum values."""
        from app.models.query_params import FilterOperator

        assert FilterOperator.EQ.value == "eq"
        assert FilterOperator.CONTAINS.value == "contains"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
