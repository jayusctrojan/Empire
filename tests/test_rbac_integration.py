"""
Empire v7.3 - RBAC Integration Tests
Tests for API key lifecycle, role management, and audit logging.

Run with: pytest tests/test_rbac_integration.py -v
"""

import pytest
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Skip module entirely if SUPABASE_URL not set (prevents import-time errors)
if not os.getenv("SUPABASE_URL"):
    pytest.skip(
        "SUPABASE_URL not set - skipping RBAC integration tests",
        allow_module_level=True
    )

# Mark as integration test - requires real database connection
pytestmark = pytest.mark.integration

from app.services.rbac_service import RBACService
from app.core.supabase_client import get_supabase_client

# Test user IDs (simulate Clerk user IDs)
TEST_USER_ADMIN = "user_test_admin_001"
TEST_USER_EDITOR = "user_test_editor_001"
TEST_USER_VIEWER = "user_test_viewer_001"


@pytest.fixture
def rbac_service():
    """Get RBAC service instance."""
    return RBACService()


@pytest.fixture
def supabase_client():
    """Get Supabase client instance."""
    return get_supabase_client()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Clean up test data before and after test session."""
    supabase = get_supabase_client()

    # Cleanup before tests
    print("\n🧹 Cleaning up test data from previous runs...")

    # Delete test API keys
    supabase.table("api_keys").delete().like("user_id", "user_test_%").execute()

    # Delete test user roles
    supabase.table("user_roles").delete().like("user_id", "user_test_%").execute()

    print("✅ Test data cleanup complete")

    yield

    # Cleanup after tests (optional)
    print("\n🧹 Cleaning up test data after tests...")
    supabase.table("api_keys").delete().like("user_id", "user_test_%").execute()
    supabase.table("user_roles").delete().like("user_id", "user_test_%").execute()
    print("✅ Post-test cleanup complete")


@pytest.mark.asyncio
async def test_01_list_roles(rbac_service):
    """Test listing available roles."""
    print("\n=== TEST 1: List Available Roles ===")

    roles = await rbac_service.list_roles()

    assert len(roles) == 4, "Should have 4 roles"
    role_names = [r["role_name"] for r in roles]

    assert "admin" in role_names
    assert "editor" in role_names
    assert "viewer" in role_names
    assert "guest" in role_names

    print(f"✅ Found {len(roles)} roles: {role_names}")

    # Check admin role permissions
    admin_role = next(r for r in roles if r["role_name"] == "admin")
    assert admin_role["can_manage_users"] == True
    assert admin_role["can_manage_api_keys"] == True
    assert admin_role["can_view_audit_logs"] == True
    print("✅ Admin role has correct permissions")


@pytest.mark.asyncio
async def test_02_create_api_key(rbac_service, supabase_client):
    """Test API key creation with bcrypt hashing."""
    print("\n=== TEST 2: Create API Key ===")

    # Get admin role ID
    roles = await rbac_service.list_roles()
    admin_role = next(r for r in roles if r["role_name"] == "admin")

    # Create API key
    result = await rbac_service.create_api_key(
        user_id=TEST_USER_ADMIN,
        key_name="Test Admin Key",
        role_id=admin_role["id"],
        scopes=["documents:read", "documents:write"],
        rate_limit_per_hour=1000,
        expires_at=datetime.utcnow() + timedelta(days=30),
        ip_address="127.0.0.1",
        user_agent="pytest"
    )

    assert result["key_id"] is not None
    assert result["api_key"].startswith("emp_")
    assert len(result["api_key"]) == 68  # emp_ + 64 hex chars
    assert result["key_prefix"] == result["api_key"][:12]
    assert result["key_name"] == "Test Admin Key"
    assert result["role_id"] == admin_role["id"]

    print(f"✅ API Key Created: {result['key_prefix']}...")
    print(f"   Full Key (SAVE THIS): {result['api_key']}")
    print(f"   Key ID: {result['key_id']}")

    # Verify key is hashed in database
    db_key = supabase_client.table("api_keys").select("key_hash").eq(
        "id", result["key_id"]
    ).execute()

    assert db_key.data[0]["key_hash"] != result["api_key"]
    assert db_key.data[0]["key_hash"].startswith("$2b$")  # bcrypt hash
    print("✅ API key is bcrypt hashed in database (not plaintext)")

    # Store key for later tests
    pytest.test_api_key = result["api_key"]
    pytest.test_key_id = result["key_id"]


@pytest.mark.asyncio
async def test_03_validate_api_key(rbac_service):
    """Test API key validation with bcrypt."""
    print("\n=== TEST 3: Validate API Key ===")

    # Validate the key we created
    key_record = await rbac_service.validate_api_key(pytest.test_api_key)

    assert key_record is not None
    assert key_record["user_id"] == TEST_USER_ADMIN
    assert key_record["is_active"] == True
    assert key_record["usage_count"] >= 0  # Usage count should be tracked

    print(f"✅ API key validated successfully")
    print(f"   User ID: {key_record['user_id']}")
    print(f"   Usage Count: {key_record['usage_count']}")

    # Test with invalid key
    invalid_key = "emp_" + "0" * 64
    invalid_record = await rbac_service.validate_api_key(invalid_key)

    assert invalid_record is None
    print("✅ Invalid API key correctly rejected")


@pytest.mark.asyncio
async def test_04_list_api_keys(rbac_service):
    """Test listing user's API keys."""
    print("\n=== TEST 4: List API Keys ===")

    keys = await rbac_service.list_api_keys(user_id=TEST_USER_ADMIN)

    assert len(keys) >= 1
    assert all(k["user_id"] == TEST_USER_ADMIN for k in keys if "user_id" in k)

    # Full key should NOT be in the list
    for key in keys:
        assert "api_key" not in key
        assert "key_prefix" in key
        assert key["key_prefix"].startswith("emp_")

    print(f"✅ Found {len(keys)} API keys for user")
    print(f"   Keys (prefixes only): {[k['key_prefix'] for k in keys]}")


