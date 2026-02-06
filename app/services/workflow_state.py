"""
Empire v7.3 - Workflow State Management Service

Provides savepoint and rollback functionality for multi-agent workflows.
Enables recovery from failures and state persistence for long-running operations.

Features:
- Savepoint creation at workflow checkpoints
- Rollback to previous savepoints
- State serialization and persistence
- Workflow resumption from savepoints
- Automatic cleanup of old savepoints

Author: Claude Code
Date: 2025-01-24
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

import structlog
from supabase import Client

from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================

class SavepointType(str, Enum):
    """Type of savepoint"""
    MANUAL = "manual"  # User-requested savepoint
    AUTOMATIC = "automatic"  # System-created at checkpoints
    PRE_AGENT = "pre_agent"  # Before agent execution
    POST_AGENT = "post_agent"  # After successful agent execution
    RECOVERY = "recovery"  # Created during recovery


class WorkflowPhase(str, Enum):
    """Workflow execution phase"""
    INITIALIZATION = "initialization"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    WRITING = "writing"
    REVIEW = "review"
    REVISION = "revision"
    FINALIZATION = "finalization"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowSavepoint:
    """Represents a workflow savepoint"""
    savepoint_id: str
    workflow_id: str
    phase: WorkflowPhase
    agent_id: str
    savepoint_type: SavepointType

    # State data
    workflow_state: Dict[str, Any]
    agent_state: Dict[str, Any]
    artifacts: List[Dict[str, Any]]

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    sequence_number: int = 0

    # Validation
    checksum: Optional[str] = None
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "savepoint_id": self.savepoint_id,
            "workflow_id": self.workflow_id,
            "phase": self.phase.value,
            "agent_id": self.agent_id,
            "savepoint_type": self.savepoint_type.value,
            "workflow_state": json.dumps(self.workflow_state),
            "agent_state": json.dumps(self.agent_state),
            "artifacts": json.dumps(self.artifacts),
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "sequence_number": self.sequence_number,
            "checksum": self.checksum,
            "is_valid": self.is_valid
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowSavepoint":
        """Create from dictionary"""
        return cls(
            savepoint_id=data["savepoint_id"],
            workflow_id=data["workflow_id"],
            phase=WorkflowPhase(data["phase"]),
            agent_id=data["agent_id"],
            savepoint_type=SavepointType(data["savepoint_type"]),
            workflow_state=json.loads(data.get("workflow_state", "{}")),
            agent_state=json.loads(data.get("agent_state", "{}")),
            artifacts=json.loads(data.get("artifacts", "[]")),
            created_at=datetime.fromisoformat(data["created_at"]),
            description=data.get("description", ""),
            sequence_number=data.get("sequence_number", 0),
            checksum=data.get("checksum"),
            is_valid=data.get("is_valid", True)
        )


@dataclass
class WorkflowContext:
    """Current workflow execution context"""
    workflow_id: str
    job_id: int
    current_phase: WorkflowPhase
    current_agent: str

    # State
    state: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    # History
    savepoints: List[str] = field(default_factory=list)  # List of savepoint IDs
    rollback_count: int = 0

    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_savepoint_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "workflow_id": self.workflow_id,
            "job_id": self.job_id,
            "current_phase": self.current_phase.value,
            "current_agent": self.current_agent,
            "state": self.state,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "savepoints": self.savepoints,
            "rollback_count": self.rollback_count,
            "started_at": self.started_at.isoformat(),
            "last_savepoint_at": self.last_savepoint_at.isoformat() if self.last_savepoint_at else None
        }


# ==============================================================================
# Workflow State Manager
# ==============================================================================

class WorkflowStateManager:
    """
    Manages workflow state, savepoints, and rollback operations.

    Provides:
    - Savepoint creation and management
    - State serialization and persistence
    - Rollback to previous states
    - Workflow resumption
    - Automatic cleanup
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self._contexts: Dict[str, WorkflowContext] = {}
        self._sequence_counters: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    # ==========================================================================
    # Context Management
    # ==========================================================================

    def create_context(
        self,
        workflow_id: str,
        job_id: int,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> WorkflowContext:
        """
        Create a new workflow context.

        Note: This is a synchronous method that does not acquire self._lock.
        It must only be called from the event loop thread (not from executors
        or background threads) to avoid races with async savepoint/rollback methods.

        Args:
            workflow_id: Unique workflow identifier
            job_id: Associated job ID
            initial_state: Optional initial state

        Returns:
            New WorkflowContext
        """
        context = WorkflowContext(
            workflow_id=workflow_id,
            job_id=job_id,
            current_phase=WorkflowPhase.INITIALIZATION,
            current_agent="",
            state=initial_state or {}
        )

        self._contexts[workflow_id] = context
        self._sequence_counters[workflow_id] = 0

        logger.info("Workflow context created", workflow_id=workflow_id, job_id=job_id)

        return context

    def get_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """Get an existing workflow context.

        Note: Synchronous — must only be called from the event loop thread.
        """
        return self._contexts.get(workflow_id)

    def update_context(
        self,
        workflow_id: str,
        phase: Optional[WorkflowPhase] = None,
        agent: Optional[str] = None,
        state_updates: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[WorkflowContext]:
        """
        Update workflow context.

        Note: Synchronous — must only be called from the event loop thread.

        Args:
            workflow_id: Workflow to update
            phase: New phase
            agent: New current agent
            state_updates: State updates to merge
            artifacts: Artifacts to add

        Returns:
            Updated context or None if not found
        """
        context = self._contexts.get(workflow_id)
        if not context:
            return None

        if phase:
            context.current_phase = phase
        if agent:
            context.current_agent = agent
        if state_updates:
            context.state.update(state_updates)
        if artifacts:
            context.artifacts.extend(artifacts)

        return context

    # ==========================================================================
    # Savepoint Operations
    # ==========================================================================

    async def create_savepoint(
        self,
        workflow_id: str,
        savepoint_type: SavepointType = SavepointType.AUTOMATIC,
        description: str = "",
        agent_state: Optional[Dict[str, Any]] = None,
        set_agent_id: Optional[str] = None
    ) -> Optional[WorkflowSavepoint]:
        """
        Create a savepoint for the current workflow state.

        Args:
            workflow_id: Workflow to save
            savepoint_type: Type of savepoint
            description: Optional description
            agent_state: Optional agent-specific state
            set_agent_id: Optional agent ID to set atomically before snapshotting

        Returns:
            Created savepoint or None if workflow not found
        """
        async with self._lock:
            context = self._contexts.get(workflow_id)
            if not context:
                logger.warning("Cannot create savepoint: workflow not found", workflow_id=workflow_id)
                return None

            # Atomically set agent_id before snapshotting (avoids TOCTOU race)
            if set_agent_id is not None:
                context.current_agent = set_agent_id

            # Capture previous state for rollback on DB failure
            previous_sequence = self._sequence_counters.get(workflow_id, 0)
            previous_last_savepoint_at = context.last_savepoint_at

            # Increment sequence
            self._sequence_counters[workflow_id] = previous_sequence + 1
            sequence = self._sequence_counters[workflow_id]

            # Create savepoint from current state snapshot (include job_id for restore)
            state_snapshot = deepcopy(context.state)
            state_snapshot["_job_id"] = context.job_id

            savepoint = WorkflowSavepoint(
                savepoint_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                phase=context.current_phase,
                agent_id=context.current_agent,
                savepoint_type=savepoint_type,
                workflow_state=state_snapshot,
                agent_state=agent_state or {},
                artifacts=deepcopy(context.artifacts),
                description=description,
                sequence_number=sequence,
                checksum=self._calculate_checksum(context.state)
            )

            # Update in-memory context while holding lock
            context.savepoints.append(savepoint.savepoint_id)
            context.last_savepoint_at = datetime.utcnow()

        # Persist to database outside the lock to avoid blocking the event loop
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("workflow_savepoints").insert(
                    savepoint.to_dict()
                ).execute()
            )
        except Exception:
            logger.exception("Failed to store savepoint", workflow_id=workflow_id)
            # Rollback in-memory state on DB failure — only remove the savepoint ID;
            # leave sequence counter and timestamp untouched to stay monotonically increasing
            async with self._lock:
                if savepoint.savepoint_id in context.savepoints:
                    context.savepoints.remove(savepoint.savepoint_id)
            return None

        logger.info(
            "Savepoint created",
            workflow_id=workflow_id,
            savepoint_id=savepoint.savepoint_id,
            phase=context.current_phase.value,
            sequence=sequence
        )

        return savepoint

    async def create_pre_agent_savepoint(
        self,
        workflow_id: str,
        agent_id: str,
        agent_input: Dict[str, Any]
    ) -> Optional[WorkflowSavepoint]:
        """Create a savepoint before agent execution"""
        return await self.create_savepoint(
            workflow_id=workflow_id,
            savepoint_type=SavepointType.PRE_AGENT,
            description=f"Before executing {agent_id}",
            agent_state={"input": agent_input},
            set_agent_id=agent_id
        )

    async def create_post_agent_savepoint(
        self,
        workflow_id: str,
        agent_id: str,
        agent_output: Dict[str, Any]
    ) -> Optional[WorkflowSavepoint]:
        """Create a savepoint after successful agent execution"""
        return await self.create_savepoint(
            workflow_id=workflow_id,
            savepoint_type=SavepointType.POST_AGENT,
            description=f"After executing {agent_id}",
            agent_state={"output": agent_output}
        )

    # ==========================================================================
    # Rollback Operations
    # ==========================================================================

    async def rollback_to_savepoint(
        self,
        workflow_id: str,
        savepoint_id: str
    ) -> Optional[WorkflowContext]:
        """
        Rollback workflow to a previous savepoint.

        Args:
            workflow_id: Workflow to rollback
            savepoint_id: Target savepoint

        Returns:
            Restored context or None if failed
        """
        # Load savepoint from database (outside lock - read-only DB call)
        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").select("*").eq(
                "savepoint_id", savepoint_id
            ).eq("workflow_id", workflow_id).single().execute()
        )

        if not result.data:
            logger.error("Savepoint not found", savepoint_id=savepoint_id)
            return None

        savepoint = WorkflowSavepoint.from_dict(result.data)

        # Validate checksum
        if not self._validate_savepoint(savepoint):
            logger.error("Savepoint validation failed", savepoint_id=savepoint_id)
            return None

        # Create recovery savepoint before rollback (acquires lock internally)
        await self.create_savepoint(
            workflow_id=workflow_id,
            savepoint_type=SavepointType.RECOVERY,
            description=f"Pre-rollback state (rolling back to {savepoint_id})"
        )

        # Single lock region for all in-memory state mutations
        async with self._lock:
            # Get or create context
            restored_job_id = savepoint.workflow_state.get("_job_id", 0)
            context = self._contexts.get(workflow_id)
            if not context:
                context = WorkflowContext(
                    workflow_id=workflow_id,
                    job_id=restored_job_id,
                    current_phase=savepoint.phase,
                    current_agent=savepoint.agent_id
                )
                self._contexts[workflow_id] = context

            # Restore state (strip internal _job_id key before restoring)
            restored_state = deepcopy(savepoint.workflow_state)
            restored_state.pop("_job_id", None)

            context.current_phase = savepoint.phase
            context.current_agent = savepoint.agent_id
            context.job_id = restored_job_id
            context.state = restored_state
            context.artifacts = deepcopy(savepoint.artifacts)
            context.rollback_count += 1

            # Reset sequence counter
            self._sequence_counters[workflow_id] = savepoint.sequence_number

        # Invalidate savepoints in DB outside the lock
        await self._invalidate_savepoints_after(workflow_id, savepoint.sequence_number)

        logger.info(
            "Workflow rolled back",
            workflow_id=workflow_id,
            savepoint_id=savepoint_id,
            phase=savepoint.phase.value,
            rollback_count=context.rollback_count
        )

        return context

    async def rollback_to_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase
    ) -> Optional[WorkflowContext]:
        """
        Rollback to the last savepoint of a specific phase.

        Args:
            workflow_id: Workflow to rollback
            phase: Target phase

        Returns:
            Restored context or None if no savepoint found
        """
        # Find the last savepoint for the phase
        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").select("*").eq(
                "workflow_id", workflow_id
            ).eq("phase", phase.value).eq("is_valid", True).order(
                "sequence_number", desc=True
            ).limit(1).execute()
        )

        if not result.data:
            logger.warning(
                "No savepoint found for phase",
                workflow_id=workflow_id,
                phase=phase.value
            )
            return None

        savepoint_id = result.data[0]["savepoint_id"]
        return await self.rollback_to_savepoint(workflow_id, savepoint_id)

    async def rollback_to_last_agent(
        self,
        workflow_id: str,
        agent_id: str
    ) -> Optional[WorkflowContext]:
        """
        Rollback to the last savepoint before a specific agent.

        Args:
            workflow_id: Workflow to rollback
            agent_id: Target agent

        Returns:
            Restored context
        """
        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").select("*").eq(
                "workflow_id", workflow_id
            ).eq("agent_id", agent_id).eq(
                "savepoint_type", SavepointType.PRE_AGENT.value
            ).eq("is_valid", True).order(
                "sequence_number", desc=True
            ).limit(1).execute()
        )

        if not result.data:
            return None

        return await self.rollback_to_savepoint(
            workflow_id,
            result.data[0]["savepoint_id"]
        )

    async def _invalidate_savepoints_after(
        self,
        workflow_id: str,
        sequence_number: int
    ) -> None:
        """Mark savepoints after a sequence number as invalid"""
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("workflow_savepoints").update({
                    "is_valid": False
                }).eq("workflow_id", workflow_id).gt(
                    "sequence_number", sequence_number
                ).execute()
            )
        except Exception:
            logger.exception("Failed to invalidate savepoints", workflow_id=workflow_id)

    # ==========================================================================
    # Query Operations
    # ==========================================================================

    async def list_savepoints(
        self,
        workflow_id: str,
        valid_only: bool = True
    ) -> List[WorkflowSavepoint]:
        """
        List all savepoints for a workflow.

        Args:
            workflow_id: Workflow to query
            valid_only: Only return valid savepoints

        Returns:
            List of savepoints
        """
        def _query():
            query = self.supabase.table("workflow_savepoints").select("*").eq(
                "workflow_id", workflow_id
            )
            if valid_only:
                query = query.eq("is_valid", True)
            return query.order("sequence_number").execute()

        result = await asyncio.to_thread(_query)

        return [WorkflowSavepoint.from_dict(row) for row in (result.data or [])]

    async def get_savepoint(self, savepoint_id: str) -> Optional[WorkflowSavepoint]:
        """Get a specific savepoint by ID"""
        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").select("*").eq(
                "savepoint_id", savepoint_id
            ).single().execute()
        )

        if result.data:
            return WorkflowSavepoint.from_dict(result.data)
        return None

    async def get_latest_savepoint(
        self,
        workflow_id: str
    ) -> Optional[WorkflowSavepoint]:
        """Get the most recent valid savepoint"""
        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").select("*").eq(
                "workflow_id", workflow_id
            ).eq("is_valid", True).order(
                "sequence_number", desc=True
            ).limit(1).execute()
        )

        if result.data:
            return WorkflowSavepoint.from_dict(result.data[0])
        return None

    # ==========================================================================
    # Cleanup Operations
    # ==========================================================================

    async def cleanup_old_savepoints(
        self,
        workflow_id: str,
        keep_count: int = 10
    ) -> int:
        """
        Remove old savepoints, keeping the most recent ones.

        Args:
            workflow_id: Workflow to clean up
            keep_count: Number of recent savepoints to keep

        Returns:
            Number of savepoints removed
        """
        # Get savepoints to keep
        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").select(
                "savepoint_id"
            ).eq("workflow_id", workflow_id).order(
                "sequence_number", desc=True
            ).limit(keep_count).execute()
        )

        keep_ids = [row["savepoint_id"] for row in (result.data or [])]

        # Delete older ones
        if keep_ids:
            delete_result = await asyncio.to_thread(
                lambda: self.supabase.table("workflow_savepoints").delete().eq(
                    "workflow_id", workflow_id
                ).not_.in_("savepoint_id", keep_ids).execute()
            )

            deleted = len(delete_result.data or [])

            if deleted > 0:
                logger.info(
                    "Cleaned up old savepoints",
                    workflow_id=workflow_id,
                    deleted=deleted
                )

            return deleted

        return 0

    async def cleanup_expired_savepoints(
        self,
        max_age_hours: int = 24
    ) -> int:
        """
        Remove savepoints older than a specified age.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of savepoints removed
        """
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()

        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").delete().lt(
                "created_at", cutoff
            ).execute()
        )

        deleted = len(result.data or [])

        if deleted > 0:
            logger.info(
                "Cleaned up expired savepoints",
                max_age_hours=max_age_hours,
                deleted=deleted
            )

        return deleted

    async def delete_workflow_savepoints(self, workflow_id: str) -> int:
        """Delete all savepoints for a workflow"""
        result = await asyncio.to_thread(
            lambda: self.supabase.table("workflow_savepoints").delete().eq(
                "workflow_id", workflow_id
            ).execute()
        )

        deleted = len(result.data or [])
        logger.info("Deleted workflow savepoints", workflow_id=workflow_id, count=deleted)

        # Clean up in-memory state to stay consistent with DB
        async with self._lock:
            context = self._contexts.get(workflow_id)
            if context:
                context.savepoints.clear()
            self._sequence_counters.pop(workflow_id, None)

        return deleted

    # ==========================================================================
    # Validation
    # ==========================================================================

    def _calculate_checksum(self, state: Dict[str, Any]) -> str:
        """Calculate checksum for state validation"""
        import hashlib
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

    def _validate_savepoint(self, savepoint: WorkflowSavepoint) -> bool:
        """Validate savepoint integrity"""
        if not savepoint.is_valid:
            return False

        if savepoint.checksum:
            calculated = self._calculate_checksum(savepoint.workflow_state)
            if calculated != savepoint.checksum:
                logger.warning(
                    "Savepoint checksum mismatch",
                    savepoint_id=savepoint.savepoint_id
                )
                return False

        return True


# ==============================================================================
# Service Factory
# ==============================================================================

_state_manager: Optional[WorkflowStateManager] = None


def get_workflow_state_manager() -> WorkflowStateManager:
    """Get or create the workflow state manager singleton"""
    global _state_manager
    if _state_manager is None:
        supabase = get_supabase_client()
        _state_manager = WorkflowStateManager(supabase)
    return _state_manager
