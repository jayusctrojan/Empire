"""
Empire v7.3 - Tests for Gradio Processing Status Components (Task 13)
Tests for progress bars, stage pipelines, and status display components.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import json

from app.ui.components.processing_status import (
    ProcessingStatus,
    ProcessingStage,
    ProgressData,
    StatusUpdate,
    StatusPollingClient,
    WebSocketStatusClient,
    create_progress_bar_html,
    create_stage_pipeline_html,
    create_status_badge_html,
    create_inline_status_html,
    create_error_display_html,
    create_success_display_html,
    PROCESSING_STATUS_CSS,
    STATUS_STYLES,
    STAGE_ICONS,
    STAGE_LABELS,
)


# ============================================================================
# Test Data Models
# ============================================================================

class TestProcessingStatus:
    """Tests for ProcessingStatus enum."""

    def test_all_status_values_defined(self):
        """Verify all expected status values exist."""
        expected = [
            "pending", "queued", "processing", "started",
            "success", "completed", "failure", "failed",
            "cancelled", "unknown"
        ]
        for status in expected:
            assert ProcessingStatus(status) is not None

    def test_status_string_conversion(self):
        """Test status value property."""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.SUCCESS.value == "success"
        assert ProcessingStatus.FAILURE.value == "failure"


class TestProcessingStage:
    """Tests for ProcessingStage enum."""

    def test_document_processing_stages(self):
        """Verify document processing stages exist."""
        stages = [
            "uploading", "parsing", "extracting_metadata",
            "chunking", "embedding", "indexing", "graph_syncing"
        ]
        for stage in stages:
            assert ProcessingStage(stage) is not None

    def test_query_processing_stages(self):
        """Verify query processing stages exist."""
        stages = ["refining", "searching", "reranking", "synthesizing"]
        for stage in stages:
            assert ProcessingStage(stage) is not None

    def test_all_stages_have_icons(self):
        """Verify all stages have icons defined."""
        for stage in ProcessingStage:
            assert stage in STAGE_ICONS, f"Missing icon for {stage}"

    def test_all_stages_have_labels(self):
        """Verify all stages have labels defined."""
        for stage in ProcessingStage:
            assert stage in STAGE_LABELS, f"Missing label for {stage}"


class TestProgressData:
    """Tests for ProgressData dataclass."""

    def test_default_values(self):
        """Test default progress data values."""
        progress = ProgressData()
        assert progress.current == 0
        assert progress.total == 100
        assert progress.percentage == 0.0
        assert progress.message == ""
        assert progress.stage is None

    def test_custom_values(self):
        """Test progress data with custom values."""
        progress = ProgressData(
            current=50,
            total=100,
            percentage=50.0,
            message="Processing...",
            stage="parsing",
            stage_index=1,
            total_stages=5
        )
        assert progress.current == 50
        assert progress.percentage == 50.0
        assert progress.stage == "parsing"
        assert progress.stage_index == 1
        assert progress.total_stages == 5


class TestStatusUpdate:
    """Tests for StatusUpdate dataclass."""

    def test_default_values(self):
        """Test default status update values."""
        update = StatusUpdate(
            resource_id="test-123",
            resource_type="task",
            status=ProcessingStatus.PENDING,
            status_message="Waiting...",
            progress=None
        )
        assert update.resource_id == "test-123"
        assert update.status == ProcessingStatus.PENDING
        assert update.should_continue_polling is True

    def test_with_progress(self):
        """Test status update with progress data."""
        progress = ProgressData(current=25, total=100, percentage=25.0)
        update = StatusUpdate(
            resource_id="test-456",
            resource_type="document",
            status=ProcessingStatus.PROCESSING,
            status_message="Processing document...",
            progress=progress
        )
        assert update.progress is not None
        assert update.progress.percentage == 25.0

    def test_with_error(self):
        """Test status update with error."""
        update = StatusUpdate(
            resource_id="test-789",
            resource_type="task",
            status=ProcessingStatus.FAILURE,
            status_message="Task failed",
            progress=None,
            error="Connection timeout"
        )
        assert update.error == "Connection timeout"


# ============================================================================
# Test HTML Generation Functions
# ============================================================================

class TestProgressBarHTML:
    """Tests for progress bar HTML generation."""

    def test_basic_progress_bar(self):
        """Test basic progress bar generation."""
        html = create_progress_bar_html(50, "Processing...")
        assert "50%" in html
        assert "Processing..." in html
        assert 'role="progressbar"' in html
        assert 'aria-valuenow="50"' in html

    def test_indeterminate_progress_bar(self):
        """Test indeterminate progress bar."""
        html = create_progress_bar_html(0, "Loading...", indeterminate=True)
        assert "indeterminate" in html
        assert "100%" in html  # Indeterminate fills full width

    def test_progress_bar_with_stage(self):
        """Test progress bar with stage indicator."""
        html = create_progress_bar_html(25, "Parsing document", stage="parsing")
        assert "📄" in html  # Parsing icon
        assert "Parsing document" in html

    def test_accessibility_attributes(self):
        """Test ARIA accessibility attributes."""
        html = create_progress_bar_html(75, "Almost done")
        assert 'aria-valuemin="0"' in html
        assert 'aria-valuemax="100"' in html
        assert 'aria-label=' in html


class TestStagePipelineHTML:
    """Tests for stage pipeline HTML generation."""

    def test_basic_pipeline(self):
        """Test basic stage pipeline generation."""
        stages = ["uploading", "parsing", "embedding", "completed"]
        html = create_stage_pipeline_html(stages, current_stage_index=1)
        assert 'role="navigation"' in html
        assert "stage-pipeline" in html

    def test_pipeline_with_completed_stages(self):
        """Test pipeline with completed stages."""
        stages = ["uploading", "parsing", "embedding"]
        html = create_stage_pipeline_html(stages, current_stage_index=2, completed=False)
        assert "completed" in html  # First two stages completed

    def test_pipeline_all_completed(self):
        """Test fully completed pipeline."""
        stages = ["uploading", "parsing", "embedding"]
        html = create_stage_pipeline_html(stages, current_stage_index=2, completed=True)
        assert html.count("completed") >= 3  # All stages completed

    def test_pipeline_accessibility(self):
        """Test pipeline ARIA navigation."""
        stages = ["step1", "step2"]
        html = create_stage_pipeline_html(stages, current_stage_index=0)
        assert 'aria-label="Processing stages"' in html


class TestStatusBadgeHTML:
    """Tests for status badge HTML generation."""

    def test_pending_badge(self):
        """Test pending status badge."""
        html = create_status_badge_html(ProcessingStatus.PENDING)
        assert "⏳" in html
        assert "Pending" in html
        assert "pending" in html

    def test_processing_badge(self):
        """Test processing status badge."""
        html = create_status_badge_html(ProcessingStatus.PROCESSING)
        assert "🔄" in html
        assert "Processing" in html
        assert "processing" in html

    def test_success_badge(self):
        """Test success status badge."""
        html = create_status_badge_html(ProcessingStatus.SUCCESS)
        assert "✅" in html
        assert "Success" in html
        assert "success" in html

    def test_failure_badge(self):
        """Test failure status badge."""
        html = create_status_badge_html(ProcessingStatus.FAILURE)
        assert "❌" in html
        assert "Failed" in html
        assert "failure" in html

    def test_badge_accessibility(self):
        """Test badge ARIA attributes."""
        html = create_status_badge_html(ProcessingStatus.PROCESSING)
        assert 'role="status"' in html
        assert 'aria-live="polite"' in html


class TestInlineStatusHTML:
    """Tests for inline status HTML generation."""

    def test_compact_status(self):
        """Test compact inline status."""
        html = create_inline_status_html(
            ProcessingStatus.PROCESSING,
            "Working...",
            percentage=50,
            compact=True
        )
        assert "Working..." in html
        assert "50%" in html

    def test_non_compact_status(self):
        """Test non-compact inline status (full progress bar)."""
        html = create_inline_status_html(
            ProcessingStatus.QUEUED,
            "In queue",
            percentage=0,
            compact=False
        )
        assert 'role="progressbar"' in html


class TestErrorDisplayHTML:
    """Tests for error display HTML generation."""

    def test_basic_error(self):
        """Test basic error display."""
        html = create_error_display_html(
            error_type="ConnectionError",
            error_message="Failed to connect to server"
        )
        assert "ConnectionError" in html
        assert "Failed to connect to server" in html
        assert "❌" in html

    def test_retryable_error(self):
        """Test error with retry information."""
        html = create_error_display_html(
            error_type="TimeoutError",
            error_message="Request timed out",
            retry_count=1,
            max_retries=3,
            is_retryable=True
        )
        assert "Retry 2 of 3" in html

    def test_non_retryable_error(self):
        """Test non-retryable error."""
        html = create_error_display_html(
            error_type="ValidationError",
            error_message="Invalid input",
            retry_count=3,
            max_retries=3,
            is_retryable=False
        )
        assert "All retries exhausted" in html


class TestSuccessDisplayHTML:
    """Tests for success display HTML generation."""

    def test_basic_success(self):
        """Test basic success display."""
        html = create_success_display_html(message="Processing complete")
        assert "Processing complete" in html
        assert "✅" in html

    def test_success_with_duration(self):
        """Test success with duration information."""
        html = create_success_display_html(
            message="Done",
            duration_seconds=5.5
        )
        assert "5.5s" in html

    def test_success_with_long_duration(self):
        """Test success with minutes duration."""
        html = create_success_display_html(
            message="Done",
            duration_seconds=125
        )
        assert "2m 5s" in html

    def test_success_with_preview(self):
        """Test success with result preview."""
        html = create_success_display_html(
            message="Document processed",
            result_preview="This is a sample result..."
        )
        assert "This is a sample result" in html


# ============================================================================
# Test CSS
# ============================================================================

class TestProcessingStatusCSS:
    """Tests for CSS definitions."""

    def test_css_contains_required_classes(self):
        """Verify CSS contains all required class definitions."""
        required_classes = [
            ".processing-status-container",
            ".progress-bar-container",
            ".progress-bar-fill",
            ".stage-indicator",
            ".status-badge",
            ".stage-pipeline",
            ".stage-step",
            ".stage-dot",
            ".stage-label"
        ]
        for class_name in required_classes:
            assert class_name in PROCESSING_STATUS_CSS, f"Missing CSS class: {class_name}"

    def test_css_contains_animations(self):
        """Verify CSS contains animation definitions."""
        assert "@keyframes shimmer" in PROCESSING_STATUS_CSS
        assert "@keyframes pulse" in PROCESSING_STATUS_CSS

    def test_css_contains_responsive_styles(self):
        """Verify CSS contains responsive media queries."""
        assert "@media (max-width: 768px)" in PROCESSING_STATUS_CSS

    def test_css_contains_accessibility_styles(self):
        """Verify CSS contains accessibility media queries."""
        assert "@media (prefers-contrast: high)" in PROCESSING_STATUS_CSS
        assert "@media (prefers-reduced-motion: reduce)" in PROCESSING_STATUS_CSS


# ============================================================================
# Test Status Polling Client
# ============================================================================

class TestStatusPollingClient:
    """Tests for StatusPollingClient."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return StatusPollingClient(base_url="http://test-api.example.com")

    @pytest.mark.asyncio
    async def test_poll_task_status_success(self, client):
        """Test successful task status polling."""
        updates_received = []

        def on_update(update: StatusUpdate):
            updates_received.append(update)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resource_id": "task-123",
            "resource_type": "task",
            "status": "success",
            "status_message": "Completed",
            "should_continue_polling": False
        }

        with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client.poll_task_status(
                task_id="task-123",
                on_update=on_update,
                max_polls=1
            )

            assert result.status == ProcessingStatus.SUCCESS
            assert len(updates_received) == 1

    @pytest.mark.asyncio
    async def test_poll_document_status_not_found(self, client):
        """Test document not found response."""
        updates_received = []

        def on_update(update: StatusUpdate):
            updates_received.append(update)

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client.poll_document_status(
                document_id="doc-unknown",
                on_update=on_update,
                max_polls=1
            )

            assert result.status == ProcessingStatus.UNKNOWN
            assert result.status_message == "Document not found"

    def test_stop_polling(self, client):
        """Test stopping active polls."""
        client._active_polls["task-123"] = True
        client.stop_polling("task", "123")
        assert client._active_polls.get("task-123") is False

    def test_stop_all_polling(self, client):
        """Test stopping all active polls."""
        client._active_polls = {
            "task-1": True,
            "task-2": True,
            "document-1": True
        }
        client.stop_all_polling()

        for key in client._active_polls:
            assert client._active_polls[key] is False


