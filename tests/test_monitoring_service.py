"""
Tests for Monitoring Service
Tests metrics collection, cost calculation, and database logging
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from prometheus_client import REGISTRY

from app.services.monitoring_service import (CostCalculator, MonitoringService,
                                             ProcessingMetrics,
                                             ProcessingStage, StageMetrics,
                                             get_monitoring_service)

# ============================================================================
# Test Cost Calculator
# ============================================================================


class TestCostCalculator:
    """Test cost calculation logic"""

    def test_calculate_llm_cost_claude_sonnet(self):
        """Test LLM cost calculation for Claude Sonnet"""
        cost = CostCalculator.calculate_llm_cost(
            "claude-sonnet-4-5",  # Use model name from LLM_COSTS config
            input_tokens=1000,
            output_tokens=500,
        )
        # (1000/1000 * 0.003) + (500/1000 * 0.015) = 0.003 + 0.0075 = 0.0105
        assert cost == pytest.approx(0.0105, rel=1e-4)

    def test_calculate_llm_cost_claude_haiku(self):
        """Test LLM cost calculation for Claude Haiku"""
        cost = CostCalculator.calculate_llm_cost(
            "claude-haiku-4-5",  # Use model name from LLM_COSTS config
            input_tokens=2000,
            output_tokens=1000,
        )
        # (2000/1000 * 0.001) + (1000/1000 * 0.005) = 0.002 + 0.005 = 0.007
        assert cost == pytest.approx(0.007, rel=1e-4)

    def test_calculate_llm_cost_unknown_model(self):
        """Test LLM cost calculation for unknown model (defaults to 0)"""
        cost = CostCalculator.calculate_llm_cost(
            "unknown-model", input_tokens=1000, output_tokens=500
        )
        assert cost == 0.0

    def test_calculate_embedding_cost_openai(self):
        """Test embedding cost calculation for OpenAI"""
        cost = CostCalculator.calculate_embedding_cost(
            "openai-text-embedding-3-small", tokens=10000
        )
        # (10000/1000 * 0.00002) = 0.0002
        assert cost == pytest.approx(0.0002, rel=1e-4)

    def test_calculate_embedding_cost_bge_m3(self):
        """Test embedding cost for BGE-M3 (free via Ollama)"""
        cost = CostCalculator.calculate_embedding_cost("bge-m3", tokens=10000)
        assert cost == 0.0

    def test_calculate_storage_cost(self):
        """Test storage cost calculation"""
        # 1 GB for 30 days
        cost = CostCalculator.calculate_storage_cost(
            bytes_stored=1024**3, days=30  # 1 GB
        )
        # 1 GB * $0.005 per GB per month * (30/30) = $0.005
        assert cost == pytest.approx(0.005, rel=1e-4)

        # 500 MB for 15 days
        cost = CostCalculator.calculate_storage_cost(
            bytes_stored=500 * 1024**2, days=15  # 500 MB
        )
        # 0.488 GB * $0.005 * (15/30) = $0.00122
        assert cost > 0.001 and cost < 0.002


# ============================================================================
# Test Processing Stage Enum
# ============================================================================


class TestProcessingStage:
    """Test processing stage enumeration"""

    def test_stage_values(self):
        """Test that stage enum has expected values"""
        assert ProcessingStage.UPLOAD.value == "upload"
        assert ProcessingStage.PARSING.value == "parsing"
        assert ProcessingStage.EMBEDDING_GENERATION.value == "embedding_generation"
        assert ProcessingStage.GRAPH_SYNC.value == "graph_sync"


# ============================================================================
# Test Monitoring Service
# ============================================================================


class TestMonitoringService:
    """Test monitoring service core functionality"""

    @pytest.mark.asyncio
    async def test_track_processing_context_manager(self):
        """Test processing tracking context manager"""
        monitor = MonitoringService()

        async with monitor.track_processing(
            file_id="test-123", filename="test.pdf", file_type="pdf"
        ) as metrics:
            assert isinstance(metrics, ProcessingMetrics)
            assert metrics.file_id == "test-123"
            assert metrics.filename == "test.pdf"
            assert metrics.file_type == "pdf"
            assert metrics.total_start_time > 0

        # After context exit, metrics should be calculated
        assert metrics.total_end_time is not None
        assert metrics.total_duration is not None
        assert metrics.total_duration > 0

    @pytest.mark.asyncio
    async def test_track_stage_context_manager_success(self):
        """Test stage tracking context manager on success"""
        monitor = MonitoringService()

        async with monitor.track_processing("test-123", "test.pdf", "pdf"):
            async with monitor.track_stage(
                "test-123", ProcessingStage.PARSING, metadata={"pages": 10}
            ) as stage_metrics:
                assert isinstance(stage_metrics, StageMetrics)
                assert stage_metrics.stage == "parsing"
                assert stage_metrics.start_time > 0

                # Simulate some work
                await asyncio.sleep(0.1)

            # After context exit, stage should be marked success
            assert stage_metrics.status == "success"
            assert stage_metrics.end_time is not None
            assert stage_metrics.duration is not None
            assert stage_metrics.duration >= 0.1

    @pytest.mark.asyncio
    async def test_track_stage_context_manager_failure(self):
        """Test stage tracking context manager on failure"""
        monitor = MonitoringService()

        async with monitor.track_processing("test-123", "test.pdf", "pdf"):
            with pytest.raises(ValueError):
                async with monitor.track_stage(
                    "test-123", ProcessingStage.PARSING
                ) as stage_metrics:
                    raise ValueError("Parsing failed")

            # After context exit, stage should be marked failure
            assert stage_metrics.status == "failure"
            assert stage_metrics.error == "Parsing failed"

    @pytest.mark.asyncio
    async def test_track_multiple_stages(self):
        """Test tracking multiple stages in sequence"""
        monitor = MonitoringService()

        async with monitor.track_processing("test-123", "test.pdf", "pdf") as metrics:
            # Stage 1: Parsing
            async with monitor.track_stage("test-123", ProcessingStage.PARSING):
                await asyncio.sleep(0.05)

            # Stage 2: Embedding
            async with monitor.track_stage(
                "test-123", ProcessingStage.EMBEDDING_GENERATION
            ):
                await asyncio.sleep(0.05)

            # Stage 3: Storage
            async with monitor.track_stage("test-123", ProcessingStage.STORAGE):
                await asyncio.sleep(0.05)

        # Check that all stages were tracked
        assert len(metrics.stages) == 3
        assert metrics.stages[0].stage == "parsing"
        assert metrics.stages[1].stage == "embedding_generation"
        assert metrics.stages[2].stage == "storage"

        # Check all stages have durations
        for stage in metrics.stages:
            assert stage.duration is not None
            assert stage.duration > 0

    @pytest.mark.asyncio
    async def test_record_llm_call(self):
        """Test recording LLM API call metrics"""
        monitor = MonitoringService()

        cost = await monitor.record_llm_call(
            provider="anthropic",
            model="claude-3-5-haiku-20241022",
            operation="query_expansion",
            input_tokens=1000,
            output_tokens=500,
            duration=2.5,
            status="success",
        )

        # Check cost is calculated correctly
        expected_cost = CostCalculator.calculate_llm_cost(
            "claude-3-5-haiku-20241022", 1000, 500
        )
        assert cost == expected_cost

    @pytest.mark.asyncio
    async def test_record_embedding_generation(self):
        """Test recording embedding generation metrics"""
        monitor = MonitoringService()

        cost = await monitor.record_embedding_generation(
            provider="ollama",
            model="bge-m3",
            num_embeddings=100,
            tokens=5000,
            duration=1.2,
            status="success",
        )

        # BGE-M3 via Ollama is free
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_record_storage_operation(self):
        """Test recording storage operation metrics"""
        monitor = MonitoringService()

        await monitor.record_storage_operation(
            operation="upload",
            backend="b2",
            bytes_transferred=1024 * 1024,  # 1 MB
            duration=0.5,
            status="success",
        )

        # No assertion needed - just verify no exceptions

    @pytest.mark.asyncio
    async def test_record_graph_sync(self):
        """Test recording graph sync metrics"""
        monitor = MonitoringService()

        await monitor.record_graph_sync(
            operation="create", duration=0.3, status="success"
        )

        # No assertion needed - just verify no exceptions

    @pytest.mark.asyncio
    async def test_update_queue_metrics(self):
        """Test updating queue metrics"""
        monitor = MonitoringService()

        await monitor.update_queue_metrics(
            queue_name="documents", size=42, avg_latency=5.5
        )

        # No assertion needed - just verify no exceptions

    @pytest.mark.asyncio
    async def test_log_metrics_to_database(self):
        """Test logging metrics to database"""
        mock_storage = AsyncMock()
        mock_storage.insert_processing_log = AsyncMock(return_value={"id": "log-123"})

        monitor = MonitoringService(supabase_storage=mock_storage)

        async with monitor.track_processing("test-123", "test.pdf", "pdf"):
            async with monitor.track_stage("test-123", ProcessingStage.PARSING):
                await asyncio.sleep(0.05)

        # Verify database logging was called
        assert mock_storage.insert_processing_log.called

    @pytest.mark.asyncio
    async def test_processing_with_cost_tracking(self):
        """Test full processing pipeline with cost tracking"""
        monitor = MonitoringService()

        async with monitor.track_processing("test-123", "test.pdf", "pdf") as metrics:
            # Stage 1: Parsing
            async with monitor.track_stage(
                "test-123", ProcessingStage.PARSING
            ) as parsing_stage:
                await asyncio.sleep(0.05)
                parsing_stage.cost = 0.0  # Free

            # Stage 2: Embedding (with cost)
            async with monitor.track_stage(
                "test-123", ProcessingStage.EMBEDDING_GENERATION
            ) as embedding_stage:
                await asyncio.sleep(0.05)
                # Simulate embedding cost
                embedding_stage.cost = await monitor.record_embedding_generation(
                    provider="ollama",
                    model="bge-m3",
                    num_embeddings=50,
                    tokens=2000,
                    duration=0.5,
                )

            # Stage 3: LLM processing (with cost)
            async with monitor.track_stage(
                "test-123", ProcessingStage.CLASSIFICATION
            ) as llm_stage:
                await asyncio.sleep(0.05)
                llm_stage.cost = await monitor.record_llm_call(
                    provider="anthropic",
                    model="claude-3-5-haiku-20241022",
                    operation="classification",
                    input_tokens=500,
                    output_tokens=250,
                    duration=1.0,
                )

        # Check total cost is sum of all stage costs
        assert metrics.total_cost > 0

    @pytest.mark.asyncio
    async def test_resource_usage_tracking(self):
        """Test CPU and memory usage tracking"""
        monitor = MonitoringService()

        async with monitor.track_processing("test-123", "test.pdf", "pdf"):
            async with monitor.track_stage(
                "test-123", ProcessingStage.PARSING
            ) as stage_metrics:
                # Simulate some work
                await asyncio.sleep(0.1)

        # Check resource metrics were recorded
        assert stage_metrics.cpu_usage is not None
        assert stage_metrics.memory_usage is not None


# ============================================================================
# Test Singleton Pattern
# ============================================================================


class TestSingleton:
    """Test singleton pattern for monitoring service"""

    def test_get_monitoring_service_singleton(self):
        """Test get_monitoring_service returns same instance"""
        service1 = get_monitoring_service()
        service2 = get_monitoring_service()

        assert service1 is service2

    def test_get_monitoring_service_with_storage(self):
        """Test get_monitoring_service with storage parameter"""
        mock_storage = Mock()
        service = get_monitoring_service(supabase_storage=mock_storage)

        assert isinstance(service, MonitoringService)


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for complete monitoring flow"""

    @pytest.mark.asyncio
    async def test_full_document_processing_pipeline(self):
        """Test complete document processing with metrics"""
        mock_storage = AsyncMock()
        mock_storage.insert_processing_log = AsyncMock(return_value={"id": "log-123"})

        monitor = MonitoringService(supabase_storage=mock_storage)

        async with monitor.track_processing(
            file_id="doc-123", filename="contract.pdf", file_type="pdf"
        ) as metrics:
            # 1. Upload
            async with monitor.track_stage("doc-123", ProcessingStage.UPLOAD):
                await asyncio.sleep(0.01)

            # 2. Validation
            async with monitor.track_stage("doc-123", ProcessingStage.VALIDATION):
                await asyncio.sleep(0.01)

            # 3. Parsing (with metadata)
            async with monitor.track_stage(
                "doc-123",
                ProcessingStage.PARSING,
                metadata={"pages": 25, "parser": "llama_parse"},
            ) as parsing:
                await asyncio.sleep(0.05)
                parsing.cost = 0.01  # Parsing cost

            # 4. Metadata Extraction
            async with monitor.track_stage(
                "doc-123", ProcessingStage.METADATA_EXTRACTION
            ):
                await asyncio.sleep(0.02)

            # 5. Chunking
            async with monitor.track_stage(
                "doc-123",
                ProcessingStage.CHUNKING,
                metadata={"chunks": 150, "avg_chunk_size": 512},
            ):
                await asyncio.sleep(0.03)

            # 6. Embedding Generation
            async with monitor.track_stage(
                "doc-123", ProcessingStage.EMBEDDING_GENERATION
            ) as embedding:
                embedding.cost = await monitor.record_embedding_generation(
                    provider="ollama",
                    model="bge-m3",
                    num_embeddings=150,
                    tokens=76800,  # 150 chunks * 512 tokens
                    duration=2.5,
                )
                await asyncio.sleep(0.05)

            # 7. Storage
            async with monitor.track_stage("doc-123", ProcessingStage.STORAGE):
                await monitor.record_storage_operation(
                    operation="upload",
                    backend="b2",
                    bytes_transferred=5 * 1024 * 1024,  # 5 MB
                    duration=1.2,
                )
                await asyncio.sleep(0.02)

            # 8. Graph Sync
            async with monitor.track_stage("doc-123", ProcessingStage.GRAPH_SYNC):
                await monitor.record_graph_sync(operation="create", duration=0.8)
                await asyncio.sleep(0.03)

            # 9. Classification (with LLM)
            async with monitor.track_stage(
                "doc-123", ProcessingStage.CLASSIFICATION
            ) as classification:
                classification.cost = await monitor.record_llm_call(
                    provider="anthropic",
                    model="claude-3-5-haiku-20241022",
                    operation="classification",
                    input_tokens=1000,
                    output_tokens=200,
                    duration=1.5,
                )
                await asyncio.sleep(0.05)

        # Verify all stages were tracked
        assert len(metrics.stages) == 9
        assert all(stage.duration is not None for stage in metrics.stages)
        assert all(stage.status == "success" for stage in metrics.stages)

        # Verify total cost
        assert metrics.total_cost > 0

        # Verify database logging
        assert mock_storage.insert_processing_log.call_count == 9

    @pytest.mark.asyncio
    async def test_partial_failure_scenario(self):
        """Test handling of partial failures in pipeline"""
        monitor = MonitoringService()

        async with monitor.track_processing("doc-456", "test.pdf", "pdf") as metrics:
            # Stage 1: Success
            async with monitor.track_stage("doc-456", ProcessingStage.UPLOAD):
                await asyncio.sleep(0.01)

            # Stage 2: Success
            async with monitor.track_stage("doc-456", ProcessingStage.PARSING):
                await asyncio.sleep(0.01)

            # Stage 3: Failure
            try:
                async with monitor.track_stage(
                    "doc-456", ProcessingStage.EMBEDDING_GENERATION
                ) as stage:
                    raise ConnectionError("Embedding service unavailable")
            except ConnectionError:
                pass  # Expected

        # Verify metrics were still collected
        assert len(metrics.stages) == 3
        assert metrics.stages[0].status == "success"
        assert metrics.stages[1].status == "success"
        assert metrics.stages[2].status == "failure"
        assert metrics.stages[2].error == "Embedding service unavailable"
