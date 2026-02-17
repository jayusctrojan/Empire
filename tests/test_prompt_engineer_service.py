"""
Empire v7.3 - Prompt Engineer & Output Architect Service Tests
Phase 1: Multi-Model Quality Pipeline

Tests for:
- Prompt Engineer: intent detection, format detection, JSON parsing, fallback
- Output Architect: formatting, artifact detection, content block extraction, streaming
- Pipeline mode tracking
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.prompt_engineer_service import (
    PromptEngineerService,
    QueryIntent,
    OutputFormat,
    PipelineMode,
    StructuredPrompt,
)
from app.services.output_architect_service import (
    OutputArchitectService,
    ContentBlock,
    ArchitecturedOutput,
)


# ============================================================================
# Prompt Engineer Tests
# ============================================================================

class TestPromptEngineerParsing:
    """Test JSON parsing and fallback behavior."""

    def setup_method(self):
        self.mock_llm = MagicMock()
        self.service = PromptEngineerService(llm_client=self.mock_llm)

    def test_parse_valid_json(self):
        raw = json.dumps({
            "enriched_query": "What are the key financial metrics for Q4?",
            "intent": "analytical",
            "desired_format": "table",
            "scope": "Q4 financial data",
            "constraints": ["Only 2025 data"],
            "output_instructions": "Present as a comparison table"
        })

        result = self.service._parse_response("Q4 metrics", raw)

        assert result.intent == QueryIntent.ANALYTICAL
        assert result.desired_format == OutputFormat.TABLE
        assert result.enriched_query == "What are the key financial metrics for Q4?"
        assert "Only 2025 data" in result.constraints
        assert result.original_query == "Q4 metrics"

    def test_parse_json_with_code_fences(self):
        raw = '```json\n{"enriched_query": "test", "intent": "factual", "desired_format": "text", "scope": "", "constraints": [], "output_instructions": "be clear"}\n```'

        result = self.service._parse_response("test", raw)

        assert result.intent == QueryIntent.FACTUAL
        assert result.desired_format == OutputFormat.TEXT

    def test_parse_malformed_json_falls_back(self):
        raw = "This is not valid JSON at all {broken"

        result = self.service._parse_response("create a spreadsheet", raw)

        # Fallback heuristic should detect "create" → DOCUMENT
        assert result.intent == QueryIntent.DOCUMENT
        assert result.enriched_query == "create a spreadsheet"

    def test_parse_invalid_enum_falls_back(self):
        raw = json.dumps({
            "enriched_query": "test",
            "intent": "nonexistent_intent",
            "desired_format": "text",
        })

        result = self.service._parse_response("test", raw)

        # ValueError on enum → fallback
        assert result.original_query == "test"


class TestPromptEngineerFallback:
    """Test heuristic fallback intent/format detection."""

    def test_create_keyword_detected(self):
        result = PromptEngineerService._fallback_prompt("Create a marketing strategy document")
        assert result.intent == QueryIntent.DOCUMENT

    def test_compare_keyword_detected(self):
        result = PromptEngineerService._fallback_prompt("Compare Q3 vs Q4 revenue")
        assert result.intent == QueryIntent.ANALYTICAL

    def test_how_to_keyword_detected(self):
        result = PromptEngineerService._fallback_prompt("How to set up CI/CD pipeline")
        assert result.intent == QueryIntent.PROCEDURAL

    def test_default_intent_is_factual(self):
        result = PromptEngineerService._fallback_prompt("What is the company revenue?")
        assert result.intent == QueryIntent.FACTUAL

    def test_spreadsheet_format_detected(self):
        result = PromptEngineerService._fallback_prompt("Create an excel spreadsheet of sales data")
        assert result.desired_format == OutputFormat.SPREADSHEET

    def test_presentation_format_detected(self):
        result = PromptEngineerService._fallback_prompt("Build a slides presentation for the board")
        assert result.desired_format == OutputFormat.PRESENTATION

    def test_document_format_detected(self):
        result = PromptEngineerService._fallback_prompt("Write a report on compliance")
        assert result.desired_format == OutputFormat.DOCUMENT

    def test_default_format_is_text(self):
        result = PromptEngineerService._fallback_prompt("What is our revenue?")
        assert result.desired_format == OutputFormat.TEXT


class TestPromptEngineerGenerate:
    """Test the full engineer_prompt flow."""

    @pytest.mark.asyncio
    async def test_engineer_prompt_success(self):
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=json.dumps({
            "enriched_query": "Detailed Q4 analysis",
            "intent": "analytical",
            "desired_format": "report",
            "scope": "Q4 2025",
            "constraints": [],
            "output_instructions": "Use sections",
        }))

        service = PromptEngineerService(llm_client=mock_llm)
        result = await service.engineer_prompt("Q4 analysis")

        assert result.intent == QueryIntent.ANALYTICAL
        assert result.desired_format == OutputFormat.REPORT
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_engineer_prompt_with_context(self):
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=json.dumps({
            "enriched_query": "Follow up on revenue",
            "intent": "factual",
            "desired_format": "text",
            "scope": "",
            "constraints": [],
            "output_instructions": "",
        }))

        service = PromptEngineerService(llm_client=mock_llm)
        await service.engineer_prompt("tell me more", conversation_context="Discussed revenue trends")

        # Check that conversation context was included
        call_args = mock_llm.generate.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        assert "Conversation context" in messages[0]["content"]


# ============================================================================
# Structured Prompt Tests
# ============================================================================

class TestStructuredPrompt:
    def test_to_dict(self):
        sp = StructuredPrompt(
            original_query="test",
            enriched_query="enriched test",
            intent=QueryIntent.ANALYTICAL,
            desired_format=OutputFormat.REPORT,
            scope="Q4",
            constraints=["recent only"],
            output_instructions="use headers",
        )
        d = sp.to_dict()
        assert d["intent"] == "analytical"
        assert d["desiredFormat"] == "report"
        assert d["constraints"] == ["recent only"]


class TestPipelineMode:
    def test_all_modes_exist(self):
        assert PipelineMode.FULL.value == "full"
        assert PipelineMode.NO_PROMPT_ENGINEER.value == "no_prompt_engineer"
        assert PipelineMode.NO_OUTPUT_ARCHITECT.value == "no_output_architect"
        assert PipelineMode.DIRECT.value == "direct"


# ============================================================================
# Output Architect Tests
# ============================================================================

class TestOutputArchitectParsing:
    """Test output parsing and artifact detection."""

    def setup_method(self):
        self.mock_llm = MagicMock()
        self.service = OutputArchitectService(llm_client=self.mock_llm)

    def _make_prompt(self, intent=QueryIntent.FACTUAL, fmt=OutputFormat.TEXT):
        return StructuredPrompt(
            original_query="test query",
            enriched_query="enriched test query",
            intent=intent,
            desired_format=fmt,
        )

    def test_parse_with_json_metadata_block(self):
        raw = """## Summary

