"""
Celery tasks for async query processing with LangGraph + Arcade.dev for Empire v7.3

Provides background task processing for:
- Long-running adaptive research queries
- Bulk query processing
- Scheduled query refreshes
"""
from app.celery_app import celery_app
from app.workflows.langgraph_workflows import LangGraphWorkflows, QueryState
from app.workflows.workflow_router import workflow_router, WorkflowType
import structlog
import asyncio
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)


@celery_app.task(name="process_adaptive_query", bind=True)
def process_adaptive_query(
    self,
    query: str,
    max_iterations: int = 3,
    user_id: Optional[str] = None,
    use_external_tools: bool = True
) -> Dict[str, Any]:
    """
    Process adaptive query as background task using LangGraph.

    Use this for:
    - Long-running research queries (30+ seconds)
    - Queries requiring external web search
    - Complex queries needing iterative refinement
    - Bulk query processing

    Args:
        query: User query to process
        max_iterations: Maximum refinement iterations (default: 3)
        user_id: Optional user identifier for tracking
        use_external_tools: Allow external Arcade.dev tools (default: True)

    Returns:
        Dict containing answer, iterations, sources, tool_calls, and status

    Example:
        task = process_adaptive_query.apply_async(
            args=["Compare our policies with CA regulations"],
            kwargs={"max_iterations": 3}
        )
        result = task.get(timeout=300)
    """
    try:
        logger.info(
            "Celery adaptive query started",
            task_id=self.request.id,
            query=query[:100],
            user_id=user_id,
            max_iterations=max_iterations
        )

        # Send WebSocket notification - Task 10.4
        from app.utils.websocket_notifications import send_query_processing_update
        send_query_processing_update(
            task_id=self.request.id,
            query_id=self.request.id,  # Use task ID as query ID
            stage="initialization",
            status="started",
            message="Initializing adaptive research workflow",
            progress=10,
            metadata={"max_iterations": max_iterations},
            user_id=user_id
        )

        # Initialize LangGraph workflow
        workflows = LangGraphWorkflows()
        graph = workflows.build_adaptive_research_graph()

        # Set initial state
        initial_state: QueryState = {
            "query": query,
            "messages": [],
            "refined_queries": [],
            "search_results": [],
            "tool_calls": [],
            "final_answer": "",
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "needs_external_data": False
        }

        # Send progress update - Task 10.4
        send_query_processing_update(
            task_id=self.request.id,
            query_id=self.request.id,
            stage="processing",
            status="progress",
            message="Processing query with LangGraph workflow",
            progress=30,
            user_id=user_id
        )

        # Run async graph in sync Celery context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(graph.ainvoke(initial_state))
        finally:
            loop.close()

        # Send completion update - Task 10.4
        send_query_processing_update(
            task_id=self.request.id,
            query_id=self.request.id,
            stage="completed",
            status="success",
            message="Query processing completed",
            progress=100,
            metadata={
                "iterations": result["iteration_count"],
                "tool_calls": len(result.get("tool_calls", []))
            },
            user_id=user_id
        )

        logger.info(
            "Celery adaptive query completed",
            task_id=self.request.id,
            iterations=result["iteration_count"],
            tool_calls_count=len(result.get("tool_calls", []))
        )

        return {
            "answer": result.get("final_answer", ""),
            "refined_queries": result.get("refined_queries", []),
            "iterations": result["iteration_count"],
            "sources": result.get("search_results", []),
            "tool_calls": result.get("tool_calls", []),
            "status": "completed"
        }

    except Exception as e:
        logger.error(
            "Celery adaptive query failed",
            task_id=self.request.id,
            error=str(e),
            query=query[:100]
        )
        return {
            "status": "failed",
            "error": str(e),
            "answer": "",
            "iterations": 0,
            "sources": [],
            "tool_calls": []
        }


