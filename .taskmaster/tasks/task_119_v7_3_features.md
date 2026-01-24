# Task ID: 119

**Title:** Implement chunk filtering by header metadata

**Status:** done

**Dependencies:** 112 ✓, 116 ✓

**Priority:** low

**Description:** Add functionality to filter chunks by header level or section name

**Details:**

Implement functionality to allow filtering of chunks based on header metadata, enabling advanced search capabilities.

Implementation details:
1. Extend the search/query interface to accept header filter parameters
2. Implement filtering logic based on header level, section name, or header hierarchy
3. Ensure efficient filtering without significant performance impact
4. Add documentation for the new filtering capabilities

Pseudo-code:
```python
class ChunkRepository:
    # Existing methods...
    
    def search_with_filters(self, query, filters=None, **kwargs):
        # Start with basic search
        results = self.basic_search(query, **kwargs)
        
        # Apply header filters if specified
        if filters and results:
            if 'header_level' in filters:
                results = [r for r in results if r.chunk.metadata.get('header_level') == filters['header_level']]
            
            if 'section_header' in filters:
                section_pattern = re.compile(filters['section_header'], re.IGNORECASE)
                results = [r for r in results if r.chunk.metadata.get('section_header') and 
                           section_pattern.search(r.chunk.metadata.get('section_header'))]
            
            if 'header_hierarchy' in filters:
                hierarchy_pattern = re.compile(filters['header_hierarchy'], re.IGNORECASE)
                results = [r for r in results if r.chunk.metadata.get('header_hierarchy') and 
                           hierarchy_pattern.search(r.chunk.metadata.get('header_hierarchy'))]
        
        return results

# API endpoint or service method
def search_documents(query, header_level=None, section_name=None, header_path=None, **kwargs):
    filters = {}
    if header_level is not None:
        filters['header_level'] = int(header_level)
    if section_name:
        filters['section_header'] = section_name
    if header_path:
        filters['header_hierarchy'] = header_path
    
    return chunk_repository.search_with_filters(query, filters, **kwargs)
```

**Test Strategy:**

1. Test filtering by header level
2. Test filtering by section name (exact and partial matches)
3. Test filtering by header hierarchy
4. Test combinations of multiple filters
5. Verify performance impact is minimal
6. Test with edge cases like non-existent headers or malformed filters
