"""
Empire v7.3 - Agent Interaction API Routes (Task 39)
REST API for inter-agent messaging, events, state sync, and conflict resolution
"""

from fastapi import APIRouter, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import asyncio
import json

from app.core.connections import get_supabase, get_redis
from app.services.agent_interaction_service import get_agent_interaction_service, AgentInteractionService
from app.models.agent_interactions import (
    DirectMessageRequest,
    BroadcastMessageRequest,
    EventPublicationRequest,
    StateSyncRequest,
    ConflictReportRequest,
    AgentInteractionResponse,
    ConflictResolutionRequest,
    ConflictSummaryResponse,
    PendingResponsesResponse,
    BroadcastMessageResponse,
    EventType,
    InteractionHistoryResponse,
    AgentActivityResponse,
    InteractionTimelineResponse,
    ConflictAnalyticsResponse,
    MessageFlowResponse
)

router = APIRouter(prefix="/api/crewai/agent-interactions", tags=["Agent Interactions (Task 39)"])


def get_service() -> AgentInteractionService:
    """Dependency to get AgentInteractionService instance"""
    supabase = get_supabase()
    redis_client = get_redis()
    return get_agent_interaction_service(supabase, redis_client)


# ==================== Messaging Endpoints (Subtask 39.2) ====================

