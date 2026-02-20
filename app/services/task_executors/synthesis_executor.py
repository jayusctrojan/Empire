"""
Empire v7.3 - Synthesis Executor (Task 97)

Combines retrieved artifacts into coherent research findings using AI synthesis.
Handles both synthesis and fact-checking task types.

Features:
- AI-powered synthesis using Claude
- Multi-source artifact combination
- Quality gates for synthesis validation
- Confidence scoring
- Source citation tracking

Author: Claude Code
Date: 2025-01-10
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

import structlog
from anthropic import AsyncAnthropic
from supabase import Client

from app.core.supabase_client import get_supabase_client
from app.services.task_harness import TaskExecutor
from app.models.research_project import TaskType, ArtifactType

logger = structlog.get_logger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class SynthesisConfig:
    """Configuration for synthesis operations"""
    # Model settings
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 0.2

    # Quality thresholds
    min_confidence_score: float = 0.7
    min_key_findings: int = 2
    min_analysis_length: int = 300
    min_source_citations: int = 1

    # Input limits
    max_artifacts: int = 20
    max_content_length: int = 50000  # chars


class SynthesisQualityError(Exception):
    """Raised when synthesis fails quality gate"""
    pass


# ==============================================================================
# Prompts
# ==============================================================================

SYNTHESIS_SYSTEM_PROMPT = """You are a research synthesis expert. Your task is to analyze multiple source documents and synthesize coherent findings.

Guidelines:
1. Identify key themes and patterns across sources
2. Maintain factual accuracy - don't invent information
3. Cite sources clearly using [Source N] format
4. Provide confidence levels for claims
5. Highlight areas of consensus and disagreement
6. Structure findings logically

Always respond with valid JSON."""


def get_synthesis_prompt(query: str, artifacts: List[Dict], task_config: Dict) -> str:
    """Generate the synthesis prompt from artifacts"""
    # Format artifacts as numbered sources
    sources = []
    for i, artifact in enumerate(artifacts, 1):
        content = artifact.get("content", "")
        title = artifact.get("title", f"Source {i}")
        source_ref = artifact.get("source_reference", "")

        # Truncate if too long
        if len(content) > 3000:
            content = content[:3000] + "...[truncated]"

        sources.append(f"[Source {i}] {title}\nReference: {source_ref}\n{content}")

    context = "\n\n---\n\n".join(sources)

    focus_areas = task_config.get("focus_areas", [])
    focus_text = f"\nFocus areas: {', '.join(focus_areas)}" if focus_areas else ""

    return f"""Research Query: {query}{focus_text}

Sources to synthesize:

{context}

Synthesize these sources into coherent research findings. Structure your response as JSON:

{{
    "key_findings": [
        {{
            "finding": "Main finding statement",
            "evidence": "Supporting evidence from sources",
            "sources": [1, 2],
            "confidence": 0.9
        }}
    ],
    "detailed_analysis": "Comprehensive analysis connecting all findings...",
    "themes": ["theme1", "theme2"],
    "source_citations": [
        {{
            "source_num": 1,
            "title": "Source title",
            "key_contribution": "What this source contributed"
        }}
    ],
    "gaps_and_limitations": "Any gaps in the evidence or limitations of the analysis",
    "confidence_score": 0.85
}}"""


FACT_CHECK_SYSTEM_PROMPT = """You are a fact-checking expert. Your task is to verify claims against available evidence.

Guidelines:
1. Evaluate each claim against the provided evidence
2. Assign confidence scores based on evidence strength
3. Identify claims that lack supporting evidence
4. Note any contradictions between sources
5. Provide clear verification status for each claim

Always respond with valid JSON."""


def get_fact_check_prompt(claims: List[str], artifacts: List[Dict]) -> str:
    """Generate fact-checking prompt"""
    sources = []
    for i, artifact in enumerate(artifacts, 1):
        content = artifact.get("content", "")[:2000]
        sources.append(f"[Evidence {i}]: {content}")

    evidence = "\n\n".join(sources)
    claims_text = "\n".join(f"{i+1}. {claim}" for i, claim in enumerate(claims))

    return f"""Claims to verify:
{claims_text}

