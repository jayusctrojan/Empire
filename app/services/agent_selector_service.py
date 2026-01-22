"""
Agent Selector Service - Task 146

Intelligently routes tasks to optimal agents based on capabilities and performance history.
Uses multi-armed bandit approach (epsilon-greedy) for exploration-exploitation balance.

Agents in Empire v7.3:
- AGENT-001: Query Router (routes queries to appropriate workflow)
- AGENT-002: Content Summarizer (PDF summary generation)
- AGENT-003: Entity Extractor (knowledge graph entities)
- AGENT-004: Relationship Mapper (graph relationships)
- AGENT-005: Context Synthesizer (multi-source context)
- AGENT-006: Answer Generator (final response generation)
- AGENT-007: Citation Validator (source citation verification)
- AGENT-008: Department Classifier (10-dept classification)
- AGENT-009: Senior Research Analyst (topic/entity extraction)
- AGENT-010: Content Strategist (executive summaries)
- AGENT-011: Fact Checker (claim verification)
- AGENT-012: Research Agent (web/academic search)
- AGENT-013: Analysis Agent (pattern detection)
- AGENT-014: Writing Agent (report generation)
- AGENT-015: Review Agent (quality assurance)
- AGENT-016: Memory Agent (user context management)
- AGENT-017: Graph Query Agent (Neo4j traversal)
"""

import os
import random
import structlog
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from supabase import create_client, Client

logger = structlog.get_logger(__name__)


class TaskType(str, Enum):
    """Types of tasks that can be routed to agents."""
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    ENTITY_EXTRACTION = "entity_extraction"
    RELATIONSHIP_MAPPING = "relationship_mapping"
    CONTEXT_SYNTHESIS = "context_synthesis"
    ANSWER_GENERATION = "answer_generation"
    CITATION_VALIDATION = "citation_validation"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    WRITING = "writing"
    REVIEW = "review"
    FACT_CHECKING = "fact_checking"
    QUERY_ROUTING = "query_routing"
    MEMORY_MANAGEMENT = "memory_management"
    GRAPH_QUERY = "graph_query"


class AgentCapability(BaseModel):
    """Defines an agent's capabilities and task affinities."""
    agent_id: str
    agent_name: str
    primary_tasks: List[TaskType]
    secondary_tasks: List[TaskType] = Field(default_factory=list)
    model: str = "claude-sonnet-4-5"
    description: str = ""
    max_context_tokens: int = 100000
    supports_streaming: bool = True
    cost_tier: str = "standard"  # low, standard, high


class AgentPerformance(BaseModel):
    """Performance metrics for an agent on a specific task type."""
    agent_id: str
    task_type: TaskType
    total_executions: int = 0
    successful_executions: int = 0
    average_latency_ms: float = 0.0
    average_quality_score: float = 0.0
    last_execution: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    @property
    def composite_score(self) -> float:
        """Calculate composite score combining success rate and quality."""
        if self.total_executions == 0:
            return 0.5  # Default for unexplored agents
        # Weighted combination: 60% quality, 30% success rate, 10% speed bonus
        speed_bonus = max(0, 1 - (self.average_latency_ms / 10000))  # Bonus for <10s
        return (
            0.6 * self.average_quality_score +
            0.3 * self.success_rate +
            0.1 * speed_bonus
        )


class SelectionResult(BaseModel):
    """Result of agent selection with explanation."""
    selected_agent_id: str
    selected_agent_name: str
    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0)
    selection_reason: str
    alternative_agents: List[str] = Field(default_factory=list)
    exploration_mode: bool = False
    performance_history: Optional[Dict[str, Any]] = None


class OutcomeRecord(BaseModel):
    """Record of task execution outcome for learning."""
    agent_id: str
    task_type: TaskType
    success: bool
    quality_score: float = Field(ge=0.0, le=1.0)
    latency_ms: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Agent capability registry
