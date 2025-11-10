"""
LangGraph workflow definitions with Arcade.dev tool integration for Empire v7.3
Implements adaptive query processing with branching, loops, and external tool access
"""
from typing import TypedDict, Annotated, List, Literal, Any, Dict
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import Tool
import operator
import structlog
import os
import json

from app.services.arcade_service import arcade_service
from app.core.langfuse_config import observe

logger = structlog.get_logger(__name__)


class QueryState(TypedDict):
    """State object for adaptive query workflows with all necessary fields."""
    query: str
    messages: Annotated[List[BaseMessage], operator.add]
    refined_queries: Annotated[List[str], operator.add]
    search_results: Annotated[List[dict], operator.add]
    tool_calls: Annotated[List[dict], operator.add]
    final_answer: str
    iteration_count: int
    max_iterations: int
    needs_external_data: bool


class LangGraphWorkflows:
    """
    LangGraph workflow definitions with Arcade.dev integration.

    Implements adaptive query processing with:
    - Conditional branching based on query analysis
    - Iterative refinement loops with quality evaluation
    - Tool integration (internal + external via Arcade.dev)
    - State management for complex workflows
    """

    def __init__(self, llm_model: str = None):
        model = llm_model or os.getenv("LANGGRAPH_DEFAULT_MODEL", "claude-3-5-haiku-20241022")
        self.llm = ChatAnthropic(model=model, temperature=0)
        self.tools = self._setup_tools()
        logger.info("LangGraph workflows initialized", tool_count=len(self.tools), model=model)

    def _setup_tools(self) -> List[Tool]:
        """
        Setup both internal (Empire) and external (Arcade.dev) tools.

        Returns:
            Combined list of all available tools for use in workflows
        """
        tools = []

        # Layer 3: External tools via Arcade.dev (ready when needed)
        if arcade_service.enabled:
            try:
                arcade_tools = arcade_service.get_langchain_tools([
                    "Google.Search",      # Web search for external context
                    "Slack.SendMessage",  # Notifications (future use)
                ])
                tools.extend(arcade_tools)
                logger.info("Arcade tools loaded", count=len(arcade_tools))
            except Exception as e:
                logger.warning("Failed to load Arcade tools", error=str(e))

        # Layer 2: Internal Empire tools (stubs for now - will be implemented)
        tools.extend([
            Tool(
                name="VectorSearch",
                func=lambda q: self._vector_search_stub(q),
                description=(
                    "Search Empire's internal knowledge base using vector similarity. "
                    "Use this for queries about documents, policies, or internal data."
                )
            ),
            Tool(
                name="GraphQuery",
                func=lambda q: self._graph_query_stub(q),
                description=(
                    "Query Empire's knowledge graph (Neo4j) for entity relationships. "
                    "Use this to explore connections between entities, documents, or concepts."
                )
            ),
            Tool(
                name="HybridSearch",
                func=lambda q: self._hybrid_search_stub(q),
                description=(
                    "Combine vector and graph search for comprehensive results. "
                    "Use this for complex queries needing both semantic and relational context."
                )
            ),
        ])

        logger.info("Total tools available", count=len(tools))
        return tools

    @observe(name="build_langgraph_workflow")
    def build_adaptive_research_graph(self) -> StateGraph:
        """
        Build adaptive research workflow with tool support.

        Flow:
        1. Analyze Query → Determine strategy and required tools
        2. Plan Execution → Decide which tools to use
        3. Execute Tools → Call internal/external tools as needed
        4. Evaluate Results → Check quality, refine if needed
        5. Synthesize Answer → Generate final response

        Returns:
            Compiled StateGraph ready for execution
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
        logger.info("Adaptive research graph compiled successfully")
        return compiled

    def _execute_tools_node(self) -> ToolNode:
        """Create ToolNode with all available tools."""
        return ToolNode(self.tools)

    @observe(name="langgraph_analyze_query")
    async def _analyze_query(self, state: QueryState) -> QueryState:
        """
        Analyze query to determine search strategy.

        Uses Claude to understand query intent and requirements.
        """
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

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            # Extract JSON from response
            content = response.content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content

            analysis = json.loads(json_str)

            # Update state with analysis
            state["iteration_count"] = 0
            state["needs_external_data"] = analysis.get("needs_external_data", False)
            state["messages"].append(response)

            logger.info(
                "Query analyzed",
                query=query[:50],
                needs_external=state["needs_external_data"],
                complexity=analysis.get("complexity")
            )
        except Exception as e:
            logger.error("Query analysis failed", error=str(e))
            state["needs_external_data"] = False
            state["iteration_count"] = 0

        return state

    async def _plan_execution(self, state: QueryState) -> QueryState:
        """
        Plan which tools to execute based on query analysis.

        Determines the optimal sequence of tool calls.
        """
        query = state["query"]
        needs_external = state.get("needs_external_data", False)

        prompt = f"""Based on this query, determine which tools to use:

