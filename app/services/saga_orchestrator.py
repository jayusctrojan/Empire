"""
Empire v7.3 - Saga Orchestrator
Data Persistence P0 Fix - Multi-step operations with automatic rollback

The Saga pattern ensures data consistency across distributed operations by:
1. Executing steps in sequence
2. Recording completed steps
3. Compensating (rolling back) on failure in reverse order

Usage:
    saga = Saga("graph_sync", document_id)
    saga.add_step(
        name="create_doc_node",
        action=neo4j.create_document_node,
        compensation=neo4j.delete_document_node
    )
    saga.add_step(
        name="create_entities",
        action=neo4j.create_entity_nodes,
        compensation=neo4j.delete_entity_nodes
    )
    await saga.execute(document=doc)  # Automatic rollback on failure
"""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

SAGA_EXECUTIONS_TOTAL = Counter(
    "empire_saga_executions_total",
    "Total saga executions",
    ["saga_name", "result"]
)

SAGA_STEP_EXECUTIONS = Counter(
    "empire_saga_step_executions_total",
    "Total saga step executions",
    ["saga_name", "step_name", "result"]
)

SAGA_COMPENSATIONS_TOTAL = Counter(
    "empire_saga_compensations_total",
    "Total saga compensations triggered",
    ["saga_name"]
)

