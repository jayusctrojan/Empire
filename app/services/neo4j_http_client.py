# app/services/neo4j_http_client.py
"""
Production-optimized Neo4j HTTP client using direct HTTP API.

Task 101: Graph Agent - Neo4j HTTP Client
Feature: 005-graph-agent

Benefits over driver:
- Better connection handling for high-volume operations
- Simpler deployment (no native dependencies)
- Easier query batching
- More predictable performance
"""

import httpx
from typing import Dict, Any, List, Optional
import structlog
from urllib.parse import urlparse
import os

logger = structlog.get_logger()


class Neo4jQueryError(Exception):
    """Raised when a Cypher query fails."""

    def __init__(self, message: str, code: str = ""):
        self.message = message
        self.code = code
        super().__init__(f"[{code}] {message}" if code else message)


class Neo4jConnectionError(Exception):
    """Raised when connection to Neo4j fails."""

    pass


class Neo4jHTTPClient:
    """
    Production-optimized Neo4j client using direct HTTP API.

    Uses the transaction/commit endpoint for single-request transactions,
    providing better performance for high-volume operations.

    Reference: AI Automators Neo4j integration patterns
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "neo4j",
        timeout: float = 30.0,
        max_connections: int = 10,
    ):
        """
        Initialize Neo4j HTTP client.

        Args:
            uri: Neo4j URI (bolt://, bolt+ssc://, etc.). Defaults to NEO4J_URI env var.
            username: Neo4j username. Defaults to NEO4J_USERNAME env var.
            password: Neo4j password. Defaults to NEO4J_PASSWORD env var.
            database: Database name. Defaults to "neo4j".
            timeout: Request timeout in seconds. Defaults to 30.0.
            max_connections: Maximum concurrent connections. Defaults to 10.
        """
        # Parse URI to HTTP endpoint
        uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        parsed = urlparse(uri)

        # Convert bolt:// to http://
        # bolt+ssc:// or bolt+s:// = secure connection -> https
        scheme = "https" if "ssc" in parsed.scheme or "+s" in parsed.scheme else "http"
        host = parsed.hostname or "localhost"
        port = parsed.port or (7687 if "bolt" in parsed.scheme else 7474)

        # HTTP port is typically 7474 (or 7473 for HTTPS)
        # If port is bolt port (7687), convert to HTTP port
        if port == 7687:
            port = int(os.getenv("NEO4J_HTTP_PORT", "7474")) if scheme == "http" else 7473

        self.base_url = f"{scheme}://{host}:{port}"
        self.tx_endpoint = f"{self.base_url}/db/{database}/tx/commit"
        self.database = database

        self.auth = (
            username or os.getenv("NEO4J_USERNAME", "neo4j"),
            password or os.getenv("NEO4J_PASSWORD", ""),
        )

        self.timeout = timeout
        self._max_connections = max_connections
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(
            "Neo4j HTTP client initialized",
            base_url=self.base_url,
            database=database,
            max_connections=max_connections,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client (lazy initialization)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=self._max_connections),
            )
        return self._client

    async def execute_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a single Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result rows as dictionaries

        Raises:
            Neo4jQueryError: If the query fails
            Neo4jConnectionError: If connection fails
        """
        return await self._execute_statements(
            [{"statement": query, "parameters": parameters or {}}]
        )

    async def execute_batch(
        self, queries: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple queries in a single transaction.

        Args:
            queries: List of query dicts with "statement" and optional "parameters"

        Returns:
            List of results for each query

        Example:
            results = await client.execute_batch([
                {"statement": "MATCH (n:Customer) RETURN n LIMIT 10"},
                {"statement": "MATCH (d:Document) RETURN d LIMIT 10"}
            ])
        """
        statements = [
            {"statement": q["statement"], "parameters": q.get("parameters", {})}
            for q in queries
        ]

        return await self._execute_statements_full(statements)

    async def _execute_statements(
        self, statements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute statements and return flattened results."""
        payload = {"statements": statements}
        client = await self._get_client()

        try:
            response = await client.post(
                self.tx_endpoint,
                json=payload,
                auth=self.auth,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()

            # Check for Neo4j errors
            if result.get("errors"):
                error = result["errors"][0]
                raise Neo4jQueryError(
                    error.get("message", "Unknown error"), error.get("code", "")
                )

            return self._parse_results(result)

        except httpx.HTTPStatusError as e:
            logger.error(
                "Neo4j HTTP error",
                status=e.response.status_code,
                endpoint=self.tx_endpoint,
            )
            raise Neo4jConnectionError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            logger.error("Neo4j request error", error=str(e), endpoint=self.tx_endpoint)
            raise Neo4jConnectionError(str(e))

    async def _execute_statements_full(
        self, statements: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Execute statements and return results per statement."""
        payload = {"statements": statements}
        client = await self._get_client()

        try:
            response = await client.post(
                self.tx_endpoint,
                json=payload,
                auth=self.auth,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()

            if result.get("errors"):
                error = result["errors"][0]
                raise Neo4jQueryError(
                    error.get("message", "Unknown error"), error.get("code", "")
                )

            return self._parse_results_by_statement(result)

        except httpx.HTTPStatusError as e:
            logger.error("Neo4j HTTP error", status=e.response.status_code)
            raise Neo4jConnectionError(f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("Neo4j request error", error=str(e))
            raise Neo4jConnectionError(str(e))

    def _parse_results(self, result: Dict) -> List[Dict[str, Any]]:
        """Parse Neo4j response into list of row dictionaries."""
        rows = []
        for statement_result in result.get("results", []):
            columns = statement_result.get("columns", [])
            for row_data in statement_result.get("data", []):
                row = row_data.get("row", [])
                rows.append(dict(zip(columns, row)))
        return rows

    def _parse_results_by_statement(
        self, result: Dict
    ) -> List[List[Dict[str, Any]]]:
        """Parse results keeping them grouped by statement."""
        all_results = []
        for statement_result in result.get("results", []):
            columns = statement_result.get("columns", [])
            rows = []
            for row_data in statement_result.get("data", []):
                row = row_data.get("row", [])
                rows.append(dict(zip(columns, row)))
            all_results.append(rows)
        return all_results

    async def health_check(self) -> bool:
        """
        Check if Neo4j is accessible.

        Returns:
            True if Neo4j is healthy, False otherwise
        """
        try:
            result = await self.execute_query("RETURN 1 as health")
            return len(result) == 1 and result[0].get("health") == 1
        except Exception as e:
            logger.warning("Neo4j health check failed", error=str(e))
            return False

    async def close(self):
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.info("Neo4j HTTP client closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance for dependency injection
_client: Optional[Neo4jHTTPClient] = None


def get_neo4j_http_client() -> Neo4jHTTPClient:
    """
    Get or create singleton Neo4j HTTP client.

    Use this for FastAPI dependency injection:

        @app.get("/api/graph/health")
        async def health(client: Neo4jHTTPClient = Depends(get_neo4j_http_client)):
            return {"healthy": await client.health_check()}
    """
    global _client
    if _client is None:
        _client = Neo4jHTTPClient()
    return _client


async def close_neo4j_http_client():
    """Close the singleton client. Call on application shutdown."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
