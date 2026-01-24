"""
Empire v7.3 - Gradio Processing Status Components - Task 13
Real-time progress indicators and status displays for document/query processing

Features:
- Progress bars with stage indicators
- WebSocket integration for real-time updates
- REST polling fallback
- Accessibility-compliant design
- Mobile responsive layout
"""

import os
import json
import asyncio
import gradio as gr
import httpx
import structlog
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

# Configuration
API_BASE_URL = os.getenv("EMPIRE_API_URL", "https://jb-empire-api.onrender.com")
WS_BASE_URL = os.getenv("EMPIRE_WS_URL", "wss://jb-empire-api.onrender.com")


class ProcessingStatus(str, Enum):
    """Status values aligned with backend."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    STARTED = "started"
    SUCCESS = "success"
    COMPLETED = "completed"
    FAILURE = "failure"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ProcessingStage(str, Enum):
    """Processing stages for multi-stage tasks."""
    UPLOADING = "uploading"
    PARSING = "parsing"
    EXTRACTING_METADATA = "extracting_metadata"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    GRAPH_SYNCING = "graph_syncing"
    REFINING = "refining"
    SEARCHING = "searching"
    RERANKING = "reranking"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"


@dataclass
class ProgressData:
    """Progress information for long-running operations."""
    current: int = 0
    total: int = 100
    percentage: float = 0.0
    message: str = ""
    stage: Optional[str] = None
    stage_index: Optional[int] = None
    total_stages: Optional[int] = None


@dataclass
class StatusUpdate:
    """Status update from backend."""
    resource_id: str
    resource_type: str
    status: ProcessingStatus
    status_message: str
    progress: Optional[ProgressData]
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    poll_interval_ms: int = 2000
    should_continue_polling: bool = True


# ============================================================================
# Status Icons and Styling
# ============================================================================

STATUS_STYLES = {
    ProcessingStatus.PENDING: {"icon": "⏳", "color": "#6b7280", "label": "Pending"},
    ProcessingStatus.QUEUED: {"icon": "📋", "color": "#6b7280", "label": "Queued"},
    ProcessingStatus.PROCESSING: {"icon": "🔄", "color": "#3b82f6", "label": "Processing"},
    ProcessingStatus.STARTED: {"icon": "🚀", "color": "#3b82f6", "label": "Started"},
    ProcessingStatus.SUCCESS: {"icon": "✅", "color": "#10b981", "label": "Success"},
    ProcessingStatus.COMPLETED: {"icon": "✅", "color": "#10b981", "label": "Completed"},
    ProcessingStatus.FAILURE: {"icon": "❌", "color": "#ef4444", "label": "Failed"},
    ProcessingStatus.FAILED: {"icon": "❌", "color": "#ef4444", "label": "Failed"},
    ProcessingStatus.CANCELLED: {"icon": "🚫", "color": "#f59e0b", "label": "Cancelled"},
    ProcessingStatus.UNKNOWN: {"icon": "❓", "color": "#9ca3af", "label": "Unknown"},
}

STAGE_ICONS = {
    ProcessingStage.UPLOADING: "📤",
    ProcessingStage.PARSING: "📄",
    ProcessingStage.EXTRACTING_METADATA: "🔍",
    ProcessingStage.CHUNKING: "✂️",
    ProcessingStage.EMBEDDING: "🧮",
    ProcessingStage.INDEXING: "📊",
    ProcessingStage.GRAPH_SYNCING: "🔗",
    ProcessingStage.REFINING: "🎯",
    ProcessingStage.SEARCHING: "🔎",
    ProcessingStage.RERANKING: "📈",
    ProcessingStage.SYNTHESIZING: "🧠",
    ProcessingStage.COMPLETED: "✅",
}

STAGE_LABELS = {
    ProcessingStage.UPLOADING: "Uploading file",
    ProcessingStage.PARSING: "Parsing document",
    ProcessingStage.EXTRACTING_METADATA: "Extracting metadata",
    ProcessingStage.CHUNKING: "Chunking content",
    ProcessingStage.EMBEDDING: "Generating embeddings",
    ProcessingStage.INDEXING: "Indexing content",
    ProcessingStage.GRAPH_SYNCING: "Syncing to knowledge graph",
    ProcessingStage.REFINING: "Refining query",
    ProcessingStage.SEARCHING: "Searching knowledge base",
    ProcessingStage.RERANKING: "Reranking results",
    ProcessingStage.SYNTHESIZING: "Synthesizing response",
    ProcessingStage.COMPLETED: "Processing complete",
}


# ============================================================================
# Custom CSS for Processing Status Components
# ============================================================================

PROCESSING_STATUS_CSS = """
/* Processing Status Container */
.processing-status-container {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* Progress Bar Container */
.progress-bar-container {
    width: 100%;
    height: 12px;
    background-color: #e2e8f0;
    border-radius: 6px;
    overflow: hidden;
    margin: 12px 0;
}

/* Progress Bar Fill */
.progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
    border-radius: 6px;
    transition: width 0.3s ease-in-out;
}

