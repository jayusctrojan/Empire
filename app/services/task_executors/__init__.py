"""
Empire v7.3 - Task Executors Package

Task executors for the Research Projects (Agent Harness) feature.
Each executor handles a specific type of research task.

Executors:
- RetrievalExecutor: RAG, NLQ, Graph, and API retrieval tasks
- SynthesisExecutor: Combining and analyzing findings
- ReportExecutor: Report generation and review tasks

Progress Tracking:
- ProgressEmitter: Mixin for mid-task progress updates
- BatchProgressTracker: Track progress across batch operations
"""

from app.services.task_executors.retrieval_executor import (
    RetrievalExecutor,
    get_retrieval_executor,
)
from app.services.task_executors.synthesis_executor import (
    SynthesisExecutor,
    get_synthesis_executor,
)
from app.services.task_executors.report_executor import (
    ReportExecutor,
    get_report_executor,
)
from app.services.task_executors.progress_emitter import (
    ProgressEmitter,
    ProgressState,
    ProgressStep,
    BatchProgressTracker,
)

__all__ = [
    "RetrievalExecutor",
    "get_retrieval_executor",
    "SynthesisExecutor",
    "get_synthesis_executor",
    "ReportExecutor",
    "get_report_executor",
    "ProgressEmitter",
    "ProgressState",
    "ProgressStep",
    "BatchProgressTracker",
]
