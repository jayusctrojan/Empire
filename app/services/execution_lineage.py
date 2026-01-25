"""
Execution Lineage and Provenance Tracking Service

Provides comprehensive tracking of workflow execution history, data lineage,
and provenance for audit, debugging, and reproducibility purposes.

Features:
- Full execution tree tracking with parent-child relationships
- Input/output artifact versioning and checksums
- Execution metadata (timing, resources, errors)
- Lineage queries (ancestors, descendants, impact analysis)
- Export for audit and compliance
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


class ExecutionStatus(str, Enum):
    """Status of an execution step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ArtifactType(str, Enum):
    """Type of artifact in the lineage."""
    DATA = "data"
    MODEL = "model"
    CONFIG = "config"
    DOCUMENT = "document"
    EMBEDDING = "embedding"
    REPORT = "report"
    INTERMEDIATE = "intermediate"


@dataclass
class Artifact:
    """Represents an input or output artifact."""
    id: UUID
    name: str
    artifact_type: ArtifactType
    checksum: str
    size_bytes: int
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_data(
        cls,
        name: str,
        data: Any,
        artifact_type: ArtifactType = ArtifactType.DATA,
        location: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "Artifact":
        """Create an artifact from data."""
        serialized = json.dumps(data, default=str, sort_keys=True)
        checksum = hashlib.sha256(serialized.encode()).hexdigest()

        return cls(
            id=uuid4(),
            name=name,
            artifact_type=artifact_type,
            checksum=checksum,
            size_bytes=len(serialized.encode()),
            location=location,
            metadata=metadata or {}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "artifact_type": self.artifact_type.value,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "location": self.location,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Artifact":
        """Create from dictionary."""
        return cls(
            id=UUID(data["id"]),
            name=data["name"],
            artifact_type=ArtifactType(data["artifact_type"]),
            checksum=data["checksum"],
            size_bytes=data["size_bytes"],
            location=data.get("location"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"])
        )


@dataclass
class ExecutionStep:
    """Represents a single step in the execution lineage."""
    id: UUID
    workflow_id: UUID
    agent_id: str
    step_name: str
    parent_step_id: Optional[UUID] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    input_artifacts: List[Artifact] = field(default_factory=list)
    output_artifacts: List[Artifact] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "agent_id": self.agent_id,
            "step_name": self.step_name,
            "parent_step_id": str(self.parent_step_id) if self.parent_step_id else None,
            "status": self.status.value,
            "input_artifacts": [a.to_dict() for a in self.input_artifacts],
            "output_artifacts": [a.to_dict() for a in self.output_artifacts],
            "parameters": self.parameters,
            "metrics": self.metrics,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "duration_seconds": self.duration_seconds
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionStep":
        """Create from dictionary."""
        return cls(
            id=UUID(data["id"]),
            workflow_id=UUID(data["workflow_id"]),
            agent_id=data["agent_id"],
            step_name=data["step_name"],
            parent_step_id=UUID(data["parent_step_id"]) if data.get("parent_step_id") else None,
            status=ExecutionStatus(data["status"]),
            input_artifacts=[Artifact.from_dict(a) for a in data.get("input_artifacts", [])],
            output_artifacts=[Artifact.from_dict(a) for a in data.get("output_artifacts", [])],
            parameters=data.get("parameters", {}),
            metrics=data.get("metrics", {}),
            error_message=data.get("error_message"),
            error_traceback=data.get("error_traceback"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            created_at=datetime.fromisoformat(data["created_at"])
        )


@dataclass
class WorkflowLineage:
    """Complete lineage for a workflow execution."""
    workflow_id: UUID
    name: str
    steps: Dict[UUID, ExecutionStep] = field(default_factory=dict)
    root_step_ids: List[UUID] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def add_step(self, step: ExecutionStep) -> None:
        """Add a step to the lineage."""
        self.steps[step.id] = step
        if step.parent_step_id is None:
            self.root_step_ids.append(step.id)

    def get_children(self, step_id: UUID) -> List[ExecutionStep]:
        """Get child steps of a given step."""
        return [
            step for step in self.steps.values()
            if step.parent_step_id == step_id
        ]

    def get_ancestors(self, step_id: UUID) -> List[ExecutionStep]:
        """Get all ancestor steps of a given step."""
        ancestors = []
        current = self.steps.get(step_id)

        while current and current.parent_step_id:
            parent = self.steps.get(current.parent_step_id)
            if parent:
                ancestors.append(parent)
                current = parent
            else:
                break

        return ancestors

    def get_descendants(self, step_id: UUID) -> List[ExecutionStep]:
        """Get all descendant steps of a given step."""
        descendants = []
        to_visit = [step_id]

        while to_visit:
            current_id = to_visit.pop(0)
            children = self.get_children(current_id)
            descendants.extend(children)
            to_visit.extend([c.id for c in children])

        return descendants

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workflow_id": str(self.workflow_id),
            "name": self.name,
            "steps": {str(k): v.to_dict() for k, v in self.steps.items()},
            "root_step_ids": [str(sid) for sid in self.root_step_ids],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class LineageStore:
    """Abstract base for lineage storage backends."""

    async def save_step(self, step: ExecutionStep) -> None:
        """Save an execution step."""
        raise NotImplementedError

    async def get_step(self, step_id: UUID) -> Optional[ExecutionStep]:
        """Get a step by ID."""
        raise NotImplementedError

    async def get_workflow_steps(self, workflow_id: UUID) -> List[ExecutionStep]:
        """Get all steps for a workflow."""
        raise NotImplementedError

    async def save_artifact(self, artifact: Artifact) -> None:
        """Save an artifact."""
        raise NotImplementedError

    async def get_artifact(self, artifact_id: UUID) -> Optional[Artifact]:
        """Get an artifact by ID."""
        raise NotImplementedError

    async def find_artifacts_by_checksum(self, checksum: str) -> List[Artifact]:
        """Find artifacts with matching checksum."""
        raise NotImplementedError


class InMemoryLineageStore(LineageStore):
    """In-memory lineage storage for development/testing."""

    def __init__(self):
        self._steps: Dict[UUID, ExecutionStep] = {}
        self._artifacts: Dict[UUID, Artifact] = {}
        self._workflow_steps: Dict[UUID, Set[UUID]] = {}
        self._checksum_index: Dict[str, Set[UUID]] = {}

    async def save_step(self, step: ExecutionStep) -> None:
        """Save an execution step."""
        self._steps[step.id] = step

        if step.workflow_id not in self._workflow_steps:
            self._workflow_steps[step.workflow_id] = set()
        self._workflow_steps[step.workflow_id].add(step.id)

        # Index artifacts
        for artifact in step.input_artifacts + step.output_artifacts:
            await self.save_artifact(artifact)

    async def get_step(self, step_id: UUID) -> Optional[ExecutionStep]:
        """Get a step by ID."""
        return self._steps.get(step_id)

    async def get_workflow_steps(self, workflow_id: UUID) -> List[ExecutionStep]:
        """Get all steps for a workflow."""
        step_ids = self._workflow_steps.get(workflow_id, set())
        return [self._steps[sid] for sid in step_ids if sid in self._steps]

    async def save_artifact(self, artifact: Artifact) -> None:
        """Save an artifact."""
        self._artifacts[artifact.id] = artifact

        if artifact.checksum not in self._checksum_index:
            self._checksum_index[artifact.checksum] = set()
        self._checksum_index[artifact.checksum].add(artifact.id)

    async def get_artifact(self, artifact_id: UUID) -> Optional[Artifact]:
        """Get an artifact by ID."""
        return self._artifacts.get(artifact_id)

    async def find_artifacts_by_checksum(self, checksum: str) -> List[Artifact]:
        """Find artifacts with matching checksum."""
        artifact_ids = self._checksum_index.get(checksum, set())
        return [self._artifacts[aid] for aid in artifact_ids if aid in self._artifacts]


class DatabaseLineageStore(LineageStore):
    """Database-backed lineage storage using Supabase."""

    def __init__(self, supabase_client):
        self._client = supabase_client

    async def save_step(self, step: ExecutionStep) -> None:
        """Save an execution step to database."""
        data = {
            "id": str(step.id),
            "workflow_id": str(step.workflow_id),
            "agent_id": step.agent_id,
            "step_name": step.step_name,
            "parent_step_id": str(step.parent_step_id) if step.parent_step_id else None,
            "status": step.status.value,
            "input_artifacts": [a.to_dict() for a in step.input_artifacts],
            "output_artifacts": [a.to_dict() for a in step.output_artifacts],
            "parameters": step.parameters,
            "metrics": step.metrics,
            "error_message": step.error_message,
            "error_traceback": step.error_traceback,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "completed_at": step.completed_at.isoformat() if step.completed_at else None
        }

        await asyncio.to_thread(
            lambda: self._client.table("execution_lineage").upsert(data).execute()
        )

        logger.debug("saved_execution_step", step_id=str(step.id), workflow_id=str(step.workflow_id))

    async def get_step(self, step_id: UUID) -> Optional[ExecutionStep]:
        """Get a step by ID from database."""
        result = await asyncio.to_thread(
            lambda: self._client.table("execution_lineage")
                .select("*")
                .eq("id", str(step_id))
                .single()
                .execute()
        )

        if result.data:
            return self._row_to_step(result.data)
        return None

    async def get_workflow_steps(self, workflow_id: UUID) -> List[ExecutionStep]:
        """Get all steps for a workflow from database."""
        result = await asyncio.to_thread(
            lambda: self._client.table("execution_lineage")
                .select("*")
                .eq("workflow_id", str(workflow_id))
                .order("created_at")
                .execute()
        )

        return [self._row_to_step(row) for row in result.data]

    async def save_artifact(self, artifact: Artifact) -> None:
        """Save artifact metadata to database."""
        data = {
            "id": str(artifact.id),
            "name": artifact.name,
            "artifact_type": artifact.artifact_type.value,
            "checksum": artifact.checksum,
            "size_bytes": artifact.size_bytes,
            "location": artifact.location,
            "metadata": artifact.metadata
        }

        await asyncio.to_thread(
            lambda: self._client.table("lineage_artifacts").upsert(data).execute()
        )

    async def get_artifact(self, artifact_id: UUID) -> Optional[Artifact]:
        """Get an artifact by ID from database."""
        result = await asyncio.to_thread(
            lambda: self._client.table("lineage_artifacts")
                .select("*")
                .eq("id", str(artifact_id))
                .single()
                .execute()
        )

        if result.data:
            return Artifact.from_dict(result.data)
        return None

    async def find_artifacts_by_checksum(self, checksum: str) -> List[Artifact]:
        """Find artifacts with matching checksum."""
        result = await asyncio.to_thread(
            lambda: self._client.table("lineage_artifacts")
                .select("*")
                .eq("checksum", checksum)
                .execute()
        )

        return [Artifact.from_dict(row) for row in result.data]

    def _row_to_step(self, row: Dict[str, Any]) -> ExecutionStep:
        """Convert database row to ExecutionStep."""
        return ExecutionStep(
            id=UUID(row["id"]),
            workflow_id=UUID(row["workflow_id"]),
            agent_id=row["agent_id"],
            step_name=row["step_name"],
            parent_step_id=UUID(row["parent_step_id"]) if row.get("parent_step_id") else None,
            status=ExecutionStatus(row["status"]),
            input_artifacts=[Artifact.from_dict(a) for a in row.get("input_artifacts", [])],
            output_artifacts=[Artifact.from_dict(a) for a in row.get("output_artifacts", [])],
            parameters=row.get("parameters", {}),
            metrics=row.get("metrics", {}),
            error_message=row.get("error_message"),
            error_traceback=row.get("error_traceback"),
            started_at=datetime.fromisoformat(row["started_at"]) if row.get("started_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow()
        )


class ExecutionLineageTracker:
    """
    Main service for tracking execution lineage and provenance.

    Provides methods for recording execution steps, managing artifacts,
    querying lineage, and exporting for audit purposes.
    """

    def __init__(
        self,
        store: Optional[LineageStore] = None
    ):
        self._store = store or InMemoryLineageStore()
        self._active_workflows: Dict[UUID, WorkflowLineage] = {}
        self._lock = asyncio.Lock()

    async def start_workflow(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Start tracking a new workflow execution."""
        workflow_id = uuid4()

        lineage = WorkflowLineage(
            workflow_id=workflow_id,
            name=name,
            metadata=metadata or {}
        )

        async with self._lock:
            self._active_workflows[workflow_id] = lineage

        logger.info("workflow_started", workflow_id=str(workflow_id), name=name)

        return workflow_id

    async def complete_workflow(self, workflow_id: UUID) -> Optional[WorkflowLineage]:
        """Mark a workflow as completed and return its lineage."""
        async with self._lock:
            lineage = self._active_workflows.get(workflow_id)
            if lineage:
                lineage.completed_at = datetime.utcnow()
                del self._active_workflows[workflow_id]

        if lineage:
            logger.info(
                "workflow_completed",
                workflow_id=str(workflow_id),
                total_steps=len(lineage.steps)
            )

        return lineage

    async def start_step(
        self,
        workflow_id: UUID,
        agent_id: str,
        step_name: str,
        parent_step_id: Optional[UUID] = None,
        input_artifacts: Optional[List[Artifact]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Start tracking a new execution step."""
        step = ExecutionStep(
            id=uuid4(),
            workflow_id=workflow_id,
            agent_id=agent_id,
            step_name=step_name,
            parent_step_id=parent_step_id,
            status=ExecutionStatus.RUNNING,
            input_artifacts=input_artifacts or [],
            parameters=parameters or {},
            started_at=datetime.utcnow()
        )

        await self._store.save_step(step)

        async with self._lock:
            lineage = self._active_workflows.get(workflow_id)
            if lineage:
                lineage.add_step(step)

        logger.debug(
            "step_started",
            step_id=str(step.id),
            workflow_id=str(workflow_id),
            agent_id=agent_id,
            step_name=step_name
        )

        return step.id

    async def complete_step(
        self,
        step_id: UUID,
        output_artifacts: Optional[List[Artifact]] = None,
        metrics: Optional[Dict[str, float]] = None
    ) -> None:
        """Mark a step as completed with outputs."""
        step = await self._store.get_step(step_id)
        if not step:
            logger.warning("step_not_found", step_id=str(step_id))
            return

        step.status = ExecutionStatus.COMPLETED
        step.completed_at = datetime.utcnow()
        step.output_artifacts = output_artifacts or []
        step.metrics = metrics or {}

        await self._store.save_step(step)

        # Update active workflow
        async with self._lock:
            lineage = self._active_workflows.get(step.workflow_id)
            if lineage:
                lineage.steps[step_id] = step

        logger.debug(
            "step_completed",
            step_id=str(step_id),
            duration_seconds=step.duration_seconds,
            output_count=len(step.output_artifacts)
        )

    async def fail_step(
        self,
        step_id: UUID,
        error_message: str,
        error_traceback: Optional[str] = None
    ) -> None:
        """Mark a step as failed with error information."""
        step = await self._store.get_step(step_id)
        if not step:
            logger.warning("step_not_found", step_id=str(step_id))
            return

        step.status = ExecutionStatus.FAILED
        step.completed_at = datetime.utcnow()
        step.error_message = error_message
        step.error_traceback = error_traceback

        await self._store.save_step(step)

        async with self._lock:
            lineage = self._active_workflows.get(step.workflow_id)
            if lineage:
                lineage.steps[step_id] = step

        logger.warning(
            "step_failed",
            step_id=str(step_id),
            error_message=error_message
        )

    async def skip_step(self, step_id: UUID, reason: str) -> None:
        """Mark a step as skipped."""
        step = await self._store.get_step(step_id)
        if not step:
            return

        step.status = ExecutionStatus.SKIPPED
        step.completed_at = datetime.utcnow()
        step.metrics["skip_reason"] = reason

        await self._store.save_step(step)

        logger.debug("step_skipped", step_id=str(step_id), reason=reason)

    async def add_artifact_to_step(
        self,
        step_id: UUID,
        artifact: Artifact,
        is_input: bool = False
    ) -> None:
        """Add an artifact to a step."""
        step = await self._store.get_step(step_id)
        if not step:
            return

        if is_input:
            step.input_artifacts.append(artifact)
        else:
            step.output_artifacts.append(artifact)

        await self._store.save_step(step)
        await self._store.save_artifact(artifact)

    async def get_step_lineage(self, step_id: UUID) -> Dict[str, Any]:
        """Get complete lineage for a step (ancestors and descendants)."""
        step = await self._store.get_step(step_id)
        if not step:
            return {}

        # Get all workflow steps
        workflow_steps = await self._store.get_workflow_steps(step.workflow_id)
        steps_by_id = {s.id: s for s in workflow_steps}

        # Build lineage
        ancestors = []
        current = step
        while current.parent_step_id:
            parent = steps_by_id.get(current.parent_step_id)
            if parent:
                ancestors.append(parent.to_dict())
                current = parent
            else:
                break

        # Get descendants
        descendants = []
        to_visit = [step_id]
        while to_visit:
            current_id = to_visit.pop(0)
            children = [s for s in workflow_steps if s.parent_step_id == current_id]
            for child in children:
                descendants.append(child.to_dict())
                to_visit.append(child.id)

        return {
            "step": step.to_dict(),
            "ancestors": ancestors,
            "descendants": descendants
        }

    async def get_artifact_usage(self, artifact_id: UUID) -> Dict[str, Any]:
        """Get all steps that used or produced an artifact."""
        artifact = await self._store.get_artifact(artifact_id)
        if not artifact:
            return {}

        # Find steps by checksum (artifact might be used in multiple places)
        matching_artifacts = await self._store.find_artifacts_by_checksum(artifact.checksum)

        produced_by = []
        consumed_by = []

        # This would need additional indexing in a real implementation
        # For now, return basic info
        return {
            "artifact": artifact.to_dict(),
            "matching_checksums": len(matching_artifacts),
            "produced_by": produced_by,
            "consumed_by": consumed_by
        }

    async def get_workflow_summary(self, workflow_id: UUID) -> Dict[str, Any]:
        """Get summary statistics for a workflow."""
        steps = await self._store.get_workflow_steps(workflow_id)

        if not steps:
            return {}

        status_counts = {}
        total_duration = 0.0
        agent_counts = {}
        error_count = 0

        for step in steps:
            # Status counts
            status_counts[step.status.value] = status_counts.get(step.status.value, 0) + 1

            # Duration
            if step.duration_seconds:
                total_duration += step.duration_seconds

            # Agent counts
            agent_counts[step.agent_id] = agent_counts.get(step.agent_id, 0) + 1

            # Errors
            if step.status == ExecutionStatus.FAILED:
                error_count += 1

        return {
            "workflow_id": str(workflow_id),
            "total_steps": len(steps),
            "status_counts": status_counts,
            "total_duration_seconds": total_duration,
            "agent_counts": agent_counts,
            "error_count": error_count,
            "success_rate": (len(steps) - error_count) / len(steps) if steps else 0
        }

    async def export_lineage(
        self,
        workflow_id: UUID,
        format: str = "json"
    ) -> str:
        """Export workflow lineage for audit purposes."""
        steps = await self._store.get_workflow_steps(workflow_id)

        lineage_data = {
            "workflow_id": str(workflow_id),
            "exported_at": datetime.utcnow().isoformat(),
            "steps": [step.to_dict() for step in steps],
            "summary": await self.get_workflow_summary(workflow_id)
        }

        if format == "json":
            return json.dumps(lineage_data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def find_impacted_artifacts(
        self,
        artifact_id: UUID
    ) -> List[Artifact]:
        """Find all artifacts that were derived from a given artifact."""
        # This would trace through the lineage to find downstream artifacts
        # Implementation depends on how artifacts are linked through steps
        artifact = await self._store.get_artifact(artifact_id)
        if not artifact:
            return []

        # For a full implementation, this would trace through execution steps
        # to find all artifacts that used this one as input
        return []

    async def get_reproducibility_info(
        self,
        step_id: UUID
    ) -> Dict[str, Any]:
        """Get information needed to reproduce a step's execution."""
        step = await self._store.get_step(step_id)
        if not step:
            return {}

        return {
            "step_id": str(step.id),
            "agent_id": step.agent_id,
            "step_name": step.step_name,
            "parameters": step.parameters,
            "input_artifacts": [
                {
                    "name": a.name,
                    "checksum": a.checksum,
                    "location": a.location
                }
                for a in step.input_artifacts
            ],
            "executed_at": step.started_at.isoformat() if step.started_at else None
        }


# Global instance
_lineage_tracker: Optional[ExecutionLineageTracker] = None


async def get_lineage_tracker() -> ExecutionLineageTracker:
    """Get the global lineage tracker instance."""
    global _lineage_tracker

    if _lineage_tracker is None:
        _lineage_tracker = ExecutionLineageTracker()

    return _lineage_tracker


async def init_lineage_tracker(store: Optional[LineageStore] = None) -> ExecutionLineageTracker:
    """Initialize the global lineage tracker with a specific store."""
    global _lineage_tracker

    _lineage_tracker = ExecutionLineageTracker(store=store)

    logger.info("lineage_tracker_initialized")

    return _lineage_tracker
