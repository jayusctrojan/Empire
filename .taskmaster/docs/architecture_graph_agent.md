# Graph Agent Architecture Plan

## Empire v7.4 - Graph Intelligence for CKO Chat

**Document Version**: 1.0
**Created**: 2025-01-11
**Status**: Draft - Pending Review

---

## 1. Executive Summary

This document details the technical architecture for implementing **Graph Agent capabilities** in Empire's Chief Knowledge Officer Chat, enabling intelligent graph traversal for Customer 360 views, Document Structure navigation, and Graph-Enhanced RAG. The architecture builds upon Empire v7.3's existing Neo4j integration while adding new capabilities for relationship-aware document intelligence.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Neo4j Connection | Direct HTTP API | Better performance than driver for high-volume production |
| Graph Schema | Extend existing | Leverage current Neo4j infrastructure |
| Customer Data | Neo4j nodes | Graph model ideal for relationship queries |
| Document Structure | Neo4j self-referencing | Hierarchies + cross-refs natural in graphs |
| RAG Integration | Post-retrieval expansion | Augment, don't replace, vector search |
| Query Routing | Intent classification | Automatic detection of graph query types |

### Design Principles

1. **Augment, Not Replace**: Graph features enhance existing search, not replace it
2. **Progressive Disclosure**: Start simple, expand context on demand
3. **Performance First**: Cache aggressively, limit traversal depth
4. **Graceful Degradation**: Fall back to vector search if graph unavailable
5. **Existing Patterns**: Follow Empire v7.3 service and route patterns

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EMPIRE DESKTOP CLIENT                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   CKO Chat      │  │ Customer 360    │  │  Document       │              │
│  │   Interface     │  │    Viewer       │  │  Structure View │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
└───────────┼────────────────────┼────────────────────┼────────────────────────┘
            │ REST/WebSocket     │ REST API           │ REST API
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EMPIRE FASTAPI SERVICE                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Query Intent Router                               │    │
│  │  Classifies query type: Customer360 | DocStructure | EnhancedRAG    │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                 │                                            │
│  ┌──────────────────────────────┼──────────────────────────────────────┐    │
│  │                         Graph Router                                 │    │
│  │  POST /api/graph/customer360/*   - Customer unified view            │    │
│  │  POST /api/graph/document-structure/*  - Document navigation        │    │
│  │  POST /api/graph/enhanced-rag/*  - Graph-augmented search           │    │
│  │  GET  /api/graph/entity/*        - Entity context                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │                         Core Services                                 │   │
│  │                                                                       │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │  │  Customer 360   │  │ Document        │  │ Graph-Enhanced  │      │   │
│  │  │    Service      │  │ Structure Svc   │  │   RAG Service   │      │   │
│  │  │                 │  │                 │  │                 │      │   │
│  │  │ - Traversal     │  │ - Extraction    │  │ - Expansion     │      │   │
│  │  │ - Aggregation   │  │ - Cross-refs    │  │ - Enrichment    │      │   │
│  │  │ - NL Queries    │  │ - Smart Retrieve│  │ - Re-ranking    │      │   │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘      │   │
│  │           │                    │                    │                │   │
│  │  ┌────────┴────────────────────┴────────────────────┴────────┐      │   │
│  │  │                   Neo4j HTTP Client                        │      │   │
│  │  │  - Direct transaction/commit API                           │      │   │
│  │  │  - Connection pooling                                      │      │   │
│  │  │  - Query batching                                          │      │   │
│  │  └───────────────────────────────────────────────────────────┘      │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Existing Empire Services                          │    │
│  │  - RAG Service (vector search)                                       │    │
│  │  - neo4j_connection.py (driver fallback)                            │    │
│  │  - neo4j_graph_queries.py (existing patterns)                       │    │
│  │  - knowledge_graph.py routes (extend)                               │    │
│  │  - AI Agents (AGENT-009 through AGENT-015)                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA & STORAGE LAYER                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                          Neo4j (Mac Studio Docker)                   │    │
│  │                                                                      │    │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │    │
│  │  │   Customer     │  │   Document     │  │    Entity      │        │    │
│  │  │   360 Graph    │  │ Structure Graph│  │ Relationships  │        │    │
│  │  │                │  │                │  │                │        │    │
│  │  │ - Customer     │  │ - Section      │  │ - Entity nodes │        │    │
│  │  │ - Document     │  │ - DefinedTerm  │  │ - MENTIONS rel │        │    │
│  │  │ - Ticket       │  │ - Citation     │  │ - RELATED_TO   │        │    │
│  │  │ - Order        │  │ - REFERENCES   │  │                │        │    │
│  │  │ - Interaction  │  │ - HAS_SECTION  │  │                │        │    │
│  │  └────────────────┘  └────────────────┘  └────────────────┘        │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                                   │
│  │    Supabase     │  │  Upstash Redis  │                                   │
│  │   PostgreSQL    │  │                 │                                   │
│  │                 │  │ - Graph query   │                                   │
│  │ - documents_v2  │  │   cache         │                                   │
│  │ - embeddings    │  │ - Entity cache  │                                   │
│  │ - (unchanged)   │  │ - TTL: 5 min    │                                   │
│  └─────────────────┘  └─────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Request Flow - Customer 360 Query

```
User                    FastAPI                 Services              Neo4j
  │                        │                       │                     │
  │ "Show me Acme Corp"    │                       │                     │
  │───────────────────────>│                       │                     │
  │                        │                       │                     │
  │                        │ Intent: Customer360   │                     │
  │                        │──────────────────────>│                     │
  │                        │                       │                     │
  │                        │                       │ Check Redis cache   │
  │                        │                       │──────────┐          │
  │                        │                       │<─────────┘          │
  │                        │                       │                     │
  │                        │                       │ Cypher: Customer360 │
  │                        │                       │────────────────────>│
  │                        │                       │                     │
  │                        │                       │ Nodes + Relationships
  │                        │                       │<────────────────────│
  │                        │                       │                     │
  │                        │                       │ Format + Cache      │
  │                        │                       │──────────┐          │
  │                        │                       │<─────────┘          │
  │                        │                       │                     │
  │                        │ Customer360Response   │                     │
  │                        │<──────────────────────│                     │
  │                        │                       │                     │
  │ Unified Customer View  │                       │                     │
  │<───────────────────────│                       │                     │
```

### 2.3 Request Flow - Graph-Enhanced RAG

```
User                    FastAPI                 RAG Svc         Graph Svc         Neo4j
  │                        │                       │                │               │
  │ "CA insurance reqs"    │                       │                │               │
  │───────────────────────>│                       │                │               │
  │                        │                       │                │               │
  │                        │ Vector search         │                │               │
  │                        │──────────────────────>│                │               │
  │                        │                       │                │               │
  │                        │ Top 10 chunks         │                │               │
  │                        │<──────────────────────│                │               │
  │                        │                       │                │               │
  │                        │ Extract entities      │                │               │
  │                        │──────────────────────────────────────>│               │
  │                        │                       │                │               │
  │                        │                       │                │ Expand graph  │
  │                        │                       │                │──────────────>│
  │                        │                       │                │               │
  │                        │                       │                │ Related nodes │
  │                        │                       │                │<──────────────│
  │                        │                       │                │               │
  │                        │ Expanded context      │                │               │
  │                        │<──────────────────────────────────────│               │
  │                        │                       │                │               │
  │ Answer + Graph Context │                       │                │               │
  │<───────────────────────│                       │                │               │
```

---

## 3. Component Specifications

### 3.1 Neo4j Schema Extensions

#### 3.1.1 Customer 360 Schema

```cypher
// Create Customer 360 nodes and relationships
// Run against existing Neo4j database

// Customer node
CREATE CONSTRAINT customer_id IF NOT EXISTS
FOR (c:Customer) REQUIRE c.id IS UNIQUE;

CREATE INDEX customer_name IF NOT EXISTS
FOR (c:Customer) ON (c.name);

// Ticket node
CREATE CONSTRAINT ticket_id IF NOT EXISTS
FOR (t:Ticket) REQUIRE t.id IS UNIQUE;

CREATE INDEX ticket_customer IF NOT EXISTS
FOR (t:Ticket) ON (t.customer_id);

CREATE INDEX ticket_status IF NOT EXISTS
FOR (t:Ticket) ON (t.status);

// Order node
CREATE CONSTRAINT order_id IF NOT EXISTS
FOR (o:Order) REQUIRE o.id IS UNIQUE;

CREATE INDEX order_customer IF NOT EXISTS
FOR (o:Order) ON (o.customer_id);

// Interaction node
CREATE CONSTRAINT interaction_id IF NOT EXISTS
FOR (i:Interaction) REQUIRE i.id IS UNIQUE;

CREATE INDEX interaction_customer IF NOT EXISTS
FOR (i:Interaction) ON (i.customer_id);

// Product node
CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

// Relationship indexes for fast traversal
CREATE INDEX rel_has_document IF NOT EXISTS
FOR ()-[r:HAS_DOCUMENT]-() ON (r.created_at);

CREATE INDEX rel_has_ticket IF NOT EXISTS
FOR ()-[r:HAS_TICKET]-() ON (r.created_at);
```

#### 3.1.2 Document Structure Schema

```cypher
// Document Structure nodes and relationships

// Section node
CREATE CONSTRAINT section_id IF NOT EXISTS
FOR (s:Section) REQUIRE s.id IS UNIQUE;

CREATE INDEX section_document IF NOT EXISTS
FOR (s:Section) ON (s.document_id);

CREATE INDEX section_number IF NOT EXISTS
FOR (s:Section) ON (s.number);

// DefinedTerm node
CREATE CONSTRAINT defined_term_id IF NOT EXISTS
FOR (dt:DefinedTerm) REQUIRE dt.id IS UNIQUE;

CREATE INDEX defined_term_document IF NOT EXISTS
FOR (dt:DefinedTerm) ON (dt.document_id);

// Citation node
CREATE CONSTRAINT citation_id IF NOT EXISTS
FOR (c:Citation) REQUIRE c.id IS UNIQUE;

// Self-referencing relationship for section hierarchy
// (:Section)-[:HAS_SUBSECTION]->(:Section)

// Cross-reference relationship
// (:Section)-[:REFERENCES]->(:Section)
```

### 3.2 Neo4j HTTP Client

```python
# app/services/neo4j_http_client.py

import httpx
from typing import Dict, Any, List, Optional
from functools import lru_cache
import json
import structlog
from urllib.parse import urlparse
import os

logger = structlog.get_logger()


class Neo4jHTTPClient:
    """
    Production-optimized Neo4j client using direct HTTP API.

    Benefits over driver:
    - Better connection handling for high-volume operations
    - Simpler deployment (no native dependencies)
    - Easier query batching
    - More predictable performance

    Reference: AI Automators Neo4j integration patterns
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "neo4j",
        timeout: float = 30.0,
        max_connections: int = 10
    ):
        # Parse URI to HTTP endpoint
        uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        parsed = urlparse(uri)

        # Convert bolt:// to http://
        scheme = "https" if "ssc" in parsed.scheme or "s" in parsed.scheme else "http"
        host = parsed.hostname or "localhost"
        port = parsed.port or (7687 if "bolt" in parsed.scheme else 7474)

        # HTTP port is typically 7474 (or 7473 for HTTPS)
        if port == 7687:
            port = 7474 if scheme == "http" else 7473

        self.base_url = f"{scheme}://{host}:{port}"
        self.tx_endpoint = f"{self.base_url}/db/{database}/tx/commit"

        self.auth = (
            username or os.getenv("NEO4J_USERNAME", "neo4j"),
            password or os.getenv("NEO4J_PASSWORD", "")
        )

        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=max_connections)
        )

        logger.info(
            "Neo4j HTTP client initialized",
            base_url=self.base_url,
            database=database
        )

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a single Cypher query.

        Returns list of result rows as dictionaries.
        """
        return await self._execute_statements([{
            "statement": query,
            "parameters": parameters or {}
        }])

    async def execute_batch(
        self,
        queries: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple queries in a single transaction.

        Each query should be: {"statement": "CYPHER", "parameters": {}}
        Returns list of results for each query.
        """
        statements = [
            {"statement": q["statement"], "parameters": q.get("parameters", {})}
            for q in queries
        ]

        # Execute all statements
        all_results = await self._execute_statements_full(statements)
        return all_results

    async def _execute_statements(
        self,
        statements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute statements and return flattened results."""
        payload = {"statements": statements}

        try:
            response = await self.client.post(
                self.tx_endpoint,
                json=payload,
                auth=self.auth,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()

            # Check for Neo4j errors
            if result.get("errors"):
                error = result["errors"][0]
                raise Neo4jQueryError(
                    error.get("message", "Unknown error"),
                    error.get("code", "")
                )

            return self._parse_results(result)

        except httpx.HTTPStatusError as e:
            logger.error("Neo4j HTTP error", status=e.response.status_code)
            raise Neo4jConnectionError(f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("Neo4j request error", error=str(e))
            raise Neo4jConnectionError(str(e))

    async def _execute_statements_full(
        self,
        statements: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Execute statements and return results per statement."""
        payload = {"statements": statements}

        response = await self.client.post(
            self.tx_endpoint,
            json=payload,
            auth=self.auth,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        result = response.json()

        if result.get("errors"):
            error = result["errors"][0]
            raise Neo4jQueryError(error.get("message", "Unknown error"))

        return self._parse_results_by_statement(result)

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
        self,
        result: Dict
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
        """Check if Neo4j is accessible."""
        try:
            result = await self.execute_query("RETURN 1 as health")
            return len(result) == 1 and result[0].get("health") == 1
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class Neo4jQueryError(Exception):
    """Raised when a Cypher query fails."""
    def __init__(self, message: str, code: str = ""):
        self.message = message
        self.code = code
        super().__init__(f"[{code}] {message}" if code else message)


class Neo4jConnectionError(Exception):
    """Raised when connection to Neo4j fails."""
    pass


# Singleton instance
_client: Optional[Neo4jHTTPClient] = None


def get_neo4j_http_client() -> Neo4jHTTPClient:
    """Get or create singleton Neo4j HTTP client."""
    global _client
    if _client is None:
        _client = Neo4jHTTPClient()
    return _client
```

### 3.3 Customer 360 Service

```python
# app/services/customer360_service.py

from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
from app.services.neo4j_http_client import get_neo4j_http_client, Neo4jHTTPClient
from app.services.cache_service import CacheService
from app.models.graph_agent import (
    Customer360Request,
    Customer360Response,
    CustomerNode
)

logger = structlog.get_logger()


class Customer360Service:
    """
    Provides unified customer views by traversing the knowledge graph.

    Consolidates data from:
    - Documents (contracts, agreements)
    - Support tickets
    - Orders/transactions
    - Interactions (emails, calls, meetings)
    - Products/services

    Reference: AI Automators Customer360 GraphAgent pattern
    """

    CACHE_TTL = 300  # 5 minutes

    def __init__(
        self,
        neo4j_client: Optional[Neo4jHTTPClient] = None,
        cache: Optional[CacheService] = None
    ):
        self.neo4j = neo4j_client or get_neo4j_http_client()
        self.cache = cache

    async def get_customer_360(
        self,
        request: Customer360Request
    ) -> Customer360Response:
        """
        Get unified customer view.

        If customer_id provided, use directly.
        Otherwise, extract from natural language query.
        """
        customer_id = request.customer_id

        # If no customer_id, try to extract from query
        if not customer_id:
            customer_id = await self._extract_customer_from_query(request.query)
            if not customer_id:
                raise ValueError("Could not identify customer from query")

        # Check cache
        cache_key = f"customer360:{customer_id}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.info("Customer 360 cache hit", customer_id=customer_id)
                return Customer360Response(**cached)

        # Build and execute query
        result = await self._execute_customer_360_query(
            customer_id=customer_id,
            include_documents=request.include_documents,
            include_tickets=request.include_tickets,
            include_orders=request.include_orders,
            include_interactions=request.include_interactions,
            max_items=request.max_items_per_category
        )

        # Generate summary
        result["summary"] = self._generate_summary(result)

        response = Customer360Response(**result)

        # Cache result
        if self.cache:
            await self.cache.set(cache_key, response.dict(), ttl=self.CACHE_TTL)

        return response

    async def _execute_customer_360_query(
        self,
        customer_id: str,
        include_documents: bool,
        include_tickets: bool,
        include_orders: bool,
        include_interactions: bool,
        max_items: int
    ) -> Dict[str, Any]:
        """Execute the Customer 360 graph query."""

        query = """
        MATCH (c:Customer {id: $customer_id})

        // Documents
        OPTIONAL MATCH (c)-[:HAS_DOCUMENT]->(d:Document)
        WITH c, collect(DISTINCT d)[..{max_items}] as documents

        // Tickets
        OPTIONAL MATCH (c)-[:HAS_TICKET]->(t:Ticket)
        WITH c, documents, collect(DISTINCT t)[..{max_items}] as tickets

        // Orders
        OPTIONAL MATCH (c)-[:PLACED_ORDER]->(o:Order)
        WITH c, documents, tickets, collect(DISTINCT o)[..{max_items}] as orders

        // Interactions
        OPTIONAL MATCH (c)-[:HAD_INTERACTION]->(i:Interaction)
        WITH c, documents, tickets, orders, collect(DISTINCT i)[..{max_items}] as interactions

        // Products
        OPTIONAL MATCH (c)-[:USES_PRODUCT]->(p:Product)
        WITH c, documents, tickets, orders, interactions, collect(DISTINCT p) as products

        // Count all relationships
        OPTIONAL MATCH (c)-[r]-()

        RETURN c as customer,
               documents,
               tickets,
               orders,
               interactions,
               products,
               count(DISTINCT r) as relationship_count
        """.format(max_items=max_items)

        results = await self.neo4j.execute_query(
            query,
            {"customer_id": customer_id}
        )

        if not results:
            raise ValueError(f"Customer {customer_id} not found")

        row = results[0]

        return {
            "customer": CustomerNode(
                id=row["customer"]["id"],
                name=row["customer"]["name"],
                type=row["customer"].get("type", "unknown"),
                industry=row["customer"].get("industry"),
                metadata=row["customer"].get("metadata", {})
            ),
            "documents": row.get("documents", []) if include_documents else [],
            "tickets": row.get("tickets", []) if include_tickets else [],
            "orders": row.get("orders", []) if include_orders else [],
            "interactions": row.get("interactions", []) if include_interactions else [],
            "products": row.get("products", []),
            "relationship_count": row.get("relationship_count", 0)
        }

    async def _extract_customer_from_query(self, query: str) -> Optional[str]:
        """Extract customer ID or name from natural language query."""
        # Try to find customer by name in the query
        # This uses a simple pattern match - could be enhanced with NLP

        search_query = """
        MATCH (c:Customer)
        WHERE toLower(c.name) CONTAINS toLower($search_term)
        RETURN c.id as id, c.name as name
        LIMIT 1
        """

        # Extract potential customer name from query
        # Simple heuristic: look for capitalized words/phrases
        import re
        potential_names = re.findall(r'[A-Z][a-zA-Z\s]+(?:Corp|Inc|LLC|Ltd)?', query)

        for name in potential_names:
            results = await self.neo4j.execute_query(
                search_query,
                {"search_term": name.strip()}
            )
            if results:
                return results[0]["id"]

        return None

    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """Generate a natural language summary of the customer."""
        customer = result["customer"]

        parts = [f"{customer.name} is a {customer.type} customer"]

        if customer.industry:
            parts[0] += f" in the {customer.industry} industry"

        doc_count = len(result.get("documents", []))
        ticket_count = len(result.get("tickets", []))
        order_count = len(result.get("orders", []))

        if doc_count:
            parts.append(f"{doc_count} associated documents")
        if ticket_count:
            parts.append(f"{ticket_count} support tickets")
        if order_count:
            parts.append(f"{order_count} orders")

        return ". ".join(parts) + "."

    async def find_similar_customers(
        self,
        customer_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find customers with similar profiles based on graph relationships."""

        query = """
        MATCH (c:Customer {id: $customer_id})

        // Find customers with similar products
        OPTIONAL MATCH (c)-[:USES_PRODUCT]->(p:Product)<-[:USES_PRODUCT]-(similar:Customer)
        WHERE similar.id <> c.id

        WITH similar, count(p) as shared_products

        // Find customers in same industry
        OPTIONAL MATCH (c:Customer {id: $customer_id})
        WHERE similar.industry = c.industry

        RETURN similar.id as id,
               similar.name as name,
               similar.type as type,
               similar.industry as industry,
               shared_products,
               CASE WHEN similar.industry = c.industry THEN 1 ELSE 0 END as same_industry
        ORDER BY shared_products DESC, same_industry DESC
        LIMIT $limit
        """

        return await self.neo4j.execute_query(
            query,
            {"customer_id": customer_id, "limit": limit}
        )
```

### 3.4 Document Structure Service

```python
# app/services/document_structure_service.py

from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
import re
from anthropic import Anthropic
from app.services.neo4j_http_client import get_neo4j_http_client, Neo4jHTTPClient
from app.models.graph_agent import (
    DocumentStructureRequest,
    DocumentStructureResponse,
    SmartRetrievalRequest,
    SmartRetrievalResponse,
    SectionNode
)

logger = structlog.get_logger()


class DocumentStructureService:
    """
    Extracts and navigates document structure graphs.

    Capabilities:
    - Extract section hierarchy from documents
    - Detect and link cross-references
    - Extract defined terms and link to definitions
    - Smart retrieval that follows cross-references

    Reference: AI Automators Document Structure Graph pattern
    """

    def __init__(
        self,
        neo4j_client: Optional[Neo4jHTTPClient] = None,
        anthropic_client: Optional[Anthropic] = None
    ):
        self.neo4j = neo4j_client or get_neo4j_http_client()
        self.claude = anthropic_client

    async def extract_structure(
        self,
        document_id: str,
        document_content: str,
        request: DocumentStructureRequest
    ) -> DocumentStructureResponse:
        """
        Extract document structure and store in Neo4j.

        Process:
        1. Use LLM to identify sections and hierarchy
        2. Detect cross-references between sections
        3. Extract defined terms
        4. Build graph in Neo4j
        """
        logger.info("Extracting document structure", document_id=document_id)

        # Step 1: Extract sections using LLM
        sections = await self._extract_sections(document_content)

        # Step 2: Detect cross-references
        cross_refs = []
        if request.extract_cross_refs:
            cross_refs = await self._detect_cross_references(
                document_content, sections
            )

        # Step 3: Extract defined terms
        definitions = []
        if request.extract_definitions:
            definitions = await self._extract_definitions(
                document_content, sections
            )

        # Step 4: Build graph in Neo4j
        await self._build_structure_graph(
            document_id, sections, cross_refs, definitions
        )

        # Build response
        section_nodes = [
            SectionNode(
                id=s["id"],
                title=s["title"],
                number=s["number"],
                level=s["level"],
                content_preview=s["content"][:200] + "..." if len(s["content"]) > 200 else s["content"],
                child_count=len([c for c in sections if c.get("parent_id") == s["id"]]),
                reference_count=len([r for r in cross_refs if r["from_id"] == s["id"]])
            )
            for s in sections
        ]

        max_depth = max(s["level"] for s in sections) if sections else 0

        return DocumentStructureResponse(
            document_id=document_id,
            title=sections[0]["title"] if sections else "Untitled",
            sections=section_nodes,
            definitions=definitions,
            cross_references=cross_refs,
            structure_depth=max_depth
        )

    async def _extract_sections(self, content: str) -> List[Dict[str, Any]]:
        """Use LLM to extract section hierarchy."""

        if not self.claude:
            # Fall back to regex-based extraction
            return self._extract_sections_regex(content)

        prompt = """Extract the section structure from this document.

For each section, provide:
- number (e.g., "1", "1.1", "1.1.1")
- title
- level (1 = top level, 2 = subsection, etc.)
- start_position (character offset where section starts)
- content (the section text, abbreviated)

Return as JSON array.

Document:
{content}
"""

        response = self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt.format(content=content[:15000])  # Limit context
            }],
            response_format={"type": "json_object"}
        )

        import json
        sections = json.loads(response.content[0].text)

        # Add IDs
        for i, section in enumerate(sections):
            section["id"] = f"section_{i}"

        return sections

    def _extract_sections_regex(self, content: str) -> List[Dict[str, Any]]:
        """Fallback regex-based section extraction."""

        # Pattern matches common section numbering
        pattern = r'^((?:\d+\.)*\d+)\s+(.+?)(?:\n|$)'
        matches = re.finditer(pattern, content, re.MULTILINE)

        sections = []
        for i, match in enumerate(matches):
            number = match.group(1)
            title = match.group(2).strip()
            level = number.count('.') + 1

            sections.append({
                "id": f"section_{i}",
                "number": number,
                "title": title,
                "level": level,
                "start_position": match.start(),
                "content": ""  # Would need to extract content between sections
            })

        return sections

    async def _detect_cross_references(
        self,
        content: str,
        sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect cross-references between sections."""

        # Pattern matches references like "Section 3.2", "see 1.1.1", etc.
        ref_patterns = [
            r'[Ss]ection\s+(\d+(?:\.\d+)*)',
            r'[Ss]ee\s+(?:[Ss]ection\s+)?(\d+(?:\.\d+)*)',
            r'[Pp]ursuant\s+to\s+(?:[Ss]ection\s+)?(\d+(?:\.\d+)*)',
            r'[Aa]rticle\s+(\d+(?:\.\d+)*)',
            r'[Cc]lause\s+(\d+(?:\.\d+)*)',
        ]

        cross_refs = []
        section_numbers = {s["number"]: s["id"] for s in sections}

        for pattern in ref_patterns:
            for match in re.finditer(pattern, content):
                ref_number = match.group(1)

                if ref_number in section_numbers:
                    # Find which section contains this reference
                    ref_pos = match.start()
                    from_section = None
                    for s in sections:
                        if s["start_position"] <= ref_pos:
                            from_section = s
                        else:
                            break

                    if from_section and from_section["number"] != ref_number:
                        cross_refs.append({
                            "from_id": from_section["id"],
                            "from_number": from_section["number"],
                            "to_id": section_numbers[ref_number],
                            "to_number": ref_number,
                            "context": content[max(0, ref_pos-50):ref_pos+100],
                            "reference_text": match.group(0)
                        })

        return cross_refs

    async def _extract_definitions(
        self,
        content: str,
        sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract defined terms from the document."""

        # Pattern matches "Term" means... or Term: definition
        patterns = [
            r'"([^"]+)"\s+(?:means|shall mean|is defined as)\s+([^.]+\.)',
            r'([A-Z][a-zA-Z\s]+):\s+([^.]+\.)',
        ]

        definitions = []
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                term = match.group(1).strip()
                definition = match.group(2).strip()

                # Find which section contains this definition
                def_pos = match.start()
                section_id = None
                for s in sections:
                    if s["start_position"] <= def_pos:
                        section_id = s["id"]

                definitions.append({
                    "term": term,
                    "definition": definition,
                    "section_id": section_id
                })

        return definitions

    async def _build_structure_graph(
        self,
        document_id: str,
        sections: List[Dict[str, Any]],
        cross_refs: List[Dict[str, Any]],
        definitions: List[Dict[str, Any]]
    ):
        """Build the document structure graph in Neo4j."""

        # Create sections
        for section in sections:
            await self.neo4j.execute_query(
                """
                MERGE (s:Section {id: $id})
                SET s.document_id = $document_id,
                    s.number = $number,
                    s.title = $title,
                    s.level = $level,
                    s.content = $content

                WITH s
                MATCH (d:Document {id: $document_id})
                MERGE (d)-[:HAS_SECTION]->(s)
                """,
                {
                    "id": section["id"],
                    "document_id": document_id,
                    "number": section["number"],
                    "title": section["title"],
                    "level": section["level"],
                    "content": section.get("content", "")
                }
            )

        # Create section hierarchy (parent-child)
        for section in sections:
            if section["level"] > 1:
                # Find parent (section with level - 1 and matching prefix)
                parent_number = ".".join(section["number"].split(".")[:-1])
                await self.neo4j.execute_query(
                    """
                    MATCH (parent:Section {document_id: $doc_id, number: $parent_num})
                    MATCH (child:Section {id: $child_id})
                    MERGE (parent)-[:HAS_SUBSECTION]->(child)
                    """,
                    {
                        "doc_id": document_id,
                        "parent_num": parent_number,
                        "child_id": section["id"]
                    }
                )

        # Create cross-references
        for ref in cross_refs:
            await self.neo4j.execute_query(
                """
                MATCH (from:Section {id: $from_id})
                MATCH (to:Section {id: $to_id})
                MERGE (from)-[r:REFERENCES]->(to)
                SET r.context = $context,
                    r.reference_text = $ref_text
                """,
                {
                    "from_id": ref["from_id"],
                    "to_id": ref["to_id"],
                    "context": ref["context"],
                    "ref_text": ref["reference_text"]
                }
            )

        # Create definitions
        for defn in definitions:
            await self.neo4j.execute_query(
                """
                MERGE (dt:DefinedTerm {term: $term, document_id: $doc_id})
                SET dt.definition = $definition

                WITH dt
                MATCH (s:Section {id: $section_id})
                MERGE (dt)-[:DEFINED_IN]->(s)
                """,
                {
                    "term": defn["term"],
                    "doc_id": document_id,
                    "definition": defn["definition"],
                    "section_id": defn["section_id"]
                }
            )

    async def smart_retrieve(
        self,
        request: SmartRetrievalRequest
    ) -> SmartRetrievalResponse:
        """
        Smart retrieval that includes context from cross-references.

        Unlike flat RAG, this:
        1. Gets the primary section matching the query
        2. Includes parent sections for context
        3. Follows cross-references to related sections
        4. Resolves definitions for terms used
        """

        # Find matching sections (could use vector search + graph)
        primary_query = """
        MATCH (d:Document {id: $doc_id})-[:HAS_SECTION]->(s:Section)
        WHERE toLower(s.title) CONTAINS toLower($search_term)
           OR toLower(s.content) CONTAINS toLower($search_term)
        RETURN s
        ORDER BY s.level ASC
        LIMIT 5
        """

        primary_results = await self.neo4j.execute_query(
            primary_query,
            {"doc_id": request.document_id, "search_term": request.query}
        )

        if not primary_results:
            return SmartRetrievalResponse(
                primary_results=[],
                parent_context=None,
                cross_references=[],
                definitions=[],
                context_chain=[]
            )

        primary_section = primary_results[0]["s"]

        # Get parent context if requested
        parent_context = None
        if request.include_parent_context:
            parent_query = """
            MATCH (s:Section {id: $section_id})
            MATCH (parent:Section)-[:HAS_SUBSECTION*]->(s)
            RETURN parent
            ORDER BY parent.level ASC
            """
            parents = await self.neo4j.execute_query(
                parent_query,
                {"section_id": primary_section["id"]}
            )
            if parents:
                parent_context = parents[0]["parent"]

        # Get cross-references if requested
        cross_refs = []
        if request.include_cross_refs:
            ref_query = """
            MATCH (s:Section {id: $section_id})-[:REFERENCES]->(ref:Section)
            RETURN ref, 'outgoing' as direction
            UNION
            MATCH (s:Section {id: $section_id})<-[:REFERENCES]-(ref:Section)
            RETURN ref, 'incoming' as direction
            """
            cross_refs = await self.neo4j.execute_query(
                ref_query,
                {"section_id": primary_section["id"]}
            )

        # Get definitions if requested
        definitions = []
        if request.include_definitions:
            def_query = """
            MATCH (s:Section {id: $section_id})<-[:DEFINED_IN]-(dt:DefinedTerm)
            RETURN dt.term as term, dt.definition as definition
            """
            definitions = await self.neo4j.execute_query(
                def_query,
                {"section_id": primary_section["id"]}
            )

        # Build context chain
        context_chain = ["Document"]
        if parent_context:
            context_chain.append(f"Section {parent_context['number']}: {parent_context['title']}")
        context_chain.append(f"Section {primary_section['number']}: {primary_section['title']}")

        return SmartRetrievalResponse(
            primary_results=[{
                "section": primary_section["number"],
                "title": primary_section["title"],
                "content": primary_section.get("content", ""),
                "relevance_score": 0.95
            }],
            parent_context=parent_context,
            cross_references=cross_refs,
            definitions=definitions,
            context_chain=context_chain
        )
```

### 3.5 Graph-Enhanced RAG Service

```python
# app/services/graph_enhanced_rag_service.py

from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
from app.services.neo4j_http_client import get_neo4j_http_client, Neo4jHTTPClient
from app.services.rag_service import RAGService
from app.models.graph_agent import (
    GraphEnhancedRAGRequest,
    GraphEnhancedRAGResponse,
    GraphExpansionResult
)

logger = structlog.get_logger()


class GraphEnhancedRAGService:
    """
    Augments vector search with graph context expansion.

    Process:
    1. Perform standard vector search
    2. Extract entities from retrieved chunks
    3. Expand via Neo4j graph traversal
    4. Enrich results with relationship context
    5. Re-rank based on graph relevance

    Reference: AI Automators Graph-Based Context Expansion pattern
    """

    def __init__(
        self,
        neo4j_client: Optional[Neo4jHTTPClient] = None,
        rag_service: Optional[RAGService] = None
    ):
        self.neo4j = neo4j_client or get_neo4j_http_client()
        self.rag = rag_service

    async def enhanced_query(
        self,
        request: GraphEnhancedRAGRequest
    ) -> GraphEnhancedRAGResponse:
        """
        Execute graph-enhanced RAG query.
        """
        logger.info("Executing graph-enhanced RAG", query=request.query[:50])

        # Step 1: Standard vector search
        original_chunks = await self._vector_search(
            request.query,
            request.top_k
        )

        # Step 2: Extract entities from chunks
        entities = await self._extract_entities(original_chunks)

        # Step 3: Graph expansion
        expanded_context = []
        relationship_paths = []

        if request.include_entity_context:
            expanded = await self._expand_via_graph(
                entities,
                depth=request.expansion_depth
            )
            expanded_context = expanded["documents"]
            relationship_paths = expanded["paths"]

        # Step 4: Find related documents
        related_docs = []
        if request.include_related_documents:
            related_docs = await self._find_related_documents(
                original_chunks,
                entities
            )
            expanded_context.extend(related_docs)

        # Step 5: Build combined context for answer generation
        all_context = original_chunks + expanded_context

        # Filter by relevance score
        all_context = [
            c for c in all_context
            if c.get("relevance_score", 0) >= request.min_relevance_score
        ]

        # Generate answer (would use Claude or existing RAG pipeline)
        answer = await self._generate_answer(request.query, all_context)

        # Build expansion stats
        expansion_stats = {
            "chunks_before_expansion": len(original_chunks),
            "chunks_after_expansion": len(all_context),
            "entities_extracted": len(entities),
            "relationships_traversed": len(relationship_paths)
        }

        return GraphEnhancedRAGResponse(
            answer=answer,
            sources=all_context[:10],  # Top 10 sources
            graph_context=GraphExpansionResult(
                original_chunks=original_chunks,
                expanded_context=expanded_context,
                entities_found=entities,
                relationship_paths=relationship_paths,
                expansion_stats=expansion_stats
            ),
            confidence_score=self._calculate_confidence(all_context),
            total_chunks_considered=len(all_context)
        )

    async def _vector_search(
        self,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Perform standard vector search."""
        if self.rag:
            return await self.rag.search(query=query, top_k=top_k)

        # Fallback: use existing Supabase vector search
        # This would integrate with existing RAG infrastructure
        return []

    async def _extract_entities(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract entities from retrieved chunks using Neo4j."""

        entities = []

        # Get entity nodes that are mentioned in these chunks
        for chunk in chunks:
            chunk_id = chunk.get("id") or chunk.get("chunk_id")

            query = """
            MATCH (c:DocumentChunk {id: $chunk_id})-[:MENTIONS]->(e:Entity)
            RETURN e.id as id, e.name as name, e.type as type,
                   count{(e)<-[:MENTIONS]-()} as mention_count
            """

            results = await self.neo4j.execute_query(
                query,
                {"chunk_id": chunk_id}
            )

            for r in results:
                if r not in entities:
                    entities.append(r)

        # Sort by mention count (most mentioned = most relevant)
        entities.sort(key=lambda x: x.get("mention_count", 0), reverse=True)

        return entities[:20]  # Limit to top 20 entities

    async def _expand_via_graph(
        self,
        entities: List[Dict[str, Any]],
        depth: int
    ) -> Dict[str, Any]:
        """Expand context via Neo4j graph traversal."""

        expanded_docs = []
        paths = []

        for entity in entities:
            # Get related documents via graph traversal
            query = """
            MATCH (e:Entity {id: $entity_id})
            MATCH (e)<-[:MENTIONS]-(chunk:DocumentChunk)-[:BELONGS_TO]->(d:Document)

            // Get related entities (1-hop)
            OPTIONAL MATCH (e)-[:RELATED_TO]-(related:Entity)
            OPTIONAL MATCH (related)<-[:MENTIONS]-(rchunk:DocumentChunk)-[:BELONGS_TO]->(rd:Document)

            RETURN d.id as doc_id, d.title as title, d.type as type,
                   chunk.content as content, chunk.id as chunk_id,
                   e.name as via_entity,
                   collect(DISTINCT {
                       entity: related.name,
                       document: rd.title
                   }) as related_context
            LIMIT 5
            """

            results = await self.neo4j.execute_query(
                query,
                {"entity_id": entity["id"]}
            )

            for r in results:
                expanded_docs.append({
                    "id": r["chunk_id"],
                    "document_id": r["doc_id"],
                    "title": r["title"],
                    "content": r["content"],
                    "relevance_score": 0.7,  # Graph-expanded = slightly lower default
                    "expansion_type": "entity_link",
                    "via_entity": r["via_entity"]
                })

                # Record path for transparency
                if r["related_context"]:
                    for rc in r["related_context"]:
                        if rc.get("entity"):
                            paths.append({
                                "from": entity["name"],
                                "to": rc["entity"],
                                "relationship": "RELATED_TO",
                                "target_document": rc.get("document")
                            })

        return {"documents": expanded_docs, "paths": paths}

    async def _find_related_documents(
        self,
        original_chunks: List[Dict[str, Any]],
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find documents related to original results."""

        doc_ids = list(set(
            c.get("document_id") for c in original_chunks
            if c.get("document_id")
        ))

        if not doc_ids:
            return []

        query = """
        MATCH (d:Document)
        WHERE d.id IN $doc_ids
        MATCH (d)-[:RELATED_TO]-(related:Document)
        WHERE NOT related.id IN $doc_ids
        RETURN related.id as id, related.title as title,
               related.type as type, related.summary as summary
        LIMIT 10
        """

        results = await self.neo4j.execute_query(
            query,
            {"doc_ids": doc_ids}
        )

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "content": r.get("summary", ""),
                "relevance_score": 0.6,  # Related docs = lower relevance
                "expansion_type": "related_document"
            }
            for r in results
        ]

    async def _generate_answer(
        self,
        query: str,
        context: List[Dict[str, Any]]
    ) -> str:
        """Generate answer using context (would use Claude or existing pipeline)."""
        # This would integrate with existing answer generation
        # For now, return placeholder
        return f"Based on {len(context)} sources..."

    def _calculate_confidence(
        self,
        context: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score based on context quality."""
        if not context:
            return 0.0

        avg_relevance = sum(
            c.get("relevance_score", 0.5) for c in context
        ) / len(context)

        # Boost confidence if we have good coverage
        coverage_boost = min(len(context) / 10, 0.2)

        return min(avg_relevance + coverage_boost, 1.0)
```

### 3.6 API Routes

```python
# app/routes/graph_agent.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.models.graph_agent import (
    Customer360Request, Customer360Response,
    DocumentStructureRequest, DocumentStructureResponse,
    SmartRetrievalRequest, SmartRetrievalResponse,
    GraphEnhancedRAGRequest, GraphEnhancedRAGResponse
)
from app.services.customer360_service import Customer360Service
from app.services.document_structure_service import DocumentStructureService
from app.services.graph_enhanced_rag_service import GraphEnhancedRAGService
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/graph", tags=["Graph Agent"])


# Customer 360 Endpoints
@router.post("/customer360/query", response_model=Customer360Response)
async def customer_360_query(
    request: Customer360Request,
    user=Depends(get_current_user),
    service: Customer360Service = Depends()
):
    """
    Query customer 360 view using natural language.

    Returns unified customer view including documents, tickets, orders,
    and interactions.
    """
    try:
        return await service.get_customer_360(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/customer360/{customer_id}", response_model=Customer360Response)
async def get_customer_360(
    customer_id: str,
    include_documents: bool = True,
    include_tickets: bool = True,
    include_orders: bool = True,
    include_interactions: bool = True,
    max_items: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
    service: Customer360Service = Depends()
):
    """Get full Customer 360 view by customer ID."""
    request = Customer360Request(
        query="",
        customer_id=customer_id,
        include_documents=include_documents,
        include_tickets=include_tickets,
        include_orders=include_orders,
        include_interactions=include_interactions,
        max_items_per_category=max_items
    )
    try:
        return await service.get_customer_360(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/customer360/{customer_id}/similar")
async def find_similar_customers(
    customer_id: str,
    limit: int = Query(5, ge=1, le=20),
    user=Depends(get_current_user),
    service: Customer360Service = Depends()
):
    """Find customers similar to the specified customer."""
    return await service.find_similar_customers(customer_id, limit)


# Document Structure Endpoints
@router.post("/document-structure/extract", response_model=DocumentStructureResponse)
async def extract_document_structure(
    document_id: str,
    document_content: str,
    request: DocumentStructureRequest,
    user=Depends(get_current_user),
    service: DocumentStructureService = Depends()
):
    """
    Extract structure from a document and store in graph.

    Extracts:
    - Section hierarchy
    - Cross-references between sections
    - Defined terms and definitions
    """
    return await service.extract_structure(document_id, document_content, request)


@router.get("/document-structure/{document_id}", response_model=DocumentStructureResponse)
async def get_document_structure(
    document_id: str,
    user=Depends(get_current_user),
    service: DocumentStructureService = Depends()
):
    """Get the extracted structure graph for a document."""
    return await service.get_structure(document_id)


@router.post("/document-structure/smart-retrieve", response_model=SmartRetrievalResponse)
async def smart_retrieve(
    request: SmartRetrievalRequest,
    user=Depends(get_current_user),
    service: DocumentStructureService = Depends()
):
    """
    Smart retrieval that includes cross-reference context.

    Returns matching sections with:
    - Parent context
    - Cross-referenced sections
    - Relevant definitions
    """
    return await service.smart_retrieve(request)


# Graph-Enhanced RAG Endpoints
@router.post("/enhanced-rag/query", response_model=GraphEnhancedRAGResponse)
async def graph_enhanced_rag_query(
    request: GraphEnhancedRAGRequest,
    user=Depends(get_current_user),
    service: GraphEnhancedRAGService = Depends()
):
    """
    Graph-enhanced RAG query.

    Combines vector search with graph expansion:
    1. Vector search for initial results
    2. Entity extraction from results
    3. Graph traversal to expand context
    4. Re-ranked results with graph relevance
    """
    return await service.enhanced_query(request)


@router.post("/enhanced-rag/expand")
async def expand_with_graph(
    chunk_ids: List[str],
    expansion_depth: int = Query(1, ge=1, le=3),
    user=Depends(get_current_user),
    service: GraphEnhancedRAGService = Depends()
):
    """Expand given chunks with graph context."""
    return await service.expand_chunks(chunk_ids, expansion_depth)


# Health Check
@router.get("/health")
async def graph_health():
    """Check Neo4j connection and graph capabilities."""
    from app.services.neo4j_http_client import get_neo4j_http_client

    client = get_neo4j_http_client()
    is_healthy = await client.health_check()

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "neo4j_connected": is_healthy,
        "capabilities": {
            "customer_360": is_healthy,
            "document_structure": is_healthy,
            "graph_enhanced_rag": is_healthy
        }
    }
```

---

## 4. Integration Points

### 4.1 Existing Empire Services Integration

| Service | Integration Point | Usage |
|---------|------------------|-------|
| **neo4j_connection.py** | Driver fallback | Use if HTTP client unavailable |
| **neo4j_graph_queries.py** | Query patterns | Extend with new graph patterns |
| **knowledge_graph.py** | Existing routes | Add new endpoints alongside |
| **RAG Service** | Vector search | Base for graph-enhanced RAG |
| **LlamaIndex Service** | Document parsing | Structure extraction input |
| **AGENT-009** | Document analysis | Enhanced entity extraction |
| **Cache Service** | Redis caching | Graph query results |

### 4.2 Extending Existing Routes

```python
# In app/main.py or app/routes/__init__.py

from app.routes.graph_agent import router as graph_agent_router

# Add to existing routes
app.include_router(graph_agent_router)  # Adds /api/graph/* endpoints
```

---

## 5. Deployment Considerations

### 5.1 Neo4j Schema Migration

```bash
# Migration order - run against existing Neo4j
1. 001_customer360_schema.cypher    # Customer 360 nodes and indexes
2. 002_document_structure_schema.cypher  # Document structure nodes
3. 003_entity_relationships.cypher   # Enhanced entity linking
```

### 5.2 Environment Variables

```bash
# New environment variables (add to existing .env)
# Optional - defaults work with existing NEO4J_* vars
NEO4J_HTTP_PORT=7474              # For HTTP API (default: 7474)
GRAPH_CACHE_TTL=300               # Cache TTL in seconds
GRAPH_MAX_EXPANSION_DEPTH=3       # Max graph traversal depth
CUSTOMER360_ENABLED=true          # Feature flag
DOCUMENT_STRUCTURE_ENABLED=true   # Feature flag
GRAPH_ENHANCED_RAG_ENABLED=true   # Feature flag
```

### 5.3 Render Service Updates

- **Empire API**: No new services needed - extends existing FastAPI
- **Environment**: Add new environment variables
- **No additional workers**: Uses existing Celery infrastructure

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_neo4j_http_client.py
# tests/test_customer360_service.py
# tests/test_document_structure_service.py
# tests/test_graph_enhanced_rag_service.py
```

### 6.2 Integration Tests

```python
# tests/integration/test_graph_agent_api.py
# tests/integration/test_customer360_flow.py
# tests/integration/test_document_structure_extraction.py
```

### 6.3 Performance Tests

```python
# tests/performance/test_graph_query_performance.py
# - Customer 360 query < 2 seconds
# - Graph expansion (1-hop) < 500ms
# - Document structure extraction < 30 seconds
```

---

## 7. Monitoring & Observability

### 7.1 New Prometheus Metrics

```python
# Graph query metrics
graph_query_duration_seconds
graph_query_cache_hits_total
graph_query_cache_misses_total
graph_expansion_depth_histogram
customer360_queries_total
document_structure_extractions_total
graph_enhanced_rag_queries_total
```

### 7.2 Alert Rules

```yaml
# Graph-specific alerts
- alert: Neo4jHTTPConnectionFailed
  expr: graph_query_errors_total > 10
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Neo4j HTTP connection failures"

- alert: SlowGraphQueries
  expr: histogram_quantile(0.95, graph_query_duration_seconds) > 5
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Graph queries taking too long"
```

---

## 8. Security Considerations

### 8.1 Access Control
- Graph queries inherit user authentication from Empire
- RLS-like patterns: filter results by user's customer access
- No direct Neo4j exposure to clients

### 8.2 Query Safety
- Parameterized Cypher queries (no string interpolation)
- Query timeout limits
- Depth limits on graph traversal

---

## 9. Future Enhancements

### Phase 2+
- Graph-based recommendations
- Multi-tenant graph isolation
- Real-time graph updates from external systems
- Graph visualization UI components
- Custom relationship types per customer
- Advanced path finding algorithms

---

**Document End**