Here is a well-formatted response with citations [1].

> Key takeaway: Revenue grew 15%.

```json
{"has_artifact": true, "artifact_format": "docx", "artifact_title": "Revenue Report", "summary": "Q4 revenue analysis"}
```"""

        result = self.service.parse_output(raw, self._make_prompt())

        assert result.has_artifact is True
        assert result.artifact_format == "docx"
        assert result.artifact_title == "Revenue Report"
        assert result.summary == "Q4 revenue analysis"
        assert "```json" not in result.formatted_content

    def test_parse_without_metadata_block(self):
        raw = "## Answer\n\nSimple response without artifact metadata."

        result = self.service.parse_output(raw, self._make_prompt())

        assert result.has_artifact is False
        assert "Simple response" in result.formatted_content

    def test_fallback_artifact_detection_from_prompt(self):
        """If JSON block absent but prompt says SPREADSHEET → artifact detected."""
        raw = "Here is your data analysis."

        result = self.service.parse_output(
            raw, self._make_prompt(fmt=OutputFormat.SPREADSHEET)
        )

        assert result.has_artifact is True
        assert result.artifact_format == "xlsx"

    def test_fallback_artifact_pptx(self):
        raw = "Here are your slides."
        result = self.service.parse_output(
            raw, self._make_prompt(fmt=OutputFormat.PRESENTATION)
        )
        assert result.artifact_format == "pptx"

    def test_fallback_artifact_docx(self):
        raw = "Here is your document."
        result = self.service.parse_output(
            raw, self._make_prompt(fmt=OutputFormat.DOCUMENT)
        )
        assert result.artifact_format == "docx"


class TestContentBlockExtraction:
    """Test markdown → ContentBlock parsing."""

    def test_heading_extraction(self):
        blocks = OutputArchitectService._extract_content_blocks("## Section One\n\nSome text.")
        headings = [b for b in blocks if b.type == "heading"]
        assert len(headings) == 1
        assert headings[0].content == "Section One"
        assert headings[0].metadata["level"] == 2

    def test_table_extraction(self):
        md = "| Name | Value |\n| --- | --- |\n| A | 10 |\n| B | 20 |\n"
        blocks = OutputArchitectService._extract_content_blocks(md)
        tables = [b for b in blocks if b.type == "table"]
        assert len(tables) == 1
        assert tables[0].metadata["headers"] == ["Name", "Value"]
        assert len(tables[0].metadata["rows"]) == 2

    def test_list_extraction(self):
        md = "- Item one\n- Item two\n- Item three\n"
        blocks = OutputArchitectService._extract_content_blocks(md)
        lists = [b for b in blocks if b.type == "list"]
        assert len(lists) == 1
        assert "Item one" in lists[0].content

    def test_code_block_extraction(self):
        md = "```python\nprint('hello')\n```\n"
        blocks = OutputArchitectService._extract_content_blocks(md)
        codes = [b for b in blocks if b.type == "code"]
        assert len(codes) == 1
        assert codes[0].metadata["language"] == "python"

    def test_paragraph_extraction(self):
        blocks = OutputArchitectService._extract_content_blocks("Just a simple paragraph.")
        paragraphs = [b for b in blocks if b.type == "paragraph"]
        assert len(paragraphs) == 1


class TestOutputArchitectGenerate:
    """Test the full architect_output flow."""

    @pytest.mark.asyncio
    async def test_architect_output_success(self):
        formatted_response = """## Analysis

