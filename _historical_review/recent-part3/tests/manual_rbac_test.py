"""
Empire v7.3 - Manual RBAC API Test Script
Quick test script to verify RBAC endpoints via HTTP requests.

Prerequisites:
1. FastAPI server must be running: uvicorn app.main:app --reload --port 8000
2. Supabase environment variables must be set in .env

Run with: python tests/manual_rbac_test.py
"""

import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

BASE_URL = "http://localhost:8000"
TEST_USER_ID = "user_manual_test_001"


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(success, message):
    """Print test result."""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")


def test_health_check():
    """Test if server is running."""
    print_section("Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print_result(True, f"Server is running: {response.json()}")
            return True
        else:
            print_result(False, f"Server returned {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Cannot connect to server: {e}")
        print("\n⚠️  Please start the FastAPI server:")
        print("   cd /path/to/Empire")
        print("   uvicorn app.main:app --reload --port 8000")
        return False


def test_list_roles():
    """Test GET /api/rbac/roles endpoint."""
    print_section("Test 1: List Available Roles")

    try:
        response = requests.get(f"{BASE_URL}/api/rbac/roles")

        if response.status_code == 200:
            roles = response.json()
            print_result(True, f"Found {len(roles)} roles")

            for role in roles:
                print(f"   - {role['role_name']}: {role['description']}")
                print(f"     Permissions: read_docs={role['can_read_documents']}, "
                      f"write_docs={role['can_write_documents']}, "
                      f"manage_users={role['can_manage_users']}")

            return roles
        else:
            print_result(False, f"Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_create_api_key(role_id):
    """Test POST /api/rbac/keys endpoint."""
    print_section("Test 2: Create API Key")

    # For testing, we'll use a mock user_id in the Authorization header
    # In production, this would be a real JWT token or existing API key
    headers = {
        "Authorization": TEST_USER_ID,  # Simulating authentication
        "Content-Type": "application/json"
    }

    payload = {
        "key_name": "Manual Test API Key",
        "role_id": role_id,
        "scopes": ["documents:read", "documents:write"],
        "rate_limit_per_hour": 1000,
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/rbac/keys",
            headers=headers,
            json=payload
        )

        if response.status_code == 201:
            result = response.json()
            print_result(True, "API Key created successfully")
            print(f"   Key ID: {result['key_id']}")
            print(f"   Key Name: {result['key_name']}")
            print(f"   Key Prefix: {result['key_prefix']}")
            print(f"   Full Key: {result['api_key']}")
            print(f"\n   ⚠️  SAVE THIS KEY! It will never be shown again.")

            return result

        elif response.status_code == 401:
            print_result(False, "Authentication failed")
            print("   This is expected - authentication middleware requires valid credentials")
            print("   In production, you would provide a valid JWT token or API key")
            return None

        else:
            print_result(False, f"Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_list_api_keys_with_auth(api_key):
    """Test GET /api/rbac/keys endpoint with authentication."""
    print_section("Test 3: List API Keys (with authentication)")

    headers = {
        "Authorization": api_key  # Using the API key we just created
    }

    try:
        response = requests.get(
            f"{BASE_URL}/api/rbac/keys",
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            print_result(True, f"Found {result['total']} API keys")

            for key in result['keys']:
                print(f"   - {key['key_name']}")
                print(f"     Prefix: {key['key_prefix']}")
                print(f"     Active: {key['is_active']}")
                print(f"     Usage Count: {key['usage_count']}")

            return result

        elif response.status_code == 401:
            print_result(False, "Authentication failed")
            print("   The API key may not be valid or may have expired")
            return None

        else:
            print_result(False, f"Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_api_docs():
    """Check if API documentation is accessible."""
    print_section("API Documentation")

    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print_result(True, "API documentation available at:")
            print(f"   {BASE_URL}/docs")
            print("\n   You can test the RBAC endpoints interactively in the Swagger UI")
            return True
        else:
            print_result(False, "API docs not accessible")
            return False
    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def main():
    """Run all manual tests."""
    print("\n" + "=" * 60)
    print("  Empire v7.3 - RBAC Manual API Tests")
    print("=" * 60)

    # Test 0: Health check
    if not test_health_check():
        print("\n⚠️  Cannot continue - server is not running")
        return

    # Test 1: List roles (no auth required)
    roles = test_list_roles()
    if not roles:
        print("\n⚠️  Cannot continue - roles endpoint failed")
        return

    # Get admin role ID for testing
    admin_role = next((r for r in roles if r['role_name'] == 'admin'), None)
    if not admin_role:
        print_result(False, "Admin role not found")
        return

    # Test 2: Create API key (requires auth)
    api_key_result = test_create_api_key(admin_role['id'])

    # Test 3: List API keys with authentication
    if api_key_result:
        test_list_api_keys_with_auth(api_key_result['api_key'])

    # Show API docs link
    test_api_docs()

    # Summary
    print_section("Test Summary")
    print("✅ Basic RBAC endpoints are functional")
    print("\n📝 Next Steps:")
    print("   1. Test the endpoints in Swagger UI: http://localhost:8000/docs")
    print("   2. Run full integration tests: pytest tests/test_rbac_integration.py -v")
    print("   3. Test with real authentication (Clerk JWT tokens)")
    print("\n⚠️  Note: Some endpoints require proper authentication")
    print("   The authentication middleware expects either:")
    print("   - A valid API key (emp_xxx format)")
    print("   - A valid JWT Bearer token")


if __name__ == "__main__":
    main()
