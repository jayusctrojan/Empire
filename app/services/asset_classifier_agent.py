"""
Empire v7.3 - AGENT-002: Empire Asset Classifier

Dedicated agent for classifying user-provided content into one of five
mutually exclusive AI Asset Types and routing to the appropriate Generator Agent.

Asset Types:
- SKILL (AGENT-003): Modular capability package with scripts/resources
- SLASH COMMAND (AGENT-004): Single-file user shortcut
- GENERATIVE BLUEPRINT (AGENT-005): Generative blueprint for flawless external structures
- WORKFLOW (AGENT-006): Multi-step orchestration with state management
- AGENT (AGENT-007): Role-based persona with delegation capabilities

Decision Tree v2 (from Ava's research):
1. Orchestration Filter: Multi-step with external APIs? -> WORKFLOW
2. Logic/Resource Filter: Scripts or directory of files? -> SKILL
3. Automaticity Filter: Auto-triggered by AI? -> SKILL
4. Delegation Filter: Role-based with isolated context? -> AGENT
5. Blueprint vs Macro Filter: Structural recipe vs chat shortcut? -> GENERATIVE BLUEPRINT / SLASH COMMAND

Author: Claude Code
Date: 2025-01-26
"""

import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AssetType(str, Enum):
    """Mutually exclusive AI Asset Types for Empire"""
    SKILL = "skill"                         # AGENT-003 - Action/Tool Use
    SLASH_COMMAND = "slash_command"         # AGENT-004 - Chat macros
    GENERATIVE_BLUEPRINT = "generative_blueprint"  # AGENT-005 - Proven precision instructions
    WORKFLOW = "workflow"                   # AGENT-006 - Multi-step orchestration
    AGENT = "agent"                         # AGENT-007 - Role-based personas


# Target generator agents
GENERATOR_AGENTS = {
    AssetType.SKILL: "AGENT-003",
    AssetType.SLASH_COMMAND: "AGENT-004",
    AssetType.GENERATIVE_BLUEPRINT: "AGENT-005",
    AssetType.WORKFLOW: "AGENT-006",
    AssetType.AGENT: "AGENT-007",
}


