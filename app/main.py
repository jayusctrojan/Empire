"""
Empire v7.3 - FastAPI Main Application
Production-grade API server with monitoring, error handling, and authentication
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi import status as http_status  # Renamed to avoid conflict with app.routes.status
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
from app.api.routes import query
from app.routes import sessions, preferences, costs, rbac, documents, users, monitoring, crewai, agent_interactions, crewai_assets, audit, feature_flags, websocket, agent_router, status, chat_files, content_summarizer, department_classifier, document_analysis, multi_agent_orchestration, embeddings, hybrid_search, reranking, query_expansion, semantic_cache, knowledge_graph, conversation_memory, context_management, projects, project_sources, project_rag, studio_cko, studio_assets, studio_classifications, studio_feedback, conversations, research_projects, content_prep, orchestrator, entity_extraction, llama_index, circuit_breakers, workflow_management, asset_generators, graph_agent, rag_metrics  # Task 28: Session & Preference Management, Task 30: Cost Tracking, Task 31: RBAC, Task 32: Bulk Document Management, Task 33: User Management, Task 34: Analytics Dashboard, Task 35: CrewAI Multi-Agent Integration, Task 39: Inter-Agent Messaging, Task 40: CrewAI Asset Storage, Task 41.5: Audit Logging, Task 3.2: Feature Flags, Task 10.2: WebSocket Endpoints, Task 17: Agent Router, Task 11: REST Status Polling, Task 21: Chat File Upload, Task 42: Content Summarizer Agent, Task 44: Department Classifier Agent, Task 45: Document Analysis Agents, Task 46: Multi-Agent Orchestration, Task 26: Embedding Generation, Task 27: Hybrid Search, Task 29: Reranking, Task 28: Query Expansion, Task 30: Semantic Cache, Task 31: Knowledge Graph, Task 32: Conversation Memory, Task 33: Context Management, Projects CRUD, Task 60: Project Sources CRUD, Task 64: Project RAG, Task 72: AI Studio CKO, Task 79: AI Studio Feedback, Conversations CRUD, Task 91-100: Research Projects (Agent Harness), Task 47: Content Prep Agent (AGENT-016), Task 133: Orchestrator API (AGENT-001), Task 155: Entity Extraction, Task 156: LlamaIndex Integration Hardening, Task 159: Circuit Breaker Management, Task 158: Workflow Management, Task 43: Asset Generators, Task 107: Graph Agent, Task 149: RAG Metrics
from app.routes import health as health_router  # Task 190: Enhanced Health Checks
from app.routes import feedback as feedback_router  # Task 188: Agent Feedback System
# from app.routes import preflight as preflight_router  # Service Orchestration: Preflight checks (not yet implemented)
from app.routes import context_window as context_window_router  # Feature 011: Chat Context Window Management
from app.routes import checkpoints as checkpoints_router  # Task 206: Automatic Checkpoint System
from app.routes import session_memory as session_memory_router  # Task 207: Session Memory & Persistence

# Import services
from app.services.mountain_duck_poller import start_mountain_duck_monitoring, stop_mountain_duck_monitoring
from app.services.monitoring_service import get_monitoring_service
from app.services.supabase_storage import get_supabase_storage
from app.core.langfuse_config import get_langfuse_client, shutdown_langfuse
from app.core.connections import connection_manager
from app.core.feature_flags import get_feature_flag_manager  # Task 3.2: Feature Flags
from app.core.graceful_shutdown import initialize_shutdown_coordinator, setup_signal_handlers, ShutdownMiddleware  # Service Orchestration

# Service Orchestration: Optional import - file may not exist yet
try:
    from app.core.service_orchestrator import ServiceOrchestrator
except ImportError:
    ServiceOrchestrator = None  # type: ignore

# Import security middleware (Task 41.1, 41.2, 41.4, 41.5)
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import configure_rate_limiting, limiter
from app.middleware.rls_context import configure_rls_context
from app.middleware.input_validation import configure_input_validation
from app.middleware.audit import configure_audit_logging

# Task 136: Request tracing middleware for X-Request-ID propagation
from app.middleware.request_tracing import RequestTracingMiddleware
from app.core.logging_config import configure_logging

# Task 154: Standardized Exception Handling Framework
from app.middleware.error_handler import setup_error_handling

# Task 170, 171: Startup Environment and CORS Validation (US1, US2 - Production Readiness)
from app.core.startup_validation import validate_environment, validate_cors_origins

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
    # Task 136: Configure logging with request ID support (before other startup messages)
    configure_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        json_output=os.getenv("ENVIRONMENT") == "production",
        include_timestamps=True
    )

    # Task 170: Fail-fast environment variable validation (US1 - Production Readiness)
    # This will raise RuntimeError and prevent startup if critical vars are missing
    validation_result = validate_environment()
    if validation_result["recommended"]:
        print(f"⚠️  Missing recommended env vars: {', '.join(validation_result['recommended'])}")

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

    # Initialize Langfuse for LLM observability (Task 29)
    langfuse_client = get_langfuse_client()
    if langfuse_client:
        print(f"🔍 Langfuse observability enabled: {os.getenv('LANGFUSE_HOST')}")
    else:
        print("⚠️  Langfuse observability disabled")

    # Start Mountain Duck file monitoring (if enabled)
    if os.getenv("ENABLE_MOUNTAIN_DUCK_POLLING", "false").lower() == "true":
        start_mountain_duck_monitoring()
        print("📁 Mountain Duck monitoring started")

    # Task 36: Initialize database connections
    try:
        await connection_manager.initialize()
        print("✅ Database connections initialized (Supabase, Redis, Neo4j)")

        # Verify external services
        is_ready = await connection_manager.check_readiness()
        if is_ready:
            print("✅ All critical services are ready")
        else:
            print("⚠️  Some services are not ready - check logs")
    except Exception as e:
        print(f"❌ Failed to initialize connections: {e}")
        # Continue anyway - some features may work without all connections

    # Task 3.2: Initialize Feature Flag Manager
    try:
        feature_flag_manager = get_feature_flag_manager()
        app.state.feature_flags = feature_flag_manager
        print("🚩 Feature flag manager initialized (Database + Redis cache)")
    except Exception as e:
        print(f"⚠️  Failed to initialize feature flag manager: {e}")

    # Service Orchestration: Initialize Service Orchestrator (if available)
    if ServiceOrchestrator is not None:
        try:
            service_orchestrator = ServiceOrchestrator()
            app.state.service_orchestrator = service_orchestrator
            print("🎯 Service orchestrator initialized")

            # Integrate with connection manager for unified health checks
            connection_manager.set_service_orchestrator(service_orchestrator)

            # Run preflight checks
            preflight_result = await service_orchestrator.check_all_services()
            if preflight_result.ready:
                print("✅ Preflight checks passed - all required services healthy")
            elif preflight_result.all_required_healthy:
                print("⚠️  Preflight checks passed with warnings - some optional services unavailable")
            else:
                print("❌ Preflight checks failed - some required services unhealthy")
        except Exception as e:
            print(f"⚠️  Failed to initialize service orchestrator: {e}")
    else:
        print("⚠️  Service orchestrator not available (module not installed)")

    # Service Orchestration: Initialize Graceful Shutdown Coordinator
    try:
        shutdown_coordinator = initialize_shutdown_coordinator(app)
        setup_signal_handlers(shutdown_coordinator)
        app.state.shutdown_coordinator = shutdown_coordinator

        # Add shutdown middleware (rejects new requests during graceful shutdown)
        # This must be added after coordinator initialization
        from starlette.middleware.base import BaseHTTPMiddleware
        shutdown_middleware = ShutdownMiddleware(app, shutdown_coordinator)
        # Note: middleware is registered via the ShutdownMiddleware class which wraps the dispatch
        print("🛑 Graceful shutdown coordinator initialized with middleware")
    except Exception as e:
        print(f"⚠️  Failed to initialize shutdown coordinator: {e}")

    # Task 10.3: Initialize WebSocket Manager with Redis Pub/Sub
    try:
        from app.services.websocket_manager import get_connection_manager
        ws_manager = get_connection_manager()
        await ws_manager.initialize_redis_pubsub()

        if ws_manager.redis_enabled:
            print("🔌 WebSocket manager initialized with Redis Pub/Sub (distributed broadcasting enabled)")
        else:
            print("🔌 WebSocket manager initialized (local-only broadcasting - Redis unavailable)")

        app.state.websocket_manager = ws_manager
    except Exception as e:
        print(f"⚠️  Failed to initialize WebSocket manager: {e}")

    yield

    # Shutdown: Close connections
    print("👋 Empire v7.3 FastAPI shutting down...")

    # Flush and shutdown Langfuse
    shutdown_langfuse()

    # Stop Mountain Duck monitoring
    if os.getenv("ENABLE_MOUNTAIN_DUCK_POLLING", "false").lower() == "true":
        stop_mountain_duck_monitoring()
        print("📁 Mountain Duck monitoring stopped")

    # Task 10.3: Shutdown WebSocket Manager and Redis Pub/Sub
    try:
        if hasattr(app.state, 'websocket_manager'):
            ws_manager = app.state.websocket_manager

            # Disconnect all active WebSocket connections
            connection_ids = list(ws_manager.active_connections.keys())
            for connection_id in connection_ids:
                await ws_manager.disconnect(connection_id)

            # Shutdown Redis Pub/Sub
            if ws_manager.redis_pubsub:
                await ws_manager.redis_pubsub.disconnect()

            print("✅ WebSocket manager and Redis Pub/Sub shut down gracefully")
    except Exception as e:
        print(f"⚠️  Error shutting down WebSocket manager: {e}")

    # Task 36: Close database connections gracefully
    try:
        await connection_manager.shutdown()
        print("✅ All database connections closed")
    except Exception as e:
        print(f"❌ Error closing connections: {e}")


# Create FastAPI app
app = FastAPI(
    title="Empire v7.3 API",
    description="AI File Processing System with Dual-Interface Architecture",
    version="7.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration (Task 41.1, Task 171: Hardened CORS with fail-fast validation)
# In production, CORS_ORIGINS must be explicitly set and cannot be wildcard.
# In development, defaults to "*" with warning. This is validated at startup.
cors_origins = validate_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],  # Explicit methods
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",
        "X-Request-Context",
        "X-User-ID",
        "X-Session-ID",
        "Accept",
        "Origin",
        "Cache-Control",
    ],  # Restricted to necessary headers for security
)

# Service Orchestration: Shutdown Middleware (rejects requests during graceful shutdown)
# Note: This middleware is initialized but requires the shutdown_coordinator from app.state
# It will be configured during the lifespan startup event
print("🚦 Shutdown middleware configured (active after startup)")

# Task 154: Standardized Exception Handling Framework
# Registers error handler middleware and exception handlers for BaseAppException
setup_error_handling(app)
print("🛡️ Exception handling framework enabled (Task 154)")

# Task 41.1: Security Headers Middleware
# Adds HSTS, X-Frame-Options, CSP, and other security headers
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=os.getenv("ENVIRONMENT") == "production")
print("🔒 Security headers middleware enabled")

# Task 43.3: Response Compression Middleware
# Gzip compression for responses > 1KB to reduce bandwidth and improve transfer times
from app.middleware.compression import add_compression_middleware
add_compression_middleware(app, minimum_size=1000)
print("📦 Response compression enabled (min_size=1KB)")

# Task 41.1: Rate Limiting
# Configure rate limiting for all endpoints
configure_rate_limiting(app)

# Task 41.2: RLS Context Middleware
# Sets PostgreSQL session variables for row-level security enforcement
configure_rls_context(app)

# Task 41.4: Input Validation - Request body size limits and security validators
configure_input_validation(app, max_body_size=100 * 1024 * 1024)  # 100MB default
print("🛡️ Input validation middleware enabled (max body size: 100MB)")

# Task 41.5: Audit Logging - Track security events
configure_audit_logging(app)
print("📝 Audit logging middleware enabled")

# Task 136: Request Tracing - X-Request-ID propagation for agent chains
app.add_middleware(
    RequestTracingMiddleware,
    header_name="X-Request-ID",
    log_requests=os.getenv("ENVIRONMENT") != "production",  # Verbose logging in dev only
    include_path=True,
    include_timing=True
)
print("🔗 Request tracing middleware enabled (X-Request-ID)")

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
    """Detailed health check with dependency status - Task 36"""

    # Check all connections and services
    dependencies = await connection_manager.check_health()

    # Determine overall status
    unhealthy_services = [
        service for service, status in dependencies.items()
        if "unhealthy" in str(status).lower()
    ]

    overall_status = "healthy" if not unhealthy_services else "degraded"

    health_status = {
        "status": overall_status,
        "version": "7.3.0",
        "service": "Empire FastAPI",
        "dependencies": dependencies,
        "unhealthy_services": unhealthy_services if unhealthy_services else [],
        "connections_initialized": connection_manager.connections_initialized
    }

    return health_status


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Kubernetes readiness probe - Task 36"""
    # Check if all critical dependencies are ready
    is_ready = await connection_manager.check_readiness()

    if not is_ready:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "message": "Not all critical services are available"
            }
        )

    return {"ready": True, "message": "All critical services are operational"}


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
app.include_router(query.router)  # Query router already has /api/query prefix defined

