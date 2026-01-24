"""
Empire v7.3 - CrewAI Output Validation Service
Validates and scores outputs from multi-agent workflows (Task 38.5)
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import structlog
import re
import json

logger = structlog.get_logger(__name__)


class ValidationResult(BaseModel):
    """Validation result for agent output"""
    is_valid: bool = Field(description="Whether output passes validation")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality score 0-1")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed metrics")


class CrewAIOutputValidator:
    """
    Validates outputs from CrewAI multi-agent workflows.

    Provides validation rules for each agent type:
    - Research: completeness, entity extraction quality
    - Analysis: accuracy, actionability of insights
    - Writing: coherence, format compliance, structure
    - Review: thoroughness, confidence scores, claim verification
    """

    def __init__(self):
        self.min_quality_threshold = 0.6  # Minimum acceptable quality score

    def validate_execution_output(
        self,
        execution_result: Dict[str, Any],
        agent_roles: List[str]
    ) -> ValidationResult:
        """
        Validate complete execution output.

        Args:
            execution_result: Full execution results from CrewAI
            agent_roles: List of agent roles in the crew

        Returns:
            ValidationResult with overall quality assessment
        """
        try:
            errors = []
            warnings = []
            recommendations = []
            metrics = {}

            # Check basic structure
            if not execution_result:
                errors.append("Execution result is empty")
                return ValidationResult(
                    is_valid=False,
                    quality_score=0.0,
                    errors=errors
                )

            results = execution_result.get("results", "")
            if not results:
                errors.append("No results found in execution output")

            # Validate based on agent roles
            agent_validations = []
            for role in agent_roles:
                if "research" in role.lower():
                    validation = self.validate_research_output(results)
                    agent_validations.append(validation)
                    metrics["research"] = validation.metrics

                elif "strateg" in role.lower() or "analy" in role.lower():
                    validation = self.validate_analysis_output(results)
                    agent_validations.append(validation)
                    metrics["analysis"] = validation.metrics

                elif "writ" in role.lower():
                    validation = self.validate_writing_output(results)
                    agent_validations.append(validation)
                    metrics["writing"] = validation.metrics

                elif "fact" in role.lower() or "review" in role.lower():
                    validation = self.validate_review_output(results)
                    agent_validations.append(validation)
                    metrics["review"] = validation.metrics

            # Aggregate results
            if not agent_validations:
                warnings.append("No agent-specific validations performed")
                overall_score = 0.5  # Neutral score
            else:
                overall_score = sum(v.quality_score for v in agent_validations) / len(agent_validations)

                for v in agent_validations:
                    errors.extend(v.errors)
                    warnings.extend(v.warnings)
                    recommendations.extend(v.recommendations)

            # Check overall quality
            is_valid = overall_score >= self.min_quality_threshold and not errors

            if overall_score < self.min_quality_threshold:
                warnings.append(f"Quality score {overall_score:.2f} below threshold {self.min_quality_threshold}")

            return ValidationResult(
                is_valid=is_valid,
                quality_score=overall_score,
                errors=errors,
                warnings=warnings,
                recommendations=recommendations,
                metrics=metrics
            )

        except Exception as e:
            logger.error("Validation failed", error=str(e), exc_info=True)
            return ValidationResult(
                is_valid=False,
                quality_score=0.0,
                errors=[f"Validation error: {str(e)}"]
            )

    def validate_research_output(self, output: str) -> ValidationResult:
        """
        Validate research agent output.

        Checks:
        - Entity extraction quality (presence of entities)
        - Topic identification
        - Information completeness
        - Structured format
        """
        errors = []
        warnings = []
        recommendations = []
        metrics = {
            "entity_count": 0,
            "topic_count": 0,
            "length": len(output),
            "has_structure": False
        }

        score_components = []

        # Check minimum length
        if len(output) < 100:
            errors.append("Research output too short (< 100 chars)")
            score_components.append(0.0)
        else:
            score_components.append(1.0)

        # Check for entities (simple heuristic: capitalized phrases, organizations, locations)
        entity_patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+',  # Multi-word capitalized phrases
            r'\b(?:Inc|Corp|LLC|Ltd|Co)\b',  # Organizations
            r'\b[A-Z]{2,}\b',  # Acronyms
        ]

        entity_count = 0
        for pattern in entity_patterns:
            entity_count += len(re.findall(pattern, output))

        metrics["entity_count"] = entity_count

        if entity_count < 3:
            warnings.append("Few entities identified (< 3)")
            score_components.append(0.5)
        elif entity_count < 10:
            score_components.append(0.7)
        else:
            score_components.append(1.0)

        # Check for topic keywords
        topic_keywords = ["topic", "theme", "subject", "finding", "insight", "analysis", "conclusion"]
        topic_mentions = sum(1 for kw in topic_keywords if kw.lower() in output.lower())
        metrics["topic_count"] = topic_mentions

        if topic_mentions == 0:
            warnings.append("No topic/theme indicators found")
            score_components.append(0.3)
        else:
            score_components.append(min(1.0, topic_mentions / 3))

        # Check for structured output (sections, lists, etc.)
        structure_indicators = ["\n-", "\n*", "\n1.", "\n2.", "##", "**"]
        has_structure = any(ind in output for ind in structure_indicators)
        metrics["has_structure"] = has_structure

        if not has_structure:
            recommendations.append("Consider adding structured sections or lists")

        # Calculate overall score
        quality_score = sum(score_components) / len(score_components) if score_components else 0.5

        return ValidationResult(
            is_valid=len(errors) == 0,
            quality_score=quality_score,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            metrics=metrics
        )

    def validate_analysis_output(self, output: str) -> ValidationResult:
        """
        Validate analysis/strategy agent output.

        Checks:
        - Actionability (recommendations, next steps)
        - Insight quality (findings, conclusions)
        - Categorization/taxonomy
        - Executive summary presence
        """
        errors = []
        warnings = []
        recommendations = []
        metrics = {
            "length": len(output),
            "has_summary": False,
            "has_recommendations": False,
            "insight_count": 0,
            "actionable_items": 0
        }

        score_components = []

        # Check minimum length
        if len(output) < 150:
            errors.append("Analysis output too short (< 150 chars)")
            score_components.append(0.0)
        else:
            score_components.append(1.0)

        # Check for executive summary
        summary_keywords = ["summary", "executive summary", "overview", "in summary", "key findings"]
        has_summary = any(kw in output.lower() for kw in summary_keywords)
        metrics["has_summary"] = has_summary

        if not has_summary:
            warnings.append("No executive summary found")
            score_components.append(0.5)
        else:
            score_components.append(1.0)

        # Check for insights/findings
        insight_keywords = ["finding", "insight", "conclusion", "observation", "analysis shows", "data indicates"]
        insight_count = sum(1 for kw in insight_keywords if kw in output.lower())
        metrics["insight_count"] = insight_count

        if insight_count < 2:
            warnings.append("Few insights/findings (< 2)")
            score_components.append(0.4)
        else:
            score_components.append(min(1.0, insight_count / 4))

        # Check for recommendations/actionable items
        action_keywords = ["recommend", "suggest", "should", "next step", "action", "implement"]
        actionable_count = sum(1 for kw in action_keywords if kw in output.lower())
        metrics["actionable_items"] = actionable_count
        metrics["has_recommendations"] = actionable_count > 0

        if actionable_count == 0:
            recommendations.append("Add actionable recommendations or next steps")
            score_components.append(0.6)
        else:
            score_components.append(min(1.0, actionable_count / 3))

        # Calculate overall score
        quality_score = sum(score_components) / len(score_components) if score_components else 0.5

        return ValidationResult(
            is_valid=len(errors) == 0,
            quality_score=quality_score,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            metrics=metrics
        )

    def validate_writing_output(self, output: str) -> ValidationResult:
        """
        Validate writing/content generation agent output.

        Checks:
        - Coherence (paragraph structure, flow)
        - Format compliance (proper sections, headers)
        - Completeness (meets minimum length)
        - Professional tone
        """
        errors = []
        warnings = []
        recommendations = []
        metrics = {
            "length": len(output),
            "paragraph_count": 0,
            "section_count": 0,
            "avg_sentence_length": 0,
            "readability_score": 0
        }

        score_components = []

        # Check minimum length for written content
        if len(output) < 200:
            errors.append("Written content too short (< 200 chars)")
            score_components.append(0.0)
        else:
            score_components.append(1.0)

        # Check paragraph structure
        paragraphs = [p.strip() for p in output.split('\n\n') if p.strip()]
        metrics["paragraph_count"] = len(paragraphs)

        if len(paragraphs) < 2:
            warnings.append("Content should have multiple paragraphs")
            score_components.append(0.6)
        else:
            score_components.append(min(1.0, len(paragraphs) / 4))

        # Check for sections/headers
        section_markers = re.findall(r'^#{1,6}\s+.+$|^\*\*.+\*\*$', output, re.MULTILINE)
        metrics["section_count"] = len(section_markers)

        if len(section_markers) == 0:
            recommendations.append("Consider adding section headers for better organization")

        # Basic readability check (sentence length)
        sentences = re.split(r'[.!?]+', output)
        sentences = [s.strip() for s in sentences if s.strip()]

        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            metrics["avg_sentence_length"] = round(avg_sentence_length, 1)

            # Ideal: 15-20 words per sentence
            if avg_sentence_length < 10:
                warnings.append("Sentences may be too short (choppy)")
                score_components.append(0.7)
            elif avg_sentence_length > 30:
                warnings.append("Sentences may be too long (complex)")
                score_components.append(0.7)
            else:
                score_components.append(1.0)

        # Calculate overall score
        quality_score = sum(score_components) / len(score_components) if score_components else 0.5

        return ValidationResult(
            is_valid=len(errors) == 0,
            quality_score=quality_score,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            metrics=metrics
        )

    def validate_review_output(self, output: str) -> ValidationResult:
        """
        Validate fact-checking/review agent output.

        Checks:
        - Thoroughness (number of claims verified)
        - Confidence scores present
        - Citations/sources identified
        - Flagged issues documented
        """
        errors = []
        warnings = []
        recommendations = []
        metrics = {
            "length": len(output),
            "claims_identified": 0,
            "confidence_scores_found": 0,
            "sources_mentioned": 0,
            "flags_raised": 0
        }

        score_components = []

        # Check minimum length
        if len(output) < 100:
            errors.append("Review output too short (< 100 chars)")
            score_components.append(0.0)
        else:
            score_components.append(1.0)

        # Check for claim identification
        claim_keywords = ["claim", "statement", "assertion", "fact", "allegation"]
        claim_count = sum(1 for kw in claim_keywords if kw in output.lower())
        metrics["claims_identified"] = claim_count

        if claim_count == 0:
            warnings.append("No claims explicitly identified")
            score_components.append(0.5)
        else:
            score_components.append(min(1.0, claim_count / 3))

        # Check for confidence scores
        confidence_patterns = [
            r'\b\d{1,3}%',  # Percentage
            r'\b0\.\d+\b',  # Decimal 0.0-1.0
            r'\b(?:high|medium|low)\s+confidence\b',  # Named confidence
        ]

        confidence_count = 0
        for pattern in confidence_patterns:
            confidence_count += len(re.findall(pattern, output, re.IGNORECASE))

        metrics["confidence_scores_found"] = confidence_count

        if confidence_count == 0:
            recommendations.append("Add confidence scores for verified claims")
            score_components.append(0.6)
        else:
            score_components.append(min(1.0, confidence_count / 3))

        # Check for sources/citations
        source_keywords = ["source", "citation", "reference", "according to", "based on", "documented in"]
        source_count = sum(1 for kw in source_keywords if kw in output.lower())
        metrics["sources_mentioned"] = source_count

        if source_count == 0:
            warnings.append("No sources or citations mentioned")
            score_components.append(0.6)
        else:
            score_components.append(min(1.0, source_count / 2))

        # Check for flagged issues
        flag_keywords = ["flag", "concern", "issue", "warning", "unsupported", "inaccurate", "questionable"]
        flag_count = sum(1 for kw in flag_keywords if kw in output.lower())
        metrics["flags_raised"] = flag_count

        # Calculate overall score
        quality_score = sum(score_components) / len(score_components) if score_components else 0.5

        return ValidationResult(
            is_valid=len(errors) == 0,
            quality_score=quality_score,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            metrics=metrics
        )


# Singleton instance
_validator_instance = None


def get_output_validator() -> CrewAIOutputValidator:
    """Get singleton instance of output validator"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = CrewAIOutputValidator()
    return _validator_instance
