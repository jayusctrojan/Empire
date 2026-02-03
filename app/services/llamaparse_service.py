"""
Empire v7.3 - LlamaParse Document Parsing Service

Unified PDF parsing layer using LlamaParse V1 API for reliable parsing:
- Standard mode: Clean PDFs (contracts, reports, statements with selectable text)
- Premium mode: Scanned/visually complex PDFs (bank statements, forms, dense layouts)

Output:
- Clean, normalized text suitable for RAG
- Structured tables (Markdown or JSON)
- Page and block-level metadata (page number, coordinates, section hierarchy)

NOTE: V1 API is used instead of V2 because V2 has unreliable result fetching.
V1 endpoint: https://api.cloud.llamaindex.ai/api/parsing

Author: Claude Code
Date: 2026-01-30
Updated: 2026-02-01 (reverted to V1 API for reliability)
"""

import os
import asyncio
import base64
import threading
import httpx
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class ParseMode(str, Enum):
    """LlamaParse parsing modes"""
    # Standard modes
    STANDARD = "parse_page_with_llm"           # Default - good for clean PDFs
    FAST = "parse_page_without_llm"            # Fastest, text-only

    # Advanced modes
    PREMIUM = "parse_page_with_agent"          # OCR + agentic reasoning (per page)
    PREMIUM_DOCUMENT = "parse_document_with_agent"  # Full document with agent
    MULTIMODAL = "parse_page_with_lvm"         # Vision model per page
    LAYOUT = "parse_page_with_layout_agent"    # Layout-aware with citations


class ParseTier(str, Enum):
    """LlamaParse API v2 tiers"""
    FAST = "fast"
    COST_EFFECTIVE = "cost_effective"
    AGENTIC = "agentic"
    AGENTIC_PLUS = "agentic_plus"


class ResultType(str, Enum):
    """Output format types"""
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"


@dataclass
class LlamaParseConfig:
    """Configuration for LlamaParse service"""

    # API configuration (V1 API for reliability)
    api_key: str = field(default_factory=lambda: os.getenv("LLAMA_CLOUD_API_KEY", ""))
    base_url: str = "https://api.cloud.llamaindex.ai/api/parsing"

    # Default parsing options
    default_mode: ParseMode = ParseMode.STANDARD
    default_tier: ParseTier = ParseTier.AGENTIC

    # Timeouts (seconds)
    upload_timeout: float = 60.0
    parse_timeout: float = 300.0  # 5 minutes for large docs
    poll_interval: float = 2.0

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0

    # Output options
    result_type: ResultType = ResultType.MARKDOWN
    output_tables_as_html: bool = False  # False = markdown tables
    include_page_metadata: bool = True
    include_coordinates: bool = True

    # OCR settings
    language: str = "en"
    disable_ocr: bool = False

    # Table handling
    merge_tables_across_pages: bool = True

    # Page formatting
    page_separator: str = "\n\n---\n\n"
    page_prefix: str = "## Page {pageNumber}\n\n"


# =============================================================================
# DOCUMENT COMPLEXITY DETECTION
# =============================================================================

@dataclass
class DocumentComplexity:
    """Assessment of document complexity for mode selection"""
    is_scanned: bool = False
    has_complex_tables: bool = False
    has_multi_column: bool = False
    has_images_with_text: bool = False
    has_handwriting: bool = False
    has_forms: bool = False
    page_count: int = 0
    estimated_text_density: float = 0.0  # 0-1, low = likely scanned
    recommended_mode: ParseMode = ParseMode.STANDARD
    confidence: float = 0.0


