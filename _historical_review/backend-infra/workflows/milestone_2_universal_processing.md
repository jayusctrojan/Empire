## 3. Milestone 2: Text Extraction and Chunking

### 3.1 Supabase Schema

```sql
-- =====================================================
-- MILESTONE 2: Text Extraction and Chunking
-- =====================================================

-- Document chunks table for text extraction
CREATE TABLE IF NOT EXISTS public.document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    metadata JSONB DEFAULT '{}',
    embedding vector(1024), -- BGE-M3 embedding dimension
    embedding_model VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index),
    FOREIGN KEY (document_id) REFERENCES public.documents(document_id) ON DELETE CASCADE
);

-- Indexes for chunks table
CREATE INDEX idx_chunks_document_id ON public.document_chunks(document_id);
CREATE INDEX idx_chunks_content_hash ON public.document_chunks(content_hash);
CREATE INDEX idx_chunks_content_trgm ON public.document_chunks USING gin(content gin_trgm_ops);

-- Vector index (will be created after embeddings are added)
-- CREATE INDEX idx_chunks_embedding_hnsw ON public.document_chunks
--     USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);

-- Extraction metadata table
CREATE TABLE IF NOT EXISTS public.extraction_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL,
    extraction_method VARCHAR(50) NOT NULL,
    total_pages INTEGER,
    total_characters INTEGER,
    total_words INTEGER,
    extraction_duration_ms INTEGER,
    extraction_success BOOLEAN DEFAULT TRUE,
    extraction_error TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (document_id) REFERENCES public.documents(document_id) ON DELETE CASCADE
);

-- Index for extraction metadata
CREATE INDEX idx_extraction_metadata_document_id ON public.extraction_metadata(document_id);

-- Chunking metadata table
CREATE TABLE IF NOT EXISTS public.chunking_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    chunk_count INTEGER NOT NULL,
    average_chunk_size INTEGER,
    chunking_config JSONB DEFAULT '{}',
    chunking_duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (document_id) REFERENCES public.documents(document_id) ON DELETE CASCADE
);

-- Index for chunking metadata
CREATE INDEX idx_chunking_metadata_document_id ON public.chunking_metadata(document_id);
```

### 3.2 Text Extraction Service

