"""
Empire v7.3 - FastAPI Main Application
Production-grade API server with monitoring, error handling, and authentication
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Import routers
from app.api import upload, notifications

# Import services
from app.services.mountain_duck_poller import start_mountain_duck_monitoring, stop_mountain_duck_monitoring
from app.services.monitoring_service import get_monitoring_service
from app.services.supabase_storage import get_supabase_storage

# Prometheus metrics (basic request tracking)
REQUEST_COUNT = Counter('empire_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('empire_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])

# Note: Business metrics for document processing are defined in monitoring_service.py
# This includes: DOCUMENT_PROCESSING_TOTAL, DOCUMENT_PROCESSING_DURATION, EMBEDDING_GENERATION_TOTAL, etc.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup: Initialize connections
    print("🚀 Empire v7.3 FastAPI starting...")
    print(f"📊 Supabase: {os.getenv('SUPABASE_URL')}")
    print(f"🔴 Redis: {os.getenv('REDIS_URL')}")
    print(f"🗄️ Neo4j: {os.getenv('NEO4J_URI')}")
    print(f"📦 LlamaIndex Service: {os.getenv('LLAMAINDEX_SERVICE_URL')}")
    print(f"🤖 CrewAI Service: {os.getenv('CREWAI_SERVICE_URL')}")

    # Initialize monitoring service with Supabase storage
    supabase_storage = get_supabase_storage()
    monitoring_service = get_monitoring_service(supabase_storage)
    app.state.monitoring = monitoring_service
    print("📈 Monitoring service initialized")

    # Start Mountain Duck file monitoring (if enabled)
    if os.getenv("ENABLE_MOUNTAIN_DUCK_POLLING", "false").lower() == "true":
        start_mountain_duck_monitoring()
        print("📁 Mountain Duck monitoring started")

    # TODO: Initialize database connections
    # TODO: Initialize Redis connection
    # TODO: Initialize Neo4j connection
    # TODO: Verify external services

    yield

    # Shutdown: Close connections
    print("👋 Empire v7.3 FastAPI shutting down...")

    # Stop Mountain Duck monitoring
    if os.getenv("ENABLE_MOUNTAIN_DUCK_POLLING", "false").lower() == "true":
        stop_mountain_duck_monitoring()
        print("📁 Mountain Duck monitoring stopped")

    # TODO: Close database connections
    # TODO: Close Redis connection
    # TODO: Close Neo4j connection


# Create FastAPI app
app = FastAPI(
    title="Empire v7.3 API",
    description="AI File Processing System with Dual-Interface Architecture",
    version="7.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Middleware for request tracking
@app.middleware("http")
async def track_requests(request, call_next):
    """Track request metrics"""
    start_time = time.time()

    response = await call_next(request)

    # Record metrics
    duration = time.time() - start_time
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    # Add timing header
    response.headers["X-Process-Time"] = str(duration)

    return response


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "version": "7.3.0",
        "service": "Empire FastAPI"
    }


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """Detailed health check with dependency status"""

    health_status = {
        "status": "healthy",
        "version": "7.3.0",
        "service": "Empire FastAPI",
        "dependencies": {
            "supabase": "unknown",
            "redis": "unknown",
            "neo4j": "unknown",
            "llamaindex": "unknown",
            "crewai": "unknown"
        }
    }

    # TODO: Check Supabase connection
    # TODO: Check Redis connection
    # TODO: Check Neo4j connection
    # TODO: Check LlamaIndex service
    # TODO: Check CrewAI service

    return health_status


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Kubernetes readiness probe"""
    # TODO: Check if all dependencies are ready
    return {"ready": True}


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"alive": True}


# Monitoring endpoints
@app.get("/monitoring/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/monitoring/stats", tags=["Monitoring"])
async def stats():
    """Application statistics"""
    return {
        "total_requests": "see /monitoring/metrics",
        "average_latency": "see /monitoring/metrics",
        "active_tasks": "see /monitoring/metrics"
    }


# API version endpoint
@app.get("/", tags=["Info"])
async def root():
    """API root - returns version and documentation links"""
    return {
        "service": "Empire v7.3 API",
        "version": "7.3.0",
        "architecture": "FastAPI + Celery + Supabase + Neo4j + Redis",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "metrics": "/monitoring/metrics"
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    print(f"❌ Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "path": request.url.path
        }
    )


# Include routers
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
# TODO: Additional routers
# app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
# app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
# app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
# app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info"
    )
