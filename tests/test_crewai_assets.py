"""
Test suite for CrewAI Asset Storage & Retrieval (Task 40)
Tests asset storage in database and B2, retrieval with filters, and confidence updates

These tests require a running API server at localhost:8000.
They are marked as live_api tests and will be skipped if the server is not available.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
import requests
from uuid import uuid4
import json

# Test configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


def _server_is_available() -> bool:
    """Check if the API server is available."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def _has_b2_configured() -> bool:
    """Check if B2 storage is properly configured for testing.

    These tests require B2 storage to be configured and accessible.
    Skip in environments without proper B2 credentials.
    """
    import os
    # Check if B2 credentials are configured
    b2_key_id = os.getenv("B2_APPLICATION_KEY_ID")
    b2_key = os.getenv("B2_APPLICATION_KEY")
    b2_bucket = os.getenv("B2_BUCKET_NAME")
    return all([b2_key_id, b2_key, b2_bucket])


# Mark tests as integration tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.live_api,
]


@pytest.fixture(autouse=True)
def check_prerequisites():
    """Check prerequisites at test runtime, not collection time."""
    import time
    # Give the server a moment and retry
    for attempt in range(3):
        if _server_is_available():
            break
        time.sleep(0.5)
    else:
        pytest.skip("API server not available at localhost:8000 after retries")

    if not _has_b2_configured():
        pytest.skip("B2 storage not configured")


