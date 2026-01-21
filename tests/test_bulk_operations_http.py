"""
Empire v7.3 - Bulk Document Operations HTTP Endpoint Testing
Tests all bulk document operation endpoints via HTTP with authentication.

Prerequisites:
1. FastAPI server running: uvicorn app.main:app --reload --port 8000
2. Supabase environment variables set in .env
3. Celery worker running (for async task processing)

NOTE: These are INTEGRATION tests - run with: python tests/test_bulk_operations_http.py
"""

import pytest
import requests
import json
import asyncio
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os


def _local_server_is_available() -> bool:
    """Check if the local FastAPI server is available."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        return False


# Mark all tests in this module as integration tests that require a running server
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _local_server_is_available(),
        reason="Local FastAPI server not running on port 8000"
    ),
]

# Load environment
load_dotenv()

# Import services for creating test API key
from app.services.rbac_service import RBACService
from app.core.supabase_client import get_supabase_client

BASE_URL = "http://localhost:8000"
TEST_USER_ADMIN = "user_http_test_bulk_ops_admin"


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(success, message):
    """Print test result."""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")


def print_json(data, indent=2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent))


async def setup_test_api_key():
    """Create a test API key directly via service."""
    print_section("Setup: Creating Test API Key")

    rbac_service = RBACService()
    supabase = get_supabase_client()

    # Clean up any existing test data
    supabase.table("api_keys").delete().like("user_id", "user_http_test_bulk_%").execute()
    supabase.table("user_roles").delete().like("user_id", "user_http_test_bulk_%").execute()
    supabase.table("batch_operations").delete().like("user_id", "user_http_test_bulk_%").execute()

    # Get admin role
    roles = await rbac_service.list_roles()
    admin_role = next(r for r in roles if r["role_name"] == "admin")

    # Assign admin role to test user
    await rbac_service.assign_user_role(
        user_id=TEST_USER_ADMIN,
        role_name="admin",
        granted_by="system",
        expires_at=None,
        ip_address="127.0.0.1",
        user_agent="test-script"
    )
    print_result(True, f"Admin role assigned to {TEST_USER_ADMIN}")

    # Create API key
    result = await rbac_service.create_api_key(
        user_id=TEST_USER_ADMIN,
        key_name="Bulk Operations Test Key",
        role_id=admin_role["id"],
        scopes=["documents:read", "documents:write", "documents:delete"],
        rate_limit_per_hour=1000,
        expires_at=datetime.utcnow() + timedelta(days=1),
        ip_address="127.0.0.1",
        user_agent="test-script"
    )

    print_result(True, f"Test API key created: {result['key_prefix']}...")
    print(f"   Full Key: {result['api_key']}")
    print(f"   Key ID: {result['key_id']}")

    return result["api_key"], result["key_id"]


# ==================== Pytest Fixtures ====================

@pytest.fixture(scope="module")
def api_key():
    """Create and return an admin API key for testing."""
    key, _ = asyncio.get_event_loop().run_until_complete(setup_test_api_key())
    yield key


@pytest.fixture(scope="module")
def operation_id():
    """Placeholder for operation ID - will be set during tests."""
    return None


@pytest.fixture(scope="module")
def viewer_api_key():
    """Return an invalid/viewer API key for testing unauthorized access."""
    return "invalid_viewer_key_for_testing"


# ==================== Test Functions ====================

def test_bulk_upload(api_key):
    """Test POST /api/documents/bulk-upload."""
    print_section("Test 1: Bulk Upload Documents")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    payload = {
        "documents": [
            {
                "file_path": "/test/path/doc1.pdf",
                "filename": "test_doc1.pdf",
                "metadata": {
                    "category": "test",
                    "tags": ["test", "bulk-upload"]
                },
                "user_id": TEST_USER_ADMIN
            },
            {
                "file_path": "/test/path/doc2.pdf",
                "filename": "test_doc2.pdf",
                "metadata": {
                    "category": "test",
                    "tags": ["test", "bulk-upload"]
                },
                "user_id": TEST_USER_ADMIN
            }
        ],
        "auto_process": True,
        "notification_email": "test@example.com"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/documents/bulk-upload",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Bulk upload operation queued")
            print(f"   Operation ID: {data.get('operation_id')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Total Items: {data.get('total_items')}")
            print(f"   Message: {data.get('message')}")
            return data.get('operation_id')
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print_json(response.json())
            return None

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return None


def test_bulk_delete(api_key):
    """Test POST /api/documents/bulk-delete."""
    print_section("Test 2: Bulk Delete Documents")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    payload = {
        "document_ids": [
            "test_doc_id_1",
            "test_doc_id_2",
            "test_doc_id_3"
        ],
        "soft_delete": True,
        "reason": "Testing bulk delete functionality"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/documents/bulk-delete",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Bulk delete operation queued")
            print(f"   Operation ID: {data.get('operation_id')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Total Items: {data.get('total_items')}")
            print(f"   Message: {data.get('message')}")
            return data.get('operation_id')
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print_json(response.json())
            return None

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return None


def test_bulk_reprocess(api_key):
    """Test POST /api/documents/bulk-reprocess."""
    print_section("Test 3: Bulk Reprocess Documents")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    payload = {
        "document_ids": [
            "test_doc_id_1",
            "test_doc_id_2"
        ],
        "options": {
            "force_reparse": True,
            "update_embeddings": True,
            "preserve_metadata": True
        }
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/documents/bulk-reprocess",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Bulk reprocess operation queued")
            print(f"   Operation ID: {data.get('operation_id')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Total Items: {data.get('total_items')}")
            print(f"   Message: {data.get('message')}")
            return data.get('operation_id')
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print_json(response.json())
            return None

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return None


def test_bulk_metadata_update(api_key):
    """Test PATCH /api/documents/bulk-metadata."""
    print_section("Test 4: Bulk Metadata Update")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    payload = {
        "updates": [
            {
                "document_id": "test_doc_id_1",
                "metadata": {
                    "status": "updated",
                    "tags": ["bulk-test", "updated"],
                    "last_modified_by": TEST_USER_ADMIN
                }
            },
            {
                "document_id": "test_doc_id_2",
                "metadata": {
                    "status": "updated",
                    "tags": ["bulk-test", "updated"],
                    "last_modified_by": TEST_USER_ADMIN
                }
            }
        ]
    }

    try:
        response = requests.patch(
            f"{BASE_URL}/api/documents/bulk-metadata",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Bulk metadata update operation queued")
            print(f"   Operation ID: {data.get('operation_id')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Total Items: {data.get('total_items')}")
            print(f"   Message: {data.get('message')}")
            return data.get('operation_id')
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print_json(response.json())
            return None

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return None


def test_get_operation_status(api_key, operation_id):
    """Test GET /api/documents/batch-operations/{operation_id}."""
    print_section(f"Test 5: Get Batch Operation Status ({operation_id})")

    headers = {
        "Authorization": api_key  # Send API key directly (no Bearer prefix)
    }

    try:
        response = requests.get(
            f"{BASE_URL}/api/documents/batch-operations/{operation_id}",
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Operation status retrieved")
            print(f"   Operation ID: {data.get('operation_id')}")
            print(f"   Operation Type: {data.get('operation_type')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Progress: {data.get('progress_percentage', 0):.1f}%")
            print(f"   Total Items: {data.get('total_items')}")
            print(f"   Processed: {data.get('processed_items')}")
            print(f"   Successful: {data.get('successful_items')}")
            print(f"   Failed: {data.get('failed_items')}")
            if data.get('error_message'):
                print(f"   Error: {data.get('error_message')}")
            return True
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print_json(response.json())
            return False

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False


def test_list_operations(api_key):
    """Test GET /api/documents/batch-operations."""
    print_section("Test 6: List Batch Operations")

    headers = {
        "Authorization": api_key  # Send API key directly (no Bearer prefix)
    }

    try:
        response = requests.get(
            f"{BASE_URL}/api/documents/batch-operations",
            headers=headers,
            params={"limit": 10, "offset": 0}
        )

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Retrieved {len(data)} batch operations")

            for i, operation in enumerate(data[:3], 1):  # Show first 3
                print(f"\n   Operation {i}:")
                print(f"     ID: {operation.get('operation_id')}")
                print(f"     Type: {operation.get('operation_type')}")
                print(f"     Status: {operation.get('status')}")
                print(f"     Progress: {operation.get('progress_percentage', 0):.1f}%")
                print(f"     Created: {operation.get('created_at')}")

            if len(data) > 3:
                print(f"\n   ... and {len(data) - 3} more operations")

            return True
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print_json(response.json())
            return False

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False


def test_status_filter(api_key):
    """Test GET /api/documents/batch-operations with status filter."""
    print_section("Test 7: List Operations with Status Filter (queued)")

    headers = {
        "Authorization": api_key  # Send API key directly (no Bearer prefix)
    }

    try:
        response = requests.get(
            f"{BASE_URL}/api/documents/batch-operations",
            headers=headers,
            params={"status_filter": "queued", "limit": 5}
        )

        if response.status_code == 200:
            data = response.json()
            print_result(True, f"Retrieved {len(data)} queued operations")

            for operation in data:
                print(f"   - {operation.get('operation_type')}: {operation.get('operation_id')}")

            return True
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print_json(response.json())
            return False

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False


def test_unauthorized_access():
    """Test endpoints without authentication (should fail)."""
    print_section("Test 8: Unauthorized Access (No API Key)")

    payload = {"documents": [{"file_path": "/test", "filename": "test.pdf"}], "auto_process": True}

    try:
        response = requests.post(
            f"{BASE_URL}/api/documents/bulk-upload",
            json=payload
        )

        if response.status_code == 401:
            print_result(True, "Correctly rejected unauthorized request")
            return True
        else:
            print_result(False, f"Unexpected status code: {response.status_code}")
            print_json(response.json())
            return False

    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False


async def cleanup_test_data():
    """Clean up test data after tests complete."""
    print_section("Cleanup: Removing Test Data")

    supabase = get_supabase_client()

    try:
        # Delete test API keys
        supabase.table("api_keys").delete().like("user_id", "user_http_test_bulk_%").execute()
        print_result(True, "Deleted test API keys")

        # Delete test user roles
        supabase.table("user_roles").delete().like("user_id", "user_http_test_bulk_%").execute()
        print_result(True, "Deleted test user roles")

        # Delete test batch operations
        supabase.table("batch_operations").delete().like("user_id", "user_http_test_bulk_%").execute()
        print_result(True, "Deleted test batch operations")

    except Exception as e:
        print_result(False, f"Cleanup error: {str(e)}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  EMPIRE V7.3 - BULK DOCUMENT OPERATIONS HTTP TESTS")
    print("=" * 70)

    # Setup
    api_key, key_id = await setup_test_api_key()

    # Track test results
    results = []

    # Run tests
    operation_ids = []

    # Test 1: Bulk Upload
    upload_op_id = test_bulk_upload(api_key)
    results.append(("Bulk Upload", upload_op_id is not None))
    if upload_op_id:
        operation_ids.append(upload_op_id)

    # Test 2: Bulk Delete
    delete_op_id = test_bulk_delete(api_key)
    results.append(("Bulk Delete", delete_op_id is not None))
    if delete_op_id:
        operation_ids.append(delete_op_id)

    # Test 3: Bulk Reprocess
    reprocess_op_id = test_bulk_reprocess(api_key)
    results.append(("Bulk Reprocess", reprocess_op_id is not None))
    if reprocess_op_id:
        operation_ids.append(reprocess_op_id)

    # Test 4: Bulk Metadata Update
    metadata_op_id = test_bulk_metadata_update(api_key)
    results.append(("Bulk Metadata Update", metadata_op_id is not None))
    if metadata_op_id:
        operation_ids.append(metadata_op_id)

    # Test 5: Get Operation Status (for first operation if available)
    if operation_ids:
        status_result = test_get_operation_status(api_key, operation_ids[0])
        results.append(("Get Operation Status", status_result))

    # Test 6: List Operations
    list_result = test_list_operations(api_key)
    results.append(("List Operations", list_result))

    # Test 7: Status Filter
    filter_result = test_status_filter(api_key)
    results.append(("Status Filter", filter_result))

    # Test 8: Unauthorized Access
    unauth_result = test_unauthorized_access()
    results.append(("Unauthorized Access", unauth_result))

    # Summary
    print_section("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\nTests Passed: {passed}/{total}")
    print("\nDetailed Results:")
    for test_name, result in results:
        print_result(result, test_name)

    # Cleanup
    await cleanup_test_data()

    print("\n" + "=" * 70)
    print(f"  ALL TESTS COMPLETED - {passed}/{total} PASSED")
    print("=" * 70 + "\n")

    # Exit with appropriate code
    exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
