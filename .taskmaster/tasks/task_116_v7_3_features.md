# Task ID: 116

**Title:** Extend Chunk class with header metadata fields

**Status:** done

**Dependencies:** 112 ✓

**Priority:** medium

**Description:** Extend the Chunk entity to include header-related metadata fields

**Details:**

Extend the existing Chunk class or its metadata structure to include new fields for header information.

Implementation details:
1. Add the following metadata fields to the Chunk class:
   - header_level: Integer (1-6) representing the header level
   - section_header: String containing the section header text
   - header_hierarchy: String representing the full header hierarchy (e.g., "Chapter 1 > Introduction > Overview")
   - is_header_split: Boolean indicating if the chunk was created by header splitting
   - is_subdivision: Boolean indicating if the chunk is a subdivision of a larger section
   - subdivision_index: Integer representing the position in a subdivided section

2. Ensure backward compatibility with existing chunk metadata
3. Update any relevant documentation or type definitions

Pseudo-code:
```python
# If Chunk is a dataclass or similar
class Chunk:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Helper methods for header metadata
    @property
    def header_level(self) -> Optional[int]:
        return self.metadata.get('header_level')
    
    @property
    def section_header(self) -> Optional[str]:
        return self.metadata.get('section_header')
    
    @property
    def header_hierarchy(self) -> Optional[str]:
        return self.metadata.get('header_hierarchy')
    
    @property
    def is_header_split(self) -> bool:
        return self.metadata.get('is_header_split', False)
```

**Test Strategy:**

1. Unit test the extended Chunk class
2. Verify all new metadata fields can be set and retrieved
3. Test backward compatibility with existing chunks
4. Verify helper methods work correctly
5. Test serialization/deserialization of chunks with header metadata
6. Verify integration with existing systems that use Chunk objects
