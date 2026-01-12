# tests/test_neo4j_http_client.py
"""
Unit tests for Neo4j HTTP Client.

Task 101: Graph Agent - Neo4j HTTP Client
Feature: 005-graph-agent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.neo4j_http_client import (
    Neo4jHTTPClient,
    Neo4jQueryError,
    Neo4jConnectionError,
    get_neo4j_http_client,
    close_neo4j_http_client,
)


class TestNeo4jHTTPClientInit:
    """Test client initialization and URI parsing."""

    def test_default_initialization(self):
        """Test client initializes with default values."""
        with patch.dict("os.environ", {}, clear=True):
            client = Neo4jHTTPClient(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="testpass",
            )

            assert client.base_url == "http://localhost:7474"
            assert client.tx_endpoint == "http://localhost:7474/db/neo4j/tx/commit"
            assert client.auth == ("neo4j", "testpass")
            assert client.database == "neo4j"

    def test_bolt_uri_conversion(self):
        """Test bolt:// URI converts to http://."""
        client = Neo4jHTTPClient(
            uri="bolt://myhost:7687",
            username="user",
            password="pass",
        )

        assert client.base_url == "http://myhost:7474"

    def test_bolt_ssc_uri_conversion(self):
        """Test bolt+ssc:// URI converts to https://."""
        client = Neo4jHTTPClient(
            uri="bolt+ssc://myhost:7687",
            username="user",
            password="pass",
        )

        assert client.base_url == "https://myhost:7473"

    def test_bolt_s_uri_conversion(self):
        """Test bolt+s:// URI converts to https://."""
        client = Neo4jHTTPClient(
            uri="bolt+s://securehost:7687",
            username="user",
            password="pass",
        )

        assert client.base_url == "https://securehost:7473"

    def test_custom_database(self):
        """Test client uses custom database name."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="user",
            password="pass",
            database="customdb",
        )

        assert client.tx_endpoint == "http://localhost:7474/db/customdb/tx/commit"

    def test_custom_timeout(self):
        """Test client uses custom timeout."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="user",
            password="pass",
            timeout=60.0,
        )

        assert client.timeout == 60.0

    def test_env_var_fallback(self):
        """Test client uses environment variables as fallback."""
        with patch.dict(
            "os.environ",
            {
                "NEO4J_URI": "bolt://envhost:7687",
                "NEO4J_USERNAME": "envuser",
                "NEO4J_PASSWORD": "envpass",
            },
        ):
            client = Neo4jHTTPClient()

            assert "envhost" in client.base_url
            assert client.auth == ("envuser", "envpass")


class TestNeo4jHTTPClientQueries:
    """Test query execution methods."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

    @pytest.fixture
    def mock_response(self):
        """Create a mock successful response."""
        return {
            "results": [
                {
                    "columns": ["name", "age"],
                    "data": [
                        {"row": ["Alice", 30]},
                        {"row": ["Bob", 25]},
                    ],
                }
            ],
            "errors": [],
        }

    @pytest.mark.asyncio
    async def test_execute_query_success(self, client, mock_response):
        """Test successful query execution."""
        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_http_response
            mock_get_client.return_value = mock_http_client

            result = await client.execute_query(
                "MATCH (n:Person) RETURN n.name as name, n.age as age"
            )

            assert len(result) == 2
            assert result[0] == {"name": "Alice", "age": 30}
            assert result[1] == {"name": "Bob", "age": 25}

    @pytest.mark.asyncio
    async def test_execute_query_with_parameters(self, client, mock_response):
        """Test query execution with parameters."""
        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_http_response
            mock_get_client.return_value = mock_http_client

            await client.execute_query(
                "MATCH (n:Person {name: $name}) RETURN n",
                parameters={"name": "Alice"},
            )

            # Verify the parameters were included in the request
            call_args = mock_http_client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["statements"][0]["parameters"] == {"name": "Alice"}

    @pytest.mark.asyncio
    async def test_execute_query_neo4j_error(self, client):
        """Test handling of Neo4j query errors."""
        error_response = {
            "results": [],
            "errors": [
                {
                    "code": "Neo.ClientError.Statement.SyntaxError",
                    "message": "Invalid syntax",
                }
            ],
        }

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = error_response
        mock_http_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_http_response
            mock_get_client.return_value = mock_http_client

            with pytest.raises(Neo4jQueryError) as exc_info:
                await client.execute_query("INVALID CYPHER")

            assert "Invalid syntax" in str(exc_info.value)
            assert exc_info.value.code == "Neo.ClientError.Statement.SyntaxError"

    @pytest.mark.asyncio
    async def test_execute_query_connection_error(self, client):
        """Test handling of connection errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.side_effect = httpx.RequestError("Connection failed")
            mock_get_client.return_value = mock_http_client

            with pytest.raises(Neo4jConnectionError) as exc_info:
                await client.execute_query("RETURN 1")

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_query_http_error(self, client):
        """Test handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            mock_get_client.return_value = mock_http_client

            with pytest.raises(Neo4jConnectionError) as exc_info:
                await client.execute_query("RETURN 1")

            assert "401" in str(exc_info.value)


class TestNeo4jHTTPClientBatch:
    """Test batch query execution."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

    @pytest.mark.asyncio
    async def test_execute_batch_success(self, client):
        """Test successful batch execution."""
        batch_response = {
            "results": [
                {
                    "columns": ["count"],
                    "data": [{"row": [10]}],
                },
                {
                    "columns": ["name"],
                    "data": [{"row": ["Alice"]}, {"row": ["Bob"]}],
                },
            ],
            "errors": [],
        }

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = batch_response
        mock_http_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_http_response
            mock_get_client.return_value = mock_http_client

            results = await client.execute_batch(
                [
                    {"statement": "MATCH (n) RETURN count(n) as count"},
                    {"statement": "MATCH (n:Person) RETURN n.name as name"},
                ]
            )

            assert len(results) == 2
            assert results[0] == [{"count": 10}]
            assert results[1] == [{"name": "Alice"}, {"name": "Bob"}]


