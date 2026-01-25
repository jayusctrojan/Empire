"""
Empire v7.3 - Dynamic Agent Selection Service

Provides intelligent agent selection based on task requirements,
agent capabilities, load balancing, and performance history.

Features:
- Capability-based agent matching
- Performance-weighted selection
- Load balancing across agents
- Fallback agent chains
- A/B testing support for agent variants

Author: Claude Code
Date: 2025-01-24
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================

class AgentCapability(str, Enum):
    """Agent capability types"""
    RESEARCH = "research"
    ANALYSIS = "analysis"
    WRITING = "writing"
    REVIEW = "review"
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    FACT_CHECK = "fact_check"
    SYNTHESIS = "synthesis"
    VISUALIZATION = "visualization"


class SelectionStrategy(str, Enum):
    """Selection strategy types"""
    BEST_MATCH = "best_match"  # Best capability match
    ROUND_ROBIN = "round_robin"  # Rotate through agents
    LEAST_LOADED = "least_loaded"  # Least busy agent
    PERFORMANCE = "performance"  # Best performing
    RANDOM = "random"  # Random selection
    WEIGHTED = "weighted"  # Weighted by capability scores


@dataclass
class AgentProfile:
    """Profile of an available agent"""
    agent_id: str
    name: str
    description: str

    # Capabilities
    capabilities: Dict[AgentCapability, float] = field(default_factory=dict)  # Capability scores 0-1
    primary_capability: Optional[AgentCapability] = None

    # Performance metrics
    avg_response_time: float = 0.0  # seconds
    success_rate: float = 1.0  # 0-1
    quality_score: float = 0.8  # 0-1

    # Load
    current_tasks: int = 0
    max_concurrent: int = 5

    # Availability
    is_available: bool = True
    cooldown_until: Optional[datetime] = None

    # Fallback
    fallback_agent_id: Optional[str] = None

    # Metadata
    version: str = "1.0"
    model: str = "claude-3-5-sonnet-20241022"
    tags: List[str] = field(default_factory=list)

    @property
    def is_under_load(self) -> bool:
        """Check if agent is under heavy load"""
        return self.current_tasks >= self.max_concurrent * 0.8

    @property
    def load_factor(self) -> float:
        """Current load as a factor (0-1)"""
        return self.current_tasks / self.max_concurrent if self.max_concurrent > 0 else 0

    def get_capability_score(self, capability: AgentCapability) -> float:
        """Get capability score"""
        return self.capabilities.get(capability, 0.0)

    def calculate_overall_score(
        self,
        required_capabilities: List[AgentCapability],
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate overall suitability score for a task.

        Args:
            required_capabilities: Required capabilities
            weights: Optional weights for scoring factors

        Returns:
            Overall score (0-1)
        """
        weights = weights or {
            "capability": 0.4,
            "performance": 0.3,
            "quality": 0.2,
            "load": 0.1
        }

        # Capability match score
        if required_capabilities:
            capability_score = sum(
                self.get_capability_score(cap)
                for cap in required_capabilities
            ) / len(required_capabilities)
        else:
            capability_score = 0.5

        # Performance score (inverse of response time, normalized)
        perf_score = 1.0 / (1.0 + self.avg_response_time / 10.0)  # Normalize around 10s

        # Quality score
        quality_score = self.quality_score

        # Load score (prefer less loaded)
        load_score = 1.0 - self.load_factor

        overall = (
            weights["capability"] * capability_score +
            weights["performance"] * perf_score +
            weights["quality"] * quality_score +
            weights["load"] * load_score
        )

        return overall

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "capabilities": {k.value: v for k, v in self.capabilities.items()},
            "primary_capability": self.primary_capability.value if self.primary_capability else None,
            "avg_response_time": self.avg_response_time,
            "success_rate": self.success_rate,
            "quality_score": self.quality_score,
            "current_tasks": self.current_tasks,
            "max_concurrent": self.max_concurrent,
            "is_available": self.is_available,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "fallback_agent_id": self.fallback_agent_id,
            "version": self.version,
            "model": self.model,
            "tags": self.tags
        }


