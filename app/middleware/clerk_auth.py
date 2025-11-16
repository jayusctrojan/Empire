"""
Clerk authentication middleware for FastAPI.
Verifies JWT tokens from Clerk for protected endpoints.
"""
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from clerk_backend_api import Clerk
import os
import jwt
import structlog

logger = structlog.get_logger(__name__)
security = HTTPBearer()

# Initialize Clerk client with secret key from .env
clerk_client = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify Clerk JWT token and return user info.
    Raises HTTPException if token is invalid.
    """
    try:
        token = credentials.credentials

        # Decode and verify the JWT token using the Clerk secret key
        # Clerk tokens are standard JWTs signed with the secret key
        try:
            payload = jwt.decode(
                token,
                CLERK_SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_signature": True, "verify_exp": True}
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token: {str(e)}"
            )

        # Extract user info from JWT payload
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Token missing user ID"
            )

        logger.info(
            "User authenticated",
            user_id=user_id,
            email=email
        )

        return {
            "user_id": user_id,
            "email": email,
            "first_name": payload.get("given_name"),
            "last_name": payload.get("family_name")
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
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
