# LangGraph + Arcade.dev Integration Plan for Empire v7.3

## Executive Summary

This document outlines the integration plan for adding **LangGraph** (adaptive query workflows) and **Arcade.dev** (external tool integration) to Empire v7.3. Both will be integrated directly into the FastAPI application to complement the existing CrewAI service.

**Philosophy**: "Ready when we need it" - Infrastructure is set up now for future use.

**Status**: Ready for implementation (Task #46)
**Dependencies**: Tasks 16, 18, 20 (Backend infrastructure)
**Timeline**: Before Task 26 (Chat UI implementation)

---

## 1. Architecture Overview

### 1.1 Three-Layer Orchestration Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                           │
│                                                                   │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   CrewAI     │  │   LangGraph      │  │   Arcade.dev     │  │
│  │  (Layer 1)   │  │   (Layer 2)      │  │   (Layer 3)      │  │
│  │              │  │                  │  │                  │  │
│  │ Sequential   │  │ Adaptive         │  │ External Tools   │  │
│  │ Multi-Agent  │  │ Branching/Loops  │  │ Google, Slack,   │  │
│  │ Workflows    │  │ State Management │  │ GitHub, etc.     │  │
│  └──────┬───────┘  └────────┬─────────┘  └────────┬─────────┘  │
│         │                   │                      │             │
│         │          ┌────────▼──────────┐          │             │
│         └─────────►│  Workflow Router  │◄─────────┘             │
│                    │  (Query Classify) │                         │
│                    └────────┬──────────┘                         │
│                             │                                    │
│                    ┌────────▼──────────┐                         │
│                    │   RAG Pipeline    │                         │
│                    │   - Vector DB     │                         │
│                    │   - Neo4j Graph   │                         │
│                    │   - Hybrid Search │                         │
│                    └───────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 When to Use Each Layer

| Layer | Framework | Use Case | Example |
|-------|-----------|----------|---------|
| **Layer 1** | CrewAI | Multi-agent sequential workflows | Document processing pipeline |
| **Layer 2** | LangGraph | Adaptive queries with loops/branches | Research with query refinement |
| **Layer 3** | Arcade.dev | External API tool access | Web search, notifications, GitHub |

**IMPORTANT - Combined Use**: Arcade.dev tools are LangChain-compatible and available to **BOTH**:
- **CrewAI**: Tools integrated via agent tool configuration
- **LangGraph**: Tools integrated via ToolNode in StateGraphs

This means CrewAI agents can use Google Search, Slack notifications, GitHub API, and all 50+ Arcade tools, just like LangGraph workflows can.

---

## 2. Implementation Phases

### Phase 1: Dependency Installation
**Estimated Time**: 30 minutes

```bash
# Add to requirements.txt
langgraph>=0.0.50
langchain>=0.1.0
langchain-core>=0.1.0
langchain-anthropic>=0.1.0
arcadepy>=0.1.0
```

**Steps**:
1. Update `requirements.txt`
2. Install dependencies: `pip install -r requirements.txt`
3. Verify imports

**Validation**:
```python
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from arcadepy import Arcade

print("✅ LangGraph imported successfully")
print("✅ Arcade.dev imported successfully")
```

---

### Phase 2: Arcade.dev Setup
**Estimated Time**: 45 minutes

#### 2.1 Create Arcade.dev Account
1. Sign up at https://arcade.dev
2. Create new workspace for Empire
3. Generate API key
4. Configure tool access (Google, Slack, GitHub)

#### 2.2 Environment Configuration

**Add to `.env`**:
```bash
# Arcade.dev Configuration
ARCADE_API_KEY=<your-arcade-api-key>
ARCADE_ENABLED=true
ARCADE_DEFAULT_TOOLS=Google.Search,Slack.SendMessage
```

#### 2.3 Create Arcade Service

**Create `app/services/arcade_service.py`**:
```python
"""
Arcade.dev tool integration service.
"""
import os
from typing import List, Optional
from arcadepy import Arcade
from langchain.tools import Tool
import structlog

logger = structlog.get_logger(__name__)


class ArcadeService:
    """Manages Arcade.dev tool integration."""

    def __init__(self):
        api_key = os.getenv("ARCADE_API_KEY")
        if not api_key:
            logger.warning("ARCADE_API_KEY not set, Arcade tools disabled")
            self.arcade = None
            self.enabled = False
        else:
            self.arcade = Arcade(api_key=api_key)
            self.enabled = os.getenv("ARCADE_ENABLED", "true").lower() == "true"
            logger.info("Arcade.dev service initialized", enabled=self.enabled)

    def get_available_tools(self) -> List[str]:
        """List all available Arcade tools."""
        if not self.enabled or not self.arcade:
            return []

        try:
            return self.arcade.list_tools()
        except Exception as e:
            logger.error("Failed to list Arcade tools", error=str(e))
            return []

    def get_langchain_tools(self, tool_names: Optional[List[str]] = None) -> List[Tool]:
        """
        Get Arcade tools as LangChain-compatible tools.

        Args:
            tool_names: Specific tools to load (e.g., ["Google.Search", "Slack.SendMessage"])
                       If None, loads default tools from env var.

        Returns:
            List of LangChain Tool objects
        """
        if not self.enabled or not self.arcade:
            logger.warning("Arcade tools requested but service is disabled")
            return []

        # Use provided tools or fallback to defaults
        if tool_names is None:
            default_tools = os.getenv("ARCADE_DEFAULT_TOOLS", "")
            tool_names = [t.strip() for t in default_tools.split(",") if t.strip()]

        if not tool_names:
            logger.info("No Arcade tools specified, returning empty list")
            return []

        try:
            tools = self.arcade.get_langchain_tools(tool_names)
            logger.info("Loaded Arcade tools", count=len(tools), tools=tool_names)
            return tools
        except Exception as e:
            logger.error("Failed to load Arcade tools", error=str(e), tools=tool_names)
            return []


# Global instance
arcade_service = ArcadeService()
```

---

### Phase 3: LangGraph Workflow Implementation
**Estimated Time**: 2 hours

**Create `app/workflows/langgraph_workflows.py`**:
```python
"""
LangGraph workflow definitions with Arcade.dev tool integration.
"""
from typing import TypedDict, Annotated, List, Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain.tools import Tool
import operator
import structlog

from app.services.arcade_service import arcade_service

logger = structlog.get_logger(__name__)


class QueryState(TypedDict):
    """State object for adaptive query workflows."""
    query: str
    messages: Annotated[List[HumanMessage | AIMessage | ToolMessage], operator.add]
    refined_queries: Annotated[List[str], operator.add]
    search_results: Annotated[List[dict], operator.add]
    tool_calls: Annotated[List[dict], operator.add]
    final_answer: str
    iteration_count: int
    max_iterations: int
    needs_external_data: bool


class LangGraphWorkflows:
    """LangGraph workflow definitions with Arcade.dev integration."""

    def __init__(self, llm_model: str = "claude-3-5-haiku-20241022"):
        self.llm = ChatAnthropic(model=llm_model, temperature=0)
        self.tools = self._setup_tools()
        logger.info("LangGraph workflows initialized", tool_count=len(self.tools))

    def _setup_tools(self) -> List[Tool]:
        """
        Setup both internal (Empire) and external (Arcade) tools.

        Returns:
            Combined list of all available tools
        """
        tools = []

        # Layer 3: External tools via Arcade.dev (ready when needed)
        if arcade_service.enabled:
            arcade_tools = arcade_service.get_langchain_tools([
                "Google.Search",      # Web search for external context
                "Slack.SendMessage",  # Notifications (future use)
                # "GitHub.CreateIssue",  # Uncomment when needed
                # "Calendar.CreateEvent", # Uncomment when needed
            ])
            tools.extend(arcade_tools)
            logger.info("Arcade tools loaded", count=len(arcade_tools))

        # Layer 2: Internal Empire tools
        tools.extend([
            Tool(
                name="VectorSearch",
                func=self._vector_search,
                description="Search Empire's internal knowledge base using vector similarity. "
                            "Use this for queries about documents, policies, or internal data."
            ),
            Tool(
                name="GraphQuery",
                func=self._graph_query,
                description="Query Empire's knowledge graph (Neo4j) for entity relationships. "
                            "Use this to explore connections between entities, documents, or concepts."
            ),
            Tool(
                name="HybridSearch",
                func=self._hybrid_search,
                description="Combine vector and graph search for comprehensive results. "
                            "Use this for complex queries needing both semantic and relational context."
            ),
        ])

        logger.info("Total tools available", count=len(tools))
        return tools

    def build_adaptive_research_graph(self) -> StateGraph:
        """
        Build adaptive research workflow with tool support.

        Flow:
        1. Analyze Query → Determine strategy and required tools
        2. Plan Execution → Decide which tools to use
        3. Execute Tools → Call internal/external tools as needed
        4. Evaluate Results → Check quality, refine if needed
        5. Synthesize Answer → Generate final response
        """
        graph = StateGraph(QueryState)

        # Add nodes
        graph.add_node("analyze", self._analyze_query)
        graph.add_node("plan", self._plan_execution)
        graph.add_node("execute_tools", self._execute_tools_node())
        graph.add_node("evaluate", self._evaluate_results)
        graph.add_node("synthesize", self._synthesize_answer)

        # Set entry point
        graph.set_entry_point("analyze")

        # Define edges
        graph.add_edge("analyze", "plan")

        # Conditional: Use tools or go straight to synthesis
        graph.add_conditional_edges(
            "plan",
            self._should_use_tools,
            {
                "use_tools": "execute_tools",
                "synthesize": "synthesize"
            }
        )

        graph.add_edge("execute_tools", "evaluate")

        # Conditional: Refine and retry or finish
        graph.add_conditional_edges(
            "evaluate",
            self._should_refine,
            {
                "refine": "plan",  # Loop back for refinement
                "finish": "synthesize"
            }
        )

        graph.add_edge("synthesize", END)

        compiled = graph.compile()
        logger.info("Adaptive research graph compiled")
        return compiled

    def _execute_tools_node(self) -> ToolNode:
        """Create ToolNode with all available tools."""
        return ToolNode(self.tools)

    async def _analyze_query(self, state: QueryState) -> QueryState:
        """Analyze query to determine strategy."""
        query = state["query"]

        prompt = f"""Analyze this query and determine the search strategy:

Query: {query}

Determine:
1. Does it need external web search? (news, current events, external data)
2. Does it need internal knowledge base search? (documents, policies)
3. Does it need graph traversal? (relationships, connections)
4. Complexity level (simple, moderate, complex)

Respond in JSON format:
{{
    "needs_external_data": true/false,
    "needs_internal_search": true/false,
    "needs_graph_query": true/false,
    "complexity": "simple|moderate|complex",
    "reasoning": "Brief explanation"
}}"""

        response = await self.llm.ainvoke([HumanMessage(content=prompt)])

        # Parse response and update state
        # (In production, add proper JSON parsing)
        state["iteration_count"] = 0
        state["needs_external_data"] = False  # Parse from response

        logger.info("Query analyzed", query=query, iteration=0)
        return state

    async def _plan_execution(self, state: QueryState) -> QueryState:
        """Plan which tools to execute."""
        # Determine tool execution plan based on analysis
        logger.info("Planning execution", iteration=state["iteration_count"])
        return state

    async def _evaluate_results(self, state: QueryState) -> QueryState:
        """Evaluate result quality and decide if refinement needed."""
        state["iteration_count"] += 1
        logger.info("Results evaluated", iteration=state["iteration_count"])
        return state

    async def _synthesize_answer(self, state: QueryState) -> QueryState:
        """Generate final answer from all gathered information."""
        logger.info("Synthesizing answer")
        state["final_answer"] = "Generated answer"  # Implement synthesis logic
        return state

    def _should_use_tools(self, state: QueryState) -> str:
        """Decide if tools are needed."""
        # Logic to determine if tools should be called
        return "use_tools"

    def _should_refine(self, state: QueryState) -> str:
        """Decide if query needs refinement."""
        if state["iteration_count"] >= state["max_iterations"]:
            return "finish"

        # Check result quality
        return "finish"

    # Internal tool implementations
    async def _vector_search(self, query: str) -> str:
        """Execute vector search on internal knowledge base."""
        from app.services.vector_search import vector_search_service
        results = await vector_search_service.hybrid_search(query, limit=10)
        return str(results)

    async def _graph_query(self, query: str) -> str:
        """Execute graph query on Neo4j."""
        from app.services.neo4j_service import neo4j_service
        results = await neo4j_service.semantic_search(query)
        return str(results)

    async def _hybrid_search(self, query: str) -> str:
        """Execute hybrid search combining vector and graph."""
        vector_results = await self._vector_search(query)
        graph_results = await self._graph_query(query)
        return f"Vector: {vector_results}\nGraph: {graph_results}"
```

---

### Phase 4: Workflow Router
**Estimated Time**: 1 hour

**Create `app/workflows/workflow_router.py`**:
```python
"""
Route queries to optimal orchestration framework.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
import structlog

logger = structlog.get_logger(__name__)


class WorkflowType(str, Enum):
    """Supported workflow orchestration types."""
    CREWAI = "crewai"          # Layer 1: Sequential multi-agent
    LANGGRAPH = "langgraph"    # Layer 2: Adaptive branching
    SIMPLE = "simple"          # Direct RAG


class QueryClassification(BaseModel):
    """Query classification result."""
    workflow_type: WorkflowType
    confidence: float
    reasoning: str
    suggested_tools: list[str] = []


class WorkflowRouter:
    """Intelligent query routing to optimal framework."""

    def __init__(self, model: str = "claude-3-5-haiku-20241022"):
        self.llm = ChatAnthropic(model=model, temperature=0)

    async def classify_query(
        self,
        query: str,
        context: Optional[dict] = None
    ) -> QueryClassification:
        """
        Classify query and determine optimal orchestration framework.

        Decision Logic:
        - LANGGRAPH: Queries needing refinement, external data, iteration
        - CREWAI: Multi-document processing, framework extraction
        - SIMPLE: Direct factual queries from internal knowledge base
        """

        prompt = f"""Classify this query and recommend the best processing framework:

Query: "{query}"

Frameworks:
1. LANGGRAPH: Use for queries needing:
   - Iterative refinement
   - External web search (via Arcade.dev)
   - Adaptive branching logic
   - Quality evaluation and retry

2. CREWAI: Use for tasks needing:
   - Multi-agent collaboration
   - Sequential document processing
   - Role-based task delegation
   - Complex multi-step workflows

3. SIMPLE: Use for queries that:
   - Can be answered directly from knowledge base
   - Don't need refinement or iteration
   - Are straightforward factual lookups

Respond in JSON:
{{
    "workflow_type": "langgraph|crewai|simple",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "suggested_tools": ["tool1", "tool2"]
}}"""

        response = await self.llm.ainvoke([HumanMessage(content=prompt)])

        # Parse response (add proper JSON parsing in production)
        classification = QueryClassification(
            workflow_type=WorkflowType.SIMPLE,
            confidence=0.85,
            reasoning="Parsed from LLM response",
            suggested_tools=[]
        )

        logger.info(
            "Query classified",
            query=query,
            workflow=classification.workflow_type,
            confidence=classification.confidence
        )

        return classification


# Global instance
workflow_router = WorkflowRouter()
```

---

### Phase 5: FastAPI Endpoint Integration
**Estimated Time**: 1.5 hours

**Update `app/api/routes/query.py`**:
```python
"""
Query processing endpoints with LangGraph + Arcade.dev support.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
import structlog

from app.workflows.langgraph_workflows import LangGraphWorkflows
from app.workflows.workflow_router import workflow_router, WorkflowType
from app.services.auth import verify_token
from app.services.arcade_service import arcade_service

router = APIRouter(prefix="/api/query", tags=["query"])
logger = structlog.get_logger(__name__)


class AdaptiveQueryRequest(BaseModel):
    """Request for adaptive query processing."""
    query: str = Field(..., description="User query to process")
    max_iterations: int = Field(3, ge=1, le=5, description="Max refinement iterations")
    use_external_tools: bool = Field(True, description="Allow external API calls via Arcade")
    use_graph_context: bool = Field(True, description="Include Neo4j graph context")


class AdaptiveQueryResponse(BaseModel):
    """Response from adaptive query processing."""
    answer: str
    refined_queries: List[str] = []
    sources: List[dict] = []
    tool_calls: List[dict] = []
    iterations: int
    workflow_type: str
    processing_time_ms: int


class ToolListResponse(BaseModel):
    """Available tools information."""
    internal_tools: List[str]
    external_tools: List[str]
    total_count: int


@router.get("/tools", response_model=ToolListResponse)
async def list_available_tools(user=Depends(verify_token)):
    """
    List all available tools (internal + Arcade.dev).

    Useful for debugging and understanding what capabilities are available.
    """
    internal = ["VectorSearch", "GraphQuery", "HybridSearch"]
    external = arcade_service.get_available_tools() if arcade_service.enabled else []

    return ToolListResponse(
        internal_tools=internal,
        external_tools=external,
        total_count=len(internal) + len(external)
    )


@router.post("/adaptive", response_model=AdaptiveQueryResponse)
async def adaptive_query_endpoint(
    request: AdaptiveQueryRequest,
    background_tasks: BackgroundTasks,
    user=Depends(verify_token)
):
    """
    Execute adaptive query using LangGraph workflow with tool support.

    This endpoint provides:
    - Iterative query refinement
    - Conditional branching logic
    - Internal tool access (vector, graph search)
    - External tool access via Arcade.dev (when enabled and needed)
    - Quality evaluation and retry logic

    Use this for:
    - Research queries needing external context
    - Complex questions requiring refinement
    - Queries that might need web search
    """
    import time
    start_time = time.time()

    try:
        logger.info(
            "Adaptive query started",
            query=request.query,
            user_id=user.get("sub"),
            max_iterations=request.max_iterations
        )

        # Initialize workflow
        workflows = LangGraphWorkflows()
        graph = workflows.build_adaptive_research_graph()

        # Set initial state
        initial_state = {
            "query": request.query,
            "messages": [],
            "refined_queries": [],
            "search_results": [],
            "tool_calls": [],
            "final_answer": "",
            "iteration_count": 0,
            "max_iterations": request.max_iterations,
            "needs_external_data": False
        }

        # Execute graph
        result = await graph.ainvoke(initial_state)

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "Adaptive query completed",
            iterations=result["iteration_count"],
            processing_time_ms=processing_time,
            tool_calls=len(result["tool_calls"])
        )

        return AdaptiveQueryResponse(
            answer=result["final_answer"],
            refined_queries=result["refined_queries"],
            sources=result["search_results"],
            tool_calls=result["tool_calls"],
            iterations=result["iteration_count"],
            workflow_type="langgraph",
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error("Adaptive query failed", error=str(e), query=request.query)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto", response_model=AdaptiveQueryResponse)
async def auto_routed_query(
    request: AdaptiveQueryRequest,
    background_tasks: BackgroundTasks,
    user=Depends(verify_token)
):
    """
    Automatically route query to optimal framework (CrewAI, LangGraph, or Simple RAG).

    The router analyzes the query and decides:
    - LangGraph: For adaptive queries needing refinement/external data
    - CrewAI: For multi-agent document processing workflows
    - Simple: For direct knowledge base lookups

    This is the recommended endpoint for most use cases.
    """
    try:
        # Classify query
        classification = await workflow_router.classify_query(request.query)

        logger.info(
            "Query routed",
            workflow=classification.workflow_type,
            confidence=classification.confidence
        )

        # Route to appropriate handler
        if classification.workflow_type == WorkflowType.LANGGRAPH:
            return await adaptive_query_endpoint(request, background_tasks, user)

        elif classification.workflow_type == WorkflowType.CREWAI:
            # Route to CrewAI service
            from app.services.crewai_service import crewai_service
            result = await crewai_service.process_query(request.query)
            return AdaptiveQueryResponse(
                answer=result["answer"],
                workflow_type="crewai",
                processing_time_ms=result.get("processing_time", 0),
                **result
            )

        else:  # SIMPLE
            # Direct RAG pipeline
            from app.services.vector_search import vector_search_service
            results = await vector_search_service.hybrid_search(
                request.query,
                limit=10
            )
            return AdaptiveQueryResponse(
                answer=results["answer"],
                sources=results["sources"],
                workflow_type="simple",
                processing_time_ms=results.get("processing_time", 0),
                iterations=0,
                refined_queries=[],
                tool_calls=[]
            )

    except Exception as e:
        logger.error("Auto-routed query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
```

---

### Phase 6: Celery Task Integration
**Estimated Time**: 45 minutes

**Update `app/tasks/query_tasks.py`**:
```python
"""
Celery tasks for async query processing with LangGraph + Arcade.dev.
"""
from celery_app import celery_app
from app.workflows.langgraph_workflows import LangGraphWorkflows
import structlog

logger = structlog.get_logger(__name__)


@celery_app.task(name="process_adaptive_query", bind=True)
def process_adaptive_query(self, query: str, max_iterations: int = 3, user_id: str = None):
    """
    Process adaptive query as background task.

    Use this for:
    - Long-running research queries
    - Bulk query processing
    - Scheduled query refreshes
    """
    import asyncio

    try:
        logger.info(
            "Celery adaptive query started",
            task_id=self.request.id,
            query=query,
            user_id=user_id
        )

        workflows = LangGraphWorkflows()
        graph = workflows.build_adaptive_research_graph()

        initial_state = {
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

        # Run async graph in sync context
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(graph.ainvoke(initial_state))

        logger.info(
            "Celery adaptive query completed",
            task_id=self.request.id,
            iterations=result["iteration_count"]
        )

        return {
            "answer": result["final_answer"],
            "iterations": result["iteration_count"],
            "sources": result["search_results"],
            "tool_calls": result["tool_calls"],
            "status": "completed"
        }

    except Exception as e:
        logger.error(
            "Celery adaptive query failed",
            task_id=self.request.id,
            error=str(e)
        )
        return {
            "status": "failed",
            "error": str(e)
        }
```

---

## 3. Configuration

### 3.1 Environment Variables

**Update `.env`**:
```bash
# ============================================
# LangGraph Configuration
# ============================================
LANGGRAPH_ENABLED=true
LANGGRAPH_DEFAULT_MODEL=claude-3-5-haiku-20241022
LANGGRAPH_MAX_ITERATIONS=3
LANGGRAPH_TIMEOUT_SECONDS=300

# ============================================
# Arcade.dev Configuration
# ============================================
ARCADE_API_KEY=<your-arcade-api-key>
ARCADE_ENABLED=true
ARCADE_DEFAULT_TOOLS=Google.Search,Slack.SendMessage

# ============================================
# Workflow Routing
# ============================================
WORKFLOW_ROUTER_ENABLED=true
WORKFLOW_ROUTER_MODEL=claude-3-5-haiku-20241022
WORKFLOW_AUTO_ROUTING=false  # Start with manual routing

# ============================================
# Feature Flags (Gradual Rollout)
# ============================================
FEATURE_LANGGRAPH_ENABLED=true
FEATURE_ARCADE_ENABLED=true
FEATURE_AUTO_ROUTING_ENABLED=false  # Enable after testing
```

### 3.2 Feature Flags

**Create `app/config/features.py`**:
```python
"""
Feature flags for gradual rollout of new capabilities.
"""
from pydantic_settings import BaseSettings
import os


class FeatureFlags(BaseSettings):
    """Feature flags for LangGraph and Arcade.dev rollout."""

    # Core features
    langgraph_enabled: bool = os.getenv("FEATURE_LANGGRAPH_ENABLED", "true").lower() == "true"
    arcade_enabled: bool = os.getenv("FEATURE_ARCADE_ENABLED", "true").lower() == "true"

    # Advanced features (start disabled)
    auto_routing_enabled: bool = os.getenv("FEATURE_AUTO_ROUTING_ENABLED", "false").lower() == "true"
    hybrid_workflows_enabled: bool = False

    # Tool-specific features
    enable_google_search: bool = True
    enable_slack_notifications: bool = False  # Enable when ready
    enable_github_integration: bool = False  # Enable when ready

    class Config:
        env_prefix = "FEATURE_"


feature_flags = FeatureFlags()
```

---

## 4. Testing Strategy

### 4.1 Unit Tests

**Create `tests/test_arcade_service.py`**:
```python
import pytest
from app.services.arcade_service import ArcadeService


def test_arcade_service_initialization():
    """Test Arcade service initializes correctly."""
    service = ArcadeService()
    assert service is not None


def test_get_langchain_tools():
    """Test getting LangChain tools from Arcade."""
    service = ArcadeService()

    if service.enabled:
        tools = service.get_langchain_tools(["Google.Search"])
        assert len(tools) > 0
        assert tools[0].name == "Google.Search"
    else:
        tools = service.get_langchain_tools()
        assert len(tools) == 0


def test_list_available_tools():
    """Test listing all available Arcade tools."""
    service = ArcadeService()

    if service.enabled:
        tools = service.get_available_tools()
        assert isinstance(tools, list)
```

**Create `tests/test_langgraph_workflows.py`**:
```python
import pytest
from app.workflows.langgraph_workflows import LangGraphWorkflows, QueryState


@pytest.mark.asyncio
async def test_workflow_initialization():
    """Test LangGraph workflows initialize with tools."""
    workflows = LangGraphWorkflows()

    # Should have at least internal tools
    assert len(workflows.tools) >= 3
    assert any(t.name == "VectorSearch" for t in workflows.tools)
    assert any(t.name == "GraphQuery" for t in workflows.tools)


@pytest.mark.asyncio
async def test_adaptive_research_graph_execution():
    """Test full graph execution."""
    workflows = LangGraphWorkflows()
    graph = workflows.build_adaptive_research_graph()

    initial_state: QueryState = {
        "query": "What are California insurance requirements?",
        "messages": [],
        "refined_queries": [],
        "search_results": [],
        "tool_calls": [],
        "final_answer": "",
        "iteration_count": 0,
        "max_iterations": 2,
        "needs_external_data": False
    }

    result = await graph.ainvoke(initial_state)

    assert result["final_answer"] != ""
    assert result["iteration_count"] <= 2
```

### 4.2 Integration Tests

**Create `tests/integration/test_query_endpoints.py`**:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_tools_endpoint():
    """Test /api/query/tools endpoint."""
    response = client.get(
        "/api/query/tools",
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
    data = response.json()

    assert "internal_tools" in data
    assert "external_tools" in data
    assert len(data["internal_tools"]) >= 3


def test_adaptive_query_endpoint():
    """Test /api/query/adaptive endpoint."""
    response = client.post(
        "/api/query/adaptive",
        json={
            "query": "Research California insurance regulations",
            "max_iterations": 2,
            "use_external_tools": True
        },
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
    data = response.json()

    assert "answer" in data
    assert "workflow_type" in data
    assert data["workflow_type"] == "langgraph"
```

---

## 5. Monitoring & Observability

### 5.1 Prometheus Metrics

**Add to `app/monitoring/metrics.py`**:
```python
from prometheus_client import Counter, Histogram, Gauge

# LangGraph metrics
langgraph_queries_total = Counter(
    'langgraph_queries_total',
    'Total LangGraph queries processed',
    ['status', 'user_id']
)

langgraph_iterations = Histogram(
    'langgraph_iterations',
    'Number of iterations per query',
    buckets=[1, 2, 3, 4, 5]
)

langgraph_duration_seconds = Histogram(
    'langgraph_duration_seconds',
    'Query processing duration',
    buckets=[1, 5, 10, 30, 60, 120]
)

# Arcade.dev metrics
arcade_tool_calls_total = Counter(
    'arcade_tool_calls_total',
    'Total Arcade tool calls',
    ['tool_name', 'status']
)

arcade_tools_available = Gauge(
    'arcade_tools_available',
    'Number of available Arcade tools'
)

# Workflow routing metrics
workflow_routing_total = Counter(
    'workflow_routing_total',
    'Queries routed by framework',
    ['framework', 'confidence_bucket']
)
```

### 5.2 Structured Logging

All components use `structlog` for consistent logging:

```python
logger.info(
    "langgraph.query.started",
    query=query,
    user_id=user_id,
    iteration=0
)

logger.info(
    "arcade.tool.called",
    tool_name="Google.Search",
    duration_ms=234
)

logger.info(
    "workflow.routed",
    framework="langgraph",
    confidence=0.87
)
```

---

## 6. Deployment Checklist

### 6.1 Pre-Deployment

- [ ] All unit tests passing (`pytest tests/`)
- [ ] Integration tests passing
- [ ] Arcade.dev account created and API key obtained
- [ ] Environment variables configured in `.env`
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Monitoring dashboards created

### 6.2 Deployment to Render

**Step 1: Update Dependencies**
```bash
# Push updated requirements.txt to GitHub
git add requirements.txt
git commit -m "feat: Add LangGraph and Arcade.dev dependencies"
git push origin main
```

**Step 2: Configure Environment Variables** (via Render MCP)
```
"Update environment variables for FastAPI service srv-d44o2dq4d50c73elgupg with:
LANGGRAPH_ENABLED=true
ARCADE_API_KEY=<your-key>
ARCADE_ENABLED=true
FEATURE_LANGGRAPH_ENABLED=true
FEATURE_ARCADE_ENABLED=true"
```

**Step 3: Deploy**
- Render will auto-deploy on git push
- Monitor deployment logs via Render MCP

**Step 4: Validate**
```bash
# Check health
curl https://jb-empire-api.onrender.com/health

# List tools
curl -H "Authorization: Bearer $TOKEN" \
  https://jb-empire-api.onrender.com/api/query/tools

# Test adaptive query
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Research AI regulations", "max_iterations": 2}' \
  https://jb-empire-api.onrender.com/api/query/adaptive
```

---

## 7. Gradual Rollout Plan

### Week 1: Internal Testing
- Deploy with all features enabled
- Test via direct `/adaptive` endpoint
- Validate tool calling works correctly
- Monitor metrics and logs
- Keep `auto_routing_enabled=false`

### Week 2: Beta Users
- Enable for 10% of queries
- A/B test against simple RAG
- Collect feedback
- Monitor performance impact
- Optimize based on data

### Week 3: Full Rollout
- Enable `auto_routing_enabled=true`
- All queries automatically classified
- Monitor for degradation
- Adjust routing logic as needed

---

## 8. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Answer quality improvement | +20% | User satisfaction scores |
| External data usage | 5-10% of queries | Arcade tool call rate |
| Response time (with tools) | <15s | P95 latency |
| Tool call success rate | >95% | Arcade API success rate |
| Routing accuracy | >85% | Manual review of classifications |

---

## 9. Usage Examples

### Example 1: Simple Internal Query
```python
# Query routes to SIMPLE (direct RAG)
POST /api/query/auto
{
    "query": "What is our policy on employee benefits?"
}

# Response uses only internal VectorSearch
```

### Example 2: Research with External Data
```python
# Query routes to LANGGRAPH with Arcade tools
POST /api/query/auto
{
    "query": "Compare our insurance policies with current California regulations",
    "use_external_tools": true
}

# Response:
# 1. Searches internal knowledge base (VectorSearch)
# 2. Searches current CA regulations (Arcade: Google.Search)
# 3. Synthesizes comparison
```

### Example 3: Complex Multi-Document Processing
```python
# Query routes to CREWAI
POST /api/query/auto
{
    "query": "Process these 10 contracts and extract all policy numbers and dates"
}

# Response uses CrewAI multi-agent workflow
```

---

## 10. Documentation Updates

After implementation, update:

1. **API Documentation** (`/docs` Swagger UI)
   - Add examples for new endpoints
   - Document tool usage
   - Explain routing logic

2. **Developer Guide** (`docs/guides/`)
   - Create `LANGGRAPH_GUIDE.md`
   - Create `ARCADE_INTEGRATION_GUIDE.md`
   - Update `QUERY_PROCESSING_GUIDE.md`

3. **CLAUDE.md**
   - Add LangGraph and Arcade.dev to tools section
   - Update workflow examples
   - Add troubleshooting tips

---

## 11. Troubleshooting

### Issue: Arcade tools not loading
**Cause**: Missing API key or network issue
**Fix**: Check `ARCADE_API_KEY` in `.env`, verify API key is valid
**Debug**: Check logs for "Arcade.dev service initialized"

### Issue: Graph execution hangs
**Cause**: Infinite loop in conditional edges
**Fix**: Verify all edges have termination conditions
**Prevention**: Always check `iteration_count` vs `max_iterations`

### Issue: High latency with external tools
**Cause**: Sequential tool calls
**Fix**: Implement parallel tool execution (future enhancement)
**Mitigation**: Reduce `max_iterations` to 2

---

## 12. Future Enhancements

After successful deployment, consider:

1. **Parallel Tool Execution** - Run multiple tools simultaneously
2. **Streaming Responses** - Stream intermediate results to UI
3. **Tool Result Caching** - Cache external API responses
4. **Custom Tool Creation** - Allow users to add custom Arcade tools
5. **Visual Workflow Editor** - UI for building LangGraph workflows

---

## Appendix: Quick Reference

### Key Files Created/Modified

```
app/
├── services/
│   └── arcade_service.py          # NEW: Arcade.dev integration
├── workflows/
│   ├── langgraph_workflows.py     # NEW: LangGraph StateGraphs
│   └── workflow_router.py         # NEW: Query classification
├── api/routes/
│   └── query.py                   # UPDATED: New endpoints
├── tasks/
│   └── query_tasks.py             # UPDATED: Celery support
└── config/
    └── features.py                # NEW: Feature flags

tests/
├── test_arcade_service.py         # NEW
├── test_langgraph_workflows.py    # NEW
└── integration/
    └── test_query_endpoints.py    # NEW

docs/guides/
└── LANGGRAPH_ARCADE_INTEGRATION_PLAN.md  # This file
```

### Key Endpoints

- `GET /api/query/tools` - List available tools
- `POST /api/query/adaptive` - Direct LangGraph query
- `POST /api/query/auto` - Auto-routed query (recommended)

### Environment Variables Summary

```bash
LANGGRAPH_ENABLED=true
ARCADE_API_KEY=<your-key>
ARCADE_ENABLED=true
FEATURE_AUTO_ROUTING_ENABLED=false  # Enable gradually
```

---

**Version**: 1.0
**Task**: #46
**Status**: Ready for Implementation
**Last Updated**: 2025-11-07