@pytest.mark.asyncio
async def test_05_assign_user_role(rbac_service):
    """Test assigning a role to a user."""
    print("\n=== TEST 5: Assign User Role ===")

    # Get editor role
    roles = await rbac_service.list_roles()
    editor_role = next(r for r in roles if r["role_name"] == "editor")

    # Assign editor role to test user
    result = await rbac_service.assign_user_role(
        user_id=TEST_USER_EDITOR,
        role_name="editor",
        granted_by=TEST_USER_ADMIN,
        expires_at=None,
        ip_address="127.0.0.1",
        user_agent="pytest"
    )

    assert result["user_id"] == TEST_USER_EDITOR
    assert result["role_id"] == editor_role["id"]
    assert result["granted_by"] == TEST_USER_ADMIN
    assert result["is_active"] == True

    print(f"✅ Editor role assigned to user {TEST_USER_EDITOR}")
    print(f"   Role ID: {result['id']}")
    print(f"   Granted by: {result['granted_by']}")


@pytest.mark.asyncio
async def test_06_get_user_roles(rbac_service):
    """Test getting user's roles."""
    print("\n=== TEST 6: Get User Roles ===")

    roles = await rbac_service.get_user_roles(user_id=TEST_USER_EDITOR)

    assert len(roles) >= 1
    assert roles[0]["user_id"] == TEST_USER_EDITOR
    assert roles[0]["role"]["role_name"] == "editor"

    editor_role = roles[0]["role"]
    assert editor_role["can_read_documents"] == True
    assert editor_role["can_write_documents"] == True
    assert editor_role["can_delete_documents"] == False

    print(f"✅ User has {len(roles)} role(s)")
    print(f"   Role: {editor_role['role_name']}")
    print(f"   Permissions: read={editor_role['can_read_documents']}, "
          f"write={editor_role['can_write_documents']}, "
          f"delete={editor_role['can_delete_documents']}")