Available Evidence:
{evidence}

Verify each claim and respond with JSON:

{{
    "verified_claims": [
        {{
            "claim": "The original claim",
            "status": "verified|partially_verified|unverified|contradicted",
            "confidence": 0.9,
            "supporting_evidence": [1, 2],
            "contradicting_evidence": [],
            "notes": "Any relevant notes"
        }}
    ],
    "overall_confidence": 0.85,
    "summary": "Overall fact-check summary"
}}"""


# ==============================================================================
# Synthesis Executor
# ==============================================================================

class SynthesisExecutor(TaskExecutor):
    """
    Executor for synthesis and fact-checking tasks.

    Uses Claude to:
    - Synthesize findings from multiple retrieved artifacts
    - Verify claims against evidence
    - Generate structured research insights
    """

    def __init__(
        self,
        supabase: Client,
        anthropic: Optional[AsyncAnthropic] = None,
        config: Optional[SynthesisConfig] = None
    ):
        self.supabase = supabase
        self.anthropic = anthropic or AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.config = config or SynthesisConfig()

    @property
    def supported_types(self) -> List[str]:
        """Task types this executor supports"""
        return [
            TaskType.SYNTHESIS.value,
            TaskType.FACT_CHECK.value,
        ]

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a synthesis or fact-check task.

        Args:
            task: Task data from plan_tasks table

        Returns:
            Dict with success, summary, data, and artifacts
        """
        task_type = task["task_type"]

        logger.info(
            "Executing synthesis task",
            task_id=task["id"],
            task_type=task_type,
            task_key=task["task_key"]
        )

        try:
            if task_type == TaskType.SYNTHESIS.value:
                return await self.execute_synthesis(task)
            elif task_type == TaskType.FACT_CHECK.value:
                return await self.execute_fact_check(task)
            else:
                raise ValueError(f"Unsupported task type: {task_type}")

        except Exception as e:
            logger.error(
                "Synthesis task failed",
                task_id=task["id"],
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "summary": f"Synthesis failed: {str(e)}",
                "data": {},
                "artifacts": []
            }

    # ==========================================================================
    # Synthesis
    # ==========================================================================

    async def execute_synthesis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute synthesis task - combine artifacts into findings.

        Args:
            task: Task data with query, config, and dependencies

        Returns:
            Dict with synthesized findings
        """
        job_id = task["job_id"]
        query = task["query"]
        config = task.get("config", {})
        depends_on = task.get("depends_on", [])

        logger.info(
            "Executing synthesis",
            task_key=task["task_key"],
            dependency_count=len(depends_on)
        )

        # Get input artifacts from dependent tasks
        artifacts = await self.get_input_artifacts(job_id, depends_on)

        if not artifacts:
            return {
                "success": False,
                "error": "No input artifacts found from dependent tasks",
                "summary": "Synthesis failed: no input data",
                "data": {},
                "artifacts": []
            }

        # Perform AI synthesis
        synthesis = await self.synthesize_findings(query, artifacts, config)

        # Apply quality gate
        passed, issues = self.apply_quality_gate(synthesis)

        if not passed:
            logger.warning(
                "Synthesis quality gate failed",
                issues=issues,
                confidence=synthesis.get("confidence_score")
            )
            # Allow partial success with lower confidence
            if synthesis.get("confidence_score", 0) < 0.3:
                return {
                    "success": False,
                    "error": f"Quality gate failed: {', '.join(issues)}",
                    "summary": "Synthesis quality insufficient",
                    "data": synthesis,
                    "artifacts": []
                }

        # Prepare artifact for storage
        synthesis_artifact = {
            "type": ArtifactType.SYNTHESIS_FINDING.value,
            "title": f"Synthesis: {task['task_title']}",
            "content": synthesis.get("detailed_analysis", ""),
            "metadata": {
                "key_findings": synthesis.get("key_findings", []),
                "themes": synthesis.get("themes", []),
                "source_count": len(artifacts),
                "gaps": synthesis.get("gaps_and_limitations")
            },
            "confidence": synthesis.get("confidence_score", 0.5)
        }

        return {
            "success": True,
            "summary": f"Synthesized {len(synthesis.get('key_findings', []))} findings from {len(artifacts)} sources",
            "data": {
                "finding_count": len(synthesis.get("key_findings", [])),
                "themes": synthesis.get("themes", []),
                "confidence": synthesis.get("confidence_score"),
                "source_count": len(artifacts),
                "quality_issues": issues if issues else None
            },
            "artifacts": [synthesis_artifact]
        }

    async def synthesize_findings(
        self,
        query: str,
        artifacts: List[Dict[str, Any]],
        task_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use Claude to synthesize findings from artifacts.

        Args:
            query: The research query
            artifacts: List of artifacts to synthesize
            task_config: Task-specific configuration

        Returns:
            Synthesized findings as structured dict
        """
        # Limit artifacts if too many
        if len(artifacts) > self.config.max_artifacts:
            artifacts = artifacts[:self.config.max_artifacts]
            logger.info(f"Truncated artifacts to {self.config.max_artifacts}")

        prompt = get_synthesis_prompt(query, artifacts, task_config)

        try:
            response = await self.anthropic.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=SYNTHESIS_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text

            # Parse JSON response
            synthesis = self._parse_json_response(response_text)

            logger.info(
                "Synthesis complete",
                findings=len(synthesis.get("key_findings", [])),
                confidence=synthesis.get("confidence_score")
            )

            return synthesis

        except Exception as e:
            logger.error(f"Synthesis API call failed: {e}")
            return {
                "key_findings": [],
                "detailed_analysis": f"Synthesis failed: {str(e)}",
                "themes": [],
                "source_citations": [],
                "confidence_score": 0.0,
                "error": str(e)
            }

    # ==========================================================================
    # Fact Checking
    # ==========================================================================

    async def execute_fact_check(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute fact-checking task - verify claims against evidence.

        Args:
            task: Task data with claims to verify

        Returns:
            Dict with verification results
        """
        job_id = task["job_id"]
        query = task["query"]
        config = task.get("config", {})
        depends_on = task.get("depends_on", [])

        # Extract claims from query or config
        claims = config.get("claims", [query])

        # Get evidence artifacts
        artifacts = await self.get_input_artifacts(job_id, depends_on)

        if not artifacts:
            return {
                "success": False,
                "error": "No evidence artifacts found",
                "summary": "Fact-check failed: no evidence",
                "data": {},
                "artifacts": []
            }

        # Perform fact checking
        fact_check = await self.verify_claims(claims, artifacts)

        # Prepare artifact
        fact_check_artifact = {
            "type": ArtifactType.FACT_CHECK_RESULT.value,
            "title": f"Fact Check: {task['task_title']}",
            "content": fact_check.get("summary", ""),
            "metadata": {
                "verified_claims": fact_check.get("verified_claims", []),
                "claim_count": len(claims)
            },
            "confidence": fact_check.get("overall_confidence", 0.5)
        }

        # Count verification statuses
        claims_result = fact_check.get("verified_claims", [])
        verified = sum(1 for c in claims_result if c.get("status") == "verified")
        partial = sum(1 for c in claims_result if c.get("status") == "partially_verified")

        return {
            "success": True,
            "summary": f"Verified {verified}/{len(claims)} claims ({partial} partial)",
            "data": {
                "total_claims": len(claims),
                "verified": verified,
                "partially_verified": partial,
                "overall_confidence": fact_check.get("overall_confidence"),
                "claims": claims_result[:5]  # Preview
            },
            "artifacts": [fact_check_artifact]
        }

    async def verify_claims(
        self,
        claims: List[str],
        artifacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use Claude to verify claims against evidence.

        Args:
            claims: List of claims to verify
            artifacts: Evidence artifacts

        Returns:
            Verification results
        """
        prompt = get_fact_check_prompt(claims, artifacts)

        try:
            response = await self.anthropic.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=0.1,  # Lower temperature for fact-checking
                system=FACT_CHECK_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text
            return self._parse_json_response(response_text)

        except Exception as e:
            logger.error(f"Fact-check API call failed: {e}")
            return {
                "verified_claims": [],
                "overall_confidence": 0.0,
                "summary": f"Fact-check failed: {str(e)}",
                "error": str(e)
            }

    # ==========================================================================
    # Artifact Retrieval
    # ==========================================================================

    async def get_input_artifacts(
        self,
        job_id: int,
        dependency_keys: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve artifacts from dependent tasks.

        Args:
            job_id: The research job ID
            dependency_keys: List of task_keys this task depends on

        Returns:
            List of artifacts from dependent tasks
        """
        if not dependency_keys:
            # If no specific dependencies, get all retrieval artifacts for the job
            result = self.supabase.table("research_artifacts").select("*").eq(
                "job_id", job_id
            ).in_(
                "artifact_type",
                [
                    ArtifactType.RETRIEVED_CHUNK.value,
                    ArtifactType.QUERY_RESULT.value,
                    ArtifactType.GRAPH_PATH.value,
                    ArtifactType.API_RESPONSE.value
                ]
            ).order("created_at").execute()

            return result.data or []

        # Get task IDs for dependency keys
        task_result = self.supabase.table("plan_tasks").select("id").eq(
            "job_id", job_id
        ).in_("task_key", dependency_keys).execute()

        task_ids = [t["id"] for t in (task_result.data or [])]

        if not task_ids:
            return []

        # Get artifacts for those tasks
        result = self.supabase.table("research_artifacts").select("*").in_(
            "task_id", task_ids
        ).order("created_at").execute()

        artifacts = result.data or []

        logger.info(
            "Retrieved input artifacts",
            dependency_count=len(dependency_keys),
            artifact_count=len(artifacts)
        )

        return artifacts

    # ==========================================================================
    # Quality Gate
    # ==========================================================================

    def apply_quality_gate(self, synthesis: Dict[str, Any]) -> tuple:
        """
        Apply quality gate to synthesis results.

        Args:
            synthesis: The synthesis results

        Returns:
            Tuple of (passed, list of issues)
        """
        issues = []

        # Check confidence score
        confidence = synthesis.get("confidence_score", 0)
        if confidence < self.config.min_confidence_score:
            issues.append(f"Low confidence: {confidence:.2f} < {self.config.min_confidence_score}")

        # Check key findings
        findings = synthesis.get("key_findings", [])
        if len(findings) < self.config.min_key_findings:
            issues.append(f"Too few findings: {len(findings)} < {self.config.min_key_findings}")

        # Check analysis length
        analysis = synthesis.get("detailed_analysis", "")
        if len(analysis) < self.config.min_analysis_length:
            issues.append(f"Analysis too short: {len(analysis)} < {self.config.min_analysis_length}")

        # Check source citations
        citations = synthesis.get("source_citations", [])
        if len(citations) < self.config.min_source_citations:
            issues.append(f"Too few citations: {len(citations)} < {self.config.min_source_citations}")

        passed = len(issues) == 0

        return passed, issues

    # ==========================================================================
    # Helpers
    # ==========================================================================

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from Claude response, handling code blocks"""
        # Try to extract JSON from code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            # Return a minimal valid structure
            return {
                "key_findings": [],
                "detailed_analysis": text,
                "themes": [],
                "source_citations": [],
                "confidence_score": 0.5,
                "parse_error": str(e)
            }


# ==============================================================================
# Service Factory
# ==============================================================================

_executor_instance: Optional[SynthesisExecutor] = None


def get_synthesis_executor() -> SynthesisExecutor:
    """Get or create synthesis executor singleton"""
    global _executor_instance
    if _executor_instance is None:
        supabase = get_supabase_client()
        _executor_instance = SynthesisExecutor(supabase)
    return _executor_instance