# Asset Type Definitions with key indicators
ASSET_TYPE_DEFINITIONS = {
    AssetType.SKILL: {
        "definition": "A modular capability package (directory-based) that Claude loads when it needs a specific capability.",
        "key_indicator": "Independence. Claude chooses to use it.",
        "driver": "Designed to be discovered and auto-invoked by the AI based on context.",
        "examples": [
            "Project Charter skill with templates and examples",
            "Code review checklist with patterns",
            "Sales pitch generator with tone variations"
        ],
        "keywords": [
            "automate", "script", "python", "bash", "directory", "files",
            "resources", "examples", "capability", "auto-invoke", "context-aware"
        ]
    },
    AssetType.SLASH_COMMAND: {
        "definition": "A single-file user shortcut (/command) used to trigger a specific task manually.",
        "key_indicator": "Manual Control. The human must type it.",
        "driver": "Requires explicit human invocation (the / trigger).",
        "examples": [
            "/summarize - Quick content summary",
            "/follow-up - Draft follow-up email",
            "/lint - Run code linting"
        ],
        "keywords": [
            "shortcut", "macro", "quick", "hotkey", "/", "command",
            "trigger", "manual", "user-invoked", "simple action"
        ]
    },
    AssetType.GENERATIVE_BLUEPRINT: {
        "definition": "A proven, precision instruction set (prompt library) that reliably produces flawless structured output. Curated in collaboration with Claude.",
        "key_indicator": "Precision Output. Proven instructions that consistently produce flawless results.",
        "driver": "Battle-tested, high-precision instructions stored as reusable recipes for generating consistent, flawless outputs.",
        "examples": [
            "Airtable base with 6 tables and linked fields",
            "PostgreSQL schema with RLS policies",
            "Tailwind CSS landing page with pricing grid",
            "React component structure",
            "Project charter with all required sections",
            "Business plan with financials template"
        ],
        "keywords": [
            "build", "construct", "create", "airtable", "database", "schema",
            "sql", "table", "structure", "blueprint", "ui", "component",
            "flawless", "external", "platform", "proven", "precision",
            "template", "library", "recipe", "instructions", "reliable"
        ]
    },
    AssetType.WORKFLOW: {
        "definition": "A multi-step orchestration that manages state and tool-chaining across platforms.",
        "key_indicator": "Stateful Chaining. Handles the sequence.",
        "driver": "Involves state management, conditional branching (If/Else), or chaining multiple platforms.",
        "examples": [
            "Lead qualification: Signal -> Airtable -> GitHub",
            "Incident response with ticketing and escalation",
            "Data pipeline with ETL steps"
        ],
        "keywords": [
            "workflow", "pipeline", "sequence", "chain", "integration",
            "api", "webhook", "state", "conditional", "if/else", "branch",
            "orchestrate", "multi-platform", "trigger", "scheduled"
        ]
    },
    AssetType.AGENT: {
        "definition": "A role-based persona that acts as a specialized worker in an isolated session.",
        "key_indicator": "Delegation. Creates a separate context.",
        "driver": "Requires a specific persona, backstory, or an isolated context window for secure/parallel execution.",
        "examples": [
            "Research Agent with web search and document reader",
            "Editor Agent with specific writing style",
            "Security Auditor Agent with isolated context"
        ],
        "keywords": [
            "agent", "persona", "role", "backstory", "delegate", "isolated",
            "context", "parallel", "specialized", "worker", "autonomous",
            "model override", "opus", "sonnet"
        ]
    }
}


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AssetClassificationResult(BaseModel):
    """Result of asset classification by AGENT-002"""
    analysis: str = Field(description="3-sentence logic explaining the decision based on the tree")
    classification: AssetType = Field(description="The determined asset type")
    target_agent: str = Field(description="Target generator agent (AGENT-003 through AGENT-007)")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    handover_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured summary of content to pass to the generator agent"
    )
    decision_path: List[str] = Field(
        default_factory=list,
        description="The path through the decision tree"
    )


class ContentIndicators(BaseModel):
    """Extracted indicators from content for classification"""
    has_external_apis: bool = False
    has_state_management: bool = False
    has_conditional_branching: bool = False
    has_multi_platform_chaining: bool = False
    has_scripts_or_code: bool = False
    has_directory_structure: bool = False
    is_auto_triggered: bool = False
    is_user_invoked: bool = False
    has_role_persona: bool = False
    has_isolated_context: bool = False
    has_delegation: bool = False
    builds_external_structure: bool = False
    is_structural_recipe: bool = False
    is_chat_macro: bool = False
    matched_keywords: Dict[str, List[str]] = Field(default_factory=dict)


# =============================================================================
# AGENT-002: ASSET CLASSIFIER
# =============================================================================

