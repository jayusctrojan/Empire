# Task ID: 101

**Title:** Implement Neo4j HTTP Client

**Status:** pending

**Dependencies:** None

**Priority:** high

**Description:** Create a production-optimized Neo4j HTTP client that directly accesses the transaction/commit endpoint for better performance than the driver approach.

**Details:**

Implement the Neo4jHTTPClient class in app/services/neo4j_http_client.py with the following features:

1. Direct HTTP connection to Neo4j's transaction/commit endpoint
2. Connection pooling for efficient resource usage
3. Query batching capabilities
4. Proper error handling and result parsing
5. Async support for non-blocking operations

Implementation should follow the pattern provided in the PRD:
```python
import httpx
from typing import Dict, Any, List

class Neo4jHTTPClient:
    def __init__(self, uri: str, username: str, password: str):
        self.base_url = uri.replace("bolt://", "http://").replace("bolt+ssc://", "https://")
        self.base_url = f"{self.base_url}/db/neo4j/tx/commit"
        self.auth = (username, password)
        self.client = httpx.AsyncClient(timeout=30.0)

    async def execute_query(
        self,
        query: str,
        parameters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        payload = {
            "statements": [{
                "statement": query,
                "parameters": parameters or {}
            }]
        }

        response = await self.client.post(
            self.base_url,
            json=payload,
            auth=self.auth,
            headers={"Content-Type": "application/json"}
        )

        result = response.json()
        if result.get("errors"):
            raise Exception(result["errors"][0]["message"])

        return self._parse_results(result)

    def _parse_results(self, result: Dict) -> List[Dict]:
        rows = []
        for statement_result in result.get("results", []):
            columns = statement_result.get("columns", [])
            for row in statement_result.get("data", []):
                rows.append(dict(zip(columns, row["row"])))
        return rows
```

Add methods for batch query execution and connection management. Include unit tests to verify functionality against a Neo4j instance.

**Test Strategy:**

1. Unit tests with mocked HTTP responses to verify correct parsing
2. Integration tests against a test Neo4j instance to verify actual connectivity
3. Performance benchmarks comparing HTTP client vs. driver approach
4. Test connection pooling under load
5. Test error handling with malformed queries
6. Test with various Neo4j query types (READ, WRITE, etc.)