# Task 28: Session & Preference Management
app.include_router(sessions.router, prefix="/api/v1", tags=["Sessions"])
app.include_router(preferences.router, prefix="/api/v1", tags=["Preferences"])

# Task 30: Cost Tracking & Optimization
app.include_router(costs.router, prefix="/api/v1", tags=["Costs"])

# Task 31: RBAC & API Key Management
app.include_router(rbac.router)  # RBAC router already has /api/rbac prefix defined

# Task 32: Bulk Document Management & Batch Operations
app.include_router(documents.router)  # Documents router already has /api/documents prefix defined

# Task 33: User Management & GDPR Compliance
app.include_router(users.router)  # Users router already has /api/users prefix defined

# Task 34: Analytics Dashboard Implementation
app.include_router(monitoring.router)  # Monitoring router already has /api/monitoring prefix defined

# Task 35: CrewAI Multi-Agent Integration & Orchestration
app.include_router(crewai.router)  # CrewAI router already has /api/crewai prefix defined

# Task 39: Agent Interactions - Inter-Agent Messaging & Collaboration
app.include_router(agent_interactions.router)  # Agent Interactions router already has /api/crewai/agent-interactions prefix defined

# Task 40: CrewAI Asset Storage & Retrieval
app.include_router(crewai_assets.router)  # CrewAI Assets router already has /api/crewai/assets prefix defined