def detect_document_complexity(
    file_path: str,
    file_content: Optional[bytes] = None
) -> DocumentComplexity:
    """
    Analyze document to determine complexity and recommend parse mode.

    Heuristics:
    - Low text extraction from pypdf = likely scanned
    - Bank statement patterns = complex tables
    - Multi-column detection = complex layout

    Args:
        file_path: Path to PDF file
        file_content: Optional pre-loaded content

    Returns:
        DocumentComplexity assessment
    """
    result = DocumentComplexity()

    try:
        # Try quick pypdf extraction to assess text density
        from pypdf import PdfReader

        if file_content:
            from io import BytesIO
            reader = PdfReader(BytesIO(file_content))
        else:
            reader = PdfReader(file_path)

        result.page_count = len(reader.pages)

        # Sample first few pages to assess complexity
        sample_pages = min(3, result.page_count)
        total_chars = 0
        expected_chars_per_page = 2000  # Rough estimate for typical PDF

        for i in range(sample_pages):
            try:
                text = reader.pages[i].extract_text() or ""
                total_chars += len(text)

                # Check for table patterns (lots of numbers, aligned columns)
                lines = text.split('\n')
                numeric_lines = sum(1 for line in lines if sum(c.isdigit() for c in line) > len(line) * 0.3)
                if numeric_lines > len(lines) * 0.3:
                    result.has_complex_tables = True

                # Check for multi-column (short lines with consistent lengths)
                if lines:
                    avg_line_length = sum(len(line) for line in lines) / len(lines)
                    if avg_line_length < 60 and len(lines) > 20:
                        result.has_multi_column = True

            except Exception as e:
                logger.warning("Error sampling page", page=i, error=str(e))

        # Calculate text density
        result.estimated_text_density = total_chars / (sample_pages * expected_chars_per_page)

        # Determine if likely scanned
        if result.estimated_text_density < 0.1:
            result.is_scanned = True

        # Check filename patterns for document type hints
        filename = Path(file_path).stem.lower()
        bank_patterns = ['statement', 'bank', 'account', 'transaction', 'balance']
        form_patterns = ['form', 'application', 'w2', 'w-2', '1099', 'tax']

        if any(p in filename for p in bank_patterns):
            result.has_complex_tables = True
        if any(p in filename for p in form_patterns):
            result.has_forms = True

        # Recommend mode based on analysis
        if result.is_scanned or result.has_handwriting:
            result.recommended_mode = ParseMode.PREMIUM
            result.confidence = 0.9
        elif result.has_complex_tables or result.has_forms:
            result.recommended_mode = ParseMode.PREMIUM
            result.confidence = 0.8
        elif result.has_multi_column:
            result.recommended_mode = ParseMode.LAYOUT
            result.confidence = 0.7
        else:
            result.recommended_mode = ParseMode.STANDARD
            result.confidence = 0.85

        logger.info(
            "Document complexity assessed",
            file=file_path,
            is_scanned=result.is_scanned,
            has_complex_tables=result.has_complex_tables,
            recommended_mode=result.recommended_mode.value,
            confidence=result.confidence
        )

    except Exception as e:
        logger.warning("Complexity detection failed, defaulting to PREMIUM", error=str(e))
        result.recommended_mode = ParseMode.PREMIUM
        result.confidence = 0.5

    return result


# =============================================================================
# LLAMAPARSE SERVICE
# =============================================================================

