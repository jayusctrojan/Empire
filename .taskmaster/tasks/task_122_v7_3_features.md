# Task ID: 122

**Title:** Create Content Prep Agent Service

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Implement the core Content Prep Agent (AGENT-016) service that will validate, order, and prepare content before ingestion into the knowledge base.

**Details:**

Create the `app/services/content_prep_agent.py` file with the following components:

1. Implement the CrewAI agent definition as specified in the PRD
2. Create the ContentSet, ContentFile, and ProcessingManifest data classes
3. Implement the three main components:
   - Set Detector: Pattern matching and grouping logic
   - Order Resolver: Sequence parsing and gap detection
   - Manifest Generator: Ordered queue and dependency tracking

Pseudo-code:
```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
import re
import uuid

# Data models as specified in PRD
@dataclass
class ContentFile:
    b2_path: str
    filename: str
    sequence_number: Optional[int] = None
    dependencies: List[str] = None
    estimated_complexity: str = "medium"
    file_type: str = ""
    size_bytes: int = 0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ContentSet:
    id: str
    name: str
    detection_method: str
    files: List[ContentFile]
    is_complete: bool = False
    missing_files: List[str] = None
    processing_status: str = "pending"
    created_at: datetime = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.missing_files is None:
            self.missing_files = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ProcessingManifest:
    content_set_id: str
    ordered_files: List[ContentFile]
    total_files: int
    estimated_processing_time: int
    warnings: List[str] = None
    context: Dict = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.context is None:
            self.context = {}

# Sequence detection patterns as specified in PRD
SEQUENCE_PATTERNS = [
    # Numeric prefix patterns
    r"^(\d{1,3})[-_\s]",              # "01-intro.pdf", "1_chapter.pdf"
    r"[-_\s](\d{1,3})[-_\s.]",        # "chapter-01-intro.pdf"
    r"module[-_\s]?(\d{1,3})",        # "module01.pdf", "module-1.pdf"
    r"chapter[-_\s]?(\d{1,3})",       # "chapter1.pdf", "chapter-01.pdf"
    r"lesson[-_\s]?(\d{1,3})",        # "lesson5.pdf"
    r"part[-_\s]?(\d{1,3})",          # "part-1.pdf"
    r"week[-_\s]?(\d{1,3})",          # "week-01.pdf"
    r"unit[-_\s]?(\d{1,3})",          # "unit-1.pdf"

    # Alpha sequence patterns
    r"^([a-z])[-_\s]",                # "a-intro.pdf", "b-basics.pdf"

    # Roman numerals
    r"^(i{1,3}|iv|v|vi{0,3}|ix|x)[-_\s]",  # "i-intro.pdf", "ii-basics.pdf"
]

CONTENT_SET_INDICATORS = [
    r"course[-_\s]?",
    r"tutorial[-_\s]?",
    r"training[-_\s]?",
    r"documentation[-_\s]?",
    r"manual[-_\s]?",
    r"series[-_\s]?",
    r"book[-_\s]?",
]

class ContentPrepAgent:
    """AGENT-016: Content Prep Agent implementation"""
    
    def __init__(self):
        self.agent_config = {
            "id": "AGENT-016",
            "name": "Content Prep Agent",
            "role": "Content Preparation Specialist",
            "goal": "Validate, order, and prepare content sets for optimal knowledge base ingestion",
            "backstory": """You are an expert in content organization and curriculum design.
            You understand that learning materials must be processed in logical sequence
            to maintain prerequisite relationships. You detect patterns in file naming,
            identify content sets, and ensure completeness before processing begins.""",
            "model": "claude-3-5-haiku-20241022",  # Fast, cost-effective for ordering
            "tools": [
                "file_metadata_reader",
                "sequence_pattern_detector",
                "b2_file_lister",
                "manifest_generator"
            ],
            "allow_delegation": False,
            "verbose": True
        }
    
    def detect_content_sets(self, files, detection_mode="auto"):
        """Detect related content sets from a list of files"""
        # Implementation of set detection logic
        # Group by naming patterns, prefixes, etc.
        pass
        
    def validate_completeness(self, content_set):
        """Check for missing files in sequence"""
        # Gap detection in sequence numbers
        # Return list of missing files
        pass
        
    def resolve_order(self, files):
        """Determine the correct processing order"""
        # Parse file names for sequence indicators
        # Sort by detected sequence
        # Fall back to LLM for ambiguous cases
        pass
        
    def generate_manifest(self, content_set, proceed_incomplete=False):
        """Create processing manifest with ordered files"""
        # Generate ordered queue
        # Add dependencies and context
        # Include warnings for missing files
        pass
        
    def estimate_processing_time(self, files):
        """Estimate processing time based on file types and sizes"""
        # Calculate based on file size, type, and complexity
        pass
        
    def detect_sequence_number(self, filename):
        """Extract sequence number from filename using patterns"""
        # Try each pattern in SEQUENCE_PATTERNS
        # Return extracted number if found
        pass
```