@router.post("/messages/direct", response_model=AgentInteractionResponse, status_code=status.HTTP_201_CREATED)
async def send_direct_message(
    request: DirectMessageRequest,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Send a direct message from one agent to another.

    **Use Cases:**
    - Request information from another agent
    - Delegate a subtask
    - Share results or data

    **Returns:** Created message interaction
    """
    try:
        return await service.send_direct_message(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/messages/broadcast", response_model=BroadcastMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_broadcast_message(
    request: BroadcastMessageRequest,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Broadcast a message to all agents in the crew.

    **Use Cases:**
    - Announce workflow phase changes
    - Share important updates with all agents
    - Coordinate collective actions

    **Returns:** Broadcast confirmation with agent count
    """
    try:
        return await service.send_broadcast_message(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/messages/{interaction_id}/respond", response_model=AgentInteractionResponse)
async def respond_to_message(
    interaction_id: UUID,
    responder_agent_id: UUID,
    response_text: str,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Respond to a message that requires a response.

    **Use Cases:**
    - Answer a question from another agent
    - Acknowledge a delegation request
    - Provide requested data

    **Returns:** Updated interaction with response
    """
    try:
        return await service.respond_to_message(interaction_id, responder_agent_id, response_text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== Event Endpoints (Subtask 39.3) ====================

@router.post("/events/publish", response_model=AgentInteractionResponse, status_code=status.HTTP_201_CREATED)
async def publish_event(
    request: EventPublicationRequest,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Publish an event for workflow coordination and monitoring.

    **Event Types:**
    - `task_started`, `task_completed`, `task_failed`: Task lifecycle events
    - `task_delegated`, `delegation_accepted`, `delegation_rejected`: Delegation events
    - `agent_error`, `agent_idle`: Agent status events
    - `data_shared`, `workflow_started`, `workflow_completed`: Coordination events

    **Returns:** Created event interaction
    """
    try:
        return await service.publish_event(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/events/{execution_id}", response_model=List[AgentInteractionResponse])
async def get_events(
    execution_id: UUID,
    event_types: Optional[List[EventType]] = None,
    since: Optional[datetime] = None,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Retrieve events for an execution, optionally filtered by type and time.

    **Query Parameters:**
    - `event_types`: Filter by specific event types (comma-separated)
    - `since`: Get events after this timestamp (ISO 8601 format)

    **Returns:** List of event interactions
    """
    try:
        return await service.subscribe_to_events(execution_id, event_types, since)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== State Synchronization Endpoints (Subtask 39.4) ====================

@router.post("/state/sync", response_model=AgentInteractionResponse, status_code=status.HTTP_201_CREATED)
async def synchronize_state(
    request: StateSyncRequest,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Synchronize shared state across agents with automatic conflict detection.

    Uses optimistic locking via `state_version` to prevent lost updates.

    **Conflict Detection:**
    - If `state_version` ≤ current version, a conflict is automatically detected and reported
    - Returns HTTP 409 Conflict with details

    **Returns:** Created state sync interaction

    **Raises:**
    - `409 Conflict`: If state version conflict is detected
    """
    try:
        return await service.synchronize_state(request)
    except ValueError as e:
        # Version conflict
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/state/{execution_id}/{state_key}", response_model=Optional[AgentInteractionResponse])
async def get_current_state(
    execution_id: UUID,
    state_key: str,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get the current (latest) state for a given key.

    **Use Cases:**
    - Read shared task progress
    - Check current workflow phase
    - Verify data availability

    **Returns:** Latest state sync record, or null if not found
    """
    try:
        return await service.get_current_state(execution_id, state_key)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== Conflict Resolution Endpoints (Subtask 39.5) ====================

@router.post("/conflicts/report", response_model=AgentInteractionResponse, status_code=status.HTTP_201_CREATED)
async def report_conflict(
    request: ConflictReportRequest,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Manually report a detected conflict between agents.

    **Conflict Types:**
    - `concurrent_update`: Multiple agents updated the same state simultaneously
    - `duplicate_assignment`: Same task assigned to multiple agents
    - `resource_contention`: Multiple agents requesting the same resource
    - `state_mismatch`: Agent states are inconsistent
    - `deadline_conflict`: Conflicting deadline requirements
    - `priority_conflict`: Conflicting task priorities

    **Returns:** Created conflict interaction
    """
    try:
        return await service.report_conflict(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/conflicts/{conflict_id}/resolve", response_model=AgentInteractionResponse)
async def resolve_conflict(
    conflict_id: UUID,
    request: ConflictResolutionRequest,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Resolve a previously reported conflict.

    **Resolution Strategies:**
    - `latest_wins`: Accept the most recent update
    - `manual`: Human intervention required
    - `merge`: Attempt to merge conflicting changes
    - `rollback`: Revert to previous state
    - `escalate`: Escalate to supervising agent

    **Returns:** Updated conflict record
    """
    try:
        # Override conflict_id from path
        request.conflict_id = conflict_id
        return await service.resolve_conflict(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/conflicts/{execution_id}/unresolved", response_model=ConflictSummaryResponse)
async def get_unresolved_conflicts(
    execution_id: UUID,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get all unresolved conflicts for an execution.

    **Use Cases:**
    - Monitor workflow health
    - Trigger alerts for long-running conflicts
    - Prioritize conflict resolution

    **Returns:** Summary of unresolved conflicts with details
    """
    try:
        return await service.get_unresolved_conflicts(execution_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/responses/{execution_id}/pending", response_model=PendingResponsesResponse)
async def get_pending_responses(
    execution_id: UUID,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get all messages awaiting responses with deadline tracking.

    **Response Status:**
    - `pending`: Response expected, deadline not reached
    - `urgent`: Response due within 5 minutes
    - `overdue`: Response deadline has passed

    **Use Cases:**
    - Monitor agent responsiveness
    - Trigger escalations for overdue responses
    - Track workflow bottlenecks

    **Returns:** Summary of pending responses
    """
    try:
        return await service.get_pending_responses(execution_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== Analytics Endpoints ====================

@router.get("/history", response_model=InteractionHistoryResponse)
async def get_interaction_history(
    execution_id: UUID,
    agent_id: Optional[UUID] = None,
    interaction_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get interaction history with filters and pagination.

    **Query Parameters:**
    - `execution_id`: Execution to get history for (required)
    - `agent_id`: Filter by specific agent (from or to)
    - `interaction_type`: Filter by type (message, event, state_sync, conflict)
    - `start_date`: Get interactions after this timestamp
    - `end_date`: Get interactions before this timestamp
    - `limit`: Maximum number of results (default: 100)
    - `offset`: Pagination offset (default: 0)

    **Returns:** Paginated list of interactions with metadata
    """
    try:
        return await service.get_interaction_history(
            execution_id=execution_id,
            agent_id=agent_id,
            interaction_type=interaction_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/agent-activity", response_model=AgentActivityResponse)
async def get_agent_activity(
    execution_id: UUID,
    time_window: str = "24h",
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get agent activity metrics for an execution.

    **Query Parameters:**
    - `execution_id`: Execution to analyze (required)
    - `time_window`: Time window (1h, 6h, 24h, 7d) - default: 24h

    **Returns:** Agent activity metrics including:
    - Messages sent/received per agent
    - Events published per agent
    - Conflicts detected per agent
    - Last activity timestamp per agent
    """
    try:
        return await service.get_agent_activity(
            execution_id=execution_id,
            time_window=time_window
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/timeline", response_model=InteractionTimelineResponse)
async def get_interaction_timeline(
    execution_id: UUID,
    granularity: str = "hour",
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get interaction timeline with time-series data.

    **Query Parameters:**
    - `execution_id`: Execution to analyze (required)
    - `granularity`: Time granularity (minute, hour, day) - default: hour

    **Returns:** Time-series data showing:
    - Message count over time
    - Event count over time
    - State sync count over time
    - Conflict count over time
    """
    try:
        return await service.get_interaction_timeline(
            execution_id=execution_id,
            granularity=granularity
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/conflicts", response_model=ConflictAnalyticsResponse)
async def get_conflict_analytics(
    execution_id: UUID,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get conflict analytics and resolution statistics.

    **Query Parameters:**
    - `execution_id`: Execution to analyze (required)

    **Returns:** Conflict analytics including:
    - Total/resolved/unresolved conflict counts
    - Conflict breakdown by type
    - Resolution strategy distribution
    - Average resolution time in minutes
    """
    try:
        return await service.get_conflict_analytics(execution_id=execution_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analytics/message-flow", response_model=MessageFlowResponse)
async def get_message_flow(
    execution_id: UUID,
    service: AgentInteractionService = Depends(get_service)
):
    """
    Get message flow graph showing communication patterns.

    **Query Parameters:**
    - `execution_id`: Execution to analyze (required)

    **Returns:** Message flow graph with:
    - Nodes: Agents with message counts
    - Edges: Message flows between agents with counts
    - Can be visualized as a directed graph
    """
    try:
        return await service.get_message_flow(execution_id=execution_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== WebSocket Real-Time Streaming (Priority 4) ====================

@router.websocket("/ws/{execution_id}")
async def agent_interaction_websocket(
    websocket: WebSocket,
    execution_id: UUID
):
    """
    WebSocket endpoint for real-time streaming of agent interactions.

    **Connection**:
    - Connect to: `ws://localhost:8000/api/crewai/agent-interactions/ws/{execution_id}`
    - Streams all interactions (messages, events, state syncs, conflicts) in real-time

    **Message Format**:
    ```json
    {
        "id": "uuid",
        "execution_id": "uuid",
        "interaction_type": "message|event|state_sync|conflict",
        "from_agent_id": "uuid",
        "to_agent_id": "uuid|null",
        "message": "...",
        "created_at": "ISO8601 timestamp",
        ... (additional fields based on interaction type)
    }
    ```

    **Use Cases**:
    - Real-time dashboards showing agent activity
    - Live debugging of multi-agent workflows
    - Monitoring conflict resolution in real-time
    - Tracking message flows as they occur

    **Error Handling**:
    - Automatically reconnects on Redis connection loss
    - Gracefully handles client disconnections
    - Logs all WebSocket errors for debugging
    """
    await websocket.accept()

    try:
        # Get Redis client
        redis_client = get_redis()

        if not redis_client:
            await websocket.send_json({
                "error": "Redis not configured - real-time streaming unavailable"
            })
            await websocket.close()
            return

        # Subscribe to execution-specific channel
        channel = f"agent_interactions:{execution_id}"
        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel)

        await websocket.send_json({
            "status": "connected",
            "execution_id": str(execution_id),
            "channel": channel,
            "message": "Streaming agent interactions in real-time"
        })

        # Listen for messages from Redis pub/sub
        async def redis_listener():
            """Listen to Redis pub/sub and forward to WebSocket"""
            try:
                for message in pubsub.listen():
                    if message["type"] == "message":
                        # Parse interaction data
                        interaction_data = json.loads(message["data"])

                        # Send to WebSocket client
                        await websocket.send_json(interaction_data)

            except Exception as e:
                await websocket.send_json({
                    "error": f"Redis listener error: {str(e)}"
                })

        # Listen for WebSocket disconnection
        async def websocket_receiver():
            """Handle incoming WebSocket messages (keep-alive, close)"""
            try:
                while True:
                    data = await websocket.receive_text()
                    # Echo ping/pong for keep-alive
                    if data == "ping":
                        await websocket.send_text("pong")
            except WebSocketDisconnect:
                # Client disconnected
                pass

        # Run both tasks concurrently
        await asyncio.gather(
            redis_listener(),
            websocket_receiver()
        )

    except WebSocketDisconnect:
        # Client disconnected
        if pubsub:
            pubsub.unsubscribe()
            pubsub.close()

    except Exception as e:
        await websocket.send_json({
            "error": f"WebSocket error: {str(e)}"
        })
        await websocket.close()

    finally:
        # Cleanup
        if pubsub:
            pubsub.unsubscribe()
            pubsub.close()
