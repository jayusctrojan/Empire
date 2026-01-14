# Implementation Specifications: Graph Agent for CKO Chat

**Date**: 2025-01-11
**Source**: `.taskmaster/docs/architecture_graph_agent.md`
**Purpose**: Detailed code specifications for implementation

---

## Table of Contents

1. [Neo4j HTTP Client](#1-neo4j-http-client)
2. [Pydantic Models](#2-pydantic-models)
3. [Customer 360 Service](#3-customer-360-service)
4. [Document Structure Service](#4-document-structure-service)
5. [Graph-Enhanced RAG Service](#5-graph-enhanced-rag-service)
6. [API Routes](#6-api-routes)
7. [Neo4j Schema Migrations](#7-neo4j-schema-migrations)

---

## 1. Neo4j HTTP Client

**File**: `app/services/neo4j_http_client.py`

Production-optimized Neo4j client using direct HTTP API for better performance than the driver approach.

```python
# app/services/neo4j_http_client.py

import httpx
from typing import Dict, Any, List, Optional
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

---

## 2. Pydantic Models

**File**: `app/models/graph_agent.py`

```python
# app/models/graph_agent.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class CustomerType(str, Enum):
    ENTERPRISE = "enterprise"
    SMB = "smb"
    INDIVIDUAL = "individual"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InteractionType(str, Enum):
    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    CHAT = "chat"


# Node Models
class CustomerNode(BaseModel):
    id: str
    name: str
    type: CustomerType
    industry: Optional[str] = None
    status: str = "active"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentSummary(BaseModel):
    id: str
    title: str
    type: str
    upload_date: Optional[datetime] = None


class TicketSummary(BaseModel):
    id: str
    title: str
    status: TicketStatus
    priority: TicketPriority
    created_date: Optional[datetime] = None


class OrderSummary(BaseModel):
    id: str
    order_number: str
    amount: float
    status: str
    order_date: Optional[datetime] = None


class InteractionSummary(BaseModel):
    id: str
    type: InteractionType
    summary: str
    date: Optional[datetime] = None


class ProductSummary(BaseModel):
    id: str
    name: str
    category: str


class SectionNode(BaseModel):
    id: str
    number: str
    title: str
    level: int
    content_preview: Optional[str] = None
    child_count: int = 0
    reference_count: int = 0


class DefinedTermNode(BaseModel):
    term: str
    definition: str
    section_id: Optional[str] = None


class CrossReference(BaseModel):
    from_id: str
    from_number: str
    to_id: str
    to_number: str
    context: Optional[str] = None
    reference_text: Optional[str] = None


class EntityNode(BaseModel):
    id: str
    name: str
    type: str
    mention_count: int = 0


class RelationshipPath(BaseModel):
    from_entity: str = Field(alias="from")
    to_entity: str = Field(alias="to")
    relationship: str
    target_document: Optional[str] = None

    class Config:
        populate_by_name = True


# Request Models
class Customer360Request(BaseModel):
    query: str = ""
    customer_id: Optional[str] = None
    include_documents: bool = True
    include_tickets: bool = True
    include_orders: bool = True
    include_interactions: bool = True
    max_items_per_category: int = Field(default=10, ge=1, le=50)


class DocumentStructureRequest(BaseModel):
    extract_cross_refs: bool = True
    extract_definitions: bool = True


class SmartRetrievalRequest(BaseModel):
    document_id: str
    query: str
    include_parent_context: bool = True
    include_cross_refs: bool = True
    include_definitions: bool = True


class GraphEnhancedRAGRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    expansion_depth: int = Field(default=1, ge=1, le=3)
    include_entity_context: bool = True
    include_related_documents: bool = True
    min_relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)


# Response Models
class Customer360Response(BaseModel):
    customer: CustomerNode
    documents: List[DocumentSummary] = Field(default_factory=list)
    tickets: List[TicketSummary] = Field(default_factory=list)
    orders: List[OrderSummary] = Field(default_factory=list)
    interactions: List[InteractionSummary] = Field(default_factory=list)
    products: List[ProductSummary] = Field(default_factory=list)
    summary: str = ""
    relationship_count: int = 0


class DocumentStructureResponse(BaseModel):
    document_id: str
    title: str
    sections: List[SectionNode] = Field(default_factory=list)
    definitions: List[DefinedTermNode] = Field(default_factory=list)
    cross_references: List[CrossReference] = Field(default_factory=list)
    structure_depth: int = 0


class SectionResult(BaseModel):
    section: str
    title: str
    content: str
    relevance_score: float = 0.0


class SmartRetrievalResponse(BaseModel):
    primary_results: List[SectionResult] = Field(default_factory=list)
    parent_context: Optional[Dict[str, Any]] = None
    cross_references: List[Dict[str, Any]] = Field(default_factory=list)
    definitions: List[DefinedTermNode] = Field(default_factory=list)
    context_chain: List[str] = Field(default_factory=list)


class SourceChunk(BaseModel):
    id: str
    document_id: Optional[str] = None
    title: Optional[str] = None
    content: str
    relevance_score: float = 0.0
    expansion_type: str = "original"  # original, entity_link, related_document
    via_entity: Optional[str] = None


class ExpansionStats(BaseModel):
    chunks_before_expansion: int = 0
    chunks_after_expansion: int = 0
    entities_extracted: int = 0
    relationships_traversed: int = 0


class GraphExpansionResult(BaseModel):
    original_chunks: List[SourceChunk] = Field(default_factory=list)
    expanded_context: List[SourceChunk] = Field(default_factory=list)
    entities_found: List[EntityNode] = Field(default_factory=list)
    relationship_paths: List[RelationshipPath] = Field(default_factory=list)
    expansion_stats: ExpansionStats = Field(default_factory=ExpansionStats)


class GraphEnhancedRAGResponse(BaseModel):
    answer: str
    sources: List[SourceChunk] = Field(default_factory=list)
    graph_context: GraphExpansionResult = Field(default_factory=GraphExpansionResult)
    confidence_score: float = 0.0
    total_chunks_considered: int = 0


class SimilarCustomer(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    industry: Optional[str] = None
    shared_products: int = 0
    same_industry: bool = False
    similarity_score: float = 0.0


class GraphHealthResponse(BaseModel):
    status: str  # healthy, unhealthy, degraded
    neo4j_connected: bool
    capabilities: Dict[str, bool] = Field(default_factory=dict)
```

---

## 3. Customer 360 Service

**File**: `app/services/customer360_service.py`

```python
# app/services/customer360_service.py

from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
import re
from app.services.neo4j_http_client import get_neo4j_http_client, Neo4jHTTPClient
from app.services.cache_service import CacheService
from app.models.graph_agent import (
    Customer360Request,
    Customer360Response,
    CustomerNode,
    DocumentSummary,
    TicketSummary,
    OrderSummary,
    InteractionSummary,
    ProductSummary,
    SimilarCustomer
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
            await self.cache.set(cache_key, response.model_dump(), ttl=self.CACHE_TTL)

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
            "documents": [
                DocumentSummary(**d) for d in row.get("documents", [])
            ] if include_documents else [],
            "tickets": [
                TicketSummary(**t) for t in row.get("tickets", [])
            ] if include_tickets else [],
            "orders": [
                OrderSummary(**o) for o in row.get("orders", [])
            ] if include_orders else [],
            "interactions": [
                InteractionSummary(**i) for i in row.get("interactions", [])
            ] if include_interactions else [],
            "products": [
                ProductSummary(**p) for p in row.get("products", [])
            ],
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
    ) -> List[SimilarCustomer]:
        """Find customers with similar profiles based on graph relationships."""

        query = """
        MATCH (c:Customer {id: $customer_id})

        // Find customers with similar products
        OPTIONAL MATCH (c)-[:USES_PRODUCT]->(p:Product)<-[:USES_PRODUCT]-(similar:Customer)
        WHERE similar.id <> c.id

        WITH c, similar, count(p) as shared_products

        // Check same industry
        WITH c, similar, shared_products,
             CASE WHEN similar.industry = c.industry THEN 1 ELSE 0 END as same_industry

        RETURN similar.id as id,
               similar.name as name,
               similar.type as type,
               similar.industry as industry,
               shared_products,
               same_industry,
               (shared_products * 0.7 + same_industry * 0.3) as similarity_score
        ORDER BY similarity_score DESC
        LIMIT $limit
        """

        results = await self.neo4j.execute_query(
            query,
            {"customer_id": customer_id, "limit": limit}
        )

        return [
            SimilarCustomer(
                id=r["id"],
                name=r["name"],
                type=r.get("type"),
                industry=r.get("industry"),
                shared_products=r["shared_products"],
                same_industry=bool(r["same_industry"]),
                similarity_score=r["similarity_score"]
            )
            for r in results
        ]
```

---

## 4. Document Structure Service

**File**: `app/services/document_structure_service.py`

```python
# app/services/document_structure_service.py

from typing import Dict, Any, List, Optional
import structlog
import re
from anthropic import Anthropic
import os
from app.services.neo4j_http_client import get_neo4j_http_client, Neo4jHTTPClient
from app.models.graph_agent import (
    DocumentStructureRequest,
    DocumentStructureResponse,
    SmartRetrievalRequest,
    SmartRetrievalResponse,
    SectionNode,
    SectionResult,
    DefinedTermNode,
    CrossReference
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
        self.claude = anthropic_client or Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        ) if os.getenv("ANTHROPIC_API_KEY") else None

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

        definition_nodes = [
            DefinedTermNode(
                term=d["term"],
                definition=d["definition"],
                section_id=d.get("section_id")
            )
            for d in definitions
        ]

        cross_ref_models = [
            CrossReference(
                from_id=r["from_id"],
                from_number=r["from_number"],
                to_id=r["to_id"],
                to_number=r["to_number"],
                context=r.get("context"),
                reference_text=r.get("reference_text")
            )
            for r in cross_refs
        ]

        max_depth = max(s["level"] for s in sections) if sections else 0

        return DocumentStructureResponse(
            document_id=document_id,
            title=sections[0]["title"] if sections else "Untitled",
            sections=section_nodes,
            definitions=definition_nodes,
            cross_references=cross_ref_models,
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
- content (the section text, abbreviated to 500 chars max)

Return as JSON array. Example:
[
  {"number": "1", "title": "Introduction", "level": 1, "start_position": 0, "content": "..."},
  {"number": "1.1", "title": "Purpose", "level": 2, "start_position": 150, "content": "..."}
]

Document:
{content}
"""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": prompt.format(content=content[:15000])  # Limit context
                }]
            )

            import json
            # Extract JSON from response
            text = response.content[0].text
            # Find JSON array in response
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                sections = json.loads(text[start:end])
            else:
                logger.warning("No JSON array found in LLM response, falling back to regex")
                return self._extract_sections_regex(content)

            # Add IDs
            for i, section in enumerate(sections):
                section["id"] = f"section_{i}"

            return sections

        except Exception as e:
            logger.error("LLM extraction failed, falling back to regex", error=str(e))
            return self._extract_sections_regex(content)

    def _extract_sections_regex(self, content: str) -> List[Dict[str, Any]]:
        """Fallback regex-based section extraction."""

        # Pattern matches common section numbering
        pattern = r'^((?:\d+\.)*\d+)\s+(.+?)(?:\n|$)'
        matches = list(re.finditer(pattern, content, re.MULTILINE))

        sections = []
        for i, match in enumerate(matches):
            number = match.group(1)
            title = match.group(2).strip()
            level = number.count('.') + 1

            # Extract content until next section
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()[:500]

            sections.append({
                "id": f"section_{i}",
                "number": number,
                "title": title,
                "level": level,
                "start_position": match.start(),
                "content": section_content
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
        seen_terms = set()

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                term = match.group(1).strip()
                definition = match.group(2).strip()

                # Avoid duplicates
                if term.lower() in seen_terms:
                    continue
                seen_terms.add(term.lower())

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
                    "context": ref.get("context", ""),
                    "ref_text": ref.get("reference_text", "")
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
                    "section_id": defn.get("section_id")
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

        # Find matching sections
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
            def_results = await self.neo4j.execute_query(
                def_query,
                {"section_id": primary_section["id"]}
            )
            definitions = [
                DefinedTermNode(term=d["term"], definition=d["definition"])
                for d in def_results
            ]

        # Build context chain
        context_chain = ["Document"]
        if parent_context:
            context_chain.append(f"Section {parent_context['number']}: {parent_context['title']}")
        context_chain.append(f"Section {primary_section['number']}: {primary_section['title']}")

        return SmartRetrievalResponse(
            primary_results=[
                SectionResult(
                    section=primary_section["number"],
                    title=primary_section["title"],
                    content=primary_section.get("content", ""),
                    relevance_score=0.95
                )
            ],
            parent_context=parent_context,
            cross_references=cross_refs,
            definitions=definitions,
            context_chain=context_chain
        )

    async def get_structure(self, document_id: str) -> DocumentStructureResponse:
        """Get existing document structure from Neo4j."""

        # Get sections
        sections_query = """
        MATCH (d:Document {id: $doc_id})-[:HAS_SECTION]->(s:Section)
        OPTIONAL MATCH (s)-[:HAS_SUBSECTION]->(child:Section)
        OPTIONAL MATCH (s)-[:REFERENCES]->(ref:Section)
        RETURN s, count(DISTINCT child) as child_count, count(DISTINCT ref) as ref_count
        ORDER BY s.number
        """
        sections_result = await self.neo4j.execute_query(
            sections_query,
            {"doc_id": document_id}
        )

        if not sections_result:
            raise ValueError(f"No structure found for document {document_id}")

        # Get definitions
        defs_query = """
        MATCH (dt:DefinedTerm {document_id: $doc_id})
        OPTIONAL MATCH (dt)-[:DEFINED_IN]->(s:Section)
        RETURN dt.term as term, dt.definition as definition, s.id as section_id
        """
        defs_result = await self.neo4j.execute_query(
            defs_query,
            {"doc_id": document_id}
        )

        # Get cross-references
        refs_query = """
        MATCH (d:Document {id: $doc_id})-[:HAS_SECTION]->(from:Section)-[r:REFERENCES]->(to:Section)
        RETURN from.id as from_id, from.number as from_number,
               to.id as to_id, to.number as to_number,
               r.context as context, r.reference_text as reference_text
        """
        refs_result = await self.neo4j.execute_query(
            refs_query,
            {"doc_id": document_id}
        )

        sections = [
            SectionNode(
                id=r["s"]["id"],
                number=r["s"]["number"],
                title=r["s"]["title"],
                level=r["s"]["level"],
                content_preview=r["s"].get("content", "")[:200],
                child_count=r["child_count"],
                reference_count=r["ref_count"]
            )
            for r in sections_result
        ]

        definitions = [
            DefinedTermNode(
                term=d["term"],
                definition=d["definition"],
                section_id=d.get("section_id")
            )
            for d in defs_result
        ]

        cross_refs = [
            CrossReference(
                from_id=r["from_id"],
                from_number=r["from_number"],
                to_id=r["to_id"],
                to_number=r["to_number"],
                context=r.get("context"),
                reference_text=r.get("reference_text")
            )
            for r in refs_result
        ]

        max_depth = max(s.level for s in sections) if sections else 0

        return DocumentStructureResponse(
            document_id=document_id,
            title=sections[0].title if sections else "Untitled",
            sections=sections,
            definitions=definitions,
            cross_references=cross_refs,
            structure_depth=max_depth
        )
```

---

## 5. Graph-Enhanced RAG Service

**File**: `app/services/graph_enhanced_rag_service.py`

```python
# app/services/graph_enhanced_rag_service.py

from typing import Dict, Any, List, Optional
import structlog
from app.services.neo4j_http_client import get_neo4j_http_client, Neo4jHTTPClient
from app.models.graph_agent import (
    GraphEnhancedRAGRequest,
    GraphEnhancedRAGResponse,
    GraphExpansionResult,
    ExpansionStats,
    SourceChunk,
    EntityNode,
    RelationshipPath
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
        rag_service: Optional[Any] = None  # Your existing RAG service
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

        if request.include_entity_context and entities:
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
            if c.relevance_score >= request.min_relevance_score
        ]

        # Deduplicate by ID
        seen_ids = set()
        unique_context = []
        for c in all_context:
            if c.id not in seen_ids:
                seen_ids.add(c.id)
                unique_context.append(c)

        # Generate answer (would use Claude or existing RAG pipeline)
        answer = await self._generate_answer(request.query, unique_context)

        # Build expansion stats
        expansion_stats = ExpansionStats(
            chunks_before_expansion=len(original_chunks),
            chunks_after_expansion=len(unique_context),
            entities_extracted=len(entities),
            relationships_traversed=len(relationship_paths)
        )

        return GraphEnhancedRAGResponse(
            answer=answer,
            sources=unique_context[:10],  # Top 10 sources
            graph_context=GraphExpansionResult(
                original_chunks=original_chunks,
                expanded_context=expanded_context,
                entities_found=entities,
                relationship_paths=relationship_paths,
                expansion_stats=expansion_stats
            ),
            confidence_score=self._calculate_confidence(unique_context),
            total_chunks_considered=len(unique_context)
        )

    async def _vector_search(
        self,
        query: str,
        top_k: int
    ) -> List[SourceChunk]:
        """Perform standard vector search."""
        if self.rag:
            # Use existing RAG service
            results = await self.rag.search(query=query, top_k=top_k)
            return [
                SourceChunk(
                    id=r.get("id", f"chunk_{i}"),
                    document_id=r.get("document_id"),
                    title=r.get("title"),
                    content=r.get("content", ""),
                    relevance_score=r.get("score", 0.8),
                    expansion_type="original"
                )
                for i, r in enumerate(results)
            ]

        # Fallback: return empty (would integrate with existing RAG infrastructure)
        logger.warning("No RAG service configured, returning empty results")
        return []

    async def _extract_entities(
        self,
        chunks: List[SourceChunk]
    ) -> List[EntityNode]:
        """Extract entities from retrieved chunks using Neo4j."""

        entities = []
        seen_ids = set()

        for chunk in chunks:
            if not chunk.id:
                continue

            query = """
            MATCH (c:DocumentChunk {id: $chunk_id})-[:MENTIONS]->(e:Entity)
            RETURN e.id as id, e.name as name, e.type as type,
                   count{(e)<-[:MENTIONS]-()} as mention_count
            """

            try:
                results = await self.neo4j.execute_query(
                    query,
                    {"chunk_id": chunk.id}
                )

                for r in results:
                    if r["id"] not in seen_ids:
                        seen_ids.add(r["id"])
                        entities.append(EntityNode(
                            id=r["id"],
                            name=r["name"],
                            type=r.get("type", "unknown"),
                            mention_count=r.get("mention_count", 0)
                        ))
            except Exception as e:
                logger.warning("Entity extraction failed for chunk", chunk_id=chunk.id, error=str(e))

        # Sort by mention count (most mentioned = most relevant)
        entities.sort(key=lambda x: x.mention_count, reverse=True)

        return entities[:20]  # Limit to top 20 entities

    async def _expand_via_graph(
        self,
        entities: List[EntityNode],
        depth: int
    ) -> Dict[str, Any]:
        """Expand context via Neo4j graph traversal."""

        expanded_docs = []
        paths = []

        for entity in entities[:10]:  # Limit to top 10 entities for expansion
            # Get related documents via graph traversal
            query = """
            MATCH (e:Entity {id: $entity_id})
            MATCH (e)<-[:MENTIONS]-(chunk:DocumentChunk)-[:BELONGS_TO]->(d:Document)

            // Get related entities (1-hop)
            OPTIONAL MATCH (e)-[:RELATED_TO]-(related:Entity)
            OPTIONAL MATCH (related)<-[:MENTIONS]-(rchunk:DocumentChunk)-[:BELONGS_TO]->(rd:Document)
            WHERE rd.id <> d.id

            RETURN d.id as doc_id, d.title as title, d.type as type,
                   chunk.content as content, chunk.id as chunk_id,
                   e.name as via_entity,
                   collect(DISTINCT {
                       entity: related.name,
                       document: rd.title,
                       document_id: rd.id
                   })[..5] as related_context
            LIMIT 5
            """

            try:
                results = await self.neo4j.execute_query(
                    query,
                    {"entity_id": entity.id}
                )

                for r in results:
                    expanded_docs.append(SourceChunk(
                        id=r["chunk_id"],
                        document_id=r["doc_id"],
                        title=r["title"],
                        content=r.get("content", ""),
                        relevance_score=0.7,  # Graph-expanded = slightly lower default
                        expansion_type="entity_link",
                        via_entity=r["via_entity"]
                    ))

                    # Record paths for transparency
                    for rc in r.get("related_context", []):
                        if rc.get("entity"):
                            paths.append(RelationshipPath(
                                from_entity=entity.name,
                                to_entity=rc["entity"],
                                relationship="RELATED_TO",
                                target_document=rc.get("document")
                            ))
            except Exception as e:
                logger.warning("Graph expansion failed for entity", entity_id=entity.id, error=str(e))

        return {"documents": expanded_docs, "paths": paths}

    async def _find_related_documents(
        self,
        original_chunks: List[SourceChunk],
        entities: List[EntityNode]
    ) -> List[SourceChunk]:
        """Find documents related to original results."""

        doc_ids = list(set(
            c.document_id for c in original_chunks
            if c.document_id
        ))

        if not doc_ids:
            return []

        query = """
        MATCH (d:Document)
        WHERE d.id IN $doc_ids
        MATCH (d)-[:RELATED_TO]-(related:Document)
        WHERE NOT related.id IN $doc_ids
        RETURN DISTINCT related.id as id, related.title as title,
               related.type as type, related.summary as summary
        LIMIT 10
        """

        try:
            results = await self.neo4j.execute_query(
                query,
                {"doc_ids": doc_ids}
            )

            return [
                SourceChunk(
                    id=r["id"],
                    document_id=r["id"],
                    title=r.get("title"),
                    content=r.get("summary", ""),
                    relevance_score=0.6,  # Related docs = lower relevance
                    expansion_type="related_document"
                )
                for r in results
            ]
        except Exception as e:
            logger.warning("Related document search failed", error=str(e))
            return []

    async def _generate_answer(
        self,
        query: str,
        context: List[SourceChunk]
    ) -> str:
        """Generate answer using context (would use Claude or existing pipeline)."""
        # This would integrate with existing answer generation
        # For now, return a placeholder
        if not context:
            return "No relevant information found."

        source_count = len(context)
        expanded_count = len([c for c in context if c.expansion_type != "original"])

        return f"Based on {source_count} sources ({expanded_count} from graph expansion)..."

    def _calculate_confidence(
        self,
        context: List[SourceChunk]
    ) -> float:
        """Calculate confidence score based on context quality."""
        if not context:
            return 0.0

        avg_relevance = sum(
            c.relevance_score for c in context
        ) / len(context)

        # Boost confidence if we have good coverage
        coverage_boost = min(len(context) / 10, 0.2)

        return min(avg_relevance + coverage_boost, 1.0)

    async def expand_chunks(
        self,
        chunk_ids: List[str],
        expansion_depth: int = 1
    ) -> GraphExpansionResult:
        """Expand specific chunks with graph context."""

        # Create dummy chunks for the expansion
        chunks = [
            SourceChunk(id=cid, content="", relevance_score=1.0, expansion_type="original")
            for cid in chunk_ids
        ]

        # Extract entities
        entities = await self._extract_entities(chunks)

        # Expand
        expanded = await self._expand_via_graph(entities, expansion_depth)

        return GraphExpansionResult(
            original_chunks=chunks,
            expanded_context=expanded["documents"],
            entities_found=entities,
            relationship_paths=expanded["paths"],
            expansion_stats=ExpansionStats(
                chunks_before_expansion=len(chunk_ids),
                chunks_after_expansion=len(chunk_ids) + len(expanded["documents"]),
                entities_extracted=len(entities),
                relationships_traversed=len(expanded["paths"])
            )
        )
```

---

## 6. API Routes

**File**: `app/routes/graph_agent.py`

```python
# app/routes/graph_agent.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from app.models.graph_agent import (
    Customer360Request, Customer360Response,
    DocumentStructureRequest, DocumentStructureResponse,
    SmartRetrievalRequest, SmartRetrievalResponse,
    GraphEnhancedRAGRequest, GraphEnhancedRAGResponse,
    GraphExpansionResult, SimilarCustomer, GraphHealthResponse
)
from app.services.customer360_service import Customer360Service
from app.services.document_structure_service import DocumentStructureService
from app.services.graph_enhanced_rag_service import GraphEnhancedRAGService
from app.services.neo4j_http_client import get_neo4j_http_client
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/graph", tags=["Graph Agent"])


# Dependency injection
def get_customer360_service() -> Customer360Service:
    return Customer360Service()


def get_document_structure_service() -> DocumentStructureService:
    return DocumentStructureService()


def get_graph_enhanced_rag_service() -> GraphEnhancedRAGService:
    return GraphEnhancedRAGService()


# Customer 360 Endpoints
@router.post("/customer360/query", response_model=Customer360Response)
async def customer_360_query(
    request: Customer360Request,
    user=Depends(get_current_user),
    service: Customer360Service = Depends(get_customer360_service)
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
    service: Customer360Service = Depends(get_customer360_service)
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


@router.get("/customer360/{customer_id}/similar", response_model=List[SimilarCustomer])
async def find_similar_customers(
    customer_id: str,
    limit: int = Query(5, ge=1, le=20),
    user=Depends(get_current_user),
    service: Customer360Service = Depends(get_customer360_service)
):
    """Find customers similar to the specified customer."""
    return await service.find_similar_customers(customer_id, limit)


# Document Structure Endpoints
@router.post("/document-structure/extract", response_model=DocumentStructureResponse)
async def extract_document_structure(
    document_id: str,
    document_content: str,
    request: DocumentStructureRequest = DocumentStructureRequest(),
    user=Depends(get_current_user),
    service: DocumentStructureService = Depends(get_document_structure_service)
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
    service: DocumentStructureService = Depends(get_document_structure_service)
):
    """Get the extracted structure graph for a document."""
    try:
        return await service.get_structure(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/document-structure/smart-retrieve", response_model=SmartRetrievalResponse)
async def smart_retrieve(
    request: SmartRetrievalRequest,
    user=Depends(get_current_user),
    service: DocumentStructureService = Depends(get_document_structure_service)
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
    service: GraphEnhancedRAGService = Depends(get_graph_enhanced_rag_service)
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


@router.post("/enhanced-rag/expand", response_model=GraphExpansionResult)
async def expand_with_graph(
    chunk_ids: List[str],
    expansion_depth: int = Query(1, ge=1, le=3),
    user=Depends(get_current_user),
    service: GraphEnhancedRAGService = Depends(get_graph_enhanced_rag_service)
):
    """Expand given chunks with graph context."""
    return await service.expand_chunks(chunk_ids, expansion_depth)


# Health Check
@router.get("/health", response_model=GraphHealthResponse)
async def graph_health():
    """Check Neo4j connection and graph capabilities."""
    client = get_neo4j_http_client()
    is_healthy = await client.health_check()

    return GraphHealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        neo4j_connected=is_healthy,
        capabilities={
            "customer_360": is_healthy,
            "document_structure": is_healthy,
            "graph_enhanced_rag": is_healthy
        }
    )
```

---

## 7. Neo4j Schema Migrations

### 7.1 Customer 360 Schema

**File**: `migrations/neo4j/001_customer360_schema.cypher`

```cypher
// Customer 360 Schema Migration
// Run: cat migrations/neo4j/001_customer360_schema.cypher | cypher-shell -u neo4j -p <password>

// Customer node constraints and indexes
CREATE CONSTRAINT customer_id IF NOT EXISTS
FOR (c:Customer) REQUIRE c.id IS UNIQUE;

CREATE INDEX customer_name IF NOT EXISTS
FOR (c:Customer) ON (c.name);

CREATE INDEX customer_type IF NOT EXISTS
FOR (c:Customer) ON (c.type);

CREATE INDEX customer_industry IF NOT EXISTS
FOR (c:Customer) ON (c.industry);

// Ticket node constraints and indexes
CREATE CONSTRAINT ticket_id IF NOT EXISTS
FOR (t:Ticket) REQUIRE t.id IS UNIQUE;

CREATE INDEX ticket_customer IF NOT EXISTS
FOR (t:Ticket) ON (t.customer_id);

CREATE INDEX ticket_status IF NOT EXISTS
FOR (t:Ticket) ON (t.status);

CREATE INDEX ticket_priority IF NOT EXISTS
FOR (t:Ticket) ON (t.priority);

// Order node constraints and indexes
CREATE CONSTRAINT order_id IF NOT EXISTS
FOR (o:Order) REQUIRE o.id IS UNIQUE;

CREATE INDEX order_customer IF NOT EXISTS
FOR (o:Order) ON (o.customer_id);

CREATE INDEX order_status IF NOT EXISTS
FOR (o:Order) ON (o.status);

// Interaction node constraints and indexes
CREATE CONSTRAINT interaction_id IF NOT EXISTS
FOR (i:Interaction) REQUIRE i.id IS UNIQUE;

CREATE INDEX interaction_customer IF NOT EXISTS
FOR (i:Interaction) ON (i.customer_id);

CREATE INDEX interaction_type IF NOT EXISTS
FOR (i:Interaction) ON (i.type);

// Product node constraints and indexes
CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

CREATE INDEX product_name IF NOT EXISTS
FOR (p:Product) ON (p.name);

CREATE INDEX product_category IF NOT EXISTS
FOR (p:Product) ON (p.category);

// Relationship indexes for fast traversal
CREATE INDEX rel_has_document IF NOT EXISTS
FOR ()-[r:HAS_DOCUMENT]-() ON (r.created_at);

CREATE INDEX rel_has_ticket IF NOT EXISTS
FOR ()-[r:HAS_TICKET]-() ON (r.created_at);

CREATE INDEX rel_placed_order IF NOT EXISTS
FOR ()-[r:PLACED_ORDER]-() ON (r.created_at);

CREATE INDEX rel_had_interaction IF NOT EXISTS
FOR ()-[r:HAD_INTERACTION]-() ON (r.created_at);
```

### 7.2 Document Structure Schema

**File**: `migrations/neo4j/002_document_structure_schema.cypher`

```cypher
// Document Structure Schema Migration
// Run: cat migrations/neo4j/002_document_structure_schema.cypher | cypher-shell -u neo4j -p <password>

// Section node constraints and indexes
CREATE CONSTRAINT section_id IF NOT EXISTS
FOR (s:Section) REQUIRE s.id IS UNIQUE;

CREATE INDEX section_document IF NOT EXISTS
FOR (s:Section) ON (s.document_id);

CREATE INDEX section_number IF NOT EXISTS
FOR (s:Section) ON (s.number);

CREATE INDEX section_level IF NOT EXISTS
FOR (s:Section) ON (s.level);

// DefinedTerm node constraints and indexes
CREATE CONSTRAINT defined_term_id IF NOT EXISTS
FOR (dt:DefinedTerm) REQUIRE dt.id IS UNIQUE;

CREATE INDEX defined_term_document IF NOT EXISTS
FOR (dt:DefinedTerm) ON (dt.document_id);

CREATE INDEX defined_term_term IF NOT EXISTS
FOR (dt:DefinedTerm) ON (dt.term);

// Citation node (for external references)
CREATE CONSTRAINT citation_id IF NOT EXISTS
FOR (c:Citation) REQUIRE c.id IS UNIQUE;

// Relationship indexes
CREATE INDEX rel_has_section IF NOT EXISTS
FOR ()-[r:HAS_SECTION]-() ON (r.created_at);

CREATE INDEX rel_has_subsection IF NOT EXISTS
FOR ()-[r:HAS_SUBSECTION]-() ON (r.created_at);

CREATE INDEX rel_references IF NOT EXISTS
FOR ()-[r:REFERENCES]-() ON (r.created_at);

CREATE INDEX rel_defined_in IF NOT EXISTS
FOR ()-[r:DEFINED_IN]-() ON (r.created_at);
```

### 7.3 Entity Relationships Schema

**File**: `migrations/neo4j/003_entity_relationships.cypher`

```cypher
// Entity Relationships Schema Migration
// Run: cat migrations/neo4j/003_entity_relationships.cypher | cypher-shell -u neo4j -p <password>

// Entity node constraints and indexes
CREATE CONSTRAINT entity_id IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

CREATE INDEX entity_name IF NOT EXISTS
FOR (e:Entity) ON (e.name);

CREATE INDEX entity_type IF NOT EXISTS
FOR (e:Entity) ON (e.type);

CREATE INDEX entity_normalized_name IF NOT EXISTS
FOR (e:Entity) ON (e.normalized_name);

// DocumentChunk node (for RAG integration)
CREATE CONSTRAINT chunk_id IF NOT EXISTS
FOR (c:DocumentChunk) REQUIRE c.id IS UNIQUE;

CREATE INDEX chunk_document IF NOT EXISTS
FOR (c:DocumentChunk) ON (c.document_id);

// Relationship indexes for graph expansion
CREATE INDEX rel_mentions IF NOT EXISTS
FOR ()-[r:MENTIONS]-() ON (r.created_at);

CREATE INDEX rel_related_to IF NOT EXISTS
FOR ()-[r:RELATED_TO]-() ON (r.weight);

CREATE INDEX rel_belongs_to IF NOT EXISTS
FOR ()-[r:BELONGS_TO]-() ON (r.created_at);
```

---

## Implementation Notes

### Integration with Existing Empire Code

1. **Add to `app/main.py`**:
   ```python
   from app.routes.graph_agent import router as graph_agent_router
   app.include_router(graph_agent_router)
   ```

2. **Add to `requirements.txt`**:
   ```
   httpx>=0.25.0
   ```

3. **Cache Service Integration**:
   - The services expect an optional `CacheService` with `get(key)` and `set(key, value, ttl)` methods
   - Use your existing Redis/cache implementation

4. **RAG Service Integration**:
   - `GraphEnhancedRAGService` expects an optional RAG service with a `search(query, top_k)` method
   - Connect to your existing RAG implementation

5. **Auth Integration**:
   - Routes use `get_current_user` dependency
   - Ensure this matches your existing auth pattern

### Performance Considerations

- All services use connection pooling (httpx limits)
- Caching enabled by default (5-minute TTL)
- Query depth limits prevent runaway traversals
- Batch operations available for bulk processing