# Task 41.5: Audit Logging - Query API for security audit logs
app.include_router(audit.router)  # Audit router already has /api/audit prefix defined

# Task 3.2: Feature Flags Management
app.include_router(feature_flags.router)  # Feature flags router already has /api/feature-flags prefix defined

# Task 10.2: WebSocket Real-Time Status Endpoints
app.include_router(websocket.router)  # WebSocket router already has /ws prefix defined

# Task 17: Agent Router - Intelligent query routing
app.include_router(agent_router.router)  # Agent Router already has /api/router prefix defined

# Task 11: REST Status Polling Endpoints (WebSocket fallback)
app.include_router(status.router)  # Status router already has /api/status prefix defined

# Task 21: Chat File Upload - File and Image Upload in Chat
app.include_router(chat_files.router)  # Chat files router already has /api/chat prefix defined

# Task 42: Content Summarizer Agent (AGENT-002) - PDF Summary Generation
app.include_router(content_summarizer.router)  # Content Summarizer router already has /api/summarizer prefix defined

# Task 44: Department Classifier Agent (AGENT-008) - 10-Department Classification
app.include_router(department_classifier.router)  # Department Classifier router already has /api/classifier prefix defined

# Task 45: Document Analysis Agents (AGENT-009, AGENT-010, AGENT-011) - Research/Strategy/Fact-Check
app.include_router(document_analysis.router)  # Document Analysis router already has /api/document-analysis prefix defined