AGENT_CAPABILITIES: Dict[str, AgentCapability] = {
    "AGENT-001": AgentCapability(
        agent_id="AGENT-001",
        agent_name="Query Router",
        primary_tasks=[TaskType.QUERY_ROUTING],
        secondary_tasks=[TaskType.CLASSIFICATION],
        model="claude-haiku-4-5",
        description="Routes queries to appropriate workflow (LangGraph, CrewAI, Simple RAG)",
        cost_tier="low"
    ),
    "AGENT-002": AgentCapability(
        agent_id="AGENT-002",
        agent_name="Content Summarizer",
        primary_tasks=[TaskType.SUMMARIZATION],
        secondary_tasks=[TaskType.CONTEXT_SYNTHESIS],
        model="claude-sonnet-4-5",
        description="PDF summary generation with key points extraction"
    ),
    "AGENT-003": AgentCapability(
        agent_id="AGENT-003",
        agent_name="Entity Extractor",
        primary_tasks=[TaskType.ENTITY_EXTRACTION],
        secondary_tasks=[TaskType.ANALYSIS],
        model="claude-sonnet-4-5",
        description="Extracts named entities for knowledge graph population"
    ),
    "AGENT-004": AgentCapability(
        agent_id="AGENT-004",
        agent_name="Relationship Mapper",
        primary_tasks=[TaskType.RELATIONSHIP_MAPPING],
        secondary_tasks=[TaskType.GRAPH_QUERY],
        model="claude-sonnet-4-5",
        description="Maps relationships between entities"
    ),
    "AGENT-005": AgentCapability(
        agent_id="AGENT-005",
        agent_name="Context Synthesizer",
        primary_tasks=[TaskType.CONTEXT_SYNTHESIS],
        secondary_tasks=[TaskType.SUMMARIZATION, TaskType.ANSWER_GENERATION],
        model="claude-sonnet-4-5",
        description="Synthesizes context from multiple sources"
    ),
    "AGENT-006": AgentCapability(
        agent_id="AGENT-006",
        agent_name="Answer Generator",
        primary_tasks=[TaskType.ANSWER_GENERATION],
        secondary_tasks=[TaskType.WRITING],
        model="claude-sonnet-4-5",
        description="Generates final responses with citations"
    ),
    "AGENT-007": AgentCapability(
        agent_id="AGENT-007",
        agent_name="Citation Validator",
        primary_tasks=[TaskType.CITATION_VALIDATION],
        secondary_tasks=[TaskType.FACT_CHECKING],
        model="claude-haiku-4-5",
        description="Verifies source citations accuracy",
        cost_tier="low"
    ),
    "AGENT-008": AgentCapability(
        agent_id="AGENT-008",
        agent_name="Department Classifier",
        primary_tasks=[TaskType.CLASSIFICATION],
        secondary_tasks=[TaskType.QUERY_ROUTING],
        model="claude-sonnet-4-5",
        description="Classifies content into 10 business departments"
    ),
    "AGENT-009": AgentCapability(
        agent_id="AGENT-009",
        agent_name="Senior Research Analyst",
        primary_tasks=[TaskType.RESEARCH, TaskType.ANALYSIS],
        secondary_tasks=[TaskType.ENTITY_EXTRACTION, TaskType.FACT_CHECKING],
        model="claude-sonnet-4-5",
        description="Extracts topics, entities, facts with quality assessment"
    ),
    "AGENT-010": AgentCapability(
        agent_id="AGENT-010",
        agent_name="Content Strategist",
        primary_tasks=[TaskType.SUMMARIZATION, TaskType.WRITING],
        secondary_tasks=[TaskType.CONTEXT_SYNTHESIS],
        model="claude-sonnet-4-5",
        description="Generates executive summaries, findings, recommendations"
    ),
    "AGENT-011": AgentCapability(
        agent_id="AGENT-011",
        agent_name="Fact Checker",
        primary_tasks=[TaskType.FACT_CHECKING],
        secondary_tasks=[TaskType.CITATION_VALIDATION, TaskType.REVIEW],
        model="claude-sonnet-4-5",
        description="Verifies claims with confidence scores and citations"
    ),
    "AGENT-012": AgentCapability(
        agent_id="AGENT-012",
        agent_name="Research Agent",
        primary_tasks=[TaskType.RESEARCH],
        secondary_tasks=[TaskType.ANALYSIS],
        model="claude-sonnet-4-5",
        description="Web/academic search, query expansion, source credibility"
    ),
    "AGENT-013": AgentCapability(
        agent_id="AGENT-013",
        agent_name="Analysis Agent",
        primary_tasks=[TaskType.ANALYSIS],
        secondary_tasks=[TaskType.RESEARCH, TaskType.ENTITY_EXTRACTION],
        model="claude-sonnet-4-5",
        description="Pattern detection, statistical analysis, correlations"
    ),
    "AGENT-014": AgentCapability(
        agent_id="AGENT-014",
        agent_name="Writing Agent",
        primary_tasks=[TaskType.WRITING],
        secondary_tasks=[TaskType.SUMMARIZATION, TaskType.ANSWER_GENERATION],
        model="claude-sonnet-4-5",
        description="Report generation, multi-format output, citations"
    ),
    "AGENT-015": AgentCapability(
        agent_id="AGENT-015",
        agent_name="Review Agent",
        primary_tasks=[TaskType.REVIEW],
        secondary_tasks=[TaskType.FACT_CHECKING, TaskType.CITATION_VALIDATION],
        model="claude-sonnet-4-5",
        description="Quality assurance, fact verification, revision loop"
    ),
    "AGENT-016": AgentCapability(
        agent_id="AGENT-016",
        agent_name="Memory Agent",
        primary_tasks=[TaskType.MEMORY_MANAGEMENT],
        secondary_tasks=[TaskType.CONTEXT_SYNTHESIS],
        model="claude-haiku-4-5",
        description="User context management and personalization",
        cost_tier="low"
    ),
    "AGENT-017": AgentCapability(
        agent_id="AGENT-017",
        agent_name="Graph Query Agent",
        primary_tasks=[TaskType.GRAPH_QUERY],
        secondary_tasks=[TaskType.RELATIONSHIP_MAPPING, TaskType.ENTITY_EXTRACTION],
        model="claude-sonnet-4-5",
        description="Neo4j graph traversal and Cypher query generation"
    ),
}


