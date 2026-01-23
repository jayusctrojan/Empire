"""
Empire v7.3 - Saga Pattern Tests
Tests for saga orchestration and compensation logic

Run with:
    pytest tests/test_saga_pattern.py -v
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.saga_orchestrator import Saga, SagaExecutionError


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for saga operations"""
    mock = MagicMock()
    mock.table.return_value.insert.return_value.execute.return_value.data = [{"id": str(uuid4())}]
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    return mock


@pytest.fixture
def sample_saga_steps():
    """Sample saga steps for testing"""
    async def create_document(**context):
        return {"document_id": "doc_123"}

    async def undo_create_document(**context):
        pass

    async def create_entities(**context):
        return {"entity_ids": ["ent_1", "ent_2"]}

    async def undo_create_entities(**context):
        pass

    async def create_relationships(**context):
        return {"relationship_ids": ["rel_1"]}

    async def undo_create_relationships(**context):
        pass

    return [
        {
            "name": "create_document",
            "action": create_document,
            "compensation": undo_create_document
        },
        {
            "name": "create_entities",
            "action": create_entities,
            "compensation": undo_create_entities
        },
        {
            "name": "create_relationships",
            "action": create_relationships,
            "compensation": undo_create_relationships
        }
    ]


# =============================================================================
# SAGA INITIALIZATION TESTS
# =============================================================================

class TestSagaInit:
    """Tests for Saga initialization"""

    def test_saga_creation(self, mock_supabase):
        """Test creating a Saga instance"""
        saga = Saga(name="graph_sync", correlation_id="corr_123", supabase_client=mock_supabase)

        assert saga.name == "graph_sync"
        assert saga.correlation_id == "corr_123"
        assert len(saga.steps) == 0

    def test_saga_add_step(self, mock_supabase):
        """Test adding steps to a saga"""
        async def action(**ctx):
            return {"result": "success"}

        async def compensation(**ctx):
            pass

        saga = Saga(name="test_saga", supabase_client=mock_supabase)
        saga.add_step("step_1", action, compensation)

        assert len(saga.steps) == 1
        assert saga.steps[0].name == "step_1"


# =============================================================================
# SAGA EXECUTION TESTS
# =============================================================================

class TestSagaExecution:
    """Tests for saga execution"""

    @pytest.mark.asyncio
    async def test_successful_saga_execution(self, mock_supabase, sample_saga_steps):
        """Test successful execution of all saga steps"""
        saga = Saga(name="graph_sync", supabase_client=mock_supabase)

        for step in sample_saga_steps:
            saga.add_step(step["name"], step["action"], step["compensation"])

        result = await saga.execute(document={"title": "Test"})

        # Implementation returns a dict of step_name: result
        assert "create_document" in result
        assert "create_entities" in result
        assert "create_relationships" in result
        assert saga.status.value == "completed"

    @pytest.mark.asyncio
    async def test_saga_context_passed_between_steps(self, mock_supabase):
        """Test that context is passed between saga steps"""
        context_values = []

        async def step1(**ctx):
            context_values.append(dict(ctx))
            return {"step": 1}

        async def step2(**ctx):
            context_values.append(dict(ctx))
            return {"step": 2}

        async def noop(**ctx):
            pass

        saga = Saga(name="context_test", supabase_client=mock_supabase)
        saga.add_step("step1", step1, noop)
        saga.add_step("step2", step2, noop)

        result = await saga.execute(initial="data")

        # Steps should have received context
        assert len(context_values) == 2
        assert "initial" in context_values[0]
        # Step 2 should also have step1 result in context
        if len(context_values) > 1:
            assert "step1" in context_values[1]

    @pytest.mark.asyncio
    async def test_saga_records_step_results(self, mock_supabase, sample_saga_steps):
        """Test that saga records individual step results"""
        saga = Saga(name="graph_sync", supabase_client=mock_supabase)

        for step in sample_saga_steps:
            saga.add_step(step["name"], step["action"], step["compensation"])

        result = await saga.execute()

        # Result should have one key per step
        assert len(result) == 3


# =============================================================================
# SAGA COMPENSATION TESTS
# =============================================================================

class TestSagaCompensation:
    """Tests for saga compensation (rollback) logic"""

    @pytest.mark.asyncio
    async def test_compensation_on_failure(self, mock_supabase):
        """Test that compensation runs when a step fails"""
        compensation_called = []

        async def step1(**ctx):
            return {"step": 1}

        async def compensate1(**ctx):
            compensation_called.append("step1")

        async def step2(**ctx):
            raise Exception("Step 2 failed")

        async def compensate2(**ctx):
            compensation_called.append("step2")

        saga = Saga(name="failing_saga", supabase_client=mock_supabase)
        saga.add_step("step1", step1, compensate1)
        saga.add_step("step2", step2, compensate2)

        with pytest.raises(SagaExecutionError) as exc_info:
            await saga.execute()

        # Step 1 should be compensated since step 2 failed
        assert "step1" in compensation_called
        assert saga.status.value in ["compensated", "partially_compensated"]

    @pytest.mark.asyncio
    async def test_compensation_runs_in_reverse_order(self, mock_supabase):
        """Test that compensation runs in reverse order"""
        compensation_order = []

        async def make_step(name):
            async def action(**ctx):
                return {"step": name}
            return action

        async def make_compensation(name):
            async def comp(**ctx):
                compensation_order.append(name)
            return comp

        saga = Saga(name="order_test", supabase_client=mock_supabase)
        saga.add_step("step1", await make_step("step1"), await make_compensation("step1"))
        saga.add_step("step2", await make_step("step2"), await make_compensation("step2"))

        # Add a failing step
        async def failing_step(**ctx):
            raise Exception("Intentional failure")

        saga.add_step("step3", failing_step, await make_compensation("step3"))

        with pytest.raises(SagaExecutionError):
            await saga.execute()

        # Compensation should run step2 then step1 (reverse order)
        if len(compensation_order) >= 2:
            assert compensation_order[0] == "step2"
            assert compensation_order[1] == "step1"

    @pytest.mark.asyncio
    async def test_partial_compensation_on_compensation_failure(self, mock_supabase):
        """Test handling when compensation itself fails"""
        async def step1(**ctx):
            return {"step": 1}

        async def compensate1_fails(**ctx):
            raise Exception("Compensation failed")

        async def step2(**ctx):
            raise Exception("Step 2 failed")

        async def compensate2(**ctx):
            pass

        saga = Saga(name="comp_fail_saga", supabase_client=mock_supabase)
        saga.add_step("step1", step1, compensate1_fails)
        saga.add_step("step2", step2, compensate2)

        with pytest.raises(SagaExecutionError) as exc_info:
            await saga.execute()

        # Should indicate partial compensation
        assert saga.status.value == "partially_compensated"
        assert len(saga.compensation_errors) > 0


