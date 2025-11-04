"""
Empire v7.3 - Database Connection Management
Handles connections to Supabase PostgreSQL, Neo4j, and Redis
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Supabase
from supabase import create_client, Client as SupabaseClient

# Neo4j
from neo4j import GraphDatabase, Driver as Neo4jDriver

# Redis
import redis
from redis import Redis

load_dotenv()


class DatabaseManager:
    """Manages all database connections"""

    def __init__(self):
        self._supabase: Optional[SupabaseClient] = None
        self._neo4j: Optional[Neo4jDriver] = None
        self._redis: Optional[Redis] = None

    # Supabase Connection
    def get_supabase(self) -> SupabaseClient:
        """Get or create Supabase client"""
        if self._supabase is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY")

            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

            self._supabase = create_client(url, key)
            print(f"✅ Connected to Supabase: {url}")

        return self._supabase

    # Neo4j Connection
    def get_neo4j(self) -> Neo4jDriver:
        """Get or create Neo4j driver"""
        if self._neo4j is None:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            username = os.getenv("NEO4J_USERNAME", "neo4j")
            password = os.getenv("NEO4J_PASSWORD")

            if not password:
                raise ValueError("NEO4J_PASSWORD must be set")

            self._neo4j = GraphDatabase.driver(uri, auth=(username, password))
            print(f"✅ Connected to Neo4j: {uri}")

            # Verify connection
            with self._neo4j.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()

        return self._neo4j

    # Redis Connection
    def get_redis(self) -> Redis:
        """Get or create Redis client"""
        if self._redis is None:
            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis.from_url(url, decode_responses=True)
            print(f"✅ Connected to Redis: {url}")

            # Verify connection
            self._redis.ping()

        return self._redis

    # Health Checks
    def check_supabase_health(self) -> bool:
        """Check if Supabase is healthy"""
        try:
            client = self.get_supabase()
            # Try a simple query
            result = client.table("documents").select("id").limit(1).execute()
            return True
        except Exception as e:
            print(f"❌ Supabase health check failed: {e}")
            return False

    def check_neo4j_health(self) -> bool:
        """Check if Neo4j is healthy"""
        try:
            driver = self.get_neo4j()
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            return True
        except Exception as e:
            print(f"❌ Neo4j health check failed: {e}")
            return False

    def check_redis_health(self) -> bool:
        """Check if Redis is healthy"""
        try:
            client = self.get_redis()
            client.ping()
            return True
        except Exception as e:
            print(f"❌ Redis health check failed: {e}")
            return False

    def check_all_health(self) -> dict:
        """Check health of all database connections"""
        return {
            "supabase": self.check_supabase_health(),
            "neo4j": self.check_neo4j_health(),
            "redis": self.check_redis_health()
        }

    # Cleanup
    def close_all(self):
        """Close all database connections"""
        if self._neo4j:
            self._neo4j.close()
            print("👋 Closed Neo4j connection")

        if self._redis:
            self._redis.close()
            print("👋 Closed Redis connection")

        # Supabase client doesn't need explicit closing
        print("👋 All database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


# Dependency injection for FastAPI
def get_supabase() -> SupabaseClient:
    """FastAPI dependency for Supabase"""
    return db_manager.get_supabase()


def get_neo4j() -> Neo4jDriver:
    """FastAPI dependency for Neo4j"""
    return db_manager.get_neo4j()


def get_redis() -> Redis:
    """FastAPI dependency for Redis"""
    return db_manager.get_redis()
