# Task ID: 114

**Title:** Implement large section subdivision with header context preservation

**Status:** done

**Dependencies:** 112 ✓, 113 ✓

**Priority:** medium

**Description:** Create functionality to subdivide large sections exceeding token limits while preserving header context

**Details:**

Implement methods to handle sections that exceed the maximum chunk size (1024 tokens) by subdividing them into smaller chunks while preserving the header context.

Implementation details:
1. Create a method to calculate token count for sections
2. Implement sentence-aware splitting for large sections
3. Ensure each sub-chunk retains the original section's header metadata
4. Apply chunk overlap (200 tokens) between subdivided chunks
5. Maintain sequential ordering of subdivided chunks

Pseudo-code:
```python
def _get_token_count(self, text):
    # Use tokenizer to count tokens
    return len(self.tokenizer.encode(text))

def _subdivide_section(self, section):
    # Use sentence-aware splitting for large sections
    sentences = self._split_into_sentences(section.content)
    chunks = []
    current_chunk = section.header_text + '\n'  # Start with header
    current_chunk_sentences = []
    
    for sentence in sentences:
        # Check if adding this sentence would exceed the limit
        test_chunk = current_chunk + ' ' + sentence
        if self._get_token_count(test_chunk) > self.max_chunk_size and current_chunk_sentences:
            # Create chunk with current content
            chunk = self._create_chunk_with_header_context(
                content=current_chunk,
                section=section,
                is_subdivision=True,
                subdivision_index=len(chunks)
            )
            chunks.append(chunk)
            
            # Start new chunk with overlap
            overlap_sentences = current_chunk_sentences[-3:]  # Approximate 200 token overlap
            current_chunk = section.header_text + '\n' + ' '.join(overlap_sentences) + ' ' + sentence
            current_chunk_sentences = overlap_sentences + [sentence]
        else:
            # Add sentence to current chunk
            current_chunk = test_chunk
            current_chunk_sentences.append(sentence)
    
    # Add final chunk if there's content
    if current_chunk_sentences:
        chunk = self._create_chunk_with_header_context(
            content=current_chunk,
            section=section,
            is_subdivision=True,
            subdivision_index=len(chunks)
        )
        chunks.append(chunk)
    
    return chunks

def _create_chunk_with_header_context(self, content, section, is_subdivision=False, subdivision_index=0):
    # Create chunk with header metadata
    return Chunk(
        text=content,
        metadata={
            'header_level': section.level,
            'section_header': section.header_text,
            'header_hierarchy': ' > '.join(section.parent_headers + [section.header_text]),
            'is_header_split': True,
            'is_subdivision': is_subdivision,
            'subdivision_index': subdivision_index
        }
    )
```

**Test Strategy:**

1. Test with sections of various sizes to verify subdivision logic
2. Verify token counting is accurate
3. Check that subdivided chunks maintain header context
4. Verify chunk overlap is correctly applied
5. Test with edge cases like very short sentences and very long sentences
6. Verify sequential ordering of subdivided chunks

## Subtasks

### 114.1. Implement _count_tokens() method using tiktoken

**Status:** pending  
**Dependencies:** None  

Create a method to accurately count tokens in text sections using the tiktoken library

**Details:**

Implement the _count_tokens() method that uses the tiktoken library to accurately count tokens in text sections. This method will be used to determine if a section needs to be subdivided based on the maximum token limit (1024 tokens). The implementation should handle different encoding models and cache the tokenizer for efficiency.

### 114.2. Implement _chunk_oversized_section() using SentenceSplitter

**Status:** pending  
**Dependencies:** 114.1  

Create a method to split large sections into smaller chunks while preserving sentence boundaries

**Details:**

Implement the _chunk_oversized_section() method that uses a SentenceSplitter to divide large sections into smaller chunks without breaking sentences. The method should ensure that each chunk starts with the section header for context preservation and implements sentence-aware splitting logic. It should handle edge cases like very long sentences that might exceed the token limit on their own.

### 114.3. Add chunk_index and total_section_chunks metadata

**Status:** pending  
**Dependencies:** 114.2  

Enhance chunk metadata with indexing information to maintain sequential ordering of subdivided chunks

**Details:**

Modify the _create_chunk_with_header_context() method to include additional metadata fields: 'chunk_index' and 'total_section_chunks'. These fields will help maintain the sequential ordering of subdivided chunks and provide information about the total number of chunks a section was split into. Update the chunk creation logic to properly set these values when creating subdivided chunks.

### 114.4. Implement chunk_overlap with 200 tokens between subdivided sections

**Status:** pending  
**Dependencies:** 114.2, 114.3  

Add functionality to ensure 200 token overlap between adjacent chunks from the same section

**Details:**

Enhance the _chunk_oversized_section() method to implement a 200 token overlap between adjacent chunks from the same section. This involves modifying the chunking algorithm to include approximately 200 tokens from the end of the previous chunk at the beginning of the next chunk. The implementation should use the _count_tokens() method to ensure accurate token counting and should handle edge cases where the overlap might be smaller due to section size constraints.
