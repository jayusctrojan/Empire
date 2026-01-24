# Task ID: 131

**Title:** Create Comprehensive Test Suite

**Status:** done

**Dependencies:** 122 ✓, 124 ✓, 125 ✓, 126 ✓, 127 ✓, 128 ✓, 129 ✓, 130 ✓

**Priority:** medium

**Description:** Create a comprehensive test suite for the Content Prep Agent, including unit tests, integration tests, and performance benchmarks.

**Details:**

Create the file `tests/test_content_prep_agent.py` with a comprehensive test suite for the Content Prep Agent. This includes:

1. Unit tests for each component (set detection, ordering, manifest generation)
2. Integration tests with mocked dependencies
3. Performance benchmarks for large file sets
4. Test cases for all user stories

Pseudo-code:

```python
# In tests/test_content_prep_agent.py

import unittest
from unittest.mock import patch, MagicMock
import pytest
from app.services.content_prep_agent import ContentPrepAgent, ContentSet, ContentFile, ProcessingManifest

class TestContentPrepAgent(unittest.TestCase):
    def setUp(self):
        self.agent = ContentPrepAgent()
        
        # Sample test files
        self.test_files = [
            {"path": "pending/course/01-intro.pdf", "size": 1024 * 1024, "type": "pdf"},
            {"path": "pending/course/02-basics.pdf", "size": 2 * 1024 * 1024, "type": "pdf"},
            {"path": "pending/course/03-advanced.pdf", "size": 3 * 1024 * 1024, "type": "pdf"},
            {"path": "pending/course/10-appendix.pdf", "size": 500 * 1024, "type": "pdf"},
            {"path": "pending/random.txt", "size": 10 * 1024, "type": "txt"},
        ]
    
    def test_detect_sequence_number(self):
        """Test sequence number detection from filenames"""
        test_cases = [
            ("01-intro.pdf", 1),
            ("chapter-02-basics.pdf", 2),
            ("module03.pdf", 3),
            ("lesson_4_advanced.pdf", 4),
            ("part-v-conclusion.pdf", 5),  # Roman numeral
            ("a-intro.pdf", 1),  # Alpha sequence
            ("random.pdf", None),  # No sequence
        ]
        
        for filename, expected in test_cases:
            result = self.agent.detect_sequence_number(filename)
            self.assertEqual(result, expected, f"Failed for {filename}")
    
    def test_detect_content_sets(self):
        """Test content set detection"""
        content_sets, standalone = self.agent.detect_content_sets(self.test_files)
        
        # Should detect one content set with 4 files
        self.assertEqual(len(content_sets), 1)
        self.assertEqual(len(content_sets[0].files), 4)
        
        # Should have one standalone file
        self.assertEqual(len(standalone), 1)
        self.assertEqual(standalone[0]["path"], "pending/random.txt")
    
    def test_validate_completeness(self):
        """Test completeness validation"""
        # Create a content set with files 1, 2, 4 (missing 3)
        files = [
            ContentFile(b2_path="file1.pdf", filename="file1.pdf", sequence_number=1),
            ContentFile(b2_path="file2.pdf", filename="file2.pdf", sequence_number=2),
            ContentFile(b2_path="file4.pdf", filename="file4.pdf", sequence_number=4),
        ]
        
        content_set = ContentSet(
            id="test-id",
            name="Test Set",
            detection_method="pattern",
            files=files
        )
        
        # Validate completeness
        self.agent.validate_completeness(content_set)
        
        # Should be incomplete with missing file 3
        self.assertFalse(content_set.is_complete)
        self.assertEqual(len(content_set.missing_files), 1)
        
        # Add the missing file and revalidate
        content_set.files.append(
            ContentFile(b2_path="file3.pdf", filename="file3.pdf", sequence_number=3)
        )
        
        self.agent.validate_completeness(content_set)
        
        # Should now be complete
        self.assertTrue(content_set.is_complete)
        self.assertEqual(len(content_set.missing_files), 0)
    
    def test_resolve_order(self):
        """Test ordering resolution"""
        # Create a content set with files in random order
        files = [
            ContentFile(b2_path="file3.pdf", filename="file3.pdf", sequence_number=3),
            ContentFile(b2_path="file1.pdf", filename="file1.pdf", sequence_number=1),
            ContentFile(b2_path="file2.pdf", filename="file2.pdf", sequence_number=2),
        ]
        
        content_set = ContentSet(
            id="test-id",
            name="Test Set",
            detection_method="pattern",
            files=files
        )
        
        # Resolve order
        ordered_files = self.agent.resolve_order(content_set)
        
        # Should be ordered by sequence number
        self.assertEqual(ordered_files[0].sequence_number, 1)
        self.assertEqual(ordered_files[1].sequence_number, 2)
        self.assertEqual(ordered_files[2].sequence_number, 3)
    
    def test_generate_manifest(self):
        """Test manifest generation"""
        # Create a complete content set
        files = [
            ContentFile(b2_path="file1.pdf", filename="file1.pdf", sequence_number=1),
            ContentFile(b2_path="file2.pdf", filename="file2.pdf", sequence_number=2),
            ContentFile(b2_path="file3.pdf", filename="file3.pdf", sequence_number=3),
        ]
        
        content_set = ContentSet(
            id="test-id",
            name="Test Set",
            detection_method="pattern",
            files=files,
            is_complete=True
        )
        
        # Generate manifest
        manifest = self.agent.generate_manifest(content_set)
        
        # Verify manifest
        self.assertEqual(manifest.content_set_id, "test-id")
        self.assertEqual(manifest.total_files, 3)
        self.assertEqual(len(manifest.ordered_files), 3)
        self.assertEqual(len(manifest.warnings), 0)
        
        # Check dependencies
        self.assertEqual(len(manifest.ordered_files[0].dependencies), 0)  # First file has no dependencies
        self.assertEqual(len(manifest.ordered_files[1].dependencies), 1)  # Second depends on first
        self.assertEqual(len(manifest.ordered_files[2].dependencies), 1)  # Third depends on second
    
    @patch('app.services.content_prep_agent.ContentPrepAgent._request_user_clarification')
    async def test_resolve_order_with_clarification(self, mock_clarification):
        """Test ordering with user clarification"""
        # Create a content set with some files missing sequence numbers
        files = [
            ContentFile(b2_path="file1.pdf", filename="file1.pdf", sequence_number=1),
            ContentFile(b2_path="fileA.pdf", filename="fileA.pdf", sequence_number=None),
            ContentFile(b2_path="fileB.pdf", filename="fileB.pdf", sequence_number=None),
        ]
        
        content_set = ContentSet(
            id="test-id",
            name="Test Set",
            detection_method="pattern",
            files=files
        )
        
        # Mock user clarification response
        mock_clarification.return_value = "fileA.pdf, fileB.pdf"
        
        # Resolve order with clarification
        ordered_files = await self.agent.resolve_order_with_clarification(content_set, confidence_threshold=0.9)
        
        # Should have requested clarification
        mock_clarification.assert_called_once()
        
        # Should be ordered according to user input
        self.assertEqual(ordered_files[0].filename, "file1.pdf")  # Has sequence number, comes first
        self.assertEqual(ordered_files[1].filename, "fileA.pdf")  # From user input
        self.assertEqual(ordered_files[2].filename, "fileB.pdf")  # From user input

# Performance tests
@pytest.mark.benchmark
def test_performance_large_set(benchmark):
    """Benchmark performance with large file sets"""
    agent = ContentPrepAgent()
    
    # Generate 100 test files
    large_set = []
    for i in range(1, 101):
        large_set.append({
            "path": f"pending/course/module-{i:02d}.pdf",
            "size": 1024 * 1024,
            "type": "pdf"
        })
    
    # Benchmark content set detection
    result = benchmark(agent.detect_content_sets, large_set)
    
    # Verify result
    content_sets, standalone = result
    assert len(content_sets) == 1
    assert len(content_sets[0].files) == 100
```

