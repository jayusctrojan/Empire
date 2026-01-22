"""
Empire v7.3 - Complete RBAC HTTP Endpoint Testing
Tests all RBAC endpoints via HTTP with authentication.

Prerequisites:
1. FastAPI server running: uvicorn app.main:app --reload --port 8000
2. Supabase environment variables set in .env

Run with: python tests/test_rbac_http_complete.py
"""
import pytest
import requests


def _local_server_is_available() -> bool:
    """Check if the local FastAPI server is available."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        return False


# Mark all tests in this module as integration tests that require local server
pytestmark = [
    pytest.mark.integration,
    pytest.mark.local_server,
    pytest.mark.skipif(
        not _local_server_is_available(),
        reason="Local FastAPI server not running on port 8000"
    ),
]
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

# Import services for creating test API key
from app.services.rbac_service import RBACService
from app.core.supabase_client import get_supabase_client

BASE_URL = "http://localhost:8000"
TEST_USER_ADMIN = "user_http_test_admin_001"
TEST_USER_EDITOR = "user_http_test_editor_001"


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
    supabase.table("api_keys").delete().like("user_id", "user_http_test_%").execute()
    supabase.table("user_roles").delete().like("user_id", "user_http_test_%").execute()

    # Get admin role
    roles = await rbac_service.list_roles()
    admin_role = next(r for r in roles if r["role_name"] == "admin")

    # IMPORTANT: Assign admin role to test user first
    # This is required for admin-only endpoints (assign_user_role, get_audit_logs, etc.)
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
        key_name="HTTP Test Admin Key",
        role_id=admin_role["id"],
        scopes=["documents:read", "documents:write"],
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
def auth_key():
    """Create and return an admin API key for testing."""
    api_key, _ = asyncio.get_event_loop().run_until_complete(setup_test_api_key())
    yield api_key


@pytest.fixture(scope="module")
def key_id():
    """Create and return an API key ID for testing."""
    _, key_id = asyncio.get_event_loop().run_until_complete(setup_test_api_key())
    yield key_id


@pytest.fixture(scope="module")
def user_id():
    """Return the test user ID."""
    return TEST_USER_EDITOR


# ==================== Test Functions ====================

def test_list_roles():
    """Test GET /api/rbac/roles (public endpoint)."""
    print_section("Test 1: List Roles (Public)")

    try:
        response = requests.get(f"{BASE_URL}/api/rbac/roles")

        if response.status_code == 200:
            roles = response.json()
            print_result(True, f"Retrieved {len(roles)} roles")

            for role in roles:
                print(f"   - {role['role_name']}: {role['description']}")

            return True
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def test_create_api_key(auth_key):
    """Test POST /api/rbac/keys (authenticated)."""
    print_section("Test 2: Create API Key via HTTP")

    headers = {
        "Authorization": auth_key,
        "Content-Type": "application/json"
    }

    payload = {
        "key_name": "HTTP Created Key",
        "role_id": None,  # Will be set below
        "scopes": ["documents:read"],
        "rate_limit_per_hour": 500,
        "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
    }

    try:
        # First get admin role ID
        roles = requests.get(f"{BASE_URL}/api/rbac/roles").json()
        admin_role = next(r for r in roles if r["role_name"] == "admin")
        payload["role_id"] = admin_role["id"]

        response = requests.post(
            f"{BASE_URL}/api/rbac/keys",
            headers=headers,
            json=payload
        )

        if response.status_code == 201:
            result = response.json()
            print_result(True, "API key created via HTTP")
            print(f"   Key ID: {result['key_id']}")
            print(f"   Key Name: {result['key_name']}")
            print(f"   Key Prefix: {result['key_prefix']}")
            print(f"   ⚠️  Full key shown only once: {result['api_key']}")
            return result
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_list_api_keys(auth_key):
    """Test GET /api/rbac/keys (authenticated)."""
    print_section("Test 3: List API Keys")

    headers = {"Authorization": auth_key}

    try:
        response = requests.get(
            f"{BASE_URL}/api/rbac/keys",
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            print_result(True, f"Retrieved {result['total']} API keys")

            for key in result['keys']:
                print(f"   - {key['key_name']}")
                print(f"     Prefix: {key['key_prefix']}")
                print(f"     Active: {key['is_active']}")
                print(f"     Usage: {key['usage_count']} calls")
                print(f"     Created: {key['created_at']}")

            return result
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_rotate_api_key(auth_key, key_id):
    """Test POST /api/rbac/keys/rotate (authenticated)."""
    print_section("Test 4: Rotate API Key")

    headers = {
        "Authorization": auth_key,
        "Content-Type": "application/json"
    }

    payload = {
        "key_id": key_id,
        "new_key_name": "HTTP Rotated Key",
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/rbac/keys/rotate",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            result = response.json()
            print_result(True, "API key rotated successfully")
            print(f"   Old Key ID: {key_id}")
            print(f"   New Key ID: {result['key_id']}")
            print(f"   New Key Prefix: {result['key_prefix']}")
            print(f"   New Full Key: {result['api_key']}")
            return result
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_assign_role(auth_key):
    """Test POST /api/rbac/users/assign-role (authenticated, admin only)."""
    print_section("Test 5: Assign User Role")

    headers = {
        "Authorization": auth_key,
        "Content-Type": "application/json"
    }

    payload = {
        "user_id": TEST_USER_EDITOR,
        "role_name": "editor"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/rbac/users/assign-role",
            headers=headers,
            json=payload
        )

        # Accept both 200 OK and 201 Created as success
        if response.status_code in [200, 201]:
            result = response.json()
            print_result(True, "Role assigned successfully")
            print(f"   User: {result['user_id']}")
            print(f"   Role: {result['role']['role_name']}")
            print(f"   Granted by: {result['granted_by']}")
            return result
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_get_user_roles(auth_key, user_id):
    """Test GET /api/rbac/users/{user_id}/roles (authenticated)."""
    print_section("Test 6: Get User Roles")

    headers = {"Authorization": auth_key}

    try:
        response = requests.get(
            f"{BASE_URL}/api/rbac/users/{user_id}/roles",
            headers=headers
        )

        if response.status_code == 200:
            roles = response.json()  # Returns list directly
            print_result(True, f"Retrieved {len(roles)} roles for user")

            for role in roles:
                print(f"   - {role['role']['role_name']}")
                print(f"     Active: {role['is_active']}")
                print(f"     Granted: {role.get('granted_at', 'N/A')}")

            return roles
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_get_audit_logs(auth_key):
    """Test GET /api/rbac/audit-logs (authenticated, admin only)."""
    print_section("Test 7: Get Audit Logs")

    headers = {"Authorization": auth_key}

    try:
        response = requests.get(
            f"{BASE_URL}/api/rbac/audit-logs?limit=10",
            headers=headers
        )

        if response.status_code == 200:
            logs = response.json()  # Returns list directly
            print_result(True, f"Retrieved {len(logs)} audit log entries")

            event_types = {}
            for log in logs:
                event_type = log['event_type']
                event_types[event_type] = event_types.get(event_type, 0) + 1

            print(f"   Event types:")
            for event_type, count in event_types.items():
                print(f"     - {event_type}: {count}")

            return logs
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_revoke_api_key(auth_key, key_id):
    """Test POST /api/rbac/keys/revoke (authenticated)."""
    print_section("Test 8: Revoke API Key")

    headers = {
        "Authorization": auth_key,
        "Content-Type": "application/json"
    }

    payload = {
        "key_id": key_id,
        "revoke_reason": "End of HTTP testing"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/rbac/keys/revoke",
            headers=headers,
            json=payload
        )

        # Accept both 200 OK and 204 No Content as success
        if response.status_code in [200, 204]:
            if response.status_code == 200:
                result = response.json()
                print_result(True, f"API key revoked: {result.get('message', 'Success')}")
            else:
                print_result(True, "API key revoked successfully (204 No Content)")
            return True
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def test_revoke_role(auth_key, user_id):
    """Test POST /api/rbac/users/revoke-role (authenticated, admin only)."""
    print_section("Test 9: Revoke User Role")

    headers = {
        "Authorization": auth_key,
        "Content-Type": "application/json"
    }

    payload = {
        "user_id": user_id,
        "role_name": "editor"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/rbac/users/revoke-role",
            headers=headers,
            json=payload
        )

        # Accept both 200 OK and 204 No Content as success
        if response.status_code in [200, 204]:
            if response.status_code == 200:
                result = response.json()
                print_result(True, f"Role revoked: {result.get('message', 'Success')}")
            else:
                print_result(True, "Role revoked successfully (204 No Content)")
            return True
        else:
            print_result(False, f"Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


async def cleanup_test_data():
    """Clean up test data after tests."""
    print_section("Cleanup: Removing Test Data")

    supabase = get_supabase_client()

    # Delete test API keys
    supabase.table("api_keys").delete().like("user_id", "user_http_test_%").execute()

    # Delete test user roles
    supabase.table("user_roles").delete().like("user_id", "user_http_test_%").execute()

    print_result(True, "Test data cleaned up")


async def main():
    """Run all HTTP tests."""
    print("\n" + "=" * 70)
    print("  Empire v7.3 - Complete RBAC HTTP Endpoint Testing")
    print("=" * 70)

    # Setup: Create test API key
    try:
        auth_key, key_id = await setup_test_api_key()
    except Exception as e:
        print_result(False, f"Setup failed: {e}")
        return

    results = {
        "passed": 0,
        "failed": 0,
        "total": 9
    }

    # Test 1: List roles (public)
    if test_list_roles():
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 2: Create API key
    new_key = test_create_api_key(auth_key)
    if new_key:
        results["passed"] += 1
        created_key_id = new_key["key_id"]
    else:
        results["failed"] += 1
        created_key_id = None

    # Test 3: List API keys
    if test_list_api_keys(auth_key):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 4: Rotate API key (use the originally created one)
    rotated_key = test_rotate_api_key(auth_key, key_id)
    if rotated_key:
        results["passed"] += 1
        # Update auth_key to use the new rotated key
        auth_key = rotated_key["api_key"]
        key_id = rotated_key["key_id"]
    else:
        results["failed"] += 1

    # Test 5: Assign role
    if test_assign_role(auth_key):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 6: Get user roles
    if test_get_user_roles(auth_key, TEST_USER_EDITOR):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 7: Get audit logs
    if test_get_audit_logs(auth_key):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Test 8: Revoke the key we created in Test 2 (if it exists)
    if created_key_id:
        if test_revoke_api_key(auth_key, created_key_id):
            results["passed"] += 1
        else:
            results["failed"] += 1
    else:
        results["failed"] += 1

    # Test 9: Revoke role
    if test_revoke_role(auth_key, TEST_USER_EDITOR):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Cleanup
    await cleanup_test_data()

    # Summary
    print_section("Test Summary")
    print(f"✅ Passed: {results['passed']}/{results['total']}")
    print(f"❌ Failed: {results['failed']}/{results['total']}")

    if results["failed"] == 0:
        print("\n🎉 All RBAC HTTP endpoint tests passed!")
        print("\n📝 Next Steps:")
        print("   1. Test in Swagger UI: http://localhost:8000/docs")
        print("   2. Deploy to Render for production testing")
        print("   3. Integrate with Clerk for JWT authentication")
    else:
        print("\n⚠️  Some tests failed. Review the output above for details.")


if __name__ == "__main__":
    asyncio.run(main())