/* Animated Progress (Indeterminate) */
.progress-bar-fill.indeterminate {
    background: linear-gradient(
        90deg,
        #3b82f6 0%,
        #60a5fa 50%,
        #3b82f6 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

/* Stage Indicator */
.stage-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #475569;
    margin: 8px 0;
}

.stage-icon {
    font-size: 20px;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

/* Status Badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
}

.status-badge.pending { background: #f3f4f6; color: #6b7280; }
.status-badge.processing { background: #dbeafe; color: #1d4ed8; }
.status-badge.success { background: #d1fae5; color: #059669; }
.status-badge.failure { background: #fee2e2; color: #dc2626; }

/* Stage Pipeline */
.stage-pipeline {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 16px 0;
    padding: 8px 0;
}

.stage-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
    position: relative;
}

.stage-step::after {
    content: '';
    position: absolute;
    top: 16px;
    left: 50%;
    width: calc(100% - 32px);
    height: 2px;
    background: #e2e8f0;
    z-index: 0;
}

.stage-step:last-child::after {
    display: none;
}

.stage-step.completed::after {
    background: #10b981;
}

.stage-step.active::after {
    background: linear-gradient(90deg, #10b981 0%, #3b82f6 50%, #e2e8f0 100%);
}

.stage-dot {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    background: #f3f4f6;
    border: 2px solid #e2e8f0;
    z-index: 1;
    transition: all 0.3s ease;
}

.stage-step.completed .stage-dot {
    background: #10b981;
    border-color: #10b981;
    color: white;
}

.stage-step.active .stage-dot {
    background: #3b82f6;
    border-color: #3b82f6;
    color: white;
    animation: pulse 1.5s infinite;
}

.stage-label {
    font-size: 10px;
    color: #64748b;
    text-align: center;
    max-width: 60px;
}

/* Mobile Responsiveness */
@media (max-width: 768px) {
    .stage-pipeline {
        flex-wrap: wrap;
        gap: 16px;
    }

    .stage-step::after {
        display: none;
    }

    .stage-step {
        flex: 0 0 calc(33.33% - 16px);
    }
}

/* Accessibility - High Contrast Mode */
@media (prefers-contrast: high) {
    .progress-bar-fill {
        background: #000;
    }

    .stage-dot {
        border-width: 3px;
    }
}

/* Accessibility - Reduced Motion */
@media (prefers-reduced-motion: reduce) {
    .progress-bar-fill.indeterminate {
        animation: none;
    }

    .stage-icon,
    .stage-step.active .stage-dot {
        animation: none;
    }
}
"""


# ============================================================================
# Status Polling Client
# ============================================================================

class StatusPollingClient:
    """
    Client for polling status from REST API.
    Used as fallback when WebSocket is unavailable.
    """

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=10.0)
        self._active_polls: Dict[str, bool] = {}

    async def poll_task_status(
        self,
        task_id: str,
        on_update: Callable[[StatusUpdate], None],
        auth_token: Optional[str] = None,
        max_polls: int = 100
    ) -> StatusUpdate:
        """
        Poll for task status until completion or max polls reached.

        Args:
            task_id: Celery task ID
            on_update: Callback for each status update
            auth_token: Optional auth token
            max_polls: Maximum number of polls

        Returns:
            Final StatusUpdate
        """
        poll_key = f"task-{task_id}"
        self._active_polls[poll_key] = True
        poll_count = 0
        poll_interval = 2.0

        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        try:
            while self._active_polls.get(poll_key) and poll_count < max_polls:
                poll_count += 1

                try:
                    response = await self.client.get(
                        f"{self.base_url}/api/status/task/{task_id}",
                        headers=headers
                    )

                    if response.status_code == 200:
                        data = response.json()
                        status_update = self._parse_status_response(data)
                        on_update(status_update)

                        if not status_update.should_continue_polling:
                            return status_update

                        poll_interval = data.get("poll_interval_ms", 2000) / 1000
                    else:
                        logger.warning(
                            "Status poll failed",
                            task_id=task_id,
                            status_code=response.status_code
                        )

                except httpx.RequestError as e:
                    logger.error("Status poll request error", task_id=task_id, error=str(e))

                await asyncio.sleep(poll_interval)

            # Return unknown status if max polls reached
            return StatusUpdate(
                resource_id=task_id,
                resource_type="task",
                status=ProcessingStatus.UNKNOWN,
                status_message="Polling timeout",
                progress=None,
                should_continue_polling=False
            )

        finally:
            self._active_polls.pop(poll_key, None)

    async def poll_document_status(
        self,
        document_id: str,
        on_update: Callable[[StatusUpdate], None],
        auth_token: Optional[str] = None,
        max_polls: int = 100
    ) -> StatusUpdate:
        """Poll for document processing status."""
        poll_key = f"document-{document_id}"
        self._active_polls[poll_key] = True
        poll_count = 0
        poll_interval = 2.0

        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        try:
            while self._active_polls.get(poll_key) and poll_count < max_polls:
                poll_count += 1

                try:
                    response = await self.client.get(
                        f"{self.base_url}/api/status/document/{document_id}",
                        headers=headers
                    )

                    if response.status_code == 200:
                        data = response.json()
                        status_update = self._parse_status_response(data)
                        on_update(status_update)

                        if not status_update.should_continue_polling:
                            return status_update

                        poll_interval = data.get("poll_interval_ms", 2000) / 1000
                    elif response.status_code == 404:
                        logger.warning("Document not found", document_id=document_id)
                        return StatusUpdate(
                            resource_id=document_id,
                            resource_type="document",
                            status=ProcessingStatus.UNKNOWN,
                            status_message="Document not found",
                            progress=None,
                            should_continue_polling=False
                        )

                except httpx.RequestError as e:
                    logger.error("Document status poll error", document_id=document_id, error=str(e))

                await asyncio.sleep(poll_interval)

            return StatusUpdate(
                resource_id=document_id,
                resource_type="document",
                status=ProcessingStatus.UNKNOWN,
                status_message="Polling timeout",
                progress=None,
                should_continue_polling=False
            )

        finally:
            self._active_polls.pop(poll_key, None)

    def stop_polling(self, resource_type: str, resource_id: str):
        """Stop polling for a specific resource."""
        poll_key = f"{resource_type}-{resource_id}"
        self._active_polls[poll_key] = False

    def stop_all_polling(self):
        """Stop all active polls."""
        for key in list(self._active_polls.keys()):
            self._active_polls[key] = False

    def _parse_status_response(self, data: Dict[str, Any]) -> StatusUpdate:
        """Parse API response into StatusUpdate."""
        progress = None
        if data.get("progress"):
            prog = data["progress"]
            progress = ProgressData(
                current=prog.get("current", 0),
                total=prog.get("total", 100),
                percentage=prog.get("percentage", 0),
                message=prog.get("message", ""),
                stage=prog.get("stage"),
                stage_index=prog.get("stage_index"),
                total_stages=prog.get("total_stages")
            )

        try:
            status = ProcessingStatus(data.get("status", "unknown").lower())
        except ValueError:
            status = ProcessingStatus.UNKNOWN

        return StatusUpdate(
            resource_id=data.get("resource_id", ""),
            resource_type=data.get("resource_type", "task"),
            status=status,
            status_message=data.get("status_message", ""),
            progress=progress,
            error=data.get("error"),
            result=data.get("result"),
            poll_interval_ms=data.get("poll_interval_ms", 2000),
            should_continue_polling=data.get("should_continue_polling", True)
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# ============================================================================
# Gradio Components
# ============================================================================

def create_progress_bar_html(
    percentage: float = 0,
    message: str = "",
    stage: Optional[str] = None,
    indeterminate: bool = False
) -> str:
    """
    Create HTML for progress bar component.

    Args:
        percentage: Progress percentage (0-100)
        message: Status message to display
        stage: Current processing stage
        indeterminate: Whether to show indeterminate progress

    Returns:
        HTML string for progress bar
    """
    stage_icon = ""
    stage_label = message

    if stage:
        try:
            stage_enum = ProcessingStage(stage.lower())
            stage_icon = STAGE_ICONS.get(stage_enum, "🔄")
            stage_label = f"{STAGE_LABELS.get(stage_enum, stage)}"
        except ValueError:
            stage_icon = "🔄"

    fill_class = "progress-bar-fill indeterminate" if indeterminate else "progress-bar-fill"
    fill_width = "100%" if indeterminate else f"{percentage}%"

    html = f"""
    <div class="processing-status-container" role="progressbar"
         aria-valuenow="{int(percentage)}" aria-valuemin="0" aria-valuemax="100"
         aria-label="Processing progress: {int(percentage)}%">

        <div class="stage-indicator">
            <span class="stage-icon" aria-hidden="true">{stage_icon}</span>
            <span>{stage_label}</span>
        </div>

        <div class="progress-bar-container">
            <div class="{fill_class}" style="width: {fill_width};"></div>
        </div>

        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #64748b;">
            <span>{message or 'Processing...'}</span>
            <span>{int(percentage)}%</span>
        </div>
    </div>
    """

    return html


def create_stage_pipeline_html(
    stages: List[str],
    current_stage_index: int = 0,
    completed: bool = False
) -> str:
    """
    Create HTML for multi-stage pipeline indicator.

    Args:
        stages: List of stage names
        current_stage_index: Index of current stage (0-based)
        completed: Whether processing is complete

    Returns:
        HTML string for stage pipeline
    """
    steps_html = ""

    for i, stage in enumerate(stages):
        try:
            stage_enum = ProcessingStage(stage.lower())
            icon = STAGE_ICONS.get(stage_enum, str(i + 1))
            label = STAGE_LABELS.get(stage_enum, stage)[:12]
        except ValueError:
            icon = str(i + 1)
            label = stage[:12]

        if completed or i < current_stage_index:
            step_class = "stage-step completed"
            dot_content = "✓"
        elif i == current_stage_index:
            step_class = "stage-step active"
            dot_content = icon
        else:
            step_class = "stage-step"
            dot_content = icon

        steps_html += f"""
        <div class="{step_class}">
            <div class="stage-dot" aria-current="{'step' if i == current_stage_index else 'false'}">
                {dot_content}
            </div>
            <span class="stage-label">{label}</span>
        </div>
        """

    return f"""
    <div class="stage-pipeline" role="navigation" aria-label="Processing stages">
        {steps_html}
    </div>
    """


def create_status_badge_html(status: ProcessingStatus) -> str:
    """
    Create HTML for status badge.

    Args:
        status: Current processing status

    Returns:
        HTML string for status badge
    """
    style = STATUS_STYLES.get(status, STATUS_STYLES[ProcessingStatus.UNKNOWN])

    status_class = "status-badge"
    if status in [ProcessingStatus.PENDING, ProcessingStatus.QUEUED]:
        status_class += " pending"
    elif status in [ProcessingStatus.PROCESSING, ProcessingStatus.STARTED]:
        status_class += " processing"
    elif status in [ProcessingStatus.SUCCESS, ProcessingStatus.COMPLETED]:
        status_class += " success"
    elif status in [ProcessingStatus.FAILURE, ProcessingStatus.FAILED]:
        status_class += " failure"

    return f"""
    <span class="{status_class}" role="status" aria-live="polite">
        <span aria-hidden="true">{style['icon']}</span>
        <span>{style['label']}</span>
    </span>
    """


def create_processing_status_component() -> gr.Blocks:
    """
    Create a reusable Gradio Blocks component for displaying processing status.

    Returns:
        gr.Blocks: Gradio Blocks component
    """
    with gr.Blocks(css=PROCESSING_STATUS_CSS) as status_component:
        # Hidden state for tracking
        status_state = gr.State(value={
            "resource_id": None,
            "resource_type": None,
            "status": "pending",
            "percentage": 0,
            "message": "",
            "stage": None,
            "stages": []
        })

        with gr.Column(elem_classes="processing-status-wrapper"):
            # Status badge
            status_badge = gr.HTML(
                value=create_status_badge_html(ProcessingStatus.PENDING),
                elem_id="status-badge"
            )

            # Progress bar
            progress_bar = gr.HTML(
                value=create_progress_bar_html(0, "Waiting to start..."),
                elem_id="progress-bar"
            )

            # Stage pipeline (hidden by default)
            stage_pipeline = gr.HTML(
                value="",
                visible=False,
                elem_id="stage-pipeline"
            )

            # Error message (hidden by default)
            error_message = gr.HTML(
                value="",
                visible=False,
                elem_id="error-message"
            )

        def update_display(state):
            """Update all display elements based on state."""
            status = ProcessingStatus(state.get("status", "pending"))
            percentage = state.get("percentage", 0)
            message = state.get("message", "")
            stage = state.get("stage")
            stages = state.get("stages", [])
            error = state.get("error")

            # Update badge
            badge_html = create_status_badge_html(status)

            # Update progress bar
            indeterminate = status in [ProcessingStatus.PENDING, ProcessingStatus.QUEUED]
            progress_html = create_progress_bar_html(percentage, message, stage, indeterminate)

            # Update stage pipeline
            pipeline_html = ""
            pipeline_visible = False
            if stages and len(stages) > 1:
                current_index = stages.index(stage) if stage in stages else 0
                completed = status in [ProcessingStatus.SUCCESS, ProcessingStatus.COMPLETED]
                pipeline_html = create_stage_pipeline_html(stages, current_index, completed)
                pipeline_visible = True

            # Update error message
            error_html = ""
            error_visible = False
            if error and status in [ProcessingStatus.FAILURE, ProcessingStatus.FAILED]:
                error_html = f"""
                <div style="padding: 12px; background: #fee2e2; border-radius: 8px; border-left: 4px solid #dc2626; margin-top: 12px;">
                    <strong>Error:</strong> {error}
                </div>
                """
                error_visible = True

            return (
                badge_html,
                progress_html,
                gr.update(value=pipeline_html, visible=pipeline_visible),
                gr.update(value=error_html, visible=error_visible)
            )

        # Bind state changes to display updates
        status_state.change(
            fn=update_display,
            inputs=[status_state],
            outputs=[status_badge, progress_bar, stage_pipeline, error_message]
        )

    return status_component


def create_document_upload_status_component() -> gr.Blocks:
    """
    Create a Gradio component specifically for document upload status.

    Returns:
        gr.Blocks: Gradio Blocks component for document upload
    """
    document_stages = [
        "uploading",
        "parsing",
        "extracting_metadata",
        "chunking",
        "embedding",
        "indexing",
        "graph_syncing",
        "completed"
    ]

    with gr.Blocks(css=PROCESSING_STATUS_CSS) as upload_status:
        document_id = gr.State(value=None)  # noqa: F841
        upload_state = gr.State(value={
            "status": "pending",
            "percentage": 0,
            "message": "Ready to upload",
            "stage": None,
            "stages": document_stages
        })

        gr.Markdown("### Document Processing Status")

        status_badge = gr.HTML(
            value=create_status_badge_html(ProcessingStatus.PENDING)
        )

        progress_html = gr.HTML(
            value=create_progress_bar_html(0, "Ready to upload")
        )

        pipeline_html = gr.HTML(
            value=create_stage_pipeline_html(document_stages, 0, False)
        )

        with gr.Row():
            filename_display = gr.Textbox(  # noqa: F841
                label="File",
                value="No file selected",
                interactive=False
            )

            elapsed_time = gr.Textbox(  # noqa: F841
                label="Elapsed Time",
                value="--:--",
                interactive=False
            )

        def update_upload_display(state):
            """Update upload status display."""
            status = ProcessingStatus(state.get("status", "pending"))
            percentage = state.get("percentage", 0)
            message = state.get("message", "")
            stage = state.get("stage")
            stages = state.get("stages", document_stages)

            badge = create_status_badge_html(status)
            progress = create_progress_bar_html(
                percentage,
                message,
                stage,
                indeterminate=status == ProcessingStatus.QUEUED
            )

            current_index = 0
            if stage and stage in stages:
                current_index = stages.index(stage)

            completed = status in [ProcessingStatus.SUCCESS, ProcessingStatus.COMPLETED]
            pipeline = create_stage_pipeline_html(stages, current_index, completed)

            return badge, progress, pipeline

        upload_state.change(
            fn=update_upload_display,
            inputs=[upload_state],
            outputs=[status_badge, progress_html, pipeline_html]
        )

    return upload_status


def create_query_status_component() -> gr.Blocks:
    """
    Create a Gradio component for query processing status.

    Returns:
        gr.Blocks: Gradio Blocks component for query status
    """
    query_stages = [  # noqa: F841
        "refining",
        "searching",
        "reranking",
        "synthesizing",
        "completed"
    ]

    with gr.Blocks(css=PROCESSING_STATUS_CSS) as query_status:
        query_id = gr.State(value=None)  # noqa: F841
        query_state = gr.State(value={
            "status": "pending",
            "percentage": 0,
            "message": "Waiting for query...",
            "stage": None,
            "iteration": 0,
            "max_iterations": 3
        })

        with gr.Column():
            # Compact status indicator for chat integration
            status_indicator = gr.HTML(
                value="""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 12px;
                            background: #f8fafc; border-radius: 8px; font-size: 14px;">
                    <span>🔍</span>
                    <span>Processing your query...</span>
                </div>
                """,
                visible=False
            )

            # Progress bar (shown during processing)
            progress_display = gr.HTML(
                value="",
                visible=False
            )

        def update_query_display(state):
            """Update query status display."""
            status = ProcessingStatus(state.get("status", "pending"))
            message = state.get("message", "Processing...")
            percentage = state.get("percentage", 0)
            stage = state.get("stage")
            iteration = state.get("iteration", 0)
            max_iterations = state.get("max_iterations", 3)

            if status in [ProcessingStatus.PENDING, ProcessingStatus.QUEUED]:
                indicator_visible = False
                progress_visible = False
            elif status in [ProcessingStatus.PROCESSING, ProcessingStatus.STARTED]:
                indicator_visible = True
                progress_visible = True
            else:
                indicator_visible = False
                progress_visible = False

            stage_icon = STAGE_ICONS.get(
                ProcessingStage(stage) if stage else None,
                "🔄"
            )

            indicator_html = f"""
            <div style="display: flex; align-items: center; gap: 8px; padding: 8px 12px;
                        background: #dbeafe; border-radius: 8px; font-size: 14px; color: #1e40af;">
                <span class="stage-icon">{stage_icon}</span>
                <span>{message}</span>
                {f'<span style="margin-left: auto; opacity: 0.7;">Iteration {iteration}/{max_iterations}</span>' if max_iterations > 1 else ''}
            </div>
            """

            progress_html = create_progress_bar_html(percentage, message, stage)

            return (
                gr.update(value=indicator_html, visible=indicator_visible),
                gr.update(value=progress_html, visible=progress_visible)
            )

        query_state.change(
            fn=update_query_display,
            inputs=[query_state],
            outputs=[status_indicator, progress_display]
        )

    return query_status


# ============================================================================
# WebSocket Client for Real-Time Updates (Task 13.3)
# ============================================================================

class WebSocketStatusClient:
    """
    WebSocket client for real-time status updates.
    Provides real-time status updates from the Empire backend via WebSocket.
    Falls back to REST polling if WebSocket connection fails.
    """

    def __init__(
        self,
        ws_url: str = WS_BASE_URL,
        api_url: str = API_BASE_URL,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 5
    ):
        self.ws_url = ws_url
        self.api_url = api_url
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self._websocket = None
        self._connected = False
        self._reconnect_count = 0
        self._subscriptions: Dict[str, Callable[[StatusUpdate], None]] = {}
        self._polling_fallback = StatusPollingClient(api_url)
        self._use_fallback = False

    async def connect(self, auth_token: Optional[str] = None) -> bool:
        """
        Establish WebSocket connection.

        Args:
            auth_token: Optional authentication token

        Returns:
            True if connection successful, False otherwise
        """
        try:
            import websockets

            # Build WebSocket URL with auth
            ws_endpoint = f"{self.ws_url}/ws/status"
            if auth_token:
                ws_endpoint += f"?token={auth_token}"

            self._websocket = await websockets.connect(
                ws_endpoint,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5
            )
            self._connected = True
            self._reconnect_count = 0
            self._use_fallback = False

            logger.info("WebSocket connected successfully", endpoint=ws_endpoint)
            return True

        except ImportError:
            logger.warning("websockets library not installed, using REST polling fallback")
            self._use_fallback = True
            return False

        except Exception as e:
            logger.error("WebSocket connection failed", error=str(e))
            self._connected = False

            # Try to reconnect
            if self.auto_reconnect and self._reconnect_count < self.max_reconnect_attempts:
                self._reconnect_count += 1
                backoff = min(2 ** self._reconnect_count, 30)
                logger.info(f"Reconnecting in {backoff}s (attempt {self._reconnect_count})")
                await asyncio.sleep(backoff)
                return await self.connect(auth_token)

            # Fall back to REST polling
            logger.warning("WebSocket unavailable, falling back to REST polling")
            self._use_fallback = True
            return False

    async def disconnect(self):
        """Close WebSocket connection."""
        if self._websocket and self._connected:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.warning("Error closing WebSocket", error=str(e))
            finally:
                self._connected = False
                self._websocket = None

    async def subscribe_to_task(
        self,
        task_id: str,
        callback: Callable[[StatusUpdate], None],
        auth_token: Optional[str] = None
    ):
        """
        Subscribe to status updates for a specific task.

        Args:
            task_id: Celery task ID
            callback: Function to call with each status update
            auth_token: Optional auth token
        """
        if self._use_fallback:
            # Use REST polling fallback
            await self._polling_fallback.poll_task_status(
                task_id=task_id,
                on_update=callback,
                auth_token=auth_token
            )
            return

        if not self._connected:
            await self.connect(auth_token)

        if self._use_fallback:
            # Connection failed, use fallback
            await self._polling_fallback.poll_task_status(
                task_id=task_id,
                on_update=callback,
                auth_token=auth_token
            )
            return

        # Send subscription request
        subscription_key = f"task-{task_id}"
        self._subscriptions[subscription_key] = callback

        try:
            subscribe_msg = json.dumps({
                "type": "subscribe",
                "resource_type": "task",
                "resource_id": task_id
            })
            await self._websocket.send(subscribe_msg)
            logger.info("Subscribed to task updates", task_id=task_id)

        except Exception as e:
            logger.error("Failed to subscribe to task", task_id=task_id, error=str(e))
            # Fall back to polling
            self._use_fallback = True
            await self._polling_fallback.poll_task_status(
                task_id=task_id,
                on_update=callback,
                auth_token=auth_token
            )

    async def subscribe_to_document(
        self,
        document_id: str,
        callback: Callable[[StatusUpdate], None],
        auth_token: Optional[str] = None
    ):
        """
        Subscribe to status updates for a document.

        Args:
            document_id: Document ID
            callback: Function to call with each status update
            auth_token: Optional auth token
        """
        if self._use_fallback:
            await self._polling_fallback.poll_document_status(
                document_id=document_id,
                on_update=callback,
                auth_token=auth_token
            )
            return

        if not self._connected:
            await self.connect(auth_token)

        if self._use_fallback:
            await self._polling_fallback.poll_document_status(
                document_id=document_id,
                on_update=callback,
                auth_token=auth_token
            )
            return

        subscription_key = f"document-{document_id}"
        self._subscriptions[subscription_key] = callback

        try:
            subscribe_msg = json.dumps({
                "type": "subscribe",
                "resource_type": "document",
                "resource_id": document_id
            })
            await self._websocket.send(subscribe_msg)
            logger.info("Subscribed to document updates", document_id=document_id)

        except Exception as e:
            logger.error("Failed to subscribe to document", document_id=document_id, error=str(e))
            self._use_fallback = True
            await self._polling_fallback.poll_document_status(
                document_id=document_id,
                on_update=callback,
                auth_token=auth_token
            )

    async def listen(self):
        """
        Listen for incoming status updates and dispatch to callbacks.
        This runs in a loop until disconnected.
        """
        if not self._connected or self._use_fallback:
            return

        try:
            async for message in self._websocket:
                try:
                    data = json.loads(message)

                    # Parse status update
                    resource_type = data.get("resource_type", "task")
                    resource_id = data.get("resource_id", data.get("task_id", ""))

                    status_update = self._parse_ws_message(data)

                    # Find matching callback
                    subscription_key = f"{resource_type}-{resource_id}"
                    callback = self._subscriptions.get(subscription_key)

                    if callback:
                        callback(status_update)

                        # Remove subscription if complete
                        if not status_update.should_continue_polling:
                            self._subscriptions.pop(subscription_key, None)

                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON from WebSocket")
                except Exception as e:
                    logger.error("Error processing WebSocket message", error=str(e))

        except Exception as e:
            logger.error("WebSocket connection error", error=str(e))
            self._connected = False

            # Auto-reconnect if enabled
            if self.auto_reconnect and self._reconnect_count < self.max_reconnect_attempts:
                await self.connect()
                if self._connected:
                    await self.listen()

    def _parse_ws_message(self, data: Dict[str, Any]) -> StatusUpdate:
        """Parse WebSocket message into StatusUpdate."""
        progress = None
        if data.get("progress"):
            prog = data["progress"]
            progress = ProgressData(
                current=prog.get("current", 0),
                total=prog.get("total", 100),
                percentage=prog.get("percentage", 0),
                message=prog.get("message", ""),
                stage=prog.get("stage"),
                stage_index=prog.get("stage_index"),
                total_stages=prog.get("total_stages")
            )

        try:
            status = ProcessingStatus(data.get("status", "unknown").lower())
        except ValueError:
            status = ProcessingStatus.UNKNOWN

        # Determine if polling should continue
        terminal_states = [
            ProcessingStatus.SUCCESS,
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILURE,
            ProcessingStatus.FAILED,
            ProcessingStatus.CANCELLED
        ]
        should_continue = status not in terminal_states

        return StatusUpdate(
            resource_id=data.get("resource_id", data.get("task_id", "")),
            resource_type=data.get("resource_type", "task"),
            status=status,
            status_message=data.get("status_message", data.get("message", "")),
            progress=progress,
            error=data.get("error"),
            result=data.get("result"),
            poll_interval_ms=data.get("poll_interval_ms", 2000),
            should_continue_polling=should_continue
        )

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected

    @property
    def using_fallback(self) -> bool:
        """Check if using REST polling fallback."""
        return self._use_fallback


# ============================================================================
# Integrated Status Display Functions for Chat UI
# ============================================================================

def create_inline_status_html(
    status: ProcessingStatus,
    message: str,
    percentage: float = 0,
    compact: bool = True
) -> str:
    """
    Create a compact inline status indicator for chat messages.

    Args:
        status: Current processing status
        message: Status message
        percentage: Progress percentage
        compact: Whether to use compact display

    Returns:
        HTML string for inline status
    """
    style = STATUS_STYLES.get(status, STATUS_STYLES[ProcessingStatus.UNKNOWN])

    if compact:
        return f"""
        <div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px;
                    background: {style['color']}15; border-radius: 16px; font-size: 13px;
                    border: 1px solid {style['color']}30;">
            <span style="animation: {'pulse 1.5s infinite' if status in [ProcessingStatus.PROCESSING, ProcessingStatus.STARTED] else 'none'};">
                {style['icon']}
            </span>
            <span style="color: {style['color']};">{message}</span>
            {f'<span style="opacity: 0.7;">({int(percentage)}%)</span>' if percentage > 0 else ''}
        </div>
        """

    return create_progress_bar_html(percentage, message, indeterminate=status == ProcessingStatus.QUEUED)


def create_error_display_html(
    error_type: str,
    error_message: str,
    retry_count: int = 0,
    max_retries: int = 3,
    is_retryable: bool = True
) -> str:
    """
    Create an error display with retry information.

    Args:
        error_type: Type of error
        error_message: Error description
        retry_count: Number of retries attempted
        max_retries: Maximum retries allowed
        is_retryable: Whether error can be retried

    Returns:
        HTML string for error display
    """
    retry_info = ""
    if is_retryable and retry_count < max_retries:
        retry_info = f"""
        <div style="margin-top: 8px; font-size: 12px; color: #64748b;">
            Retry {retry_count + 1} of {max_retries} in progress...
        </div>
        """
    elif retry_count >= max_retries:
        retry_info = """
        <div style="margin-top: 8px; font-size: 12px; color: #dc2626;">
            ⚠️ All retries exhausted. Please try again later.
        </div>
        """

    return f"""
    <div style="padding: 16px; background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
                border-radius: 12px; border-left: 4px solid #dc2626; margin: 12px 0;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span style="font-size: 20px;">❌</span>
            <strong style="color: #dc2626;">{error_type}</strong>
        </div>
        <p style="margin: 0; color: #7f1d1d;">{error_message}</p>
        {retry_info}
    </div>
    """


def create_success_display_html(
    message: str,
    duration_seconds: Optional[float] = None,
    result_preview: Optional[str] = None
) -> str:
    """
    Create a success display with optional duration and result preview.

    Args:
        message: Success message
        duration_seconds: Optional processing duration
        result_preview: Optional preview of result

    Returns:
        HTML string for success display
    """
    duration_info = ""
    if duration_seconds is not None:
        if duration_seconds < 1:
            duration_info = f"Completed in {int(duration_seconds * 1000)}ms"
        elif duration_seconds < 60:
            duration_info = f"Completed in {duration_seconds:.1f}s"
        else:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            duration_info = f"Completed in {minutes}m {seconds}s"

    preview_html = ""
    if result_preview:
        preview_html = f"""
        <div style="margin-top: 12px; padding: 8px; background: white; border-radius: 6px;
                    font-size: 13px; color: #374151; max-height: 100px; overflow: hidden;">
            {result_preview[:200]}{'...' if len(result_preview) > 200 else ''}
        </div>
        """

    return f"""
    <div style="padding: 16px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
                border-radius: 12px; border-left: 4px solid #10b981; margin: 12px 0;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span style="font-size: 20px;">✅</span>
            <strong style="color: #059669;">{message}</strong>
        </div>
        {f'<p style="margin: 0; font-size: 12px; color: #64748b;">{duration_info}</p>' if duration_info else ''}
        {preview_html}
    </div>
    """


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "ProcessingStatus",
    "ProcessingStage",
    "ProgressData",
    "StatusUpdate",
    "StatusPollingClient",
    "WebSocketStatusClient",
    "PROCESSING_STATUS_CSS",
    "create_progress_bar_html",
    "create_stage_pipeline_html",
    "create_status_badge_html",
    "create_processing_status_component",
    "create_document_upload_status_component",
    "create_query_status_component",
    "create_inline_status_html",
    "create_error_display_html",
    "create_success_display_html",
]