Query: {query}
Needs External Data: {needs_external}

Available Tools:
- VectorSearch: Search internal knowledge base
- GraphQuery: Query knowledge graph for relationships
- HybridSearch: Combined vector + graph search
- Google.Search: Search the web (use sparingly, only if truly needed)

Respond with JSON array of tool names to call:
{{"tools": ["tool1", "tool2"]}}

Keep it minimal - only use necessary tools."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            state["messages"].append(response)

            logger.info("Execution planned", iteration=state["iteration_count"])
        except Exception as e:
            logger.error("Planning failed", error=str(e))

        return state

    async def _evaluate_results(self, state: QueryState) -> QueryState:
        """
        Evaluate result quality and decide if refinement needed.

        Checks if gathered information is sufficient or if another iteration is needed.
        """
        state["iteration_count"] += 1

        # Simple quality check for now
        has_results = len(state.get("search_results", [])) > 0

        logger.info(
            "Results evaluated",
            iteration=state["iteration_count"],
            has_results=has_results,
            result_count=len(state.get("search_results", []))
        )

        return state

    async def _synthesize_answer(self, state: QueryState) -> QueryState:
        """
        Generate final answer from all gathered information.

        Combines search results and context into coherent response.
        """
        query = state["query"]
        search_results = state.get("search_results", [])

        prompt = f"""Generate a comprehensive answer based on the following:

Query: {query}

Search Results: {json.dumps(search_results[:3], indent=2)}

Provide a clear, accurate answer based on the available information."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            state["final_answer"] = response.content
            state["messages"].append(response)

            logger.info("Answer synthesized", query=query[:50])
        except Exception as e:
            logger.error("Synthesis failed", error=str(e))
            state["final_answer"] = f"Error generating answer: {str(e)}"

        return state

    def _should_use_tools(self, state: QueryState) -> str:
        """
        Decide if tools are needed or can go straight to synthesis.

        Returns:
            "use_tools" or "synthesize"
        """
        # For now, always use tools unless we have no tools available
        if len(self.tools) == 0:
            return "synthesize"

        return "use_tools"

    def _should_refine(self, state: QueryState) -> str:
        """
        Decide if query needs refinement or is ready for final answer.

        Returns:
            "refine" to loop back for another iteration, or "finish" to synthesize
        """
        # Check max iterations
        if state["iteration_count"] >= state.get("max_iterations", 3):
            logger.info("Max iterations reached", iterations=state["iteration_count"])
            return "finish"

        # Check if we have enough information
        has_results = len(state.get("search_results", [])) > 0
        if has_results:
            return "finish"

        # Default: continue if under max iterations
        return "finish"

    # Tool implementation stubs (will be replaced with actual services)
    def _vector_search_stub(self, query: str) -> str:
        """Stub for vector search - will connect to actual service later."""
        logger.info("VectorSearch called", query=query[:50])
        return f"Vector search results for: {query}"

    def _graph_query_stub(self, query: str) -> str:
        """Stub for graph query - will connect to actual service later."""
        logger.info("GraphQuery called", query=query[:50])
        return f"Graph query results for: {query}"

    def _hybrid_search_stub(self, query: str) -> str:
        """Stub for hybrid search - will connect to actual service later."""
        logger.info("HybridSearch called", query=query[:50])
        return f"Hybrid search results for: {query}"
