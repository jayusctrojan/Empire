# Task ID: 140

**Title:** Enhance Content Prep Agent Health Endpoint

**Status:** done

**Dependencies:** 122 ✓, 124 ✓

**Priority:** medium

**Description:** Update the existing GET /api/content-prep/health endpoint to include comprehensive agent status information including agent_id, version, uptime, error metrics, and processing statistics.

**Details:**

Enhance the existing health endpoint in the content_prep.py routes file to provide more detailed status information:

1. Modify the route in app/routes/content_prep.py:
```python
@router.get("/health", response_model=ContentPrepHealthResponse)
async def get_health():
    """
    Get health status for the Content Prep Agent (AGENT-016).
    
    Returns:
        ContentPrepHealthResponse: Detailed health status including connectivity and metrics
    """
    health_service = get_health_service()
    
    # Get basic agent information
    agent_info = {
        "agent_id": "AGENT-016",
        "name": "Content Prep Agent",
        "version": get_version(),
        "uptime": calculate_uptime()
    }
    
    # Get processing metrics
    metrics = {
        "recent_error_count": await health_service.get_recent_error_count(),
        "pending_content_sets": await health_service.get_pending_content_sets_count(),
        "active_processing_count": await health_service.get_active_processing_count()
    }
    
    # Check database connectivity
    connectivity = {
        "supabase": await health_service.check_supabase_connectivity(),
        "neo4j": await health_service.check_neo4j_connectivity()
    }
    
    return ContentPrepHealthResponse(
        status="healthy" if all(connectivity.values()) else "degraded",
        agent=agent_info,
        metrics=metrics,
        connectivity=connectivity
    )
```

2. Create or update the response model in app/models/health.py:
```python
class ContentPrepHealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    agent: Dict[str, Any]  # Contains agent_id, name, version, uptime
    metrics: Dict[str, int]  # Contains error_count, pending_sets, active_processing
    connectivity: Dict[str, bool]  # Contains status of connected services
```

3. Implement the health service methods in app/services/health_service.py:
```python
class HealthService:
    # ... existing code ...
    
    async def get_recent_error_count(self) -> int:
        """Get count of errors in the last 24 hours"""
        try:
            # Query error logs from database
            return await self.db.fetch_error_count(hours=24)
        except Exception:
            return -1  # Indicate error retrieving count
    
    async def get_pending_content_sets_count(self) -> int:
        """Get count of content sets waiting to be processed"""
        try:
            return await self.db.fetch_content_sets_count(status="pending")
        except Exception:
            return -1
    
    async def get_active_processing_count(self) -> int:
        """Get count of content sets currently being processed"""
        try:
            return await self.db.fetch_content_sets_count(status="processing")
        except Exception:
            return -1
    
    async def check_supabase_connectivity(self) -> bool:
        """Check if Supabase connection is working"""
        try:
            # Simple query to verify connection
            await self.db.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    async def check_neo4j_connectivity(self) -> bool:
        """Check if Neo4j connection is working"""
        try:
            # Simple query to verify connection
            result = await self.neo4j_client.run("MATCH (n) RETURN count(n) LIMIT 1")
            return result is not None
        except Exception:
            return False
```

4. Implement the utility functions in app/utils/system.py:
```python
def get_version() -> str:
    """Get the current version of the application"""
    try:
        with open("VERSION", "r") as f:
            return f.read().strip()
    except Exception:
        return "unknown"

def calculate_uptime() -> int:
    """Calculate uptime in seconds since application start"""
    global _start_time
    return int(time.time() - _start_time)
```

5. Update the application startup to record start time:
```python
# In app/main.py
import time

_start_time = time.time()

def start_application():
    # ... existing code ...
```

**Test Strategy:**

1. Create unit tests in tests/routes/test_content_prep.py:
```python
async def test_health_endpoint_returns_correct_structure():
    # Arrange
    client = TestClient(app)
    
    # Act
    response = client.get("/api/content-prep/health")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "agent" in data
    assert "metrics" in data
    assert "connectivity" in data
    
    # Check agent info
    assert "agent_id" in data["agent"]
    assert data["agent"]["agent_id"] == "AGENT-016"
    assert "version" in data["agent"]
    assert "uptime" in data["agent"]
    
    # Check metrics
    assert "recent_error_count" in data["metrics"]
    assert "pending_content_sets" in data["metrics"]
    assert "active_processing_count" in data["metrics"]
    
    # Check connectivity
    assert "supabase" in data["connectivity"]
    assert "neo4j" in data["connectivity"]

async def test_health_endpoint_with_mocked_services():
    # Arrange
    app.dependency_overrides[get_health_service] = lambda: MockHealthService(
        supabase_healthy=True,
        neo4j_healthy=True,
        error_count=5,
        pending_sets=10,
        active_processing=3
    )
    client = TestClient(app)
    
    # Act
    response = client.get("/api/content-prep/health")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["metrics"]["recent_error_count"] == 5
    assert data["metrics"]["pending_content_sets"] == 10
    assert data["metrics"]["active_processing_count"] == 3
    assert data["connectivity"]["supabase"] is True
    assert data["connectivity"]["neo4j"] is True
    
    # Clean up
    app.dependency_overrides.clear()

async def test_health_endpoint_with_degraded_services():
    # Arrange
    app.dependency_overrides[get_health_service] = lambda: MockHealthService(
        supabase_healthy=True,
        neo4j_healthy=False,
        error_count=5,
        pending_sets=10,
        active_processing=3
    )
    client = TestClient(app)
    
    # Act
    response = client.get("/api/content-prep/health")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["connectivity"]["supabase"] is True
    assert data["connectivity"]["neo4j"] is False
    
    # Clean up
    app.dependency_overrides.clear()
```

2. Create the MockHealthService class in tests/mocks/health_service.py:
```python
class MockHealthService:
    def __init__(self, supabase_healthy=True, neo4j_healthy=True, 
                 error_count=0, pending_sets=0, active_processing=0):
        self.supabase_healthy = supabase_healthy
        self.neo4j_healthy = neo4j_healthy
        self.error_count = error_count
        self.pending_sets = pending_sets
        self.active_processing = active_processing
    
    async def get_recent_error_count(self) -> int:
        return self.error_count
    
    async def get_pending_content_sets_count(self) -> int:
        return self.pending_sets
    
    async def get_active_processing_count(self) -> int:
        return self.active_processing
    
    async def check_supabase_connectivity(self) -> bool:
        return self.supabase_healthy
    
    async def check_neo4j_connectivity(self) -> bool:
        return self.neo4j_healthy
```

3. Perform integration testing:
   - Test the endpoint with actual database connections
   - Verify correct status reporting when services are unavailable
   - Test with various load conditions to ensure metrics are accurate

4. Verify the endpoint follows the pattern established by other agent health endpoints by comparing the response structure with existing health endpoints.