Revenue grew 15% [1].

```json
{"has_artifact": false, "artifact_format": null, "artifact_title": null, "summary": "Revenue analysis"}
```"""

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=formatted_response)

        service = OutputArchitectService(llm_client=mock_llm)
        prompt = StructuredPrompt(
            original_query="revenue analysis",
            enriched_query="detailed revenue analysis",
            intent=QueryIntent.ANALYTICAL,
            desired_format=OutputFormat.TEXT,
        )

        result = await service.architect_output("raw kimi output", prompt)

        assert isinstance(result, ArchitecturedOutput)
        assert result.summary == "Revenue analysis"
        assert result.has_artifact is False
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_architect_output(self):
        tokens = ["Hello", " World", "!"]

        mock_llm = AsyncMock()

        async def mock_stream(**_kwargs):
            for t in tokens:
                yield t

        mock_llm.stream = mock_stream

        service = OutputArchitectService(llm_client=mock_llm)
        prompt = StructuredPrompt(
            original_query="test",
            enriched_query="test",
            intent=QueryIntent.FACTUAL,
            desired_format=OutputFormat.TEXT,
        )

        collected = []
        async for token in service.stream_architect_output("raw output", prompt):
            collected.append(token)

        assert collected == tokens


class TestContentBlockModel:
    def test_to_dict(self):
        block = ContentBlock(
            type="heading",
            content="Test Heading",
            metadata={"level": 2},
        )
        d = block.to_dict()
        assert d["type"] == "heading"
        assert d["metadata"]["level"] == 2

    def test_architectured_output_to_dict(self):
        output = ArchitecturedOutput(
            formatted_content="# Test",
            content_blocks=[ContentBlock(type="heading", content="Test", metadata={"level": 1})],
            has_artifact=True,
            artifact_format="docx",
            artifact_title="My Doc",
            summary="A summary",
        )
        d = output.to_dict()
        assert d["hasArtifact"] is True
        assert d["artifactFormat"] == "docx"
        assert len(d["contentBlocks"]) == 1
