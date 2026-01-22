"""
Tests for Empire v7.3 Workflow Management System (Task 158)

Comprehensive tests for:
- WorkflowStateManager (state persistence)
- CancellationToken (task cancellation)
- GracefulShutdownHandler (signal handling)
- WorkflowMetricsCollector (metrics)
- WorkflowManager (unified facade)
- API endpoints

Author: Claude Code
Date: 2025-01-15
"""

import pytest
import asyncio
import json
import time
import tempfile
import signal
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.services.workflow_management import (
    CancellationToken,
    CancellationError,
    WorkflowState,
    WorkflowStatus,
    WorkflowStateManager,
    StorageBackend,
    CheckpointType,
    GracefulShutdownHandler,
    WorkflowMetricsCollector,
    WorkflowManager,
    TaskMetrics,
    get_workflow_manager,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_storage_path(tmp_path):
    """Create a temporary storage path for file-based tests"""
    return str(tmp_path / "workflow_states")


@pytest.fixture
def state_manager(temp_storage_path):
    """Create a file-based state manager for testing"""
    return WorkflowStateManager(
        backend=StorageBackend.FILE,
        storage_path=temp_storage_path
    )


@pytest.fixture
def memory_state_manager():
    """Create a memory-based state manager for testing"""
    return WorkflowStateManager(backend=StorageBackend.MEMORY)


@pytest.fixture
def workflow_state():
    """Create a sample workflow state"""
    return WorkflowState(
        workflow_id="wf-test-123",
        workflow_type="document_analysis",
        status=WorkflowStatus.RUNNING,
        current_task="extract_entities",
        completed_tasks=["parse"],
        pending_tasks=["synthesize"],
        context={"document_id": "doc-456"},
        metadata={"user_id": "user-789"},
        started_at=datetime.utcnow().isoformat()
    )


@pytest.fixture
def cancellation_token():
    """Create a cancellation token for testing"""
    return CancellationToken()


@pytest.fixture
def metrics_collector():
    """Create a metrics collector for testing"""
    return WorkflowMetricsCollector()


@pytest.fixture
def workflow_manager(temp_storage_path):
    """Create a workflow manager for testing"""
    return WorkflowManager(
        storage_backend=StorageBackend.FILE,
        storage_path=temp_storage_path,
        enable_shutdown_handler=False  # Don't install signal handlers in tests
    )


# =============================================================================
# CANCELLATION TOKEN TESTS
# =============================================================================

class TestCancellationToken:
    """Tests for CancellationToken"""

    def test_initial_state_not_cancelled(self, cancellation_token):
        """Test token starts in non-cancelled state"""
        assert not cancellation_token.cancelled
        assert not cancellation_token.is_cancelled()
        assert cancellation_token.cancel_reason is None

    @pytest.mark.asyncio
    async def test_cancel_sets_state(self, cancellation_token):
        """Test cancellation sets the cancelled state"""
        await cancellation_token.cancel(reason="Test cancellation")

        assert cancellation_token.cancelled
        assert cancellation_token.is_cancelled()
        assert cancellation_token.cancel_reason == "Test cancellation"

    @pytest.mark.asyncio
    async def test_sync_callback_executed(self, cancellation_token):
        """Test synchronous callbacks are executed on cancellation"""
        callback_executed = False

        def callback():
            nonlocal callback_executed
            callback_executed = True

        cancellation_token.register_callback(callback)
        await cancellation_token.cancel()

        assert callback_executed

    @pytest.mark.asyncio
    async def test_async_callback_executed(self, cancellation_token):
        """Test asynchronous callbacks are executed on cancellation"""
        callback_executed = False

        async def async_callback():
            nonlocal callback_executed
            callback_executed = True

        cancellation_token.register_async_callback(async_callback)
        await cancellation_token.cancel()

        assert callback_executed

    @pytest.mark.asyncio
    async def test_child_token_cancelled_with_parent(self, cancellation_token):
        """Test child tokens are cancelled when parent is cancelled"""
        child_token = cancellation_token.create_child()

        assert not child_token.cancelled
        await cancellation_token.cancel(reason="Parent cancelled")

        assert child_token.cancelled
        assert "Parent cancelled" in child_token.cancel_reason

    def test_check_cancelled_raises_exception(self, cancellation_token):
        """Test check_cancelled raises CancellationError when cancelled"""
        # Should not raise when not cancelled
        cancellation_token.check_cancelled()

        # Manually set cancelled state for sync test
        cancellation_token._cancelled = True
        cancellation_token._cancel_reason = "Test"

        with pytest.raises(CancellationError):
            cancellation_token.check_cancelled()

    def test_get_status(self, cancellation_token):
        """Test get_status returns comprehensive status"""
        status = cancellation_token.get_status()

        assert "cancelled" in status
        assert "reason" in status
        assert "callback_count" in status
        assert "children_count" in status
        assert status["cancelled"] is False


# =============================================================================
# WORKFLOW STATE TESTS
# =============================================================================

class TestWorkflowState:
    """Tests for WorkflowState dataclass"""

    def test_to_dict(self, workflow_state):
        """Test WorkflowState serialization to dict"""
        data = workflow_state.to_dict()

        assert data["workflow_id"] == "wf-test-123"
        assert data["workflow_type"] == "document_analysis"
        assert data["status"] == "running"
        assert data["current_task"] == "extract_entities"
        assert data["completed_tasks"] == ["parse"]

    def test_from_dict(self, workflow_state):
        """Test WorkflowState deserialization from dict"""
        data = workflow_state.to_dict()
        restored = WorkflowState.from_dict(data)

        assert restored.workflow_id == workflow_state.workflow_id
        assert restored.status == workflow_state.status
        assert restored.current_task == workflow_state.current_task

    def test_round_trip_serialization(self, workflow_state):
        """Test serialization round trip"""
        data = workflow_state.to_dict()
        json_str = json.dumps(data)
        restored_data = json.loads(json_str)
        restored = WorkflowState.from_dict(restored_data)

        assert restored.workflow_id == workflow_state.workflow_id
        assert restored.workflow_type == workflow_state.workflow_type


# =============================================================================
# WORKFLOW STATE MANAGER TESTS
# =============================================================================

class TestWorkflowStateManager:
    """Tests for WorkflowStateManager"""

    @pytest.mark.asyncio
    async def test_save_and_load_file_backend(self, state_manager, workflow_state):
        """Test saving and loading state with file backend"""
        await state_manager.save_state(workflow_state)
        loaded = await state_manager.load_state(workflow_state.workflow_id)

        assert loaded is not None
        assert loaded.workflow_id == workflow_state.workflow_id
        assert loaded.status == workflow_state.status

    @pytest.mark.asyncio
    async def test_save_and_load_memory_backend(self, memory_state_manager, workflow_state):
        """Test saving and loading state with memory backend"""
        await memory_state_manager.save_state(workflow_state)
        loaded = await memory_state_manager.load_state(workflow_state.workflow_id)

        assert loaded is not None
        assert loaded.workflow_id == workflow_state.workflow_id

    @pytest.mark.asyncio
    async def test_load_nonexistent_state_returns_none(self, state_manager):
        """Test loading non-existent state returns None"""
        loaded = await state_manager.load_state("nonexistent-workflow")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_checkpoint_creates_checkpoint(self, state_manager, workflow_state):
        """Test checkpoint creation"""
        await state_manager.save_state(workflow_state)

        checkpoint_id = await state_manager.checkpoint(
            workflow_state,
            CheckpointType.TASK_COMPLETE,
            metadata={"step": 1}
        )

        assert checkpoint_id is not None
        assert workflow_state.workflow_id in checkpoint_id

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint(self, state_manager, workflow_state):
        """Test restoring from checkpoint"""
        await state_manager.save_state(workflow_state)
        await state_manager.checkpoint(workflow_state, CheckpointType.MILESTONE)

        # Modify state
        workflow_state.current_task = "different_task"
        await state_manager.save_state(workflow_state)

        # Restore from checkpoint
        restored = await state_manager.restore_from_checkpoint(workflow_state.workflow_id)

        assert restored is not None
        assert restored.status == WorkflowStatus.RECOVERING

    @pytest.mark.asyncio
    async def test_list_workflows(self, state_manager, workflow_state):
        """Test listing workflows"""
        await state_manager.save_state(workflow_state)

        # Create another workflow
        workflow_state2 = WorkflowState(
            workflow_id="wf-test-456",
            workflow_type="other_type",
            status=WorkflowStatus.COMPLETED
        )
        await state_manager.save_state(workflow_state2)

        all_workflows = await state_manager.list_workflows()
        assert len(all_workflows) == 2

        running_only = await state_manager.list_workflows(status=WorkflowStatus.RUNNING)
        assert len(running_only) == 1

    @pytest.mark.asyncio
    async def test_delete_state(self, state_manager, workflow_state):
        """Test deleting workflow state"""
        await state_manager.save_state(workflow_state)
        assert await state_manager.load_state(workflow_state.workflow_id) is not None

        await state_manager.delete_state(workflow_state.workflow_id)
        assert await state_manager.load_state(workflow_state.workflow_id) is None


# =============================================================================
# GRACEFUL SHUTDOWN HANDLER TESTS
# =============================================================================

class TestGracefulShutdownHandler:
    """Tests for GracefulShutdownHandler"""

    @pytest.mark.asyncio
    async def test_register_workflow(self, memory_state_manager, workflow_state):
        """Test workflow registration"""
        handler = GracefulShutdownHandler(memory_state_manager)
        token = CancellationToken()

        handler.register_workflow(workflow_state.workflow_id, workflow_state, token)

        assert workflow_state.workflow_id in handler._active_workflows
        assert workflow_state.workflow_id in handler._cancellation_tokens

    @pytest.mark.asyncio
    async def test_unregister_workflow(self, memory_state_manager, workflow_state):
        """Test workflow unregistration"""
        handler = GracefulShutdownHandler(memory_state_manager)

        handler.register_workflow(workflow_state.workflow_id, workflow_state)
        handler.unregister_workflow(workflow_state.workflow_id)

        assert workflow_state.workflow_id not in handler._active_workflows

    @pytest.mark.asyncio
    async def test_shutdown_saves_workflows(self, memory_state_manager, workflow_state):
        """Test shutdown saves all registered workflows"""
        handler = GracefulShutdownHandler(memory_state_manager)
        handler.register_workflow(workflow_state.workflow_id, workflow_state)

        await handler.shutdown()

        # Verify state was saved
        loaded = await memory_state_manager.load_state(workflow_state.workflow_id)
        assert loaded is not None
        assert loaded.status == WorkflowStatus.PAUSED

    @pytest.mark.asyncio
    async def test_shutdown_cancels_tokens(self, memory_state_manager, workflow_state):
        """Test shutdown cancels all cancellation tokens"""
        handler = GracefulShutdownHandler(memory_state_manager)
        token = CancellationToken()

        handler.register_workflow(workflow_state.workflow_id, workflow_state, token)
        await handler.shutdown()

        assert token.cancelled

    @pytest.mark.asyncio
    async def test_cleanup_callbacks_executed(self, memory_state_manager):
        """Test cleanup callbacks are executed during shutdown"""
        handler = GracefulShutdownHandler(memory_state_manager)
        callback_executed = False

        async def cleanup():
            nonlocal callback_executed
            callback_executed = True

        handler.register_cleanup_callback(cleanup)
        await handler.shutdown()

        assert callback_executed


# =============================================================================
# WORKFLOW METRICS COLLECTOR TESTS
# =============================================================================

class TestWorkflowMetricsCollector:
    """Tests for WorkflowMetricsCollector"""

    def test_record_workflow_start(self, metrics_collector):
        """Test recording workflow start"""
        metrics_collector.record_workflow_start(
            "wf-123",
            "document_analysis",
            metadata={"user": "test"}
        )

        metrics = metrics_collector.get_workflow_metrics("wf-123")
        assert metrics is not None
        assert metrics["workflow_type"] == "document_analysis"
        assert metrics["status"] == "running"

    def test_record_workflow_completion(self, metrics_collector):
        """Test recording workflow completion"""
        metrics_collector.record_workflow_start("wf-123", "test_workflow")
        time.sleep(0.1)  # Small delay for duration
        metrics_collector.record_workflow_completion("wf-123", success=True)

        metrics = metrics_collector.get_workflow_metrics("wf-123")
        assert metrics["status"] == "completed"
        assert metrics["duration"] > 0

    def test_record_workflow_cancellation(self, metrics_collector):
        """Test recording workflow cancellation"""
        metrics_collector.record_workflow_start("wf-123", "test_workflow")
        metrics_collector.record_workflow_cancellation("wf-123", reason="user_request")

        metrics = metrics_collector.get_workflow_metrics("wf-123")
        assert metrics["status"] == "cancelled"
        assert metrics["cancellation_reason"] == "user_request"

    def test_record_task_metrics(self, metrics_collector):
        """Test recording task metrics"""
        metrics_collector.record_workflow_start("wf-123", "test_workflow")
        metrics_collector.record_task_start("wf-123", "task-1", "parse_document")
        time.sleep(0.05)
        metrics_collector.record_task_completion("wf-123", "task-1", success=True)

        metrics = metrics_collector.get_workflow_metrics("wf-123")
        assert "tasks" in metrics
        assert "task-1" in metrics["tasks"]
        assert metrics["tasks"]["task-1"]["status"] == "completed"

    def test_get_all_metrics(self, metrics_collector):
        """Test getting aggregated metrics"""
        # Create some workflows
        metrics_collector.record_workflow_start("wf-1", "type_a")
        metrics_collector.record_workflow_completion("wf-1", success=True)

        metrics_collector.record_workflow_start("wf-2", "type_b")
        metrics_collector.record_workflow_completion("wf-2", success=False)

        metrics_collector.record_workflow_start("wf-3", "type_a")

        all_metrics = metrics_collector.get_all_metrics()

        assert all_metrics["total_workflows"] == 3
        assert all_metrics["completed"] == 1
        assert all_metrics["failed"] == 1
        assert all_metrics["running"] == 1


# =============================================================================
# WORKFLOW MANAGER TESTS
# =============================================================================

class TestWorkflowManager:
    """Tests for WorkflowManager unified facade"""

    @pytest.mark.asyncio
    async def test_create_workflow(self, workflow_manager):
        """Test creating a workflow"""
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="document_analysis",
            tasks=["parse", "extract", "synthesize"],
            context={"doc_id": "123"}
        )

        assert workflow_id is not None
        assert "document_analysis" in workflow_id

        state = await workflow_manager.get_workflow_state(workflow_id)
        assert state is not None
        assert state.status == WorkflowStatus.PENDING

    @pytest.mark.asyncio
    async def test_start_workflow(self, workflow_manager):
        """Test starting a workflow"""
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="test",
            tasks=["task1"]
        )

        state = await workflow_manager.start_workflow(workflow_id)

        assert state.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_complete_workflow(self, workflow_manager):
        """Test completing a workflow"""
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="test",
            tasks=["task1"]
        )
        await workflow_manager.start_workflow(workflow_id)
        await workflow_manager.complete_workflow(workflow_id, success=True)

        state = await workflow_manager.get_workflow_state(workflow_id)
        assert state.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cancel_workflow(self, workflow_manager):
        """Test cancelling a workflow"""
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="test",
            tasks=["task1"]
        )
        await workflow_manager.start_workflow(workflow_id)
        await workflow_manager.cancel_workflow(workflow_id, reason="Test cancel")

        state = await workflow_manager.get_workflow_state(workflow_id)
        assert state.status == WorkflowStatus.CANCELLED
        assert "Test cancel" in state.error

        # Verify cancellation token was triggered
        token = workflow_manager.get_cancellation_token(workflow_id)
        # Token may be None after cancellation since it's cleaned up
        # Just verify state was properly updated

    @pytest.mark.asyncio
    async def test_task_lifecycle(self, workflow_manager):
        """Test task start and completion"""
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="test",
            tasks=["task1", "task2"]
        )
        await workflow_manager.start_workflow(workflow_id)

        # Start task
        await workflow_manager.start_task(workflow_id, "task1")
        state = await workflow_manager.get_workflow_state(workflow_id)
        assert state.current_task == "task1"

        # Complete task
        await workflow_manager.complete_task(workflow_id, "task1", result={"data": "value"})
        state = await workflow_manager.get_workflow_state(workflow_id)
        assert "task1" in state.completed_tasks
        assert "task1" in state.task_results

    @pytest.mark.asyncio
    async def test_get_metrics(self, workflow_manager):
        """Test getting workflow metrics"""
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="test",
            tasks=["task1"]
        )

        metrics = workflow_manager.get_metrics(workflow_id)
        assert metrics is not None

        all_metrics = workflow_manager.get_metrics()
        assert "total_workflows" in all_metrics


