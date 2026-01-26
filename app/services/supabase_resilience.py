"""
Empire v7.3 - Resilient Supabase Service (Task 159)

Circuit breaker implementation for Supabase database operations
with retry logic, fallback responses, and monitoring.

Features:
- Circuit breaker for all Supabase operations
- Automatic retry with exponential backoff
- Configurable fallback handlers
- Prometheus metrics integration
- Connection error handling

Author: Claude Code
Date: 2025-01-15
"""

import os
import asyncio
from typing import Any, Dict, List, Optional, TypeVar, Callable, Union
from datetime import datetime

import structlog
from supabase import create_client, Client
from postgrest.exceptions import APIError as PostgrestAPIError
from httpx import HTTPError, ConnectError, TimeoutException
from prometheus_client import Counter, Histogram, Gauge

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    get_circuit_breaker_sync,
    get_fallback_registry,
)
from app.exceptions import (
    SupabaseException,
    DatabaseException,
    ServiceUnavailableException,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

SUPABASE_OPERATION_COUNTER = Counter(
    "empire_supabase_operations_total",
    "Total Supabase operations",
    ["operation", "table", "status"]
)

SUPABASE_OPERATION_LATENCY = Histogram(
    "empire_supabase_operation_latency_seconds",
    "Supabase operation latency in seconds",
    ["operation", "table"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

SUPABASE_CONNECTION_ERRORS = Counter(
    "empire_supabase_connection_errors_total",
    "Total Supabase connection errors"
)


# =============================================================================
# SUPABASE CIRCUIT BREAKER CONFIGURATION
# =============================================================================

SUPABASE_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=3,
    recovery_timeout=30.0,
    max_retries=3,
    retry_base_delay=0.5,
    retry_max_delay=10.0,
    retry_multiplier=2.0,
    operation_timeout=15.0,
    retryable_exceptions=(
        HTTPError,
        ConnectError,
        TimeoutException,
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    ),
)


# =============================================================================
# RESILIENT SUPABASE CLIENT
# =============================================================================

class ResilientSupabaseClient:
    """
    Supabase client wrapper with built-in circuit breaker protection.

    Features:
    - Circuit breaker for all database operations
    - Automatic retry with exponential backoff
    - Fallback support for cached results
    - Prometheus metrics integration

    Usage:
        client = ResilientSupabaseClient()
        result = await client.select("documents", columns="*", limit=10)
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize resilient Supabase client.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service key
            config: Optional custom circuit breaker config
        """
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY")

        self._client: Optional[Client] = None
        self._initialized = False

        # Circuit breaker
        self._circuit = get_circuit_breaker_sync(
            "supabase",
            config or SUPABASE_CONFIG
        )

        # Statistics
        self._stats = {
            "operations_total": 0,
            "operations_successful": 0,
            "operations_failed": 0,
            "cache_hits": 0,
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Resilient Supabase client initialized",
            url=self.supabase_url
        )

    def _ensure_client(self) -> Client:
        """Ensure Supabase client is initialized"""
        if self._client is None:
            if not self.supabase_url or not self.supabase_key:
                raise SupabaseException(
                    message="Supabase credentials not configured",
                    operation="initialize"
                )

            self._client = create_client(self.supabase_url, self.supabase_key)
            self._initialized = True
            logger.info("Supabase client created", url=self.supabase_url)

        return self._client

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Access the circuit breaker for status checks"""
        return self._circuit

    @property
    def is_available(self) -> bool:
        """Check if client is available (initialized and circuit not open)"""
        return (
            self.supabase_url is not None and
            self.supabase_key is not None and
            not self._circuit.is_open
        )

    async def _execute(
        self,
        operation: str,
        table: str,
        func: Callable[[], Any],
    ) -> Any:
        """
        Execute a Supabase operation with circuit breaker protection.

        Args:
            operation: Operation name (select, insert, update, delete)
            table: Table name
            func: Sync function that returns the operation result

        Returns:
            Operation result
        """
        self._stats["operations_total"] += 1
        start_time = asyncio.get_event_loop().time()

        try:
            # Wrap sync function in async
            async def async_func():
                return func()

            result = await self._circuit.call(
                async_func,
                operation=f"{operation}:{table}",
                use_fallback=True,
            )

            elapsed = asyncio.get_event_loop().time() - start_time
            self._stats["operations_successful"] += 1

            SUPABASE_OPERATION_COUNTER.labels(
                operation=operation,
                table=table,
                status="success"
            ).inc()

            SUPABASE_OPERATION_LATENCY.labels(
                operation=operation,
                table=table
            ).observe(elapsed)

            return result

        except CircuitOpenError:
            elapsed = asyncio.get_event_loop().time() - start_time
            self._stats["operations_failed"] += 1

            SUPABASE_OPERATION_COUNTER.labels(
                operation=operation,
                table=table,
                status="circuit_open"
            ).inc()

            logger.warning(
                "Supabase operation rejected - circuit open",
                operation=operation,
                table=table
            )
            raise ServiceUnavailableException(
                message="Supabase service temporarily unavailable",
                service_name="supabase"
            )

        except (PostgrestAPIError, HTTPError, ConnectError) as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            self._stats["operations_failed"] += 1

            SUPABASE_OPERATION_COUNTER.labels(
                operation=operation,
                table=table,
                status="error"
            ).inc()

            SUPABASE_CONNECTION_ERRORS.inc()

            logger.error(
                "Supabase operation failed",
                operation=operation,
                table=table,
                error=str(e)
            )

            raise SupabaseException(
                message=f"Supabase {operation} failed: {str(e)}",
                operation=operation,
                table=table
            )

    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Select records from a table.

        Args:
            table: Table name
            columns: Columns to select (default "*")
            filters: Optional filter conditions
            order: Optional order by column
            limit: Optional limit
            offset: Optional offset

        Returns:
            List of records
        """
        def _select():
            client = self._ensure_client()
            query = client.table(table).select(columns)

            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            if order:
                query = query.order(order)

            if limit:
                query = query.limit(limit)

            if offset:
                query = query.range(offset, offset + (limit or 100) - 1)

            return query.execute()

        result = await self._execute("select", table, _select)
        return result.data

    async def insert(
        self,
        table: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        upsert: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Insert records into a table.

        Args:
            table: Table name
            data: Record or list of records to insert
            upsert: Whether to upsert on conflict

        Returns:
            Inserted records
        """
        def _insert():
            client = self._ensure_client()
            if upsert:
                return client.table(table).upsert(data).execute()
            return client.table(table).insert(data).execute()

        result = await self._execute("insert", table, _insert)
        return result.data

    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Update records in a table.

        Args:
            table: Table name
            data: Data to update
            filters: Filter conditions to identify records

        Returns:
            Updated records
        """
        def _update():
            client = self._ensure_client()
            query = client.table(table).update(data)

            for key, value in filters.items():
                query = query.eq(key, value)

            return query.execute()

        result = await self._execute("update", table, _update)
        return result.data

    async def delete(
        self,
        table: str,
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Delete records from a table.

        Args:
            table: Table name
            filters: Filter conditions to identify records

        Returns:
            Deleted records
        """
        def _delete():
            client = self._ensure_client()
            query = client.table(table).delete()

            for key, value in filters.items():
                query = query.eq(key, value)

            return query.execute()

        result = await self._execute("delete", table, _delete)
        return result.data

    async def rpc(
        self,
        function_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Call a Postgres RPC function.

        Args:
            function_name: Name of the function
            params: Function parameters

        Returns:
            Function result
        """
        def _rpc():
            client = self._ensure_client()
            return client.rpc(function_name, params or {}).execute()

        result = await self._execute("rpc", function_name, _rpc)
        return result.data

    async def vector_search(
        self,
        table: str,
        column: str,
        query_embedding: List[float],
        match_count: int = 10,
        filter_column: Optional[str] = None,
        filter_value: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.

        Args:
            table: Table name
            column: Embedding column name
            query_embedding: Query embedding vector
            match_count: Number of results
            filter_column: Optional filter column
            filter_value: Optional filter value

        Returns:
            Similar records with similarity scores
        """
        params = {
            "query_embedding": query_embedding,
            "match_count": match_count,
        }

        if filter_column and filter_value is not None:
            params["filter_column"] = filter_column
            params["filter_value"] = filter_value

        # Assumes a match_documents RPC function exists
        return await self.rpc(f"match_{table}", params)

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            **self._stats,
            "service_name": "ResilientSupabaseClient",
            "circuit_status": self._circuit.get_status(),
            "initialized": self._initialized,
        }


# =============================================================================
# DEFAULT FALLBACKS
# =============================================================================

async def _default_select_fallback(*args, **kwargs) -> List[Dict]:
    """Default fallback for select operations - returns empty list"""
    logger.info("Using select fallback - returning empty list")
    return []


async def _default_insert_fallback(*args, **kwargs) -> List[Dict]:
    """Default fallback for insert operations - returns empty list with warning"""
    logger.warning("Insert fallback triggered - data not persisted")
    return []


# Register default fallbacks
def register_default_fallbacks():
    """Register default Supabase fallback handlers"""
    registry = get_fallback_registry()
    registry.register("supabase", "select", _default_select_fallback)
    registry.register_default("supabase", _default_select_fallback)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_supabase_client: Optional[ResilientSupabaseClient] = None


def get_resilient_supabase_client(
    config: Optional[CircuitBreakerConfig] = None
) -> ResilientSupabaseClient:
    """
    Get singleton resilient Supabase client.

    Args:
        config: Optional custom configuration

    Returns:
        ResilientSupabaseClient instance
    """
    global _supabase_client

    if _supabase_client is None:
        _supabase_client = ResilientSupabaseClient(config=config)
        register_default_fallbacks()

    return _supabase_client


async def close_resilient_supabase_client():
    """Close the singleton Supabase client"""
    global _supabase_client
    _supabase_client = None
