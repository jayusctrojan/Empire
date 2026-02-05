"""
Empire v7.3 - Adaptive Chunking Strategy Service
Implement semantic, code, and transcript chunking with configurable size and overlap
"""

import os
import ast
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# LlamaIndex for semantic chunking
try:
    from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
    from llama_index.core.schema import Document, TextNode
    from llama_index.embeddings.openai import OpenAIEmbedding
    LLAMAINDEX_SUPPORT = True
except ImportError:
    LLAMAINDEX_SUPPORT = False
    logging.warning("LlamaIndex not available - install with: pip install llama-index")

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class ChunkingStrategy(str, Enum):
    """Available chunking strategies"""
    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    CODE_AST = "code_ast"
    TRANSCRIPT_TIME = "transcript_time"
    TRANSCRIPT_TOPIC = "transcript_topic"
    MARKDOWN = "markdown"


@dataclass
class ChunkMetadata:
    """Metadata for a chunk"""
    chunk_index: int
    source_document_id: str
    strategy: ChunkingStrategy
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    overlap_chars: int = 0

    # Code-specific metadata
    language: Optional[str] = None
    function_names: Optional[List[str]] = None
    class_names: Optional[List[str]] = None

    # Transcript-specific metadata
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speaker: Optional[str] = None
    topic: Optional[str] = None

    # Markdown-specific metadata
    section_header: Optional[str] = None
    header_level: Optional[int] = None
    header_hierarchy: Optional[Dict[str, str]] = None
    is_header_split: bool = True
    total_section_chunks: int = 1


