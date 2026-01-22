"""
Empire v7.3 - Integration Tests for Status Broadcasting - Task 12.5
Tests for the unified status broadcasting system including:
- TaskStatusMessage schema validation
- StatusBroadcaster Redis Pub/Sub publishing
- Database status persistence
- Celery signal handler integration
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

# Import models
from app.models.task_status import (
    TaskStatusMessage,
    TaskState,
    TaskType,
    ProcessingStage,
    ProgressInfo,
    ErrorInfo,
    TaskStatusHistory,
    TaskStatusHistoryEntry,
    RedisStatusChannel,
    create_started_status,
    create_progress_status,
    create_success_status,
    create_failure_status,
    create_retry_status
)

# Import broadcaster
from app.services.status_broadcaster import (
    StatusBroadcaster,
    SyncStatusBroadcaster,
    get_task_type_from_name
)


class TestTaskStatusModels:
    """Tests for Task Status Pydantic models (Task 12.2)"""

    def test_task_state_enum_values(self):
        """Test TaskState enum contains all required states"""
        assert TaskState.PENDING.value == "pending"
        assert TaskState.STARTED.value == "started"
        assert TaskState.SUCCESS.value == "success"
        assert TaskState.FAILURE.value == "failure"
        assert TaskState.RETRY.value == "retry"
        assert TaskState.PROGRESS.value == "progress"
        assert TaskState.COMPLETED.value == "completed"

    def test_task_type_enum_values(self):
        """Test TaskType enum contains all task categories"""
        assert TaskType.DOCUMENT_PROCESSING.value == "document_processing"
        assert TaskType.EMBEDDING_GENERATION.value == "embedding_generation"
        assert TaskType.GRAPH_SYNC.value == "graph_sync"
        assert TaskType.CREWAI_WORKFLOW.value == "crewai_workflow"
        assert TaskType.QUERY_PROCESSING.value == "query_processing"
        assert TaskType.GENERIC.value == "generic"

    def test_processing_stage_enum_values(self):
        """Test ProcessingStage enum contains document processing stages"""
        assert ProcessingStage.PARSING.value == "parsing"
        assert ProcessingStage.EXTRACTING_METADATA.value == "extracting_metadata"
        assert ProcessingStage.CHUNKING.value == "chunking"
        assert ProcessingStage.EMBEDDING.value == "embedding"
        assert ProcessingStage.INDEXING.value == "indexing"

    def test_progress_info_creation(self):
        """Test ProgressInfo model creation and percentage calculation"""
        progress = ProgressInfo(current=50, total=100, message="Processing...")
        assert progress.current == 50
        assert progress.total == 100
        assert progress.percentage == 50.0
        assert progress.message == "Processing..."

    def test_progress_info_percentage_auto_calculation(self):
        """Test that percentage is auto-calculated from current/total"""
        progress = ProgressInfo(current=25, total=200)
        assert progress.percentage == 12.5

    def test_progress_info_with_stage(self):
        """Test ProgressInfo with processing stage"""
        progress = ProgressInfo(
            current=30,
            total=100,
            message="Extracting metadata",
            stage=ProcessingStage.EXTRACTING_METADATA,
            stage_index=2,
            total_stages=6
        )
        assert progress.stage == ProcessingStage.EXTRACTING_METADATA
        assert progress.stage_index == 2
        assert progress.total_stages == 6

    def test_error_info_creation(self):
        """Test ErrorInfo model creation"""
        error = ErrorInfo(
            error_type="ValueError",
            error_message="Invalid document format",
            retry_count=1,
            max_retries=3,
            is_retryable=True
        )
        assert error.error_type == "ValueError"
        assert error.error_message == "Invalid document format"
        assert error.retry_count == 1
        assert error.is_retryable == True

    def test_error_info_with_stack_trace(self):
        """Test ErrorInfo with stack trace"""
        error = ErrorInfo(
            error_type="FileNotFoundError",
            error_message="Document not found",
            stack_trace="Traceback (most recent call last):\n  File ...",
            retry_count=3,
            max_retries=3,
            is_retryable=False
        )
        assert error.stack_trace is not None
        assert error.is_retryable == False

    def test_task_status_message_creation(self):
        """Test TaskStatusMessage full model creation"""
        task_id = str(uuid4())
        message = TaskStatusMessage(
            task_id=task_id,
            task_name="app.tasks.document_processing.process_document",
            task_type=TaskType.DOCUMENT_PROCESSING,
            status=TaskState.STARTED,
            status_message="Processing document",
            document_id="doc-123",
            user_id="user-456"
        )
        assert message.task_id == task_id
        assert message.task_type == TaskType.DOCUMENT_PROCESSING
        assert message.status == TaskState.STARTED
        assert message.document_id == "doc-123"
        assert message.schema_version == "1.0"

    def test_task_status_message_with_progress(self):
        """Test TaskStatusMessage with progress info"""
        message = TaskStatusMessage(
            task_id=str(uuid4()),
            task_name="app.tasks.embedding_generation.generate_embeddings",
            task_type=TaskType.EMBEDDING_GENERATION,
            status=TaskState.PROGRESS,
            status_message="Generating embeddings",
            progress=ProgressInfo(
                current=50,
                total=100,
                message="Processing chunk 50 of 100",
                stage=ProcessingStage.EMBEDDING
            )
        )
        assert message.progress is not None
        assert message.progress.current == 50
        assert message.progress.stage == ProcessingStage.EMBEDDING

    def test_task_status_message_with_error(self):
        """Test TaskStatusMessage with error info"""
        message = TaskStatusMessage(
            task_id=str(uuid4()),
            task_name="app.tasks.graph_sync.sync_to_graph",
            task_type=TaskType.GRAPH_SYNC,
            status=TaskState.FAILURE,
            status_message="Graph sync failed",
            error=ErrorInfo(
                error_type="ConnectionError",
                error_message="Neo4j connection failed",
                retry_count=3,
                max_retries=3,
                is_retryable=False
            )
        )
        assert message.error is not None
        assert message.error.error_type == "ConnectionError"
        assert message.status == TaskState.FAILURE

    def test_task_status_message_json_serialization(self):
        """Test TaskStatusMessage can be serialized to JSON"""
        message = TaskStatusMessage(
            task_id=str(uuid4()),
            task_name="test_task",
            status=TaskState.SUCCESS,
            result={"chunks_processed": 10}
        )
        json_str = message.model_dump_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["status"] == "success"
        assert parsed["result"]["chunks_processed"] == 10


class TestStatusFactoryFunctions:
    """Tests for status message factory functions"""

    def test_create_started_status(self):
        """Test create_started_status factory function"""
        task_id = str(uuid4())
        message = create_started_status(
            task_id=task_id,
            task_name="app.tasks.document_processing.process_document",
            task_type=TaskType.DOCUMENT_PROCESSING,
            document_id="doc-123",
            user_id="user-456"
        )
        assert message.task_id == task_id
        assert message.status == TaskState.STARTED
        assert message.progress is not None
        assert message.progress.current == 0
        assert message.document_id == "doc-123"

    def test_create_progress_status(self):
        """Test create_progress_status factory function"""
        task_id = str(uuid4())
        message = create_progress_status(
            task_id=task_id,
            task_name="app.tasks.embedding_generation.generate",
            current=45,
            total=100,
            message="Processing chunk 45 of 100",
            stage=ProcessingStage.EMBEDDING,
            document_id="doc-123"
        )
        assert message.status == TaskState.PROGRESS
        assert message.progress.current == 45
        assert message.progress.total == 100
        assert message.progress.stage == ProcessingStage.EMBEDDING

    def test_create_success_status(self):
        """Test create_success_status factory function"""
        task_id = str(uuid4())
        message = create_success_status(
            task_id=task_id,
            task_name="app.tasks.document_processing.process_document",
            result={"chunks": 50, "embeddings": 50},
            runtime_seconds=12.5,
            document_id="doc-123"
        )
        assert message.status == TaskState.SUCCESS
        assert message.result["chunks"] == 50
        assert message.runtime_seconds == 12.5
        assert message.progress.percentage == 100.0

    def test_create_failure_status(self):
        """Test create_failure_status factory function"""
        task_id = str(uuid4())
        message = create_failure_status(
            task_id=task_id,
            task_name="app.tasks.graph_sync.sync",
            error_type="ConnectionError",
            error_message="Neo4j unavailable",
            retry_count=3,
            max_retries=3,
            stack_trace="Traceback...",
            runtime_seconds=5.2
        )
        assert message.status == TaskState.FAILURE
        assert message.error is not None
        assert message.error.error_type == "ConnectionError"
        assert message.error.retry_count == 3
        assert message.error.is_retryable == False

    def test_create_retry_status(self):
        """Test create_retry_status factory function"""
        task_id = str(uuid4())
        message = create_retry_status(
            task_id=task_id,
            task_name="app.tasks.embedding_generation.generate",
            retry_count=1,
            max_retries=3,
            error_message="Temporary failure",
            countdown_seconds=60,
            document_id="doc-123"
        )
        assert message.status == TaskState.RETRY
        assert message.error is not None
        assert message.error.retry_count == 1
        assert message.error.is_retryable == True
        assert message.estimated_remaining_seconds == 60.0


class TestRedisStatusChannel:
    """Tests for Redis channel configuration"""

    def test_channel_patterns(self):
        """Test channel patterns are correctly defined"""
        channels = RedisStatusChannel()
        assert "empire:task:" in channels.task_channel_pattern
        assert "empire:document:" in channels.document_channel_pattern
        assert "empire:query:" in channels.query_channel_pattern
        assert "empire:user:" in channels.user_channel_pattern
        assert channels.global_channel == "empire:tasks:all"

    def test_get_task_channel(self):
        """Test task channel generation"""
        channels = RedisStatusChannel()
        task_id = "abc-123"
        channel = channels.get_task_channel(task_id)
        assert channel == "empire:task:abc-123"

    def test_get_document_channel(self):
        """Test document channel generation"""
        channels = RedisStatusChannel()
        doc_id = "doc-456"
        channel = channels.get_document_channel(doc_id)
        assert channel == "empire:document:doc-456"

    def test_get_query_channel(self):
        """Test query channel generation"""
        channels = RedisStatusChannel()
        query_id = "query-789"
        channel = channels.get_query_channel(query_id)
        assert channel == "empire:query:query-789"

    def test_get_user_channel(self):
        """Test user channel generation"""
        channels = RedisStatusChannel()
        user_id = "user-101"
        channel = channels.get_user_channel(user_id)
        assert channel == "empire:user:user-101"


class TestTaskStatusHistory:
    """Tests for TaskStatusHistory model"""

    def test_create_empty_history(self):
        """Test creating empty status history"""
        history = TaskStatusHistory(
            task_id=str(uuid4()),
            task_name="test_task",
            task_type=TaskType.GENERIC,
            current_status=TaskState.PENDING
        )
        assert len(history.entries) == 0
        assert history.current_status == TaskState.PENDING

    def test_add_entry_to_history(self):
        """Test adding entries to status history"""
        history = TaskStatusHistory(
            task_id=str(uuid4()),
            task_name="test_task",
            task_type=TaskType.DOCUMENT_PROCESSING,
            current_status=TaskState.PENDING
        )

        history.add_entry(
            status=TaskState.STARTED,
            message="Task started"
        )

        assert len(history.entries) == 1
        assert history.current_status == TaskState.STARTED
        assert history.started_at is not None

    def test_history_records_completion(self):
        """Test history records completion time"""
        history = TaskStatusHistory(
            task_id=str(uuid4()),
            task_name="test_task",
            task_type=TaskType.GENERIC,
            current_status=TaskState.PENDING
        )

        history.add_entry(TaskState.STARTED, "Started")
        history.add_entry(TaskState.SUCCESS, "Completed")

        assert history.completed_at is not None
        assert history.total_runtime_seconds is not None


class TestGetTaskTypeFromName:
    """Tests for task type inference from task name"""

    def test_document_processing_task(self):
        """Test document processing task type detection"""
        task_type = get_task_type_from_name("app.tasks.document_processing.process_document")
        assert task_type == TaskType.DOCUMENT_PROCESSING

    def test_embedding_generation_task(self):
        """Test embedding generation task type detection"""
        task_type = get_task_type_from_name("app.tasks.embedding_generation.generate_embeddings")
        assert task_type == TaskType.EMBEDDING_GENERATION

    def test_graph_sync_task(self):
        """Test graph sync task type detection"""
        task_type = get_task_type_from_name("app.tasks.graph_sync.sync_to_neo4j")
        assert task_type == TaskType.GRAPH_SYNC

    def test_crewai_workflow_task(self):
        """Test CrewAI workflow task type detection"""
        task_type = get_task_type_from_name("app.tasks.crewai_workflows.run_crew")
        assert task_type == TaskType.CREWAI_WORKFLOW

    def test_query_processing_task(self):
        """Test query processing task type detection"""
        task_type = get_task_type_from_name("app.tasks.query_tasks.run_query")
        assert task_type == TaskType.QUERY_PROCESSING

    def test_generic_task(self):
        """Test generic task type fallback"""
        task_type = get_task_type_from_name("app.tasks.some_random_task")
        assert task_type == TaskType.GENERIC

    def test_health_check_task(self):
        """Test health check task type detection"""
        task_type = get_task_type_from_name("app.tasks.health_check")
        assert task_type == TaskType.HEALTH_CHECK


class TestStatusBroadcaster:
    """Tests for StatusBroadcaster service"""

    @pytest.fixture
    def broadcaster(self):
        """Create StatusBroadcaster instance"""
        return StatusBroadcaster()

    @pytest.mark.asyncio
    async def test_broadcaster_initialization(self, broadcaster):
        """Test broadcaster initializes correctly"""
        assert broadcaster.redis_url is not None
        assert broadcaster.channels is not None
        assert broadcaster._connected == False

    @pytest.mark.asyncio
    async def test_broadcast_status_publishes_to_channels(self, broadcaster):
        """Test broadcast_status publishes to multiple channels"""
        # Mock Redis client
        broadcaster.redis_client = AsyncMock()
        broadcaster._connected = True
        broadcaster._supabase = Mock()
        broadcaster._supabase.client.table.return_value.update.return_value.eq.return_value.execute.return_value = Mock()
        broadcaster._supabase.client.table.return_value.upsert.return_value.execute.return_value = Mock()

        message = create_started_status(
            task_id=str(uuid4()),
            task_name="test_task",
            task_type=TaskType.DOCUMENT_PROCESSING,
            document_id="doc-123",
            user_id="user-456"
        )

        await broadcaster.broadcast_status(message, persist_to_db=False)

        # Verify Redis publish was called (multiple channels)
        assert broadcaster.redis_client.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_broadcast_started_creates_correct_message(self, broadcaster):
        """Test broadcast_started creates correct status message"""
        broadcaster.redis_client = AsyncMock()
        broadcaster._connected = True
        broadcaster._supabase = None  # Skip DB persistence

        task_id = str(uuid4())
        await broadcaster.broadcast_started(
            task_id=task_id,
            task_name="app.tasks.document_processing.process",
            task_type=TaskType.DOCUMENT_PROCESSING,
            document_id="doc-123"
        )

        # Verify publish was called
        assert broadcaster.redis_client.publish.called

    @pytest.mark.asyncio
    async def test_broadcast_progress_includes_stage(self, broadcaster):
        """Test broadcast_progress includes processing stage"""
        broadcaster.redis_client = AsyncMock()
        broadcaster._connected = True
        broadcaster._supabase = None

        task_id = str(uuid4())
        await broadcaster.broadcast_progress(
            task_id=task_id,
            task_name="test_task",
            current=50,
            total=100,
            message="Processing...",
            stage=ProcessingStage.EMBEDDING,
            document_id="doc-123"
        )

        # Verify publish was called
        assert broadcaster.redis_client.publish.called

    @pytest.mark.asyncio
    async def test_broadcast_success_includes_result(self, broadcaster):
        """Test broadcast_success includes result data"""
        broadcaster.redis_client = AsyncMock()
        broadcaster._connected = True
        broadcaster._supabase = None

        task_id = str(uuid4())
        result = {"chunks": 50, "embeddings": 50}

        await broadcaster.broadcast_success(
            task_id=task_id,
            task_name="test_task",
            result=result,
            runtime_seconds=10.5,
            document_id="doc-123"
        )

        assert broadcaster.redis_client.publish.called

    @pytest.mark.asyncio
    async def test_broadcast_failure_includes_error_info(self, broadcaster):
        """Test broadcast_failure includes error information"""
        broadcaster.redis_client = AsyncMock()
        broadcaster._connected = True
        broadcaster._supabase = None

        task_id = str(uuid4())

        await broadcaster.broadcast_failure(
            task_id=task_id,
            task_name="test_task",
            error_type="ValueError",
            error_message="Invalid input",
            retry_count=2,
            max_retries=3,
            stack_trace="Traceback..."
        )

        assert broadcaster.redis_client.publish.called

    @pytest.mark.asyncio
    async def test_broadcast_handles_redis_connection_failure(self, broadcaster):
        """Test broadcaster handles Redis connection failure gracefully"""
        broadcaster._connected = False
        broadcaster.redis_client = None
        broadcaster._supabase = None

        message = create_started_status(
            task_id=str(uuid4()),
            task_name="test_task"
        )

        # Should not raise exception
        await broadcaster.broadcast_status(message, persist_to_db=False)


class TestSyncStatusBroadcaster:
    """Tests for synchronous StatusBroadcaster wrapper"""

    def test_sync_broadcaster_initialization(self):
        """Test sync broadcaster initializes correctly"""
        sync_broadcaster = SyncStatusBroadcaster()
        assert sync_broadcaster._async_broadcaster is None

    def test_sync_broadcaster_lazy_loads_async(self):
        """Test sync broadcaster lazy loads async broadcaster"""
        sync_broadcaster = SyncStatusBroadcaster()
        broadcaster = sync_broadcaster._get_broadcaster()
        assert broadcaster is not None
        assert isinstance(broadcaster, StatusBroadcaster)

    @patch('app.services.status_broadcaster.StatusBroadcaster')
    def test_sync_broadcast_started_calls_async(self, mock_broadcaster_class):
        """Test sync broadcast_started triggers async call"""
        mock_broadcaster = Mock()
        mock_broadcaster.broadcast_started = AsyncMock()
        mock_broadcaster_class.return_value = mock_broadcaster

        sync_broadcaster = SyncStatusBroadcaster()
        sync_broadcaster._async_broadcaster = mock_broadcaster

        # This should trigger the async call
        sync_broadcaster.broadcast_started(
            task_id=str(uuid4()),
            task_name="test_task"
        )

        # The async method should have been scheduled


class TestCelerySignalIntegration:
    """Tests for Celery signal handler integration"""

    @patch('app.celery_app._get_status_broadcaster')
    def test_prerun_handler_broadcasts_started(self, mock_get_broadcaster):
        """Test task_prerun handler broadcasts started status"""
        mock_broadcaster = Mock()
        mock_broadcaster.broadcast_started = Mock()
        mock_get_broadcaster.return_value = mock_broadcaster

        # Import the handler
        from app.celery_app import task_prerun_handler

        # Create mock task
        mock_task = Mock()
        mock_task.name = "app.tasks.document_processing.process_document"

        # Call handler
        task_prerun_handler(
            sender=mock_task,
            task_id="test-task-123",
            task=mock_task,
            kwargs={"document_id": "doc-123", "user_id": "user-456"}
        )

        # Verify broadcaster was called
        mock_broadcaster.broadcast_started.assert_called_once()

    @patch('app.celery_app._get_status_broadcaster')
    def test_postrun_handler_broadcasts_success(self, mock_get_broadcaster):
        """Test task_postrun handler broadcasts success status"""
        mock_broadcaster = Mock()
        mock_broadcaster.broadcast_success = Mock()
        mock_get_broadcaster.return_value = mock_broadcaster

        from app.celery_app import task_postrun_handler, _task_start_times
        import time

        task_id = "test-task-456"
        _task_start_times[task_id] = time.time() - 5  # 5 seconds ago

        mock_task = Mock()
        mock_task.name = "app.tasks.document_processing.process_document"

        task_postrun_handler(
            sender=mock_task,
            task_id=task_id,
            task=mock_task,
            retval={"chunks": 10},
            kwargs={"document_id": "doc-123"}
        )

        mock_broadcaster.broadcast_success.assert_called_once()

    @patch('app.celery_app._get_status_broadcaster')
    @patch('app.celery_app.send_to_dead_letter_queue')
    def test_failure_handler_broadcasts_failure(self, mock_dlq, mock_get_broadcaster):
        """Test task_failure handler broadcasts failure status"""
        mock_broadcaster = Mock()
        mock_broadcaster.broadcast_failure = Mock()
        mock_get_broadcaster.return_value = mock_broadcaster

        from app.celery_app import task_failure_handler

        mock_sender = Mock()
        mock_sender.name = "app.tasks.graph_sync.sync"
        mock_sender.max_retries = 3

        # Mock celery.current_app at the module level
        with patch('celery.current_app') as mock_app:
            mock_app.backend.get_task_meta.return_value = {"retries": 1}

            task_failure_handler(
                sender=mock_sender,
                task_id="test-task-789",
                exception=ValueError("Test error"),
                args=[],
                kwargs={"document_id": "doc-123"}
            )

        mock_broadcaster.broadcast_failure.assert_called_once()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
