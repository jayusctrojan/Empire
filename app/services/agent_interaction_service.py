"""
Empire v7.3 - Agent Interaction Service (Task 39)
Handles inter-agent messaging, events, state sync, and conflict resolution
Implements Subtasks 39.2, 39.3, 39.4, 39.5
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from supabase import Client
import structlog
from prometheus_client import Counter, Histogram, Gauge
import redis
import json

from app.models.agent_interactions import (
    DirectMessageRequest,
    BroadcastMessageRequest,
    EventPublicationRequest,
    StateSyncRequest,
    ConflictReportRequest,
    AgentInteractionResponse,
    ConflictResolutionRequest,
    StateUpdateRequest,
    MessageThreadResponse,
    ConflictSummaryResponse,
    PendingResponsesResponse,
    BroadcastMessageResponse,
    InteractionType,
    EventType,
    ConflictType,
    ResolutionStrategy
)

logger = structlog.get_logger(__name__)

# Prometheus Metrics for Agent Interactions
AGENT_INTERACTION_TOTAL = Counter(
    'agent_interaction_total',
    'Total agent interactions by type',
    ['interaction_type', 'execution_id']
)

AGENT_INTERACTION_DURATION = Histogram(
    'agent_interaction_duration_seconds',
    'Time spent processing agent interactions',
    ['interaction_type']
)

AGENT_CONFLICTS_DETECTED = Counter(
    'agent_conflicts_detected_total',
    'Total conflicts detected by type',
    ['conflict_type', 'execution_id']
)

AGENT_CONFLICTS_RESOLVED = Counter(
    'agent_conflicts_resolved_total',
    'Total conflicts resolved by strategy',
    ['resolution_strategy', 'execution_id']
)

AGENT_STATE_SYNC_CONFLICTS = Counter(
    'agent_state_sync_conflicts_total',
    'State synchronization version conflicts',
    ['state_key', 'execution_id']
)

AGENT_ACTIVE_INTERACTIONS = Gauge(
    'agent_active_interactions',
    'Currently active interactions by execution',
    ['execution_id']
)

AGENT_BROADCAST_RECIPIENTS = Histogram(
    'agent_broadcast_recipients',
    'Number of recipients for broadcast messages',
    buckets=[1, 2, 5, 10, 20, 50, 100]
)


class AgentInteractionService:
    """
    Service for managing inter-agent interactions in CrewAI workflows.

    Features:
    - Direct and broadcast messaging (Subtask 39.2)
    - Event publication for coordination (Subtask 39.3)
    - State synchronization with conflict detection (Subtask 39.4)
    - Automatic and manual conflict resolution (Subtask 39.5)
    - Real-time WebSocket streaming via Redis pub/sub (Priority 4)
    """

    def __init__(self, supabase: Client, redis_client: Optional[redis.Redis] = None):
        self.supabase = supabase
        self.redis = redis_client

    def _publish_interaction(self, execution_id: UUID, interaction: Dict[str, Any]):
        """
        Publish interaction to Redis pub/sub for real-time WebSocket streaming.

        Args:
            execution_id: Execution ID to publish to
            interaction: Interaction data to publish
        """
        if not self.redis:
            return  # Redis not configured, skip pub/sub

        try:
            # Publish to execution-specific channel
            channel = f"agent_interactions:{execution_id}"
            message = json.dumps(interaction, default=str)  # default=str handles UUID serialization
            self.redis.publish(channel, message)

            logger.debug(
                "Published interaction to Redis",
                channel=channel,
                interaction_id=interaction.get("id")
            )
        except Exception as e:
            # Non-critical: log error but don't fail the request
            logger.error("Failed to publish interaction to Redis", error=str(e))

    # ==================== Subtask 39.2: Direct and Broadcast Messaging ====================

    async def send_direct_message(
        self,
        request: DirectMessageRequest
    ) -> AgentInteractionResponse:
        """
        Send a direct message from one agent to another.

        Args:
            request: Direct message request with from/to agent IDs and message content

        Returns:
            Created interaction record
        """
        # Track metrics
        start_time = datetime.now()

        try:
            logger.info(
                "Sending direct message",
                from_agent=str(request.from_agent_id),
                to_agent=str(request.to_agent_id),
                requires_response=request.requires_response
            )

            # Insert interaction record
            response = self.supabase.table("crewai_agent_interactions").insert({
                "execution_id": str(request.execution_id),
                "from_agent_id": str(request.from_agent_id),
                "to_agent_id": str(request.to_agent_id),
                "interaction_type": request.interaction_type,
                "message": request.message,
                "priority": request.priority,
                "requires_response": request.requires_response,
                "response_deadline": request.response_deadline.isoformat() if request.response_deadline else None,
                "metadata": request.metadata
            }).execute()

            if not response.data:
                raise ValueError("Failed to create interaction record")

            interaction = response.data[0]

            # Publish to Redis for WebSocket streaming
            self._publish_interaction(request.execution_id, interaction)

            # Update Prometheus metrics
            AGENT_INTERACTION_TOTAL.labels(
                interaction_type="message",
                execution_id=str(request.execution_id)
            ).inc()

            duration = (datetime.now() - start_time).total_seconds()
            AGENT_INTERACTION_DURATION.labels(interaction_type="message").observe(duration)

            logger.info(
                "Direct message sent",
                interaction_id=interaction["id"],
                from_agent=str(request.from_agent_id),
                to_agent=str(request.to_agent_id)
            )

            return AgentInteractionResponse(**interaction)

        except Exception as e:
            logger.error("Failed to send direct message", error=str(e), exc_info=True)
            raise

    async def send_broadcast_message(
        self,
        request: BroadcastMessageRequest
    ) -> BroadcastMessageResponse:
        """
        Broadcast a message to all agents in the crew.

        Args:
            request: Broadcast message request (to_agent_id must be None)

        Returns:
            Broadcast confirmation with agent count
        """
        try:
            logger.info(
                "Sending broadcast message",
                from_agent=str(request.from_agent_id),
                execution_id=str(request.execution_id)
            )

            # Get all agents in this execution's crew
            execution_response = self.supabase.table("crewai_executions") \
                .select("crew_id") \
                .eq("id", str(request.execution_id)) \
                .execute()

            if not execution_response.data:
                raise ValueError(f"Execution {request.execution_id} not found")

            crew_id = execution_response.data[0]["crew_id"]

            # Count agents in the crew (agent_ids is an ARRAY column in crewai_crews)
            crew_response = self.supabase.table("crewai_crews") \
                .select("agent_ids") \
                .eq("id", crew_id) \
                .single() \
                .execute()

            if not crew_response.data:
                raise ValueError(f"Crew {crew_id} not found")
            agent_ids = crew_response.data.get("agent_ids") or []
            total_agents = len(agent_ids)

            # Create broadcast interaction
            broadcast_response = self.supabase.table("crewai_agent_interactions").insert({
                "execution_id": str(request.execution_id),
                "from_agent_id": str(request.from_agent_id),
                "to_agent_id": None,  # Null = broadcast
                "interaction_type": request.interaction_type,
                "message": request.message,
                "priority": request.priority,
                "metadata": {
                    **request.metadata,
                    "broadcast": True,
                    "total_agents": total_agents
                }
            }).execute()

            if not broadcast_response.data:
                raise ValueError("Failed to create broadcast interaction")

            broadcast = broadcast_response.data[0]

            # Publish to Redis for WebSocket streaming
            self._publish_interaction(request.execution_id, broadcast)

            # Update Prometheus metrics
            AGENT_INTERACTION_TOTAL.labels(
                interaction_type="broadcast",
                execution_id=str(request.execution_id)
            ).inc()
            AGENT_BROADCAST_RECIPIENTS.observe(total_agents)

            logger.info(
                "Broadcast message sent",
                broadcast_id=broadcast["id"],
                from_agent=str(request.from_agent_id),
                total_agents=total_agents
            )

            return BroadcastMessageResponse(
                broadcast_id=broadcast["id"],
                execution_id=request.execution_id,
                from_agent_id=request.from_agent_id,
                message=request.message,
                total_agents=total_agents,
                broadcast_at=datetime.fromisoformat(broadcast["created_at"])
            )

        except Exception as e:
            logger.error("Failed to send broadcast message", error=str(e), exc_info=True)
            raise

    async def respond_to_message(
        self,
        interaction_id: UUID,
        responder_agent_id: UUID,
        response_text: str
    ) -> AgentInteractionResponse:
        """
        Respond to a message that requires a response.

        Args:
            interaction_id: ID of the message being responded to
            responder_agent_id: Agent sending the response
            response_text: Response content

        Returns:
            Updated interaction with response
        """
        try:
            logger.info(
                "Responding to message",
                interaction_id=str(interaction_id),
                responder=str(responder_agent_id)
            )

            # Update the original interaction with the response
            update_response = self.supabase.table("crewai_agent_interactions") \
                .update({"response": response_text}) \
                .eq("id", str(interaction_id)) \
                .execute()

            if not update_response.data:
                raise ValueError(f"Interaction {interaction_id} not found")

            interaction = update_response.data[0]

            # Publish to Redis for WebSocket streaming
            # Note: Need to extract execution_id from the interaction
            self._publish_interaction(UUID(interaction["execution_id"]), interaction)

            logger.info("Message response recorded", interaction_id=str(interaction_id))

            return AgentInteractionResponse(**interaction)

        except Exception as e:
            logger.error("Failed to respond to message", error=str(e), exc_info=True)
            raise

    # ==================== Subtask 39.3: Event Publication ====================

    async def publish_event(
        self,
        request: EventPublicationRequest
    ) -> AgentInteractionResponse:
        """
        Publish an event for workflow coordination and monitoring.

        Events notify other agents about state changes, completions, errors, etc.

        Args:
            request: Event publication request with event type and data

        Returns:
            Created event interaction record
        """
        try:
            logger.info(
                "Publishing event",
                event_type=request.event_type,
                from_agent=str(request.from_agent_id),
                execution_id=str(request.execution_id)
            )

            # Insert event interaction
            response = self.supabase.table("crewai_agent_interactions").insert({
                "execution_id": str(request.execution_id),
                "from_agent_id": str(request.from_agent_id),
                "to_agent_id": str(request.to_agent_id) if request.to_agent_id else None,
                "interaction_type": "event",
                "message": request.message,
                "event_type": request.event_type,
                "event_data": request.event_data,
                "priority": request.priority,
                "metadata": request.metadata
            }).execute()

            if not response.data:
                raise ValueError("Failed to publish event")

            event = response.data[0]

            # Publish to Redis for WebSocket streaming
            self._publish_interaction(request.execution_id, event)

            logger.info(
                "Event published",
                event_id=event["id"],
                event_type=request.event_type,
                from_agent=str(request.from_agent_id)
            )

            return AgentInteractionResponse(**event)

        except Exception as e:
            logger.error("Failed to publish event", error=str(e), exc_info=True)
            raise

    async def subscribe_to_events(
        self,
        execution_id: UUID,
        event_types: Optional[List[EventType]] = None,
        since: Optional[datetime] = None
    ) -> List[AgentInteractionResponse]:
        """
        Retrieve events for an execution, optionally filtered by type and time.

        Args:
            execution_id: Execution to get events for
            event_types: Optional list of event types to filter
            since: Optional timestamp to get events after

        Returns:
            List of event interactions
        """
        try:
            query = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .eq("interaction_type", "event") \
                .order("created_at", desc=False)

            if event_types:
                query = query.in_("event_type", event_types)

            if since:
                query = query.gte("created_at", since.isoformat())

            response = query.execute()

            events = [AgentInteractionResponse(**event) for event in response.data]

            logger.info(
                "Events retrieved",
                execution_id=str(execution_id),
                event_count=len(events)
            )

            return events

        except Exception as e:
            logger.error("Failed to retrieve events", error=str(e), exc_info=True)
            raise

    # ==================== Subtask 39.4: State Synchronization ====================

    async def synchronize_state(
        self,
        request: StateSyncRequest
    ) -> AgentInteractionResponse:
        """
        Synchronize shared state across agents with conflict detection.

        Uses optimistic locking (state_version) to detect concurrent updates.

        Args:
            request: State sync request with key, value, and version

        Returns:
            Created state sync interaction

        Raises:
            ValueError: If state version conflict is detected
        """
        try:
            logger.info(
                "Synchronizing state",
                state_key=request.state_key,
                version=request.state_version,
                from_agent=str(request.from_agent_id)
            )

            # Check for existing state with this key
            existing_state_response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(request.execution_id)) \
                .eq("interaction_type", "state_sync") \
                .eq("state_key", request.state_key) \
                .order("state_version", desc=True) \
                .limit(1) \
                .execute()

            # Detect version conflict
            if existing_state_response.data:
                latest_state = existing_state_response.data[0]
                latest_version = latest_state.get("state_version", 0)

                if request.state_version <= latest_version:
                    # Version conflict detected!
                    logger.warning(
                        "State version conflict detected",
                        state_key=request.state_key,
                        expected_version=request.state_version,
                        actual_version=latest_version
                    )

                    # Update Prometheus metrics for state sync conflict
                    AGENT_STATE_SYNC_CONFLICTS.labels(
                        state_key=request.state_key,
                        execution_id=str(request.execution_id)
                    ).inc()

                    # Auto-create conflict record
                    await self.report_conflict(ConflictReportRequest(
                        execution_id=request.execution_id,
                        from_agent_id=request.from_agent_id,
                        to_agent_id=None,
                        interaction_type="conflict",
                        message=f"State version conflict on key '{request.state_key}'",
                        conflict_type="concurrent_update",
                        conflict_detected=True,
                        resolution_data={
                            "state_key": request.state_key,
                            "expected_version": request.state_version,
                            "actual_version": latest_version,
                            "attempted_value": request.state_value,
                            "current_value": latest_state.get("state_value")
                        }
                    ))

                    raise ValueError(
                        f"State version conflict: expected version {request.state_version}, "
                        f"but current version is {latest_version}"
                    )

            # No conflict - create state sync record
            response = self.supabase.table("crewai_agent_interactions").insert({
                "execution_id": str(request.execution_id),
                "from_agent_id": str(request.from_agent_id),
                "to_agent_id": str(request.to_agent_id) if request.to_agent_id else None,
                "interaction_type": "state_sync",
                "message": request.message,
                "state_key": request.state_key,
                "state_value": request.state_value,
                "state_version": request.state_version,
                "previous_state": request.previous_state,
                "priority": request.priority,
                "metadata": request.metadata
            }).execute()

            if not response.data:
                raise ValueError("Failed to create state sync record")

            state_sync = response.data[0]

            # Publish to Redis for WebSocket streaming
            self._publish_interaction(request.execution_id, state_sync)

            logger.info(
                "State synchronized",
                state_id=state_sync["id"],
                state_key=request.state_key,
                version=request.state_version
            )

            return AgentInteractionResponse(**state_sync)

        except Exception as e:
            logger.error("Failed to synchronize state", error=str(e), exc_info=True)
            raise

    async def get_current_state(
        self,
        execution_id: UUID,
        state_key: str
    ) -> Optional[AgentInteractionResponse]:
        """
        Get the current (latest) state for a given key.

        Args:
            execution_id: Execution ID
            state_key: State key to retrieve

        Returns:
            Latest state sync record, or None if not found
        """
        try:
            response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .eq("interaction_type", "state_sync") \
                .eq("state_key", state_key) \
                .order("state_version", desc=True) \
                .limit(1) \
                .execute()

            if not response.data:
                return None

            return AgentInteractionResponse(**response.data[0])

        except Exception as e:
            logger.error("Failed to get current state", error=str(e), exc_info=True)
            raise

    # ==================== Subtask 39.5: Conflict Detection and Resolution ====================

    async def report_conflict(
        self,
        request: ConflictReportRequest
    ) -> AgentInteractionResponse:
        """
        Report a detected conflict between agents.

        Args:
            request: Conflict report with type and details

        Returns:
            Created conflict interaction record
        """
        try:
            logger.warning(
                "Conflict reported",
                conflict_type=request.conflict_type,
                from_agent=str(request.from_agent_id)
            )

            response = self.supabase.table("crewai_agent_interactions").insert({
                "execution_id": str(request.execution_id),
                "from_agent_id": str(request.from_agent_id),
                "to_agent_id": str(request.to_agent_id) if request.to_agent_id else None,
                "interaction_type": "conflict",
                "message": request.message,
                "conflict_detected": True,
                "conflict_type": request.conflict_type,
                "conflict_resolved": request.conflict_resolved,
                "resolution_strategy": request.resolution_strategy,
                "resolution_data": request.resolution_data,
                "priority": request.priority,
                "metadata": request.metadata
            }).execute()

            if not response.data:
                raise ValueError("Failed to report conflict")

            conflict = response.data[0]

            # Publish to Redis for WebSocket streaming
            self._publish_interaction(request.execution_id, conflict)

            # Update Prometheus metrics for conflict detection
            AGENT_CONFLICTS_DETECTED.labels(
                conflict_type=request.conflict_type,
                execution_id=str(request.execution_id)
            ).inc()

            logger.warning(
                "Conflict recorded",
                conflict_id=conflict["id"],
                conflict_type=request.conflict_type
            )

            return AgentInteractionResponse(**conflict)

        except Exception as e:
            logger.error("Failed to report conflict", error=str(e), exc_info=True)
            raise

    async def resolve_conflict(
        self,
        request: ConflictResolutionRequest
    ) -> AgentInteractionResponse:
        """
        Resolve a previously reported conflict.

        Supports both manual and automatic resolution strategies.

        Args:
            request: Resolution request with strategy and data

        Returns:
            Updated conflict record
        """
        try:
            logger.info(
                "Resolving conflict",
                conflict_id=str(request.conflict_id),
                strategy=request.resolution_strategy
            )

            # For auto-resolution strategies, execute the strategy first
            if request.resolution_strategy == "latest_wins":
                await self._resolve_conflict_latest_wins(request.conflict_id)
            elif request.resolution_strategy == "merge":
                await self._resolve_conflict_merge(request.conflict_id)
            elif request.resolution_strategy == "rollback":
                await self._resolve_conflict_rollback(request.conflict_id)
            elif request.resolution_strategy == "escalate":
                await self._resolve_conflict_escalate(request.conflict_id)
            # For "manual" strategy, just mark as resolved with provided data

            # Mark conflict as resolved
            update_response = self.supabase.table("crewai_agent_interactions") \
                .update({
                    "conflict_resolved": True,
                    "resolution_strategy": request.resolution_strategy,
                    "resolution_data": request.resolution_data,
                    "resolved_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", str(request.conflict_id)) \
                .execute()

            if not update_response.data:
                raise ValueError(f"Conflict {request.conflict_id} not found")

            conflict = update_response.data[0]

            # Publish to Redis for WebSocket streaming
            self._publish_interaction(UUID(conflict["execution_id"]), conflict)

            # Update Prometheus metrics for conflict resolution
            AGENT_CONFLICTS_RESOLVED.labels(
                resolution_strategy=request.resolution_strategy,
                execution_id=str(conflict["execution_id"])
            ).inc()

            logger.info(
                "Conflict resolved",
                conflict_id=str(request.conflict_id),
                strategy=request.resolution_strategy
            )

            return AgentInteractionResponse(**conflict)

        except Exception as e:
            logger.error("Failed to resolve conflict", error=str(e), exc_info=True)
            raise

    async def _resolve_conflict_latest_wins(self, conflict_id: UUID):
        """
        Auto-resolve conflict by accepting the most recent state update.

        Strategy: Find the latest state version and apply it.
        """
        try:
            # Get the conflict details
            conflict_response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("id", str(conflict_id)) \
                .single() \
                .execute()

            if not conflict_response.data:
                raise ValueError(f"Conflict {conflict_id} not found")

            conflict = conflict_response.data
            resolution_data = conflict.get("resolution_data", {})

            # Extract state information from conflict
            state_key = resolution_data.get("state_key")
            if not state_key:
                logger.warning("No state_key in conflict resolution_data, skipping latest_wins")
                return

            execution_id = conflict["execution_id"]

            # Get the latest state for this key
            latest_state_response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", execution_id) \
                .eq("interaction_type", "state_sync") \
                .eq("state_key", state_key) \
                .order("state_version", desc=True) \
                .limit(1) \
                .execute()

            if latest_state_response.data:
                latest_state = latest_state_response.data[0]
                logger.info(
                    "Latest wins resolution applied",
                    conflict_id=str(conflict_id),
                    state_key=state_key,
                    winning_version=latest_state.get("state_version")
                )

        except Exception as e:
            logger.error("Failed to apply latest_wins resolution", error=str(e), exc_info=True)
            raise

    async def _resolve_conflict_merge(self, conflict_id: UUID):
        """
        Auto-resolve conflict by attempting to merge non-conflicting changes.

        Strategy: Deep merge JSON objects if no key conflicts exist.
        If key conflicts exist, escalate to manual resolution.
        """
        try:
            # Get the conflict details
            conflict_response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("id", str(conflict_id)) \
                .single() \
                .execute()

            if not conflict_response.data:
                raise ValueError(f"Conflict {conflict_id} not found")

            conflict = conflict_response.data
            resolution_data = conflict.get("resolution_data", {})

            # Get both state versions
            current_value = resolution_data.get("current_value", {})
            attempted_value = resolution_data.get("attempted_value", {})

            # Attempt to merge
            if isinstance(current_value, dict) and isinstance(attempted_value, dict):
                # Check for key conflicts
                current_keys = set(current_value.keys())
                attempted_keys = set(attempted_value.keys())
                common_keys = current_keys & attempted_keys

                # Check if values for common keys are different
                has_conflict = False
                for key in common_keys:
                    if current_value[key] != attempted_value[key]:
                        has_conflict = True
                        break

                if has_conflict:
                    logger.warning(
                        "Merge conflict detected - escalating to manual",
                        conflict_id=str(conflict_id),
                        conflicting_keys=list(common_keys)
                    )
                    # Escalate to manual resolution
                    await self._resolve_conflict_escalate(conflict_id)
                else:
                    # Safe to merge
                    merged_value = {**current_value, **attempted_value}

                    # Create new state sync with merged value
                    state_key = resolution_data.get("state_key")
                    if state_key:
                        execution_id = conflict["execution_id"]
                        from_agent_id = conflict["from_agent_id"]

                        # Get latest version
                        latest_version_response = self.supabase.table("crewai_agent_interactions") \
                            .select("state_version") \
                            .eq("execution_id", execution_id) \
                            .eq("state_key", state_key) \
                            .order("state_version", desc=True) \
                            .limit(1) \
                            .execute()

                        next_version = 1
                        if latest_version_response.data:
                            next_version = latest_version_response.data[0]["state_version"] + 1

                        # Insert merged state
                        self.supabase.table("crewai_agent_interactions").insert({
                            "execution_id": execution_id,
                            "from_agent_id": from_agent_id,
                            "to_agent_id": None,
                            "interaction_type": "state_sync",
                            "message": f"Merged state resolution for conflict {conflict_id}",
                            "state_key": state_key,
                            "state_value": merged_value,
                            "state_version": next_version,
                            "previous_state": current_value,
                            "metadata": {"resolved_conflict_id": str(conflict_id)}
                        }).execute()

                        logger.info(
                            "Merge resolution applied",
                            conflict_id=str(conflict_id),
                            state_key=state_key,
                            merged_version=next_version
                        )

        except Exception as e:
            logger.error("Failed to apply merge resolution", error=str(e), exc_info=True)
            raise

    async def _resolve_conflict_rollback(self, conflict_id: UUID):
        """
        Auto-resolve conflict by reverting to the last known good state.

        Strategy: Restore previous_state from conflict record.
        """
        try:
            # Get the conflict details
            conflict_response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("id", str(conflict_id)) \
                .single() \
                .execute()

            if not conflict_response.data:
                raise ValueError(f"Conflict {conflict_id} not found")

            conflict = conflict_response.data
            resolution_data = conflict.get("resolution_data", {})

            # Get previous state
            current_value = resolution_data.get("current_value")
            state_key = resolution_data.get("state_key")

            if current_value and state_key:
                execution_id = conflict["execution_id"]
                from_agent_id = conflict["from_agent_id"]

                # Get latest version
                latest_version_response = self.supabase.table("crewai_agent_interactions") \
                    .select("state_version") \
                    .eq("execution_id", execution_id) \
                    .eq("state_key", state_key) \
                    .order("state_version", desc=True) \
                    .limit(1) \
                    .execute()

                next_version = 1
                if latest_version_response.data:
                    next_version = latest_version_response.data[0]["state_version"] + 1

                # Insert rollback state (using current_value as it's the "good" state)
                self.supabase.table("crewai_agent_interactions").insert({
                    "execution_id": execution_id,
                    "from_agent_id": from_agent_id,
                    "to_agent_id": None,
                    "interaction_type": "state_sync",
                    "message": f"Rollback resolution for conflict {conflict_id}",
                    "state_key": state_key,
                    "state_value": current_value,
                    "state_version": next_version,
                    "metadata": {"resolved_conflict_id": str(conflict_id), "rollback": True}
                }).execute()

                logger.info(
                    "Rollback resolution applied",
                    conflict_id=str(conflict_id),
                    state_key=state_key,
                    rollback_version=next_version
                )

        except Exception as e:
            logger.error("Failed to apply rollback resolution", error=str(e), exc_info=True)
            raise

    async def _resolve_conflict_escalate(self, conflict_id: UUID):
        """
        Auto-resolve conflict by escalating to a supervising agent.

        Strategy: Send escalation message to supervising agent or crew coordinator.
        """
        try:
            # Get the conflict details
            conflict_response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("id", str(conflict_id)) \
                .single() \
                .execute()

            if not conflict_response.data:
                raise ValueError(f"Conflict {conflict_id} not found")

            conflict = conflict_response.data
            execution_id = conflict["execution_id"]

            # Get the crew to find supervisor/coordinator
            exec_response = self.supabase.table("crewai_executions") \
                .select("crew_id") \
                .eq("id", execution_id) \
                .execute()

            if not exec_response.data:
                logger.warning(f"No execution found for conflict {conflict_id}")
                return

            crew_id = exec_response.data[0]["crew_id"]

            # Get all agents in crew to find supervisor
            crew_response = self.supabase.table("crewai_crews") \
                .select("agent_ids") \
                .eq("id", crew_id) \
                .single() \
                .execute()

            if not crew_response.data or not crew_response.data.get("agent_ids"):
                raise ValueError(f"No agents found for crew {crew_id} during escalation")
            agent_ids = crew_response.data["agent_ids"]

            # For now, escalate to all agents in the crew
            # In production, you'd have a designated supervisor agent
            # Batch insert all escalation events
            escalation_records = [
                {
                    "execution_id": execution_id,
                    "from_agent_id": conflict["from_agent_id"],
                    "to_agent_id": agent_id,
                    "interaction_type": "event",
                    "event_type": "agent_error",
                    "message": f"Conflict escalated: {conflict.get('conflict_type', 'unknown')}",
                    "event_data": {
                        "conflict_id": str(conflict_id),
                        "conflict_type": conflict.get("conflict_type"),
                        "requires_manual_intervention": True
                    },
                    "priority": 10,  # Highest priority
                    "metadata": {"escalated_conflict_id": str(conflict_id)}
                }
                for agent_id in agent_ids
            ]
            insert_response = self.supabase.table("crewai_agent_interactions").insert(escalation_records).execute()
            if not insert_response.data:
                raise ValueError(f"Failed to insert escalation records for conflict {conflict_id}")

            logger.info(
                "Conflict escalated",
                conflict_id=str(conflict_id),
                notified_agents=len(agent_ids)
            )

        except Exception as e:
            logger.error("Failed to escalate conflict", error=str(e), exc_info=True)
            raise

    async def get_unresolved_conflicts(
        self,
        execution_id: UUID
    ) -> ConflictSummaryResponse:
        """
        Get all unresolved conflicts for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            Summary of unresolved conflicts
        """
        try:
            # Query full table for unresolved conflicts (not the view, as it has limited fields)
            response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .eq("conflict_detected", True) \
                .eq("conflict_resolved", False) \
                .order("priority.desc,created_at") \
                .execute()

            conflicts = [AgentInteractionResponse(**c) for c in response.data]

            # Count by type
            conflict_types: Dict[ConflictType, int] = {}
            for conflict in conflicts:
                if conflict.conflict_type:
                    conflict_types[conflict.conflict_type] = conflict_types.get(conflict.conflict_type, 0) + 1

            # Calculate oldest conflict age
            oldest_age = None
            if response.data:
                from datetime import datetime
                from dateutil import parser
                # Use dateutil parser for robust timestamp parsing
                oldest_created = min([parser.isoparse(c["created_at"]) for c in response.data])
                oldest_age = (datetime.now(oldest_created.tzinfo) - oldest_created).total_seconds() / 60

            # Get crew_id from execution
            exec_response = self.supabase.table("crewai_executions") \
                .select("crew_id") \
                .eq("id", str(execution_id)) \
                .execute()
            crew_id = exec_response.data[0]["crew_id"] if exec_response.data else None

            return ConflictSummaryResponse(
                execution_id=execution_id,
                crew_id=crew_id,
                total_conflicts=len(conflicts),
                unresolved_conflicts=len(conflicts),
                conflict_types=conflict_types,
                oldest_conflict_age_minutes=oldest_age,
                conflicts=conflicts
            )

        except Exception as e:
            logger.error("Failed to get unresolved conflicts", error=str(e), exc_info=True)
            raise

    async def get_pending_responses(
        self,
        execution_id: UUID
    ) -> PendingResponsesResponse:
        """
        Get all messages awaiting responses.

        Args:
            execution_id: Execution ID

        Returns:
            Summary of pending responses
        """
        try:
            # Use the view created in the migration
            response = self.supabase.table("crewai_pending_responses") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .execute()

            pending = [AgentInteractionResponse(**p) for p in response.data]

            # Count by status
            overdue_count = sum(1 for p in response.data if p.get("status") == "overdue")
            urgent_count = sum(1 for p in response.data if p.get("status") == "urgent")

            return PendingResponsesResponse(
                execution_id=execution_id,
                total_pending=len(pending),
                overdue_count=overdue_count,
                urgent_count=urgent_count,
                pending_responses=pending
            )

        except Exception as e:
            logger.error("Failed to get pending responses", error=str(e), exc_info=True)
            raise

    # ==================== Analytics Methods ====================

    async def get_interaction_history(
        self,
        execution_id: UUID,
        agent_id: Optional[UUID] = None,
        interaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ):
        """
        Get interaction history with filters and pagination.

        Returns dict with: total, interactions, pagination
        """
        try:
            # Build query
            query = self.supabase.table("crewai_agent_interactions") \
                .select("*", count="exact") \
                .eq("execution_id", str(execution_id)) \
                .order("created_at", desc=True)

            # Apply filters
            if agent_id:
                # Filter by agent (either from or to)
                query = query.or_(f"from_agent_id.eq.{str(agent_id)},to_agent_id.eq.{str(agent_id)}")

            if interaction_type:
                query = query.eq("interaction_type", interaction_type)

            if start_date:
                query = query.gte("created_at", start_date.isoformat())

            if end_date:
                query = query.lte("created_at", end_date.isoformat())

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            response = query.execute()

            total = response.count if hasattr(response, 'count') else len(response.data)
            has_more = total > (offset + len(response.data))

            from app.models.agent_interactions import (
                InteractionHistoryResponse,
                PaginationInfo,
                AgentInteractionResponse
            )

            return InteractionHistoryResponse(
                total=total,
                interactions=[AgentInteractionResponse(**item) for item in response.data],
                pagination=PaginationInfo(
                    limit=limit,
                    offset=offset,
                    has_more=has_more
                )
            )

        except Exception as e:
            logger.error("Failed to get interaction history", error=str(e), exc_info=True)
            raise

    async def get_agent_activity(
        self,
        execution_id: UUID,
        time_window: str = "24h"
    ):
        """
        Get agent activity metrics for an execution.

        Returns dict with: execution_id, time_window, agents (list of metrics)
        """
        try:
            # Calculate time window
            from dateutil import parser as date_parser

            time_windows = {
                "1h": timedelta(hours=1),
                "6h": timedelta(hours=6),
                "24h": timedelta(hours=24),
                "7d": timedelta(days=7)
            }

            delta = time_windows.get(time_window, timedelta(hours=24))
            since = datetime.now() - delta

            # Get all interactions in time window
            response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .gte("created_at", since.isoformat()) \
                .execute()

            # Calculate metrics per agent
            agent_metrics = {}

            for interaction in response.data:
                from_agent = interaction["from_agent_id"]
                to_agent = interaction.get("to_agent_id")
                interaction_type = interaction["interaction_type"]
                created_at = date_parser.isoparse(interaction["created_at"])

                # Initialize agent metrics if needed
                if from_agent not in agent_metrics:
                    agent_metrics[from_agent] = {
                        "agent_id": from_agent,
                        "messages_sent": 0,
                        "messages_received": 0,
                        "events_published": 0,
                        "conflicts_detected": 0,
                        "last_activity": created_at
                    }

                if to_agent and to_agent not in agent_metrics:
                    agent_metrics[to_agent] = {
                        "agent_id": to_agent,
                        "messages_sent": 0,
                        "messages_received": 0,
                        "events_published": 0,
                        "conflicts_detected": 0,
                        "last_activity": created_at
                    }

                # Update metrics
                if interaction_type == "message":
                    agent_metrics[from_agent]["messages_sent"] += 1
                    if to_agent:
                        agent_metrics[to_agent]["messages_received"] += 1
                elif interaction_type == "event":
                    agent_metrics[from_agent]["events_published"] += 1
                elif interaction_type == "conflict":
                    agent_metrics[from_agent]["conflicts_detected"] += 1

                # Update last activity
                if created_at > agent_metrics[from_agent]["last_activity"]:
                    agent_metrics[from_agent]["last_activity"] = created_at

                if to_agent and created_at > agent_metrics[to_agent]["last_activity"]:
                    agent_metrics[to_agent]["last_activity"] = created_at

            from app.models.agent_interactions import (
                AgentActivityResponse,
                AgentActivityMetrics
            )

            return AgentActivityResponse(
                execution_id=execution_id,
                time_window=time_window,
                agents=[AgentActivityMetrics(**metrics) for metrics in agent_metrics.values()]
            )

        except Exception as e:
            logger.error("Failed to get agent activity", error=str(e), exc_info=True)
            raise

    async def get_interaction_timeline(
        self,
        execution_id: UUID,
        granularity: str = "hour"
    ):
        """
        Get interaction timeline with time-series data.

        Returns dict with: execution_id, granularity, timeline (list of data points)
        """
        try:
            from dateutil import parser as date_parser
            from collections import defaultdict

            # Get all interactions
            response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .order("created_at") \
                .execute()

            # Group by time bucket
            timeline_data = defaultdict(lambda: {
                "messages": 0,
                "events": 0,
                "state_syncs": 0,
                "conflicts": 0
            })

            for interaction in response.data:
                created_at = date_parser.isoparse(interaction["created_at"])
                interaction_type = interaction["interaction_type"]

                # Round to granularity
                if granularity == "minute":
                    bucket = created_at.replace(second=0, microsecond=0)
                elif granularity == "hour":
                    bucket = created_at.replace(minute=0, second=0, microsecond=0)
                else:  # day
                    bucket = created_at.replace(hour=0, minute=0, second=0, microsecond=0)

                # Increment counters
                if interaction_type == "message":
                    timeline_data[bucket]["messages"] += 1
                elif interaction_type == "event":
                    timeline_data[bucket]["events"] += 1
                elif interaction_type == "state_sync":
                    timeline_data[bucket]["state_syncs"] += 1
                elif interaction_type == "conflict":
                    timeline_data[bucket]["conflicts"] += 1

            from app.models.agent_interactions import (
                InteractionTimelineResponse,
                TimelineDataPoint
            )

            return InteractionTimelineResponse(
                execution_id=execution_id,
                granularity=granularity,
                timeline=[
                    TimelineDataPoint(timestamp=bucket, **data)
                    for bucket, data in sorted(timeline_data.items())
                ]
            )

        except Exception as e:
            logger.error("Failed to get interaction timeline", error=str(e), exc_info=True)
            raise

    async def get_conflict_analytics(
        self,
        execution_id: UUID
    ):
        """
        Get conflict analytics and resolution statistics.

        Returns dict with: total, resolved, unresolved, by_type, resolution_strategies, avg_resolution_time
        """
        try:
            from dateutil import parser as date_parser

            # Get all conflict interactions
            response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .eq("interaction_type", "conflict") \
                .execute()

            total_conflicts = len(response.data)
            resolved_conflicts = sum(1 for c in response.data if c.get("conflict_resolved"))
            unresolved_conflicts = total_conflicts - resolved_conflicts

            # Count by type
            by_type = {}
            for conflict in response.data:
                conflict_type = conflict.get("conflict_type")
                if conflict_type:
                    by_type[conflict_type] = by_type.get(conflict_type, 0) + 1

            # Count by resolution strategy
            resolution_strategies = {}
            for conflict in response.data:
                if conflict.get("conflict_resolved"):
                    strategy = conflict.get("resolution_strategy")
                    if strategy:
                        resolution_strategies[strategy] = resolution_strategies.get(strategy, 0) + 1

            # Calculate average resolution time
            resolution_times = []
            for conflict in response.data:
                if conflict.get("conflict_resolved") and conflict.get("resolved_at"):
                    created = date_parser.isoparse(conflict["created_at"])
                    resolved = date_parser.isoparse(conflict["resolved_at"])
                    resolution_times.append((resolved - created).total_seconds() / 60)

            avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else None

            from app.models.agent_interactions import ConflictAnalyticsResponse

            return ConflictAnalyticsResponse(
                execution_id=execution_id,
                total_conflicts=total_conflicts,
                resolved_conflicts=resolved_conflicts,
                unresolved_conflicts=unresolved_conflicts,
                by_type=by_type,
                resolution_strategies=resolution_strategies,
                avg_resolution_time_minutes=avg_resolution_time
            )

        except Exception as e:
            logger.error("Failed to get conflict analytics", error=str(e), exc_info=True)
            raise

    async def get_message_flow(
        self,
        execution_id: UUID
    ):
        """
        Get message flow graph showing communication patterns.

        Returns dict with: execution_id, nodes (agents), edges (message flows)
        """
        try:
            from dateutil import parser as date_parser
            from collections import defaultdict

            # Get all message interactions
            response = self.supabase.table("crewai_agent_interactions") \
                .select("*") \
                .eq("execution_id", str(execution_id)) \
                .eq("interaction_type", "message") \
                .execute()

            # Build nodes (agents)
            agent_message_counts = defaultdict(int)

            # Build edges (flows)
            flow_data = defaultdict(lambda: {"count": 0, "total_latency": 0})

            for interaction in response.data:
                from_agent = interaction["from_agent_id"]
                to_agent = interaction.get("to_agent_id")

                agent_message_counts[from_agent] += 1

                if to_agent:
                    agent_message_counts[to_agent] += 1
                    flow_key = (from_agent, to_agent)
                    flow_data[flow_key]["count"] += 1

                    # You could calculate latency here if you have response timestamps
                    # For now, we'll leave avg_latency_ms as None

            from app.models.agent_interactions import (
                MessageFlowResponse,
                MessageFlowNode,
                MessageFlowEdge
            )

            nodes = [
                MessageFlowNode(
                    agent_id=agent_id,
                    name=f"Agent {str(agent_id)[:8]}",
                    message_count=count
                )
                for agent_id, count in agent_message_counts.items()
            ]

            edges = [
                MessageFlowEdge(
                    **{"from": from_agent, "to": to_agent},
                    count=data["count"],
                    avg_latency_ms=None  # Could be calculated with response timestamps
                )
                for (from_agent, to_agent), data in flow_data.items()
            ]

            return MessageFlowResponse(
                execution_id=execution_id,
                nodes=nodes,
                edges=edges
            )

        except Exception as e:
            logger.error("Failed to get message flow", error=str(e), exc_info=True)
            raise


def get_agent_interaction_service(supabase: Client, redis_client: Optional[redis.Redis] = None) -> AgentInteractionService:
    """Factory function to create AgentInteractionService instance with Redis for WebSocket support"""
    return AgentInteractionService(supabase=supabase, redis_client=redis_client)
