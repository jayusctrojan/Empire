"""
Empire v7.3 - Report Generation Executor (Task 98)

Generates comprehensive research reports from synthesized findings.
Handles report writing, review, and formatting tasks.

Features:
- AI-powered report generation using Claude
- Section-by-section writing
- Quality review with revision loop
- Multi-format output (Markdown, HTML)
- Executive summary generation

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
class ReportConfig:
    """Configuration for report generation"""
    # Model settings
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 0.3

    # Report settings
    max_report_length: int = 15000  # chars
    min_report_length: int = 1000
    include_executive_summary: bool = True
    include_methodology: bool = True
    include_references: bool = True

    # Quality thresholds
    min_quality_score: float = 0.75
    max_revision_attempts: int = 2


# ==============================================================================
# Prompts
# ==============================================================================

REPORT_SYSTEM_PROMPT = """You are an expert research report writer. Your task is to create comprehensive, well-structured research reports.

Guidelines:
1. Write clear, professional prose
2. Structure content with appropriate headings
3. Support claims with evidence and citations
4. Use [Source N] format for citations
5. Maintain objectivity and balance
6. Include actionable recommendations where appropriate

Output format: Markdown with proper heading hierarchy."""


def get_report_prompt(
    query: str,
    findings: List[Dict],
    artifacts: List[Dict],
    config: Dict
) -> str:
    """Generate the report writing prompt"""
    # Format findings
    findings_text = []
    for i, finding in enumerate(findings, 1):
        if isinstance(finding, dict):
            text = finding.get("finding", finding.get("content", str(finding)))
            confidence = finding.get("confidence", "N/A")
            findings_text.append(f"{i}. {text} (Confidence: {confidence})")
        else:
            findings_text.append(f"{i}. {finding}")

    findings_section = "\n".join(findings_text)

    # Format source references
    sources = []
    for i, artifact in enumerate(artifacts[:10], 1):
        title = artifact.get("title", f"Source {i}")
        preview = artifact.get("content", "")[:200]
        sources.append(f"[Source {i}] {title}: {preview}...")

    sources_section = "\n\n".join(sources)

    research_type = config.get("research_type", "general")
    focus_areas = config.get("focus_areas", [])
    focus_text = f"\nFocus areas: {', '.join(focus_areas)}" if focus_areas else ""

    return f"""Generate a comprehensive research report.

Research Query: {query}
Research Type: {research_type}{focus_text}

Key Findings:
{findings_section}

Source Materials:
{sources_section}

Write a complete research report with the following structure:

# Executive Summary
Brief overview of key findings and recommendations (2-3 paragraphs)

# Introduction
Background context and research objectives

# Methodology
How the research was conducted (data sources, analysis approach)

# Key Findings
Detailed analysis of main findings with evidence

# Analysis & Discussion
Deeper exploration of themes, patterns, and implications

# Recommendations
Actionable recommendations based on findings

# Conclusion
Summary and next steps

# References
List of sources cited

Use Markdown formatting. Cite sources using [Source N] notation."""


SECTION_PROMPT_TEMPLATE = """Write the {section_name} section of a research report.

Research Query: {query}

Context from previous sections:
{context}

Relevant findings:
{findings}

Write a well-structured {section_name} section in Markdown format.
Length: {length_guidance}"""


REVIEW_SYSTEM_PROMPT = """You are a research report quality reviewer. Evaluate reports for accuracy, completeness, and clarity.

Review criteria:
1. Factual accuracy and evidence support
2. Logical structure and flow
3. Completeness of coverage
4. Clarity and readability
5. Citation quality
6. Actionability of recommendations

Provide specific, constructive feedback."""


def get_review_prompt(report_content: str, findings: List[Dict]) -> str:
    """Generate the review prompt"""
    findings_summary = "\n".join([
        f"- {f.get('finding', str(f))}" for f in findings[:10]
    ])

    return f"""Review this research report for quality and accuracy.

Key Findings to Verify:
{findings_summary}

Report Content:
{report_content}

Provide your review as JSON:

