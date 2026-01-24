"""
Empire v7.3 - Connection Manager
Centralized management of database and service connections
"""

import os
import redis
from neo4j import GraphDatabase
from supabase import create_client, Client
from typing import Optional
import structlog
import httpx

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """
    Manages all external connections for Empire v7.3
    Provides connection pooling, health checks, and graceful shutdown
    """

    def __init__(self):
        # Connection instances
        self.supabase: Optional[Client] = None
        self.redis: Optional[redis.Redis] = None
        self.neo4j_driver: Optional[any] = None

        # HTTP client for service health checks
        self.http_client: Optional[httpx.AsyncClient] = None

        # Connection status tracking
        self.connections_initialized = False

    async def initialize(self):
        """Initialize all connections during FastAPI startup"""
        logger.info("Initializing database connections...")

        try:
            # Initialize Supabase
            await self._init_supabase()

            # Initialize Redis
            await self._init_redis()

            # Initialize Neo4j
            await self._init_neo4j()

            # Initialize HTTP client for health checks
            self.http_client = httpx.AsyncClient(timeout=10.0)

            self.connections_initialized = True
            logger.info("All database connections initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize connections", error=str(e))
            raise

    async def _init_supabase(self):
        """Initialize Supabase client"""
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not configured")
                return

            self.supabase = create_client(supabase_url, supabase_key)

            # Test connection with a simple query
            _result = self.supabase.table("documents").select("id").limit(1).execute()  # noqa: F841

            logger.info("Supabase connection established", url=supabase_url)

        except Exception as e:
            logger.error("Failed to initialize Supabase", error=str(e))
            raise

    async def _init_redis(self):
        """Initialize Redis connection"""
        try:
            redis_url = os.getenv("REDIS_URL")

            if not redis_url:
                logger.warning("Redis URL not configured")
                return

            # Parse Redis URL and create connection
            # Handle SSL parameters properly for Upstash Redis
            import ssl

            # Remove invalid ssl_cert_reqs parameter from URL if present
            clean_redis_url = redis_url.split("?")[0] if "?" in redis_url else redis_url

            # For rediss:// URLs (TLS), let redis-py handle SSL automatically
            if clean_redis_url.startswith("rediss://"):
                self.redis = redis.from_url(
                    clean_redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True
                )
            else:
                self.redis = redis.from_url(
                    clean_redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True
                )

            # Test connection
            self.redis.ping()

            logger.info("Redis connection established", url=clean_redis_url.split("@")[-1] if "@" in clean_redis_url else clean_redis_url)

        except Exception as e:
            logger.error("Failed to initialize Redis", error=str(e))
            raise

    async def _init_neo4j(self):
        """Initialize Neo4j driver"""
        try:
            neo4j_uri = os.getenv("NEO4J_URI")
            neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD")

            if not neo4j_uri or not neo4j_password:
                logger.warning("Neo4j credentials not configured")
                return

            # Create Neo4j driver
            self.neo4j_driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )

            # Test connection
            self.neo4j_driver.verify_connectivity()

            logger.info("Neo4j connection established", uri=neo4j_uri)

        except Exception as e:
            logger.error("Failed to initialize Neo4j", error=str(e))
            raise

    async def check_health(self) -> dict:
        """
        Check health of all connections and external services
        Returns detailed status for each component
        """
        health_status = {
            "supabase": "unknown",
            "redis": "unknown",
            "neo4j": "unknown",
            "llamaindex": "unknown",
            "crewai": "unknown"
        }

        # Check Supabase
        try:
            if self.supabase:
                _result = self.supabase.table("documents").select("id").limit(1).execute()  # noqa: F841
                health_status["supabase"] = "healthy"
            else:
                health_status["supabase"] = "not_configured"
        except Exception as e:
            logger.error("Supabase health check failed", error=str(e))
            health_status["supabase"] = f"unhealthy: {str(e)}"

        # Check Redis
        try:
            if self.redis:
                self.redis.ping()
                health_status["redis"] = "healthy"
            else:
                health_status["redis"] = "not_configured"
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            health_status["redis"] = f"unhealthy: {str(e)}"

        # Check Neo4j
        try:
            if self.neo4j_driver:
                self.neo4j_driver.verify_connectivity()
                health_status["neo4j"] = "healthy"
            else:
                health_status["neo4j"] = "not_configured"
        except Exception as e:
            logger.error("Neo4j health check failed", error=str(e))
            health_status["neo4j"] = f"unhealthy: {str(e)}"

        # Check LlamaIndex service
        try:
            llamaindex_url = os.getenv("LLAMAINDEX_SERVICE_URL")
            if llamaindex_url and self.http_client:
                response = await self.http_client.get(f"{llamaindex_url}/health", timeout=5.0)
                if response.status_code == 200:
                    health_status["llamaindex"] = "healthy"
                else:
                    health_status["llamaindex"] = f"unhealthy: HTTP {response.status_code}"
            else:
                health_status["llamaindex"] = "not_configured"
        except Exception as e:
            logger.error("LlamaIndex health check failed", error=str(e))
            health_status["llamaindex"] = f"unhealthy: {str(e)}"

        # Check CrewAI service
        try:
            crewai_url = os.getenv("CREWAI_SERVICE_URL")
            if crewai_url and self.http_client:
                response = await self.http_client.get(f"{crewai_url}/api/crewai/health", timeout=5.0)
                if response.status_code == 200:
                    health_status["crewai"] = "healthy"
                else:
                    health_status["crewai"] = f"unhealthy: HTTP {response.status_code}"
            else:
                health_status["crewai"] = "not_configured"
        except Exception as e:
            logger.error("CrewAI health check failed", error=str(e))
            health_status["crewai"] = f"unhealthy: {str(e)}"

        return health_status

    async def check_readiness(self) -> bool:
        """
        Check if all critical dependencies are ready
        Returns True only if all required services are healthy
        """
        health = await self.check_health()

        # Define critical services (must be healthy)
        critical_services = ["supabase", "redis"]

        # Check if all critical services are healthy or configured
        for service in critical_services:
            status = health.get(service, "unknown")
            if status not in ["healthy", "not_configured"]:
                logger.warning(f"Critical service not ready: {service} = {status}")
                return False

        return True

    async def shutdown(self):
        """Close all connections gracefully"""
        logger.info("Shutting down database connections...")

        try:
            # Close HTTP client
            if self.http_client:
                await self.http_client.aclose()
                logger.info("HTTP client closed")

            # Close Neo4j driver
            if self.neo4j_driver:
                self.neo4j_driver.close()
                logger.info("Neo4j connection closed")

            # Close Redis connection
            if self.redis:
                self.redis.close()
                logger.info("Redis connection closed")

            # Supabase client doesn't require explicit cleanup

            self.connections_initialized = False
            logger.info("All connections closed successfully")

        except Exception as e:
            logger.error("Error during connection shutdown", error=str(e))
            raise


# Global connection manager instance
connection_manager = ConnectionManager()


# Dependency injection for FastAPI routes
def get_connection_manager() -> ConnectionManager:
    """FastAPI dependency to get connection manager"""
    return connection_manager


def get_supabase() -> Optional[Client]:
    """FastAPI dependency to get Supabase client"""
    return connection_manager.supabase


def get_redis() -> Optional[redis.Redis]:
    """FastAPI dependency to get Redis client"""
    return connection_manager.redis


def get_neo4j_driver():
    """FastAPI dependency to get Neo4j driver"""
    return connection_manager.neo4j_driver