@pytest.mark.asyncio
async def test_07_rotate_api_key(rbac_service):
    """Test API key rotation."""
    print("\n=== TEST 7: Rotate API Key ===")

    # Rotate the key
    new_key = await rbac_service.rotate_api_key(
        key_id=pytest.test_key_id,
        user_id=TEST_USER_ADMIN,
        new_key_name="Test Admin Key (Rotated)",
        expires_at=datetime.utcnow() + timedelta(days=30),
        ip_address="127.0.0.1",
        user_agent="pytest"
    )

    assert new_key["api_key"] != pytest.test_api_key
    assert new_key["api_key"].startswith("emp_")
    assert new_key["key_name"] == "Test Admin Key (Rotated)"

    print(f"✅ API key rotated successfully")
    print(f"   Old Key ID: {pytest.test_key_id}")
    print(f"   New Key ID: {new_key['key_id']}")
    print(f"   New Key Prefix: {new_key['key_prefix']}")

    # Verify old key is revoked
    old_key_valid = await rbac_service.validate_api_key(pytest.test_api_key)
    assert old_key_valid is None
    print("✅ Old API key is now revoked")

    # Store new key for cleanup
    pytest.test_api_key = new_key["api_key"]
    pytest.test_key_id = new_key["key_id"]


@pytest.mark.asyncio
async def test_08_check_audit_logs(rbac_service):
    """Test audit log recording."""
    print("\n=== TEST 8: Check Audit Logs ===")

    # Get recent audit logs
    logs = await rbac_service.get_audit_logs(
        event_type=None,
        user_id=TEST_USER_ADMIN,
        limit=20,
        offset=0
    )

    assert len(logs) > 0

    # Check for expected events
    event_types = [log["event_type"] for log in logs]

    print(f"✅ Found {len(logs)} audit log entries")
    print(f"   Event types: {set(event_types)}")

    # Verify api_key_created event
    created_events = [log for log in logs if log["event_type"] == "api_key_created"]
    assert len(created_events) >= 1
    print(f"✅ Found {len(created_events)} api_key_created events")

    # Verify api_key_rotated event
    rotated_events = [log for log in logs if log["event_type"] == "api_key_rotated"]
    assert len(rotated_events) >= 1
    print(f"✅ Found {len(rotated_events)} api_key_rotated events")

    # Verify role_assigned event
    role_events = [log for log in logs if log["event_type"] == "role_assigned"]
    assert len(role_events) >= 1
    print(f"✅ Found {len(role_events)} role_assigned events")

    # Check audit log structure
    sample_log = logs[0]
    assert "event_type" in sample_log
    assert "actor_user_id" in sample_log
    assert "action" in sample_log
    assert "result" in sample_log
    assert "created_at" in sample_log
    print("✅ Audit logs have correct structure")


@pytest.mark.asyncio
async def test_09_revoke_api_key(rbac_service):
    """Test API key revocation."""
    print("\n=== TEST 9: Revoke API Key ===")

    # Revoke the key
    await rbac_service.revoke_api_key(
        key_id=pytest.test_key_id,
        user_id=TEST_USER_ADMIN,
        revoke_reason="End of testing",
        ip_address="127.0.0.1",
        user_agent="pytest"
    )

    print(f"✅ API key revoked: {pytest.test_key_id}")

    # Verify key is no longer valid
    revoked_key_valid = await rbac_service.validate_api_key(pytest.test_api_key)
    assert revoked_key_valid is None
    print("✅ Revoked API key cannot be validated")


@pytest.mark.asyncio
async def test_10_revoke_user_role(rbac_service):
    """Test revoking a role from a user."""
    print("\n=== TEST 10: Revoke User Role ===")

    # Revoke editor role
    await rbac_service.revoke_user_role(
        user_id=TEST_USER_EDITOR,
        role_name="editor",
        revoked_by=TEST_USER_ADMIN,
        ip_address="127.0.0.1",
        user_agent="pytest"
    )

    print(f"✅ Editor role revoked from user {TEST_USER_EDITOR}")

    # Verify role is removed
    roles = await rbac_service.get_user_roles(user_id=TEST_USER_EDITOR)
    active_roles = [r for r in roles if r["is_active"]]

    assert len(active_roles) == 0 or all(
        r["role"]["role_name"] != "editor" for r in active_roles
    )
    print("✅ User no longer has editor role")


if __name__ == "__main__":
    print("=" * 60)
    print("Empire v7.3 - RBAC Integration Tests")
    print("=" * 60)

    # Run tests
    pytest.main([__file__, "-v", "-s"])
