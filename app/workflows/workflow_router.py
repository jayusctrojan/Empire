"""
Intelligent query routing to optimal orchestration framework for Empire v7.3

Routes queries to:
- LangGraph: Adaptive queries needing refinement, external data, iteration
- CrewAI: Multi-agent document processing and sequential workflows
- Simple RAG: Direct factual queries from internal knowledge base
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
import structlog
import os
import json

logger = structlog.get_logger(__name__)


class WorkflowType(str, Enum):
    """Supported workflow orchestration types."""
    CREWAI = "crewai"          # Layer 1: Sequential multi-agent workflows
    LANGGRAPH = "langgraph"    # Layer 2: Adaptive branching/loops
    SIMPLE = "simple"          # Direct RAG pipeline


class QueryClassification(BaseModel):
    """Query classification result with confidence and reasoning."""
    workflow_type: WorkflowType = Field(..., description="Optimal workflow framework for this query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence score")
    reasoning: str = Field(..., description="Explanation of why this framework was chosen")
    suggested_tools: list[str] = Field(default_factory=list, description="Tools that should be used")


class WorkflowRouter:
    """
    Intelligent query routing to optimal orchestration framework.

    Uses Claude to analyze queries and determine the best processing approach.
    """

    def __init__(self, model: str = None):
        model_name = model or os.getenv("WORKFLOW_ROUTER_MODEL", "claude-haiku-4-5")
        self.llm = ChatAnthropic(model=model_name, temperature=0)
        logger.info("Workflow router initialized", model=model_name)

    async def classify_query(
        self,
        query: str,
        context: Optional[dict] = None
    ) -> QueryClassification:
        """
        Classify query and determine optimal orchestration framework.

        Args:
            query: User query to classify
            context: Optional additional context about the query

        Returns:
            QueryClassification with workflow type, confidence, and reasoning

        Decision Logic:
        - LANGGRAPH: Queries needing refinement, external data, iteration
        - CREWAI: Multi-document processing, framework extraction
        - SIMPLE: Direct factual queries from internal knowledge base
        """

        prompt = f"""Classify this query and recommend the best processing framework:

Query: "{query}"

Frameworks:

1. LANGGRAPH - Use for queries needing:
   - Iterative refinement and quality evaluation
   - External web search (via Arcade.dev for current events, regulations)
   - Adaptive branching logic based on intermediate results
   - Multiple attempts with fallback strategies
   - Complex research requiring multiple sources

   Examples:
   - "Compare our policies with current California insurance regulations"
   - "Research recent changes in employment law and how they affect us"
   - "What are the latest industry trends and how do they impact our strategy?"

2. CREWAI - Use for tasks needing:
   - Multi-agent collaboration with specialized roles
   - Sequential document processing pipelines
   - Role-based task delegation (parser, extractor, synthesizer)
   - Complex multi-step workflows with handoffs between agents

   Examples:
   - "Process these 10 contracts and extract all policy numbers and effective dates"
   - "Analyze multiple documents and extract the common framework they use"
   - "Review all employee handbooks and identify inconsistencies"

3. SIMPLE - Use for queries that:
   - Can be answered directly from the knowledge base
   - Don't need refinement or iteration
   - Are straightforward factual lookups
   - Don't require external data or multi-step processing

   Examples:
   - "What is our policy on employee vacation days?"
   - "Show me documents related to 'data privacy'"
   - "What does contract #12345 say about payment terms?"

Respond in JSON format:
{{
    "workflow_type": "langgraph|crewai|simple",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation (1-2 sentences)",
    "suggested_tools": ["tool1", "tool2"]
}}

Be conservative - if unsure, choose SIMPLE."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            # Extract JSON from response
            content = response.content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content

            # Parse classification
            data = json.loads(json_str)

            classification = QueryClassification(
                workflow_type=WorkflowType(data["workflow_type"]),
                confidence=float(data["confidence"]),
                reasoning=data["reasoning"],
                suggested_tools=data.get("suggested_tools", [])
            )

            logger.info(
                "Query classified",
                query=query[:50],
                workflow=classification.workflow_type.value,
                confidence=classification.confidence
            )

            return classification

        except Exception as e:
            logger.error("Query classification failed", error=str(e), query=query[:50])

            # Fallback to SIMPLE on error
            return QueryClassification(
                workflow_type=WorkflowType.SIMPLE,
                confidence=0.5,
                reasoning=f"Fallback to SIMPLE due to classification error: {str(e)}",
                suggested_tools=["VectorSearch"]
            )


# Global singleton instance
workflow_router = WorkflowRouter()
