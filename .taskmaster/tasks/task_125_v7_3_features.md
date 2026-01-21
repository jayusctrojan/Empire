# Task ID: 125

**Title:** Implement Set Detection and Ordering Logic

**Status:** done

**Dependencies:** 122 ✓

**Priority:** high

**Description:** Implement the core algorithms for detecting content sets, validating completeness, and determining the correct processing order.

**Details:**

Enhance the ContentPrepAgent class with detailed implementations of the set detection and ordering algorithms. This includes:

1. Pattern-based content set detection
2. Sequence number extraction from filenames
3. Gap detection in sequences
4. Chronological ordering logic

Pseudo-code for key methods:

```python
class ContentPrepAgent:
    # ... existing code ...
    
    def detect_content_sets(self, files, detection_mode="auto"):
        """Detect related content sets from a list of files"""
        content_sets = []
        standalone_files = []
        
        # Group files by common prefixes
        prefix_groups = self._group_by_prefix(files)
        
        for prefix, group_files in prefix_groups.items():
            # Skip single files
            if len(group_files) <= 1:
                standalone_files.extend(group_files)
                continue
                
            # Check if group matches content set indicators
            is_content_set = any(re.search(pattern, prefix, re.IGNORECASE) 
                               for pattern in CONTENT_SET_INDICATORS)
            
            # If it's a potential content set or has >3 files with sequence numbers
            if is_content_set or self._has_sequence_numbers(group_files, threshold=0.7):
                # Create content set
                content_set = ContentSet(
                    id=str(uuid.uuid4()),
                    name=self._generate_set_name(prefix, group_files),
                    detection_method=detection_mode,
                    files=[self._create_content_file(f) for f in group_files],
                )
                
                # Validate completeness
                self.validate_completeness(content_set)
                
                content_sets.append(content_set)
            else:
                standalone_files.extend(group_files)
        
        return content_sets, standalone_files
    
    def _group_by_prefix(self, files):
        """Group files by common prefixes"""
        groups = {}
        
        for file in files:
            filename = os.path.basename(file['path'])
            
            # Try to find a common prefix
            prefix = self._extract_prefix(filename)
            if prefix not in groups:
                groups[prefix] = []
            
            groups[prefix].append(file)
            
        return groups
    
    def _extract_prefix(self, filename):
        """Extract prefix from filename"""
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        # Try to match common content set patterns
        for pattern in CONTENT_SET_INDICATORS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return name[:match.end()]
        
        # Fall back to first part of name (before first number or separator)
        match = re.search(r'^([^\d\-_\s]+)', name)
        if match:
            return match.group(1)
            
        return name
    
    def _has_sequence_numbers(self, files, threshold=0.7):
        """Check if files have sequence numbers"""
        count = sum(1 for f in files if self.detect_sequence_number(os.path.basename(f['path'])) is not None)
        return count / len(files) >= threshold
    
    def detect_sequence_number(self, filename):
        """Extract sequence number from filename using patterns"""
        for pattern in SEQUENCE_PATTERNS:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                # Extract the captured group
                sequence_str = match.group(1)
                
                # Convert to integer if numeric
                if sequence_str.isdigit():
                    return int(sequence_str)
                    
                # Handle roman numerals
                if re.match(r'^(i{1,3}|iv|v|vi{0,3}|ix|x)$', sequence_str, re.IGNORECASE):
                    return self._roman_to_int(sequence_str.lower())
                    
                # Handle alpha sequence (a, b, c...)
                if len(sequence_str) == 1 and sequence_str.isalpha():
                    return ord(sequence_str.lower()) - ord('a') + 1
        
        return None
    
    def _roman_to_int(self, s):
        """Convert Roman numeral to integer"""
        roman_map = {'i': 1, 'v': 5, 'x': 10}
        result = 0
        
        for i in range(len(s)):
            if i > 0 and roman_map[s[i]] > roman_map[s[i-1]]:
                result += roman_map[s[i]] - 2 * roman_map[s[i-1]]
            else:
                result += roman_map[s[i]]
                
        return result
    
    def validate_completeness(self, content_set):
        """Check for missing files in sequence"""
        # Get sequence numbers
        sequence_numbers = []
        for file in content_set.files:
            if file.sequence_number is not None:
                sequence_numbers.append(file.sequence_number)
        
        if not sequence_numbers:
            # No sequence numbers detected
            content_set.is_complete = True
            return content_set
        
        # Find min and max sequence
        min_seq = min(sequence_numbers)
        max_seq = max(sequence_numbers)
        
        # Check for gaps
        expected_range = set(range(min_seq, max_seq + 1))
        actual_set = set(sequence_numbers)
        missing = expected_range - actual_set
        
        if missing:
            content_set.is_complete = False
            content_set.missing_files = [f"Missing sequence {num}" for num in missing]
        else:
            content_set.is_complete = True
            content_set.missing_files = []
        
        return content_set
    
    def resolve_order(self, content_set):
        """Determine the correct processing order"""
        # Sort files by sequence number if available
        files_with_sequence = []
        files_without_sequence = []
        
        for file in content_set.files:
            if file.sequence_number is not None:
                files_with_sequence.append(file)
            else:
                files_without_sequence.append(file)
        
        # Sort by sequence number
        files_with_sequence.sort(key=lambda f: f.sequence_number)
        
        # For files without sequence, try to use creation date or name
        files_without_sequence.sort(key=lambda f: f.filename)
        
        # Combine the lists
        ordered_files = files_with_sequence + files_without_sequence
        
        return ordered_files
```