@dataclass
class Chunk:
    """Represents a text chunk with metadata"""
    content: str
    metadata: ChunkMetadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for storage"""
        return {
            "content": self.content,
            "chunk_index": self.metadata.chunk_index,
            "source_document_id": self.metadata.source_document_id,
            "strategy": self.metadata.strategy.value,
            "start_char": self.metadata.start_char,
            "end_char": self.metadata.end_char,
            "start_line": self.metadata.start_line,
            "end_line": self.metadata.end_line,
            "overlap_chars": self.metadata.overlap_chars,
            "language": self.metadata.language,
            "function_names": self.metadata.function_names,
            "class_names": self.metadata.class_names,
            "start_time": self.metadata.start_time,
            "end_time": self.metadata.end_time,
            "speaker": self.metadata.speaker,
            "topic": self.metadata.topic,
            # Markdown-specific fields
            "section_header": self.metadata.section_header,
            "header_level": self.metadata.header_level,
            "header_hierarchy": self.metadata.header_hierarchy,
            "is_header_split": self.metadata.is_header_split,
            "total_section_chunks": self.metadata.total_section_chunks,
        }


# ============================================================================
# MARKDOWN CHUNKING DATA STRUCTURES
# ============================================================================

# Header detection regex pattern: matches # through ###### headers
HEADER_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


@dataclass
class MarkdownSection:
    """
    Represents a section of a markdown document delimited by headers.

    Attributes:
        header: Full header text including # markers (e.g., "## Methods")
        header_text: Header text without # markers (e.g., "Methods")
        level: Header level 1-6
        content: Section content including the header line
        start_line: Line number where section starts (0-indexed)
        end_line: Line number where section ends (0-indexed)
        parent_headers: List of parent header texts for hierarchy
    """
    header: str
    header_text: str
    level: int
    content: str
    start_line: int
    end_line: int
    parent_headers: List[str]


@dataclass
class MarkdownChunkerConfig:
    """
    Configuration for the MarkdownChunkerStrategy.

    Attributes:
        max_chunk_size: Maximum tokens per chunk (default 1024)
        chunk_overlap: Token overlap for sentence-split fallback (default 200)
        min_headers_threshold: Minimum headers to trigger markdown splitting (default 2)
        include_header_in_chunk: Whether to include header text in chunk content (default True)
        preserve_hierarchy: Whether to include parent headers in metadata (default True)
        max_header_length: Maximum characters for header text (default 200)
    """
    max_chunk_size: int = 1024
    chunk_overlap: int = 200
    min_headers_threshold: int = 2
    include_header_in_chunk: bool = True
    preserve_hierarchy: bool = True
    max_header_length: int = 200


# ============================================================================
# MARKDOWN CHUNKING STRATEGY (Feature 006)
# ============================================================================

class MarkdownChunkerStrategy:
    """
    Chunking strategy that splits markdown documents by headers.

    This strategy preserves semantic context by splitting at header boundaries
    instead of character counts. For sections exceeding max_chunk_size, it
    falls back to sentence-based splitting while preserving header metadata.

    Usage:
        chunker = MarkdownChunkerStrategy()
        nodes = await chunker.chunk(markdown_text, document_id="doc-123")
    """

    def __init__(self, config: Optional[MarkdownChunkerConfig] = None):
        """
        Initialize the markdown chunker.

        Args:
            config: Configuration options. Uses defaults if not provided.
        """
        self.config = config or MarkdownChunkerConfig()
        self._sentence_splitter = None

        if LLAMAINDEX_SUPPORT:
            self._sentence_splitter = SentenceSplitter(
                chunk_size=self.config.max_chunk_size,
                chunk_overlap=self.config.chunk_overlap
            )

    def is_markdown_content(self, text: str) -> bool:
        """
        Detect if text contains sufficient markdown headers for header-based splitting.

        Args:
            text: Document text to analyze

        Returns:
            True if text has >= min_headers_threshold markdown headers
        """
        headers = HEADER_PATTERN.findall(text)
        return len(headers) >= self.config.min_headers_threshold

    def _count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses a simple heuristic of ~4 characters per token as approximation.
        For production, consider using tiktoken for accurate counts.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Simple estimation: ~4 characters per token
        return len(text) // 4

    def _split_by_headers(self, text: str) -> List[MarkdownSection]:
        """
        Extract sections from markdown text based on headers.

        Args:
            text: Markdown document text

        Returns:
            List of MarkdownSection objects representing each section
        """
        sections = []
        lines = text.split('\n')
        current_section_start = 0
        current_header = ""
        current_header_text = ""
        current_level = 0
        header_stack: List[Tuple[int, str]] = []  # (level, header_text)

        for i, line in enumerate(lines):
            match = HEADER_PATTERN.match(line)
            if match:
                # Save previous section if exists
                if current_section_start < i or current_header:
                    section_content = '\n'.join(lines[current_section_start:i])
                    if section_content.strip():
                        # Build parent headers list
                        parent_headers = [h[1] for h in header_stack if h[0] < current_level]
                        sections.append(MarkdownSection(
                            header=current_header,
                            header_text=current_header_text,
                            level=current_level,
                            content=section_content,
                            start_line=current_section_start,
                            end_line=i - 1,
                            parent_headers=parent_headers
                        ))

                # Start new section
                hashes, header_text = match.groups()
                current_level = len(hashes)
                current_header = line
                current_header_text = header_text.strip()[:self.config.max_header_length]
                current_section_start = i

                # Update header stack
                while header_stack and header_stack[-1][0] >= current_level:
                    header_stack.pop()
                header_stack.append((current_level, current_header_text))

        # Add final section
        section_content = '\n'.join(lines[current_section_start:])
        if section_content.strip():
            parent_headers = [h[1] for h in header_stack[:-1]] if header_stack else []
            sections.append(MarkdownSection(
                header=current_header,
                header_text=current_header_text,
                level=current_level,
                content=section_content,
                start_line=current_section_start,
                end_line=len(lines) - 1,
                parent_headers=parent_headers
            ))

        return sections

    def _build_header_hierarchy(self, section: MarkdownSection) -> Dict[str, str]:
        """
        Build the header hierarchy dict for a section.

        Args:
            section: MarkdownSection to build hierarchy for

        Returns:
            Dict mapping h1, h2, etc. to header text
        """
        hierarchy = {}
        for i, parent in enumerate(section.parent_headers):
            hierarchy[f"h{i + 1}"] = parent
        if section.header_text:
            hierarchy[f"h{section.level}"] = section.header_text
        return hierarchy

    def _chunk_oversized_section(
        self,
        section: MarkdownSection,
        document_id: str,
        base_chunk_index: int
    ) -> List[Chunk]:
        """
        Split an oversized section using sentence-based chunking.

        Args:
            section: MarkdownSection that exceeds max_chunk_size
            document_id: Source document identifier
            base_chunk_index: Starting chunk index for numbering

        Returns:
            List of Chunk objects with preserved header metadata
        """
        if not self._sentence_splitter:
            # Fallback: simple character-based splitting
            content = section.content
            chunks = []
            chunk_size = self.config.max_chunk_size * 4  # Approximate chars
            for i in range(0, len(content), chunk_size - self.config.chunk_overlap * 4):
                chunk_text = content[i:i + chunk_size]
                if not chunk_text.strip():
                    continue
                chunks.append(Chunk(
                    content=chunk_text,
                    metadata=ChunkMetadata(
                        chunk_index=base_chunk_index + len(chunks),
                        source_document_id=document_id,
                        strategy=ChunkingStrategy.MARKDOWN,
                        start_line=section.start_line,
                        end_line=section.end_line,
                        section_header=section.header,
                        header_level=section.level,
                        header_hierarchy=self._build_header_hierarchy(section),
                        is_header_split=False,
                        total_section_chunks=0  # Will be updated after
                    )
                ))
            # Update total_section_chunks
            for chunk in chunks:
                chunk.metadata.total_section_chunks = len(chunks)
            return chunks

        # Use LlamaIndex SentenceSplitter
        if LLAMAINDEX_SUPPORT:
            doc = Document(text=section.content)
            nodes = self._sentence_splitter.get_nodes_from_documents([doc])
            chunks = []
            for node in nodes:
                chunks.append(Chunk(
                    content=node.text,
                    metadata=ChunkMetadata(
                        chunk_index=base_chunk_index + len(chunks),
                        source_document_id=document_id,
                        strategy=ChunkingStrategy.MARKDOWN,
                        start_line=section.start_line,
                        end_line=section.end_line,
                        section_header=section.header,
                        header_level=section.level,
                        header_hierarchy=self._build_header_hierarchy(section),
                        is_header_split=False,
                        total_section_chunks=len(nodes)
                    )
                ))
            return chunks

        return []

    async def chunk(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk markdown document by headers.

        Args:
            text: Markdown document text
            document_id: Source document identifier
            metadata: Additional metadata to attach to chunks

        Returns:
            List of Chunk objects with header-aware metadata
        """
        if not self.is_markdown_content(text):
            logger.info(
                "Text does not meet markdown threshold, using sentence splitting",
                doc_id=document_id,
                threshold=self.config.min_headers_threshold
            )
            # Fallback to sentence splitting
            if self._sentence_splitter and LLAMAINDEX_SUPPORT:
                doc = Document(text=text)
                nodes = self._sentence_splitter.get_nodes_from_documents([doc])
                return [
                    Chunk(
                        content=node.text,
                        metadata=ChunkMetadata(
                            chunk_index=i,
                            source_document_id=document_id,
                            strategy=ChunkingStrategy.SENTENCE,
                            is_header_split=False
                        )
                    )
                    for i, node in enumerate(nodes)
                ]
            return []

        # Split by headers
        sections = self._split_by_headers(text)
        logger.info(
            "Markdown document split by headers",
            doc_id=document_id,
            section_count=len(sections)
        )

        chunks = []
        chunk_index = 0

        for section in sections:
            token_count = self._count_tokens(section.content)

            if token_count > self.config.max_chunk_size:
                # Oversized section: use sentence splitting
                logger.debug(
                    "Section exceeds max_chunk_size, using sentence splitting",
                    extra={"header": section.header_text, "tokens": token_count}
                )
                section_chunks = self._chunk_oversized_section(
                    section, document_id, chunk_index
                )
                chunks.extend(section_chunks)
                chunk_index += len(section_chunks)
            else:
                # Section fits in one chunk
                hierarchy = self._build_header_hierarchy(section)
                chunks.append(Chunk(
                    content=section.content,
                    metadata=ChunkMetadata(
                        chunk_index=chunk_index,
                        source_document_id=document_id,
                        strategy=ChunkingStrategy.MARKDOWN,
                        start_line=section.start_line,
                        end_line=section.end_line,
                        section_header=section.header,
                        header_level=section.level,
                        header_hierarchy=hierarchy,
                        is_header_split=True,
                        total_section_chunks=1
                    )
                ))
                chunk_index += 1

        logger.info(
            "Markdown chunking complete",
            doc_id=document_id,
            total_chunks=len(chunks),
            header_split_chunks=sum(1 for c in chunks if c.metadata.is_header_split)
        )

        return chunks


