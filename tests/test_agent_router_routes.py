"""
Empire v7.3 - Agent Router Routes Tests (Task 17.5)
Tests for FastAPI endpoints for intelligent agent routing

Author: Claude Code
Date: 2025-01-25
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models.agent_router import (
    AgentType,
    QueryCategory,
    RoutingConfidence,
    AgentRouterRequest,
    AgentRouterResponse,
    ClassificationDetail,
)


class TestHealthEndpoints:
    """Test health and info endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        # Mock the service
        mock_service = MagicMock(spec=AgentRouterService)
        mock_service.supabase = MagicMock()  # Simulate available Supabase
        mock_service.cache_ttl_hours = 168
        mock_service.similarity_threshold = 0.85
        mock_service.use_semantic_cache = True

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/router/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "agent_router"
            assert "dependencies" in data
            assert "config" in data

    @pytest.mark.asyncio
    async def test_list_agents(self):
        """Test list agents endpoint."""
        from app.routes.agent_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/router/agents")
            assert response.status_code == 200
            data = response.json()
            assert "agents" in data
            assert data["count"] == 3
            assert any(a["type"] == "langgraph" for a in data["agents"])
            assert any(a["type"] == "crewai" for a in data["agents"])
            assert any(a["type"] == "simple" for a in data["agents"])

    @pytest.mark.asyncio
    async def test_list_categories(self):
        """Test list categories endpoint."""
        from app.routes.agent_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/router/categories")
            assert response.status_code == 200
            data = response.json()
            assert "categories" in data
            assert data["count"] == 6