SAGA_DURATION = Histogram(
    "empire_saga_duration_seconds",
    "Duration of saga executions",
    ["saga_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)


# =============================================================================
# MODELS
# =============================================================================

class SagaStepStatus(str, Enum):
    """Status of a saga step"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class SagaStatus(str, Enum):
    """Status of the entire saga"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    PARTIALLY_COMPENSATED = "partially_compensated"


class SagaStep(BaseModel):
    """A step in a saga with action and compensation"""
    name: str = Field(..., description="Step identifier")
    status: SagaStepStatus = Field(default=SagaStepStatus.PENDING)
    result: Optional[Any] = Field(None, description="Result from action")
    error: Optional[str] = Field(None, description="Error if failed")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    compensation_error: Optional[str] = None

    # These are set externally (not serialized)
    _action: Optional[Callable] = None
    _compensation: Optional[Callable] = None

    class Config:
        arbitrary_types_allowed = True


class SagaRecord(BaseModel):
    """Persistent record of a saga execution"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Saga name")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing")
    status: SagaStatus = Field(default=SagaStatus.PENDING)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    compensation_errors: List[str] = Field(default_factory=list)


# =============================================================================
# SAGA IMPLEMENTATION
# =============================================================================

class Saga:
    """
    Saga pattern implementation for distributed transactions.

    A Saga is a sequence of steps where each step has:
    - An action (the operation to perform)
    - A compensation (the rollback if later steps fail)

    On failure, compensations run in reverse order to maintain consistency.

    Example:
        saga = Saga("create_order")
        saga.add_step("reserve_inventory", reserve, unreserve)
        saga.add_step("charge_payment", charge, refund)
        saga.add_step("ship_order", ship, cancel_shipment)
        result = await saga.execute(order=order_data)
    """

    def __init__(
        self,
        name: str,
        correlation_id: Optional[str] = None,
        supabase_client=None
    ):
        """
        Initialize a saga.

        Args:
            name: Saga identifier (e.g., "graph_sync", "create_order")
            correlation_id: Optional correlation ID for tracing
            supabase_client: Optional Supabase client for persistence
        """
        self.id = str(uuid4())
        self.name = name
        self.correlation_id = correlation_id
        self.supabase = supabase_client

        self.steps: List[SagaStep] = []
        self.completed_steps: List[SagaStep] = []
        self.status = SagaStatus.PENDING
        self.context: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.compensation_errors: List[str] = []

        self._actions: Dict[str, Callable] = {}
        self._compensations: Dict[str, Callable] = {}

        logger.debug(
            "Saga created",
            saga_id=self.id,
            name=name,
            correlation_id=correlation_id
        )

    def add_step(
        self,
        name: str,
        action: Callable[..., Coroutine[Any, Any, Any]],
        compensation: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None
    ) -> "Saga":
        """
        Add a step to the saga.

        Args:
            name: Step identifier
            action: Async function to execute for this step
            compensation: Async function to undo this step (optional)

        Returns:
            Self for chaining
        """
        step = SagaStep(name=name)
        self.steps.append(step)
        self._actions[name] = action
        if compensation:
            self._compensations[name] = compensation

        logger.debug(
            "Saga step added",
            saga_id=self.id,
            step_name=name,
            has_compensation=compensation is not None
        )

        return self

    async def _persist_state(self):
        """Persist current saga state to database"""
        if not self.supabase:
            return

        try:
            record = SagaRecord(
                id=self.id,
                name=self.name,
                correlation_id=self.correlation_id,
                status=self.status,
                steps=[
                    {
                        "name": s.name,
                        "status": s.status.value,
                        "error": s.error,
                        "started_at": s.started_at.isoformat() if s.started_at else None,
                        "completed_at": s.completed_at.isoformat() if s.completed_at else None
                    }
                    for s in self.steps
                ],
                context=self.context,
                updated_at=datetime.utcnow(),
                error=self.error,
                compensation_errors=self.compensation_errors
            )

            self.supabase.table("saga_executions").upsert(
                record.model_dump()
            ).execute()

        except Exception as e:
            logger.warning("Failed to persist saga state", saga_id=self.id, error=str(e))

    async def _execute_step(
        self,
        step: SagaStep,
        **context
    ) -> Any:
        """Execute a single saga step"""
        action = self._actions.get(step.name)
        if not action:
            raise ValueError(f"No action registered for step: {step.name}")

        step.status = SagaStepStatus.IN_PROGRESS
        step.started_at = datetime.utcnow()

        try:
            result = await action(**context)
            step.status = SagaStepStatus.COMPLETED
            step.completed_at = datetime.utcnow()
            step.result = result

            SAGA_STEP_EXECUTIONS.labels(
                saga_name=self.name,
                step_name=step.name,
                result="success"
            ).inc()

            logger.debug(
                "Saga step completed",
                saga_id=self.id,
                step_name=step.name
            )

            return result

        except Exception as e:
            step.status = SagaStepStatus.FAILED
            step.error = str(e)

            SAGA_STEP_EXECUTIONS.labels(
                saga_name=self.name,
                step_name=step.name,
                result="failure"
            ).inc()

            logger.error(
                "Saga step failed",
                saga_id=self.id,
                step_name=step.name,
                error=str(e)
            )

            raise

    async def _compensate(self, **context) -> bool:
        """
        Run compensations for completed steps in reverse order.

        Returns:
            True if all compensations succeeded, False otherwise
        """
        self.status = SagaStatus.COMPENSATING
        await self._persist_state()

        SAGA_COMPENSATIONS_TOTAL.labels(saga_name=self.name).inc()

        all_compensated = True

        # Compensate in reverse order
        for step in reversed(self.completed_steps):
            compensation = self._compensations.get(step.name)

            if not compensation:
                logger.debug(
                    "No compensation for step",
                    saga_id=self.id,
                    step_name=step.name
                )
                continue

            step.status = SagaStepStatus.COMPENSATING

            try:
                # Pass both context and step result to compensation
                await compensation(**context, step_result=step.result)
                step.status = SagaStepStatus.COMPENSATED

                logger.info(
                    "Saga step compensated",
                    saga_id=self.id,
                    step_name=step.name
                )

            except Exception as e:
                error_msg = f"Compensation failed for {step.name}: {str(e)}"
                step.compensation_error = str(e)
                self.compensation_errors.append(error_msg)
                all_compensated = False

                logger.error(
                    "Saga compensation failed",
                    saga_id=self.id,
                    step_name=step.name,
                    error=str(e)
                )

        return all_compensated

    async def execute(self, **context) -> Dict[str, Any]:
        """
        Execute the saga.

        Runs all steps in sequence. On failure, compensates completed steps
        in reverse order.

        Args:
            **context: Context data passed to all steps and compensations

        Returns:
            Dict with results from all steps

        Raises:
            SagaExecutionError: If saga fails and compensation was needed
        """
        start_time = time.time()
        self.context = context
        self.status = SagaStatus.IN_PROGRESS
        results: Dict[str, Any] = {}

        logger.info(
            "Saga execution started",
            saga_id=self.id,
            name=self.name,
            steps_count=len(self.steps)
        )

        await self._persist_state()

        try:
            # Execute steps in sequence
            for step in self.steps:
                # Merge previous results into context
                step_context = {**context, **results}
                result = await self._execute_step(step, **step_context)

                results[step.name] = result
                self.completed_steps.append(step)

            # All steps completed successfully
            self.status = SagaStatus.COMPLETED
            await self._persist_state()

            duration = time.time() - start_time
            SAGA_DURATION.labels(saga_name=self.name).observe(duration)
            SAGA_EXECUTIONS_TOTAL.labels(saga_name=self.name, result="success").inc()

            logger.info(
                "Saga completed successfully",
                saga_id=self.id,
                name=self.name,
                duration_seconds=round(duration, 2)
            )

            return results

        except Exception as e:
            self.error = str(e)

            # Run compensations
            all_compensated = await self._compensate(**context)

            if all_compensated:
                self.status = SagaStatus.COMPENSATED
            else:
                self.status = SagaStatus.PARTIALLY_COMPENSATED

            await self._persist_state()

            duration = time.time() - start_time
            SAGA_DURATION.labels(saga_name=self.name).observe(duration)
            SAGA_EXECUTIONS_TOTAL.labels(saga_name=self.name, result="failure").inc()

            logger.error(
                "Saga failed",
                saga_id=self.id,
                name=self.name,
                error=str(e),
                compensated=all_compensated,
                duration_seconds=round(duration, 2)
            )

            raise SagaExecutionError(
                saga_id=self.id,
                saga_name=self.name,
                error=str(e),
                compensated=all_compensated,
                compensation_errors=self.compensation_errors
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current saga status"""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "error": s.error
                }
                for s in self.steps
            ],
            "completed_steps": len(self.completed_steps),
            "total_steps": len(self.steps),
            "error": self.error,
            "compensation_errors": self.compensation_errors
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================