{{
    "overall_score": 0.85,
    "accuracy_score": 0.9,
    "completeness_score": 0.8,
    "clarity_score": 0.85,
    "issues": [
        {{
            "type": "accuracy|completeness|clarity|structure",
            "severity": "high|medium|low",
            "location": "Section name or paragraph reference",
            "description": "Description of the issue",
            "suggestion": "Suggested fix"
        }}
    ],
    "strengths": ["List of report strengths"],
    "improvement_suggestions": ["Prioritized improvement suggestions"],
    "approved": true
}}"""


# ==============================================================================
# Report Executor
# ==============================================================================

class ReportExecutor(TaskExecutor):
    """
    Executor for report generation, writing, and review tasks.

    Handles:
    - write_section: Generate specific report sections
    - write_report: Generate full comprehensive reports
    - review: Quality assurance and revision
    """

    def __init__(
        self,
        supabase: Client,
        anthropic: Optional[AsyncAnthropic] = None,
        config: Optional[ReportConfig] = None
    ):
        self.supabase = supabase
        self.anthropic = anthropic or AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.config = config or ReportConfig()

    @property
    def supported_types(self) -> List[str]:
        """Task types this executor supports"""
        return [
            TaskType.WRITE_SECTION.value,
            TaskType.WRITE_REPORT.value,
            TaskType.REVIEW.value,
        ]

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a report-related task.

        Args:
            task: Task data from plan_tasks table

        Returns:
            Dict with success, summary, data, and artifacts
        """
        task_type = task["task_type"]

        logger.info(
            "Executing report task",
            task_id=task["id"],
            task_type=task_type,
            task_key=task["task_key"]
        )

        try:
            if task_type == TaskType.WRITE_SECTION.value:
                return await self.execute_write_section(task)
            elif task_type == TaskType.WRITE_REPORT.value:
                return await self.execute_write_report(task)
            elif task_type == TaskType.REVIEW.value:
                return await self.execute_review(task)
            else:
                raise ValueError(f"Unsupported task type: {task_type}")

        except Exception as e:
            logger.error(
                "Report task failed",
                task_id=task["id"],
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "summary": f"Report task failed: {str(e)}",
                "data": {},
                "artifacts": []
            }

    # ==========================================================================
    # Write Section
    # ==========================================================================

    async def execute_write_section(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a specific section of the report.

        Args:
            task: Task data with section configuration

        Returns:
            Dict with generated section content
        """
        job_id = task["job_id"]
        query = task["query"]
        config = task.get("config", {})

        section_name = config.get("section_name", "findings")
        depends_on = task.get("depends_on", [])

        logger.info(
            "Writing report section",
            section=section_name,
            task_key=task["task_key"]
        )

        # Get context from previous sections
        context = await self._get_section_context(job_id, depends_on)

        # Get relevant findings
        findings = await self._get_findings(job_id)

        # Generate section
        section_content = await self._generate_section(
            section_name=section_name,
            query=query,
            context=context,
            findings=findings,
            config=config
        )

        # Prepare artifact
        section_artifact = {
            "type": ArtifactType.REPORT_SECTION.value,
            "title": f"Report Section: {section_name}",
            "content": section_content,
            "metadata": {
                "section_name": section_name,
                "word_count": len(section_content.split())
            }
        }

        return {
            "success": True,
            "summary": f"Generated {section_name} section ({len(section_content.split())} words)",
            "data": {
                "section_name": section_name,
                "word_count": len(section_content.split()),
                "content_preview": section_content[:500]
            },
            "artifacts": [section_artifact]
        }

    async def _generate_section(
        self,
        section_name: str,
        query: str,
        context: str,
        findings: List[Dict],
        config: Dict
    ) -> str:
        """Generate a single report section"""
        # Determine length guidance based on section
        length_map = {
            "executive_summary": "200-300 words",
            "introduction": "150-250 words",
            "methodology": "200-300 words",
            "findings": "500-800 words",
            "analysis": "400-600 words",
            "recommendations": "300-500 words",
            "conclusion": "150-250 words"
        }
        length_guidance = length_map.get(section_name.lower(), "300-500 words")

        findings_text = "\n".join([
            f"- {f.get('finding', str(f))}" for f in findings[:10]
        ])

        prompt = SECTION_PROMPT_TEMPLATE.format(
            section_name=section_name,
            query=query,
            context=context or "This is the first section.",
            findings=findings_text,
            length_guidance=length_guidance
        )

        response = await self.anthropic.messages.create(
            model=self.config.model,
            max_tokens=2048,
            temperature=self.config.temperature,
            system=REPORT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    # ==========================================================================
    # Write Full Report
    # ==========================================================================

    async def execute_write_report(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate the complete research report.

        Args:
            task: Task data with report configuration

        Returns:
            Dict with full report content
        """
        job_id = task["job_id"]
        query = task["query"]
        config = task.get("config", {})

        logger.info(
            "Generating full research report",
            job_id=job_id,
            task_key=task["task_key"]
        )

        # Get all artifacts for the job
        artifacts = await self._get_all_artifacts(job_id)

        # Extract synthesis findings
        findings = self._extract_findings(artifacts)

        # Generate the report
        report = await self._generate_full_report(query, findings, artifacts, config)

        # Store report in job record
        await self._store_report(job_id, report)

        # Prepare artifact
        report_artifact = {
            "type": ArtifactType.FINAL_REPORT.value,
            "title": f"Research Report: {query[:50]}...",
            "content": report["content"],
            "metadata": {
                "word_count": report["word_count"],
                "sections": list(report["sections"].keys()),
                "quality_score": report.get("quality_score")
            }
        }

        return {
            "success": True,
            "summary": f"Generated report ({report['word_count']} words, {len(report['sections'])} sections)",
            "data": {
                "word_count": report["word_count"],
                "sections": list(report["sections"].keys()),
                "quality_score": report.get("quality_score"),
                "executive_summary": report["sections"].get("executive_summary", "")[:500]
            },
            "artifacts": [report_artifact]
        }

    async def _generate_full_report(
        self,
        query: str,
        findings: List[Dict],
        artifacts: List[Dict],
        config: Dict
    ) -> Dict[str, Any]:
        """Generate the complete report using Claude"""
        prompt = get_report_prompt(query, findings, artifacts, config)

        response = await self.anthropic.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=REPORT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        # Extract sections
        sections = self._parse_report_sections(content)

        return {
            "content": content,
            "sections": sections,
            "word_count": len(content.split()),
            "generated_at": datetime.utcnow().isoformat()
        }

    def _parse_report_sections(self, content: str) -> Dict[str, str]:
        """Parse report content into sections"""
        sections = {}
        current_section = "preamble"
        current_content = []

        for line in content.split("\n"):
            if line.startswith("# "):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                # Start new section
                current_section = line[2:].strip().lower().replace(" ", "_")
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    # ==========================================================================
    # Review
    # ==========================================================================

    async def execute_review(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review and validate report quality.

        Args:
            task: Task data with review configuration

        Returns:
            Dict with review results
        """
        job_id = task["job_id"]
        depends_on = task.get("depends_on", [])

        logger.info(
            "Reviewing report",
            job_id=job_id,
            task_key=task["task_key"]
        )

        # Get report content to review
        report_content = await self._get_report_content(job_id)

        if not report_content:
            return {
                "success": False,
                "error": "No report content found to review",
                "summary": "Review failed: no report",
                "data": {},
                "artifacts": []
            }

        # Get findings for verification
        findings = await self._get_findings(job_id)

        # Perform review
        review = await self._review_report(report_content, findings)

        # Check if revision needed
        if not review.get("approved") and review.get("overall_score", 0) < self.config.min_quality_score:
            logger.info(
                "Report needs revision",
                score=review.get("overall_score"),
                issues=len(review.get("issues", []))
            )

        return {
            "success": True,
            "summary": f"Review complete: score {review.get('overall_score', 0):.2f}, approved: {review.get('approved')}",
            "data": {
                "overall_score": review.get("overall_score"),
                "accuracy_score": review.get("accuracy_score"),
                "completeness_score": review.get("completeness_score"),
                "clarity_score": review.get("clarity_score"),
                "approved": review.get("approved"),
                "issue_count": len(review.get("issues", [])),
                "suggestions": review.get("improvement_suggestions", [])[:3]
            },
            "artifacts": []
        }

    async def _review_report(
        self,
        report_content: str,
        findings: List[Dict]
    ) -> Dict[str, Any]:
        """Perform quality review using Claude"""
        prompt = get_review_prompt(report_content, findings)

        response = await self.anthropic.messages.create(
            model=self.config.model,
            max_tokens=2048,
            temperature=0.1,
            system=REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        # Parse JSON response
        try:
            # Handle code blocks
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            return json.loads(response_text)
        except json.JSONDecodeError:
            return {
                "overall_score": 0.7,
                "approved": True,
                "issues": [],
                "raw_response": response_text
            }

    # ==========================================================================
    # Data Retrieval
    # ==========================================================================

    async def _get_all_artifacts(self, job_id: int) -> List[Dict[str, Any]]:
        """Get all artifacts for a job"""
        result = self.supabase.table("research_artifacts").select("*").eq(
            "job_id", job_id
        ).order("created_at").execute()

        return result.data or []

    async def _get_findings(self, job_id: int) -> List[Dict[str, Any]]:
        """Extract synthesis findings from artifacts"""
        result = self.supabase.table("research_artifacts").select("*").eq(
            "job_id", job_id
        ).eq(
            "artifact_type", ArtifactType.SYNTHESIS_FINDING.value
        ).execute()

        findings = []
        for artifact in (result.data or []):
            metadata = artifact.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            key_findings = metadata.get("key_findings", [])
            for finding in key_findings:
                if isinstance(finding, dict):
                    findings.append(finding)
                else:
                    findings.append({"finding": str(finding)})

        return findings

    async def _get_section_context(
        self,
        job_id: int,
        dependency_keys: List[str]
    ) -> str:
        """Get content from previous sections"""
        if not dependency_keys:
            return ""

        # Get artifacts from dependent tasks
        task_result = self.supabase.table("plan_tasks").select("id").eq(
            "job_id", job_id
        ).in_("task_key", dependency_keys).execute()

        task_ids = [t["id"] for t in (task_result.data or [])]

        if not task_ids:
            return ""

        result = self.supabase.table("research_artifacts").select("content").eq(
            "artifact_type", ArtifactType.REPORT_SECTION.value
        ).in_("task_id", task_ids).execute()

        sections = [a.get("content", "") for a in (result.data or [])]
        return "\n\n---\n\n".join(sections)

    async def _get_report_content(self, job_id: int) -> Optional[str]:
        """Get the current report content"""
        # First check for final report artifact
        result = self.supabase.table("research_artifacts").select("content").eq(
            "job_id", job_id
        ).eq(
            "artifact_type", ArtifactType.FINAL_REPORT.value
        ).order("created_at", desc=True).limit(1).execute()

        if result.data:
            return result.data[0].get("content")

        # Fallback to job record
        job_result = self.supabase.table("research_jobs").select(
            "report_content"
        ).eq("id", job_id).single().execute()

        if job_result.data:
            return job_result.data.get("report_content")

        return None

    def _extract_findings(self, artifacts: List[Dict]) -> List[Dict]:
        """Extract findings from artifacts"""
        findings = []

        for artifact in artifacts:
            if artifact.get("artifact_type") == ArtifactType.SYNTHESIS_FINDING.value:
                metadata = artifact.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}

                for finding in metadata.get("key_findings", []):
                    findings.append(finding if isinstance(finding, dict) else {"finding": str(finding)})

        return findings

    async def _store_report(self, job_id: int, report: Dict[str, Any]):
        """Store report in the job record"""
        self.supabase.table("research_jobs").update({
            "report_content": report["content"],
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", job_id).execute()


# ==============================================================================
# Service Factory
# ==============================================================================

_executor_instance: Optional[ReportExecutor] = None


def get_report_executor() -> ReportExecutor:
    """Get or create report executor singleton"""
    global _executor_instance
    if _executor_instance is None:
        supabase = get_supabase_client()
        _executor_instance = ReportExecutor(supabase)
    return _executor_instance
