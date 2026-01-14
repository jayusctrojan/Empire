"""
Output Validator Service - Task 147

Validates and corrects agent outputs before delivery.
Ensures format compliance, completeness, consistency, and style guidelines.

Features:
- Format compliance checking (JSON, markdown, etc.)
- Completeness validation (required sections present)
- Consistency checking (no internal contradictions)
- Style guideline enforcement
- Auto-correction of formatting issues
- Flagging of uncorrectable issues for human review
"""

import json
import re
import structlog
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class OutputFormat(str, Enum):
    """Supported output formats."""
    JSON = "json"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    HTML = "html"
    STRUCTURED_ANSWER = "structured_answer"


class IssueType(str, Enum):
    """Types of validation issues."""
    FORMAT_ERROR = "format_error"
    MISSING_SECTION = "missing_section"
    INCOMPLETE_CONTENT = "incomplete_content"
    CONSISTENCY_ERROR = "consistency_error"
    STYLE_VIOLATION = "style_violation"
    LENGTH_VIOLATION = "length_violation"
    ENCODING_ERROR = "encoding_error"
    FORBIDDEN_CONTENT = "forbidden_content"


class IssueSeverity(str, Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Must be fixed, blocks output
    WARNING = "warning"  # Should be fixed, doesn't block
    INFO = "info"        # Minor issue, informational


class ValidationIssue(BaseModel):
    """Represents a validation issue found in output."""
    issue_type: IssueType
    severity: IssueSeverity
    message: str
    location: Optional[str] = None  # Where in the output
    suggestion: Optional[str] = None  # How to fix
    auto_correctable: bool = False
    correction: Optional[str] = None  # Auto-correction if available


class OutputRequirements(BaseModel):
    """Requirements for output validation."""
    format: OutputFormat = OutputFormat.PLAIN_TEXT
    min_length: int = 0
    max_length: int = 50000
    required_sections: List[str] = Field(default_factory=list)
    forbidden_patterns: List[str] = Field(default_factory=list)
    must_include_citations: bool = False
    must_include_confidence: bool = False
    style_guidelines: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Result of output validation."""
    is_valid: bool
    corrected_output: Optional[str] = None
    issues: List[ValidationIssue] = Field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    requires_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    validation_time_ms: float = 0.0


class CorrectionResult(BaseModel):
    """Result of auto-correction attempt."""
    success: bool
    corrected_text: str
    corrections_made: List[str] = Field(default_factory=list)
    corrections_failed: List[str] = Field(default_factory=list)


# Default style guidelines
DEFAULT_STYLE_GUIDELINES = {
    "no_first_person": True,  # Avoid "I", "we"
    "professional_tone": True,
    "consistent_tense": True,
    "no_placeholder_text": True,
    "proper_capitalization": True,
    "no_redundant_spaces": True,
    "max_sentence_length": 50,  # words
    "min_paragraph_length": 2,  # sentences
}

# Common forbidden patterns
DEFAULT_FORBIDDEN_PATTERNS = [
    r"\[TODO\]",
    r"\[PLACEHOLDER\]",
    r"\[INSERT.*?\]",
    r"Lorem ipsum",
    r"xxx+",
    r"TBD\b",
    r"\{\{.*?\}\}",  # Template variables
]


class OutputValidatorService:
    """
    Service for validating and correcting agent outputs.

    Provides comprehensive validation including:
    - Format compliance (JSON, markdown, etc.)
    - Completeness (required sections)
    - Consistency (no contradictions)
    - Style guidelines
    - Auto-correction when possible
    """

    def __init__(
        self,
        default_requirements: Optional[OutputRequirements] = None,
        enable_auto_correction: bool = True
    ):
        """
        Initialize output validator.

        Args:
            default_requirements: Default validation requirements.
            enable_auto_correction: Whether to attempt auto-corrections.
        """
        self.default_requirements = default_requirements or OutputRequirements()
        self.enable_auto_correction = enable_auto_correction

    async def validate(
        self,
        output: str,
        requirements: Optional[OutputRequirements] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate output against requirements.

        Args:
            output: The output text to validate.
            requirements: Validation requirements (uses defaults if not provided).
            context: Optional context for validation.

        Returns:
            ValidationResult with issues and corrected output if applicable.
        """
        import time
        start_time = time.time()

        requirements = requirements or self.default_requirements
        context = context or {}
        issues: List[ValidationIssue] = []
        corrected_output = output

        # Run all validation checks
        issues.extend(self._check_format_compliance(output, requirements.format))
        issues.extend(self._check_length(output, requirements.min_length, requirements.max_length))
        issues.extend(self._check_required_sections(output, requirements.required_sections))
        issues.extend(self._check_forbidden_patterns(output, requirements.forbidden_patterns))
        issues.extend(self._check_style_guidelines(output, requirements.style_guidelines))
        issues.extend(self._check_encoding(output))

        if requirements.must_include_citations:
            issues.extend(self._check_citations(output))

        if requirements.must_include_confidence:
            issues.extend(self._check_confidence(output))

        # Check for internal consistency
        issues.extend(self._check_consistency(output, context))

        # Attempt auto-corrections if enabled
        if self.enable_auto_correction:
            correction_result = self._apply_auto_corrections(corrected_output, issues)
            corrected_output = correction_result.corrected_text

            # Update issues that were corrected
            for issue in issues:
                if issue.auto_correctable and issue.message in correction_result.corrections_made:
                    issue.severity = IssueSeverity.INFO
                    issue.message = f"[AUTO-CORRECTED] {issue.message}"

        # Count issues by severity
        error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == IssueSeverity.INFO)

        # Determine if human review needed
        requires_human_review = False
        review_reasons = []

        if error_count > 0:
            uncorrected_errors = [i for i in issues
                                 if i.severity == IssueSeverity.ERROR
                                 and not i.message.startswith("[AUTO-CORRECTED]")]
            if uncorrected_errors:
                requires_human_review = True
                review_reasons.extend([i.message for i in uncorrected_errors[:3]])

        # Check for consistency issues (always flag for review)
        consistency_issues = [i for i in issues if i.issue_type == IssueType.CONSISTENCY_ERROR]
        if consistency_issues:
            requires_human_review = True
            review_reasons.append("Potential internal consistency issues detected")

        validation_time_ms = (time.time() - start_time) * 1000

        is_valid = error_count == 0 or (
            error_count > 0 and all(
                i.message.startswith("[AUTO-CORRECTED]")
                for i in issues if i.severity == IssueSeverity.ERROR
            )
        )

        logger.info(
            "output_validation_complete",
            is_valid=is_valid,
            error_count=error_count,
            warning_count=warning_count,
            requires_human_review=requires_human_review,
            validation_time_ms=validation_time_ms
        )

        return ValidationResult(
            is_valid=is_valid,
            corrected_output=corrected_output if corrected_output != output else None,
            issues=issues,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            requires_human_review=requires_human_review,
            review_reasons=review_reasons,
            validation_time_ms=validation_time_ms
        )

    def _check_format_compliance(
        self,
        output: str,
        expected_format: OutputFormat
    ) -> List[ValidationIssue]:
        """Check if output complies with expected format."""
        issues = []

        if expected_format == OutputFormat.JSON:
            try:
                json.loads(output)
            except json.JSONDecodeError as e:
                issues.append(ValidationIssue(
                    issue_type=IssueType.FORMAT_ERROR,
                    severity=IssueSeverity.ERROR,
                    message=f"Invalid JSON: {str(e)}",
                    location=f"position {e.pos}" if hasattr(e, 'pos') else None,
                    suggestion="Fix JSON syntax errors",
                    auto_correctable=False
                ))

        elif expected_format == OutputFormat.MARKDOWN:
            # Check for common markdown issues
            if output.count("```") % 2 != 0:
                issues.append(ValidationIssue(
                    issue_type=IssueType.FORMAT_ERROR,
                    severity=IssueSeverity.WARNING,
                    message="Unclosed code block",
                    suggestion="Ensure all ``` blocks are properly closed",
                    auto_correctable=True,
                    correction="append_closing_code_block"
                ))

            # Check for broken links
            link_pattern = r'\[([^\]]+)\]\(([^)]*)\)'
            for match in re.finditer(link_pattern, output):
                if not match.group(2).strip():
                    issues.append(ValidationIssue(
                        issue_type=IssueType.FORMAT_ERROR,
                        severity=IssueSeverity.WARNING,
                        message=f"Empty link URL for '{match.group(1)}'",
                        location=f"position {match.start()}"
                    ))

        elif expected_format == OutputFormat.STRUCTURED_ANSWER:
            # Check for expected structure
            expected_sections = ["answer", "sources", "confidence"]
            for section in expected_sections:
                patterns = [
                    f"**{section}**:",
                    f"#{1,3} {section}",
                    f'"{section}":',
                    f"{section}:"
                ]
                found = any(p.lower() in output.lower() for p in patterns)
                if not found:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.MISSING_SECTION,
                        severity=IssueSeverity.WARNING,
                        message=f"Missing expected section: {section}",
                        suggestion=f"Add a '{section}' section to the output"
                    ))

        return issues

    def _check_length(
        self,
        output: str,
        min_length: int,
        max_length: int
    ) -> List[ValidationIssue]:
        """Check output length constraints."""
        issues = []
        output_length = len(output)

        if output_length < min_length:
            issues.append(ValidationIssue(
                issue_type=IssueType.LENGTH_VIOLATION,
                severity=IssueSeverity.ERROR,
                message=f"Output too short: {output_length} chars (min: {min_length})",
                suggestion="Provide more detailed response"
            ))

        if output_length > max_length:
            issues.append(ValidationIssue(
                issue_type=IssueType.LENGTH_VIOLATION,
                severity=IssueSeverity.WARNING,
                message=f"Output too long: {output_length} chars (max: {max_length})",
                suggestion="Consider summarizing or truncating",
                auto_correctable=True,
                correction="truncate_output"
            ))

        return issues

    def _check_required_sections(
        self,
        output: str,
        required_sections: List[str]
    ) -> List[ValidationIssue]:
        """Check that all required sections are present."""
        issues = []
        output_lower = output.lower()

        for section in required_sections:
            section_lower = section.lower()
            # Check various header formats
            patterns = [
                f"# {section_lower}",
                f"## {section_lower}",
                f"### {section_lower}",
                f"**{section_lower}**",
                f"{section_lower}:",
            ]

            found = any(p in output_lower for p in patterns)
            if not found:
                issues.append(ValidationIssue(
                    issue_type=IssueType.MISSING_SECTION,
                    severity=IssueSeverity.ERROR,
                    message=f"Missing required section: {section}",
                    suggestion=f"Add section '{section}' to the output"
                ))

        return issues

    def _check_forbidden_patterns(
        self,
        output: str,
        forbidden_patterns: List[str]
    ) -> List[ValidationIssue]:
        """Check for forbidden patterns in output."""
        issues = []
        all_patterns = forbidden_patterns + DEFAULT_FORBIDDEN_PATTERNS

        for pattern in all_patterns:
            try:
                matches = list(re.finditer(pattern, output, re.IGNORECASE))
                for match in matches:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.FORBIDDEN_CONTENT,
                        severity=IssueSeverity.ERROR,
                        message=f"Forbidden pattern found: '{match.group()}'",
                        location=f"position {match.start()}",
                        suggestion="Remove or replace the forbidden content",
                        auto_correctable=True,
                        correction=f"remove_pattern:{pattern}"
                    ))
            except re.error:
                logger.warning("invalid_forbidden_pattern", pattern=pattern)

        return issues

    def _check_style_guidelines(
        self,
        output: str,
        style_guidelines: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Check style guideline compliance."""
        issues = []
        guidelines = {**DEFAULT_STYLE_GUIDELINES, **style_guidelines}

        # Check for first person usage
        if guidelines.get("no_first_person"):
            first_person = re.findall(r'\b(I|we|my|our|me|us)\b', output, re.IGNORECASE)
            if first_person:
                issues.append(ValidationIssue(
                    issue_type=IssueType.STYLE_VIOLATION,
                    severity=IssueSeverity.WARNING,
                    message=f"First person pronouns used: {', '.join(set(first_person)[:3])}",
                    suggestion="Use third person or passive voice"
                ))

        # Check for redundant spaces
        if guidelines.get("no_redundant_spaces"):
            if re.search(r'  +', output):
                issues.append(ValidationIssue(
                    issue_type=IssueType.STYLE_VIOLATION,
                    severity=IssueSeverity.INFO,
                    message="Multiple consecutive spaces found",
                    auto_correctable=True,
                    correction="fix_redundant_spaces"
                ))

        # Check sentence length
        max_sentence_length = guidelines.get("max_sentence_length", 50)
        sentences = re.split(r'[.!?]+', output)
        for i, sentence in enumerate(sentences):
            word_count = len(sentence.split())
            if word_count > max_sentence_length:
                issues.append(ValidationIssue(
                    issue_type=IssueType.STYLE_VIOLATION,
                    severity=IssueSeverity.INFO,
                    message=f"Sentence {i+1} too long ({word_count} words, max {max_sentence_length})",
                    suggestion="Consider breaking into shorter sentences"
                ))

        # Check for placeholder text
        if guidelines.get("no_placeholder_text"):
            placeholder_patterns = [
                r'\[.*?\](?!\()',  # [text] not followed by (link)
                r'<.*?>',  # <placeholder>
                r'\{.*?\}',  # {placeholder}
            ]
            for pattern in placeholder_patterns:
                matches = re.findall(pattern, output)
                for match in matches:
                    # Exclude common valid patterns
                    if match not in ['[1]', '[2]', '[3]', '[source]', '[citation]']:
                        issues.append(ValidationIssue(
                            issue_type=IssueType.STYLE_VIOLATION,
                            severity=IssueSeverity.WARNING,
                            message=f"Possible placeholder text: '{match}'",
                            suggestion="Replace with actual content"
                        ))

        return issues

    def _check_encoding(self, output: str) -> List[ValidationIssue]:
        """Check for encoding issues."""
        issues = []

        # Check for common encoding problems
        encoding_issues = [
            ('\ufffd', 'replacement character'),
            ('\x00', 'null byte'),
            ('\u200b', 'zero-width space'),
            ('\u200c', 'zero-width non-joiner'),
            ('\u200d', 'zero-width joiner'),
        ]

        for char, name in encoding_issues:
            if char in output:
                issues.append(ValidationIssue(
                    issue_type=IssueType.ENCODING_ERROR,
                    severity=IssueSeverity.WARNING,
                    message=f"Found {name} in output",
                    auto_correctable=True,
                    correction=f"remove_char:{repr(char)}"
                ))

        return issues

    def _check_citations(self, output: str) -> List[ValidationIssue]:
        """Check for citation presence and format."""
        issues = []

        # Look for common citation patterns
        citation_patterns = [
            r'\[\d+\]',  # [1], [2]
            r'\[source:\s*[^\]]+\]',
            r'\(source:\s*[^)]+\)',
            r'Source:',
            r'Reference:',
            r'Citation:',
        ]

        has_citation = any(
            re.search(pattern, output, re.IGNORECASE)
            for pattern in citation_patterns
        )

        if not has_citation:
            issues.append(ValidationIssue(
                issue_type=IssueType.MISSING_SECTION,
                severity=IssueSeverity.ERROR,
                message="No citations found in output",
                suggestion="Add source citations using [1], [2] format or 'Source:' sections"
            ))

        return issues

    def _check_confidence(self, output: str) -> List[ValidationIssue]:
        """Check for confidence indication in output."""
        issues = []

        confidence_patterns = [
            r'confidence[:\s]+\d+',
            r'certainty[:\s]+\d+',
            r'\d+%\s*(?:confident|certain)',
            r'(?:high|medium|low)\s+confidence',
        ]

        has_confidence = any(
            re.search(pattern, output, re.IGNORECASE)
            for pattern in confidence_patterns
        )

        if not has_confidence:
            issues.append(ValidationIssue(
                issue_type=IssueType.MISSING_SECTION,
                severity=IssueSeverity.WARNING,
                message="No confidence level indicated",
                suggestion="Add confidence level (e.g., 'Confidence: 85%' or 'High confidence')"
            ))

        return issues

    def _check_consistency(
        self,
        output: str,
        context: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Check for internal consistency issues."""
        issues = []

        # Check for contradictory statements
        contradiction_pairs = [
            (r'always', r'never'),
            (r'all', r'none'),
            (r'must', r'must not'),
            (r'required', r'optional'),
            (r'true', r'false'),
            (r'yes', r'no'),
        ]

        output_lower = output.lower()
        paragraphs = output_lower.split('\n\n')

        for para in paragraphs:
            for word1, word2 in contradiction_pairs:
                if re.search(rf'\b{word1}\b', para) and re.search(rf'\b{word2}\b', para):
                    issues.append(ValidationIssue(
                        issue_type=IssueType.CONSISTENCY_ERROR,
                        severity=IssueSeverity.WARNING,
                        message=f"Potential contradiction: '{word1}' and '{word2}' in same paragraph",
                        suggestion="Review for logical consistency"
                    ))

        # Check for numeric inconsistencies
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\s*%', output)
        if numbers:
            percentages = [float(n) for n in numbers]
            if any(p > 100 for p in percentages):
                issues.append(ValidationIssue(
                    issue_type=IssueType.CONSISTENCY_ERROR,
                    severity=IssueSeverity.ERROR,
                    message="Percentage value exceeds 100%",
                    suggestion="Verify percentage calculations"
                ))

        return issues

    def _apply_auto_corrections(
        self,
        output: str,
        issues: List[ValidationIssue]
    ) -> CorrectionResult:
        """Apply auto-corrections for correctable issues."""
        corrected = output
        corrections_made = []
        corrections_failed = []

        for issue in issues:
            if not issue.auto_correctable or not issue.correction:
                continue

            try:
                if issue.correction == "fix_redundant_spaces":
                    corrected = re.sub(r'  +', ' ', corrected)
                    corrections_made.append(issue.message)

                elif issue.correction == "append_closing_code_block":
                    if corrected.count("```") % 2 != 0:
                        corrected += "\n```"
                        corrections_made.append(issue.message)

                elif issue.correction.startswith("remove_pattern:"):
                    pattern = issue.correction.split(":", 1)[1]
                    corrected = re.sub(pattern, '', corrected, flags=re.IGNORECASE)
                    corrections_made.append(issue.message)

                elif issue.correction.startswith("remove_char:"):
                    char = issue.correction.split(":", 1)[1]
                    char = eval(char)  # Convert repr back to char
                    corrected = corrected.replace(char, '')
                    corrections_made.append(issue.message)

                elif issue.correction == "truncate_output":
                    # Don't auto-truncate - just flag it
                    corrections_failed.append(issue.message)

            except Exception as e:
                logger.warning("auto_correction_failed",
                             correction=issue.correction, error=str(e))
                corrections_failed.append(issue.message)

        return CorrectionResult(
            success=len(corrections_failed) == 0,
            corrected_text=corrected,
            corrections_made=corrections_made,
            corrections_failed=corrections_failed
        )

    def get_requirements_for_format(
        self,
        output_format: OutputFormat,
        task_type: Optional[str] = None
    ) -> OutputRequirements:
        """
        Get recommended requirements for a given format and task type.

        Args:
            output_format: Target output format.
            task_type: Optional task type for specialized requirements.

        Returns:
            OutputRequirements configured for the format.
        """
        base_requirements = OutputRequirements(format=output_format)

        if output_format == OutputFormat.JSON:
            base_requirements.min_length = 2  # {}
            base_requirements.max_length = 100000

        elif output_format == OutputFormat.MARKDOWN:
            base_requirements.min_length = 50
            base_requirements.max_length = 50000

        elif output_format == OutputFormat.STRUCTURED_ANSWER:
            base_requirements.must_include_citations = True
            base_requirements.must_include_confidence = True
            base_requirements.required_sections = ["Answer", "Sources"]

        # Task-specific adjustments
        if task_type == "summarization":
            base_requirements.min_length = 100
            base_requirements.max_length = 2000
            base_requirements.required_sections = ["Summary", "Key Points"]

        elif task_type == "analysis":
            base_requirements.min_length = 200
            base_requirements.required_sections = ["Analysis", "Findings", "Recommendations"]

        elif task_type == "research":
            base_requirements.must_include_citations = True
            base_requirements.required_sections = ["Research Findings", "Sources"]

        return base_requirements


# Singleton instance
_output_validator_instance: Optional[OutputValidatorService] = None


def get_output_validator(
    enable_auto_correction: bool = True
) -> OutputValidatorService:
    """Get or create the output validator singleton."""
    global _output_validator_instance

    if _output_validator_instance is None:
        _output_validator_instance = OutputValidatorService(
            enable_auto_correction=enable_auto_correction
        )

    return _output_validator_instance
