# app/services/customer360_service.py
"""
Customer 360 Service for unified customer views.

Task 104: Graph Agent - Customer 360 Service
Feature: 005-graph-agent

Provides consolidated customer data from multiple sources:
- Documents (contracts, agreements)
- Support tickets
- Orders/transactions
- Interactions (emails, calls, meetings)
- Products/services

Reference: AI Automators Customer360 GraphAgent Blueprint
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import structlog

from app.services.neo4j_http_client import (
    Neo4jHTTPClient,
    get_neo4j_http_client,
    Neo4jQueryError,
    Neo4jConnectionError,
)
from app.models.graph_agent import (
    Customer360Request,
    Customer360Response,
    CustomerNode,
    CustomerType,
    DocumentNode,
    TicketNode,
    TicketStatus,
    TicketPriority,
    OrderNode,
    OrderStatus,
    InteractionNode,
    InteractionType,
    ProductNode,
    SimilarCustomer,
    TraversalDepth,
)

logger = structlog.get_logger()


class CustomerNotFoundError(Exception):
    """Raised when a customer cannot be found."""
    pass


class CustomerQueryError(Exception):
    """Raised when a customer query fails."""
    pass


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
        cache_service: Optional[Any] = None,
    ):
        """
        Initialize Customer 360 Service.

        Args:
            neo4j_client: Neo4j HTTP client instance. Uses singleton if not provided.
            cache_service: Optional cache service for result caching.
        """
        self.neo4j = neo4j_client or get_neo4j_http_client()
        self.cache = cache_service

        logger.info("Customer360Service initialized")

    async def get_customer_360(
        self, request: Customer360Request
    ) -> Customer360Response:
        """
        Get unified customer view.

        If customer_id provided, use directly.
        Otherwise, extract customer from natural language query.

        Args:
            request: Customer360Request with query or customer_id

        Returns:
            Customer360Response with consolidated customer data

        Raises:
            CustomerNotFoundError: If customer cannot be found
            CustomerQueryError: If query execution fails
        """
        customer_id = request.customer_id

        # If no customer_id, try to extract from query
        if not customer_id and request.query:
            customer_id = await self._extract_customer_from_query(request.query)

        if not customer_id:
            raise CustomerNotFoundError("Could not identify customer from query")

        # Check cache
        cache_key = f"customer360:{customer_id}"
        if self.cache:
            try:
                cached = await self.cache.get(cache_key)
                if cached:
                    logger.info("Customer 360 cache hit", customer_id=customer_id)
                    return Customer360Response(**cached)
            except Exception as e:
                logger.warning("Cache lookup failed", error=str(e))

        try:
            # Build and execute query
            result = await self._execute_customer_360_query(
                customer_id=customer_id,
                include_documents=request.include_documents,
                include_tickets=request.include_tickets,
                include_orders=request.include_orders,
                include_interactions=request.include_interactions,
                max_items=request.max_items_per_category,
                traversal_depth=request.traversal_depth,
            )

            # Generate summary
            result["summary"] = self._generate_summary(result)

            response = Customer360Response(**result)

            # Cache result
            if self.cache:
                try:
                    await self.cache.set(
                        cache_key, response.model_dump(), ttl=self.CACHE_TTL
                    )
                except Exception as e:
                    logger.warning("Cache set failed", error=str(e))

            logger.info(
                "Customer 360 retrieved",
                customer_id=customer_id,
                documents=len(response.documents),
                tickets=len(response.tickets),
                orders=len(response.orders),
                interactions=len(response.interactions),
            )

            return response

        except Neo4jQueryError as e:
            logger.error("Neo4j query failed", error=str(e), customer_id=customer_id)
            raise CustomerQueryError(f"Query failed: {e}")
        except Neo4jConnectionError as e:
            logger.error("Neo4j connection failed", error=str(e))
            raise CustomerQueryError(f"Connection failed: {e}")

    async def get_customer_by_id(self, customer_id: str) -> CustomerNode:
        """
        Get customer node by ID.

        Args:
            customer_id: Customer identifier

        Returns:
            CustomerNode with customer data

        Raises:
            CustomerNotFoundError: If customer not found
        """
        query = """
        MATCH (c:Customer {id: $customer_id})
        RETURN c.id AS id,
               c.name AS name,
               c.type AS type,
               c.industry AS industry,
               c.created_at AS created_at,
               c.metadata AS metadata
        """

        try:
            results = await self.neo4j.execute_query(
                query, {"customer_id": customer_id}
            )

            if not results:
                raise CustomerNotFoundError(f"Customer {customer_id} not found")

            row = results[0]
            return CustomerNode(
                id=row["id"],
                name=row["name"],
                type=CustomerType(row.get("type", "unknown")),
                industry=row.get("industry"),
                created_at=row.get("created_at"),
                metadata=row.get("metadata") or {},
            )
        except Neo4jQueryError as e:
            logger.error("Failed to get customer", customer_id=customer_id, error=str(e))
            raise CustomerNotFoundError(f"Failed to retrieve customer: {e}")

    async def find_similar_customers(
        self, customer_id: str, limit: int = 5
    ) -> List[SimilarCustomer]:
        """
        Find customers with similar profiles based on graph relationships.

        Similarity is based on:
        - Shared products/services
        - Same industry
        - Similar relationship patterns

        Args:
            customer_id: Source customer ID
            limit: Maximum number of similar customers to return

        Returns:
            List of SimilarCustomer objects
        """
        query = """
        MATCH (c:Customer {id: $customer_id})

        // Find customers with similar products
        OPTIONAL MATCH (c)-[:USES_PRODUCT]->(p:Product)<-[:USES_PRODUCT]-(similar:Customer)
        WHERE similar.id <> c.id

        WITH c, similar, count(DISTINCT p) AS shared_products

        WHERE similar IS NOT NULL

        // Calculate similarity score
        WITH similar,
             shared_products,
             CASE WHEN similar.industry = c.industry THEN 1 ELSE 0 END AS same_industry,
             c.industry AS source_industry

        RETURN similar.id AS id,
               similar.name AS name,
               similar.type AS type,
               similar.industry AS industry,
               shared_products,
               same_industry = 1 AS same_industry,
               (shared_products * 0.7 + same_industry * 0.3) AS similarity_score
        ORDER BY similarity_score DESC, shared_products DESC
        LIMIT $limit
        """

        try:
            results = await self.neo4j.execute_query(
                query, {"customer_id": customer_id, "limit": limit}
            )

            return [
                SimilarCustomer(
                    id=row["id"],
                    name=row["name"],
                    type=CustomerType(row.get("type", "unknown")) if row.get("type") else None,
                    industry=row.get("industry"),
                    shared_products=row.get("shared_products", 0),
                    same_industry=row.get("same_industry", False),
                    similarity_score=min(1.0, row.get("similarity_score", 0) / 10),
                )
                for row in results
            ]
        except Neo4jQueryError as e:
            logger.error("Failed to find similar customers", error=str(e))
            return []

    async def search_customers(
        self, search_term: str, limit: int = 10
    ) -> List[CustomerNode]:
        """
        Search customers by name.

        Args:
            search_term: Search term to match against customer names
            limit: Maximum results to return

        Returns:
            List of matching CustomerNode objects
        """
        query = """
        MATCH (c:Customer)
        WHERE toLower(c.name) CONTAINS toLower($search_term)
        RETURN c.id AS id,
               c.name AS name,
               c.type AS type,
               c.industry AS industry,
               c.created_at AS created_at
        ORDER BY c.name
        LIMIT $limit
        """

        try:
            results = await self.neo4j.execute_query(
                query, {"search_term": search_term, "limit": limit}
            )

            return [
                CustomerNode(
                    id=row["id"],
                    name=row["name"],
                    type=CustomerType(row.get("type", "unknown")),
                    industry=row.get("industry"),
                    created_at=row.get("created_at"),
                )
                for row in results
            ]
        except Neo4jQueryError as e:
            logger.error("Customer search failed", error=str(e))
            return []

    async def _execute_customer_360_query(
        self,
        customer_id: str,
        include_documents: bool,
        include_tickets: bool,
        include_orders: bool,
        include_interactions: bool,
        max_items: int,
        traversal_depth: TraversalDepth,
    ) -> Dict[str, Any]:
        """Execute the Customer 360 graph query."""

        # Build query with parameterized max items
        query = f"""
        MATCH (c:Customer {{id: $customer_id}})

        // Documents
        OPTIONAL MATCH (c)-[:HAS_DOCUMENT]->(d:Document)
        WITH c, collect(DISTINCT d)[..{max_items}] AS documents

        // Tickets
        OPTIONAL MATCH (c)-[:HAS_TICKET]->(t:Ticket)
        WITH c, documents, collect(DISTINCT t)[..{max_items}] AS tickets

        // Orders
        OPTIONAL MATCH (c)-[:PLACED_ORDER]->(o:Order)
        WITH c, documents, tickets, collect(DISTINCT o)[..{max_items}] AS orders

        // Interactions
        OPTIONAL MATCH (c)-[:HAD_INTERACTION]->(i:Interaction)
        WITH c, documents, tickets, orders, collect(DISTINCT i)[..{max_items}] AS interactions

        // Products
        OPTIONAL MATCH (c)-[:USES_PRODUCT]->(p:Product)
        WITH c, documents, tickets, orders, interactions, collect(DISTINCT p) AS products

        // Count all relationships
        OPTIONAL MATCH (c)-[r]-()

        RETURN c AS customer,
               documents,
               tickets,
               orders,
               interactions,
               products,
               count(DISTINCT r) AS relationship_count
        """

        results = await self.neo4j.execute_query(query, {"customer_id": customer_id})

        if not results:
            raise CustomerNotFoundError(f"Customer {customer_id} not found")

        row = results[0]
        customer_data = row.get("customer", {})

        # Parse customer node
        customer = CustomerNode(
            id=customer_data.get("id", customer_id),
            name=customer_data.get("name", "Unknown"),
            type=CustomerType(customer_data.get("type", "unknown")),
            industry=customer_data.get("industry"),
            created_at=customer_data.get("created_at"),
            metadata=customer_data.get("metadata") or {},
        )

        # Parse documents
        documents = []
        if include_documents:
            for doc in row.get("documents") or []:
                if doc:
                    documents.append(
                        DocumentNode(
                            id=doc.get("id", ""),
                            title=doc.get("title", "Untitled"),
                            type=doc.get("type"),
                            created_at=doc.get("created_at"),
                            status=doc.get("status"),
                        )
                    )

        # Parse tickets
        tickets = []
        if include_tickets:
            for ticket in row.get("tickets") or []:
                if ticket:
                    tickets.append(
                        TicketNode(
                            id=ticket.get("id", ""),
                            customer_id=customer_id,
                            subject=ticket.get("subject", "No subject"),
                            status=TicketStatus(ticket.get("status", "open")),
                            priority=TicketPriority(ticket.get("priority", "medium")),
                            created_at=ticket.get("created_at"),
                            resolved_at=ticket.get("resolved_at"),
                            description=ticket.get("description"),
                        )
                    )

        # Parse orders
        orders = []
        if include_orders:
            for order in row.get("orders") or []:
                if order:
                    orders.append(
                        OrderNode(
                            id=order.get("id", ""),
                            customer_id=customer_id,
                            status=OrderStatus(order.get("status", "pending")),
                            total_amount=order.get("total_amount"),
                            currency=order.get("currency", "USD"),
                            created_at=order.get("created_at"),
                            items=order.get("items") or [],
                        )
                    )

        # Parse interactions
        interactions = []
        if include_interactions:
            for interaction in row.get("interactions") or []:
                if interaction:
                    interactions.append(
                        InteractionNode(
                            id=interaction.get("id", ""),
                            customer_id=customer_id,
                            type=InteractionType(interaction.get("type", "other")),
                            subject=interaction.get("subject"),
                            summary=interaction.get("summary"),
                            created_at=interaction.get("created_at"),
                            duration_minutes=interaction.get("duration_minutes"),
                            sentiment=interaction.get("sentiment"),
                        )
                    )

        # Parse products
        products = []
        for product in row.get("products") or []:
            if product:
                products.append(
                    ProductNode(
                        id=product.get("id", ""),
                        name=product.get("name", "Unknown"),
                        category=product.get("category"),
                        description=product.get("description"),
                    )
                )

        return {
            "customer": customer,
            "documents": documents,
            "tickets": tickets,
            "orders": orders,
            "interactions": interactions,
            "products": products,
            "relationship_count": row.get("relationship_count", 0),
        }

    async def _extract_customer_from_query(self, query: str) -> Optional[str]:
        """
        Extract customer ID or name from natural language query.

        Uses pattern matching to identify potential customer names,
        then searches the graph for matches.

        Args:
            query: Natural language query string

        Returns:
            Customer ID if found, None otherwise
        """
        if not query:
            return None

        search_query = """
        MATCH (c:Customer)
        WHERE toLower(c.name) CONTAINS toLower($search_term)
        RETURN c.id AS id, c.name AS name
        LIMIT 1
        """

        # Extract potential customer names from query
        # Pattern 1: Capitalized words/phrases (company names)
        potential_names = re.findall(
            r"[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*(?:\s+(?:Corp|Inc|LLC|Ltd|Company|Co))?",
            query,
        )

        # Pattern 2: Quoted strings
        quoted_names = re.findall(r'"([^"]+)"', query)
        quoted_names.extend(re.findall(r"'([^']+)'", query))

        # Combine and deduplicate
        all_names = list(set(potential_names + quoted_names))

        for name in all_names:
            name = name.strip()
            if len(name) < 2:
                continue

            try:
                results = await self.neo4j.execute_query(
                    search_query, {"search_term": name}
                )
                if results:
                    logger.info(
                        "Customer extracted from query",
                        search_term=name,
                        found_id=results[0]["id"],
                    )
                    return results[0]["id"]
            except Neo4jQueryError:
                continue

        return None

    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """
        Generate a natural language summary of the customer.

        Args:
            result: Customer 360 query result

        Returns:
            Human-readable summary string
        """
        customer = result["customer"]

        # Build description
        type_str = customer.type.value if hasattr(customer.type, "value") else str(customer.type)
        parts = [f"{customer.name} is a {type_str} customer"]

        if customer.industry:
            parts[0] += f" in the {customer.industry} industry"

        parts[0] += "."

        # Count items
        doc_count = len(result.get("documents", []))
        ticket_count = len(result.get("tickets", []))
        order_count = len(result.get("orders", []))
        interaction_count = len(result.get("interactions", []))
        product_count = len(result.get("products", []))

        # Build item summaries
        item_parts = []
        if doc_count:
            item_parts.append(f"{doc_count} document{'s' if doc_count != 1 else ''}")
        if ticket_count:
            item_parts.append(f"{ticket_count} support ticket{'s' if ticket_count != 1 else ''}")
        if order_count:
            item_parts.append(f"{order_count} order{'s' if order_count != 1 else ''}")
        if interaction_count:
            item_parts.append(f"{interaction_count} interaction{'s' if interaction_count != 1 else ''}")
        if product_count:
            item_parts.append(f"{product_count} product{'s' if product_count != 1 else ''}")

        if item_parts:
            if len(item_parts) == 1:
                parts.append(f"They have {item_parts[0]}.")
            elif len(item_parts) == 2:
                parts.append(f"They have {item_parts[0]} and {item_parts[1]}.")
            else:
                parts.append(
                    f"They have {', '.join(item_parts[:-1])}, and {item_parts[-1]}."
                )
        else:
            parts.append("No associated data found.")

        return " ".join(parts)


# Singleton instance for dependency injection
_service: Optional[Customer360Service] = None


def get_customer360_service() -> Customer360Service:
    """
    Get or create singleton Customer360Service.

    Use this for FastAPI dependency injection:

        @app.get("/api/graph/customer360/{customer_id}")
        async def get_customer(
            customer_id: str,
            service: Customer360Service = Depends(get_customer360_service)
        ):
            return await service.get_customer_by_id(customer_id)
    """
    global _service
    if _service is None:
        _service = Customer360Service()
    return _service


async def close_customer360_service():
    """Close the singleton service. Call on application shutdown."""
    global _service
    _service = None