**Test Strategy:**

1. Unit tests for each component (Set Detector, Order Resolver, Manifest Generator)
2. Test with various file naming patterns to ensure correct sequence detection
3. Test gap detection with incomplete sequences
4. Test with edge cases (single files, very large sets)
5. Verify correct data model instantiation
6. Mock B2 file listing for integration testing

## Subtasks

### 122.1. Create data classes for ContentFile, ContentSet, and ProcessingManifest

**Status:** pending  
**Dependencies:** None  

Implement the data models needed for the Content Prep Agent service as specified in the PRD.

**Details:**

Create the data classes ContentFile, ContentSet, and ProcessingManifest with all required fields and proper type annotations. Implement the __post_init__ methods to handle default values for lists and dictionaries. Ensure all fields match the specifications in the PRD and pseudo-code.

### 122.2. Implement sequence detection patterns and content set indicators

**Status:** pending  
**Dependencies:** 122.1  

Define the regex patterns for sequence detection and content set identification.

**Details:**

Create the SEQUENCE_PATTERNS list containing all regex patterns for detecting sequence numbers in filenames. Implement the CONTENT_SET_INDICATORS list with patterns for identifying related content sets. Ensure patterns cover all specified cases in the PRD including numeric prefixes, alpha sequences, and roman numerals.

### 122.3. Create ContentPrepAgent class skeleton with CrewAI configuration

**Status:** pending  
**Dependencies:** 122.1, 122.2  

Implement the base ContentPrepAgent class with CrewAI agent configuration.

**Details:**

Create the ContentPrepAgent class with proper initialization and CrewAI agent configuration as specified in the PRD. Include the agent_config dictionary with all required fields (id, name, role, goal, backstory, model, tools, etc.). Define method stubs for all required functionality.

### 122.4. Implement sequence detection and extraction methods

**Status:** pending  
**Dependencies:** 122.2, 122.3  

Create methods for extracting sequence numbers and prefixes from filenames.

**Details:**

Implement the detect_sequence_number method to extract sequence numbers from filenames using the defined regex patterns. Create helper methods for extracting prefixes and other metadata from filenames. Ensure proper handling of edge cases and different sequence formats.

### 122.5. Implement content set detection functionality

**Status:** pending  
**Dependencies:** 122.3, 122.4  

Create the detect_content_sets method to identify related content sets from file lists.

**Details:**

Implement the detect_content_sets method that groups files into related content sets based on naming patterns, prefixes, and other indicators. Include support for different detection modes (auto, pattern-based, prefix-based). Create helper methods for pattern matching and grouping logic.

### 122.6. Implement order resolution and completeness validation

**Status:** pending  
**Dependencies:** 122.4, 122.5  

Create methods for determining processing order and detecting missing files.

**Details:**

Implement the resolve_order method to determine the correct processing sequence for files based on detected sequence numbers. Create the validate_completeness method to identify gaps in sequences and generate a list of potentially missing files. Include logic for handling ambiguous cases using LLM fallback.

### 122.7. Implement manifest generation and processing time estimation

**Status:** pending  
**Dependencies:** 122.5, 122.6  

Create methods for generating processing manifests and estimating processing times.

**Details:**

Implement the generate_manifest method to create a ProcessingManifest with ordered files, dependencies, and context information. Create the estimate_processing_time method to calculate expected processing duration based on file types, sizes, and complexity. Include handling for warnings about missing files and incomplete sets.

### 122.8. Implement database storage and retrieval methods

**Status:** pending  
**Dependencies:** 122.1, 122.7  

Create methods for persisting content sets and manifests to the database.

**Details:**

Implement methods for storing ContentSet and ProcessingManifest objects in the database. Create retrieval methods for loading existing content sets and manifests. Ensure proper error handling and transaction management. Implement status update methods for tracking processing progress.
