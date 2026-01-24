# Task ID: 182

**Title:** Implement Retrieval Executor Service Integrations

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Complete the Retrieval Executor service by integrating NLQ service for natural language queries, Neo4j service for graph retrieval, and implementing external API retrieval.

**Details:**

In `app/services/task_executors/retrieval_executor.py`, implement the following TODOs:

1. Integrate NLQ service for natural language queries:
```python
def execute_nlq_query(self, query, context=None):
    """Execute a natural language query against the database."""
    # Initialize NLQ service
    nlq_service = NLQService()
    
    # Convert natural language to SQL
    sql_query = nlq_service.translate_to_sql(
        query=query,
        context=context or {},
        schema=self.db_schema
    )
    
    # Log the generated SQL for debugging
    logger.debug(f"Generated SQL: {sql_query}")
    
    # Execute the SQL query
    try:
        results = self.db.execute_raw(sql_query)
        return {
            "success": True,
            "results": results,
            "query": query,
            "sql": sql_query
        }
    except Exception as e:
        logger.error(f"Error executing NLQ query: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "sql": sql_query
        }
```

2. Integrate Neo4j service for graph retrieval:
```python
def execute_graph_query(self, query, params=None):
    """Execute a query against the Neo4j knowledge graph."""
    # Initialize Neo4j client
    neo4j_client = Neo4jClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    
    # Execute Cypher query
    try:
        results = neo4j_client.execute_query(
            query=query,
            params=params or {}
        )
        
        # Process results into a more usable format
        processed_results = []
        for record in results:
            processed_record = {}
            for key, value in record.items():
                # Handle Neo4j node objects
                if hasattr(value, "labels") and hasattr(value, "items"):
                    # It's a node
                    processed_record[key] = {
                        "labels": list(value.labels),
                        "properties": dict(value.items())
                    }
                # Handle Neo4j relationship objects
                elif hasattr(value, "type") and hasattr(value, "start_node"):
                    # It's a relationship
                    processed_record[key] = {
                        "type": value.type,
                        "properties": dict(value.items())
                    }
                else:
                    # Regular value
                    processed_record[key] = value
            processed_results.append(processed_record)
        
        return {
            "success": True,
            "results": processed_results,
            "query": query
        }
    except Exception as e:
        logger.error(f"Error executing graph query: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }
```

3. Implement external API retrieval:
```python
def execute_api_retrieval(self, endpoint, params=None, headers=None, method="GET", body=None):
    """Execute a request to an external API endpoint."""
    # Validate the endpoint against allowed list
    if not self._is_allowed_endpoint(endpoint):
        return {
            "success": False,
            "error": f"Endpoint {endpoint} is not in the allowed list"
        }
    
    # Prepare request
    request_params = params or {}
    request_headers = headers or {}
    
    # Add authentication if configured for this endpoint
    auth_config = self._get_endpoint_auth(endpoint)
    if auth_config:
        if auth_config["type"] == "bearer":
            request_headers["Authorization"] = f"Bearer {auth_config['token']}"
        elif auth_config["type"] == "api_key":
            if auth_config["in"] == "header":
                request_headers[auth_config["name"]] = auth_config["value"]
            elif auth_config["in"] == "query":
                request_params[auth_config["name"]] = auth_config["value"]
    
    # Execute request
    try:
        response = requests.request(
            method=method.upper(),
            url=endpoint,
            params=request_params,
            headers=request_headers,
            json=body if method.upper() in ["POST", "PUT", "PATCH"] else None,
            timeout=30  # 30 second timeout
        )
        
        # Try to parse as JSON
        try:
            response_data = response.json()
        except ValueError:
            response_data = response.text
        
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response_data,
            "headers": dict(response.headers)
        }
    except Exception as e:
        logger.error(f"Error executing API retrieval: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "endpoint": endpoint
        }

def _is_allowed_endpoint(self, endpoint):
    """Check if the endpoint is in the allowed list."""
    allowed_endpoints = settings.ALLOWED_API_ENDPOINTS
    
    # Direct match
    if endpoint in allowed_endpoints:
        return True
    
    # Pattern match
    for pattern in allowed_endpoints:
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            if endpoint.startswith(prefix):
                return True
    
    return False

def _get_endpoint_auth(self, endpoint):
    """Get authentication configuration for an endpoint."""
    endpoint_auth = settings.API_ENDPOINT_AUTH or {}
    
    # Find the matching configuration
    for pattern, auth in endpoint_auth.items():
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            if endpoint.startswith(prefix):
                return auth
        elif pattern == endpoint:
            return auth
    
    return None
```

**Test Strategy:**

1. Unit tests for each retrieval method:
   - Test NLQ translation with various query types
   - Test Neo4j query execution with mock Neo4j client
   - Test API retrieval with mock requests library
   - Test endpoint validation and authentication logic

2. Integration tests:
   - Test NLQ against actual database with sample queries
   - Test Neo4j retrieval with actual Neo4j instance
   - Test API retrieval with mock API server

3. Security tests:
   - Verify endpoint validation prevents unauthorized API access
   - Test SQL injection protection in NLQ service
   - Test authentication handling for API endpoints
