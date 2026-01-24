# Task ID: 190

**Title:** Implement Enhanced Health Checks

**Status:** done

**Dependencies:** 189 ✓

**Priority:** high

**Description:** Implement deep health checks for all dependencies, including readiness vs. liveness probes and dependency timeout handling.

**Details:**

1. Create a new file `app/routes/health.py` with enhanced health check endpoints:

```python
from fastapi import APIRouter, Depends, Response, status
from typing import Dict, List, Optional
import time
import asyncio
from pydantic import BaseModel
import requests
from app.db.database import Database
from app.core.config import settings
from app.services.b2_storage_service import B2StorageService
from app.celery_app import app as celery_app
from app.core.tracing import TracingSpan

router = APIRouter()

class HealthStatus(BaseModel):
    status: str
    version: str
    environment: str
    checks: Dict[str, Dict]

@router.get("/health", response_model=HealthStatus, tags=["health"])
async def health_check():
    """Basic health check endpoint."""
    with TracingSpan(name="health.basic_check"):
        return {
            "status": "ok",
            "version": settings.SERVICE_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": {}
        }

@router.get("/health/liveness", response_model=HealthStatus, tags=["health"])
async def liveness_probe():
    """Kubernetes liveness probe endpoint.
    
    Checks if the application is running and responsive.
    Should be lightweight and not check external dependencies.
    """
    with TracingSpan(name="health.liveness_probe"):
        # Just check if the application is running
        return {
            "status": "ok",
            "version": settings.SERVICE_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": {
                "app": {
                    "status": "ok",
                    "message": "Application is running"
                }
            }
        }

@router.get("/health/readiness", response_model=HealthStatus, tags=["health"])
async def readiness_probe(response: Response):
    """Kubernetes readiness probe endpoint.
    
    Checks if the application is ready to receive traffic.
    Should check all critical dependencies.
    """
    with TracingSpan(name="health.readiness_probe") as span:
        start_time = time.time()
        checks = {}
        overall_status = "ok"
        
        # Check database connection
        try:
            with TracingSpan(name="health.check_database"):
                db = Database()
                db_start = time.time()
                db_result = db.execute_raw("SELECT 1")
                db_duration = time.time() - db_start
                
                checks["database"] = {
                    "status": "ok",
                    "message": "Database connection successful",
                    "duration_ms": round(db_duration * 1000, 2)
                }
        except Exception as e:
            span.record_exception(e)
            checks["database"] = {
                "status": "error",
                "message": str(e),
                "duration_ms": round((time.time() - start_time) * 1000, 2)
            }
            overall_status = "error"
        
        # Check B2 storage
        try:
            with TracingSpan(name="health.check_b2"):
                b2_start = time.time()
                b2_service = B2StorageService()
                b2_service.check_connection()
                b2_duration = time.time() - b2_start
                
                checks["b2_storage"] = {
                    "status": "ok",
                    "message": "B2 connection successful",
                    "duration_ms": round(b2_duration * 1000, 2)
                }
        except Exception as e:
            span.record_exception(e)
            checks["b2_storage"] = {
                "status": "error",
                "message": str(e),
                "duration_ms": round((time.time() - b2_start) * 1000, 2)
            }
            overall_status = "error"
        
        # Check Celery connection
        try:
            with TracingSpan(name="health.check_celery"):
                celery_start = time.time()
                celery_ping = celery_app.control.ping(timeout=1.0)
                celery_duration = time.time() - celery_start
                
                if celery_ping:
                    checks["celery"] = {
                        "status": "ok",
                        "message": f"Celery connection successful, {len(celery_ping)} workers responded",
                        "duration_ms": round(celery_duration * 1000, 2),
                        "workers": len(celery_ping)
                    }
                else:
                    checks["celery"] = {
                        "status": "warning",
                        "message": "No Celery workers responded",
                        "duration_ms": round(celery_duration * 1000, 2),
                        "workers": 0
                    }
                    # Don't fail readiness for Celery, just warn
        except Exception as e:
            span.record_exception(e)
            checks["celery"] = {
                "status": "error",
                "message": str(e),
                "duration_ms": round((time.time() - celery_start) * 1000, 2)
            }
            # Don't fail readiness for Celery, just report error
        
        # Set response status code based on overall status
        if overall_status != "ok":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        total_duration = time.time() - start_time
        span.set_attribute("health.duration_ms", round(total_duration * 1000, 2))
        span.set_attribute("health.status", overall_status)
        
        return {
            "status": overall_status,
            "version": settings.SERVICE_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks
        }

@router.get("/health/deep", response_model=HealthStatus, tags=["health"])
async def deep_health_check(response: Response):
    """Deep health check that tests all dependencies."""
    with TracingSpan(name="health.deep_check") as span:
        start_time = time.time()
        checks = {}
        overall_status = "ok"
        
        # Check database with more detailed query
        try:
            with TracingSpan(name="health.check_database_deep"):
                db = Database()
                db_start = time.time()
                # Check table counts to verify database is properly populated
                tables = ["documents", "research_projects", "task_queue"]
                db_details = {}
                
                for table in tables:
                    count = db.count(table)
                    db_details[table] = count
                
                db_duration = time.time() - db_start
                
                checks["database"] = {
                    "status": "ok",
                    "message": "Database checks passed",
                    "duration_ms": round(db_duration * 1000, 2),
                    "details": db_details
                }
        except Exception as e:
            span.record_exception(e)
            checks["database"] = {
                "status": "error",
                "message": str(e),
                "duration_ms": round((time.time() - start_time) * 1000, 2)
            }
            overall_status = "error"
        
        # Check B2 storage with file listing
        try:
            with TracingSpan(name="health.check_b2_deep"):
                b2_start = time.time()
                b2_service = B2StorageService()
                # List files in a test directory
                files = b2_service.list_files("health_check", max_files=5)
                b2_duration = time.time() - b2_start
                
                checks["b2_storage"] = {
                    "status": "ok",
                    "message": "B2 storage checks passed",
                    "duration_ms": round(b2_duration * 1000, 2),
                    "details": {
                        "files_listed": len(files)
                    }
                }
        except Exception as e:
            span.record_exception(e)
            checks["b2_storage"] = {
                "status": "error",
                "message": str(e),
                "duration_ms": round((time.time() - b2_start) * 1000, 2)
            }
            overall_status = "error"
        
        # Check Celery with more details
        try:
            with TracingSpan(name="health.check_celery_deep"):
                celery_start = time.time()
                # Get stats from workers
                stats = celery_app.control.inspect().stats()
                # Get active tasks
                active = celery_app.control.inspect().active()
                celery_duration = time.time() - celery_start
                
                if stats:
                    worker_details = {}
                    for worker, worker_stats in stats.items():
                        worker_details[worker] = {
                            "processed": worker_stats.get("total", {}).get("processed", 0),
                            "active": len(active.get(worker, [])) if active else 0
                        }
                    
                    checks["celery"] = {
                        "status": "ok",
                        "message": f"Celery checks passed, {len(stats)} workers active",
                        "duration_ms": round(celery_duration * 1000, 2),
                        "details": {
                            "workers": len(stats),
                            "worker_stats": worker_details
                        }
                    }
                else:
                    checks["celery"] = {
                        "status": "warning",
                        "message": "No Celery workers responded",
                        "duration_ms": round(celery_duration * 1000, 2),
                        "details": {
                            "workers": 0
                        }
                    }
        except Exception as e:
            span.record_exception(e)
            checks["celery"] = {
                "status": "error",
                "message": str(e),
                "duration_ms": round((time.time() - celery_start) * 1000, 2)
            }
        
        # Check external APIs if configured
        if settings.EXTERNAL_API_HEALTH_CHECKS:
            for api_name, api_url in settings.EXTERNAL_API_HEALTH_CHECKS.items():
                try:
                    with TracingSpan(name=f"health.check_api.{api_name}"):
                        api_start = time.time()
                        response = requests.get(api_url, timeout=5.0)
                        api_duration = time.time() - api_start
                        
                        if response.status_code < 400:
                            checks[f"api_{api_name}"] = {
                                "status": "ok",
                                "message": f"API {api_name} responded with status {response.status_code}",
                                "duration_ms": round(api_duration * 1000, 2)
                            }
                        else:
                            checks[f"api_{api_name}"] = {
                                "status": "error",
                                "message": f"API {api_name} responded with error status {response.status_code}",
                                "duration_ms": round(api_duration * 1000, 2)
                            }
                            overall_status = "error"
                except Exception as e:
                    span.record_exception(e)
                    checks[f"api_{api_name}"] = {
                        "status": "error",
                        "message": str(e),
                        "duration_ms": round((time.time() - api_start) * 1000, 2)
                    }
                    overall_status = "error"
        
        # Set response status code based on overall status
        if overall_status != "ok":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        total_duration = time.time() - start_time
        span.set_attribute("health.duration_ms", round(total_duration * 1000, 2))
        span.set_attribute("health.status", overall_status)
        
        return {
            "status": overall_status,
            "version": settings.SERVICE_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks
        }
```

