# Task ID: 126

**Title:** Implement Processing Manifest Generation

**Status:** done

**Dependencies:** 122 ✓, 125 ✓

**Priority:** medium

**Description:** Create the functionality to generate processing manifests that specify the ordered processing queue, dependencies, and context for downstream agents.

**Details:**

Enhance the ContentPrepAgent class with methods to generate processing manifests. This includes:

1. Creating an ordered processing queue
2. Identifying dependencies between files
3. Estimating processing complexity and time
4. Adding context metadata for downstream agents

Pseudo-code:

```python
class ContentPrepAgent:
    # ... existing code ...
    
    def generate_manifest(self, content_set, proceed_incomplete=False):
        """Create processing manifest with ordered files"""
        # Check if content set is complete
        if not content_set.is_complete and not proceed_incomplete:
            raise ValueError("Content set is incomplete. Set proceed_incomplete=True to generate manifest anyway.")
        
        # Get ordered files
        ordered_files = self.resolve_order(content_set)
        
        # Identify dependencies
        self._identify_dependencies(ordered_files)
        
        # Estimate processing time
        estimated_time = self.estimate_processing_time(ordered_files)
        
        # Create manifest
        manifest = ProcessingManifest(
            content_set_id=content_set.id,
            ordered_files=ordered_files,
            total_files=len(ordered_files),
            estimated_processing_time=estimated_time,
            warnings=content_set.missing_files if not content_set.is_complete else [],
            context={
                "content_set_name": content_set.name,
                "is_complete": content_set.is_complete,
                "detection_method": content_set.detection_method,
                "total_files": len(ordered_files),
            }
        )
        
        return manifest
    
    def _identify_dependencies(self, ordered_files):
        """Identify dependencies between files based on order"""
        # Simple sequential dependencies - each file depends on the previous one
        for i in range(1, len(ordered_files)):
            prev_file = ordered_files[i-1]
            curr_file = ordered_files[i]
            
            # Add dependency on previous file
            curr_file.dependencies.append(prev_file.b2_path)
    
    def estimate_processing_time(self, files):
        """Estimate processing time based on file types and sizes"""
        total_time = 0
        
        for file in files:
            # Base time by file type
            if file.file_type.lower() == "pdf":
                base_time = 30  # 30 seconds base for PDF
            elif file.file_type.lower() in ["docx", "doc"]:
                base_time = 25  # 25 seconds base for Word docs
            elif file.file_type.lower() in ["txt", "md"]:
                base_time = 10  # 10 seconds base for text files
            else:
                base_time = 20  # Default base time
            
            # Adjust by file size (very simple heuristic)
            size_factor = max(1, file.size_bytes / (1024 * 1024))  # Size in MB, minimum 1
            
            # Adjust by complexity
            complexity_factor = 1.0
            if file.estimated_complexity == "high":
                complexity_factor = 1.5
            elif file.estimated_complexity == "low":
                complexity_factor = 0.8
            
            # Calculate time for this file
            file_time = base_time * size_factor * complexity_factor
            total_time += file_time
        
        return int(total_time)  # Return as integer seconds
    
    def estimate_file_complexity(self, file):
        """Estimate file complexity based on size, type, and content"""
        # Simple heuristic based on file size
        if file.size_bytes > 5 * 1024 * 1024:  # > 5MB
            return "high"
        elif file.size_bytes < 100 * 1024:  # < 100KB
            return "low"
        else:
            return "medium"
```

**Test Strategy:**

1. Unit tests for manifest generation
2. Test dependency identification with different file orders
3. Test processing time estimation with various file types and sizes
4. Verify manifest structure matches expected schema
5. Test error handling for incomplete sets
6. Test with large file sets to ensure performance