Create integration tests for the API endpoints:

```python
# In tests/test_content_prep_api.py

from fastapi.testclient import TestClient
from app.main import app
import pytest
from unittest.mock import patch

client = TestClient(app)

@pytest.fixture
def mock_content_prep_agent():
    with patch('app.routes.content_prep.ContentPrepAgent') as mock:
        yield mock

def test_analyze_endpoint(mock_content_prep_agent):
    """Test the analyze endpoint"""
    # Mock agent response
    mock_instance = mock_content_prep_agent.return_value
    mock_instance.detect_content_sets.return_value = ([], [])
    
    # Test API
    response = client.post(
        "/api/content-prep/analyze",
        json={"b2_folder": "pending/test/", "detection_mode": "auto"}
    )
    
    # Verify response
    assert response.status_code == 200
    assert "content_sets" in response.json()
    assert "standalone_files" in response.json()
    
    # Verify agent was called correctly
    mock_instance.detect_content_sets.assert_called_once()

def test_manifest_endpoint(mock_content_prep_agent):
    """Test the manifest endpoint"""
    # Mock agent response
    mock_instance = mock_content_prep_agent.return_value
    mock_instance.generate_manifest.return_value = {
        "content_set_id": "test-id",
        "ordered_files": [],
        "total_files": 0,
        "estimated_processing_time": 0,
        "warnings": [],
        "context": {}
    }
    
    # Test API
    response = client.post(
        "/api/content-prep/manifest",
        json={"content_set_id": "test-id", "proceed_incomplete": True}
    )
    
    # Verify response
    assert response.status_code == 200
    assert "content_set_id" in response.json()
    assert "ordered_files" in response.json()
    
    # Verify agent was called correctly
    mock_instance.generate_manifest.assert_called_once()
```

**Test Strategy:**

1. Run unit tests for each component
2. Run integration tests with mocked dependencies
3. Run performance benchmarks with large file sets
4. Test with various file naming patterns
5. Test error handling and edge cases
6. Verify test coverage meets targets (>90%)
7. Run tests in CI/CD pipeline