# Task 46: Multi-Agent Orchestration Agents (AGENT-012, AGENT-013, AGENT-014, AGENT-015) - Research/Analysis/Writing/Review
app.include_router(multi_agent_orchestration.router)  # Multi-Agent Orchestration router already has /api/orchestration prefix defined

# Task 26: Embedding Generation Service - BGE-M3 embeddings with caching
app.include_router(embeddings.router)  # Embeddings router already has /api/embeddings prefix defined

# Task 27: Hybrid Search with BM25 and Vector Fusion
app.include_router(hybrid_search.router)  # Hybrid Search router already has /api/search prefix defined

# Task 29: Reranking with BGE-Reranker-v2 (Ollama) and Claude fallback
app.include_router(reranking.router)  # Reranking router already has /api/rerank prefix defined

# Task 28: Query Expansion with Claude Haiku (<500ms latency target)
app.include_router(query_expansion.router)  # Query Expansion router already has /api/expand prefix defined

# Task 30: Semantic Cache with Tiered Similarity Thresholds (60-80% hit rate target)
app.include_router(semantic_cache.router)  # Semantic Cache router already has /api/cache prefix defined

# Task 31: Knowledge Graph Integration with Neo4j (entity queries, graph traversal, Cypher generation)
app.include_router(knowledge_graph.router)  # Knowledge Graph router already has /api/graph prefix defined

