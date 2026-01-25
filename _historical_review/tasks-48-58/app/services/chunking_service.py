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
        }


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
    Provides a single interface for document, code, and transcript chunking.
    """

    def __init__(self):
        """Initialize chunking service with default strategies"""
        self.semantic_chunker = SemanticChunker()
        self.code_chunker = CodeChunker()
        self.transcript_chunker = TranscriptChunker()

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


# Singleton instance
_chunking_service_instance = None


def get_chunking_service() -> ChunkingService:
    """Get singleton instance of ChunkingService"""
    global _chunking_service_instance
    if _chunking_service_instance is None:
        _chunking_service_instance = ChunkingService()
    return _chunking_service_instance