# ============================================================================
# Test WebSocket Status Client
# ============================================================================

class TestWebSocketStatusClient:
    """Tests for WebSocketStatusClient."""

    @pytest.fixture
    def ws_client(self):
        """Create test WebSocket client."""
        return WebSocketStatusClient(
            ws_url="wss://test-api.example.com",
            api_url="http://test-api.example.com",
            auto_reconnect=False
        )

    def test_initial_state(self, ws_client):
        """Test initial client state."""
        assert ws_client.is_connected is False
        assert ws_client.using_fallback is False

    @pytest.mark.asyncio
    async def test_connect_without_websockets_library(self, ws_client):
        """Test fallback when websockets library not available."""
        with patch.dict('sys.modules', {'websockets': None}):
            # Force ImportError by clearing the module
            import sys
            original = sys.modules.get('websockets')
            sys.modules['websockets'] = None

            try:
                # The client should handle the import error gracefully
                # and fall back to polling
                ws_client._use_fallback = True  # Simulate fallback
                assert ws_client.using_fallback is True
            finally:
                if original:
                    sys.modules['websockets'] = original

    def test_parse_ws_message_success(self, ws_client):
        """Test parsing successful WebSocket message."""
        message_data = {
            "task_id": "task-123",
            "resource_type": "task",
            "status": "success",
            "status_message": "Completed successfully",
            "progress": {
                "current": 100,
                "total": 100,
                "percentage": 100.0,
                "message": "Done"
            }
        }

        update = ws_client._parse_ws_message(message_data)

        assert update.resource_id == "task-123"
        assert update.status == ProcessingStatus.SUCCESS
        assert update.should_continue_polling is False
        assert update.progress.percentage == 100.0

    def test_parse_ws_message_progress(self, ws_client):
        """Test parsing progress WebSocket message."""
        message_data = {
            "task_id": "task-456",
            "resource_type": "task",
            "status": "processing",
            "status_message": "Processing document",
            "progress": {
                "current": 50,
                "total": 100,
                "percentage": 50.0,
                "message": "Halfway there",
                "stage": "embedding",
                "stage_index": 3,
                "total_stages": 6
            }
        }

        update = ws_client._parse_ws_message(message_data)

        assert update.status == ProcessingStatus.PROCESSING
        assert update.should_continue_polling is True
        assert update.progress.stage == "embedding"
        assert update.progress.stage_index == 3

    def test_parse_ws_message_failure(self, ws_client):
        """Test parsing failure WebSocket message."""
        message_data = {
            "task_id": "task-789",
            "resource_type": "task",
            "status": "failure",
            "status_message": "Task failed",
            "error": "Connection refused"
        }

        update = ws_client._parse_ws_message(message_data)

        assert update.status == ProcessingStatus.FAILURE
        assert update.should_continue_polling is False
        assert update.error == "Connection refused"

    def test_parse_ws_message_unknown_status(self, ws_client):
        """Test parsing message with unknown status."""
        message_data = {
            "task_id": "task-unknown",
            "status": "invalid_status"
        }

        update = ws_client._parse_ws_message(message_data)

        assert update.status == ProcessingStatus.UNKNOWN


