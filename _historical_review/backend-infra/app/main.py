"""
Empire v7.3 - FastAPI Main Application
Production-grade API server with monitoring, error handling, and authentication
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers (to be created)
# from app.api import documents, search, chat, admin

# Prometheus metrics
REQUEST_COUNT = Counter('empire_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('empire_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
PROCESSING_TASKS = Counter('empire_processing_tasks_total', 'Total processing tasks', ['task_type', 'status'])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup: Initialize connections (log status only, not URLs for security)
    print("🚀 Empire v7.3 FastAPI starting...")
    print(f"📊 Supabase: {'configured' if os.getenv('SUPABASE_URL') else 'not configured'}")
    print(f"🔴 Redis: {'configured' if os.getenv('REDIS_URL') else 'not configured'}")
    print(f"🗄️ Neo4j: {'configured' if os.getenv('NEO4J_URI') else 'not configured'}")
    print(f"📦 LlamaIndex Service: {'configured' if os.getenv('LLAMAINDEX_SERVICE_URL') else 'not configured'}")
    print(f"🤖 CrewAI Service: {'configured' if os.getenv('CREWAI_SERVICE_URL') else 'not configured'}")

    # TODO: Initialize database connections
    # TODO: Initialize Redis connection
    # TODO: Initialize Neo4j connection
    # TODO: Verify external services

    yield

    # Shutdown: Close connections
    print("👋 Empire v7.3 FastAPI shutting down...")
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
# Note: allow_credentials=True requires explicit origins, not wildcards
_cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
_cors_origins = [o.strip() for o in _cors_origins if o.strip() and o.strip() != "*"]

if not _cors_origins:
    # Default safe origins for development
    _cors_origins = ["http://localhost:3000", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


import re as _re


def _normalize_path(path: str) -> str:
    """
    Normalize request path to prevent high cardinality metrics.
    Replaces path parameters with placeholders.
    """
    # Replace UUIDs with placeholder
    path = _re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
    # Replace numeric IDs with placeholder
    path = _re.sub(r'/\d+', '/{id}', path)
    return path


# Middleware for request tracking
@app.middleware("http")
async def track_requests(request, call_next):
    """Track request metrics"""
    start_time = time.time()

    response = await call_next(request)

    # Record metrics with normalized path to prevent high cardinality
    duration = time.time() - start_time
    normalized_path = _normalize_path(request.url.path)

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=normalized_path
    ).observe(duration)

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=normalized_path,
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


# TODO: Include routers
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