class TestRoutingEndpoints:
    """Test routing endpoints."""

    @pytest.mark.asyncio
    async def test_route_query_simple(self):
        """Test routing a simple query."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        # Mock the service
        mock_service = MagicMock(spec=AgentRouterService)
        mock_response = AgentRouterResponse(
            query="What is our vacation policy?",
            selected_agent=AgentType.SIMPLE,
            confidence=0.90,
            confidence_level=RoutingConfidence.HIGH,
            reasoning="Simple factual lookup",
            classification=ClassificationDetail(
                category=QueryCategory.DOCUMENT_LOOKUP,
                category_confidence=0.90,
                features_detected=["simple_lookup"],
                query_complexity="simple"
            ),
            suggested_tools=["VectorSearch"],
            routing_time_ms=5,
            from_cache=False,
            request_id="test-123"
        )
        mock_service.route_query = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/route",
                json={"query": "What is our vacation policy?"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["selected_agent"] == "simple"
            assert data["confidence"] == 0.90
            assert data["request_id"] == "test-123"

    @pytest.mark.asyncio
    async def test_route_query_research(self):
        """Test routing a research query."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_response = AgentRouterResponse(
            query="What are the latest California regulations?",
            selected_agent=AgentType.LANGGRAPH,
            confidence=0.90,
            confidence_level=RoutingConfidence.HIGH,
            reasoning="Research query needs external data",
            routing_time_ms=10,
            from_cache=False,
            request_id="test-456"
        )
        mock_service.route_query = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/route",
                json={"query": "What are the latest California regulations?"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["selected_agent"] == "langgraph"

    @pytest.mark.asyncio
    async def test_route_query_with_llm(self):
        """Test routing with LLM classification."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_response = AgentRouterResponse(
            query="Complex query",
            selected_agent=AgentType.CREWAI,
            confidence=0.85,
            confidence_level=RoutingConfidence.HIGH,
            reasoning="LLM classification",
            routing_time_ms=500,
            from_cache=False,
            request_id="test-789"
        )
        mock_service.route_query = AsyncMock(return_value=mock_response)

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/route?use_llm=true",
                json={"query": "Complex query"}
            )
            assert response.status_code == 200
            # Verify use_llm was passed
            mock_service.route_query.assert_called_once()
            call_args = mock_service.route_query.call_args
            assert call_args.kwargs.get("use_llm") is True

    @pytest.mark.asyncio
    async def test_route_batch(self):
        """Test batch routing."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from app.models.agent_router import BatchRouterResponse
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_batch_response = BatchRouterResponse(
            results=[
                AgentRouterResponse(
                    query="Query 1",
                    selected_agent=AgentType.SIMPLE,
                    confidence=0.90,
                    confidence_level=RoutingConfidence.HIGH,
                    routing_time_ms=5,
                    from_cache=False,
                    request_id="batch-1"
                ),
                AgentRouterResponse(
                    query="Query 2",
                    selected_agent=AgentType.LANGGRAPH,
                    confidence=0.85,
                    confidence_level=RoutingConfidence.HIGH,
                    routing_time_ms=8,
                    from_cache=True,
                    request_id="batch-2"
                ),
            ],
            total_queries=2,
            processing_time_ms=15,
            cache_hits=1
        )
        mock_service.route_batch = AsyncMock(return_value=mock_batch_response)

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/route/batch",
                json={"queries": ["Query 1", "Query 2"]}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_queries"] == 2
            assert data["cache_hits"] == 1
            assert len(data["results"]) == 2


class TestClassifyEndpoint:
    """Test classify endpoint."""

    @pytest.mark.asyncio
    async def test_classify_query(self):
        """Test query classification endpoint."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_service.classify_query_rules = MagicMock(
            return_value=(QueryCategory.DOCUMENT_LOOKUP, ["simple_lookup"], "simple")
        )
        mock_service._select_agent = MagicMock(
            return_value=(AgentType.SIMPLE, 0.90, "Simple lookup")
        )

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/classify",
                params={"query": "What is our vacation policy?"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["category"] == "document_lookup"
            assert data["complexity"] == "simple"
            assert "simple_lookup" in data["features_detected"]
            assert data["suggested_agent"] == "simple"


class TestFeedbackEndpoint:
    """Test feedback endpoint."""

    @pytest.mark.asyncio
    async def test_submit_positive_feedback(self):
        """Test submitting positive feedback."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "feedback-123"}]
        )
        mock_service.supabase = mock_supabase

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/feedback",
                json={
                    "request_id": "test-request-123",
                    "feedback": "positive"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_submit_negative_feedback_with_correction(self):
        """Test submitting negative feedback with agent correction."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "feedback-456"}]
        )
        mock_service.supabase = mock_supabase

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/feedback",
                json={
                    "request_id": "test-request-456",
                    "feedback": "negative",
                    "comment": "Should have used CrewAI",
                    "correct_agent": "crewai"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestAnalyticsEndpoints:
    """Test analytics endpoints."""

    @pytest.mark.asyncio
    async def test_get_analytics(self):
        """Test getting routing analytics."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.gte.return_value.execute.return_value = MagicMock(
            data=[
                {"selected_agent": "simple", "confidence": 0.90, "confidence_level": "high"},
                {"selected_agent": "langgraph", "confidence": 0.85, "confidence_level": "high"},
                {"selected_agent": "crewai", "confidence": 0.80, "confidence_level": "high"},
            ]
        )
        mock_service.supabase = mock_supabase

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/router/analytics?time_period=24h")
            assert response.status_code == 200
            data = response.json()
            assert "metrics" in data
            assert data["metrics"]["time_period"] == "24h"
            assert data["metrics"]["total_requests"] == 3

    @pytest.mark.asyncio
    async def test_get_cache_analytics(self):
        """Test getting cache analytics."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_service.use_semantic_cache = True
        mock_service.cache_ttl_hours = 168
        mock_service.similarity_threshold = 0.85

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "hit_count": 5},
                {"id": "2", "hit_count": 10},
                {"id": "3", "hit_count": 3},
            ]
        )
        mock_service.supabase = mock_supabase

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/router/analytics/cache")
            assert response.status_code == 200
            data = response.json()
            assert data["cache_enabled"] is True
            assert data["statistics"]["total_entries"] == 3
            assert data["statistics"]["total_hits"] == 18


class TestAdminEndpoints:
    """Test admin endpoints."""

    @pytest.mark.asyncio
    async def test_clear_expired_cache(self):
        """Test clearing expired cache entries."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from app.middleware.auth import require_admin
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_supabase = MagicMock()
        mock_supabase.rpc.return_value.execute.return_value = MagicMock()
        mock_service.supabase = mock_supabase

        app.dependency_overrides[get_router_service] = lambda: mock_service
        # Mock require_admin to return True (simulating admin user)
        app.dependency_overrides[require_admin] = lambda: True

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.delete("/api/router/cache/clear?expired_only=true")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["expired_only"] is True


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_route_query_error(self):
        """Test error handling when routing fails."""
        from app.routes.agent_router import router, get_router_service
        from app.services.agent_router_service import AgentRouterService
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_service = MagicMock(spec=AgentRouterService)
        mock_service.route_query = AsyncMock(side_effect=Exception("Database error"))

        app.dependency_overrides[get_router_service] = lambda: mock_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/route",
                json={"query": "Test query"}
            )
            assert response.status_code == 500
            data = response.json()
            assert "Query routing failed" in data["detail"]

    @pytest.mark.asyncio
    async def test_invalid_request(self):
        """Test handling of invalid request."""
        from app.routes.agent_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/router/route",
                json={"query": ""}  # Empty query should fail validation
            )
            assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
