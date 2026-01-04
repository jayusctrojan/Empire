"""
Empire v7.3 - Supabase Client Helper
Provides Supabase client instance for RBAC operations
"""

import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


# Singleton instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get Supabase client instance with service key.

    Uses singleton pattern to reuse the same client instance.
    Service key bypasses RLS (Row Level Security) for admin operations.

    Returns:
        Supabase client with RLS bypass enabled

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_SERVICE_KEY are not set
    """
    global _supabase_client

    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url:
            raise ValueError("SUPABASE_URL environment variable is not set")

        if not key:
            raise ValueError("SUPABASE_SERVICE_KEY environment variable is not set")

        _supabase_client = create_client(url, key)

    return _supabase_client


def reset_supabase_client():
    """
    Reset the singleton Supabase client instance.

    Useful for testing or when credentials change.
    """
    global _supabase_client
    _supabase_client = None
