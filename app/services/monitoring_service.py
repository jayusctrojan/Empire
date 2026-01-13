"""
Empire v7.3 - Monitoring Service
Centralized monitoring for document processing pipeline with Prometheus metrics and database logging
"""

import time
import logging
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from prometheus_client import Counter, Histogram, Gauge, Summary
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


# ============================================================================
# Processing Stages
# ============================================================================

class ProcessingStage(str, Enum):
    """Document processing pipeline stages"""
    UPLOAD = "upload"
    VALIDATION = "validation"
    PARSING = "parsing"
    METADATA_EXTRACTION = "metadata_extraction"
    EMBEDDING_GENERATION = "embedding_generation"
    STORAGE = "storage"
    GRAPH_SYNC = "graph_sync"
    CLASSIFICATION = "classification"
    CHUNKING = "chunking"
    INDEXING = "indexing"


# ============================================================================
# Prometheus Metrics
# ============================================================================

# Document processing metrics
DOCUMENT_PROCESSING_TOTAL = Counter(
    'empire_document_processing_total',
    'Total documents processed',
    ['stage', 'status', 'file_type']
)

DOCUMENT_PROCESSING_DURATION = Histogram(
    'empire_document_processing_duration_seconds',
    'Document processing duration by stage',
    ['stage', 'file_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

DOCUMENT_PROCESSING_ERRORS = Counter(
    'empire_document_processing_errors_total',
    'Total processing errors',
    ['stage', 'error_type']
)

# Resource usage metrics
PROCESSING_CPU_USAGE = Gauge(
    'empire_processing_cpu_usage_percent',
    'CPU usage during processing',
    ['stage']
)

PROCESSING_MEMORY_USAGE = Gauge(
    'empire_processing_memory_usage_bytes',
    'Memory usage during processing',
    ['stage']
)

# Cost metrics
PROCESSING_COST = Counter(
    'empire_processing_cost_dollars',
    'Cumulative processing cost',
    ['service', 'operation']
)

DOCUMENT_COST = Summary(
    'empire_document_cost_dollars',
    'Cost per document',
    ['operation']
)

# Embedding metrics
EMBEDDING_GENERATION_TOTAL = Counter(
    'empire_embedding_generation_total',
    'Total embeddings generated',
    ['provider', 'model', 'status']
)

EMBEDDING_GENERATION_DURATION = Histogram(
    'empire_embedding_generation_duration_seconds',
    'Embedding generation duration',
    ['provider', 'model'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)

EMBEDDING_TOKENS = Counter(
    'empire_embedding_tokens_total',
    'Total tokens processed for embeddings',
    ['provider', 'model']
)

# LLM API metrics
LLM_API_CALLS = Counter(
    'empire_llm_api_calls_total',
    'Total LLM API calls',
    ['provider', 'model', 'operation', 'status']
)

LLM_API_DURATION = Histogram(
    'empire_llm_api_duration_seconds',
    'LLM API call duration',
    ['provider', 'model', 'operation'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
)

LLM_API_TOKENS = Counter(
    'empire_llm_api_tokens_total',
    'Total LLM API tokens used',
    ['provider', 'model', 'token_type']  # token_type: input, output
)

# Storage metrics
STORAGE_OPERATIONS = Counter(
    'empire_storage_operations_total',
    'Total storage operations',
    ['operation', 'backend', 'status']  # operation: upload, download, delete
)

STORAGE_BYTES = Counter(
    'empire_storage_bytes_total',
    'Total bytes stored/retrieved',
    ['operation', 'backend']
)

# Graph sync metrics
GRAPH_SYNC_OPERATIONS = Counter(
    'empire_graph_sync_operations_total',
    'Total graph synchronization operations',
    ['operation', 'status']  # operation: create, update, delete, query
)

GRAPH_SYNC_DURATION = Histogram(
    'empire_graph_sync_duration_seconds',
    'Graph synchronization duration',
    ['operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Queue metrics
QUEUE_SIZE = Gauge(
    'empire_queue_size',
    'Number of items in queue',
    ['queue_name']
)

QUEUE_LATENCY = Histogram(
    'empire_queue_latency_seconds',
    'Time tasks spend in queue before processing',
    ['queue_name'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0]
)

# ============================================================================
# Content Prep Agent Metrics (Feature 007 / Task 130)
# ============================================================================

# Counters for content set operations
CONTENT_SETS_CREATED = Counter(
    'empire_content_sets_created_total',
    'Number of content sets created',
    ['detection_mode']  # auto, pattern, metadata, llm
)

CONTENT_SETS_PROCESSED = Counter(
    'empire_content_sets_processed_total',
    'Number of content sets processed',
    ['status']  # success, failed, incomplete
)

CONTENT_SETS_DELETED = Counter(
    'empire_content_sets_deleted_total',
    'Number of content sets deleted by retention policy',
    ['reason']  # retention_policy, manual, error
)

# Gauges for current state
CONTENT_SETS_PENDING = Gauge(
    'empire_content_sets_pending',
    'Number of pending content sets'
)

CONTENT_SETS_PROCESSING = Gauge(
    'empire_content_sets_processing',
    'Number of content sets currently processing'
)

CONTENT_SETS_COMPLETE = Gauge(
    'empire_content_sets_complete',
    'Number of completed content sets'
)

# Content set processing metrics
CONTENT_SET_FILES = Histogram(
    'empire_content_set_files_count',
    'Number of files per content set',
    buckets=[1, 5, 10, 20, 50, 100, 200, 500]
)

CONTENT_SET_PROCESSING_DURATION = Histogram(
    'empire_content_set_processing_duration_seconds',
    'Content set processing duration',
    ['content_type'],  # course, documentation, book, standalone
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600]
)

# Ordering confidence metrics
ORDERING_CONFIDENCE = Histogram(
    'empire_content_set_ordering_confidence',
    'Ordering confidence score for content sets',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

CLARIFICATION_REQUESTS = Counter(
    'empire_content_set_clarification_requests_total',
    'Number of clarification requests sent to users',
    ['clarification_type', 'outcome']  # ordering, content_type; answered, timeout, cancelled
)

# Retention cleanup metrics
RETENTION_CLEANUP_RUNS = Counter(
    'empire_content_set_cleanup_runs_total',
    'Number of retention cleanup task runs',
    ['status']  # success, error
)

RETENTION_CLEANUP_DELETED = Counter(
    'empire_content_set_cleanup_deleted_total',
    'Number of content sets deleted during cleanup'
)

RETENTION_CLEANUP_DURATION = Histogram(
    'empire_content_set_cleanup_duration_seconds',
    'Retention cleanup task duration',
    buckets=[1, 5, 10, 30, 60, 120, 300]
)


# ============================================================================
# Metrics Data Classes
# ============================================================================

@dataclass
class StageMetrics:
    """Metrics for a single processing stage"""
    stage: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[int] = None
    status: str = "in_progress"
    error: Optional[str] = None
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProcessingMetrics:
    """Complete metrics for document processing"""
    file_id: str
    filename: str
    file_type: str
    total_start_time: float
    total_end_time: Optional[float] = None
    total_duration: Optional[float] = None
    total_cost: float = 0.0
    stages: List[StageMetrics] = None
    resource_summary: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.stages is None:
            self.stages = []


# ============================================================================
# Cost Calculator
# ============================================================================

class CostCalculator:
    """Calculate costs for various operations"""

    # Cost per 1K tokens (in dollars)
    LLM_COSTS = {
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
        "claude-3-5-haiku-20241022": {"input": 0.001, "output": 0.005},
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    }

    # Cost per embedding (BGE-M3 is free via Ollama, but track for other providers)
    EMBEDDING_COSTS = {
        "openai-text-embedding-3-small": 0.00002,  # per 1K tokens
        "openai-text-embedding-3-large": 0.00013,  # per 1K tokens
        "bge-m3": 0.0,  # Free via Ollama
    }

    # Storage costs (B2 pricing)
    STORAGE_COST_PER_GB_MONTH = 0.005  # $0.005 per GB per month

    @staticmethod
    def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate LLM API cost"""
        costs = CostCalculator.LLM_COSTS.get(model, {"input": 0.0, "output": 0.0})
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        return input_cost + output_cost

    @staticmethod
    def calculate_embedding_cost(model: str, tokens: int) -> float:
        """Calculate embedding generation cost"""
        cost_per_1k = CostCalculator.EMBEDDING_COSTS.get(model, 0.0)
        return (tokens / 1000) * cost_per_1k

    @staticmethod
    def calculate_storage_cost(bytes_stored: int, days: int = 30) -> float:
        """Calculate storage cost (assumes 30-day billing)"""
        gb_stored = bytes_stored / (1024 ** 3)
        return gb_stored * CostCalculator.STORAGE_COST_PER_GB_MONTH * (days / 30)


# ============================================================================
# Monitoring Service
# ============================================================================

class MonitoringService:
    """Centralized monitoring service for Empire"""

    def __init__(self, supabase_storage=None):
        """
        Initialize monitoring service

        Args:
            supabase_storage: Optional Supabase storage for logging metrics
        """
        self.supabase_storage = supabase_storage
        self.active_tracking: Dict[str, ProcessingMetrics] = {}

    @asynccontextmanager
    async def track_processing(
        self,
        file_id: str,
        filename: str,
        file_type: str
    ):
        """
        Context manager to track overall document processing

        Usage:
            async with monitor.track_processing(file_id, filename, file_type) as metrics:
                # Processing code here
                async with monitor.track_stage(file_id, ProcessingStage.PARSING):
                    # Parsing code
                    pass
        """
        metrics = ProcessingMetrics(
            file_id=file_id,
            filename=filename,
            file_type=file_type,
            total_start_time=time.time()
        )
        self.active_tracking[file_id] = metrics

        try:
            yield metrics
        finally:
            metrics.total_end_time = time.time()
            metrics.total_duration = metrics.total_end_time - metrics.total_start_time

            # Calculate total cost
            metrics.total_cost = sum(
                stage.cost for stage in metrics.stages if stage.cost is not None
            )

            # Log to database if available
            if self.supabase_storage:
                await self._log_metrics_to_database(metrics)

            # Clean up
            del self.active_tracking[file_id]

    @asynccontextmanager
    async def track_stage(
        self,
        file_id: str,
        stage: ProcessingStage,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager to track a single processing stage

        Usage:
            async with monitor.track_stage(file_id, ProcessingStage.PARSING) as stage_metrics:
                # Parsing code
                result = await parse_document(file_id)
                stage_metrics.metadata = {"pages": result.num_pages}
        """
        stage_metrics = StageMetrics(
            stage=stage.value,
            start_time=time.time(),
            metadata=metadata or {}
        )

        # Get initial resource usage
        process = psutil.Process()
        cpu_start = process.cpu_percent(interval=0.1)
        memory_start = process.memory_info().rss

        try:
            yield stage_metrics
            stage_metrics.status = "success"

        except Exception as e:
            stage_metrics.status = "failure"
            stage_metrics.error = str(e)
            DOCUMENT_PROCESSING_ERRORS.labels(
                stage=stage.value,
                error_type=type(e).__name__
            ).inc()
            raise

        finally:
            # Calculate duration
            stage_metrics.end_time = time.time()
            stage_metrics.duration = stage_metrics.end_time - stage_metrics.start_time

            # Get final resource usage
            cpu_end = process.cpu_percent(interval=0.1)
            memory_end = process.memory_info().rss

            stage_metrics.cpu_usage = (cpu_start + cpu_end) / 2
            stage_metrics.memory_usage = memory_end - memory_start

            # Record Prometheus metrics
            if file_id in self.active_tracking:
                file_type = self.active_tracking[file_id].file_type

                DOCUMENT_PROCESSING_TOTAL.labels(
                    stage=stage.value,
                    status=stage_metrics.status,
                    file_type=file_type
                ).inc()

                DOCUMENT_PROCESSING_DURATION.labels(
                    stage=stage.value,
                    file_type=file_type
                ).observe(stage_metrics.duration)

                PROCESSING_CPU_USAGE.labels(stage=stage.value).set(stage_metrics.cpu_usage)
                PROCESSING_MEMORY_USAGE.labels(stage=stage.value).set(stage_metrics.memory_usage)

                # Add to tracking
                self.active_tracking[file_id].stages.append(stage_metrics)

    async def record_llm_call(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        duration: float,
        status: str = "success"
    ) -> float:
        """
        Record LLM API call metrics and return cost

        Args:
            provider: LLM provider (e.g., "anthropic", "openai")
            model: Model name
            operation: Operation type (e.g., "query_expansion", "classification")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            duration: API call duration in seconds
            status: Call status (success/failure)

        Returns:
            Cost of the API call in dollars
        """
        # Record metrics
        LLM_API_CALLS.labels(
            provider=provider,
            model=model,
            operation=operation,
            status=status
        ).inc()

        LLM_API_DURATION.labels(
            provider=provider,
            model=model,
            operation=operation
        ).observe(duration)

        LLM_API_TOKENS.labels(
            provider=provider,
            model=model,
            token_type="input"
        ).inc(input_tokens)

        LLM_API_TOKENS.labels(
            provider=provider,
            model=model,
            token_type="output"
        ).inc(output_tokens)

        # Calculate and record cost
        cost = CostCalculator.calculate_llm_cost(model, input_tokens, output_tokens)

        PROCESSING_COST.labels(
            service=provider,
            operation=operation
        ).inc(cost)

        DOCUMENT_COST.labels(operation=operation).observe(cost)

        return cost

    async def record_embedding_generation(
        self,
        provider: str,
        model: str,
        num_embeddings: int,
        tokens: int,
        duration: float,
        status: str = "success"
    ) -> float:
        """
        Record embedding generation metrics and return cost

        Returns:
            Cost of embedding generation in dollars
        """
        # Record metrics
        EMBEDDING_GENERATION_TOTAL.labels(
            provider=provider,
            model=model,
            status=status
        ).inc(num_embeddings)

        EMBEDDING_GENERATION_DURATION.labels(
            provider=provider,
            model=model
        ).observe(duration)

        EMBEDDING_TOKENS.labels(
            provider=provider,
            model=model
        ).inc(tokens)

        # Calculate and record cost
        cost = CostCalculator.calculate_embedding_cost(model, tokens)

        if cost > 0:
            PROCESSING_COST.labels(
                service=provider,
                operation="embedding_generation"
            ).inc(cost)

        return cost

    async def record_storage_operation(
        self,
        operation: str,
        backend: str,
        bytes_transferred: int,
        duration: float,
        status: str = "success"
    ):
        """
        Record storage operation metrics

        Args:
            operation: Operation type (upload, download, delete)
            backend: Storage backend (b2, supabase)
            bytes_transferred: Number of bytes transferred
            duration: Operation duration
            status: Operation status
        """
        STORAGE_OPERATIONS.labels(
            operation=operation,
            backend=backend,
            status=status
        ).inc()

        STORAGE_BYTES.labels(
            operation=operation,
            backend=backend
        ).inc(bytes_transferred)

    async def record_graph_sync(
        self,
        operation: str,
        duration: float,
        status: str = "success"
    ):
        """
        Record graph synchronization metrics

        Args:
            operation: Operation type (create, update, delete, query)
            duration: Operation duration
            status: Operation status
        """
        GRAPH_SYNC_OPERATIONS.labels(
            operation=operation,
            status=status
        ).inc()

        GRAPH_SYNC_DURATION.labels(operation=operation).observe(duration)

    async def update_queue_metrics(self, queue_name: str, size: int, avg_latency: float):
        """Update queue size and latency metrics"""
        QUEUE_SIZE.labels(queue_name=queue_name).set(size)
        QUEUE_LATENCY.labels(queue_name=queue_name).observe(avg_latency)

    async def _log_metrics_to_database(self, metrics: ProcessingMetrics):
        """Log processing metrics to processing_logs table"""
        if not self.supabase_storage:
            return

        try:
            # Create log entry for each stage
            for stage in metrics.stages:
                log_data = {
                    "timestamp": datetime.fromtimestamp(stage.start_time).isoformat(),
                    "severity": "error" if stage.status == "failure" else "info",
                    "category": "processing",
                    "error_type": stage.error if stage.error else None,
                    "error_message": f"Processing stage: {stage.stage}",
                    "file_id": metrics.file_id,
                    "filename": metrics.filename,
                    "task_type": f"processing_{stage.stage}",
                    "resolution_status": stage.status,
                    "additional_context": {
                        "stage": stage.stage,
                        "duration": stage.duration,
                        "cpu_usage": stage.cpu_usage,
                        "memory_usage": stage.memory_usage,
                        "cost": stage.cost,
                        "metadata": stage.metadata
                    }
                }

                await self.supabase_storage.insert_processing_log(log_data)

        except Exception as e:
            logger.error(f"Failed to log metrics to database: {e}")


# ============================================================================
# Singleton Instance
# ============================================================================

_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service(supabase_storage=None) -> MonitoringService:
    """Get or create singleton MonitoringService instance"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService(supabase_storage)
    return _monitoring_service