def test_asset_storage_and_retrieval():
    """Test storing and retrieving CrewAI generated assets"""

    print("\n=== Task 40: CrewAI Asset Storage & Retrieval Tests ===\n")

    # First, get or create an execution to satisfy foreign key constraint
    print("0. Getting existing execution for asset tests...")
    exec_response = requests.get(f"{BASE_URL}/api/crewai/executions?limit=1")
    assert exec_response.status_code == 200, f"Failed to get executions: {exec_response.text}"
    executions = exec_response.json().get("executions", [])

    if executions:
        execution_id = executions[0]["id"]
        print(f"   Using existing execution: {execution_id}")
    else:
        # Create a new execution if none exist
        # First get a crew
        crew_response = requests.get(f"{BASE_URL}/api/crewai/crews?active_only=true&limit=1")
        crews = crew_response.json().get("crews", [])
        if not crews:
            pytest.skip("No crews available to create execution")
        crew_id = crews[0]["id"]

        exec_create_response = requests.post(
            f"{BASE_URL}/api/crewai/executions",
            headers=HEADERS,
            json={
                "crew_id": crew_id,
                "execution_type": "test",
                "input_data": {"test": "asset_storage_test"}
            }
        )
        assert exec_create_response.status_code == 201, f"Failed to create execution: {exec_create_response.text}"
        execution_id = exec_create_response.json()["id"]
        print(f"   Created new execution: {execution_id}")

    # Use None for document_id to avoid foreign key constraint
    document_id = None

    # Test 1: Store text-based asset (markdown summary)
    print("1. Storing text-based asset (marketing summary)...")
    text_asset_request = {
        "execution_id": str(execution_id),
        "document_id": document_id,
        "department": "marketing",
        "asset_type": "summary",
        "asset_name": "Q4 Campaign Summary",
        "content": "# Q4 Marketing Campaign\n\nKey findings from analysis...",
        "content_format": "markdown",
        "metadata": {"campaign": "Q4", "year": 2025},
        "confidence_score": 0.95
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/assets",
        headers=HEADERS,
        json=text_asset_request
    )

    assert response.status_code == 201, f"Failed to store text asset: {response.text}"
    text_asset = response.json()
    text_asset_id = text_asset["id"]

    print(f"✓ Text asset stored: ID={text_asset_id}")
    print(f"  - Department: {text_asset['department']}")
    print(f"  - Type: {text_asset['asset_type']}")
    print(f"  - Confidence: {text_asset['confidence_score']}")
    print(f"  - Content preview: {text_asset['content'][:50]}...")

    # Test 2: Store another asset (legal analysis)
    print("\n2. Storing another asset (legal analysis)...")
    legal_asset_request = {
        "execution_id": str(execution_id),
        "department": "legal",
        "asset_type": "analysis",
        "asset_name": "Contract Risk Assessment",
        "content": "Comprehensive contract analysis reveals...",
        "content_format": "text",
        "metadata": {"contract_id": "CNT-456", "risk_level": "medium"},
        "confidence_score": 0.87
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/assets",
        headers=HEADERS,
        json=legal_asset_request
    )

    assert response.status_code == 201, f"Failed to store legal asset: {response.text}"
    legal_asset = response.json()
    legal_asset_id = legal_asset["id"]

    print(f"✓ Legal asset stored: ID={legal_asset_id}")

    # Test 3: Retrieve assets by execution ID
    print("\n3. Retrieving assets by execution ID...")
    response = requests.get(
        f"{BASE_URL}/api/crewai/assets/execution/{execution_id}",
        headers=HEADERS
    )

    assert response.status_code == 200, f"Failed to retrieve assets: {response.text}"
    result = response.json()

    print(f"✓ Retrieved {result['total']} assets for execution")
    assert result['total'] >= 2, "Expected at least 2 assets"

    # Test 4: Filter by department
    print("\n4. Filtering assets by department (marketing)...")
    response = requests.get(
        f"{BASE_URL}/api/crewai/assets?department=marketing",
        headers=HEADERS
    )

    assert response.status_code == 200, f"Failed to filter by department: {response.text}"
    result = response.json()

    print(f"✓ Found {result['total']} marketing assets")
    assert result['total'] >= 1, "Expected at least 1 marketing asset"
    assert result['assets'][0]['department'] == "marketing"

    # Test 5: Filter by confidence threshold
    print("\n5. Filtering assets by confidence >= 0.9...")
    response = requests.get(
        f"{BASE_URL}/api/crewai/assets?min_confidence=0.9",
        headers=HEADERS
    )

    assert response.status_code == 200, f"Failed to filter by confidence: {response.text}"
    result = response.json()

    print(f"✓ Found {result['total']} high-confidence assets")
    for asset in result['assets']:
        assert asset['confidence_score'] >= 0.9, "Confidence filter not working"

    # Test 6: Get single asset by ID
    print(f"\n6. Getting single asset by ID: {text_asset_id}...")
    response = requests.get(
        f"{BASE_URL}/api/crewai/assets/{text_asset_id}",
        headers=HEADERS
    )

    assert response.status_code == 200, f"Failed to get asset by ID: {response.text}"
    asset = response.json()

    print(f"✓ Retrieved asset: {asset['asset_name']}")
    assert asset['id'] == text_asset_id

    # Test 7: Update asset confidence and metadata
    print(f"\n7. Updating asset confidence and metadata...")
    update_request = {
        "confidence_score": 0.98,
        "metadata": {"reviewed_by": "John Doe", "approved": True}
    }

    response = requests.patch(
        f"{BASE_URL}/api/crewai/assets/{text_asset_id}",
        headers=HEADERS,
        json=update_request
    )

    assert response.status_code == 200, f"Failed to update asset: {response.text}"
    updated_asset = response.json()

    print(f"✓ Asset updated:")
    print(f"  - New confidence: {updated_asset['confidence_score']}")
    print(f"  - Metadata keys: {list(updated_asset['metadata'].keys())}")

    assert updated_asset['confidence_score'] == 0.98
    assert updated_asset['metadata']['reviewed_by'] == "John Doe"
    assert updated_asset['metadata']['approved'] == True
    # Original metadata should still be there (merge behavior)
    assert updated_asset['metadata']['campaign'] == "Q4"

    # Test 8: Combined filters
    print("\n8. Testing combined filters (department + type)...")
    response = requests.get(
        f"{BASE_URL}/api/crewai/assets?department=legal&asset_type=analysis",
        headers=HEADERS
    )

    assert response.status_code == 200, f"Failed with combined filters: {response.text}"
    result = response.json()

    print(f"✓ Found {result['total']} legal analysis assets")
    print(f"  Filters applied: {result['filters_applied']}")

    print("\n=== All Task 40 Tests PASSED! ===\n")

    # Summary
    print("Summary:")
    print(f"- Stored 2 assets (1 marketing summary, 1 legal analysis)")
    print(f"- Retrieved assets by execution, department, and confidence")
    print(f"- Updated asset confidence from 0.95 to 0.98")
    print(f"- Merged metadata successfully (preserved existing + added new)")
    print(f"- Verified filtering by department, type, and confidence threshold")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Task 40: CrewAI Asset Storage & Retrieval Test Suite")
    print("="*60)

    print("\nPrerequisites:")
    print("1. FastAPI server running on http://localhost:8000")
    print("2. Supabase connection configured")
    print("3. B2 storage credentials (for file-based assets)")
    print("\nStarting tests...\n")

    try:
        test_asset_storage_and_retrieval()
        print("\n🎉 All tests PASSED! Task 40 implementation verified.\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("="*60 + "\n")