# ============================================================================
# SUBTASK 13.1: Semantic Chunking for Documents
# ============================================================================

class SemanticChunker:
    """
    Semantic chunking for text documents using LlamaIndex.
    Supports both sentence-based and semantic similarity-based chunking.
    """

    def __init__(
        self,
        chunk_size: int = 1024,
        chunk_overlap: int = 200,
        use_semantic: bool = False,
        embed_model: Optional[Any] = None
    ):
        """
        Initialize semantic chunker.

        Args:
            chunk_size: Target size for chunks in tokens
            chunk_overlap: Overlap between chunks in tokens
            use_semantic: Use semantic similarity-based chunking
            embed_model: Embedding model for semantic chunking
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_semantic = use_semantic
        self.embed_model = embed_model

        if not LLAMAINDEX_SUPPORT:
            logger.warning("LlamaIndex not available - semantic chunking disabled")

    async def chunk_document(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk document using semantic strategy.

        Args:
            text: Document text to chunk
            document_id: Source document identifier
            metadata: Additional metadata to attach

        Returns:
            List of Chunk objects with metadata
        """
        if not LLAMAINDEX_SUPPORT:
            # Fallback to simple chunking
            return await self._fallback_chunking(text, document_id, metadata)

        try:
            # Create LlamaIndex document
            doc = Document(text=text, metadata=metadata or {})

            if self.use_semantic and self.embed_model:
                # Use semantic similarity-based chunking
                splitter = SemanticSplitterNodeParser(
                    buffer_size=1,
                    breakpoint_percentile_threshold=95,
                    embed_model=self.embed_model
                )
            else:
                # Use sentence-based chunking
                splitter = SentenceSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                )

            # Split document into nodes
            nodes = splitter.get_nodes_from_documents([doc])

            # Convert nodes to Chunk objects
            chunks = []
            for idx, node in enumerate(nodes):
                chunk_metadata = ChunkMetadata(
                    chunk_index=idx,
                    source_document_id=document_id,
                    strategy=ChunkingStrategy.SEMANTIC if self.use_semantic else ChunkingStrategy.SENTENCE,
                    start_char=node.start_char_idx,
                    end_char=node.end_char_idx,
                    overlap_chars=self.chunk_overlap if idx > 0 else 0
                )

                chunks.append(Chunk(
                    content=node.text,
                    metadata=chunk_metadata
                ))

            logger.info(f"Created {len(chunks)} semantic chunks from document {document_id}")
            return chunks

        except Exception as e:
            logger.error(f"Semantic chunking failed: {e}")
            return await self._fallback_chunking(text, document_id, metadata)

    async def _fallback_chunking(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Simple fallback chunking when LlamaIndex unavailable"""
        chunks = []
        text_length = len(text)
        start_idx = 0
        chunk_idx = 0

        # Ensure overlap is less than chunk size to avoid infinite loop
        effective_overlap = min(self.chunk_overlap, self.chunk_size - 1)

        while start_idx < text_length:
            end_idx = min(start_idx + self.chunk_size, text_length)
            chunk_text = text[start_idx:end_idx]

            chunk_metadata = ChunkMetadata(
                chunk_index=chunk_idx,
                source_document_id=document_id,
                strategy=ChunkingStrategy.SENTENCE,
                start_char=start_idx,
                end_char=end_idx,
                overlap_chars=effective_overlap if chunk_idx > 0 else 0
            )

            chunks.append(Chunk(
                content=chunk_text,
                metadata=chunk_metadata
            ))

            # Move forward, ensuring we always make progress
            if end_idx == text_length:
                break  # Reached the end
            start_idx = end_idx - effective_overlap
            chunk_idx += 1

        return chunks


# ============================================================================
# SUBTASK 13.2: Code Chunking Using AST Parsing
# ============================================================================

class CodeChunker:
    """
    AST-based code chunking that splits code into logical units
    (functions, classes, methods) while preserving context.
    """

    def __init__(
        self,
        max_chunk_lines: int = 100,
        chunk_overlap_lines: int = 5,
        include_docstrings: bool = True
    ):
        """
        Initialize code chunker.

        Args:
            max_chunk_lines: Maximum lines per chunk
            chunk_overlap_lines: Overlap in lines between chunks
            include_docstrings: Include docstrings in chunks
        """
        self.max_chunk_lines = max_chunk_lines
        self.chunk_overlap_lines = chunk_overlap_lines
        self.include_docstrings = include_docstrings

    async def chunk_code(
        self,
        code: str,
        document_id: str,
        language: str = "python",
        filename: Optional[str] = None
    ) -> List[Chunk]:
        """
        Chunk code using AST parsing.

        Args:
            code: Source code to chunk
            document_id: Source document identifier
            language: Programming language (currently supports "python")
            filename: Original filename (optional)

        Returns:
            List of Chunk objects with code metadata
        """
        if language.lower() != "python":
            logger.warning(f"AST chunking only supports Python, falling back for {language}")
            return await self._fallback_code_chunking(code, document_id, language)

        try:
            # Parse code into AST
            tree = ast.parse(code)

            # Extract top-level definitions
            code_units = self._extract_code_units(tree, code)

            # Group code units into chunks
            chunks = self._group_into_chunks(code_units, code, document_id, language)

            logger.info(f"Created {len(chunks)} AST-based code chunks from {filename or document_id}")
            return chunks

        except SyntaxError as e:
            logger.error(f"Code parsing failed: {e}")
            return await self._fallback_code_chunking(code, document_id, language)

    def _extract_code_units(self, tree: ast.AST, source_code: str) -> List[Dict[str, Any]]:
        """Extract functions, classes, and methods from AST"""
        code_units = []
        lines = source_code.split('\n')

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                unit = {
                    "type": "function",
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno or node.lineno,
                    "docstring": ast.get_docstring(node) if self.include_docstrings else None,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                }
                code_units.append(unit)

            elif isinstance(node, ast.ClassDef):
                unit = {
                    "type": "class",
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno or node.lineno,
                    "docstring": ast.get_docstring(node) if self.include_docstrings else None,
                    "methods": []
                }

                # Extract methods from class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        unit["methods"].append(item.name)

                code_units.append(unit)

        # Sort by line number
        code_units.sort(key=lambda x: x["start_line"])

        # Adjust end_line to include blank lines after each unit
        # This ensures accurate line counting for chunk size limits
        for i in range(len(code_units) - 1):
            # Extend end_line to just before next unit starts
            next_start = code_units[i + 1]["start_line"]
            code_units[i]["end_line"] = next_start - 1

        # For the last unit, extend to end of file if needed
        if code_units and len(lines) > 0:
            code_units[-1]["end_line"] = min(code_units[-1]["end_line"], len(lines))

        return code_units

    def _group_into_chunks(
        self,
        code_units: List[Dict[str, Any]],
        source_code: str,
        document_id: str,
        language: str
    ) -> List[Chunk]:
        """Group code units into chunks respecting size limits"""
        chunks = []
        lines = source_code.split('\n')
        current_chunk_units = []
        current_chunk_lines = 0
        chunk_idx = 0

        for unit in code_units:
            unit_lines = unit["end_line"] - unit["start_line"] + 1

            # Check if adding this unit exceeds max chunk size
            if current_chunk_lines + unit_lines > self.max_chunk_lines and current_chunk_units:
                # Create chunk from current units
                chunk = self._create_chunk_from_units(
                    current_chunk_units,
                    lines,
                    chunk_idx,
                    document_id,
                    language
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                current_chunk_units = self._get_overlap_units(current_chunk_units)
                current_chunk_lines = sum(
                    u["end_line"] - u["start_line"] + 1 for u in current_chunk_units
                )

                # If overlap + new unit exceeds limit, reduce overlap
                while current_chunk_units and current_chunk_lines + unit_lines > self.max_chunk_lines:
                    removed_unit = current_chunk_units.pop(0)
                    removed_lines = removed_unit["end_line"] - removed_unit["start_line"] + 1
                    current_chunk_lines -= removed_lines

                chunk_idx += 1

            current_chunk_units.append(unit)
            current_chunk_lines += unit_lines

        # Create final chunk
        if current_chunk_units:
            chunk = self._create_chunk_from_units(
                current_chunk_units,
                lines,
                chunk_idx,
                document_id,
                language
            )
            chunks.append(chunk)

        return chunks

    def _create_chunk_from_units(
        self,
        units: List[Dict[str, Any]],
        lines: List[str],
        chunk_idx: int,
        document_id: str,
        language: str
    ) -> Chunk:
        """Create a chunk from code units"""
        start_line = units[0]["start_line"] - 1  # Convert to 0-indexed
        end_line = units[-1]["end_line"]

        chunk_lines = lines[start_line:end_line]
        content = '\n'.join(chunk_lines)

        # Extract metadata
        function_names = [u["name"] for u in units if u["type"] == "function"]
        class_names = [u["name"] for u in units if u["type"] == "class"]

        chunk_metadata = ChunkMetadata(
            chunk_index=chunk_idx,
            source_document_id=document_id,
            strategy=ChunkingStrategy.CODE_AST,
            start_line=start_line + 1,  # Convert back to 1-indexed
            end_line=end_line,
            language=language,
            function_names=function_names if function_names else None,
            class_names=class_names if class_names else None,
            overlap_chars=0  # Will be calculated if there's overlap
        )

        return Chunk(content=content, metadata=chunk_metadata)

    def _get_overlap_units(self, units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get last few units for overlap"""
        total_lines = 0
        overlap_units = []

        for unit in reversed(units):
            unit_lines = unit["end_line"] - unit["start_line"] + 1
            if total_lines + unit_lines <= self.chunk_overlap_lines:
                overlap_units.insert(0, unit)
                total_lines += unit_lines
            else:
                break

        return overlap_units

    async def _fallback_code_chunking(
        self,
        code: str,
        document_id: str,
        language: str
    ) -> List[Chunk]:
        """Simple line-based chunking fallback"""
        chunks = []
        lines = code.split('\n')
        total_lines = len(lines)
        chunk_idx = 0
        start_line = 0

        # Ensure overlap is less than chunk size to avoid infinite loop
        effective_overlap = min(self.chunk_overlap_lines, self.max_chunk_lines - 1)

        while start_line < total_lines:
            end_line = min(start_line + self.max_chunk_lines, total_lines)
            chunk_lines = lines[start_line:end_line]
            content = '\n'.join(chunk_lines)

            chunk_metadata = ChunkMetadata(
                chunk_index=chunk_idx,
                source_document_id=document_id,
                strategy=ChunkingStrategy.CODE_AST,
                start_line=start_line + 1,
                end_line=end_line,
                language=language,
                overlap_chars=0
            )

            chunks.append(Chunk(content=content, metadata=chunk_metadata))

            # Move forward, ensuring we always make progress
            if end_line == total_lines:
                break  # Reached the end
            start_line = end_line - effective_overlap
            chunk_idx += 1

        return chunks


# ============================================================================
# SUBTASK 13.3: Time/Topic-Based Transcript Chunking
# ============================================================================

class TranscriptChunker:
    """
    Chunking for transcripts using time intervals or topic detection.
    Preserves speaker context and timestamps.
    """

    def __init__(
        self,
        time_window_seconds: float = 60.0,
        overlap_seconds: float = 5.0,
        use_topic_detection: bool = False
    ):
        """
        Initialize transcript chunker.

        Args:
            time_window_seconds: Duration of each time-based chunk
            overlap_seconds: Overlap between time-based chunks
            use_topic_detection: Use topic shifts instead of fixed time windows
        """
        self.time_window_seconds = time_window_seconds
        self.overlap_seconds = overlap_seconds
        self.use_topic_detection = use_topic_detection

    async def chunk_transcript(
        self,
        transcript: List[Dict[str, Any]],
        document_id: str,
        strategy: str = "time"
    ) -> List[Chunk]:
        """
        Chunk transcript by time or topic.

        Args:
            transcript: List of transcript segments with timestamps
                       Each segment: {"text": str, "start": float, "end": float, "speaker": str}
            document_id: Source document identifier
            strategy: "time" or "topic"

        Returns:
            List of Chunk objects with transcript metadata
        """
        if strategy == "topic" and self.use_topic_detection:
            return await self._chunk_by_topic(transcript, document_id)
        else:
            return await self._chunk_by_time(transcript, document_id)

    async def _chunk_by_time(
        self,
        transcript: List[Dict[str, Any]],
        document_id: str
    ) -> List[Chunk]:
        """Chunk transcript using fixed time windows"""
        chunks = []
        chunk_idx = 0

        if not transcript:
            return chunks

        # Sort by start time
        sorted_transcript = sorted(transcript, key=lambda x: x.get("start", 0))

        # Determine time range
        start_time = sorted_transcript[0].get("start", 0)
        end_time = sorted_transcript[-1].get("end", start_time)

        current_time = start_time

        while current_time < end_time:
            window_end = current_time + self.time_window_seconds

            # Get segments in this time window
            window_segments = [
                seg for seg in sorted_transcript
                if (seg.get("start", 0) >= current_time and
                    seg.get("start", 0) < window_end) or
                   (seg.get("end", 0) > current_time and
                    seg.get("end", 0) <= window_end)
            ]

            if window_segments:
                # Combine segments into chunk
                chunk_text = " ".join(seg.get("text", "") for seg in window_segments)
                speakers = list(set(seg.get("speaker", "Unknown") for seg in window_segments))

                chunk_start = window_segments[0].get("start", current_time)
                chunk_end = window_segments[-1].get("end", window_end)

                chunk_metadata = ChunkMetadata(
                    chunk_index=chunk_idx,
                    source_document_id=document_id,
                    strategy=ChunkingStrategy.TRANSCRIPT_TIME,
                    start_time=chunk_start,
                    end_time=chunk_end,
                    speaker=", ".join(speakers) if len(speakers) > 1 else speakers[0],
                    overlap_chars=0  # Time-based overlap
                )

                chunks.append(Chunk(content=chunk_text, metadata=chunk_metadata))
                chunk_idx += 1

            # Move to next window with overlap
            current_time = window_end - self.overlap_seconds

        logger.info(f"Created {len(chunks)} time-based transcript chunks")
        return chunks

    async def _chunk_by_topic(
        self,
        transcript: List[Dict[str, Any]],
        document_id: str
    ) -> List[Chunk]:
        """Chunk transcript using simple topic detection (speaker changes + pauses)"""
        chunks = []
        chunk_idx = 0

        if not transcript:
            return chunks

        # Sort by start time
        sorted_transcript = sorted(transcript, key=lambda x: x.get("start", 0))

        current_chunk_segments = []
        current_speaker = None
        last_end_time = 0

        for seg in sorted_transcript:
            speaker = seg.get("speaker", "Unknown")
            start_time = seg.get("start", 0)

            # Detect topic boundary: speaker change or long pause (>3 seconds)
            is_topic_boundary = (
                (current_speaker and speaker != current_speaker) or
                (start_time - last_end_time > 3.0)
            )

            if is_topic_boundary and current_chunk_segments:
                # Create chunk from current segments
                chunk = self._create_transcript_chunk(
                    current_chunk_segments,
                    chunk_idx,
                    document_id,
                    ChunkingStrategy.TRANSCRIPT_TOPIC
                )
                chunks.append(chunk)
                chunk_idx += 1
                current_chunk_segments = []

            current_chunk_segments.append(seg)
            current_speaker = speaker
            last_end_time = seg.get("end", start_time)

        # Create final chunk
        if current_chunk_segments:
            chunk = self._create_transcript_chunk(
                current_chunk_segments,
                chunk_idx,
                document_id,
                ChunkingStrategy.TRANSCRIPT_TOPIC
            )
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} topic-based transcript chunks")
        return chunks

    def _create_transcript_chunk(
        self,
        segments: List[Dict[str, Any]],
        chunk_idx: int,
        document_id: str,
        strategy: ChunkingStrategy
    ) -> Chunk:
        """Create a chunk from transcript segments"""
        chunk_text = " ".join(seg.get("text", "") for seg in segments)
        speakers = list(set(seg.get("speaker", "Unknown") for seg in segments))

        chunk_start = segments[0].get("start", 0)
        chunk_end = segments[-1].get("end", chunk_start)

        chunk_metadata = ChunkMetadata(
            chunk_index=chunk_idx,
            source_document_id=document_id,
            strategy=strategy,
            start_time=chunk_start,
            end_time=chunk_end,
            speaker=", ".join(speakers) if len(speakers) > 1 else speakers[0],
            topic=f"Topic {chunk_idx + 1}"  # Simple topic labeling
        )

        return Chunk(content=chunk_text, metadata=chunk_metadata)


