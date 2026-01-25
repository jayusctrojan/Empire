"""
Generate Clerk Test Token from Secret Key
Task 43.3+ - Simplified token generation for load testing

This script uses your CLERK_SECRET_KEY to generate a test JWT token
that can be used for load testing authenticated endpoints.
"""

import os
import sys
import jwt
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def generate_test_token(
    user_id: str = "test_user_load_testing",
    email: str = "test@empire.local",
    expiration_hours: int = 24
) -> str:
    """
    Generate a test JWT token for load testing.

    Args:
        user_id: Test user ID (default: test_user_load_testing)
        email: Test user email (default: test@empire.local)
        expiration_hours: Token expiration in hours (default: 24)

    Returns:
        JWT token string
    """
    secret_key = os.getenv("CLERK_SECRET_KEY")

    if not secret_key:
        print("❌ Error: CLERK_SECRET_KEY not found in .env file")
        print("\nPlease ensure your .env file contains:")
        print("CLERK_SECRET_KEY=sk-...")
        sys.exit(1)

    # Create JWT payload
    now = int(time.time())
    expiration = now + (expiration_hours * 3600)

    payload = {
        # Standard JWT claims
        "iss": "https://clerk.empire.test",  # Issuer
        "sub": user_id,                      # Subject (user ID)
        "iat": now,                          # Issued at
        "exp": expiration,                   # Expiration
        "nbf": now,                          # Not before

        # Clerk-specific claims
        "azp": "test-client",                # Authorized party
        "email": email,
        "email_verified": True,
        "given_name": "Test",
        "family_name": "User",
        "name": "Test User",

        # Session metadata
        "sid": "test_session_123",
        "org_id": None,
        "org_role": None,
        "org_slug": None,
    }

    # Generate JWT token
    token = jwt.encode(payload, secret_key, algorithm="HS256")

    return token


def main():
    """Generate and display test token"""
    print("\n" + "=" * 70)
    print("Clerk Test Token Generator")
    print("Task 43.3+ - Load Testing Helper")
    print("=" * 70 + "\n")

    # Check if secret key exists
    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        print("❌ CLERK_SECRET_KEY not found in environment")
        print("\nPlease add to your .env file:")
        print("CLERK_SECRET_KEY=sk-...")
        sys.exit(1)

    print(f"✅ Found CLERK_SECRET_KEY: {secret_key[:15]}...")

    # Generate token
    print("\nGenerating test token...")
    try:
        token = generate_test_token(
            user_id="test_user_load_testing",
            email="loadtest@empire.local",
            expiration_hours=24
        )

        print("✅ Token generated successfully!\n")

        # Display token
        print("=" * 70)
        print("Export this to your environment:")
        print("=" * 70)
        print(f"\nexport CLERK_TEST_TOKEN='{token}'\n")

        # Save to file for convenience
        token_file = os.path.join(
            os.path.dirname(__file__),
            ".clerk_test_token"
        )
        with open(token_file, "w") as f:
            f.write(f"export CLERK_TEST_TOKEN='{token}'\n")

        print(f"✅ Token also saved to: {token_file}")
        print("\nTo use it, run:")
        print(f"source {token_file}")
        print()

        # Decode and display payload (for verification)
        decoded = jwt.decode(token, options={"verify_signature": False})
        print("=" * 70)
        print("Token Details:")
        print("=" * 70)
        print(f"User ID: {decoded['sub']}")
        print(f"Email: {decoded['email']}")
        print(f"Issued: {datetime.fromtimestamp(decoded['iat'])}")
        print(f"Expires: {datetime.fromtimestamp(decoded['exp'])}")
        print(f"Valid for: {(decoded['exp'] - decoded['iat']) // 3600} hours")
        print()

        print("=" * 70)
        print("Next Steps:")
        print("=" * 70)
        print("1. Export the token:")
        print(f"   source {token_file}")
        print()
        print("2. Run the load test:")
        print("   python3 query_load_test.py")
        print()
        print("3. Or run it directly:")
        print(f"   CLERK_TEST_TOKEN='{token}' python3 query_load_test.py")
        print()

    except Exception as e:
        print(f"❌ Error generating token: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