class AgentSelectorService:
    """
    Intelligent agent selection service using epsilon-greedy multi-armed bandit.

    Features:
    - Agent capability mapping for all 17 agents
    - Historical performance tracking per agent per task type
    - Optimal agent selection based on performance history
    - Exploration factor for underutilized agents
    - Selection explanation for transparency
    - Outcome recording for continuous improvement
    """

    def __init__(
        self,
        epsilon: float = 0.1,
        min_explorations: int = 5,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        """
        Initialize agent selector.

        Args:
            epsilon: Exploration rate (0-1). Higher = more exploration.
            min_explorations: Minimum executions before trusting performance data.
            supabase_url: Supabase URL for persistence.
            supabase_key: Supabase service key.
        """
        self.epsilon = epsilon
        self.min_explorations = min_explorations
        self.capabilities = AGENT_CAPABILITIES.copy()

        # In-memory performance cache
        self._performance_cache: Dict[str, AgentPerformance] = {}

        # Initialize Supabase client
        url = supabase_url or os.getenv("SUPABASE_URL")
        key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY")

        if url and key:
            self.supabase: Optional[Client] = create_client(url, key)
        else:
            self.supabase = None
            logger.warning("agent_selector_no_supabase",
                          message="Supabase not configured, using in-memory only")

    def _get_cache_key(self, agent_id: str, task_type: TaskType) -> str:
        """Generate cache key for agent-task combination."""
        return f"{agent_id}:{task_type.value}"

    async def _load_performance(
        self,
        agent_id: str,
        task_type: TaskType
    ) -> AgentPerformance:
        """Load performance data from database or cache."""
        cache_key = self._get_cache_key(agent_id, task_type)

        # Check cache first
        if cache_key in self._performance_cache:
            return self._performance_cache[cache_key]

        # Try loading from database
        if self.supabase:
            try:
                result = self.supabase.rpc(
                    "get_agent_performance_summary",
                    {"p_agent_id": agent_id}
                ).execute()

                if result.data and len(result.data) > 0:
                    for row in result.data:
                        if row.get("task_type") == task_type.value:
                            perf = AgentPerformance(
                                agent_id=agent_id,
                                task_type=task_type,
                                total_executions=row.get("total_executions", 0),
                                successful_executions=row.get("successful_executions", 0),
                                average_latency_ms=row.get("avg_latency_ms", 0),
                                average_quality_score=row.get("avg_quality_score", 0),
                                last_execution=row.get("last_execution")
                            )
                            self._performance_cache[cache_key] = perf
                            return perf
            except Exception as e:
                logger.warning("agent_selector_load_perf_error",
                              agent_id=agent_id, task_type=task_type.value, error=str(e))

        # Return default performance
        perf = AgentPerformance(agent_id=agent_id, task_type=task_type)
        self._performance_cache[cache_key] = perf
        return perf

    def _get_eligible_agents(self, task_type: TaskType) -> List[str]:
        """Get agents capable of handling a task type."""
        eligible = []

        for agent_id, capability in self.capabilities.items():
            if task_type in capability.primary_tasks:
                eligible.append(agent_id)
            elif task_type in capability.secondary_tasks:
                eligible.append(agent_id)

        return eligible

    async def select_agent(
        self,
        task_type: TaskType,
        context: Optional[Dict[str, Any]] = None,
        exclude_agents: Optional[List[str]] = None,
        prefer_low_cost: bool = False
    ) -> SelectionResult:
        """
        Select optimal agent for a task using epsilon-greedy strategy.

        Args:
            task_type: Type of task to route.
            context: Optional context for selection (e.g., query complexity).
            exclude_agents: Agents to exclude from selection.
            prefer_low_cost: If True, prefer lower-cost agents when scores are similar.

        Returns:
            SelectionResult with selected agent and explanation.
        """
        context = context or {}
        exclude_agents = exclude_agents or []

        # Get eligible agents
        eligible = [a for a in self._get_eligible_agents(task_type)
                   if a not in exclude_agents]

        if not eligible:
            raise ValueError(f"No agents available for task type: {task_type.value}")

        # Load performance for all eligible agents
        performances: Dict[str, AgentPerformance] = {}
        for agent_id in eligible:
            performances[agent_id] = await self._load_performance(agent_id, task_type)

        # Determine if we should explore
        exploration_mode = random.random() < self.epsilon

        # Find agents needing exploration (< min_explorations)
        underexplored = [
            a for a in eligible
            if performances[a].total_executions < self.min_explorations
        ]

        selected_agent_id: str
        selection_reason: str

        if exploration_mode and underexplored:
            # Explore: pick random underexplored agent
            selected_agent_id = random.choice(underexplored)
            selection_reason = (
                f"Exploration mode: testing underexplored agent "
                f"({performances[selected_agent_id].total_executions} prior executions)"
            )
        else:
            # Exploit: pick best performing agent
            scored_agents = [
                (agent_id, performances[agent_id].composite_score)
                for agent_id in eligible
            ]

            # Apply cost preference if requested
            if prefer_low_cost:
                scored_agents = [
                    (aid, score * (1.2 if self.capabilities[aid].cost_tier == "low" else 1.0))
                    for aid, score in scored_agents
                ]

            # Sort by score descending
            scored_agents.sort(key=lambda x: x[1], reverse=True)

            selected_agent_id = scored_agents[0][0]
            best_score = scored_agents[0][1]

            perf = performances[selected_agent_id]
            selection_reason = (
                f"Highest composite score ({best_score:.3f}): "
                f"{perf.success_rate*100:.1f}% success rate, "
                f"{perf.average_quality_score:.2f} avg quality, "
                f"{perf.total_executions} executions"
            )

            if perf.total_executions < self.min_explorations:
                selection_reason += " (limited data)"

        # Get alternative agents
        alternatives = [a for a in eligible if a != selected_agent_id][:3]

        # Calculate confidence based on data availability
        perf = performances[selected_agent_id]
        if perf.total_executions >= self.min_explorations * 2:
            confidence = 0.9
        elif perf.total_executions >= self.min_explorations:
            confidence = 0.7
        else:
            confidence = 0.5

        if exploration_mode:
            confidence *= 0.8  # Lower confidence in exploration mode

        logger.info(
            "agent_selected",
            selected_agent=selected_agent_id,
            task_type=task_type.value,
            exploration_mode=exploration_mode,
            confidence=confidence,
            alternatives=alternatives
        )

        return SelectionResult(
            selected_agent_id=selected_agent_id,
            selected_agent_name=self.capabilities[selected_agent_id].agent_name,
            task_type=task_type,
            confidence=confidence,
            selection_reason=selection_reason,
            alternative_agents=alternatives,
            exploration_mode=exploration_mode,
            performance_history={
                "total_executions": perf.total_executions,
                "success_rate": perf.success_rate,
                "average_quality": perf.average_quality_score,
                "average_latency_ms": perf.average_latency_ms
            }
        )

    async def record_outcome(self, outcome: OutcomeRecord) -> bool:
        """
        Record task execution outcome for learning.

        Args:
            outcome: Outcome record with execution results.

        Returns:
            True if successfully recorded.
        """
        cache_key = self._get_cache_key(outcome.agent_id, outcome.task_type)

        # Update in-memory cache
        if cache_key in self._performance_cache:
            perf = self._performance_cache[cache_key]
        else:
            perf = AgentPerformance(
                agent_id=outcome.agent_id,
                task_type=outcome.task_type
            )

        # Update running averages
        n = perf.total_executions
        perf.total_executions += 1

        if outcome.success:
            perf.successful_executions += 1

        # Exponential moving average for latency and quality
        alpha = 0.3  # Weight for new observation
        perf.average_latency_ms = (
            alpha * outcome.latency_ms + (1 - alpha) * perf.average_latency_ms
            if n > 0 else outcome.latency_ms
        )
        perf.average_quality_score = (
            alpha * outcome.quality_score + (1 - alpha) * perf.average_quality_score
            if n > 0 else outcome.quality_score
        )
        perf.last_execution = datetime.now(timezone.utc)

        self._performance_cache[cache_key] = perf

        # Persist to database
        if self.supabase:
            try:
                self.supabase.rpc(
                    "record_agent_outcome",
                    {
                        "p_agent_id": outcome.agent_id,
                        "p_task_type": outcome.task_type.value,
                        "p_success": outcome.success,
                        "p_quality_score": outcome.quality_score,
                        "p_latency_ms": int(outcome.latency_ms)
                    }
                ).execute()

                logger.info(
                    "agent_outcome_recorded",
                    agent_id=outcome.agent_id,
                    task_type=outcome.task_type.value,
                    success=outcome.success,
                    quality_score=outcome.quality_score
                )
                return True
            except Exception as e:
                logger.error("agent_outcome_record_error",
                           agent_id=outcome.agent_id, error=str(e))
                return False

        return True

    def get_agent_capabilities(self, agent_id: str) -> Optional[AgentCapability]:
        """Get capabilities for a specific agent."""
        return self.capabilities.get(agent_id)

    def list_agents_for_task(self, task_type: TaskType) -> List[Dict[str, Any]]:
        """
        List all agents capable of handling a task type with their capabilities.

        Args:
            task_type: Task type to query.

        Returns:
            List of agent info dicts.
        """
        eligible = self._get_eligible_agents(task_type)
        result = []

        for agent_id in eligible:
            cap = self.capabilities[agent_id]
            is_primary = task_type in cap.primary_tasks

            result.append({
                "agent_id": agent_id,
                "agent_name": cap.agent_name,
                "is_primary": is_primary,
                "model": cap.model,
                "cost_tier": cap.cost_tier,
                "description": cap.description
            })

        # Sort: primary agents first, then by name
        result.sort(key=lambda x: (not x["is_primary"], x["agent_name"]))
        return result

    async def get_performance_report(
        self,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get performance report for one or all agents.

        Args:
            agent_id: Specific agent to report, or None for all.

        Returns:
            Performance report dict.
        """
        agents = [agent_id] if agent_id else list(self.capabilities.keys())
        report = {"agents": {}, "summary": {}}

        total_executions = 0
        total_success = 0

        for aid in agents:
            agent_report = {
                "agent_name": self.capabilities[aid].agent_name,
                "task_performance": {}
            }

            for task_type in TaskType:
                perf = await self._load_performance(aid, task_type)

                if perf.total_executions > 0:
                    agent_report["task_performance"][task_type.value] = {
                        "total_executions": perf.total_executions,
                        "success_rate": perf.success_rate,
                        "average_quality": perf.average_quality_score,
                        "average_latency_ms": perf.average_latency_ms,
                        "composite_score": perf.composite_score
                    }
                    total_executions += perf.total_executions
                    total_success += perf.successful_executions

            if agent_report["task_performance"]:
                report["agents"][aid] = agent_report

        report["summary"] = {
            "total_executions": total_executions,
            "overall_success_rate": total_success / total_executions if total_executions > 0 else 0,
            "agents_tracked": len(report["agents"])
        }

        return report

    def set_epsilon(self, epsilon: float) -> None:
        """Update exploration rate (0-1)."""
        if not 0 <= epsilon <= 1:
            raise ValueError("Epsilon must be between 0 and 1")
        self.epsilon = epsilon
        logger.info("agent_selector_epsilon_updated", epsilon=epsilon)


# Singleton instance
_agent_selector_instance: Optional[AgentSelectorService] = None


def get_agent_selector(
    epsilon: float = 0.1,
    min_explorations: int = 5
) -> AgentSelectorService:
    """Get or create the agent selector singleton."""
    global _agent_selector_instance

    if _agent_selector_instance is None:
        _agent_selector_instance = AgentSelectorService(
            epsilon=epsilon,
            min_explorations=min_explorations
        )

    return _agent_selector_instance
