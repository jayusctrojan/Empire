# Task ID: 193

**Title:** Implement Retrieval Executor Service Integrations

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Complete the Retrieval Executor service by integrating NLQ service for natural language queries, Neo4j service for graph retrieval, and implementing external API retrieval.

**Details:**

This task involves completing 3 TODOs in app/services/task_executors/retrieval_executor.py:

1. Integrate NLQ service for natural language queries:
```python
class RetrievalExecutor:
    def __init__(self, db_client=None, neo4j_client=None, nlq_service=None):
        self.db_client = db_client or get_supabase_client()
        self.neo4j_client = neo4j_client or Neo4jClient()
        self.nlq_service = nlq_service or NLQService()
    
    def execute_natural_language_query(self, query, context=None):
        """Execute a natural language query against the database"""
        try:
            # Use NLQ service to translate natural language to SQL
            sql_query = self.nlq_service.translate_to_sql(query, context)
            
            # Log the generated SQL for debugging
            logger.debug(f"Generated SQL: {sql_query}")
            
            # Execute the SQL query
            result = self.db_client.rpc("execute_raw_query", {"query": sql_query}).execute()
            
            # Format and return results
            return {
                "success": True,
                "query": query,
                "sql": sql_query,
                "results": result.data
            }
        except Exception as e:
            logger.error(f"NLQ query failed: {str(e)}")
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }
```

2. Integrate Neo4j service for graph retrieval:
```python
    def execute_graph_query(self, query_type, parameters):
        """Execute a graph query against Neo4j"""
        try:
            # Map query types to Neo4j Cypher queries
            query_templates = {
                "related_entities": """
                MATCH (n {id: $entity_id})-[r]-(m)
                RETURN n, r, m
                LIMIT $limit
                """,
                "shortest_path": """
                MATCH p=shortestPath((a {id: $source_id})-[*]-(b {id: $target_id}))
                RETURN p
                """,
                "entity_search": """
                MATCH (n)
                WHERE n.name CONTAINS $search_term
                RETURN n
                LIMIT $limit
                """
            }
            
            # Get the appropriate query template
            if query_type not in query_templates:
                raise ValueError(f"Unknown graph query type: {query_type}")
                
            cypher_query = query_templates[query_type]
            
            # Execute the query
            result = self.neo4j_client.execute_query(cypher_query, parameters)
            
            # Process and format the results
            formatted_result = self._format_graph_results(result, query_type)
            
            return {
                "success": True,
                "query_type": query_type,
                "results": formatted_result
            }
        except Exception as e:
            logger.error(f"Graph query failed: {str(e)}")
            return {
                "success": False,
                "query_type": query_type,
                "error": str(e)
            }
            
    def _format_graph_results(self, result, query_type):
        """Format Neo4j results based on query type"""
        if query_type == "related_entities":
            return [{
                "source": self._node_to_dict(record["n"]),
                "relationship": self._rel_to_dict(record["r"]),
                "target": self._node_to_dict(record["m"])
            } for record in result]
        elif query_type == "shortest_path":
            # Extract nodes and relationships from path
            path = result[0]["p"]
            return {
                "nodes": [self._node_to_dict(node) for node in path.nodes],
                "relationships": [self._rel_to_dict(rel) for rel in path.relationships]
            }
        elif query_type == "entity_search":
            return [self._node_to_dict(record["n"]) for record in result]
        
        return result
        
    def _node_to_dict(self, node):
        """Convert Neo4j node to dictionary"""
        return {
            "id": node.id,
            "labels": list(node.labels),
            "properties": dict(node)
        }
        
    def _rel_to_dict(self, relationship):
        """Convert Neo4j relationship to dictionary"""
        return {
            "id": relationship.id,
            "type": relationship.type,
            "properties": dict(relationship)
        }
```

3. Implement external API retrieval:
```python
    def execute_api_retrieval(self, api_config, parameters):
        """Execute retrieval from external API"""
        try:
            # Get API configuration
            if isinstance(api_config, str):
                # Look up predefined API config by name
                config = self.db_client.table("api_configs").select("*").eq("name", api_config).single().execute()
                if not config.data:
                    raise ValueError(f"API configuration not found: {api_config}")
                api_config = config.data
            
            # Extract API details
            url = api_config["base_url"]
            method = api_config.get("method", "GET").upper()
            headers = api_config.get("headers", {})
            auth = None
            
            # Handle authentication if specified
            if "auth" in api_config:
                auth_type = api_config["auth"].get("type")
                if auth_type == "basic":
                    auth = (api_config["auth"]["username"], api_config["auth"]["password"])
                elif auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {api_config['auth']['token']}"
            
            # Replace URL parameters
            for key, value in parameters.items():
                placeholder = f"{{{key}}}"
                if placeholder in url:
                    url = url.replace(placeholder, str(value))
            
            # Make the request
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                auth=auth,
                params=parameters if method == "GET" else None,
                json=parameters if method != "GET" else None,
                timeout=30
            )
            
            # Check for successful response
            response.raise_for_status()
            
            # Parse response based on content type
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                result = response.json()
            else:
                result = response.text
            
            return {
                "success": True,
                "api": api_config.get("name", "custom"),
                "status_code": response.status_code,
                "results": result
            }
        except requests.RequestException as e:
            logger.error(f"API retrieval failed: {str(e)}")
            return {
                "success": False,
                "api": api_config.get("name", "custom"),
                "error": str(e),
                "status_code": e.response.status_code if hasattr(e, "response") else None
            }
        except Exception as e:
            logger.error(f"API retrieval failed: {str(e)}")
            return {
                "success": False,
                "api": api_config.get("name", "custom"),
                "error": str(e)
            }
```

**Test Strategy:**

1. Unit tests for each retrieval method with mocked dependencies
   - Test NLQ service with various natural language queries
   - Test Neo4j integration with different query types
   - Test API retrieval with various configurations
2. Integration tests with actual services in test environment
3. Test cases:
   - NLQ: Test translation to SQL and execution
   - Graph: Test related entities, shortest path, and entity search
   - API: Test with different HTTP methods, auth types, and response formats
4. Error handling tests:
   - Invalid queries
   - Neo4j connection failures
   - API timeouts and error responses
5. Performance tests for complex queries