**Test Strategy:**

1. Unit tests for each algorithm (prefix grouping, sequence detection, gap detection)
2. Test with various file naming patterns
3. Test with edge cases (no sequence numbers, mixed formats)
4. Test completeness validation with different gap scenarios
5. Benchmark performance with large file sets
6. Test with real-world examples of course materials

## Subtasks

### 125.1. Implement analyze_folder() method for content set detection

**Status:** pending  
**Dependencies:** None  

Create the analyze_folder() method that scans a directory and identifies potential content sets based on file patterns.

**Details:**

Implement the analyze_folder() method in ContentPrepAgent class that takes a folder path as input, scans all files, and calls detect_content_sets() with the file list. Include logic to handle large directories by processing files in batches. The method should return a tuple of (content_sets, standalone_files).

### 125.2. Implement _create_content_set() builder method

**Status:** pending  
**Dependencies:** 125.1  

Create a helper method to build ContentSet objects with proper metadata extraction and initialization.

**Details:**

Implement the _create_content_set() method that takes a group of files and creates a properly initialized ContentSet object. This includes generating a unique ID, determining an appropriate name based on common prefixes, setting the detection method, and initializing the files list with proper metadata for each file.

### 125.3. Implement sequence number extraction from filenames

**Status:** pending  
**Dependencies:** 125.2  

Create robust methods to detect and extract sequence numbers from various filename formats.

**Details:**

Implement the detect_sequence_number() method to extract sequence numbers from filenames using regular expressions. Handle numeric sequences, roman numerals, and alphabetic sequences. Include the _roman_to_int() helper method for converting roman numerals to integers. Ensure the method can handle various delimiter patterns and position of sequence numbers in filenames.

### 125.4. Implement gap detection for missing files in sequences

**Status:** pending  
**Dependencies:** 125.3  

Create the validate_completeness() method to identify gaps in file sequences and mark content sets as incomplete when files are missing.

**Details:**

Implement the validate_completeness() method that analyzes a content set's files to detect missing sequence numbers. The method should extract sequence numbers from all files, determine the expected range, identify any gaps, and update the content set's is_complete flag and missing_files list accordingly. Handle edge cases where no sequence numbers are detected.

### 125.5. Implement chronological ordering logic for content sets

**Status:** pending  
**Dependencies:** 125.3, 125.4  

Create the resolve_order() method to determine the correct processing order for files within a content set.

**Details:**

Implement the resolve_order() method that sorts files within a content set based on sequence numbers when available. For files without sequence numbers, implement fallback ordering based on creation date or filename. The method should return an ordered list of files and handle mixed cases where some files have sequence numbers and others don't.

### 125.6. Implement batched analysis for large file sets

**Status:** pending  
**Dependencies:** 125.1, 125.2, 125.5  

Enhance the content set detection to handle large directories by processing files in batches and merging results.

**Details:**

Modify the analyze_folder() method to process large directories (>100 files) in batches to prevent memory issues. Implement a merge_content_sets() helper method that combines results from multiple batches while preserving chronological ordering. Include progress tracking and logging for batch processing. Ensure the final merged result maintains all metadata and relationships between files.
