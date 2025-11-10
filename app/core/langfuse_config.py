"""
Langfuse Configuration and Initialization

Provides centralized Langfuse setup for LLM observability across Empire.
Automatically traces all LLM calls, tracks costs, and monitors performance.

Usage:
    from app.core.langfuse_config import observe, langfuse_context

    @observe()
    async def my_llm_function(query: str):
        # Your LLM call here
        pass
"""

import os
from functools import wraps
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

# Langfuse imports
try:
    from langfuse import Langfuse
    from langfuse.decorators import observe, langfuse_context
    LANGFUSE_AVAILABLE = True
except ImportError:
    logger.warning("Langfuse not installed. Install with: pip install langfuse")
    LANGFUSE_AVAILABLE = False

    # Provide no-op decorators if Langfuse is not available
    def observe(*args, **kwargs):
        """No-op decorator when Langfuse is not available"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*func_args, **func_kwargs):
                return await func(*func_args, **func_kwargs)
            return wrapper
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator

    langfuse_context = None


# Initialize Langfuse client
_langfuse_client: Optional[Langfuse] = None


def get_langfuse_client() -> Optional[Langfuse]:
    """
    Get or initialize the Langfuse client.

    Returns:
        Langfuse client instance or None if disabled/unavailable
    """
    global _langfuse_client

    # Check if Langfuse is enabled
    if not os.getenv("LANGFUSE_ENABLED", "false").lower() == "true":
        return None

    if not LANGFUSE_AVAILABLE:
        return None

    # Initialize client if not already done
    if _langfuse_client is None:
        try:
            host = os.getenv("LANGFUSE_HOST")
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")

            if not all([host, public_key, secret_key]):
                logger.warning(
                    "Langfuse credentials not configured. "
                    "Set LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, and LANGFUSE_SECRET_KEY"
                )
                return None

            _langfuse_client = Langfuse(
                host=host,
                public_key=public_key,
                secret_key=secret_key,
                debug=os.getenv("LANGFUSE_LOG_LEVEL", "INFO") == "DEBUG"
            )

            logger.info(
                "Langfuse initialized successfully",
                host=host,
                enabled=True
            )

        except Exception as e:
            logger.error(
                "Failed to initialize Langfuse",
                error=str(e),
                exc_info=True
            )
            return None

    return _langfuse_client


def shutdown_langfuse():
    """
    Flush any pending traces and shutdown Langfuse.
    Call this on application shutdown.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            logger.info("Langfuse flushed and shutdown")
        except Exception as e:
            logger.error(
                "Error shutting down Langfuse",
                error=str(e),
                exc_info=True
            )
        finally:
            _langfuse_client = None


# Export the decorator and context for easy imports
__all__ = [
    "observe",
    "langfuse_context",
    "get_langfuse_client",
    "shutdown_langfuse",
    "LANGFUSE_AVAILABLE"
]