# ============================================================================
# UNIFIED CHUNKING SERVICE
# ============================================================================

class ChunkingService:
    """
    Unified service for all chunking strategies.
    Provides a single interface for document, code, transcript, and markdown chunking.

    Feature 006: Added MarkdownChunkerStrategy for header-aware document splitting.
    """

    def __init__(self):
        """Initialize chunking service with default strategies"""
        self.semantic_chunker = SemanticChunker()
        self.code_chunker = CodeChunker()
        self.transcript_chunker = TranscriptChunker()
        self.markdown_chunker = MarkdownChunkerStrategy()

    async def chunk_document(
        self,
        text: str,
        document_id: str,
        chunk_size: int = 1024,
        chunk_overlap: int = 200,
        use_semantic: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Chunk a text document"""
        chunker = SemanticChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            use_semantic=use_semantic
        )
        return await chunker.chunk_document(text, document_id, metadata)

    async def chunk_code(
        self,
        code: str,
        document_id: str,
        language: str = "python",
        max_chunk_lines: int = 100,
        chunk_overlap_lines: int = 5
    ) -> List[Chunk]:
        """Chunk source code"""
        chunker = CodeChunker(
            max_chunk_lines=max_chunk_lines,
            chunk_overlap_lines=chunk_overlap_lines
        )
        return await chunker.chunk_code(code, document_id, language)

    async def chunk_transcript(
        self,
        transcript: List[Dict[str, Any]],
        document_id: str,
        time_window_seconds: float = 60.0,
        overlap_seconds: float = 5.0,
        strategy: str = "time"
    ) -> List[Chunk]:
        """Chunk a transcript"""
        chunker = TranscriptChunker(
            time_window_seconds=time_window_seconds,
            overlap_seconds=overlap_seconds,
            use_topic_detection=(strategy == "topic")
        )
        return await chunker.chunk_transcript(transcript, document_id, strategy)

    async def chunk_markdown(
        self,
        text: str,
        document_id: str,
        max_chunk_size: int = 1024,
        chunk_overlap: int = 200,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk markdown document by headers.

        Feature 006: Header-aware document splitting.

        Args:
            text: Markdown document text
            document_id: Source document identifier
            max_chunk_size: Maximum tokens per chunk
            chunk_overlap: Token overlap for oversized sections
            metadata: Additional metadata to attach

        Returns:
            List of Chunk objects with header-aware metadata
        """
        config = MarkdownChunkerConfig(
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunker = MarkdownChunkerStrategy(config=config)
        return await chunker.chunk(text, document_id, metadata)

    async def auto_chunk(
        self,
        text: str,
        document_id: str,
        chunk_size: int = 1024,
        chunk_overlap: int = 200,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Automatically select the best chunking strategy based on content.

        Feature 006: Auto-detects markdown and uses header-aware splitting.

        Args:
            text: Document text
            document_id: Source document identifier
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Token overlap between chunks
            metadata: Additional metadata to attach

        Returns:
            List of Chunk objects
        """
        # Check if content is markdown with sufficient headers
        if self.markdown_chunker.is_markdown_content(text):
            logger.info(
                "Auto-chunk: Using markdown strategy",
                extra={"document_id": document_id}
            )
            return await self.chunk_markdown(
                text, document_id, chunk_size, chunk_overlap, metadata
            )

        # Default to semantic/sentence chunking
        logger.info(
            "Auto-chunk: Using semantic strategy",
            extra={"document_id": document_id}
        )
        return await self.chunk_document(
            text, document_id, chunk_size, chunk_overlap, False, metadata
        )

    def get_strategy(self, strategy: ChunkingStrategy) -> Any:
        """
        Get a chunker instance by strategy type.

        Args:
            strategy: The chunking strategy enum value

        Returns:
            The corresponding chunker instance
        """
        strategy_map = {
            ChunkingStrategy.SEMANTIC: self.semantic_chunker,
            ChunkingStrategy.SENTENCE: self.semantic_chunker,
            ChunkingStrategy.CODE_AST: self.code_chunker,
            ChunkingStrategy.TRANSCRIPT_TIME: self.transcript_chunker,
            ChunkingStrategy.TRANSCRIPT_TOPIC: self.transcript_chunker,
            ChunkingStrategy.MARKDOWN: self.markdown_chunker,
        }
        return strategy_map.get(strategy, self.semantic_chunker)


# ============================================================================
# CHUNK FILTERING BY HEADER METADATA (Feature 006 - Task 119)
# ============================================================================

@dataclass
class ChunkFilter:
    """
    Filter criteria for chunks based on header metadata.

    Feature 006: Enables filtered search by section type using header metadata.

    Attributes:
        header_level: Filter by exact header level (1-6)
        header_levels: Filter by multiple header levels
        section_header: Filter by section header text (substring match)
        section_header_exact: Filter by exact section header text
        header_hierarchy_contains: Filter by text in header hierarchy
        is_header_split: Filter by whether chunk was header-split
        min_header_level: Filter by minimum header level (inclusive)
        max_header_level: Filter by maximum header level (inclusive)
    """
    header_level: Optional[int] = None
    header_levels: Optional[List[int]] = None
    section_header: Optional[str] = None
    section_header_exact: Optional[str] = None
    header_hierarchy_contains: Optional[str] = None
    is_header_split: Optional[bool] = None
    min_header_level: Optional[int] = None
    max_header_level: Optional[int] = None


def filter_chunks_by_header(
    chunks: List[Chunk],
    filter_criteria: ChunkFilter
) -> List[Chunk]:
    """
    Filter chunks based on header metadata criteria.

    Feature 006: Enables filtered search by section type.

    Args:
        chunks: List of Chunk objects to filter
        filter_criteria: ChunkFilter with criteria to apply

    Returns:
        List of chunks matching all specified criteria

    Example:
        >>> filtered = filter_chunks_by_header(chunks, ChunkFilter(header_level=2))
        >>> filtered = filter_chunks_by_header(chunks, ChunkFilter(section_header="Methods"))
    """
    result = chunks

    # Filter by exact header level
    if filter_criteria.header_level is not None:
        result = [
            c for c in result
            if c.metadata.header_level == filter_criteria.header_level
        ]

    # Filter by multiple header levels
    if filter_criteria.header_levels is not None:
        result = [
            c for c in result
            if c.metadata.header_level in filter_criteria.header_levels
        ]

    # Filter by section header substring
    if filter_criteria.section_header is not None:
        search_text = filter_criteria.section_header.lower()
        result = [
            c for c in result
            if c.metadata.section_header and
               search_text in c.metadata.section_header.lower()
        ]

    # Filter by exact section header
    if filter_criteria.section_header_exact is not None:
        result = [
            c for c in result
            if c.metadata.section_header == filter_criteria.section_header_exact
        ]

    # Filter by header hierarchy contains text
    if filter_criteria.header_hierarchy_contains is not None:
        search_text = filter_criteria.header_hierarchy_contains.lower()
        result = [
            c for c in result
            if c.metadata.header_hierarchy and
               any(search_text in v.lower() for v in c.metadata.header_hierarchy.values())
        ]

    # Filter by is_header_split flag
    if filter_criteria.is_header_split is not None:
        result = [
            c for c in result
            if c.metadata.is_header_split == filter_criteria.is_header_split
        ]

    # Filter by minimum header level
    if filter_criteria.min_header_level is not None:
        result = [
            c for c in result
            if c.metadata.header_level is not None and
               c.metadata.header_level >= filter_criteria.min_header_level
        ]

    # Filter by maximum header level
    if filter_criteria.max_header_level is not None:
        result = [
            c for c in result
            if c.metadata.header_level is not None and
               c.metadata.header_level <= filter_criteria.max_header_level
        ]

    return result


def filter_chunks_by_header_level(chunks: List[Chunk], level: int) -> List[Chunk]:
    """
    Convenience function to filter chunks by header level.

    Args:
        chunks: List of chunks to filter
        level: Header level (1-6)

    Returns:
        List of chunks with the specified header level
    """
    return filter_chunks_by_header(chunks, ChunkFilter(header_level=level))


def filter_chunks_by_section(chunks: List[Chunk], section_name: str) -> List[Chunk]:
    """
    Convenience function to filter chunks by section name.

    Args:
        chunks: List of chunks to filter
        section_name: Text to search for in section headers

    Returns:
        List of chunks with matching section headers
    """
    return filter_chunks_by_header(chunks, ChunkFilter(section_header=section_name))


def filter_chunks_by_hierarchy(chunks: List[Chunk], hierarchy_text: str) -> List[Chunk]:
    """
    Convenience function to filter chunks by header hierarchy.

    Args:
        chunks: List of chunks to filter
        hierarchy_text: Text to search for in header hierarchy

    Returns:
        List of chunks with matching hierarchy text
    """
    return filter_chunks_by_header(chunks, ChunkFilter(header_hierarchy_contains=hierarchy_text))


def get_chunks_under_header(
    chunks: List[Chunk],
    parent_header: str,
    include_parent: bool = True
) -> List[Chunk]:
    """
    Get all chunks that fall under a specific parent header.

    Args:
        chunks: List of chunks to filter
        parent_header: The parent header text to search for
        include_parent: Whether to include the parent header's chunk

    Returns:
        List of chunks under the specified parent header
    """
    result = []
    search_text = parent_header.lower()

    for chunk in chunks:
        # Check if this chunk's section_header matches the parent (is the parent itself)
        is_parent_chunk = (
            chunk.metadata.section_header and
            search_text in chunk.metadata.section_header.lower()
        )

        # Check if this chunk's hierarchy contains the parent
        has_parent_in_hierarchy = False
        if chunk.metadata.header_hierarchy:
            hierarchy_values = [v.lower() for v in chunk.metadata.header_hierarchy.values()]
            has_parent_in_hierarchy = any(search_text in v for v in hierarchy_values)

        # Include if:
        # 1. It's under the parent (has parent in hierarchy) AND either we include parent or it's not the parent chunk
        # 2. Or it's the parent chunk and we want to include parent
        if has_parent_in_hierarchy:
            if include_parent or not is_parent_chunk:
                result.append(chunk)
        elif include_parent and is_parent_chunk:
            result.append(chunk)

    return result


def group_chunks_by_header_level(chunks: List[Chunk]) -> Dict[int, List[Chunk]]:
    """
    Group chunks by their header level.

    Args:
        chunks: List of chunks to group

    Returns:
        Dictionary mapping header level to list of chunks
    """
    groups: Dict[int, List[Chunk]] = {}
    for chunk in chunks:
        level = chunk.metadata.header_level or 0
        if level not in groups:
            groups[level] = []
        groups[level].append(chunk)
    return groups


def group_chunks_by_section(chunks: List[Chunk]) -> Dict[str, List[Chunk]]:
    """
    Group chunks by their section header.

    Args:
        chunks: List of chunks to group

    Returns:
        Dictionary mapping section header to list of chunks
    """
    groups: Dict[str, List[Chunk]] = {}
    for chunk in chunks:
        section = chunk.metadata.section_header or "No Header"
        if section not in groups:
            groups[section] = []
        groups[section].append(chunk)
    return groups


# Singleton instance
_chunking_service_instance = None


def get_chunking_service() -> ChunkingService:
    """Get singleton instance of ChunkingService"""
    global _chunking_service_instance
    if _chunking_service_instance is None:
        _chunking_service_instance = ChunkingService()
    return _chunking_service_instance