class TestNeo4jHTTPClientHealth:
    """Test health check functionality."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        health_response = {
            "results": [
                {
                    "columns": ["health"],
                    "data": [{"row": [1]}],
                }
            ],
            "errors": [],
        }

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = health_response
        mock_http_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_http_response
            mock_get_client.return_value = mock_http_client

            is_healthy = await client.health_check()

            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Test health check returns False on error."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post.side_effect = httpx.RequestError("Connection refused")
            mock_get_client.return_value = mock_http_client

            is_healthy = await client.health_check()

            assert is_healthy is False


class TestNeo4jHTTPClientLifecycle:
    """Test client lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test client closes properly."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

        # Force client creation with mock
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        client._client = mock_http_client

        await client.close()

        # Verify aclose was called
        mock_http_client.aclose.assert_called_once()
        # Client should be set to None after close
        assert client._client is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager usage."""
        async with Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        ) as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_lazy_client_initialization(self):
        """Test HTTP client is created lazily."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

        # Client should not be created yet
        assert client._client is None

        # Getting client should create it
        http_client = await client._get_client()
        assert http_client is not None
        assert client._client is not None


class TestNeo4jHTTPClientSingleton:
    """Test singleton pattern."""

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        """Test get_neo4j_http_client returns same instance."""
        # Reset singleton
        await close_neo4j_http_client()

        with patch.dict(
            "os.environ",
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USERNAME": "neo4j",
                "NEO4J_PASSWORD": "testpass",
            },
        ):
            client1 = get_neo4j_http_client()
            client2 = get_neo4j_http_client()

            assert client1 is client2

        # Cleanup
        await close_neo4j_http_client()

    @pytest.mark.asyncio
    async def test_close_singleton(self):
        """Test closing singleton client."""
        # Reset singleton
        await close_neo4j_http_client()

        with patch.dict(
            "os.environ",
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USERNAME": "neo4j",
                "NEO4J_PASSWORD": "testpass",
            },
        ):
            client = get_neo4j_http_client()
            assert client is not None

            await close_neo4j_http_client()

            # After closing, getting client should create new one
            new_client = get_neo4j_http_client()
            assert new_client is not client

        # Cleanup
        await close_neo4j_http_client()


class TestNeo4jHTTPClientResultParsing:
    """Test result parsing functionality."""

    def test_parse_empty_results(self):
        """Test parsing empty result set."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

        # Empty data array returns empty list
        result = {"results": [{"columns": [], "data": []}], "errors": []}
        parsed = client._parse_results(result)

        assert parsed == []

    def test_parse_no_results(self):
        """Test parsing when no results returned."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

        result = {"results": [], "errors": []}
        parsed = client._parse_results(result)

        assert parsed == []

    def test_parse_multiple_columns(self):
        """Test parsing results with multiple columns."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

        result = {
            "results": [
                {
                    "columns": ["a", "b", "c"],
                    "data": [
                        {"row": [1, 2, 3]},
                        {"row": [4, 5, 6]},
                    ],
                }
            ],
            "errors": [],
        }
        parsed = client._parse_results(result)

        assert len(parsed) == 2
        assert parsed[0] == {"a": 1, "b": 2, "c": 3}
        assert parsed[1] == {"a": 4, "b": 5, "c": 6}

    def test_parse_results_by_statement(self):
        """Test parsing results grouped by statement."""
        client = Neo4jHTTPClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpass",
        )

        result = {
            "results": [
                {"columns": ["x"], "data": [{"row": [1]}]},
                {"columns": ["y"], "data": [{"row": [2]}, {"row": [3]}]},
            ],
            "errors": [],
        }
        parsed = client._parse_results_by_statement(result)

        assert len(parsed) == 2
        assert parsed[0] == [{"x": 1}]
        assert parsed[1] == [{"y": 2}, {"y": 3}]