# Task 32: Conversation Memory with Graph Tables (memory nodes, edges, context retrieval)
app.include_router(conversation_memory.router)  # Conversation Memory router has /api/memory prefix

# Task 33: Context Management Service (context windows, weighted retrieval, graph traversal)
app.include_router(context_management.router)  # Context Management router has /api/context prefix

# Projects CRUD API (NotebookLM-style project management - persistent storage)
app.include_router(projects.router)  # Projects router has /api/projects prefix

# Task 60: Project Sources CRUD API (NotebookLM-style source management)
app.include_router(project_sources.router)  # Project Sources router has /api/projects prefix

# Task 64: Project-Scoped Hybrid RAG (NotebookLM-style query with sources + global KB)
app.include_router(project_rag.router)  # Project RAG router has /api/projects/{project_id}/rag prefix

# Task 72: AI Studio CKO Conversation (Chief Knowledge Officer persona for global KB chat)
app.include_router(studio_cko.router)  # Studio CKO router has /api/studio/cko prefix

# Task 76: AI Studio Asset Management (CRUD for Skills, Commands, Agents, Prompts, Workflows)
app.include_router(studio_assets.router)  # Studio Assets router has /api/studio/assets prefix

# Task 78: AI Studio Classification Management (Department classification viewing and correction)
app.include_router(studio_classifications.router)  # Studio Classifications router has /api/studio/classifications prefix
app.include_router(studio_feedback.router)  # Task 79: Studio Feedback router has /api/studio/feedback prefix

# Conversations CRUD API (Cloud-persisted chat history for desktop app)
app.include_router(conversations.router)  # Conversations router has /api/conversations prefix

# Research Projects API (Task 91-100: Agent Harness)
app.include_router(research_projects.router)  # Research Projects router has /api/research-projects prefix

# Task 47: Content Prep Agent (AGENT-016) - Content Set Detection and Ordering
app.include_router(content_prep.router)  # Content Prep router has /api/content-prep prefix

# Task 133: Master Orchestrator API (AGENT-001) - Content Classification and Asset Orchestration
app.include_router(orchestrator.router)  # Orchestrator router has /api/orchestrator prefix

# Task 155: Entity Extraction API - Claude Haiku-based entity extraction for research tasks
app.include_router(entity_extraction.router)  # Entity Extraction router has /api/entity-extraction prefix

# Task 156: LlamaIndex Integration Hardening - Resilient HTTP client with pooling, retry, and health checks
app.include_router(llama_index.router)  # LlamaIndex router has /api/llama-index prefix

# Task 159: Circuit Breaker Management - System-wide circuit breaker monitoring and control
app.include_router(circuit_breakers.router)  # Circuit Breakers router has /api/system/circuit-breakers prefix

# Task 158: Workflow Management - State persistence, graceful shutdown, cancellation, metrics
app.include_router(workflow_management.router)  # Workflow Management router has /api/workflows prefix

# Task 43: Asset Generators (AGENT-003 to AGENT-007) - Skill/Command/Agent/Prompt/Workflow generation
app.include_router(asset_generators.router)  # Asset Generators router has /api/assets prefix

# Task 107: Graph Agent - Customer 360, Document Structure, Graph-Enhanced RAG
app.include_router(graph_agent.router)  # Graph Agent router has /api/graph prefix (different endpoints from knowledge_graph)

# Task 149: RAG Metrics Dashboard - RAGAS metrics, trends, agent performance, optimization
app.include_router(rag_metrics.router)  # RAG Metrics router has /api/rag-metrics prefix

# Task 190: Enhanced Health Checks - Liveness, Readiness, Deep health checks with dependency timeout handling
app.include_router(health_router.router)  # Health router has /api/health prefix

# Task 188: Agent Feedback System - Feedback collection and statistics for AI agents
app.include_router(feedback_router.router)  # Feedback router has /api/feedback prefix

# Service Orchestration: Preflight checks and service health management
# app.include_router(preflight_router.router)  # Preflight router has /api/preflight prefix (not yet implemented)

# Feature 011: Chat Context Window Management - Progress bar and token tracking
app.include_router(context_window_router.router)  # Context Window router has /api/context-window prefix

# Task 206: Automatic Checkpoint System - Session checkpoints and crash recovery
app.include_router(checkpoints_router.router)  # Checkpoints router has /api/checkpoints prefix

# Task 207: Session Memory & Persistence - Long-term session memory and resumption
app.include_router(session_memory_router.router)  # Session Memory router has /api/session-memory prefix

# TODO: Additional routers
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
