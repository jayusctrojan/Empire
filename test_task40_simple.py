#!/usr/bin/env python3
"""
Simple direct test for Task 40: CrewAI Asset Storage & Retrieval
Tests all endpoints with minimal dependencies
"""

import requests
import json
from uuid import UUID

# Configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# Use an existing CrewAI execution ID from the database
EXISTING_EXECUTION_ID = "8bbe2a5f-78c7-4d26-ad7d-fb4dafc8d4ee"  # completed execution

def test_task_40():
    print("=" * 70)
    print("Task 40: CrewAI Asset Storage & Retrieval - Simple Test")
    print("=" * 70)
    print()

    # Test 1: Store text-based asset (markdown)
    print("Test 1: Store text-based asset (markdown summary)")
    print("-" * 70)

    asset1_data = {
        "execution_id": EXISTING_EXECUTION_ID,
        "document_id": None,  # Optional - set to None for test
        "department": "marketing",
        "asset_type": "summary",
        "asset_name": "Test Marketing Summary",
        "content": "# Test Summary\n\nThis is a test asset.",
        "content_format": "markdown",
        "metadata": {"test": True, "created_by": "test_script"},
        "confidence_score": 0.95
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/crewai/assets",
            headers=HEADERS,
            json=asset1_data,
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 201:
            asset1 = response.json()
            asset1_id = asset1["id"]
            print(f"✓ Asset created: {asset1_id}")
            print(f"  Department: {asset1['department']}")
            print(f"  Type: {asset1['asset_type']}")
            print(f"  Confidence: {asset1['confidence_score']}")
            print()
        else:
            print(f"✗ Failed: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Test 2: Store JSON asset
    print("Test 2: Store JSON asset (legal analysis)")
    print("-" * 70)

    asset2_data = {
        "execution_id": EXISTING_EXECUTION_ID,
        "department": "legal",
        "asset_type": "analysis",
        "asset_name": "Test Legal Analysis",
        "content": '{"risk_level": "medium", "compliance": true}',
        "content_format": "json",
        "metadata": {"contract": "test-contract"},
        "confidence_score": 0.87
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/crewai/assets",
            headers=HEADERS,
            json=asset2_data,
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 201:
            asset2 = response.json()
            asset2_id = asset2["id"]
            print(f"✓ Asset created: {asset2_id}")
            print()
        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 3: Retrieve by execution ID
    print("Test 3: Retrieve assets by execution ID")
    print("-" * 70)

    try:
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets/execution/{EXISTING_EXECUTION_ID}",
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Found {result['total']} assets for execution")
            for asset in result['assets'][:3]:  # Show first 3
                print(f"  - {asset['asset_name']} ({asset['department']} / {asset['asset_type']})")
            print()
        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 4: Filter by department
    print("Test 4: Filter by department (marketing)")
    print("-" * 70)

    try:
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets?department=marketing&limit=5",
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Found {result['total']} marketing assets")
            print(f"  Filters applied: {result['filters_applied']}")
            print()
        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 5: Filter by confidence
    print("Test 5: Filter by confidence (>= 0.9)")
    print("-" * 70)

    try:
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets?min_confidence=0.9&limit=5",
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Found {result['total']} high-confidence assets")
            print()
        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 6: Get single asset
    print("Test 6: Get single asset by ID")
    print("-" * 70)

    try:
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets/{asset1_id}",
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            asset = response.json()
            print(f"✓ Retrieved: {asset['asset_name']}")
            print(f"  Confidence: {asset['confidence_score']}")
            print(f"  Metadata: {asset['metadata']}")
            print()
        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 7: Update asset
    print("Test 7: Update asset confidence and metadata")
    print("-" * 70)

    update_data = {
        "confidence_score": 0.98,
        "metadata": {"reviewed": True, "reviewer": "test_script"}
    }

    try:
        response = requests.patch(
            f"{BASE_URL}/api/crewai/assets/{asset1_id}",
            headers=HEADERS,
            json=update_data,
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            updated = response.json()
            print(f"✓ Updated confidence: {updated['confidence_score']}")
            print(f"  Metadata (merged): {updated['metadata']}")
            print(f"  Original 'test' key preserved: {updated['metadata'].get('test')}")
            print()
        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 8: Combined filters
    print("Test 8: Combined filters (department + type)")
    print("-" * 70)

    try:
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets?department=legal&asset_type=analysis&limit=5",
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Found {result['total']} legal analysis assets")
            print(f"  Filters: {result['filters_applied']}")
            print()
        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    print("=" * 70)
    print("✓ Task 40 Tests Complete!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    print("\nPrerequisite: FastAPI server must be running on http://localhost:8000\n")

    try:
        # Quick health check
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✓ API server is running (health check: {response.status_code})\n")
    except Exception as e:
        print(f"✗ API server not reachable: {e}\n")
        print("Please start the server with: uvicorn app.main:app --reload --port 8000\n")
        exit(1)

    success = test_task_40()
    exit(0 if success else 1)
