"""
Clerk authentication middleware for FastAPI.
Verifies JWT tokens from Clerk for protected endpoints.
"""
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from clerk_backend_api import Clerk
import os
import structlog

logger = structlog.get_logger(__name__)
security = HTTPBearer()

# Initialize Clerk client with secret key from .env
clerk_client = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify Clerk JWT token and return user info.
    Raises HTTPException if token is invalid.
    """
    try:
        token = credentials.credentials

        # Verify the session token with Clerk
        session = clerk_client.sessions.verify_token(token)

        if not session:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )

        # Get user details
        user = clerk_client.users.get(session.user_id)

        logger.info(
            "User authenticated",
            user_id=user.id,
            email=user.email_addresses[0].email_address if user.email_addresses else None
        )

        return {
            "user_id": user.id,
            "email": user.email_addresses[0].email_address if user.email_addresses else None,
            "first_name": user.first_name,
            "last_name": user.last_name
        }

    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )


async def verify_clerk_token_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Optional authentication - returns None if no token."""
    if not credentials:
        return None
    return await verify_clerk_token(credentials)