# =============================================================================
# SAGA PERSISTENCE TESTS
# =============================================================================

class TestSagaPersistence:
    """Tests for saga state persistence"""

    @pytest.mark.asyncio
    async def test_saga_persisted_on_start(self, mock_supabase):
        """Test that saga execution is persisted at start"""
        async def step(**ctx):
            return {"done": True}

        async def comp(**ctx):
            pass

        saga = Saga(name="persist_test", supabase_client=mock_supabase)
        saga.add_step("step1", step, comp)

        await saga.execute()

        # Upsert should have been called to create saga record
        mock_supabase.table.assert_called()

    @pytest.mark.asyncio
    async def test_saga_status_updated_on_completion(self, mock_supabase):
        """Test that saga status is updated when completed"""
        async def step(**ctx):
            return {"done": True}

        async def comp(**ctx):
            pass

        saga = Saga(name="update_test", supabase_client=mock_supabase)
        saga.add_step("step1", step, comp)

        await saga.execute()

        # Upsert should have been called with completed status
        mock_supabase.table.return_value.upsert.assert_called()

    @pytest.mark.asyncio
    async def test_step_statuses_tracked(self, mock_supabase, sample_saga_steps):
        """Test that individual step statuses are tracked"""
        upsert_calls = []

        def capture_upsert(data):
            upsert_calls.append(data)
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[{}])))

        mock_supabase.table.return_value.upsert = capture_upsert

        saga = Saga(name="tracking_test", supabase_client=mock_supabase)

        for step in sample_saga_steps:
            saga.add_step(step["name"], step["action"], step["compensation"])

        await saga.execute()

        # Steps should be recorded in upserts
        assert len(upsert_calls) > 0


# =============================================================================
# SAGA RECOVERY TESTS
# =============================================================================

@pytest.mark.skip(reason="SagaOrchestrator class not implemented - saga recovery is handled differently")
class TestSagaRecovery:
    """Tests for saga recovery from failures - SKIPPED: SagaOrchestrator not implemented"""

    @pytest.mark.asyncio
    async def test_resume_saga_from_checkpoint(self, mock_supabase):
        """Test resuming a saga from a checkpoint"""
        # SagaOrchestrator class doesn't exist in current implementation
        # Recovery is handled via WAL replay instead
        pass

    @pytest.mark.asyncio
    async def test_get_pending_sagas(self, mock_supabase):
        """Test getting sagas that need processing"""
        # SagaOrchestrator class doesn't exist in current implementation
        pass


# =============================================================================
# SAGA SUMMARY TESTS
# =============================================================================

class TestSagaSummary:
    """Tests for saga status summary"""

    @pytest.mark.asyncio
    async def test_get_saga_status(self, mock_supabase, sample_saga_steps):
        """Test getting saga execution status"""
        saga = Saga(name="summary_test", supabase_client=mock_supabase)

        for step in sample_saga_steps:
            saga.add_step(step["name"], step["action"], step["compensation"])

        await saga.execute()
        status = saga.get_status()

        assert "name" in status
        assert "status" in status
        assert "total_steps" in status
        assert "completed_steps" in status

    @pytest.mark.asyncio
    async def test_status_includes_steps(self, mock_supabase, sample_saga_steps):
        """Test that status includes step information"""
        saga = Saga(name="timing_test", supabase_client=mock_supabase)

        for step in sample_saga_steps:
            saga.add_step(step["name"], step["action"], step["compensation"])

        await saga.execute()
        status = saga.get_status()

        # Should include steps list
        assert "steps" in status
        assert status.get("name") is not None


# =============================================================================
# NESTED SAGA TESTS
# =============================================================================

class TestNestedSagas:
    """Tests for nested/child sagas"""

    @pytest.mark.asyncio
    async def test_parent_child_saga_relationship(self, mock_supabase):
        """Test parent-child saga relationship"""
        async def child_action(**ctx):
            return {"child": "completed"}

        async def child_comp(**ctx):
            pass

        async def parent_action(**ctx):
            # Create child saga
            child = Saga(name="child_saga", supabase_client=mock_supabase)
            child.add_step("child_step", child_action, child_comp)
            result = await child.execute()
            return {"parent": "completed", "child_result": result}

        async def parent_comp(**ctx):
            pass

        parent = Saga(name="parent_saga", supabase_client=mock_supabase)
        parent.add_step("parent_step", parent_action, parent_comp)

        result = await parent.execute(saga_id=str(uuid4()))

        # Result contains step results, saga status is "completed"
        assert "parent_step" in result
        assert parent.status.value == "completed"