@celery_app.task(name="process_auto_routed_query", bind=True)
def process_auto_routed_query(
    self,
    query: str,
    max_iterations: int = 3,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process query with automatic workflow routing (CrewAI, LangGraph, or Simple).

    The router analyzes the query and selects:
    - LangGraph: For adaptive queries needing refinement/external data
    - CrewAI: For multi-agent document processing workflows
    - Simple: For direct knowledge base lookups

    Args:
        query: User query to process
        max_iterations: Maximum refinement iterations (default: 3)
        user_id: Optional user identifier for tracking

    Returns:
        Dict containing answer, workflow_type, and metadata

    Example:
        task = process_auto_routed_query.apply_async(
            args=["What are California insurance requirements?"]
        )
        result = task.get(timeout=300)
    """
    try:
        logger.info(
            "Celery auto-routed query started",
            task_id=self.request.id,
            query=query[:100],
            user_id=user_id
        )

        # Classify query using workflow router
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            classification = loop.run_until_complete(
                workflow_router.classify_query(query)
            )
        finally:
            loop.close()

        logger.info(
            "Query classified",
            workflow=classification.workflow_type.value,
            confidence=classification.confidence,
            task_id=self.request.id
        )

        # Route to appropriate handler
        if classification.workflow_type == WorkflowType.LANGGRAPH:
            # Use LangGraph for adaptive processing
            return process_adaptive_query(
                query=query,
                max_iterations=max_iterations,
                user_id=user_id
            )

        elif classification.workflow_type == WorkflowType.CREWAI:
            # Route to CrewAI service (stub for now)
            logger.info("CrewAI routing not yet implemented", task_id=self.request.id)
            return {
                "status": "pending",
                "answer": "CrewAI routing not yet implemented. This would process via multi-agent workflow.",
                "workflow_type": "crewai",
                "iterations": 0,
                "sources": [],
                "tool_calls": []
            }

        else:  # SIMPLE
            # Direct RAG pipeline (stub for now)
            logger.info("Simple RAG query", task_id=self.request.id, query=query[:100])
            return {
                "status": "completed",
                "answer": f"Simple RAG result for: {query}",
                "sources": [{"type": "vector", "content": "Stub result"}],
                "workflow_type": "simple",
                "iterations": 0,
                "tool_calls": []
            }

    except Exception as e:
        logger.error(
            "Celery auto-routed query failed",
            task_id=self.request.id,
            error=str(e)
        )
        return {
            "status": "failed",
            "error": str(e),
            "answer": "",
            "workflow_type": "unknown",
            "iterations": 0,
            "sources": [],
            "tool_calls": []
        }


@celery_app.task(name="batch_process_queries", bind=True)
def batch_process_queries(
    self,
    queries: list[str],
    max_iterations: int = 2,
    use_auto_routing: bool = True
) -> Dict[str, Any]:
    """
    Process multiple queries in batch using Celery group.

    Args:
        queries: List of queries to process
        max_iterations: Maximum iterations per query (default: 2 for batch)
        use_auto_routing: Use auto-routing vs direct LangGraph (default: True)

    Returns:
        Dict with task_ids for tracking individual query results

    Example:
        task = batch_process_queries.apply_async(
            args=[[
                "What are CA insurance laws?",
                "Compare with TX regulations",
                "Show compliance gaps"
            ]]
        )
        result = task.get()
        # Poll individual tasks with result['task_ids']
    """
    try:
        logger.info(
            "Batch query processing started",
            task_id=self.request.id,
            query_count=len(queries)
        )

        # Choose task function based on routing preference
        task_func = (
            process_auto_routed_query if use_auto_routing
            else process_adaptive_query
        )

        # Create async tasks for each query
        async_results = [
            task_func.apply_async(
                args=[query],
                kwargs={"max_iterations": max_iterations}
            )
            for query in queries
        ]

        task_ids = [result.id for result in async_results]

        logger.info(
            "Batch tasks created",
            parent_task_id=self.request.id,
            task_ids=task_ids,
            query_count=len(queries)
        )

        return {
            "status": "processing",
            "task_ids": task_ids,
            "query_count": len(queries),
            "message": "Queries submitted for processing. Poll task_ids for results."
        }

    except Exception as e:
        logger.error(
            "Batch query processing failed",
            task_id=self.request.id,
            error=str(e)
        )
        return {
            "status": "failed",
            "error": str(e),
            "task_ids": []
        }
