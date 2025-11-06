"""
Empire v7.3 - Chunking Service Tests
Test semantic, code, and transcript chunking strategies
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Dict, Any, List
import ast

# Import the service
import app.services.chunking_service as chunking_module
from app.services.chunking_service import (
    ChunkingStrategy,
    ChunkMetadata,
    Chunk,
    SemanticChunker,
    CodeChunker,
    TranscriptChunker,
    ChunkingService,
    get_chunking_service
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_document_text():
    """Sample document text for testing"""
    return """
    This is a sample document for testing semantic chunking.
    It contains multiple sentences and paragraphs.

    The first paragraph discusses the importance of text chunking in NLP systems.
    Proper chunking ensures that semantic context is preserved across chunks.

    The second paragraph explains different chunking strategies.
    Some strategies use fixed sizes, while others adapt to content boundaries.
    Semantic chunking is particularly useful for maintaining coherent text segments.

    The third paragraph concludes the discussion.
    Effective chunking improves retrieval accuracy in RAG systems.
    """


@pytest.fixture
def sample_python_code():
    """Sample Python code for testing AST chunking"""
    return '''
def hello_world():
    """Print hello world"""
    print("Hello, World!")

class Calculator:
    """Simple calculator class"""

    def add(self, a, b):
        """Add two numbers"""
        return a + b

    def subtract(self, a, b):
        """Subtract two numbers"""
        return a - b

    def multiply(self, a, b):
        """Multiply two numbers"""
        return a * b

async def fetch_data(url):
    """Fetch data from URL"""
    # Simulated async function
    return {"status": "success"}

def process_data(data):
    """Process the fetched data"""
    results = []
    for item in data:
        results.append(item * 2)
    return results
'''


@pytest.fixture
def sample_transcript():
    """Sample transcript with timestamps and speakers"""
    return [
        {"text": "Welcome to our discussion today.", "start": 0.0, "end": 2.5, "speaker": "Alice"},
        {"text": "We'll be talking about AI and machine learning.", "start": 2.5, "end": 5.0, "speaker": "Alice"},
        {"text": "That sounds great!", "start": 5.5, "end": 6.5, "speaker": "Bob"},
        {"text": "Let's start with the basics.", "start": 7.0, "end": 9.0, "speaker": "Alice"},
        {"text": "Machine learning is a subset of AI.", "start": 9.0, "end": 12.0, "speaker": "Alice"},
        {"text": "It involves training models on data.", "start": 12.0, "end": 15.0, "speaker": "Alice"},
        # Long pause
        {"text": "Can you give an example?", "start": 20.0, "end": 22.0, "speaker": "Bob"},
        {"text": "Sure! Image classification is a common example.", "start": 22.5, "end": 25.0, "speaker": "Alice"},
        {"text": "You train a model to recognize objects in images.", "start": 25.0, "end": 28.0, "speaker": "Alice"},
    ]


# ============================================================================
# Test ChunkMetadata and Chunk
# ============================================================================

class TestChunkDataClasses:
    """Test Chunk data structures"""

    def test_chunk_metadata_creation(self):
        """Test creating ChunkMetadata"""
        metadata = ChunkMetadata(
            chunk_index=0,
            source_document_id="doc-123",
            strategy=ChunkingStrategy.SEMANTIC,
            start_char=0,
            end_char=100
        )

        assert metadata.chunk_index == 0
        assert metadata.source_document_id == "doc-123"
        assert metadata.strategy == ChunkingStrategy.SEMANTIC
        assert metadata.start_char == 0
        assert metadata.end_char == 100

    def test_chunk_metadata_with_code_fields(self):
        """Test ChunkMetadata with code-specific fields"""
        metadata = ChunkMetadata(
            chunk_index=1,
            source_document_id="code-456",
            strategy=ChunkingStrategy.CODE_AST,
            language="python",
            function_names=["hello_world", "process_data"],
            class_names=["Calculator"]
        )

        assert metadata.language == "python"
        assert "hello_world" in metadata.function_names
        assert "Calculator" in metadata.class_names

    def test_chunk_to_dict(self):
        """Test converting Chunk to dictionary"""
        metadata = ChunkMetadata(
            chunk_index=0,
            source_document_id="doc-123",
            strategy=ChunkingStrategy.SEMANTIC,
            start_char=0,
            end_char=50
        )

        chunk = Chunk(content="Sample text chunk", metadata=metadata)
        chunk_dict = chunk.to_dict()

        assert chunk_dict["content"] == "Sample text chunk"
        assert chunk_dict["chunk_index"] == 0
        assert chunk_dict["source_document_id"] == "doc-123"
        assert chunk_dict["strategy"] == "semantic"
        assert chunk_dict["start_char"] == 0
        assert chunk_dict["end_char"] == 50


# ============================================================================
# Test Semantic Chunking (Subtask 13.1)
# ============================================================================

class TestSemanticChunker:
    """Test semantic and sentence-based chunking"""

    @pytest.mark.asyncio
    async def test_fallback_chunking_without_llamaindex(self, sample_document_text):
        """Test fallback chunking when LlamaIndex unavailable"""
        with patch('app.services.chunking_service.LLAMAINDEX_SUPPORT', False):
            chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)

            chunks = await chunker.chunk_document(
                text=sample_document_text,
                document_id="doc-123"
            )

            assert len(chunks) > 0
            assert all(isinstance(chunk, Chunk) for chunk in chunks)
            assert chunks[0].metadata.source_document_id == "doc-123"
            assert chunks[0].metadata.strategy == ChunkingStrategy.SENTENCE

    @pytest.mark.asyncio
    async def test_sentence_chunking_with_llamaindex(self, sample_document_text):
        """Test sentence-based chunking with LlamaIndex"""
        with patch('app.services.chunking_service.LLAMAINDEX_SUPPORT', True), \
             patch('app.services.chunking_service.SentenceSplitter', create=True) as MockSplitter, \
             patch('app.services.chunking_service.Document', create=True) as MockDocument:

            # Mock LlamaIndex components
            mock_node1 = MagicMock()
            mock_node1.text = "First chunk of text"
            mock_node1.start_char_idx = 0
            mock_node1.end_char_idx = 20

            mock_node2 = MagicMock()
            mock_node2.text = "Second chunk of text"
            mock_node2.start_char_idx = 20
            mock_node2.end_char_idx = 40

            mock_splitter = MockSplitter.return_value
            mock_splitter.get_nodes_from_documents.return_value = [mock_node1, mock_node2]

            chunker = SemanticChunker(chunk_size=1024, chunk_overlap=200)

            chunks = await chunker.chunk_document(
                text=sample_document_text,
                document_id="doc-456"
            )

            assert len(chunks) == 2
            assert chunks[0].content == "First chunk of text"
            assert chunks[1].content == "Second chunk of text"
            assert chunks[0].metadata.start_char == 0
            assert chunks[1].metadata.start_char == 20

    @pytest.mark.asyncio
    async def test_semantic_chunking_with_embeddings(self, sample_document_text):
        """Test semantic similarity-based chunking"""
        with patch('app.services.chunking_service.LLAMAINDEX_SUPPORT', True), \
             patch('app.services.chunking_service.SemanticSplitterNodeParser', create=True) as MockSplitter, \
             patch('app.services.chunking_service.Document', create=True):

            mock_node = MagicMock()
            mock_node.text = "Semantic chunk"
            mock_node.start_char_idx = 0
            mock_node.end_char_idx = 15

            MockSplitter.return_value.get_nodes_from_documents.return_value = [mock_node]

            mock_embed = MagicMock()
            chunker = SemanticChunker(
                chunk_size=1024,
                chunk_overlap=200,
                use_semantic=True,
                embed_model=mock_embed
            )

            chunks = await chunker.chunk_document(
                text=sample_document_text,
                document_id="doc-789"
            )

            assert len(chunks) > 0
            assert chunks[0].metadata.strategy == ChunkingStrategy.SEMANTIC

    @pytest.mark.asyncio
    async def test_chunking_preserves_overlap(self, sample_document_text):
        """Test that chunk overlap is preserved in metadata"""
        with patch('app.services.chunking_service.LLAMAINDEX_SUPPORT', False):
            chunker = SemanticChunker(chunk_size=50, chunk_overlap=10)

            chunks = await chunker.chunk_document(
                text=sample_document_text,
                document_id="doc-overlap"
            )

            # First chunk should have no overlap
            assert chunks[0].metadata.overlap_chars == 0

            # Subsequent chunks should have overlap
            if len(chunks) > 1:
                assert chunks[1].metadata.overlap_chars == 10


# ============================================================================
# Test Code Chunking (Subtask 13.2)
# ============================================================================

class TestCodeChunker:
    """Test AST-based code chunking"""

    @pytest.mark.asyncio
    async def test_python_code_ast_chunking(self, sample_python_code):
        """Test AST-based chunking for Python code"""
        chunker = CodeChunker(max_chunk_lines=20, chunk_overlap_lines=2)

        chunks = await chunker.chunk_code(
            code=sample_python_code,
            document_id="code-123",
            language="python"
        )

        assert len(chunks) > 0
        assert all(chunk.metadata.strategy == ChunkingStrategy.CODE_AST for chunk in chunks)
        assert all(chunk.metadata.language == "python" for chunk in chunks)

    @pytest.mark.asyncio
    async def test_code_chunking_extracts_functions(self, sample_python_code):
        """Test that function names are extracted"""
        chunker = CodeChunker(max_chunk_lines=100)

        chunks = await chunker.chunk_code(
            code=sample_python_code,
            document_id="code-456",
            language="python"
        )

        # Check that function names are captured
        all_functions = []
        for chunk in chunks:
            if chunk.metadata.function_names:
                all_functions.extend(chunk.metadata.function_names)

        assert "hello_world" in all_functions
        assert "fetch_data" in all_functions
        assert "process_data" in all_functions

    @pytest.mark.asyncio
    async def test_code_chunking_extracts_classes(self, sample_python_code):
        """Test that class names are extracted"""
        chunker = CodeChunker(max_chunk_lines=100)

        chunks = await chunker.chunk_code(
            code=sample_python_code,
            document_id="code-789",
            language="python"
        )

        # Check that class names are captured
        all_classes = []
        for chunk in chunks:
            if chunk.metadata.class_names:
                all_classes.extend(chunk.metadata.class_names)

        assert "Calculator" in all_classes

    @pytest.mark.asyncio
    async def test_code_chunking_preserves_line_numbers(self, sample_python_code):
        """Test that line numbers are tracked"""
        chunker = CodeChunker(max_chunk_lines=50)

        chunks = await chunker.chunk_code(
            code=sample_python_code,
            document_id="code-lines",
            language="python"
        )

        for chunk in chunks:
            assert chunk.metadata.start_line is not None
            assert chunk.metadata.end_line is not None
            assert chunk.metadata.end_line >= chunk.metadata.start_line

    @pytest.mark.asyncio
    async def test_code_chunking_invalid_syntax(self):
        """Test handling of invalid Python syntax"""
        invalid_code = """
