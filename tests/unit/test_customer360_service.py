# tests/unit/test_customer360_service.py
"""
Unit tests for Customer 360 Service.

Task 104: Graph Agent - Customer 360 Service
Feature: 005-graph-agent

Tests:
- Customer retrieval by ID
- Natural language query extraction
- Customer 360 aggregation
- Similar customer detection
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.customer360_service import (
    Customer360Service,
    CustomerNotFoundError,
    CustomerQueryError,
    get_customer360_service,
    close_customer360_service,
)
from app.models.graph_agent import (
    Customer360Request,
    Customer360Response,
    CustomerNode,
    CustomerType,
    SimilarCustomer,
    TraversalDepth,
)
from app.services.neo4j_http_client import Neo4jQueryError, Neo4jConnectionError


class TestCustomer360ServiceInit:
    """Test service initialization."""

    def test_default_initialization(self):
        """Test service initializes with defaults."""
        with patch("app.services.customer360_service.get_neo4j_http_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client

            service = Customer360Service()

            assert service.neo4j == mock_client
            assert service.cache is None

    def test_custom_client_initialization(self):
        """Test service with custom client."""
        mock_client = MagicMock()
        mock_cache = MagicMock()

        service = Customer360Service(
            neo4j_client=mock_client, cache_service=mock_cache
        )

        assert service.neo4j == mock_client
        assert service.cache == mock_cache


class TestGetCustomerById:
    """Test get_customer_by_id method."""

    @pytest.fixture
    def service(self):
        """Create service with mock client."""
        mock_client = AsyncMock()
        return Customer360Service(neo4j_client=mock_client)

    @pytest.mark.asyncio
    async def test_get_customer_success(self, service):
        """Test successful customer retrieval."""
        service.neo4j.execute_query.return_value = [
            {
                "id": "cust_001",
                "name": "Acme Corp",
                "type": "enterprise",
                "industry": "Technology",
                "created_at": None,
                "metadata": {"source": "CRM"},
            }
        ]

        customer = await service.get_customer_by_id("cust_001")

        assert customer.id == "cust_001"
        assert customer.name == "Acme Corp"
        assert customer.type == CustomerType.ENTERPRISE
        assert customer.industry == "Technology"
        assert customer.metadata == {"source": "CRM"}

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, service):
        """Test customer not found error."""
        service.neo4j.execute_query.return_value = []

        with pytest.raises(CustomerNotFoundError) as exc_info:
            await service.get_customer_by_id("nonexistent")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_customer_query_error(self, service):
        """Test query error handling."""
        service.neo4j.execute_query.side_effect = Neo4jQueryError("Query failed")

        with pytest.raises(CustomerNotFoundError):
            await service.get_customer_by_id("cust_001")


class TestGetCustomer360:
    """Test get_customer_360 method."""

    @pytest.fixture
    def service(self):
        """Create service with mock client."""
        mock_client = AsyncMock()
        return Customer360Service(neo4j_client=mock_client)

    @pytest.fixture
    def mock_customer_360_response(self):
        """Mock response for Customer 360 query."""
        return [
            {
                "customer": {
                    "id": "cust_001",
                    "name": "Acme Corp",
                    "type": "enterprise",
                    "industry": "Technology",
                },
                "documents": [
                    {"id": "doc_001", "title": "Contract", "type": "contract"},
                    {"id": "doc_002", "title": "Agreement", "type": "agreement"},
                ],
                "tickets": [
                    {
                        "id": "ticket_001",
                        "subject": "Login Issue",
                        "status": "open",
                        "priority": "high",
                    }
                ],
                "orders": [
                    {
                        "id": "order_001",
                        "status": "completed",
                        "total_amount": 1000.00,
                    }
                ],
                "interactions": [
                    {"id": "int_001", "type": "call", "subject": "Support call"}
                ],
                "products": [{"id": "prod_001", "name": "Enterprise Plan"}],
                "relationship_count": 10,
            }
        ]

    @pytest.mark.asyncio
    async def test_get_customer_360_with_id(self, service, mock_customer_360_response):
        """Test Customer 360 with direct customer ID."""
        service.neo4j.execute_query.return_value = mock_customer_360_response

        request = Customer360Request(customer_id="cust_001")
        response = await service.get_customer_360(request)

        assert response.customer.id == "cust_001"
        assert response.customer.name == "Acme Corp"
        assert len(response.documents) == 2
        assert len(response.tickets) == 1
        assert len(response.orders) == 1
        assert len(response.interactions) == 1
        assert len(response.products) == 1
        assert response.relationship_count == 10
        assert "Acme Corp" in response.summary

    @pytest.mark.asyncio
    async def test_get_customer_360_with_query(self, service, mock_customer_360_response):
        """Test Customer 360 with natural language query."""
        # First call extracts customer from query
        service.neo4j.execute_query.side_effect = [
            [{"id": "cust_001", "name": "Acme Corp"}],  # Customer search
            mock_customer_360_response,  # Customer 360 query
        ]

        request = Customer360Request(query="Show me Acme Corp")
        response = await service.get_customer_360(request)

        assert response.customer.id == "cust_001"
        assert response.customer.name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_get_customer_360_exclude_categories(self, service):
        """Test excluding certain categories."""
        service.neo4j.execute_query.return_value = [
            {
                "customer": {"id": "cust_001", "name": "Test Corp", "type": "smb"},
                "documents": [{"id": "doc_001", "title": "Doc"}],
                "tickets": [{"id": "t_001", "subject": "Issue", "status": "open", "priority": "low"}],
                "orders": [],
                "interactions": [],
                "products": [],
                "relationship_count": 2,
            }
        ]

        request = Customer360Request(
            customer_id="cust_001",
            include_documents=False,
            include_tickets=True,
            include_orders=False,
            include_interactions=False,
        )
        response = await service.get_customer_360(request)

        # Documents excluded
        assert len(response.documents) == 0
        # Tickets included
        assert len(response.tickets) == 1

    @pytest.mark.asyncio
    async def test_get_customer_360_not_found(self, service):
        """Test Customer 360 when customer not found."""
        service.neo4j.execute_query.return_value = []

        request = Customer360Request(customer_id="nonexistent")

        with pytest.raises(CustomerNotFoundError):
            await service.get_customer_360(request)

    @pytest.mark.asyncio
    async def test_get_customer_360_no_query_or_id(self, service):
        """Test error when neither query nor ID provided."""
        request = Customer360Request()

        with pytest.raises(CustomerNotFoundError):
            await service.get_customer_360(request)

    @pytest.mark.asyncio
    async def test_get_customer_360_cache_hit(self, service, mock_customer_360_response):
        """Test cache hit."""
        mock_cache = AsyncMock()
        service.cache = mock_cache

        # Simulate cache hit
        cached_data = {
            "customer": CustomerNode(
                id="cust_001", name="Acme Corp", type=CustomerType.ENTERPRISE
            ).model_dump(),
            "documents": [],
            "tickets": [],
            "orders": [],
            "interactions": [],
            "products": [],
            "relationship_count": 5,
            "summary": "Cached summary",
            "generated_at": datetime.utcnow().isoformat(),
        }
        mock_cache.get.return_value = cached_data

        request = Customer360Request(customer_id="cust_001")
        response = await service.get_customer_360(request)

        assert response.customer.id == "cust_001"
        # Neo4j should not be called when cache hits
        service.neo4j.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_customer_360_cache_miss(self, service, mock_customer_360_response):
        """Test cache miss followed by DB query."""
        mock_cache = AsyncMock()
        service.cache = mock_cache
        mock_cache.get.return_value = None

        service.neo4j.execute_query.return_value = mock_customer_360_response

        request = Customer360Request(customer_id="cust_001")
        response = await service.get_customer_360(request)

        assert response.customer.id == "cust_001"
        # Verify cache was set
        mock_cache.set.assert_called_once()


class TestFindSimilarCustomers:
    """Test find_similar_customers method."""

    @pytest.fixture
    def service(self):
        """Create service with mock client."""
        mock_client = AsyncMock()
        return Customer360Service(neo4j_client=mock_client)

    @pytest.mark.asyncio
    async def test_find_similar_customers_success(self, service):
        """Test finding similar customers."""
        service.neo4j.execute_query.return_value = [
            {
                "id": "cust_002",
                "name": "Similar Corp",
                "type": "enterprise",
                "industry": "Technology",
                "shared_products": 3,
                "same_industry": True,
                "similarity_score": 8.5,
            },
            {
                "id": "cust_003",
                "name": "Another Corp",
                "type": "smb",
                "industry": "Finance",
                "shared_products": 1,
                "same_industry": False,
                "similarity_score": 2.0,
            },
        ]

        similar = await service.find_similar_customers("cust_001", limit=5)

        assert len(similar) == 2
        assert similar[0].id == "cust_002"
        assert similar[0].shared_products == 3
        assert similar[0].same_industry is True
        assert similar[1].id == "cust_003"

    @pytest.mark.asyncio
    async def test_find_similar_customers_none_found(self, service):
        """Test when no similar customers found."""
        service.neo4j.execute_query.return_value = []

        similar = await service.find_similar_customers("cust_001")

        assert len(similar) == 0

    @pytest.mark.asyncio
    async def test_find_similar_customers_error(self, service):
        """Test error handling returns empty list."""
        service.neo4j.execute_query.side_effect = Neo4jQueryError("Query failed")

        similar = await service.find_similar_customers("cust_001")

        assert len(similar) == 0


class TestSearchCustomers:
    """Test search_customers method."""

    @pytest.fixture
    def service(self):
        """Create service with mock client."""
        mock_client = AsyncMock()
        return Customer360Service(neo4j_client=mock_client)

    @pytest.mark.asyncio
    async def test_search_customers_success(self, service):
        """Test successful customer search."""
        service.neo4j.execute_query.return_value = [
            {"id": "cust_001", "name": "Acme Corp", "type": "enterprise", "industry": "Tech"},
            {"id": "cust_002", "name": "Acme Inc", "type": "smb", "industry": "Finance"},
        ]

        results = await service.search_customers("Acme")

        assert len(results) == 2
        assert results[0].name == "Acme Corp"
        assert results[1].name == "Acme Inc"

    @pytest.mark.asyncio
    async def test_search_customers_no_results(self, service):
        """Test search with no results."""
        service.neo4j.execute_query.return_value = []

        results = await service.search_customers("Nonexistent")

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_customers_error(self, service):
        """Test error handling returns empty list."""
        service.neo4j.execute_query.side_effect = Neo4jQueryError("Query failed")

        results = await service.search_customers("Acme")

        assert len(results) == 0


class TestExtractCustomerFromQuery:
    """Test _extract_customer_from_query method."""

    @pytest.fixture
    def service(self):
        """Create service with mock client."""
        mock_client = AsyncMock()
        return Customer360Service(neo4j_client=mock_client)

    @pytest.mark.asyncio
    async def test_extract_capitalized_name(self, service):
        """Test extracting capitalized company name."""
        service.neo4j.execute_query.return_value = [
            {"id": "cust_001", "name": "Acme Corp"}
        ]

        customer_id = await service._extract_customer_from_query(
            "Show me details about Acme Corp"
        )

        assert customer_id == "cust_001"

    @pytest.mark.asyncio
    async def test_extract_quoted_name(self, service):
        """Test extracting quoted company name."""
        service.neo4j.execute_query.return_value = [
            {"id": "cust_002", "name": "Big Company Inc"}
        ]

        customer_id = await service._extract_customer_from_query(
            'What is the status of "Big Company Inc"?'
        )

        assert customer_id == "cust_002"

    @pytest.mark.asyncio
    async def test_extract_no_match(self, service):
        """Test when no customer matches."""
        service.neo4j.execute_query.return_value = []

        customer_id = await service._extract_customer_from_query(
            "Show me all customers"
        )

        assert customer_id is None

    @pytest.mark.asyncio
    async def test_extract_empty_query(self, service):
        """Test empty query returns None."""
        customer_id = await service._extract_customer_from_query("")

        assert customer_id is None

    @pytest.mark.asyncio
    async def test_extract_none_query(self, service):
        """Test None query returns None."""
        customer_id = await service._extract_customer_from_query(None)

        assert customer_id is None


class TestGenerateSummary:
    """Test _generate_summary method."""

    @pytest.fixture
    def service(self):
        """Create service with mock client."""
        mock_client = AsyncMock()
        return Customer360Service(neo4j_client=mock_client)

    def test_summary_with_all_data(self, service):
        """Test summary with all categories populated."""
        result = {
            "customer": CustomerNode(
                id="cust_001",
                name="Acme Corp",
                type=CustomerType.ENTERPRISE,
                industry="Technology",
            ),
            "documents": [{"id": "d1"}, {"id": "d2"}],
            "tickets": [{"id": "t1"}],
            "orders": [{"id": "o1"}, {"id": "o2"}, {"id": "o3"}],
            "interactions": [{"id": "i1"}],
            "products": [{"id": "p1"}],
        }

        summary = service._generate_summary(result)

        assert "Acme Corp" in summary
        assert "enterprise" in summary
        assert "Technology" in summary
        assert "2 documents" in summary
        assert "1 support ticket" in summary  # Singular
        assert "3 orders" in summary

    def test_summary_no_data(self, service):
        """Test summary with no associated data."""
        result = {
            "customer": CustomerNode(
                id="cust_001", name="Empty Corp", type=CustomerType.SMB
            ),
            "documents": [],
            "tickets": [],
            "orders": [],
            "interactions": [],
            "products": [],
        }

        summary = service._generate_summary(result)

        assert "Empty Corp" in summary
        assert "No associated data found" in summary


class TestSingletonPattern:
    """Test singleton pattern for service."""

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        """Test get_customer360_service returns same instance."""
        await close_customer360_service()

        with patch("app.services.customer360_service.get_neo4j_http_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client

            service1 = get_customer360_service()
            service2 = get_customer360_service()

            assert service1 is service2

        await close_customer360_service()

    @pytest.mark.asyncio
    async def test_close_singleton(self):
        """Test closing singleton service."""
        await close_customer360_service()

        with patch("app.services.customer360_service.get_neo4j_http_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client

            service1 = get_customer360_service()
            await close_customer360_service()
            service2 = get_customer360_service()

            # After close, should get new instance
            assert service1 is not service2

        await close_customer360_service()


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def service(self):
        """Create service with mock client."""
        mock_client = AsyncMock()
        return Customer360Service(neo4j_client=mock_client)

    @pytest.mark.asyncio
    async def test_neo4j_connection_error(self, service):
        """Test Neo4j connection error handling."""
        service.neo4j.execute_query.side_effect = Neo4jConnectionError("Connection failed")

        request = Customer360Request(customer_id="cust_001")

        with pytest.raises(CustomerQueryError) as exc_info:
            await service.get_customer_360(request)

        assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_neo4j_query_error(self, service):
        """Test Neo4j query error handling."""
        service.neo4j.execute_query.side_effect = Neo4jQueryError("Invalid query")

        request = Customer360Request(customer_id="cust_001")

        with pytest.raises(CustomerQueryError) as exc_info:
            await service.get_customer_360(request)

        assert "Query failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cache_error_graceful(self, service):
        """Test cache errors are handled gracefully."""
        mock_cache = AsyncMock()
        service.cache = mock_cache
        mock_cache.get.side_effect = Exception("Cache error")

        service.neo4j.execute_query.return_value = [
            {
                "customer": {"id": "cust_001", "name": "Test", "type": "smb"},
                "documents": [],
                "tickets": [],
                "orders": [],
                "interactions": [],
                "products": [],
                "relationship_count": 0,
            }
        ]

        request = Customer360Request(customer_id="cust_001")
        response = await service.get_customer_360(request)

        # Should still return data even with cache error
        assert response.customer.id == "cust_001"
