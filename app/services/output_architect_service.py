"""
Empire v7.3 - Output Architect Service
Phase 1: Multi-Model Quality Pipeline

Final stage of the Sonnet 4.5 bookend pipeline. Takes raw Kimi reasoning
output and reformats it into polished, structured content. Detects when
an artifact (DOCX/XLSX/PPTX) should be generated.

Pipeline: PromptEngineer(Sonnet) -> Kimi(reasoning) -> OutputArchitect(Sonnet)
"""

import json
import structlog
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from app.services.llm_client import LLMClient, get_llm_client
from app.services.prompt_engineer_service import OutputFormat, StructuredPrompt

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ContentBlock:
    """A structured content block for document generation."""
    type: str  # heading, paragraph, table, code, list, chart_data
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    # For tables: metadata has "headers" and "rows"
    # For headings: metadata has "level" (1-3)
    # For code: metadata has "language"
    # For lists: metadata has "ordered" bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class ArchitecturedOutput:
    """Output from the Output Architect."""
    formatted_content: str              # Polished markdown for streaming to user
    content_blocks: List[ContentBlock]  # Structured blocks for document generation
    has_artifact: bool = False
    artifact_format: Optional[str] = None  # docx, xlsx, pptx
    artifact_title: Optional[str] = None
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formattedContent": self.formatted_content,
            "contentBlocks": [b.to_dict() for b in self.content_blocks],
            "hasArtifact": self.has_artifact,
            "artifactFormat": self.artifact_format,
            "artifactTitle": self.artifact_title,
            "summary": self.summary,
        }


# ============================================================================
# System Prompt
# ============================================================================

OUTPUT_ARCHITECT_SYSTEM = """You are an Output Architect that transforms raw AI reasoning into polished, well-formatted responses.

Your job:
1. Take the raw reasoning output and format it beautifully with clear structure
2. Preserve all citations [1], [2] etc. exactly as they appear
3. Add clear headings, bullet points, and formatting where appropriate
4. Detect if the content should generate a downloadable artifact

Your output format:
- Write the polished response directly (this gets streamed to the user)
- At the END of your response, on a new line, add a JSON metadata block:

```json
{"has_artifact": true/false, "artifact_format": "docx"|"xlsx"|"pptx"|null, "artifact_title": "string"|null, "summary": "1-2 sentence summary"}
```

Artifact detection rules:
- If the response contains structured data suitable for a spreadsheet (comparisons, lists with columns, financial data) → xlsx
- If the user originally asked for a document, report, or paper → docx
- If the content has clear sections suitable for slides (3+ distinct topics) → pptx
- If it's a normal conversational answer → no artifact (has_artifact=false)

Formatting rules:
- Use ## for major sections, ### for subsections
- Use tables for comparative data
- Use bullet points for lists
- Use > blockquotes for key takeaways
- Keep prose concise and scannable
- Do NOT add information that wasn't in the raw response
- Do NOT remove citations"""


# ============================================================================
# Service
# ============================================================================

