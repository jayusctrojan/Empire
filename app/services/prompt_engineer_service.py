"""
Empire v7.3 - Prompt Engineer Service
Phase 1: Multi-Model Quality Pipeline

First stage of the Sonnet 4.5 bookend pipeline. Analyzes user queries
to detect intent, desired output format, and produces enriched prompts
with explicit instructions for the reasoning engine (Kimi K2.5).

Pipeline: PromptEngineer(Sonnet) → Kimi(reasoning) → OutputArchitect(Sonnet)
"""

import json
import structlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.services.llm_client import LLMClient, get_llm_client

logger = structlog.get_logger(__name__)


# ============================================================================
# Enums & Data Models
# ============================================================================

class QueryIntent(str, Enum):
    """Detected intent of the user's query."""
    FACTUAL = "factual"          # Lookup / fact-finding
    ANALYTICAL = "analytical"    # Comparison, analysis, synthesis
    CREATIVE = "creative"        # Brainstorming, ideation
    PROCEDURAL = "procedural"    # How-to, step-by-step
    DOCUMENT = "document"        # Request to generate a document/artifact


class OutputFormat(str, Enum):
    """Desired output format."""
    TEXT = "text"                  # Plain prose response
    TABLE = "table"               # Tabular data
    REPORT = "report"             # Structured report with sections
    SPREADSHEET = "spreadsheet"   # Tabular data → XLSX artifact
    PRESENTATION = "presentation" # Slide deck → PPTX artifact
    DOCUMENT = "document"         # Formal document → DOCX artifact


class PipelineMode(str, Enum):
    """Tracks which pipeline path was taken (for cost/quality analytics)."""
    FULL = "full"                                # All 3 models
    NO_PROMPT_ENGINEER = "no_prompt_engineer"     # Sonnet #1 failed
    NO_OUTPUT_ARCHITECT = "no_output_architect"   # Sonnet #2 failed
    DIRECT = "direct"                            # Both Sonnet calls failed


@dataclass
class StructuredPrompt:
    """Output of the Prompt Engineer — enriched query + metadata."""
    original_query: str
    enriched_query: str
    intent: QueryIntent
    desired_format: OutputFormat
    scope: str = ""                        # What to focus on
    constraints: List[str] = field(default_factory=list)  # What to avoid
    output_instructions: str = ""          # Instructions for the reasoning engine
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "originalQuery": self.original_query,
            "enrichedQuery": self.enriched_query,
            "intent": self.intent.value,
            "desiredFormat": self.desired_format.value,
            "scope": self.scope,
            "constraints": self.constraints,
            "outputInstructions": self.output_instructions,
            "metadata": self.metadata,
        }


# ============================================================================
# System Prompt
# ============================================================================

PROMPT_ENGINEER_SYSTEM = """You are a Prompt Engineer that analyzes user queries and produces structured instructions for a reasoning AI.

Your job:
1. Detect the user's intent (factual, analytical, creative, procedural, document)
2. Detect the desired output format (text, table, report, spreadsheet, presentation, document)
3. Rewrite the query to be more precise and complete
4. Write specific instructions for the reasoning engine

Respond ONLY with valid JSON matching this schema:
{
  "enriched_query": "string - the improved, more precise query",
  "intent": "factual|analytical|creative|procedural|document",
  "desired_format": "text|table|report|spreadsheet|presentation|document",
  "scope": "string - what the reasoning engine should focus on",
  "constraints": ["string - things to avoid or limitations"],
  "output_instructions": "string - specific formatting/structure instructions for the reasoning engine"
}

Rules:
- If the user asks to "create", "generate", "make", "build" a document/spreadsheet/presentation → intent=document
- If asking for comparison or analysis → intent=analytical
- If asking "how to" or steps → intent=procedural
- Default to intent=factual for information queries
- Default to desired_format=text unless the query clearly implies another format
- Keep enriched_query under 500 characters
- Keep output_instructions actionable and specific"""


# ============================================================================
# Service
# ============================================================================

class PromptEngineerService:
    """
    Analyzes user queries and produces enriched, structured prompts.
    Uses Sonnet 4.5 (~200-400 output tokens, ~1-2s latency).
    """

    MODEL = "claude-sonnet-4-5-20250929"
    MAX_TOKENS = 500
    TEMPERATURE = 0.2

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client("anthropic")

    async def engineer_prompt(
        self,
        query: str,
        conversation_context: Optional[str] = None,
    ) -> StructuredPrompt:
        """
        Analyze a user query and produce an enriched structured prompt.

        Args:
            query: The raw user query
            conversation_context: Optional summary of prior conversation

        Returns:
            StructuredPrompt with intent, format, enriched query, and instructions

        Raises:
            Exception if LLM call fails (caller should handle for graceful degradation)
        """
        user_message = query
        if conversation_context:
            user_message = f"Conversation context: {conversation_context}\n\nCurrent query: {query}"

        raw_response = await self.llm_client.generate(
            system=PROMPT_ENGINEER_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE,
            model=self.MODEL,
        )

        return self._parse_response(query, raw_response)

    def _parse_response(self, original_query: str, raw_response: str) -> StructuredPrompt:
        """Parse JSON response from Sonnet, with fallback for malformed output."""
        try:
            # Strip markdown code fences if present
            text = raw_response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

            data = json.loads(text)

            return StructuredPrompt(
                original_query=original_query,
                enriched_query=data.get("enriched_query", original_query),
                intent=QueryIntent(data.get("intent", "factual")),
                desired_format=OutputFormat(data.get("desired_format", "text")),
                scope=data.get("scope", ""),
                constraints=data.get("constraints", []),
                output_instructions=data.get("output_instructions", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(
                "Prompt engineer JSON parse failed, using defaults",
                error=str(e),
                raw_response=raw_response[:200],
            )
            return self._fallback_prompt(original_query)

    @staticmethod
    def _fallback_prompt(query: str) -> StructuredPrompt:
        """Produce a reasonable default when parsing fails."""
        query_lower = query.lower()

        # Simple heuristic intent detection
        if any(kw in query_lower for kw in ("create", "generate", "make", "build", "write")):
            intent = QueryIntent.DOCUMENT
        elif any(kw in query_lower for kw in ("compare", "analyze", "analysis", "evaluate")):
            intent = QueryIntent.ANALYTICAL
        elif any(kw in query_lower for kw in ("how to", "steps", "guide", "instructions")):
            intent = QueryIntent.PROCEDURAL
        else:
            intent = QueryIntent.FACTUAL

        # Simple heuristic format detection
        if any(kw in query_lower for kw in ("spreadsheet", "xlsx", "excel", "table")):
            fmt = OutputFormat.SPREADSHEET
        elif any(kw in query_lower for kw in ("presentation", "pptx", "slides", "deck")):
            fmt = OutputFormat.PRESENTATION
        elif any(kw in query_lower for kw in ("report", "document", "docx", "paper")):
            fmt = OutputFormat.DOCUMENT
        else:
            fmt = OutputFormat.TEXT

        return StructuredPrompt(
            original_query=query,
            enriched_query=query,
            intent=intent,
            desired_format=fmt,
            output_instructions="Provide a thorough, well-structured response with citations.",
        )


# ============================================================================
# Singleton
# ============================================================================

_service: Optional[PromptEngineerService] = None


def get_prompt_engineer_service() -> PromptEngineerService:
    global _service
    if _service is None:
        _service = PromptEngineerService()
    return _service