def broken_function(
    # Missing closing parenthesis
    print("This won't parse")
"""
        chunker = CodeChunker()

        chunks = await chunker.chunk_code(
            code=invalid_code,
            document_id="code-invalid",
            language="python"
        )

        # Should fall back to line-based chunking
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_code_chunking_non_python_language(self, sample_python_code):
        """Test fallback for non-Python languages"""
        chunker = CodeChunker()

        chunks = await chunker.chunk_code(
            code=sample_python_code,
            document_id="code-js",
            language="javascript"  # Not supported
        )

        # Should fall back to line-based chunking
        assert len(chunks) > 0
        assert all(chunk.metadata.language == "javascript" for chunk in chunks)

    @pytest.mark.asyncio
    async def test_code_chunking_respects_size_limits(self):
        """Test that chunks respect maximum line limits"""
        # Create large code file
        large_code = "\n".join([
            f"def function_{i}():\n    pass\n"
            for i in range(100)
        ])

        chunker = CodeChunker(max_chunk_lines=50)

        chunks = await chunker.chunk_code(
            code=large_code,
            document_id="code-large",
            language="python"
        )

        # Each chunk should be under the line limit
        for chunk in chunks:
            lines = chunk.content.split('\n')
            assert len(lines) <= 50 + chunker.chunk_overlap_lines


# ============================================================================
# Test Transcript Chunking (Subtask 13.3)
# ============================================================================

class TestTranscriptChunker:
    """Test time and topic-based transcript chunking"""

    @pytest.mark.asyncio
    async def test_time_based_chunking(self, sample_transcript):
        """Test time-based transcript chunking"""
        chunker = TranscriptChunker(time_window_seconds=10.0, overlap_seconds=2.0)

        chunks = await chunker.chunk_transcript(
            transcript=sample_transcript,
            document_id="transcript-123",
            strategy="time"
        )

        assert len(chunks) > 0
        assert all(chunk.metadata.strategy == ChunkingStrategy.TRANSCRIPT_TIME for chunk in chunks)

    @pytest.mark.asyncio
    async def test_time_chunks_preserve_timestamps(self, sample_transcript):
        """Test that time chunks include start/end timestamps"""
        chunker = TranscriptChunker(time_window_seconds=15.0)

        chunks = await chunker.chunk_transcript(
            transcript=sample_transcript,
            document_id="transcript-456",
            strategy="time"
        )

        for chunk in chunks:
            assert chunk.metadata.start_time is not None
            assert chunk.metadata.end_time is not None
            assert chunk.metadata.end_time >= chunk.metadata.start_time

    @pytest.mark.asyncio
    async def test_time_chunks_preserve_speakers(self, sample_transcript):
        """Test that speaker information is preserved"""
        chunker = TranscriptChunker(time_window_seconds=20.0)

        chunks = await chunker.chunk_transcript(
            transcript=sample_transcript,
            document_id="transcript-789",
            strategy="time"
        )

        for chunk in chunks:
            assert chunk.metadata.speaker is not None
            assert isinstance(chunk.metadata.speaker, str)

    @pytest.mark.asyncio
    async def test_topic_based_chunking(self, sample_transcript):
        """Test topic-based transcript chunking"""
        chunker = TranscriptChunker(use_topic_detection=True)

        chunks = await chunker.chunk_transcript(
            transcript=sample_transcript,
            document_id="transcript-topic",
            strategy="topic"
        )

        assert len(chunks) > 0
        assert all(chunk.metadata.strategy == ChunkingStrategy.TRANSCRIPT_TOPIC for chunk in chunks)

    @pytest.mark.asyncio
    async def test_topic_chunks_detect_speaker_changes(self, sample_transcript):
        """Test that topic detection identifies speaker changes"""
        chunker = TranscriptChunker(use_topic_detection=True)

        chunks = await chunker.chunk_transcript(
            transcript=sample_transcript,
            document_id="transcript-speakers",
            strategy="topic"
        )

        # Should create chunks when speaker changes
        # (exact number depends on pauses and speaker changes)
        assert len(chunks) >= 2

    @pytest.mark.asyncio
    async def test_topic_chunks_include_topic_labels(self, sample_transcript):
        """Test that topic chunks have topic labels"""
        chunker = TranscriptChunker(use_topic_detection=True)

        chunks = await chunker.chunk_transcript(
            transcript=sample_transcript,
            document_id="transcript-labels",
            strategy="topic"
        )

        for chunk in chunks:
            assert chunk.metadata.topic is not None

    @pytest.mark.asyncio
    async def test_transcript_chunking_empty_transcript(self):
        """Test handling of empty transcript"""
        chunker = TranscriptChunker()

        chunks = await chunker.chunk_transcript(
            transcript=[],
            document_id="transcript-empty",
            strategy="time"
        )

        assert chunks == []

    @pytest.mark.asyncio
    async def test_transcript_chunking_single_segment(self):
        """Test chunking with single transcript segment"""
        single_segment = [
            {"text": "Single utterance", "start": 0.0, "end": 2.0, "speaker": "Alice"}
        ]

        chunker = TranscriptChunker(time_window_seconds=10.0)

        chunks = await chunker.chunk_transcript(
            transcript=single_segment,
            document_id="transcript-single",
            strategy="time"
        )

        assert len(chunks) == 1
        assert chunks[0].content == "Single utterance"


# ============================================================================
# Test Unified Chunking Service
# ============================================================================

class TestChunkingService:
    """Test the unified chunking service"""

    @pytest.mark.asyncio
    async def test_service_chunk_document(self, sample_document_text):
        """Test document chunking through unified service"""
        service = ChunkingService()

        chunks = await service.chunk_document(
            text=sample_document_text,
            document_id="doc-service",
            chunk_size=100,
            chunk_overlap=20
        )

        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

    @pytest.mark.asyncio
    async def test_service_chunk_code(self, sample_python_code):
        """Test code chunking through unified service"""
        service = ChunkingService()

        chunks = await service.chunk_code(
            code=sample_python_code,
            document_id="code-service",
            language="python",
            max_chunk_lines=50
        )

        assert len(chunks) > 0
        assert all(chunk.metadata.strategy == ChunkingStrategy.CODE_AST for chunk in chunks)

    @pytest.mark.asyncio
    async def test_service_chunk_transcript(self, sample_transcript):
        """Test transcript chunking through unified service"""
        service = ChunkingService()

        chunks = await service.chunk_transcript(
            transcript=sample_transcript,
            document_id="transcript-service",
            time_window_seconds=15.0,
            strategy="time"
        )

        assert len(chunks) > 0
        assert all(chunk.metadata.strategy == ChunkingStrategy.TRANSCRIPT_TIME for chunk in chunks)

    @pytest.mark.asyncio
    async def test_service_configurable_parameters(self, sample_document_text):
        """Test that service accepts configuration parameters"""
        service = ChunkingService()

        chunks_small = await service.chunk_document(
            text=sample_document_text,
            document_id="doc-small",
            chunk_size=50,
            chunk_overlap=10
        )

        chunks_large = await service.chunk_document(
            text=sample_document_text,
            document_id="doc-large",
            chunk_size=200,
            chunk_overlap=50
        )

        # Smaller chunks should create more chunks
        assert len(chunks_small) >= len(chunks_large)


# ============================================================================
# Test Singleton Pattern
# ============================================================================

class TestSingletonPattern:
    """Test singleton service instance"""

    def test_singleton_returns_same_instance(self):
        """Test that get_chunking_service returns singleton"""
        # Reset singleton
        chunking_module._chunking_service_instance = None

        service1 = get_chunking_service()
        service2 = get_chunking_service()

        assert service1 is service2

    def test_singleton_is_chunking_service(self):
        """Test that singleton is ChunkingService instance"""
        service = get_chunking_service()

        assert isinstance(service, ChunkingService)
        assert hasattr(service, 'semantic_chunker')
        assert hasattr(service, 'code_chunker')
        assert hasattr(service, 'transcript_chunker')
