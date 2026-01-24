# Task ID: 104

**Title:** Implement Customer 360 Service

**Status:** done

**Dependencies:** 101 ✓, 102 ✓, 103 ✓

**Priority:** high

**Description:** Create the Customer 360 Service that provides unified customer views by traversing the Neo4j graph to consolidate data from multiple sources.

**Details:**

Implement the Customer360Service class in app/services/customer360_service.py with the following features:

1. Query parser for customer-related natural language queries
2. Multi-hop graph traversal to collect customer data
3. Result aggregation and formatting
4. Similar customer detection

The service should use the Neo4jHTTPClient for efficient graph queries and implement the following methods:

```python
from typing import Dict, List, Optional, Any
from app.services.neo4j_http_client import Neo4jHTTPClient
from app.models.graph_agent import Customer360Request, Customer360Response, CustomerNode

class Customer360Service:
    def __init__(self, neo4j_client: Neo4jHTTPClient):
        self.neo4j_client = neo4j_client
    
    async def process_customer_query(self, request: Customer360Request) -> Customer360Response:
        # Parse natural language query to identify customer and query intent
        # Execute appropriate graph traversal
        # Format results into Customer360Response
        pass
    
    async def get_customer_by_id(self, customer_id: str, include_documents: bool = True, 
                               include_tickets: bool = True, include_orders: bool = True,
                               include_interactions: bool = True) -> Customer360Response:
        # Direct lookup by customer ID with configurable related data
        pass
    
    async def find_similar_customers(self, customer_id: str, limit: int = 5) -> List[CustomerNode]:
        # Find customers with similar profiles/behaviors
        pass
    
    async def _execute_customer_traversal(self, cypher_query: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Execute graph traversal and process results
        pass
```

Implement Cypher queries for customer data retrieval as shown in the PRD's Cypher Query Patterns section.

**Test Strategy:**

1. Unit tests with mocked Neo4j responses
2. Integration tests with test customer data
3. Test natural language query parsing with various customer queries
4. Test multi-hop traversal with different depths
5. Test result aggregation with complex customer data
6. Performance testing with large customer datasets