class AssetClassifierAgent:
    """
    AGENT-002: Empire Asset Classifier

    Analyzes user-provided content and classifies it into one of five
    mutually exclusive AI Asset Types, then routes to the appropriate
    Generator Agent (AGENT-003 through AGENT-007).

    Classification Decision Tree (v2):
    1. Orchestration Filter -> WORKFLOW
    2. Logic/Resource Filter -> SKILL
    3. Automaticity Filter -> SKILL
    4. Delegation Filter -> AGENT
    5. Blueprint vs Macro Filter -> GENERATIVE BLUEPRINT / SLASH COMMAND
    """

    def __init__(self, use_llm_enhancement: bool = True):
        """Initialize AGENT-002 with optional LLM enhancement"""
        self.use_llm_enhancement = use_llm_enhancement
        self.llm = None

        if use_llm_enhancement:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.llm = ChatAnthropic(
                    model="claude-sonnet-4-5-20250514",
                    temperature=0.0,
                    max_tokens=1000,
                    api_key=api_key
                )

        # Statistics
        self.stats = {
            "total_classified": 0,
            "by_asset_type": {at.value: 0 for at in AssetType},
            "average_confidence": 0.0,
        }

        logger.info(
            "AGENT-002 (Asset Classifier) initialized",
            llm_enhanced=self.llm is not None
        )

    def _extract_indicators(self, content: str, title: Optional[str] = None) -> ContentIndicators:
        """
        Extract classification indicators from content.

        Args:
            content: The content to analyze
            title: Optional title/name of the asset

        Returns:
            ContentIndicators with detected patterns
        """
        content_lower = content.lower()
        title_lower = (title or "").lower()
        combined = f"{title_lower} {content_lower}"

        matched_keywords: Dict[str, List[str]] = {at.value: [] for at in AssetType}

        # Match keywords for each asset type
        for asset_type, definition in ASSET_TYPE_DEFINITIONS.items():
            for kw in definition["keywords"]:
                if kw in combined:
                    matched_keywords[asset_type.value].append(kw)

        # Step 1: Orchestration indicators (WORKFLOW)
        has_external_apis = any(kw in combined for kw in [
            "api", "webhook", "endpoint", "fetch", "request", "http",
            "rest", "graphql", "integration"
        ])

        has_state_management = any(kw in combined for kw in [
            "state", "status", "track", "persist", "save state",
            "checkpoint", "resume", "retry"
        ])

        has_conditional_branching = any(kw in combined for kw in [
            "if/else", "if else", "conditional", "branch", "decision",
            "when", "condition", "route based on"
        ])

        has_multi_platform_chaining = any(kw in combined for kw in [
            "->", "then", "chain", "pipeline", "sequence",
            "airtable -> github", "signal -> airtable"
        ]) and has_external_apis

        # Step 2: Logic/Resource indicators (SKILL)
        has_scripts_or_code = any(kw in combined for kw in [
            "script", "python", "bash", "javascript", ".py", ".sh", ".js",
            "function", "def ", "code", "execute", "run"
        ])

        has_directory_structure = any(kw in combined for kw in [
            "directory", "folder", "files", "structure",
            "skill.md", "examples/", "scripts/", "template/"
        ])

        # Step 3: Automaticity indicators (SKILL vs COMMAND)
        is_auto_triggered = any(kw in combined for kw in [
            "auto", "automatic", "detect", "context-aware", "when claude",
            "ai invoked", "triggered by", "discovered"
        ])

        is_user_invoked = any(kw in combined for kw in [
            "/", "slash", "command", "type", "user types", "manually",
            "shortcut", "macro", "hotkey"
        ])

        # Step 4: Delegation indicators (AGENT)
        has_role_persona = any(kw in combined for kw in [
            "role", "persona", "character", "backstory", "personality",
            "you are a", "act as", "behave as"
        ])

        has_isolated_context = any(kw in combined for kw in [
            "isolated", "separate context", "parallel", "secure",
            "sandboxed", "independent session"
        ])

        has_delegation = any(kw in combined for kw in [
            "delegate", "hand off", "pass to", "route to",
            "can delegate to", "works with other agents"
        ])

        # Step 5: Blueprint vs Macro indicators
        builds_external_structure = any(kw in combined for kw in [
            "airtable", "database", "schema", "sql", "postgres", "mysql",
            "table", "fields", "linked", "ui", "component", "tailwind",
            "react", "html", "css", "structure", "build", "construct",
            "generate schema", "create base"
        ])

        is_structural_recipe = (
            builds_external_structure and
            any(kw in combined for kw in ["flawless", "precise", "exact", "blueprint", "recipe"])
        )

        is_chat_macro = (
            is_user_invoked and
            any(kw in combined for kw in ["quick", "simple", "shortcut", "macro", "helper"])
        )

        return ContentIndicators(
            has_external_apis=has_external_apis,
            has_state_management=has_state_management,
            has_conditional_branching=has_conditional_branching,
            has_multi_platform_chaining=has_multi_platform_chaining,
            has_scripts_or_code=has_scripts_or_code,
            has_directory_structure=has_directory_structure,
            is_auto_triggered=is_auto_triggered,
            is_user_invoked=is_user_invoked,
            has_role_persona=has_role_persona,
            has_isolated_context=has_isolated_context,
            has_delegation=has_delegation,
            builds_external_structure=builds_external_structure,
            is_structural_recipe=is_structural_recipe,
            is_chat_macro=is_chat_macro,
            matched_keywords=matched_keywords
        )

    def _apply_decision_tree(self, indicators: ContentIndicators) -> Tuple[AssetType, List[str], str]:
        """
        Apply the 5-step decision tree to classify the asset.

        Returns:
            (asset_type, decision_path, analysis)
        """
        decision_path = []

        # Step 1: The Orchestration Filter
        decision_path.append("Step 1: Orchestration Filter - Does this require multi-step state management or coordination of multiple external platforms?")

        if (indicators.has_multi_platform_chaining or
            (indicators.has_external_apis and indicators.has_state_management and indicators.has_conditional_branching)):
            decision_path.append("YES -> WORKFLOW (requires state management and platform chaining)")
            analysis = (
                "This content involves multi-step orchestration with external API calls and state management. "
                "It requires conditional branching and coordination across platforms. "
                "Therefore, it should be classified as a WORKFLOW and routed to AGENT-006."
            )
            return AssetType.WORKFLOW, decision_path, analysis

        decision_path.append("NO -> Proceed to Step 2")

        # Step 2: The Logic/Resource Filter
        decision_path.append("Step 2: Logic/Resource Filter - Does the asset require external scripts (Python/Bash) or a directory of resources?")

        if indicators.has_scripts_or_code or indicators.has_directory_structure:
            decision_path.append("YES -> SKILL (requires scripts or directory structure)")
            analysis = (
                "This content requires external scripts or a directory of resource files to function. "
                "It represents a modular capability package that Claude can load. "
                "Therefore, it should be classified as a SKILL and routed to AGENT-003."
            )
            return AssetType.SKILL, decision_path, analysis

        decision_path.append("NO -> Proceed to Step 3")

        # Step 3: The Driver Filter (Automaticity)
        decision_path.append("Step 3: Automaticity Filter - Is this asset intended to be auto-triggered by the AI?")

        if indicators.is_auto_triggered and not indicators.is_user_invoked:
            decision_path.append("YES -> SKILL (AI auto-discovers and invokes)")
            analysis = (
                "This content is designed to be automatically discovered and invoked by the AI based on context. "
                "It operates independently without requiring manual user invocation. "
                "Therefore, it should be classified as a SKILL and routed to AGENT-003."
            )
            return AssetType.SKILL, decision_path, analysis

        decision_path.append("NO -> Proceed to Step 4")

        # Step 4: The Delegation/Persona Filter
        decision_path.append("Step 4: Delegation/Persona Filter - Does this require a dedicated role-based worker with specific personality or isolated context?")

        if indicators.has_role_persona or indicators.has_isolated_context or indicators.has_delegation:
            decision_path.append("YES -> AGENT (requires persona, backstory, or isolated context)")
            analysis = (
                "This content defines a role-based persona with specific personality traits or requires isolated context. "
                "It acts as a specialized worker that can delegate to other agents. "
                "Therefore, it should be classified as an AGENT and routed to AGENT-007."
            )
            return AssetType.AGENT, decision_path, analysis

        decision_path.append("NO -> Proceed to Step 5")

        # Step 5: The Blueprint vs. Macro Filter (Tiebreaker)
        decision_path.append("Step 5: Blueprint vs Macro Filter - Is this a generative blueprint for external structure, or a chat macro/shortcut?")

        if indicators.builds_external_structure or indicators.is_structural_recipe:
            decision_path.append("GENERATIVE BLUEPRINT -> GENERATIVE BLUEPRINT (creates flawless external structure)")
            analysis = (
                "This content is a high-precision recipe for generating a flawless external structure like a database schema or UI component. "
                "It focuses on structural output and precision prompting for platforms like Airtable, SQL, or Tailwind. "
                "Therefore, it should be classified as a GENERATIVE BLUEPRINT and routed to AGENT-005."
            )
            return AssetType.GENERATIVE_BLUEPRINT, decision_path, analysis

        if indicators.is_user_invoked or indicators.is_chat_macro:
            decision_path.append("CHAT MACRO/SHORTCUT -> SLASH COMMAND (user manually invokes)")
            analysis = (
                "This content is a manual user shortcut that requires explicit invocation via the / trigger. "
                "It performs a simple, focused action when the user types the command. "
                "Therefore, it should be classified as a SLASH COMMAND and routed to AGENT-004."
            )
            return AssetType.SLASH_COMMAND, decision_path, analysis

        # Default fallback: SLASH COMMAND (simplest type)
        decision_path.append("DEFAULT -> SLASH COMMAND (no specific indicators matched)")
        analysis = (
            "This content does not strongly match indicators for WORKFLOW, SKILL, AGENT, or GENERATIVE BLUEPRINT. "
            "It appears to be a simple, focused action that can be invoked as needed. "
            "Therefore, it should be classified as a SLASH COMMAND and routed to AGENT-004."
        )
        return AssetType.SLASH_COMMAND, decision_path, analysis

    def _apply_tiebreakers(
        self,
        asset_type: AssetType,
        indicators: ContentIndicators,
        content: str
    ) -> AssetType:
        """
        Apply tiebreaker rules when classification is ambiguous.

        Tiebreaker Rules:
        1. Building vs Doing: If it BUILDS a structure -> GENERATIVE BLUEPRINT. If it DOES things -> SKILL.
        2. Human vs AI: If user types / -> SLASH COMMAND. If AI "just knows" -> SKILL.
        3. Capability vs Worker: If you need a "way to do it" -> SKILL. If you need a "person to talk to" -> AGENT.
        """
        content_lower = content.lower()

        # Tiebreaker 1: Building vs Doing
        build_indicators = ["build", "construct", "create", "generate", "schema", "structure"]
        do_indicators = ["update", "modify", "run", "execute", "perform", "process"]

        builds = sum(1 for kw in build_indicators if kw in content_lower)
        does = sum(1 for kw in do_indicators if kw in content_lower)

        if builds > does and asset_type == AssetType.SKILL:
            if indicators.builds_external_structure:
                logger.info("Tiebreaker: Building > Doing, switching SKILL -> GENERATIVE BLUEPRINT")
                return AssetType.GENERATIVE_BLUEPRINT

        # Tiebreaker 2: Human vs AI trigger
        if asset_type == AssetType.SKILL and indicators.is_user_invoked and not indicators.is_auto_triggered:
            logger.info("Tiebreaker: User-invoked, switching SKILL -> SLASH COMMAND")
            return AssetType.SLASH_COMMAND

        # Tiebreaker 3: Capability vs Worker
        capability_words = ["capability", "tool", "function", "utility", "helper"]
        worker_words = ["agent", "assistant", "persona", "character", "worker"]

        capability_count = sum(1 for kw in capability_words if kw in content_lower)
        worker_count = sum(1 for kw in worker_words if kw in content_lower)

        if worker_count > capability_count and asset_type == AssetType.SKILL:
            logger.info("Tiebreaker: Worker > Capability, switching SKILL -> AGENT")
            return AssetType.AGENT

        return asset_type

    async def classify(
        self,
        content: str,
        title: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AssetClassificationResult:
        """
        Classify content into an asset type and determine target generator agent.

        Args:
            content: The content/description to classify
            title: Optional title or name for the asset
            context: Optional additional context (department, user preferences, etc.)

        Returns:
            AssetClassificationResult with classification, target agent, and handover data
        """
        start_time = datetime.now()

        logger.info(
            "AGENT-002 classification started",
            title=title,
            content_length=len(content)
        )

        # Step 1: Extract indicators
        indicators = self._extract_indicators(content, title)

        # Step 2: Apply decision tree
        asset_type, decision_path, analysis = self._apply_decision_tree(indicators)

        # Step 3: Apply tiebreakers
        final_asset_type = self._apply_tiebreakers(asset_type, indicators, content)

        if final_asset_type != asset_type:
            decision_path.append(f"TIEBREAKER APPLIED: {asset_type.value} -> {final_asset_type.value}")
            asset_type = final_asset_type

        # Step 4: Calculate confidence based on matched keywords
        keyword_matches = indicators.matched_keywords.get(asset_type.value, [])
        base_confidence = min(0.95, 0.5 + (len(keyword_matches) * 0.05))

        # Boost confidence if multiple indicators align
        indicator_count = sum([
            indicators.has_external_apis,
            indicators.has_state_management,
            indicators.has_scripts_or_code,
            indicators.has_directory_structure,
            indicators.is_auto_triggered,
            indicators.has_role_persona,
            indicators.builds_external_structure
        ])

        if indicator_count >= 3:
            base_confidence = min(0.98, base_confidence + 0.1)

        # Step 5: Prepare handover data for generator agent
        handover_data = {
            "original_content": content[:2000],  # Truncate for handover
            "title": title,
            "indicators": indicators.model_dump(),
            "context": context or {},
            "classified_at": datetime.now().isoformat(),
            "classifier_agent": "AGENT-002"
        }

        # Get target agent
        target_agent = GENERATOR_AGENTS[asset_type]

        # Update statistics
        self._update_stats(asset_type, base_confidence)

        processing_time = (datetime.now() - start_time).total_seconds()

        logger.info(
            "AGENT-002 classification complete",
            classification=asset_type.value,
            target_agent=target_agent,
            confidence=f"{base_confidence:.2%}",
            processing_time=f"{processing_time:.3f}s"
        )

        return AssetClassificationResult(
            analysis=analysis,
            classification=asset_type,
            target_agent=target_agent,
            confidence=base_confidence,
            handover_data=handover_data,
            decision_path=decision_path
        )

    async def classify_with_llm(
        self,
        content: str,
        title: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AssetClassificationResult:
        """
        Classify using LLM for enhanced accuracy on ambiguous content.
        Falls back to rule-based classification if LLM is unavailable.
        """
        if not self.llm:
            return await self.classify(content, title, context)

        # First get rule-based classification
        rule_result = await self.classify(content, title, context)

        # If high confidence, return rule-based result
        if rule_result.confidence >= 0.85:
            return rule_result

        # Use LLM for low-confidence cases
        try:
            llm_result = await self._llm_classify(content, title, rule_result)
            return llm_result
        except Exception as e:
            logger.warning("LLM classification failed, using rule-based result", error=str(e))
            return rule_result

    async def _llm_classify(
        self,
        content: str,
        title: Optional[str],
        rule_result: AssetClassificationResult
    ) -> AssetClassificationResult:
        """Use LLM for classification with the decision tree prompt"""

        system_prompt = """You are AGENT-002 (The Empire Asset Classifier). Your sole task is to analyze user-provided content and classify it into one of five mutually exclusive AI Asset Types. Once classified, you must route the task to the appropriate Generator Agent (AGENT-003 through AGENT-007).

THE EMPIRE TAXONOMY

1. SKILL (AGENT-003): A modular "capability package" (directory-based).
   - Key Indicator: Requires external scripts (Python/Bash) or a bundle of resource files (examples, docs).
   - Driver: Designed to be discovered and auto-invoked by the AI based on context.

2. SLASH COMMAND (AGENT-004): A manual user macro (single-file).
   - Key Indicator: A simple hotkey (e.g., /lint) for a repetitive task.
   - Driver: Requires explicit human invocation (the / trigger).

3. GENERATIVE BLUEPRINT (AGENT-005): A proven, precision instruction set (prompt library).
   - Key Indicator: Battle-tested instructions that reliably produce flawless external structures (e.g., a 6x6 Airtable base, a SQL schema, a React UI).
   - Output: Proven recipes curated in collaboration with Claude that ensure consistent, flawless results.

4. WORKFLOW (AGENT-006): Multi-step orchestration.
   - Key Indicator: Involves state management, conditional branching (If/Else), or chaining multiple platforms (e.g., Signal -> Airtable -> GitHub).

5. AGENT (AGENT-007): A role-based specialized worker.
   - Key Indicator: Requires a specific persona, backstory, or an isolated context window for secure/parallel execution.

CLASSIFICATION DECISION TREE

1. Orchestration? If it chains multiple platforms or manages state -> WORKFLOW.
2. Scripts/Resources? If it requires code (Python/Bash) or a directory of files -> SKILL.
3. Automaticity? If it should trigger "on its own" without a manual command -> SKILL.
4. Persona? If it requires a specialized role or isolated context -> AGENT.
5. Structural Recipe? If it is a blueprint for building a flawless external asset -> GENERATIVE BLUEPRINT.
6. Catch-all: If it is a manual macro for the current chat -> SLASH COMMAND.

TIEBREAKER RULES

- Building vs. Doing: If it BUILDS a tool/base (Airtable) -> GENERATIVE BLUEPRINT. If it updates/uses that tool -> SKILL.
- Human vs. AI: If the user wants to type / to make it happen -> SLASH COMMAND. If the AI should "just know" -> SKILL.
- Capability vs. Worker: If you need a "way to do it" -> SKILL. If you need a "person to talk to" -> AGENT.

REQUIRED OUTPUT FORMAT

Your response must strictly follow this structure:
- ANALYSIS: [3-sentence logic explaining your decision based on the tree]
- CLASSIFICATION: [Asset Name]
- TARGET AGENT: [AGENT-00X]
- HANDOVER DATA: [A structured summary of the content to be passed to the next agent]"""

        user_prompt = f"""Classify this content:

Title: {title or "Untitled"}

Content:
{content[:3000]}

Previous rule-based classification: {rule_result.classification.value} (confidence: {rule_result.confidence:.2%})

Respond with the required format."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            result_text = response.content.strip()

            # Parse the response
            analysis = ""
            classification = rule_result.classification
            target_agent = rule_result.target_agent

            # Extract ANALYSIS
            if "ANALYSIS:" in result_text:
                analysis_start = result_text.find("ANALYSIS:") + 9
                analysis_end = result_text.find("CLASSIFICATION:")
                if analysis_end > analysis_start:
                    analysis = result_text[analysis_start:analysis_end].strip()

            # Extract CLASSIFICATION
            if "CLASSIFICATION:" in result_text:
                class_start = result_text.find("CLASSIFICATION:") + 15
                class_end = result_text.find("TARGET AGENT:")
                if class_end > class_start:
                    class_str = result_text[class_start:class_end].strip().lower()
                    class_str = class_str.replace(" ", "_").replace("-", "_")

                    # Map to enum (supports both old and new naming)
                    type_map = {
                        "skill": AssetType.SKILL,
                        "slash_command": AssetType.SLASH_COMMAND,
                        "generative_blueprint": AssetType.GENERATIVE_BLUEPRINT,
                        "prompt_template": AssetType.GENERATIVE_BLUEPRINT,  # Legacy alias
                        "workflow": AssetType.WORKFLOW,
                        "agent": AssetType.AGENT
                    }
                    classification = type_map.get(class_str, rule_result.classification)

            # Extract TARGET AGENT
            if "TARGET AGENT:" in result_text:
                agent_start = result_text.find("TARGET AGENT:") + 13
                agent_end = result_text.find("HANDOVER DATA:")
                if agent_end > agent_start:
                    target_agent = result_text[agent_start:agent_end].strip()

            # Update statistics
            confidence = min(0.98, rule_result.confidence + 0.1)
            self._update_stats(classification, confidence)

            logger.info(
                "LLM classification complete",
                classification=classification.value,
                target_agent=target_agent
            )

            return AssetClassificationResult(
                analysis=analysis or rule_result.analysis,
                classification=classification,
                target_agent=target_agent,
                confidence=confidence,
                handover_data=rule_result.handover_data,
                decision_path=rule_result.decision_path + ["LLM enhancement applied"]
            )

        except Exception as e:
            logger.error("LLM classification failed", error=str(e))
            raise

    def _update_stats(self, asset_type: AssetType, confidence: float):
        """Update classification statistics"""
        self.stats["total_classified"] += 1
        self.stats["by_asset_type"][asset_type.value] += 1

        n = self.stats["total_classified"]
        old_avg = self.stats["average_confidence"]
        self.stats["average_confidence"] = old_avg * (n - 1) / n + confidence / n

    def get_stats(self) -> Dict[str, Any]:
        """Get classification statistics"""
        return {
            **self.stats,
            "agent_id": "AGENT-002",
            "agent_name": "Empire Asset Classifier"
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_asset_classifier(use_llm: bool = True) -> AssetClassifierAgent:
    """Factory function to create AGENT-002"""
    return AssetClassifierAgent(use_llm_enhancement=use_llm)


async def classify_asset(
    content: str,
    title: Optional[str] = None,
    use_llm: bool = True
) -> AssetClassificationResult:
    """Convenience function for asset classification"""
    classifier = create_asset_classifier(use_llm)
    return await classifier.classify(content, title)


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        """Test AGENT-002 Asset Classifier"""
        classifier = create_asset_classifier(use_llm=False)  # Rule-based only for testing

        test_cases = [
            {
                "title": "Airtable Project Tracker Builder",
                "content": """
                Build a flawless Airtable base for project management with:
                - 6 tables: Projects, Tasks, Team Members, Milestones, Documents, Comments
                - 12 linked fields connecting all tables
                - Automation: When task status changes to "Complete", update project progress
                - Views: Kanban, Calendar, Gantt-style timeline
                The schema should be precise with no hallucinated fields.
                """
            },
            {
                "title": "/follow-up",
                "content": """
                A quick shortcut to draft a follow-up email.
                User types /follow-up and Claude generates a professional follow-up.
                Simple, one-action macro.
                """
            },
            {
                "title": "Research Agent",
                "content": """
                Create an agent with the following:
                - Role: Senior Research Analyst
                - Backstory: Expert at finding and synthesizing information from multiple sources
                - Model: Claude Opus for complex reasoning
                - Tools: web_search, document_reader
                - Can delegate to: fact-checker-agent, writer-agent
                Works in isolated context for parallel research tasks.
                """
            },
            {
                "title": "Lead Qualification Workflow",
                "content": """
                Multi-step workflow for lead qualification:
                1. Signal webhook receives new contact
                2. Enrich lead data via Clearbit API
                3. Score lead based on criteria (if score > 80, route to sales)
                4. Update Airtable CRM with lead status
                5. If qualified, create GitHub issue for sales follow-up
                6. Send Slack notification to sales team
                Handles state and conditional branching.
                """
            },
            {
                "title": "Code Review Skill",
                "content": """
                A comprehensive code review capability with:
                - Directory structure with checklist templates
                - Python scripts for automated linting
                - Example reviews for reference
                - Best practices documentation
                Claude should auto-detect when to use this during code discussions.
                """
            }
        ]

        print("\n" + "="*70)
        print("AGENT-002 ASSET CLASSIFIER TEST")
        print("="*70)

        for i, case in enumerate(test_cases, 1):
            print(f"\n--- Test Case {i}: {case['title']} ---")

            result = await classifier.classify(
                content=case["content"],
                title=case["title"]
            )

            print(f"Classification: {result.classification.value}")
            print(f"Target Agent: {result.target_agent}")
            print(f"Confidence: {result.confidence:.2%}")
            print(f"Analysis: {result.analysis}")
            print(f"Decision Path:")
            for step in result.decision_path:
                print(f"  - {step}")

        print(f"\n=== Statistics ===")
        print(json.dumps(classifier.get_stats(), indent=2))

    asyncio.run(test())