@dataclass
class SelectionResult:
    """Result of agent selection"""
    agent_id: str
    agent_profile: AgentProfile
    score: float
    strategy_used: SelectionStrategy
    alternatives: List[Tuple[str, float]] = field(default_factory=list)  # [(agent_id, score), ...]
    selection_reason: str = ""


# ==============================================================================
# Agent Registry
# ==============================================================================

class AgentRegistry:
    """
    Registry of available agents with their profiles.

    Pre-populated with Empire's built-in agents.
    """

    def __init__(self):
        self._agents: Dict[str, AgentProfile] = {}
        self._initialize_default_agents()

    def _initialize_default_agents(self) -> None:
        """Initialize default Empire agents"""
        # Research Agent (AGENT-012)
        self.register(AgentProfile(
            agent_id="AGENT-012",
            name="Research Agent",
            description="Web and academic search, query expansion, source credibility",
            capabilities={
                AgentCapability.RESEARCH: 0.95,
                AgentCapability.EXTRACTION: 0.7,
                AgentCapability.CLASSIFICATION: 0.5
            },
            primary_capability=AgentCapability.RESEARCH,
            model="claude-3-5-sonnet-20241022",
            tags=["research", "search", "web"]
        ))

        # Analysis Agent (AGENT-013)
        self.register(AgentProfile(
            agent_id="AGENT-013",
            name="Analysis Agent",
            description="Pattern detection, statistical analysis, correlations",
            capabilities={
                AgentCapability.ANALYSIS: 0.95,
                AgentCapability.SYNTHESIS: 0.8,
                AgentCapability.EXTRACTION: 0.6
            },
            primary_capability=AgentCapability.ANALYSIS,
            fallback_agent_id="AGENT-012",
            model="claude-3-5-sonnet-20241022",
            tags=["analysis", "patterns", "statistics"]
        ))

        # Writing Agent (AGENT-014)
        self.register(AgentProfile(
            agent_id="AGENT-014",
            name="Writing Agent",
            description="Report generation, documentation, multi-format output",
            capabilities={
                AgentCapability.WRITING: 0.95,
                AgentCapability.SUMMARIZATION: 0.85,
                AgentCapability.SYNTHESIS: 0.7
            },
            primary_capability=AgentCapability.WRITING,
            fallback_agent_id="AGENT-013",
            model="claude-3-5-sonnet-20241022",
            tags=["writing", "reports", "documentation"]
        ))

        # Review Agent (AGENT-015)
        self.register(AgentProfile(
            agent_id="AGENT-015",
            name="Review Agent",
            description="Quality assurance, fact verification, consistency checking",
            capabilities={
                AgentCapability.REVIEW: 0.95,
                AgentCapability.FACT_CHECK: 0.9,
                AgentCapability.ANALYSIS: 0.6
            },
            primary_capability=AgentCapability.REVIEW,
            fallback_agent_id="AGENT-014",
            model="claude-3-5-sonnet-20241022",
            tags=["review", "qa", "verification"]
        ))

        # Content Summarizer (AGENT-002)
        self.register(AgentProfile(
            agent_id="AGENT-002",
            name="Content Summarizer",
            description="PDF summary generation with key points extraction",
            capabilities={
                AgentCapability.SUMMARIZATION: 0.95,
                AgentCapability.EXTRACTION: 0.8,
                AgentCapability.WRITING: 0.5
            },
            primary_capability=AgentCapability.SUMMARIZATION,
            model="claude-3-5-sonnet-20241022",
            tags=["summarization", "pdf", "extraction"]
        ))

        # Document Analysis Agents (AGENT-009, 010, 011)
        self.register(AgentProfile(
            agent_id="AGENT-009",
            name="Senior Research Analyst",
            description="Extract topics, entities, facts, quality assessment",
            capabilities={
                AgentCapability.EXTRACTION: 0.9,
                AgentCapability.RESEARCH: 0.8,
                AgentCapability.ANALYSIS: 0.7
            },
            primary_capability=AgentCapability.EXTRACTION,
            model="claude-3-5-sonnet-20241022",
            tags=["extraction", "research", "entities"]
        ))

        self.register(AgentProfile(
            agent_id="AGENT-010",
            name="Content Strategist",
            description="Executive summaries, findings, recommendations",
            capabilities={
                AgentCapability.SYNTHESIS: 0.9,
                AgentCapability.SUMMARIZATION: 0.85,
                AgentCapability.WRITING: 0.8
            },
            primary_capability=AgentCapability.SYNTHESIS,
            fallback_agent_id="AGENT-009",
            model="claude-3-5-sonnet-20241022",
            tags=["strategy", "synthesis", "recommendations"]
        ))

        self.register(AgentProfile(
            agent_id="AGENT-011",
            name="Fact Checker",
            description="Verify claims, assign confidence scores, provide citations",
            capabilities={
                AgentCapability.FACT_CHECK: 0.95,
                AgentCapability.REVIEW: 0.8,
                AgentCapability.RESEARCH: 0.6
            },
            primary_capability=AgentCapability.FACT_CHECK,
            model="claude-3-5-sonnet-20241022",
            tags=["fact-check", "verification", "citations"]
        ))

        # Department Classifier (AGENT-008)
        self.register(AgentProfile(
            agent_id="AGENT-008",
            name="Department Classifier",
            description="10-department content classification",
            capabilities={
                AgentCapability.CLASSIFICATION: 0.95,
                AgentCapability.ANALYSIS: 0.5
            },
            primary_capability=AgentCapability.CLASSIFICATION,
            model="claude-3-5-sonnet-20241022",
            tags=["classification", "departments"]
        ))

    def register(self, profile: AgentProfile) -> None:
        """Register an agent"""
        self._agents[profile.agent_id] = profile
        logger.debug("Agent registered", agent_id=profile.agent_id)

    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        """Get an agent by ID"""
        return self._agents.get(agent_id)

    def get_all(self) -> List[AgentProfile]:
        """Get all registered agents"""
        return list(self._agents.values())

    def get_available(self) -> List[AgentProfile]:
        """Get all available agents"""
        now = datetime.utcnow()
        return [
            a for a in self._agents.values()
            if a.is_available and (a.cooldown_until is None or a.cooldown_until < now)
        ]

    def get_by_capability(self, capability: AgentCapability) -> List[AgentProfile]:
        """Get agents with a specific capability"""
        return [
            a for a in self.get_available()
            if capability in a.capabilities and a.capabilities[capability] > 0.5
        ]