class SagaExecutionError(Exception):
    """Raised when a saga fails"""

    def __init__(
        self,
        saga_id: str,
        saga_name: str,
        error: str,
        compensated: bool,
        compensation_errors: List[str]
    ):
        self.saga_id = saga_id
        self.saga_name = saga_name
        self.error = error
        self.compensated = compensated
        self.compensation_errors = compensation_errors

        message = f"Saga '{saga_name}' failed: {error}"
        if not compensated:
            message += f" (compensation partially failed: {compensation_errors})"

        super().__init__(message)


# =============================================================================
# HELPER FUNCTIONS FOR COMMON SAGAS
# =============================================================================

def create_graph_sync_saga(
    document_id: str,
    neo4j_service,
    supabase_client=None
) -> Saga:
    """
    Create a saga for syncing documents to the knowledge graph.

    Steps:
    1. Create document node
    2. Extract and create entities
    3. Create relationships
    """
    saga = Saga(
        name="graph_sync",
        correlation_id=document_id,
        supabase_client=supabase_client
    )

    async def create_doc_node(document_id: str, **kwargs):
        return await neo4j_service.create_document_node(document_id)

    async def delete_doc_node(document_id: str, step_result=None, **kwargs):
        return await neo4j_service.delete_document_node(document_id)

    async def create_entities(document_id: str, **kwargs):
        return await neo4j_service.create_entity_nodes(document_id)

    async def delete_entities(document_id: str, step_result=None, **kwargs):
        return await neo4j_service.delete_entity_nodes(document_id)

    async def create_relationships(document_id: str, **kwargs):
        return await neo4j_service.create_relationships(document_id)

    async def delete_relationships(document_id: str, step_result=None, **kwargs):
        return await neo4j_service.delete_relationships(document_id)

    saga.add_step("create_doc_node", create_doc_node, delete_doc_node)
    saga.add_step("create_entities", create_entities, delete_entities)
    saga.add_step("create_relationships", create_relationships, delete_relationships)

    return saga


def create_document_processing_saga(
    document_id: str,
    services: Dict[str, Any],
    supabase_client=None
) -> Saga:
    """
    Create a saga for complete document processing.

    Steps:
    1. Parse document (LlamaIndex)
    2. Generate embeddings
    3. Store in vector database
    4. Sync to knowledge graph
    5. Update status
    """
    saga = Saga(
        name="document_processing",
        correlation_id=document_id,
        supabase_client=supabase_client
    )

    # Steps would be added based on services passed
    # This is a template for extension

    return saga