```python
# app/services/text_extractor.py
from typing import Dict, List, Any, Optional
import io
from datetime import datetime
import PyPDF2
import docx
import pandas as pd
from PIL import Image
import httpx

from app.core.config import settings

class TextExtractionService:
    """
    Unified text extraction service for all document types.

    Supports:
    - PDF documents
    - Word documents (docx)
    - Excel spreadsheets
    - PowerPoint presentations
    - Plain text files
    - CSV files
    - Images (via OCR)
    - Audio/Video (via transcription)
    """

    def __init__(self):
        self.extraction_methods = {
            'pdf': self.extract_pdf,
            'word': self.extract_word,
            'excel': self.extract_excel,
            'powerpoint': self.extract_powerpoint,
            'text': self.extract_text,
            'markdown': self.extract_text,
            'html': self.extract_text,
            'csv': self.extract_csv,
            'json': self.extract_json,
            'image': self.extract_ocr,
            'audio': self.extract_transcription,
            'video': self.extract_transcription
        }

    async def extract(self, file_data: bytes, category: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract text from document based on category.

        Args:
            file_data: Binary file content
            category: Document category (pdf, word, etc.)
            metadata: Document metadata

        Returns:
            Dict with extracted text and statistics
        """
        start_time = datetime.utcnow()

        extraction_method = self.extraction_methods.get(category, self.extract_generic)
        result = await extraction_method(file_data, metadata)

        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        result['extraction_duration_ms'] = duration_ms
        result['extraction_timestamp'] = end_time.isoformat()

        return result

    async def extract_pdf(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from PDF documents."""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            pages = []
            full_text = ""

            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                pages.append({
                    'page_number': page_num,
                    'text': text,
                    'char_count': len(text),
                    'word_count': len(text.split())
                })
                full_text += f"\n[Page {page_num}]\n{text}\n"

            return {
                'success': True,
                'full_text': full_text,
                'pages': pages,
                'total_pages': len(pages),
                'total_characters': len(full_text),
                'total_words': len(full_text.split()),
                'extraction_method': 'PyPDF2'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'PyPDF2'
            }

    async def extract_word(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from Word documents."""
        try:
            doc = docx.Document(io.BytesIO(file_data))
            full_text = []
            paragraphs = []

            for i, para in enumerate(doc.paragraphs):
                if para.text.strip():
                    full_text.append(para.text)
                    paragraphs.append({
                        'index': i,
                        'text': para.text,
                        'style': para.style.name if para.style else None,
                        'char_count': len(para.text),
                        'word_count': len(para.text.split())
                    })

            # Extract tables
            tables = []
            for table_idx, table in enumerate(doc.tables):
                table_data = []
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    table_data.append(row_data)
                tables.append({
                    'index': table_idx,
                    'data': table_data,
                    'rows': len(table.rows),
                    'columns': len(table.columns)
                })

            combined_text = '\n\n'.join(full_text)

            return {
                'success': True,
                'full_text': combined_text,
                'paragraphs': paragraphs,
                'tables': tables,
                'total_characters': len(combined_text),
                'total_words': len(combined_text.split()),
                'extraction_method': 'python-docx'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'python-docx'
            }

    async def extract_excel(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from Excel files."""
        try:
            excel_file = pd.ExcelFile(io.BytesIO(file_data))
            sheets_data = {}

            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)

                sheets_data[sheet_name] = {
                    'rows': df.to_dict('records'),
                    'columns': df.columns.tolist(),
                    'row_count': len(df),
                    'column_count': len(df.columns),
                    'summary': df.describe().to_dict() if df.select_dtypes(include='number').shape[1] > 0 else {}
                }

            # Create text representation for search
            text_parts = []
            for sheet_name, sheet_data in sheets_data.items():
                text_parts.append(f"[Sheet: {sheet_name}]")
                for row in sheet_data['rows']:
                    text_parts.append(' | '.join(str(v) for v in row.values()))

            full_text = '\n'.join(text_parts)

            return {
                'success': True,
                'full_text': full_text,
                'sheets': sheets_data,
                'sheet_count': len(sheets_data),
                'total_characters': len(full_text),
                'total_words': len(full_text.split()),
                'extraction_method': 'pandas'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'pandas'
            }

    async def extract_powerpoint(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from PowerPoint presentations."""
        try:
            from pptx import Presentation

            prs = Presentation(io.BytesIO(file_data))
            slides = []
            full_text = []

            for slide_num, slide in enumerate(prs.slides, 1):
                slide_text = []
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        slide_text.append(shape.text)

                slide_content = '\n'.join(slide_text)
                slides.append({
                    'slide_number': slide_num,
                    'text': slide_content,
                    'char_count': len(slide_content),
                    'word_count': len(slide_content.split())
                })
                full_text.append(f"[Slide {slide_num}]\n{slide_content}")

            combined_text = '\n\n'.join(full_text)

            return {
                'success': True,
                'full_text': combined_text,
                'slides': slides,
                'total_slides': len(slides),
                'total_characters': len(combined_text),
                'total_words': len(combined_text.split()),
                'extraction_method': 'python-pptx'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'python-pptx'
            }

    async def extract_text(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from plain text files."""
        try:
            text = file_data.decode('utf-8')
            lines = text.split('\n')

            return {
                'success': True,
                'full_text': text,
                'lines': lines,
                'line_count': len(lines),
                'total_characters': len(text),
                'total_words': len(text.split()),
                'extraction_method': 'direct'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'direct'
            }

    async def extract_csv(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from CSV files."""
        try:
            df = pd.read_csv(io.BytesIO(file_data))

            # Create text representation
            text_parts = []
            text_parts.append(' | '.join(df.columns.tolist()))
            for _, row in df.iterrows():
                text_parts.append(' | '.join(str(v) for v in row.values))

            full_text = '\n'.join(text_parts)

            return {
                'success': True,
                'full_text': full_text,
                'data': df.to_dict('records'),
                'columns': df.columns.tolist(),
                'row_count': len(df),
                'column_count': len(df.columns),
                'total_characters': len(full_text),
                'total_words': len(full_text.split()),
                'extraction_method': 'pandas-csv'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'pandas-csv'
            }

    async def extract_json(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from JSON files."""
        try:
            import json

            data = json.loads(file_data.decode('utf-8'))

            # Create text representation
            full_text = json.dumps(data, indent=2)

            return {
                'success': True,
                'full_text': full_text,
                'data': data,
                'total_characters': len(full_text),
                'total_words': len(full_text.split()),
                'extraction_method': 'json'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'json'
            }

    async def extract_ocr(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from images using OCR."""
        if not settings.MISTRAL_API_KEY:
            return {
                'success': False,
                'error': 'OCR not configured (missing Mistral API key)',
                'extraction_method': 'mistral-ocr'
            }

        try:
            # Use Mistral Pixtral for OCR
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://api.mistral.ai/v1/ocr',
                    headers={'Authorization': f'Bearer {settings.MISTRAL_API_KEY}'},
                    json={
                        'image': file_data.hex(),
                        'model': 'pixtral-12b-2024-09-04',
                        'extract_text': True,
                        'extract_tables': True,
                        'extract_layout': True
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    full_text = result.get('text', '')

                    return {
                        'success': True,
                        'full_text': full_text,
                        'tables': result.get('tables', []),
                        'layout': result.get('layout', {}),
                        'total_characters': len(full_text),
                        'total_words': len(full_text.split()),
                        'extraction_method': 'mistral-ocr'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'OCR API error: {response.status_code}',
                        'extraction_method': 'mistral-ocr'
                    }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extraction_method': 'mistral-ocr'
            }

    async def extract_transcription(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from audio/video using transcription."""
        # Placeholder for future Soniox or Whisper integration
        return {
            'success': False,
            'error': 'Transcription not yet implemented',
            'extraction_method': 'transcription'
        }

    async def extract_generic(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generic extraction fallback."""
        return {
            'success': False,
            'error': 'No extraction method available for this file type',
            'extraction_method': 'none'
        }
```

