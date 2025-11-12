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


class AgentInteractionService:
    """
    Service for managing inter-agent interactions in CrewAI workflows.

    Features:
    - Direct and broadcast messaging (Subtask 39.2)
    - Event publication for coordination (Subtask 39.3)
    - State synchronization with conflict detection (Subtask 39.4)
    - Automatic and manual conflict resolution (Subtask 39.5)
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase

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

            total_agents = len(crew_response.data["agent_ids"]) if crew_response.data and crew_response.data.get("agent_ids") else 0

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

            logger.info(
                "Conflict resolved",
                conflict_id=str(request.conflict_id),
                strategy=request.resolution_strategy
            )

            return AgentInteractionResponse(**conflict)

        except Exception as e:
            logger.error("Failed to resolve conflict", error=str(e), exc_info=True)
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


def get_agent_interaction_service(supabase: Client) -> AgentInteractionService:
    """Factory function to create AgentInteractionService instance"""
    return AgentInteractionService(supabase=supabase)