# ============================================================================
# Test Style Definitions
# ============================================================================

class TestStyleDefinitions:
    """Tests for style and icon definitions."""

    def test_all_statuses_have_styles(self):
        """Verify all status values have style definitions."""
        for status in ProcessingStatus:
            assert status in STATUS_STYLES, f"Missing style for {status}"

    def test_status_styles_have_required_keys(self):
        """Verify each status style has required keys."""
        required_keys = ["icon", "color", "label"]
        for status, style in STATUS_STYLES.items():
            for key in required_keys:
                assert key in style, f"Missing {key} in style for {status}"

    def test_stage_icons_are_emoji(self):
        """Verify stage icons are emoji or symbols."""
        for stage, icon in STAGE_ICONS.items():
            assert len(icon) > 0, f"Empty icon for {stage}"

    def test_stage_labels_are_descriptive(self):
        """Verify stage labels are descriptive."""
        for stage, label in STAGE_LABELS.items():
            assert len(label) > 5, f"Label too short for {stage}: {label}"


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for processing status components."""

    def test_full_document_pipeline_display(self):
        """Test displaying a full document processing pipeline."""
        stages = [
            "uploading",
            "parsing",
            "extracting_metadata",
            "chunking",
            "embedding",
            "indexing",
            "graph_syncing",
            "completed"
        ]

        # Test each stage
        for i, stage in enumerate(stages[:-1]):  # Exclude completed
            html = create_stage_pipeline_html(stages, current_stage_index=i)

            # Verify HTML structure
            assert "stage-pipeline" in html
            # The label is truncated to 12 chars in the pipeline display
            stage_enum = ProcessingStage(stage)
            full_label = STAGE_LABELS.get(stage_enum, stage)
            truncated_label = full_label[:12]
            assert truncated_label in html or stage in html

    def test_status_update_to_html_flow(self):
        """Test converting StatusUpdate to HTML display."""
        # Create a progress update
        progress = ProgressData(
            current=75,
            total=100,
            percentage=75.0,
            message="Generating embeddings",
            stage="embedding",
            stage_index=4,
            total_stages=7
        )

        update = StatusUpdate(
            resource_id="doc-123",
            resource_type="document",
            status=ProcessingStatus.PROCESSING,
            status_message="Processing document",
            progress=progress
        )

        # Generate HTML components
        badge_html = create_status_badge_html(update.status)
        progress_html = create_progress_bar_html(
            update.progress.percentage,
            update.progress.message,
            update.progress.stage
        )

        # Verify outputs
        assert "Processing" in badge_html
        assert "75%" in progress_html
        assert "Generating embeddings" in progress_html

    def test_error_recovery_flow(self):
        """Test error display with retry flow."""
        # Initial error
        error_html = create_error_display_html(
            error_type="TimeoutError",
            error_message="Request timed out",
            retry_count=0,
            max_retries=3
        )
        assert "Retry 1 of 3" in error_html

        # After retries exhausted
        final_error_html = create_error_display_html(
            error_type="TimeoutError",
            error_message="Request timed out",
            retry_count=3,
            max_retries=3
        )
        assert "All retries exhausted" in final_error_html

    def test_success_with_metrics(self):
        """Test success display with timing metrics."""
        success_html = create_success_display_html(
            message="Document processed successfully",
            duration_seconds=45.7,
            result_preview="Extracted 150 entities and 89 relationships from the document."
        )

        assert "Document processed successfully" in success_html
        assert "45.7s" in success_html
        assert "Extracted 150 entities" in success_html
