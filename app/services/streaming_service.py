"""
Empire v7.3 - Streaming Output Service

Provides streaming output capabilities for long-running operations.
Supports chunked responses, SSE (Server-Sent Events), and WebSocket streaming.

Features:
- Chunked text streaming for LLM outputs
- Progress updates during task execution
- Multi-client broadcasting
- Backpressure handling
- Redis-backed cross-instance streaming

Author: Claude Code
Date: 2025-01-24
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum

import structlog
from prometheus_client import Counter, Histogram, Gauge

logger = structlog.get_logger(__name__)


# ==============================================================================
# Prometheus Metrics
# ==============================================================================

STREAM_CHUNKS = Counter(
    'empire_stream_chunks_total',
    'Total chunks streamed',
    ['stream_type']
)

STREAM_BYTES = Counter(
    'empire_stream_bytes_total',
    'Total bytes streamed',
    ['stream_type']
)

STREAM_DURATION = Histogram(
    'empire_stream_duration_seconds',
    'Stream duration',
    ['stream_type'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

ACTIVE_STREAMS = Gauge(
    'empire_active_streams',
    'Number of active streams',
    ['stream_type']
)


# ==============================================================================
# Data Models
# ==============================================================================

class StreamType(str, Enum):
    """Type of stream"""
    TEXT = "text"  # Plain text chunks
    JSON = "json"  # JSON objects
    SSE = "sse"  # Server-Sent Events
    BINARY = "binary"  # Binary data


class StreamStatus(str, Enum):
    """Stream status"""
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class StreamChunk:
    """A chunk in the stream"""
    data: Any
    sequence: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None

    def to_sse(self) -> str:
        """Convert to SSE format.

        Handles multiline payloads by emitting one 'data:' line per line of content,
        as per the SSE specification.
        """
        if isinstance(self.data, (bytes, bytearray)):
            import base64
            data_str = base64.b64encode(self.data).decode("ascii")
        elif isinstance(self.data, dict):
            data_str = json.dumps(self.data)
        else:
            data_str = str(self.data)

        # Build the SSE message
        lines = [f"id: {self.sequence}"]

        # Insert event type before data lines if this is the final chunk
        if self.is_final:
            lines.append("event: complete")

        # Handle multiline data - each line needs its own "data:" prefix
        for data_line in data_str.split("\n"):
            lines.append(f"data: {data_line}")

        # Trailing blank line to signal end of message
        lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = self.data
        encoding = None
        if isinstance(self.data, (bytes, bytearray)):
            import base64
            data = base64.b64encode(self.data).decode("ascii")
            encoding = "base64"
        return {
            "data": data,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "is_final": self.is_final,
            "metadata": self.metadata,
            "data_encoding": encoding
        }


@dataclass
class StreamInfo:
    """Information about an active stream"""
    stream_id: str
    stream_type: StreamType
    status: StreamStatus = StreamStatus.STARTING
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Progress tracking
    chunks_sent: int = 0
    bytes_sent: int = 0
    total_chunks: Optional[int] = None  # If known in advance

    # Error handling
    error: Optional[str] = None
    retry_count: int = 0

    # Metadata
    source: str = ""  # e.g., "llm", "report_generation"
    resource_id: Optional[str] = None  # e.g., job_id, task_id

    # Track if final chunk was sent to prevent duplicates
    final_sent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "stream_id": self.stream_id,
            "stream_type": self.stream_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "chunks_sent": self.chunks_sent,
            "bytes_sent": self.bytes_sent,
            "total_chunks": self.total_chunks,
            "error": self.error,
            "source": self.source,
            "resource_id": self.resource_id
        }


# ==============================================================================
# Stream Buffer
# ==============================================================================

class StreamBuffer:
    """
    Buffer for managing stream chunks with backpressure.

    Provides:
    - Buffered chunk storage
    - Consumer notification
    - Backpressure handling
    - Automatic cleanup
    """

    def __init__(self, max_size: int = 1000, chunk_timeout: float = 30.0, max_replay_chunks: int = 100):
        self.max_size = max_size
        self.chunk_timeout = chunk_timeout
        self.max_replay_chunks = max_replay_chunks
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._chunks: List[StreamChunk] = []
        self._lock = asyncio.Lock()
        self._closed = False
        self._error: Optional[Exception] = None

    async def put(self, chunk: StreamChunk) -> None:
        """Add a chunk to the buffer"""
        if self._closed:
            raise RuntimeError("Buffer is closed")

        try:
            await asyncio.wait_for(
                self._queue.put(chunk),
                timeout=self.chunk_timeout
            )
            async with self._lock:
                self._chunks.append(chunk)
                if self.max_replay_chunks > 0 and len(self._chunks) > self.max_replay_chunks:
                    self._chunks = self._chunks[-self.max_replay_chunks:]
        except asyncio.TimeoutError:
            raise RuntimeError("Buffer full, backpressure timeout")

    async def get(self) -> StreamChunk:
        """Get the next chunk from the buffer"""
        if self._error:
            raise self._error

        try:
            chunk = await asyncio.wait_for(
                self._queue.get(),
                timeout=self.chunk_timeout
            )
            return chunk
        except asyncio.TimeoutError:
            if self._closed:
                raise StopAsyncIteration()
            raise

    def close(self, error: Optional[Exception] = None) -> None:
        """Close the buffer"""
        self._closed = True
        self._error = error

    def is_closed(self) -> bool:
        """Check if buffer is closed"""
        return self._closed

    @property
    def size(self) -> int:
        """Current buffer size"""
        return self._queue.qsize()

    def get_all_chunks(self) -> List[StreamChunk]:
        """Get all chunks (for replay)"""
        return self._chunks.copy()


# ==============================================================================
# Streaming Service
# ==============================================================================

class StreamingService:
    """
    Central service for managing streaming outputs.

    Provides:
    - Stream creation and management
    - Multi-consumer broadcasting
    - Cross-instance streaming via Redis
    - Progress tracking and metrics
    """

    REDIS_CHANNEL_PREFIX = "empire:stream:"

    def __init__(self):
        self._streams: Dict[str, StreamInfo] = {}
        self._buffers: Dict[str, StreamBuffer] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._redis = None
        self._pubsub_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the streaming service"""
        await self._connect_redis()
        logger.info("Streaming service initialized")

    async def shutdown(self) -> None:
        """Shutdown the streaming service"""
        # Close all active streams
        for stream_id in list(self._streams.keys()):
            await self.close_stream(stream_id)

        if self._pubsub_task:
            self._pubsub_task.cancel()

        if self._redis:
            await self._redis.close()

        logger.info("Streaming service shutdown")

    async def _connect_redis(self) -> None:
        """Connect to Redis for cross-instance streaming"""
        import os
        import redis.asyncio as redis

        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis.from_url(redis_url, decode_responses=True)

            # Start pubsub listener
            self._pubsub_task = asyncio.create_task(self._pubsub_listener())
        except Exception as e:
            logger.warning(f"Redis connection failed, using local-only streaming: {e}")

    async def _pubsub_listener(self) -> None:
        """Listen for cross-instance stream messages"""
        if not self._redis:
            return

        pubsub = self._redis.pubsub()
        await pubsub.psubscribe(f"{self.REDIS_CHANNEL_PREFIX}*")

        try:
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    stream_id = message["channel"].replace(self.REDIS_CHANNEL_PREFIX, "")
                    data = json.loads(message["data"])
                    await self._distribute_chunk(stream_id, data)
        except asyncio.CancelledError:
            raise  # Don't swallow cancellation
        except Exception:
            logger.exception("pubsub_listener_error")
        finally:
            await pubsub.unsubscribe()

    # ==========================================================================
    # Stream Management
    # ==========================================================================

    async def create_stream(
        self,
        stream_id: str,
        stream_type: StreamType = StreamType.TEXT,
        source: str = "",
        resource_id: Optional[str] = None,
        total_chunks: Optional[int] = None
    ) -> StreamInfo:
        """
        Create a new stream.

        Args:
            stream_id: Unique stream identifier
            stream_type: Type of stream data
            source: Source of the stream (e.g., "llm", "report")
            resource_id: Associated resource (job_id, task_id)
            total_chunks: Total chunks if known

        Returns:
            StreamInfo for the new stream
        """
        if stream_id in self._streams:
            raise ValueError(f"Stream {stream_id} already exists")

        stream = StreamInfo(
            stream_id=stream_id,
            stream_type=stream_type,
            status=StreamStatus.STARTING,
            source=source,
            resource_id=resource_id,
            total_chunks=total_chunks
        )

        self._streams[stream_id] = stream
        self._buffers[stream_id] = StreamBuffer()
        self._subscribers[stream_id] = []

        ACTIVE_STREAMS.labels(stream_type=stream_type.value).inc()

        logger.info("Stream created", stream_id=stream_id, stream_type=stream_type.value)

        return stream

    async def close_stream(
        self,
        stream_id: str,
        error: Optional[str] = None
    ) -> None:
        """
        Close a stream.

        Args:
            stream_id: Stream to close
            error: Optional error message
        """
        if stream_id not in self._streams:
            return

        stream = self._streams[stream_id]
        buffer = self._buffers.get(stream_id)

        # Send final chunk only if not already sent
        if buffer and not buffer.is_closed() and not stream.final_sent:
            stream.final_sent = True
            final_chunk = StreamChunk(
                data={"status": "complete", "error": error},
                sequence=stream.chunks_sent,
                is_final=True
            )
            try:
                await buffer.put(final_chunk)
            except Exception:
                pass
            buffer.close()

        # Update status
        if error:
            stream.status = StreamStatus.ERROR
            stream.error = error
        else:
            stream.status = StreamStatus.COMPLETED

        # Notify subscribers (non-blocking to avoid stalling on full queues)
        for queue in self._subscribers.get(stream_id, []):
            try:
                queue.put_nowait(None)  # Signal end of stream
            except asyncio.QueueFull:
                logger.warning(
                    "Subscriber queue full, end-of-stream signal not delivered",
                    stream_id=stream_id
                )

        # Record metrics
        duration = (datetime.utcnow() - stream.created_at).total_seconds()
        STREAM_DURATION.labels(stream_type=stream.stream_type.value).observe(duration)
        ACTIVE_STREAMS.labels(stream_type=stream.stream_type.value).dec()

        # Cleanup
        del self._streams[stream_id]
        if stream_id in self._buffers:
            del self._buffers[stream_id]
        if stream_id in self._subscribers:
            del self._subscribers[stream_id]

        logger.info(
            "Stream closed",
            stream_id=stream_id,
            chunks_sent=stream.chunks_sent,
            duration=duration
        )

    # ==========================================================================
    # Streaming Operations
    # ==========================================================================

    async def send_chunk(
        self,
        stream_id: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        is_final: bool = False
    ) -> None:
        """
        Send a chunk to the stream.

        Args:
            stream_id: Target stream
            data: Chunk data
            metadata: Optional metadata
            is_final: Whether this is the final chunk
        """
        if stream_id not in self._streams:
            raise ValueError(f"Stream {stream_id} not found")

        stream = self._streams[stream_id]
        buffer = self._buffers[stream_id]

        if stream.status == StreamStatus.STARTING:
            stream.status = StreamStatus.ACTIVE

        chunk = StreamChunk(
            data=data,
            sequence=stream.chunks_sent,
            metadata=metadata,
            is_final=is_final
        )

        # Add to buffer
        await buffer.put(chunk)

        # Update metrics
        stream.chunks_sent += 1
        chunk_bytes = 0
        if isinstance(data, str):
            chunk_bytes = len(data.encode())
        elif isinstance(data, bytes):
            chunk_bytes = len(data)
        stream.bytes_sent += chunk_bytes

        STREAM_CHUNKS.labels(
            stream_type=stream.stream_type.value
        ).inc()
        STREAM_BYTES.labels(stream_type=stream.stream_type.value).inc(chunk_bytes)

        # Mark final_sent if this is the final chunk
        if is_final:
            stream.final_sent = True

        # Broadcast via Redis for cross-instance
        await self._publish_chunk(stream_id, chunk)

        # Only distribute locally if Redis not available
        # (Redis pubsub listener handles distribution when Redis is connected)
        if not self._redis:
            await self._distribute_chunk(stream_id, chunk.to_dict())

        if is_final:
            await self.close_stream(stream_id)

    async def _publish_chunk(self, stream_id: str, chunk: StreamChunk) -> None:
        """Publish chunk to Redis for cross-instance streaming"""
        if not self._redis:
            return

        try:
            channel = f"{self.REDIS_CHANNEL_PREFIX}{stream_id}"
            await self._redis.publish(channel, json.dumps(chunk.to_dict()))
        except Exception as e:
            logger.warning(f"Failed to publish chunk to Redis: {e}")

    async def _distribute_chunk(self, stream_id: str, chunk_data: Dict) -> None:
        """Distribute chunk to local subscribers"""
        for queue in self._subscribers.get(stream_id, []):
            try:
                queue.put_nowait(chunk_data)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full, dropping chunk")

    # ==========================================================================
    # Subscription
    # ==========================================================================

    async def subscribe(
        self,
        stream_id: str,
        queue_size: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Subscribe to a stream.

        Args:
            stream_id: Stream to subscribe to
            queue_size: Maximum queue size for backpressure

        Yields:
            Stream chunks as dictionaries
        """
        if stream_id not in self._streams:
            raise ValueError(f"Stream {stream_id} not found")

        queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._subscribers[stream_id].append(queue)

        try:
            # First, send any buffered chunks
            last_seen_sequence = -1
            buffer = self._buffers.get(stream_id)
            if buffer:
                for chunk in buffer.get_all_chunks():
                    last_seen_sequence = chunk.sequence
                    yield chunk.to_dict()

            # Then stream new chunks
            while True:
                chunk_data = await queue.get()
                if chunk_data is None:  # End of stream
                    break
                if chunk_data.get("sequence", 0) <= last_seen_sequence:
                    continue
                last_seen_sequence = chunk_data.get("sequence", 0)
                yield chunk_data

        finally:
            if stream_id in self._subscribers:
                self._subscribers[stream_id].remove(queue)

    async def subscribe_sse(
        self,
        stream_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Subscribe to a stream in SSE format.

        Args:
            stream_id: Stream to subscribe to

        Yields:
            SSE-formatted strings
        """
        async for chunk_data in self.subscribe(stream_id):
            chunk = StreamChunk(
                data=chunk_data.get("data"),
                sequence=chunk_data.get("sequence", 0),
                is_final=chunk_data.get("is_final", False),
                metadata=chunk_data.get("metadata")
            )
            yield chunk.to_sse()

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    async def stream_generator(
        self,
        stream_id: str,
        generator: AsyncGenerator[str, None],
        chunk_size: int = 100
    ) -> None:
        """
        Stream from an async generator (e.g., LLM output).

        Args:
            stream_id: Stream ID (must already exist)
            generator: Async generator producing text
            chunk_size: Characters to accumulate before sending
        """
        buffer = ""

        try:
            async for text in generator:
                buffer += text

                while len(buffer) >= chunk_size:
                    await self.send_chunk(stream_id, buffer[:chunk_size])
                    buffer = buffer[chunk_size:]

            # Send remaining buffer
            if buffer:
                await self.send_chunk(stream_id, buffer, is_final=True)
            else:
                await self.close_stream(stream_id)

        except Exception as e:
            await self.close_stream(stream_id, error=str(e))
            raise

    async def stream_from_iterator(
        self,
        stream_id: str,
        iterator: AsyncGenerator[Any, None]
    ) -> None:
        """
        Stream from any async iterator.

        Args:
            stream_id: Stream ID
            iterator: Async iterator producing chunks
        """
        try:
            async for item in iterator:
                await self.send_chunk(stream_id, item)

            await self.close_stream(stream_id)

        except Exception as e:
            await self.close_stream(stream_id, error=str(e))
            raise

    # ==========================================================================
    # Status Methods
    # ==========================================================================

    def get_stream_info(self, stream_id: str) -> Optional[StreamInfo]:
        """Get information about a stream"""
        return self._streams.get(stream_id)

    def list_active_streams(self) -> List[StreamInfo]:
        """List all active streams"""
        return [
            s for s in self._streams.values()
            if s.status in (StreamStatus.STARTING, StreamStatus.ACTIVE)
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get streaming statistics"""
        status_counts = {s.value: 0 for s in StreamStatus}
        type_counts = {t.value: 0 for t in StreamType}

        for stream in self._streams.values():
            status_counts[stream.status.value] += 1
            type_counts[stream.stream_type.value] += 1

        return {
            "active_streams": len(self._streams),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "streams": [s.to_dict() for s in self._streams.values()]
        }


# ==============================================================================
# Service Factory
# ==============================================================================

_streaming_service: Optional[StreamingService] = None
_streaming_service_lock: asyncio.Lock = asyncio.Lock()


async def get_streaming_service() -> StreamingService:
    """Get or create the streaming service singleton (async-safe)"""
    global _streaming_service
    if _streaming_service is None:
        async with _streaming_service_lock:
            # Double-check after acquiring lock
            if _streaming_service is None:
                _streaming_service = StreamingService()
                await _streaming_service.initialize()
    return _streaming_service
