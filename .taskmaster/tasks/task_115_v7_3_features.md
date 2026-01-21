# Task ID: 115

**Title:** Implement fallback to sentence-based chunking

**Status:** done

**Dependencies:** 112 ✓

**Priority:** medium

**Description:** Create fallback mechanism for documents without markdown headers

**Details:**

Implement a fallback mechanism that uses the existing sentence-based chunking strategy when a document contains no recognizable markdown headers.

Implementation details:
1. Create a method to delegate to the existing sentence-based chunker
2. Ensure seamless transition between strategies based on document content
3. Preserve all existing functionality of sentence-based chunking
4. Add appropriate logging to indicate fallback was used

Pseudo-code:
```python
def _fallback_chunking(self, document):
    # Log that we're falling back to sentence-based chunking
    logger.info(f"No markdown headers found in document {document.id}, falling back to sentence-based chunking")
    
    # Create and use sentence chunker with same parameters
    sentence_chunker = SentenceChunkerStrategy(
        max_chunk_size=self.max_chunk_size,
        chunk_overlap=self.chunk_overlap
    )
    
    # Get chunks from sentence chunker
    chunks = sentence_chunker.split(document)
    
    # Add metadata to indicate fallback was used
    for chunk in chunks:
        chunk.metadata['chunking_strategy'] = 'sentence_fallback'
        chunk.metadata['is_header_split'] = False
    
    return chunks
```

**Test Strategy:**

1. Test with documents containing no markdown headers
2. Verify fallback to sentence-based chunking works correctly
3. Compare results with direct use of sentence chunker to ensure equivalence
4. Verify appropriate metadata is added to chunks
5. Check logging to ensure fallback is properly recorded
6. Test with edge cases like documents with malformed headers

## Subtasks

### 115.1. Add is_markdown_content() method with min_headers threshold

**Status:** pending  
**Dependencies:** None  

Create a method to detect if a document contains sufficient markdown headers to use header-based chunking

**Details:**

Implement a new method called `is_markdown_content()` that analyzes a document to determine if it contains enough markdown headers to be processed with header-based chunking. The method should accept a parameter for minimum number of headers required (default to 2 or 3). It should use regex patterns to identify markdown headers (e.g., lines starting with #, ##, etc.) and return a boolean indicating if the document meets the threshold. This will be used as the decision point for whether to use header-based chunking or fall back to sentence-based chunking.

### 115.2. Implement fallback to SentenceSplitter when no headers detected

**Status:** pending  
**Dependencies:** 115.1  

Create the fallback mechanism that delegates to sentence-based chunking when a document lacks sufficient markdown structure

**Details:**

Implement the `_fallback_chunking()` method as outlined in the pseudo-code. This method should be called when `is_markdown_content()` returns False. It should instantiate a SentenceChunkerStrategy with the same parameters as the current chunker, process the document using this strategy, and add appropriate metadata to each chunk to indicate the fallback strategy was used. Ensure proper logging is implemented to record when fallback occurs. Modify the main chunking method to check for markdown content first and delegate to the appropriate chunking strategy.

### 115.3. Add integration test for non-markdown document processing

**Status:** pending  
**Dependencies:** 115.2  

Create comprehensive integration tests to verify the fallback mechanism works end-to-end

**Details:**

Develop integration tests that process various document types through the chunking system. Include test cases for documents with no markdown headers, documents with insufficient headers (below threshold), and documents with adequate headers. Verify that the system correctly identifies document types, applies the appropriate chunking strategy, and produces expected results. Test that metadata is correctly applied in all cases. Also test edge cases such as very short documents, documents with unusual formatting, and documents with mixed content types.