class OutputArchitectService:
    """
    Formats raw Kimi reasoning into polished output with artifact detection.
    Uses Sonnet 4.5 (~2-3s latency).
    """

    MODEL = "claude-sonnet-4-5-20250929"
    MAX_TOKENS = 4096
    TEMPERATURE = 0.2

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client("anthropic")

    async def architect_output(
        self,
        raw_response: str,
        structured_prompt: StructuredPrompt,
        sources_summary: Optional[str] = None,
    ) -> ArchitecturedOutput:
        """
        Non-streaming: format raw response and detect artifacts.

        Args:
            raw_response: Raw Kimi reasoning output
            structured_prompt: Output from Prompt Engineer (intent, format info)
            sources_summary: Optional summary of source documents used

        Returns:
            ArchitecturedOutput with formatted content and artifact metadata
        """
        user_message = self._build_user_message(raw_response, structured_prompt, sources_summary)

        formatted = await self.llm_client.generate(
            system=OUTPUT_ARCHITECT_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE,
            model=self.MODEL,
        )

        return self._parse_output(formatted, structured_prompt)

    async def stream_architect_output(
        self,
        raw_response: str,
        structured_prompt: StructuredPrompt,
        sources_summary: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Streaming: format raw response token by token.
        The caller should collect the full output to parse artifact metadata.

        Yields:
            Tokens of the formatted response
        """
        user_message = self._build_user_message(raw_response, structured_prompt, sources_summary)

        async for token in self.llm_client.stream(
            system=OUTPUT_ARCHITECT_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE,
            model=self.MODEL,
        ):
            yield token

    def _build_user_message(
        self,
        raw_response: str,
        structured_prompt: StructuredPrompt,
        sources_summary: Optional[str] = None,
    ) -> str:
        parts = [
            f"Original query: {structured_prompt.original_query}",
            f"Intent: {structured_prompt.intent.value}",
            f"Desired format: {structured_prompt.desired_format.value}",
        ]

        if structured_prompt.output_instructions:
            parts.append(f"Instructions: {structured_prompt.output_instructions}")

        if sources_summary:
            parts.append(f"Sources used: {sources_summary}")

        parts.append(f"\n---\nRaw reasoning output:\n\n{raw_response}")

        return "\n".join(parts)

    def _parse_output(
        self,
        raw_output: str,
        structured_prompt: StructuredPrompt,
    ) -> ArchitecturedOutput:
        """Parse formatted output and extract artifact metadata from JSON block."""
        formatted_content = raw_output
        has_artifact = False
        artifact_format = None
        artifact_title = None
        summary = None

        # Try to extract JSON metadata block from end of response
        try:
            # Look for ```json block at the end
            if "```json" in raw_output:
                parts = raw_output.rsplit("```json", 1)
                formatted_content = parts[0].strip()
                json_str = parts[1].split("```")[0].strip()
                metadata = json.loads(json_str)

                has_artifact = metadata.get("has_artifact", False)
                artifact_format = metadata.get("artifact_format")
                artifact_title = metadata.get("artifact_title")
                summary = metadata.get("summary")
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning("Failed to parse architect metadata", error=str(e))

        # Fallback artifact detection based on prompt engineer output
        if not has_artifact and structured_prompt.desired_format in (
            OutputFormat.SPREADSHEET, OutputFormat.PRESENTATION, OutputFormat.DOCUMENT
        ):
            has_artifact = True
            format_map = {
                OutputFormat.SPREADSHEET: "xlsx",
                OutputFormat.PRESENTATION: "pptx",
                OutputFormat.DOCUMENT: "docx",
            }
            artifact_format = format_map.get(structured_prompt.desired_format)
            artifact_title = structured_prompt.original_query[:100]

        # Parse content blocks from formatted content
        content_blocks = self._extract_content_blocks(formatted_content)

        return ArchitecturedOutput(
            formatted_content=formatted_content,
            content_blocks=content_blocks,
            has_artifact=has_artifact,
            artifact_format=artifact_format,
            artifact_title=artifact_title,
            summary=summary,
        )

    @staticmethod
    def _extract_content_blocks(content: str) -> List[ContentBlock]:
        """Extract structured content blocks from markdown content."""
        blocks: List[ContentBlock] = []
        lines = content.split("\n")
        current_block: Optional[ContentBlock] = None
        in_table = False
        table_rows: List[List[str]] = []
        table_headers: List[str] = []

        for line in lines:
            stripped = line.strip()

            # Heading (# through ###)
            if stripped.startswith("#") and len(stripped) > 1 and stripped.lstrip("#").startswith(" "):
                if current_block:
                    blocks.append(current_block)
                    current_block = None

                level = len(stripped) - len(stripped.lstrip("#"))
                text = stripped.lstrip("#").strip()
                blocks.append(ContentBlock(
                    type="heading",
                    content=text,
                    metadata={"level": min(level, 3)},
                ))
                continue

            # Table row
            if "|" in stripped and stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                # Skip separator rows (---)
                if all(c.replace("-", "").replace(":", "") == "" for c in cells):
                    continue
                if not in_table:
                    in_table = True
                    table_headers = cells
                    table_rows = []
                else:
                    table_rows.append(cells)
                continue
            elif in_table:
                # End of table
                blocks.append(ContentBlock(
                    type="table",
                    content="",
                    metadata={"headers": table_headers, "rows": table_rows},
                ))
                in_table = False
                table_rows = []
                table_headers = []

            # Code block (simplified)
            if stripped.startswith("```"):
                if current_block and current_block.type == "code":
                    blocks.append(current_block)
                    current_block = None
                else:
                    if current_block:
                        blocks.append(current_block)
                    lang = stripped[3:].strip() or "text"
                    current_block = ContentBlock(type="code", content="", metadata={"language": lang})
                continue

            if current_block and current_block.type == "code":
                current_block.content += line + "\n"
                continue

            # List item (unordered: - or *, ordered: 1. 2. etc.)
            import re as _re
            ordered_match = _re.match(r'^(\d+)\.\s+(.+)', stripped)
            if stripped.startswith("- ") or stripped.startswith("* ") or ordered_match:
                is_ordered = bool(ordered_match)
                if current_block and (current_block.type != "list" or current_block.metadata.get("ordered") != is_ordered):
                    blocks.append(current_block)
                    current_block = None
                if not current_block:
                    current_block = ContentBlock(type="list", content="", metadata={"ordered": is_ordered})
                if ordered_match:
                    current_block.content += ordered_match.group(2) + "\n"
                else:
                    current_block.content += stripped[2:] + "\n"
                continue

            # Regular paragraph
            if stripped:
                if current_block and current_block.type == "paragraph":
                    current_block.content += " " + stripped
                else:
                    if current_block:
                        blocks.append(current_block)
                    current_block = ContentBlock(type="paragraph", content=stripped)
            else:
                if current_block:
                    blocks.append(current_block)
                    current_block = None

        # Flush remaining
        if in_table:
            blocks.append(ContentBlock(
                type="table",
                content="",
                metadata={"headers": table_headers, "rows": table_rows},
            ))
        if current_block:
            blocks.append(current_block)

        return blocks


# ============================================================================
# Singleton
# ============================================================================

_service: Optional[OutputArchitectService] = None


def get_output_architect_service() -> OutputArchitectService:
    global _service
    if _service is None:
        _service = OutputArchitectService()
    return _service
