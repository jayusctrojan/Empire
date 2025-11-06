"""
Neo4j Connection Service

Manages Neo4j database connections, driver initialization, and query execution.
Supports connection pooling, transaction management, and error handling.

Features:
- Connection pool management
- TLS/SSL support (bolt+ssc://)
- Session management
- Query execution with parameters
- Singleton pattern for connection reuse
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection"""
    uri: str
    username: str
    password: str
    database: str = "neo4j"
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 50
    connection_acquisition_timeout: int = 60

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        """
        Create configuration from environment variables

        Returns:
            Neo4jConfig instance populated from environment
        """
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            max_connection_lifetime=int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600")),
            max_connection_pool_size=int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "50")),
            connection_acquisition_timeout=int(os.getenv("NEO4J_CONNECTION_TIMEOUT", "60"))
        )


class Neo4jConnection:
    """
    Neo4j database connection manager

    Handles driver initialization, connection pooling, and query execution.
    Supports both synchronous and transaction-based operations.
    """

    def __init__(self, config: Optional[Neo4jConfig] = None):
        """
        Initialize Neo4j connection

        Args:
            config: Optional configuration. If None, reads from environment.
        """
        self.config = config or Neo4jConfig.from_env()
        self._closed = False

        # Create driver with connection pool settings
        self.driver = GraphDatabase.driver(
            self.config.uri,
            auth=(self.config.username, self.config.password),
            max_connection_lifetime=self.config.max_connection_lifetime,
            max_connection_pool_size=self.config.max_connection_pool_size,
            connection_acquisition_timeout=self.config.connection_acquisition_timeout
        )

        logger.info(
            f"Initialized Neo4j driver: {self.config.uri}, "
            f"database={self.config.database}"
        )

    def verify_connectivity(self) -> bool:
        """
        Verify connection to Neo4j database

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.driver.verify_connectivity()
            logger.info("Neo4j connectivity verified successfully")
            return True

        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            return False

        except AuthError as e:
            logger.error(f"Neo4j authentication failed: {e}")
            return False

        except Exception as e:
            logger.error(f"Neo4j connectivity check failed: {e}")
            return False

    def get_session(self):
        """
        Get a Neo4j session for the configured database

        Returns:
            Neo4j session object
        """
        return self.driver.session(database=self.config.database)

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results

        Args:
            query: Cypher query string
            parameters: Optional query parameters

        Returns:
            List of result records as dictionaries
        """
        if self._closed:
            logger.warning("Attempted to execute query on closed connection")
            return []

        try:
            with self.get_session() as session:
                result = session.run(query, parameters or {})
                return result.data()

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            return []

    def close(self):
        """
        Close the Neo4j driver and release resources

        Safe to call multiple times.
        """
        if not self._closed:
            self.driver.close()
            self._closed = True
            logger.info("Neo4j connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed"""
        self.close()


# Singleton instance
_neo4j_connection: Optional[Neo4jConnection] = None


def get_neo4j_connection(config: Optional[Neo4jConfig] = None) -> Neo4jConnection:
    """
    Get or create singleton Neo4j connection instance

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        Neo4jConnection instance
    """
    global _neo4j_connection

    if _neo4j_connection is None:
        _neo4j_connection = Neo4jConnection(config=config)

    return _neo4j_connection
