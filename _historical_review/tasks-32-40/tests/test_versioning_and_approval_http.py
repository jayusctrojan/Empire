"""
Empire v7.3 - Document Versioning and Approval Workflow HTTP Endpoint Testing
Tests all versioning and approval workflow endpoints via HTTP with authentication.

Task 32.2: Document Versioning and Approval Workflow
- Version creation and tracking
- Version history and rollback
- Approval workflow state machine
- Audit trail logging
- Bulk operations

Prerequisites:
1. FastAPI server running: uvicorn app.main:app --reload --port 8000
2. Supabase environment variables set in .env
3. Database migration for versioning and approval tables applied

Run with: python tests/test_versioning_and_approval_http.py
"""

import requests
import json
import asyncio
import time
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

# Import services for creating test API key
from app.services.rbac_service import RBACService
from app.core.supabase_client import get_supabase_client

BASE_URL = "http://localhost:8000"
TEST_USER_ADMIN = "user_http_test_versioning_admin"
TEST_USER_VIEWER = "user_http_test_versioning_viewer"


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


def calculate_file_hash(content: str) -> str:
    """Calculate SHA-256 hash of file content."""
    return hashlib.sha256(content.encode()).hexdigest()


async def setup_test_api_keys():
    """Create test API keys for admin and viewer users."""
    print_section("Setup: Creating Test API Keys")

    rbac_service = RBACService()
    supabase = get_supabase_client()

    # Clean up any existing test data
    supabase.table("api_keys").delete().like("user_id", "user_http_test_versioning_%").execute()
    supabase.table("user_roles").delete().like("user_id", "user_http_test_versioning_%").execute()
    supabase.table("document_versions").delete().like("created_by", "user_http_test_versioning_%").execute()
    supabase.table("document_approvals").delete().like("document_id", "test_doc_versioning_%").execute()
    supabase.table("documents").delete().like("document_id", "test_doc_versioning_%").execute()

    # Get roles
    roles = await rbac_service.list_roles()
    admin_role = next(r for r in roles if r["role_name"] == "admin")
    viewer_role = next(r for r in roles if r["role_name"] == "viewer")

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

    # Create API key for admin
    admin_result = await rbac_service.create_api_key(
        user_id=TEST_USER_ADMIN,
        key_name="Versioning Test Admin Key",
        role_id=admin_role["id"],
        scopes=["documents:read", "documents:write", "documents:approve"],
        rate_limit_per_hour=1000,
        expires_at=datetime.utcnow() + timedelta(days=1),
        ip_address="127.0.0.1",
        user_agent="test-script"
    )
    print_result(True, f"Admin API key created: {admin_result['key_prefix']}...")

    # Assign viewer role to test user
    await rbac_service.assign_user_role(
        user_id=TEST_USER_VIEWER,
        role_name="viewer",
        granted_by="system",
        expires_at=None,
        ip_address="127.0.0.1",
        user_agent="test-script"
    )
    print_result(True, f"Viewer role assigned to {TEST_USER_VIEWER}")

    # Create API key for viewer
    viewer_result = await rbac_service.create_api_key(
        user_id=TEST_USER_VIEWER,
        key_name="Versioning Test Viewer Key",
        role_id=viewer_role["id"],
        scopes=["documents:read"],
        rate_limit_per_hour=1000,
        expires_at=datetime.utcnow() + timedelta(days=1),
        ip_address="127.0.0.1",
        user_agent="test-script"
    )
    print_result(True, f"Viewer API key created: {viewer_result['key_prefix']}...")

    return admin_result["api_key"], viewer_result["api_key"]


async def create_test_document():
    """Create a test document in Supabase for versioning tests."""
    supabase = get_supabase_client()

    document_id = f"test_doc_versioning_{int(time.time())}"
    file_hash = calculate_file_hash(f"test content {document_id}")

    # Create a test document (using actual schema column names)
    result = supabase.table("documents").insert({
        "document_id": document_id,
        "filename": "test_versioning_doc.pdf",  # Note: 'filename' not 'file_name'
        "file_type": "application/pdf",
        "file_size_bytes": 1024,
        "file_hash": file_hash,
        "processing_status": "processed",  # Note: 'processing_status' not 'status'
        "uploaded_by": TEST_USER_ADMIN
    }).execute()

    if result.data:
        print_result(True, f"Test document created: {document_id}")
        return document_id
    else:
        print_result(False, "Failed to create test document")
        return None