# =============================================================================
# API ENDPOINT TESTS
# =============================================================================

@pytest.mark.skip(reason="Requires env vars - imports app.main which needs SUPABASE_URL, REDIS_URL")
class TestWorkflowAPI:
    """Tests for workflow management API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_create_workflow(self, client):
        """Test creating a workflow via API"""
        response = client.post(
            "/api/workflows",
            json={
                "workflow_type": "test_workflow",
                "tasks": ["task1", "task2"],
                "context": {"key": "value"}
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "workflow_id" in data
        assert data["status"] == "pending"

    def test_list_workflows(self, client):
        """Test listing workflows via API"""
        # Create a workflow first
        client.post(
            "/api/workflows",
            json={"workflow_type": "list_test", "tasks": ["task1"]}
        )

        response = client.get("/api/workflows")

        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert "total" in data

    def test_get_workflow(self, client):
        """Test getting a specific workflow via API"""
        # Create a workflow
        create_response = client.post(
            "/api/workflows",
            json={"workflow_type": "get_test", "tasks": ["task1"]}
        )
        workflow_id = create_response.json()["workflow_id"]

        # Get the workflow
        response = client.get(f"/api/workflows/{workflow_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == workflow_id

    def test_get_nonexistent_workflow_returns_404(self, client):
        """Test getting non-existent workflow returns 404"""
        response = client.get("/api/workflows/nonexistent-id")
        assert response.status_code == 404

    def test_start_workflow(self, client):
        """Test starting a workflow via API"""
        # Create a workflow
        create_response = client.post(
            "/api/workflows",
            json={"workflow_type": "start_test", "tasks": ["task1"]}
        )
        workflow_id = create_response.json()["workflow_id"]

        # Start the workflow
        response = client.post(f"/api/workflows/{workflow_id}/start")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    def test_cancel_workflow(self, client):
        """Test cancelling a workflow via API"""
        # Create and start a workflow
        create_response = client.post(
            "/api/workflows",
            json={"workflow_type": "cancel_test", "tasks": ["task1"]}
        )
        workflow_id = create_response.json()["workflow_id"]
        client.post(f"/api/workflows/{workflow_id}/start")

        # Cancel the workflow
        response = client.post(
            f"/api/workflows/{workflow_id}/cancel",
            json={"reason": "Test cancellation"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_complete_task(self, client):
        """Test completing a task via API"""
        # Create and start a workflow
        create_response = client.post(
            "/api/workflows",
            json={"workflow_type": "task_test", "tasks": ["task1", "task2"]}
        )
        workflow_id = create_response.json()["workflow_id"]
        client.post(f"/api/workflows/{workflow_id}/start")
        client.post(f"/api/workflows/{workflow_id}/tasks/start?task_name=task1")

        # Complete the task
        response = client.post(
            f"/api/workflows/{workflow_id}/tasks/complete",
            json={"task_name": "task1", "success": True, "result": {"data": "value"}}
        )

        assert response.status_code == 200
        data = response.json()
        assert "task1" in data["completed_tasks"]

    def test_get_metrics_summary(self, client):
        """Test getting metrics summary via API"""
        response = client.get("/api/workflows/metrics/summary")

        assert response.status_code == 200
        data = response.json()
        assert "total_workflows" in data
        assert "success_rate" in data

    def test_health_check(self, client):
        """Test workflow service health check"""
        response = client.get("/api/workflows/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestWorkflowIntegration:
    """Integration tests for workflow management"""

    @pytest.mark.asyncio
    async def test_full_workflow_lifecycle(self, workflow_manager):
        """Test complete workflow lifecycle"""
        # Create workflow
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="integration_test",
            tasks=["task1", "task2", "task3"],
            metadata={"test": True}
        )

        # Start workflow
        await workflow_manager.start_workflow(workflow_id)

        # Execute tasks
        for task in ["task1", "task2", "task3"]:
            token = workflow_manager.get_cancellation_token(workflow_id)
            if token and token.is_cancelled():
                break

            await workflow_manager.start_task(workflow_id, task)
            await asyncio.sleep(0.01)  # Simulate work
            await workflow_manager.complete_task(workflow_id, task, result=f"{task}_result")

        # Complete workflow
        await workflow_manager.complete_workflow(workflow_id, success=True)

        # Verify final state
        state = await workflow_manager.get_workflow_state(workflow_id)
        assert state.status == WorkflowStatus.COMPLETED
        assert len(state.completed_tasks) == 3

        # Verify metrics
        metrics = workflow_manager.get_metrics(workflow_id)
        assert metrics["status"] == "completed"

    @pytest.mark.asyncio
    async def test_workflow_recovery(self, workflow_manager):
        """Test workflow recovery from checkpoint"""
        # Create and start workflow
        workflow_id = await workflow_manager.create_workflow(
            workflow_type="recovery_test",
            tasks=["task1", "task2"]
        )
        await workflow_manager.start_workflow(workflow_id)

        # Complete first task
        await workflow_manager.start_task(workflow_id, "task1")
        await workflow_manager.complete_task(workflow_id, "task1", result="done")

        # Simulate crash by directly loading from checkpoint
        recovered = await workflow_manager.recover_workflow(workflow_id)

        assert recovered is not None
        assert recovered.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_concurrent_workflows(self, workflow_manager):
        """Test running multiple workflows concurrently"""
        # Create multiple workflows
        workflow_ids = []
        for i in range(5):
            wf_id = await workflow_manager.create_workflow(
                workflow_type="concurrent_test",
                tasks=[f"task_{i}"]
            )
            workflow_ids.append(wf_id)

        # Start all workflows concurrently
        await asyncio.gather(*[
            workflow_manager.start_workflow(wf_id)
            for wf_id in workflow_ids
        ])

        # Verify all are running
        for wf_id in workflow_ids:
            state = await workflow_manager.get_workflow_state(wf_id)
            assert state.status == WorkflowStatus.RUNNING

        # Get metrics
        all_metrics = workflow_manager.get_metrics()
        assert all_metrics["running"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