# ==============================================================================
# Agent Selector
# ==============================================================================

class AgentSelector:
    """
    Selects the best agent for a given task.

    Supports multiple selection strategies and can
    incorporate performance history.
    """

    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or AgentRegistry()
        self._round_robin_index: Dict[str, int] = {}
        self._performance_history: Dict[str, List[Dict]] = {}

    def select_agent(
        self,
        required_capabilities: List[AgentCapability],
        strategy: SelectionStrategy = SelectionStrategy.BEST_MATCH,
        exclude_agents: Optional[List[str]] = None,
        preferred_agent: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[SelectionResult]:
        """
        Select the best agent for a task.

        Args:
            required_capabilities: Required agent capabilities
            strategy: Selection strategy to use
            exclude_agents: Agents to exclude from selection
            preferred_agent: Preferred agent (if available)
            tags: Optional tag filters

        Returns:
            SelectionResult or None if no suitable agent
        """
        candidates = self.registry.get_available()

        # Apply filters
        if exclude_agents:
            candidates = [a for a in candidates if a.agent_id not in exclude_agents]

        if tags:
            candidates = [a for a in candidates if any(t in a.tags for t in tags)]

        if not candidates:
            logger.warning("No suitable agents available")
            return None

        # Check preferred agent first
        if preferred_agent:
            preferred = self.registry.get(preferred_agent)
            if preferred and preferred in candidates and not preferred.is_under_load:
                score = preferred.calculate_overall_score(required_capabilities)
                return SelectionResult(
                    agent_id=preferred_agent,
                    agent_profile=preferred,
                    score=score,
                    strategy_used=SelectionStrategy.BEST_MATCH,
                    selection_reason="Preferred agent available"
                )

        # Apply selection strategy
        if strategy == SelectionStrategy.BEST_MATCH:
            return self._select_best_match(candidates, required_capabilities)
        elif strategy == SelectionStrategy.ROUND_ROBIN:
            return self._select_round_robin(candidates, required_capabilities)
        elif strategy == SelectionStrategy.LEAST_LOADED:
            return self._select_least_loaded(candidates, required_capabilities)
        elif strategy == SelectionStrategy.PERFORMANCE:
            return self._select_by_performance(candidates, required_capabilities)
        elif strategy == SelectionStrategy.RANDOM:
            return self._select_random(candidates, required_capabilities)
        elif strategy == SelectionStrategy.WEIGHTED:
            return self._select_weighted(candidates, required_capabilities)
        else:
            return self._select_best_match(candidates, required_capabilities)

    def _select_best_match(
        self,
        candidates: List[AgentProfile],
        capabilities: List[AgentCapability]
    ) -> SelectionResult:
        """Select the best matching agent by capability score"""
        scored = [(a, a.calculate_overall_score(capabilities)) for a in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        best = scored[0]
        alternatives = [(a.agent_id, s) for a, s in scored[1:4]]

        return SelectionResult(
            agent_id=best[0].agent_id,
            agent_profile=best[0],
            score=best[1],
            strategy_used=SelectionStrategy.BEST_MATCH,
            alternatives=alternatives,
            selection_reason="Highest capability match score"
        )

    def _select_round_robin(
        self,
        candidates: List[AgentProfile],
        capabilities: List[AgentCapability]
    ) -> SelectionResult:
        """Select using round-robin rotation"""
        # Get capability key for round-robin tracking
        cap_key = "_".join(sorted([c.value for c in capabilities])) or "default"

        # Get and increment index
        idx = self._round_robin_index.get(cap_key, 0)
        self._round_robin_index[cap_key] = (idx + 1) % len(candidates)

        selected = candidates[idx % len(candidates)]

        return SelectionResult(
            agent_id=selected.agent_id,
            agent_profile=selected,
            score=selected.calculate_overall_score(capabilities),
            strategy_used=SelectionStrategy.ROUND_ROBIN,
            selection_reason=f"Round-robin index {idx}"
        )

    def _select_least_loaded(
        self,
        candidates: List[AgentProfile],
        capabilities: List[AgentCapability]
    ) -> SelectionResult:
        """Select the least loaded agent"""
        candidates.sort(key=lambda a: a.load_factor)
        selected = candidates[0]

        return SelectionResult(
            agent_id=selected.agent_id,
            agent_profile=selected,
            score=selected.calculate_overall_score(capabilities),
            strategy_used=SelectionStrategy.LEAST_LOADED,
            selection_reason=f"Lowest load factor: {selected.load_factor:.2f}"
        )

    def _select_by_performance(
        self,
        candidates: List[AgentProfile],
        capabilities: List[AgentCapability]
    ) -> SelectionResult:
        """Select based on performance history"""
        # Weight by performance metrics
        scored = []
        for agent in candidates:
            perf_score = agent.success_rate * agent.quality_score
            if agent.avg_response_time > 0:
                perf_score *= (1.0 / (1.0 + agent.avg_response_time / 30.0))
            scored.append((agent, perf_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0]

        return SelectionResult(
            agent_id=best[0].agent_id,
            agent_profile=best[0],
            score=best[1],
            strategy_used=SelectionStrategy.PERFORMANCE,
            selection_reason=f"Best performance score: {best[1]:.2f}"
        )

    def _select_random(
        self,
        candidates: List[AgentProfile],
        capabilities: List[AgentCapability]
    ) -> SelectionResult:
        """Random selection"""
        selected = random.choice(candidates)

        return SelectionResult(
            agent_id=selected.agent_id,
            agent_profile=selected,
            score=selected.calculate_overall_score(capabilities),
            strategy_used=SelectionStrategy.RANDOM,
            selection_reason="Random selection"
        )

    def _select_weighted(
        self,
        candidates: List[AgentProfile],
        capabilities: List[AgentCapability]
    ) -> SelectionResult:
        """Weighted random selection based on scores"""
        scored = [(a, a.calculate_overall_score(capabilities)) for a in candidates]
        total = sum(s for _, s in scored)

        if total == 0:
            return self._select_random(candidates, capabilities)

        # Weighted random choice
        r = random.uniform(0, total)
        cumulative = 0
        for agent, score in scored:
            cumulative += score
            if cumulative >= r:
                return SelectionResult(
                    agent_id=agent.agent_id,
                    agent_profile=agent,
                    score=score,
                    strategy_used=SelectionStrategy.WEIGHTED,
                    selection_reason=f"Weighted selection (weight: {score/total:.2f})"
                )

        # Fallback
        return SelectionResult(
            agent_id=scored[0][0].agent_id,
            agent_profile=scored[0][0],
            score=scored[0][1],
            strategy_used=SelectionStrategy.WEIGHTED,
            selection_reason="Weighted selection fallback"
        )

    # ==========================================================================
    # Performance Tracking
    # ==========================================================================

    def record_performance(
        self,
        agent_id: str,
        success: bool,
        response_time: float,
        quality_score: Optional[float] = None
    ) -> None:
        """
        Record agent performance for future selection.

        Args:
            agent_id: Agent that performed the task
            success: Whether the task succeeded
            response_time: Response time in seconds
            quality_score: Optional quality score (0-1)
        """
        if agent_id not in self._performance_history:
            self._performance_history[agent_id] = []

        self._performance_history[agent_id].append({
            "timestamp": datetime.utcnow(),
            "success": success,
            "response_time": response_time,
            "quality_score": quality_score
        })

        # Update agent profile with rolling averages
        agent = self.registry.get(agent_id)
        if agent:
            history = self._performance_history[agent_id][-100:]  # Last 100

            # Update success rate
            agent.success_rate = sum(1 for h in history if h["success"]) / len(history)

            # Update response time (exponential moving average)
            alpha = 0.1
            agent.avg_response_time = (
                alpha * response_time +
                (1 - alpha) * agent.avg_response_time
            )

            # Update quality score if provided
            if quality_score is not None:
                quality_scores = [h["quality_score"] for h in history if h.get("quality_score")]
                if quality_scores:
                    agent.quality_score = sum(quality_scores) / len(quality_scores)

    def get_fallback_agent(self, agent_id: str) -> Optional[AgentProfile]:
        """Get the fallback agent for a given agent"""
        agent = self.registry.get(agent_id)
        if agent and agent.fallback_agent_id:
            return self.registry.get(agent.fallback_agent_id)
        return None

    def set_agent_cooldown(
        self,
        agent_id: str,
        cooldown_seconds: int
    ) -> None:
        """Put an agent on cooldown (e.g., after rate limiting)"""
        agent = self.registry.get(agent_id)
        if agent:
            agent.cooldown_until = datetime.utcnow() + timedelta(seconds=cooldown_seconds)
            logger.info(
                "Agent on cooldown",
                agent_id=agent_id,
                until=agent.cooldown_until.isoformat()
            )


# ==============================================================================
# Service Factory
# ==============================================================================

_registry: Optional[AgentRegistry] = None
_selector: Optional[AgentSelector] = None


def get_agent_registry() -> AgentRegistry:
    """Get or create the agent registry singleton"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def get_agent_selector() -> AgentSelector:
    """Get or create the agent selector singleton"""
    global _selector
    if _selector is None:
        _selector = AgentSelector(get_agent_registry())
    return _selector