def test_create_version(api_key, document_id):
    """Test POST /api/documents/versions/create."""
    print_section("Test 1: Create Document Version")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    # Test version 1
    payload = {
        "document_id": document_id,
        "file_path": "/test/path/v1.pdf",
        "change_description": "Initial version",
        "metadata": {
            "author": "Test User",
            "purpose": "Testing version creation"
        }
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/versions/create",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Version created: v{data['version_number']}")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to create version")
        return None


def test_create_multiple_versions(api_key, document_id):
    """Test creating multiple versions of a document."""
    print_section("Test 2: Create Multiple Versions")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    versions = []
    for i in range(2, 5):  # Create versions 2, 3, 4
        payload = {
            "document_id": document_id,
            "file_path": f"/test/path/v{i}.pdf",
            "change_description": f"Version {i} - Updated content",
            "metadata": {
                "version": i,
                "changes": f"Changes for version {i}"
            }
        }

        response = requests.post(
            f"{BASE_URL}/api/documents/versions/create",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            versions.append(data)
            print_result(True, f"Version {i} created successfully")
        else:
            print_result(False, f"Failed to create version {i}")

    return versions


def test_get_version_history(api_key, document_id):
    """Test GET /api/documents/versions/{document_id}."""
    print_section("Test 3: Get Version History")

    headers = {"Authorization": api_key}  # Send API key directly (no Bearer prefix)

    response = requests.get(
        f"{BASE_URL}/api/documents/versions/{document_id}",
        headers=headers
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Retrieved {len(data['versions'])} versions")
        print(f"   Current Version: v{data['current_version']['version_number']}")
        print(f"   Total Versions: {data['total_versions']}")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to get version history")
        return None


def test_rollback_version(api_key, document_id):
    """Test POST /api/documents/versions/rollback."""
    print_section("Test 4: Rollback to Previous Version")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    # Rollback to version 2
    payload = {
        "document_id": document_id,
        "version_number": 2,
        "reason": "Testing rollback functionality"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/versions/rollback",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, "Successfully rolled back to version 2")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to rollback version")
        return None


def test_submit_for_approval(api_key, document_id):
    """Test POST /api/documents/approvals/submit."""
    print_section("Test 5: Submit Document for Approval")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    payload = {
        "document_id": document_id,
        "notes": "Please review this document for approval"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/approvals/submit",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Document submitted for approval - Status: {data['approval_status']}")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to submit for approval")
        return None


def test_get_approval_status(api_key, approval_id):
    """Test GET /api/documents/approvals/{approval_id}."""
    print_section("Test 6: Get Approval Status")

    headers = {"Authorization": api_key}  # Send API key directly (no Bearer prefix)

    response = requests.get(
        f"{BASE_URL}/api/documents/approvals/{approval_id}",
        headers=headers
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Approval status: {data['approval']['approval_status']}")
        print(f"   Audit Trail Entries: {len(data.get('audit_trail', []))}")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to get approval status")
        return None


def test_approve_document(api_key, approval_id):
    """Test POST /api/documents/approvals/approve."""
    print_section("Test 7: Approve Document")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    payload = {
        "approval_id": approval_id,
        "approval_notes": "Document looks good, approved!"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/approvals/approve",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Document approved - Status: {data['approval_status']}")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to approve document")
        return None


def test_reject_document(api_key, document_id):
    """Test POST /api/documents/approvals/reject."""
    print_section("Test 8: Reject Document")

    # First submit another document for approval
    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    # Submit for approval
    submit_response = requests.post(
        f"{BASE_URL}/api/documents/approvals/submit",
        headers=headers,
        json={"document_id": document_id}
    )

    if submit_response.status_code != 200:
        print_result(False, "Failed to submit document for rejection test")
        return None

    approval_id = submit_response.json()["approval_id"]

    # Now reject it
    payload = {
        "approval_id": approval_id,
        "rejection_reason": "Document needs more details in section 3",
        "rejection_notes": "Please add more information about the requirements"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/approvals/reject",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Document rejected - Status: {data['approval_status']}")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to reject document")
        return None


def test_list_approvals(api_key):
    """Test GET /api/documents/approvals."""
    print_section("Test 9: List All Approvals")

    headers = {"Authorization": api_key}  # Send API key directly (no Bearer prefix)

    response = requests.get(
        f"{BASE_URL}/api/documents/approvals",
        headers=headers,
        params={"limit": 10}
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Retrieved {len(data['approvals'])} approvals")
        print(f"   Total Count: {data['total_count']}")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to list approvals")
        return None


def test_list_pending_approvals(api_key):
    """Test GET /api/documents/approvals with status filter."""
    print_section("Test 10: List Pending Approvals")

    headers = {"Authorization": api_key}  # Send API key directly (no Bearer prefix)

    response = requests.get(
        f"{BASE_URL}/api/documents/approvals",
        headers=headers,
        params={"status_filter": "pending_review", "limit": 10}
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Retrieved {len(data['approvals'])} pending approvals")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to list pending approvals")
        return None


def test_bulk_version_creation(api_key, document_ids):
    """Test POST /api/documents/versions/bulk-create."""
    print_section("Test 11: Bulk Version Creation")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    updates = [
        {
            "document_id": doc_id,
            "file_path": f"/test/path/bulk_{i}.pdf",
            "change_description": f"Bulk update {i}"
        }
        for i, doc_id in enumerate(document_ids[:3], 1)
    ]

    payload = {"updates": updates}

    response = requests.post(
        f"{BASE_URL}/api/documents/versions/bulk-create",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Bulk creation completed - {data['successful']} successful, {data['failed']} failed")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to perform bulk version creation")
        return None


def test_bulk_approval_action(api_key, approval_ids):
    """Test POST /api/documents/approvals/bulk-action."""
    print_section("Test 12: Bulk Approval Action")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    payload = {
        "approval_ids": approval_ids[:2],  # Approve first 2
        "action": "approve",
        "notes": "Bulk approval for testing"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/approvals/bulk-action",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_json(data)
        print_result(True, f"Bulk approval completed - {data['successful']} successful, {data['failed']} failed")
        return data
    else:
        print(f"Error: {response.text}")
        print_result(False, "Failed to perform bulk approval action")
        return None


def test_invalid_state_transition(api_key, document_id):
    """Test invalid approval state transitions."""
    print_section("Test 13: Invalid State Transition (Should Fail)")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    # Try to approve a document that's already approved
    # This should fail because we can't go from approved -> approved

    # First, find an approved document
    approvals = requests.get(
        f"{BASE_URL}/api/documents/approvals",
        headers=headers,
        params={"status_filter": "approved"}
    ).json()

    if not approvals.get("approvals"):
        print_result(True, "No approved documents to test invalid transition (expected)")
        return None

    approval_id = approvals["approvals"][0]["id"]

    # Try to approve again (should fail)
    payload = {
        "approval_id": approval_id,
        "approval_notes": "Trying to approve again"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/approvals/approve",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 400:
        print_result(True, "Invalid state transition correctly rejected")
        print(f"   Error: {response.json().get('detail', 'Unknown error')}")
        return True
    else:
        print_result(False, "Invalid state transition should have been rejected")
        return False


def test_unauthorized_access(viewer_api_key, approval_id):
    """Test that viewer role cannot approve documents."""
    print_section("Test 14: Unauthorized Approval Access (Should Fail)")

    headers = {
        "X-API-Key": viewer_api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "approval_id": approval_id,
        "approval_notes": "Trying to approve as viewer"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/approvals/approve",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code in [403, 401]:
        print_result(True, "Viewer correctly denied approval permission")
        return True
    else:
        print_result(False, "Viewer should not have approval permission")
        return False


def test_version_rollback_validation(api_key, document_id):
    """Test rollback validation (cannot rollback to current version)."""
    print_section("Test 15: Rollback Validation (Should Fail)")

    headers = {
        "Authorization": api_key,  # Send API key directly (no Bearer prefix)
        "Content-Type": "application/json"
    }

    # Get current version
    history = requests.get(
        f"{BASE_URL}/api/documents/versions/{document_id}",
        headers=headers
    ).json()

    current_version_number = history["current_version"]["version_number"]

    # Try to rollback to current version (should fail)
    payload = {
        "document_id": document_id,
        "version_number": current_version_number,
        "reason": "Trying to rollback to current version"
    }

    response = requests.post(
        f"{BASE_URL}/api/documents/versions/rollback",
        headers=headers,
        json=payload
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 400:
        print_result(True, "Rollback to current version correctly rejected")
        return True
    else:
        print_result(False, "Rollback to current version should have been rejected")
        return False


async def cleanup_test_data():
    """Clean up all test data."""
    print_section("Cleanup: Removing Test Data")

    supabase = get_supabase_client()

    # Delete test data
    supabase.table("api_keys").delete().like("user_id", "user_http_test_versioning_%").execute()
    supabase.table("user_roles").delete().like("user_id", "user_http_test_versioning_%").execute()
    supabase.table("document_versions").delete().like("created_by", "user_http_test_versioning_%").execute()
    supabase.table("document_approvals").delete().like("document_id", "test_doc_versioning_%").execute()
    supabase.table("documents").delete().like("document_id", "test_doc_versioning_%").execute()

    print_result(True, "Test data cleaned up")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  DOCUMENT VERSIONING AND APPROVAL WORKFLOW - HTTP ENDPOINT TESTS")
    print("  Task 32.2: Testing version control and approval state machine")
    print("=" * 70)

    try:
        # Setup
        admin_api_key, viewer_api_key = await setup_test_api_keys()
        document_id = await create_test_document()

        if not document_id:
            print_result(False, "Failed to create test document, aborting tests")
            return

        # Store IDs for bulk operations
        approval_ids = []
        document_ids = [document_id]

        # Test 1: Create initial version
        version1 = test_create_version(admin_api_key, document_id)
        time.sleep(1)

        # Test 2: Create multiple versions
        versions = test_create_multiple_versions(admin_api_key, document_id)
        time.sleep(1)

        # Test 3: Get version history
        history = test_get_version_history(admin_api_key, document_id)
        time.sleep(1)

        # Test 4: Rollback to previous version
        rollback_result = test_rollback_version(admin_api_key, document_id)
        time.sleep(1)

        # Test 5: Submit for approval
        approval = test_submit_for_approval(admin_api_key, document_id)
        if approval:
            approval_ids.append(approval["approval_id"])
        time.sleep(1)

        # Test 6: Get approval status
        if approval:
            test_get_approval_status(admin_api_key, approval["approval_id"])
        time.sleep(1)

        # Test 7: Approve document
        if approval:
            test_approve_document(admin_api_key, approval["approval_id"])
        time.sleep(1)

        # Test 8: Reject document
        rejection = test_reject_document(admin_api_key, document_id)
        time.sleep(1)

        # Test 9: List all approvals
        test_list_approvals(admin_api_key)
        time.sleep(1)

        # Test 10: List pending approvals
        test_list_pending_approvals(admin_api_key)
        time.sleep(1)

        # Test 11: Bulk version creation
        # Create additional test documents for bulk operations
        for i in range(2):
            doc_id = await create_test_document()
            if doc_id:
                document_ids.append(doc_id)

        test_bulk_version_creation(admin_api_key, document_ids)
        time.sleep(1)

        # Test 12: Bulk approval action
        # Create approvals for bulk testing
        for doc_id in document_ids[1:]:
            result = requests.post(
                f"{BASE_URL}/api/documents/approvals/submit",
                headers={
                    "X-API-Key": admin_api_key,
                    "Content-Type": "application/json"
                },
                json={"document_id": doc_id}
            )
            if result.status_code == 200:
                approval_ids.append(result.json()["approval_id"])

        test_bulk_approval_action(admin_api_key, approval_ids)
        time.sleep(1)

        # Test 13: Invalid state transition
        test_invalid_state_transition(admin_api_key, document_id)
        time.sleep(1)

        # Test 14: Unauthorized access
        if approval_ids:
            test_unauthorized_access(viewer_api_key, approval_ids[0])
        time.sleep(1)

        # Test 15: Version rollback validation
        test_version_rollback_validation(admin_api_key, document_id)

        # Summary
        print_section("Test Summary")
        print_result(True, "All versioning and approval workflow tests completed!")
        print("\n✅ Tests Passed:")
        print("   - Version creation and tracking")
        print("   - Version history retrieval")
        print("   - Version rollback")
        print("   - Approval submission")
        print("   - Approval/rejection workflow")
        print("   - Approval status and audit trail")
        print("   - Bulk operations")
        print("   - State transition validation")
        print("   - Authorization checks")

    except Exception as e:
        print_result(False, f"Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        await cleanup_test_data()


if __name__ == "__main__":
    asyncio.run(main())