### 3.3 Chunking Service

```python
# app/services/chunking.py
import hashlib
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.config import settings

class ChunkingService:
    """
    Intelligent text chunking service with multiple strategies.

    Supports:
    - Sentence-based chunking
    - Paragraph-based chunking
    - Character-based chunking
    - Smart overlap for context preservation
    - Document type detection
    """

    def __init__(self):
        self.chunking_configs = {
            'default': {
                'max_chunk_size': settings.CHUNK_SIZE,
                'overlap': settings.CHUNK_OVERLAP,
                'preserve_sentences': True,
                'preserve_paragraphs': False,
                'min_chunk_size': 100
            },
            'technical': {
                'max_chunk_size': 1500,
                'overlap': 300,
                'preserve_sentences': True,
                'preserve_paragraphs': True,
                'min_chunk_size': 200,
                'preserve_code_blocks': True
            },
            'narrative': {
                'max_chunk_size': 2000,
                'overlap': 400,
                'preserve_sentences': True,
                'preserve_paragraphs': True,
                'min_chunk_size': 500
            },
            'structured': {
                'max_chunk_size': 800,
                'overlap': 100,
                'preserve_sentences': False,
                'preserve_paragraphs': False,
                'min_chunk_size': 50,
                'preserve_tables': True
            }
        }

    def detect_document_type(self, text: str) -> str:
        """Detect document type based on content patterns."""
        code_patterns = r'```|function|class|import|export|const|let|var|def |if __name__|public class'
        technical_patterns = r'API|SDK|HTTP|JSON|XML|database|server|client|endpoint|request|response'
        narrative_patterns = r'chapter|section|paragraph|story|narrative|once upon|he said|she said'
        structured_patterns = r'\||,{3,}|;{3,}|\t{2,}'

        code_score = len(re.findall(code_patterns, text, re.IGNORECASE))
        technical_score = len(re.findall(technical_patterns, text, re.IGNORECASE))
        narrative_score = len(re.findall(narrative_patterns, text, re.IGNORECASE))
        structured_score = len(re.findall(structured_patterns, text))

        scores = {
            'technical': code_score + technical_score,
            'narrative': narrative_score,
            'structured': structured_score,
            'default': 1
        }

        return max(scores, key=scores.get)

    def create_chunks(self, text: str, document_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Create intelligent chunks from text.

        Args:
            text: Full text to chunk
            document_type: Optional document type (auto-detected if not provided)

        Returns:
            Dict with chunks and metadata
        """
        start_time = datetime.utcnow()

        if not document_type:
            document_type = self.detect_document_type(text)

        config = self.chunking_configs.get(document_type, self.chunking_configs['default'])
        chunks = []

        # Pre-process text
        processed_text = text
        code_blocks = []
        tables = []

        # Preserve code blocks if needed
        if config.get('preserve_code_blocks'):
            def replace_code_block(match):
                code_blocks.append(match.group())
                return f'[CODE_BLOCK_{len(code_blocks) - 1}]'
            processed_text = re.sub(r'```[\s\S]*?```', replace_code_block, processed_text)

        # Preserve tables if needed
        if config.get('preserve_tables'):
            def replace_table(match):
                tables.append(match.group())
                return f'[TABLE_{len(tables) - 1}]'
            processed_text = re.sub(r'\|[^\n]+\|(?:\n\|[^\n]+\|)+', replace_table, processed_text)

        # Split into segments based on config
        if config['preserve_paragraphs']:
            segments = re.split(r'\n\n+', processed_text)
        elif config['preserve_sentences']:
            segments = re.split(r'(?<=[.!?])\s+', processed_text)
        else:
            # Character-based splitting
            segments = [processed_text[i:i+config['max_chunk_size']]
                       for i in range(0, len(processed_text), config['max_chunk_size'] - config['overlap'])]

        # Create chunks from segments
        current_chunk = ''
        chunk_index = 0

        for segment in segments:
            segment_len = len(segment)

            if len(current_chunk) + segment_len <= config['max_chunk_size']:
                current_chunk += (' ' if current_chunk else '') + segment
            else:
                # Save current chunk
                if len(current_chunk) >= config['min_chunk_size']:
                    final_chunk = self._restore_placeholders(current_chunk, code_blocks, tables)
                    chunks.append(self.create_chunk_object(final_chunk, chunk_index))
                    chunk_index += 1

                # Start new chunk with overlap
                if config['overlap'] > 0 and chunks:
                    overlap_text = current_chunk[-config['overlap']:]
                    current_chunk = overlap_text + ' ' + segment
                else:
                    current_chunk = segment

        # Add final chunk
        if current_chunk and len(current_chunk) >= config['min_chunk_size']:
            final_chunk = self._restore_placeholders(current_chunk, code_blocks, tables)
            chunks.append(self.create_chunk_object(final_chunk, chunk_index))

        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return {
            'chunks': chunks,
            'metadata': {
                'document_type': document_type,
                'config': config,
                'total_chunks': len(chunks),
                'average_chunk_size': sum(c['size'] for c in chunks) / len(chunks) if chunks else 0,
                'chunking_duration_ms': duration_ms
            }
        }

    def _restore_placeholders(self, text: str, code_blocks: List[str], tables: List[str]) -> str:
        """Restore code blocks and tables from placeholders."""
        for i, code_block in enumerate(code_blocks):
            text = text.replace(f'[CODE_BLOCK_{i}]', code_block)
        for i, table in enumerate(tables):
            text = text.replace(f'[TABLE_{i}]', table)
        return text

    def create_chunk_object(self, content: str, index: int) -> Dict[str, Any]:
        """Create a chunk object with metadata."""
        chunk_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        return {
            'index': index,
            'content': content,
            'size': len(content),
            'word_count': len(content.split()),
            'hash': chunk_hash,
            'metadata': {
                'has_code': '```' in content,
                'has_table': '|' in content and content.count('|') > 2,
                'has_list': bool(re.search(r'^[\s]*[-*+\d]+\.?\s', content, re.MULTILINE)),
                'has_quote': '>' in content,
                'has_url': bool(re.search(r'https?://', content)),
                'has_email': bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content))
            }
        }

    async def save_chunks(self, document_id: str, chunks: List[Dict[str, Any]], supabase_client) -> Dict[str, Any]:
        """Save chunks to database."""
        try:
            chunk_records = []
            for chunk in chunks:
                chunk_records.append({
                    'document_id': document_id,
                    'chunk_index': chunk['index'],
                    'content': chunk['content'],
                    'content_length': chunk['size'],
                    'content_hash': chunk['hash'],
                    'metadata': chunk['metadata']
                })

            # Batch insert
            result = supabase_client.table('document_chunks').upsert(
                chunk_records,
                on_conflict='document_id,chunk_index'
            ).execute()

            return {
                'success': True,
                'chunks_saved': len(chunks)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
```

### 3.4 Celery Task for Text Processing

```python
# app/tasks/celery_tasks.py
from celery import Celery
from typing import Dict, Any
import asyncio

from app.core.config import settings
from app.services.text_extractor import TextExtractionService
from app.services.chunking import ChunkingService
from app.db.supabase import get_supabase_client

celery_app = Celery(
    'empire_tasks',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task(name='process_document_text_extraction')
def process_document_text_extraction(document_id: str) -> Dict[str, Any]:
    """
    Process document text extraction and chunking.

    This is a Celery task that runs asynchronously.
    """
    try:
        # Initialize services
        supabase = get_supabase_client()
        extractor = TextExtractionService()
        chunker = ChunkingService()

        # Get document from database
        doc_result = supabase.table('documents').select('*').eq(
            'document_id', document_id
        ).single().execute()

        if not doc_result.data:
            return {'success': False, 'error': 'Document not found'}

        document = doc_result.data

        # Update status to processing
        supabase.table('documents').update({
            'processing_status': 'extracting_text',
            'processing_started_at': 'now()'
        }).eq('document_id', document_id).execute()

        # Download file from B2
        from app.services.document_processor import DocumentProcessingPipeline
        processor = DocumentProcessingPipeline()
        bucket = processor.b2_api.get_bucket_by_name(settings.B2_BUCKET_NAME)
        file_data = bucket.download_file_by_name(document['storage_path']).read()

        # Extract text
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        extraction_result = loop.run_until_complete(
            extractor.extract(file_data, document['category'], document['metadata'])
        )

        if not extraction_result['success']:
            # Log extraction failure
            supabase.table('documents').update({
                'processing_status': 'extraction_failed',
                'processing_error': extraction_result['error']
            }).eq('document_id', document_id).execute()

            return {'success': False, 'error': extraction_result['error']}

        # Save extraction metadata
        supabase.table('extraction_metadata').insert({
            'document_id': document_id,
            'extraction_method': extraction_result['extraction_method'],
            'total_pages': extraction_result.get('total_pages'),
            'total_characters': extraction_result['total_characters'],
            'total_words': extraction_result['total_words'],
            'extraction_duration_ms': extraction_result['extraction_duration_ms'],
            'extraction_success': True,
            'metadata': extraction_result
        }).execute()

        # Create chunks
        chunking_result = chunker.create_chunks(extraction_result['full_text'])

        # Save chunks to database
        save_result = loop.run_until_complete(
            chunker.save_chunks(document_id, chunking_result['chunks'], supabase)
        )

        if not save_result['success']:
            supabase.table('documents').update({
                'processing_status': 'chunking_failed',
                'processing_error': save_result['error']
            }).eq('document_id', document_id).execute()

            return {'success': False, 'error': save_result['error']}

        # Save chunking metadata
        supabase.table('chunking_metadata').insert({
            'document_id': document_id,
            'document_type': chunking_result['metadata']['document_type'],
            'chunk_count': len(chunking_result['chunks']),
            'average_chunk_size': int(chunking_result['metadata']['average_chunk_size']),
            'chunking_config': chunking_result['metadata']['config'],
            'chunking_duration_ms': chunking_result['metadata']['chunking_duration_ms']
        }).execute()

        # Update document status
        supabase.table('documents').update({
            'processing_status': 'text_extracted',
            'chunk_count': len(chunking_result['chunks'])
        }).eq('document_id', document_id).execute()

        loop.close()

        return {
            'success': True,
            'document_id': document_id,
            'chunks_created': len(chunking_result['chunks']),
            'total_words': extraction_result['total_words']
        }

    except Exception as e:
        # Log error
        try:
            supabase.table('documents').update({
                'processing_status': 'processing_failed',
                'processing_error': str(e)
            }).eq('document_id', document_id).execute()
        except:
            pass

        return {'success': False, 'error': str(e)}
```

---