2. Add a method to check B2 connection in `app/services/b2_storage_service.py`:

```python
def check_connection(self):
    """Check if B2 connection is working."""
    try:
        # Try to get account info or list buckets as a simple check
        self.b2_api.get_bucket_by_name(self.bucket_name)
        return True
    except Exception as e:
        raise ConnectionError(f"B2 connection failed: {str(e)}")

def list_files(self, prefix, max_files=100):
    """List files in B2 with the given prefix."""
    bucket = self.b2_api.get_bucket_by_name(self.bucket_name)
    files = []
    
    for file_info, _ in bucket.ls(prefix, max_count=max_files):
        files.append({
            "file_name": file_info.file_name,
            "size": file_info.size,
            "content_type": file_info.content_type,
            "upload_timestamp": file_info.upload_timestamp
        })
    
    return files
```

3. Update `app/core/config.py` to include health check settings:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Health check settings
    EXTERNAL_API_HEALTH_CHECKS: Dict[str, str] = {
        "llama_index": "https://api.llamaindex.example.com/health",
        "embedding": "https://api.embedding.example.com/health"
    }
    HEALTH_CHECK_TIMEOUT: float = 5.0
```

**Test Strategy:**

1. Unit tests:
   - Test each health check endpoint
   - Test timeout handling for dependencies
   - Test error handling for various failure scenarios

2. Integration tests:
   - Test health checks with actual dependencies
   - Test behavior when dependencies are down
   - Test response formats and status codes

3. Load tests:
   - Test health check performance under load
   - Verify health checks don't impact main application performance
   - Test with concurrent health check requests

## Subtasks

### 190.1. Create health check models and base structure

**Status:** pending  
**Dependencies:** None  

Create the base health check models and structure in app/core/health.py

**Details:**

Create a new file app/core/health.py that defines the Pydantic models for health check responses. Include HealthStatus model with status, version, environment, and checks fields. Also implement base health check utility functions for timeout handling and dependency status aggregation.

### 190.2. Implement liveness probe endpoint

**Status:** pending  
**Dependencies:** 190.1  

Implement the /health/liveness endpoint that checks if the application is running

**Details:**

Create the liveness probe endpoint in app/routes/health.py that checks only if the application is running without checking external dependencies. This endpoint should be lightweight and fast, returning a 200 status code if the application is responsive. Include basic application information in the response.

### 190.3. Implement readiness probe endpoint

**Status:** pending  
**Dependencies:** 190.1, 190.2  

Implement the /health/readiness endpoint that checks critical dependencies

**Details:**

Create the readiness probe endpoint in app/routes/health.py that checks if all critical dependencies (database, B2 storage) are available and the application is ready to receive traffic. Implement timeout handling for dependency checks and return appropriate status codes (503 if any dependency is unavailable).

### 190.4. Implement deep health check endpoint

**Status:** pending  
**Dependencies:** 190.3  

Implement the /health/deep endpoint for comprehensive dependency checking

**Details:**

Create the deep health check endpoint in app/routes/health.py that performs comprehensive checks on all dependencies including database table counts, B2 storage file listing, Celery worker stats, and external API checks. Implement detailed reporting of dependency status with timing information and proper error handling.

### 190.5. Implement dependency-specific health checks

**Status:** pending  
**Dependencies:** 190.1  

Implement health check methods for Supabase, Neo4j, Redis, and B2 dependencies

**Details:**

Add health check methods to the respective service classes for each dependency: Database class for Supabase checks, Neo4jService for graph database checks, RedisService for cache checks, and B2StorageService for object storage checks. Each method should verify connectivity and basic functionality with appropriate timeout handling.
