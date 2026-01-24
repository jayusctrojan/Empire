# Task ID: 117

**Title:** Implement automatic markdown detection for LlamaParse output

**Status:** done

**Dependencies:** 112 ✓, 113 ✓

**Priority:** medium

**Description:** Create functionality to automatically detect markdown content from LlamaParse output

**Details:**

Implement logic to automatically detect when a document comes from LlamaParse with markdown formatting and apply the appropriate chunking strategy.

Implementation details:
1. Create a detection method to identify LlamaParse markdown output
2. Integrate with the document processing pipeline to automatically select the markdown chunker
3. Look for LlamaParse metadata or specific markdown patterns
4. Handle edge cases where markdown might be malformed

Pseudo-code:
```python
def is_llamaparse_markdown(document):
    # Check document metadata for LlamaParse origin
    if document.metadata.get('source') == 'llamaparse' and document.metadata.get('result_type') == 'markdown':
        return True
    
    # Check for markdown header patterns
    if re.search(r'^(#{1,6})\s+(.+)$', document.text, re.MULTILINE):
        # Count headers to ensure it's not just occasional use of # symbols
        header_count = len(re.findall(r'^(#{1,6})\s+(.+)$', document.text, re.MULTILINE))
        if header_count >= 3:  # Arbitrary threshold for a structured document
            return True
    
    return False

# In document processor class
def select_chunking_strategy(document):
    if is_llamaparse_markdown(document):
        return MarkdownChunkerStrategy()
    elif is_code_document(document):
        return CodeChunkerStrategy()
    elif is_transcript(document):
        return TranscriptChunkerStrategy()
    else:
        return SentenceChunkerStrategy()
```

**Test Strategy:**

1. Test with various LlamaParse outputs to verify detection
2. Test with non-LlamaParse markdown documents
3. Test with documents having different levels of markdown formatting
4. Verify correct strategy selection based on document type
5. Test edge cases with minimal or malformed markdown
6. Verify integration with the document processing pipeline

## Subtasks

### 117.1. Implement is_llamaparse_markdown detection function

**Status:** pending  
**Dependencies:** None  

Create a function to detect markdown content from LlamaParse output based on metadata and content patterns.

**Details:**

Implement the is_llamaparse_markdown() function in document_processor.py that analyzes document content and metadata to determine if it's markdown from LlamaParse. The function should check for LlamaParse metadata tags, examine markdown header patterns (using regex to find patterns like '## Header'), count the frequency of markdown elements, and determine if the threshold of markdown elements is met to classify as structured markdown. Include handling for edge cases with malformed markdown.

### 117.2. Update document processing pipeline for markdown detection

**Status:** pending  
**Dependencies:** 117.1  

Modify the document processing pipeline to automatically select the markdown chunker when LlamaParse markdown is detected.

**Details:**

Update the source_processing.py file to integrate the is_llamaparse_markdown detection function into the document processing workflow. Modify the select_chunking_strategy() method to check for markdown content and route documents to the MarkdownChunkerStrategy when appropriate. Ensure the detection happens early in the pipeline to optimize processing. Add logging for strategy selection decisions to aid debugging and monitoring. Handle the transition between detection and chunking strategy selection seamlessly.

### 117.3. Add comprehensive tests for LlamaParse markdown flow

**Status:** pending  
**Dependencies:** 117.1, 117.2  

Create integration and unit tests to verify the end-to-end markdown detection and processing functionality.

**Details:**

Develop a comprehensive test suite in test_llamaparse_markdown.py that validates the entire markdown detection and processing flow. Include tests for various LlamaParse output formats, different markdown structures, and edge cases. Create mock LlamaParse outputs with varying degrees of markdown formatting. Test the integration between detection and chunking strategy selection. Verify that documents are correctly processed with the appropriate chunking strategy based on their content. Include performance tests to ensure the detection doesn't significantly impact processing time.
