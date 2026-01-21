# Task ID: 120

**Title:** Implement logging and observability for markdown chunking

**Status:** done

**Dependencies:** 112 ✓, 113 ✓, 114 ✓

**Priority:** low

**Description:** Add comprehensive logging and observability for the markdown chunking process

**Details:**

Implement logging and observability features to track the markdown chunking process, including strategy selection, chunk statistics, and performance metrics.

Implementation details:
1. Add structured logging throughout the MarkdownChunkerStrategy class
2. Log key events: strategy selection, header detection, section parsing, chunking decisions
3. Record metrics: number of chunks created, average chunk size, processing time
4. Create summary statistics for each processed document
5. Ensure logs can be used for debugging and performance analysis

Pseudo-code:
```python
class MarkdownChunkerStrategy(ChunkingStrategy):
    # Existing methods...
    
    def split(self, document):
        start_time = time.time()
        logger.info(f"Starting markdown chunking for document {document.id}")
        
        # Check if document has markdown headers
        has_headers = self._has_markdown_headers(document.text)
        logger.info(f"Markdown headers detected: {has_headers}")
        
        if not has_headers:
            logger.info(f"Falling back to sentence chunking for document {document.id}")
            chunks = self._fallback_chunking(document)
        else:
            # Parse document into sections by headers
            sections = self._parse_sections(document.text)
            logger.info(f"Parsed {len(sections)} sections from document")
            
            # Log section statistics
            header_levels = Counter([section.level for section in sections])
            logger.info(f"Header level distribution: {dict(header_levels)}")
            
            # Convert sections to chunks
            chunks = []
            subdivided_sections = 0
            
            for section in sections:
                token_count = self._get_token_count(section.content)
                if token_count > self.max_chunk_size:
                    logger.info(f"Subdividing section '{section.header_text}' with {token_count} tokens")
                    subdivided_sections += 1
                    sub_chunks = self._subdivide_section(section)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(self._create_chunk(section))
            
            logger.info(f"Created {len(chunks)} chunks, subdivided {subdivided_sections} sections")
        
        # Calculate and log metrics
        processing_time = time.time() - start_time
        avg_chunk_size = sum(len(c.text) for c in chunks) / len(chunks) if chunks else 0
        avg_token_count = sum(self._get_token_count(c.text) for c in chunks) / len(chunks) if chunks else 0
        
        logger.info(f"Markdown chunking completed in {processing_time:.2f}s")
        logger.info(f"Chunks: {len(chunks)}, Avg size: {avg_chunk_size:.1f} chars, Avg tokens: {avg_token_count:.1f}")
        
        # Add processing metadata to document
        document.metadata['chunking_stats'] = {
            'strategy': 'markdown' if has_headers else 'sentence_fallback',
            'chunk_count': len(chunks),
            'avg_chunk_size': avg_chunk_size,
            'avg_token_count': avg_token_count,
            'processing_time': processing_time,
            'subdivided_sections': subdivided_sections if has_headers else 0
        }
        
        return chunks
```

**Test Strategy:**

1. Verify logs are generated for key events in the chunking process
2. Test that metrics are accurately calculated and recorded
3. Check that document metadata is properly updated with chunking statistics
4. Test with various document types to ensure comprehensive logging
5. Verify log levels are appropriate (info for normal operation, warning/error for issues)
6. Test integration with existing logging and monitoring systems