class LlamaParseService:
    """
    LlamaParse document parsing service.

    Features:
    - Intelligent mode selection based on document complexity
    - Standard mode for clean PDFs (fast, cost-effective)
    - Premium mode for scanned/complex PDFs (OCR, agentic reasoning)
    - Structured output with tables, metadata, and page tracking
    - Retry logic with exponential backoff
    """

    def __init__(self, config: Optional[LlamaParseConfig] = None):
        """Initialize LlamaParse service"""
        self.config = config or LlamaParseConfig()
        self._client: Optional[httpx.AsyncClient] = None

        if not self.config.api_key:
            logger.warning("LLAMA_CLOUD_API_KEY not set - LlamaParse will not work")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=30.0,
                    read=self.config.parse_timeout,
                    write=self.config.upload_timeout,
                    pool=10.0
                )
            )
        return self._client

    async def close(self):
        """Close HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def parse_document(
        self,
        file_path: str,
        mode: Optional[ParseMode] = None,
        auto_detect_mode: bool = True,
        parsing_instructions: Optional[str] = None,
        extract_tables: bool = True,
        extract_images: bool = False,
        target_pages: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Parse a document using LlamaParse.

        Args:
            file_path: Path to document file
            mode: Parsing mode (auto-detected if not specified)
            auto_detect_mode: Auto-detect optimal mode based on document complexity
            parsing_instructions: Custom instructions for the parser
            extract_tables: Extract tables as structured data
            extract_images: Extract embedded images
            target_pages: Comma-separated page indices to parse (e.g., "0,1,2")
            **kwargs: Additional LlamaParse options

        Returns:
            {
                "success": True,
                "mode_used": "parse_page_with_agent",
                "complexity": {...},
                "content": {
                    "text": "Full extracted text...",
                    "markdown": "# Document\n\n...",
                    "pages": [
                        {
                            "page_number": 1,
                            "text": "...",
                            "markdown": "...",
                            "tables": [...],
                            "metadata": {...}
                        }
                    ],
                    "tables": [...],
                    "structure": {
                        "headings": [...],
                        "sections": [...]
                    }
                },
                "metadata": {
                    "page_count": 5,
                    "parse_time_seconds": 12.3,
                    "credits_used": 5
                },
                "errors": []
            }
        """
        start_time = datetime.utcnow()

        result = {
            "success": False,
            "mode_used": None,
            "complexity": None,
            "content": {
                "text": "",
                "markdown": "",
                "pages": [],
                "tables": [],
                "structure": {
                    "headings": [],
                    "sections": []
                }
            },
            "metadata": {
                "page_count": 0,
                "parse_time_seconds": 0,
                "credits_used": 0,
                "file_path": file_path,
                "timestamp": start_time.isoformat()
            },
            "errors": []
        }

        if not self.config.api_key:
            result["errors"].append("LLAMA_CLOUD_API_KEY not configured")
            return result

        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()

            filename = Path(file_path).name

            # Detect complexity and select mode
            if auto_detect_mode and mode is None:
                complexity = detect_document_complexity(file_path, file_content)
                result["complexity"] = {
                    "is_scanned": complexity.is_scanned,
                    "has_complex_tables": complexity.has_complex_tables,
                    "has_multi_column": complexity.has_multi_column,
                    "page_count": complexity.page_count,
                    "text_density": complexity.estimated_text_density,
                    "recommended_mode": complexity.recommended_mode.value,
                    "confidence": complexity.confidence
                }
                mode = complexity.recommended_mode
            else:
                mode = mode or self.config.default_mode

            result["mode_used"] = mode.value
            result["metadata"]["page_count"] = result.get("complexity", {}).get("page_count", 0)

            logger.info(
                "Starting LlamaParse",
                file=filename,
                mode=mode.value,
                auto_detected=auto_detect_mode
            )

            # Build parse options
            parse_options = self._build_parse_options(
                mode=mode,
                parsing_instructions=parsing_instructions,
                extract_tables=extract_tables,
                extract_images=extract_images,
                target_pages=target_pages,
                **kwargs
            )

            # Upload and parse
            job_id = await self._upload_document(file_content, filename, parse_options)

            if not job_id:
                result["errors"].append("Failed to upload document")
                return result

            # Poll for completion
            parse_result = await self._poll_for_result(job_id)

            if parse_result is None:
                result["errors"].append("Parse job failed or timed out")
                return result

            # Process result
            result["content"] = self._process_parse_result(parse_result)
            result["success"] = len(result["content"]["text"]) > 0

            # Update metadata
            end_time = datetime.utcnow()
            result["metadata"]["parse_time_seconds"] = (end_time - start_time).total_seconds()
            result["metadata"]["credits_used"] = parse_result.get("credits_used", 0)

            if "num_pages" in parse_result:
                result["metadata"]["page_count"] = parse_result["num_pages"]

            logger.info(
                "LlamaParse completed",
                file=filename,
                success=result["success"],
                pages=result["metadata"]["page_count"],
                chars=len(result["content"]["text"]),
                time_seconds=result["metadata"]["parse_time_seconds"]
            )

            return result

        except Exception as e:
            logger.exception("LlamaParse failed", error=str(e))
            result["errors"].append(str(e))
            return result

    def _build_parse_options(
        self,
        mode: ParseMode,
        parsing_instructions: Optional[str],
        extract_tables: bool,
        extract_images: bool,
        target_pages: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build LlamaParse V1 API options.

        V1 API uses premium_mode boolean instead of tiers.

        Note: extract_tables and extract_images parameters are accepted for API
        compatibility but are not used by V1 API (tables are auto-extracted in
        Premium mode). They are preserved here for potential future V2 migration.
        """
        # Log if callers pass unsupported options (for awareness during migration)
        if extract_tables or extract_images or kwargs:
            logger.debug(
                "V1 API ignores extract_tables/extract_images/kwargs",
                extract_tables=extract_tables,
                extract_images=extract_images,
                extra_kwargs=list(kwargs.keys()) if kwargs else None
            )

        # Determine if premium mode should be used
        use_premium = mode in [
            ParseMode.PREMIUM,
            ParseMode.PREMIUM_DOCUMENT,
            ParseMode.MULTIMODAL,
            ParseMode.LAYOUT
        ]

        # Build V1 options
        options = {
            "language": self.config.language,
        }

        if use_premium:
            options["premium_mode"] = True

        if parsing_instructions:
            options["parsing_instruction"] = parsing_instructions

        if target_pages:
            options["target_pages"] = target_pages

        logger.debug(
            "Built V1 parse options",
            premium_mode=use_premium,
            has_instructions=bool(parsing_instructions),
            has_target_pages=bool(target_pages)
        )

        return options

    async def _upload_document(
        self,
        file_content: bytes,
        filename: str,
        options: Dict[str, Any]
    ) -> Optional[str]:
        """
        Upload document to LlamaParse V1 API and get job ID.

        V1 API expects multipart form with:
        - file: The PDF file
        - Other options as form data fields
        """
        client = await self._get_client()

        # Prepare multipart upload with V1 format
        files = {
            "file": (filename, file_content, "application/pdf")
        }

        # V1 API expects options as form data
        data = {}
        for key, value in options.items():
            if isinstance(value, bool):
                data[key] = "true" if value else "false"
            else:
                data[key] = str(value)

        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(
                    f"{self.config.base_url}/upload",
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    files=files,
                    data=data,
                    timeout=self.config.upload_timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    job_id = result.get("id") or result.get("job_id")
                    logger.info(
                        "Document uploaded successfully",
                        job_id=job_id,
                        premium_mode=options.get("premium_mode", False)
                    )
                    return job_id
                else:
                    logger.warning(
                        "Upload failed",
                        attempt=attempt + 1,
                        status_code=response.status_code,
                        response_text=response.text
                    )

            except Exception as e:
                logger.warning("Upload error", attempt=attempt + 1, error=str(e))

            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

        return None

    async def _poll_for_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Poll for parse job completion using V1 API"""

        client = await self._get_client()
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        max_polls = int(self.config.parse_timeout / self.config.poll_interval)

        for _poll in range(max_polls):
            try:
                response = await client.get(
                    f"{self.config.base_url}/job/{job_id}",
                    headers=headers
                )

                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status", "").upper()

                    if status == "SUCCESS":
                        # Fetch full result with all content types
                        return await self._fetch_full_result(job_id, result)
                    elif status == "ERROR":
                        logger.error("Parse job failed", error=result.get('error', 'Unknown error'))
                        return None
                    # else: PENDING/processing, continue polling

            except Exception as e:
                logger.warning("Poll error", error=str(e))

            await asyncio.sleep(self.config.poll_interval)

        logger.error("Parse job timed out", timeout_seconds=self.config.parse_timeout)
        return None

    async def _fetch_full_result(
        self,
        job_id: str,
        job_status: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch complete parse result with all content types using V1 API.

        V1 API uses separate endpoints for each result type:
        - /job/{job_id}/result/text
        - /job/{job_id}/result/markdown
        """
        client = await self._get_client()
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        result = {
            "text": "",
            "markdown": "",
            "num_pages": job_status.get("num_pages", 0) if job_status else 0,
            "credits_used": job_status.get("credits_used", 0) if job_status else 0
        }

        try:
            # Fetch text result
            text_response = await client.get(
                f"{self.config.base_url}/job/{job_id}/result/text",
                headers=headers
            )
            if text_response.status_code == 200:
                text_data = text_response.json()
                result["text"] = text_data.get("text", "")

            # Fetch markdown result
            md_response = await client.get(
                f"{self.config.base_url}/job/{job_id}/result/markdown",
                headers=headers
            )
            if md_response.status_code == 200:
                md_data = md_response.json()
                result["markdown"] = md_data.get("markdown", "")

            logger.info(
                "Parse result fetched",
                job_id=job_id,
                num_pages=result.get("num_pages"),
                text_len=len(result.get("text", "")),
                markdown_len=len(result.get("markdown", ""))
            )
            return result

        except Exception as e:
            logger.exception("Failed to fetch result", error=str(e))
            # Return partial result if we have any content
            if result.get("text") or result.get("markdown"):
                result["fetch_error"] = str(e)
                return result

        return None

    def _process_parse_result(self, parse_result: Dict[str, Any]) -> Dict[str, Any]:
        """Process LlamaParse result into standardized format"""

        content = {
            "text": "",
            "markdown": "",
            "pages": [],
            "tables": [],
            "structure": {
                "headings": [],
                "sections": []
            }
        }

        # Extract text content
        content["text"] = parse_result.get("text", "")
        content["markdown"] = parse_result.get("markdown", content["text"])

        # Process pages if available
        pages_data = parse_result.get("pages", [])
        if not pages_data and parse_result.get("items"):
            pages_data = parse_result["items"]

        for page_idx, page in enumerate(pages_data):
            page_content = {
                "page_number": page.get("page_number", page_idx + 1),
                "text": page.get("text", ""),
                "markdown": page.get("markdown", page.get("text", "")),
                "tables": [],
                "metadata": {
                    "coordinates": page.get("bounding_box"),
                    "confidence": page.get("confidence")
                }
            }

            # Extract tables from page
            if "tables" in page:
                page_content["tables"] = page["tables"]
                content["tables"].extend(page["tables"])

            content["pages"].append(page_content)

        # Extract document structure (headings, sections)
        content["structure"] = self._extract_structure(content["markdown"])

        return content

    def _extract_structure(self, markdown: str) -> Dict[str, Any]:
        """Extract document structure from markdown"""

        structure = {
            "headings": [],
            "sections": []
        }

        if not markdown:
            return structure

        lines = markdown.split('\n')
        current_section = None

        for line_num, line in enumerate(lines):
            # Detect markdown headings
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                text = line.lstrip('#').strip()

                heading = {
                    "level": level,
                    "text": text,
                    "line_number": line_num + 1
                }
                structure["headings"].append(heading)

                # Track sections
                if level <= 2:
                    if current_section:
                        structure["sections"].append(current_section)
                    current_section = {
                        "title": text,
                        "level": level,
                        "start_line": line_num + 1,
                        "subsections": []
                    }
                elif current_section and level > 2:
                    current_section["subsections"].append({
                        "title": text,
                        "level": level,
                        "line_number": line_num + 1
                    })

        if current_section:
            structure["sections"].append(current_section)

        return structure

    async def parse_bank_statement(
        self,
        file_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Specialized parsing for bank statements.

        Uses Premium mode with table-focused instructions.

        Args:
            file_path: Path to bank statement PDF
            **kwargs: Additional parse options

        Returns:
            Parse result with structured transaction data
        """
        instructions = """
        This is a bank statement. Please:
        1. Extract all transactions with date, description, and amount columns clearly separated
        2. Identify deposits (credits) vs withdrawals (debits)
        3. Extract account summary (opening balance, closing balance, total credits/debits)
        4. Preserve the exact formatting of transaction descriptions
        5. Output tables in markdown format with proper column alignment
        6. Include page numbers for each transaction if visible
        """

        return await self.parse_document(
            file_path=file_path,
            mode=ParseMode.PREMIUM,
            auto_detect_mode=False,
            parsing_instructions=instructions,
            extract_tables=True,
            **kwargs
        )

    async def parse_financial_document(
        self,
        file_path: str,
        document_type: str = "general",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Specialized parsing for financial documents.

        Args:
            file_path: Path to document
            document_type: Type hint (invoice, receipt, tax_form, statement)
            **kwargs: Additional parse options

        Returns:
            Parse result with structured financial data
        """
        type_instructions = {
            "invoice": "Extract invoice number, date, line items with quantities and prices, tax, total due, and payment terms.",
            "receipt": "Extract merchant name, date, line items with prices, subtotal, tax, and total.",
            "tax_form": "Extract all form fields, checkboxes, and numerical values. Preserve field labels.",
            "statement": "Extract all transactions, balances, account numbers, and statement period.",
            "general": "Extract all tables, amounts, dates, and structured data. Preserve numerical precision."
        }

        instructions = type_instructions.get(document_type, type_instructions["general"])

        return await self.parse_document(
            file_path=file_path,
            mode=ParseMode.PREMIUM,
            auto_detect_mode=False,
            parsing_instructions=instructions,
            extract_tables=True,
            **kwargs
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_llamaparse_service: Optional[LlamaParseService] = None
_llamaparse_lock = threading.Lock()


def get_llamaparse_service(config: Optional[LlamaParseConfig] = None) -> LlamaParseService:
    """Get singleton LlamaParse service instance (thread-safe)"""
    global _llamaparse_service

    if _llamaparse_service is None:
        with _llamaparse_lock:
            # Double-checked locking
            if _llamaparse_service is None:
                _llamaparse_service = LlamaParseService(config)
    elif config is not None:
        logger.debug("LlamaParse singleton already exists; ignoring new config")

    return _llamaparse_service


async def close_llamaparse_service():
    """Close singleton LlamaParse service"""
    global _llamaparse_service

    if _llamaparse_service:
        await _llamaparse_service.close()
        _llamaparse_service = None
