"""
Empire v7.3 - Redis Pub/Sub Service for Distributed WebSocket Broadcasting - Task 10.3

Enables WebSocket message broadcasting across multiple server instances using Redis Pub/Sub.
When a message is published on one server, all other servers receive it and forward to their
connected WebSocket clients.

Features:
- Distributed WebSocket broadcasting via Redis Pub/Sub
- Multiple channel support (general, document-specific, query-specific)
- Automatic reconnection handling
- Message serialization/deserialization
- Integration with WebSocket ConnectionManager
- Prometheus metrics for pub/sub operations
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional, Callable
from redis import asyncio as aioredis
import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)

# Prometheus metrics for Redis Pub/Sub
PUBSUB_MESSAGES_PUBLISHED = Counter(
    'empire_pubsub_messages_published_total',
    'Total messages published to Redis',
    ['channel_type']
)

PUBSUB_MESSAGES_RECEIVED = Counter(
    'empire_pubsub_messages_received_total',
    'Total messages received from Redis',
    ['channel_type']
)

PUBSUB_ACTIVE_SUBSCRIPTIONS = Gauge(
    'empire_pubsub_active_subscriptions',
    'Number of active Redis subscriptions'
)

PUBSUB_PUBLISH_ERRORS = Counter(
    'empire_pubsub_publish_errors_total',
    'Failed publish operations',
    ['error_type']
)


class RedisPubSubService:
    """
    Redis Pub/Sub service for distributed WebSocket broadcasting

    Channels:
    - empire:websocket:broadcast - General broadcast channel
    - empire:websocket:document:{document_id} - Document-specific channel
    - empire:websocket:query:{query_id} - Query-specific channel
    """

    def __init__(self):
        """Initialize Redis Pub/Sub service"""
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self.subscribed_channels: set = set()
        self.message_handlers: Dict[str, Callable] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(
            "redis_pubsub_service_initialized",
            redis_url=self.redis_url.split("@")[-1] if "@" in self.redis_url else self.redis_url
        )

    async def connect(self):
        """Connect to Redis and initialize pub/sub"""
        try:
            # Create Redis client (supports both redis:// and rediss://)
            self.redis_client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )

            # Test connection
            await self.redis_client.ping()

            # Initialize pub/sub
            self.pubsub = self.redis_client.pubsub()

            logger.info("redis_pubsub_connected")

        except Exception as e:
            logger.error(
                "redis_pubsub_connection_failed",
                error=str(e)
            )
            raise

    async def disconnect(self):
        """Disconnect from Redis and cleanup"""
        try:
            self._running = False

            # Stop listener task
            if self._listener_task and not self._listener_task.done():
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass

            # Unsubscribe from all channels
            if self.pubsub:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()

            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()

            logger.info("redis_pubsub_disconnected")

        except Exception as e:
            logger.error(
                "redis_pubsub_disconnect_error",
                error=str(e)
            )

    async def publish_message(
        self,
        channel: str,
        message: Dict[str, Any],
        channel_type: str = "general"
    ):
        """
        Publish a message to a Redis channel

        Args:
            channel: Redis channel name
            message: Message dictionary to publish
            channel_type: Channel type for metrics (general, document, query)
        """
        try:
            if not self.redis_client:
                logger.warning("redis_client_not_connected_for_publish")
                return

            # Serialize message to JSON
            message_json = json.dumps(message)

            # Publish to Redis channel
            subscribers = await self.redis_client.publish(channel, message_json)

            # Update metrics
            PUBSUB_MESSAGES_PUBLISHED.labels(channel_type=channel_type).inc()

            logger.debug(
                "redis_message_published",
                channel=channel,
                channel_type=channel_type,
                subscribers=subscribers,
                message_type=message.get("type")
            )

        except Exception as e:
            logger.error(
                "redis_publish_failed",
                channel=channel,
                error=str(e)
            )
            PUBSUB_PUBLISH_ERRORS.labels(error_type="publish_error").inc()

    async def subscribe_channel(
        self,
        channel: str,
        handler: Callable[[Dict[str, Any]], None]
    ):
        """
        Subscribe to a Redis channel with a message handler

        Args:
            channel: Redis channel name to subscribe to
            handler: Async function to call when messages are received
        """
        try:
            if not self.pubsub:
                logger.error("pubsub_not_initialized")
                return

            # Subscribe to channel
            await self.pubsub.subscribe(channel)

            # Store handler
            self.message_handlers[channel] = handler
            self.subscribed_channels.add(channel)

            # Update metrics
            PUBSUB_ACTIVE_SUBSCRIPTIONS.set(len(self.subscribed_channels))

            logger.info(
                "redis_channel_subscribed",
                channel=channel,
                total_subscriptions=len(self.subscribed_channels)
            )

        except Exception as e:
            logger.error(
                "redis_subscribe_failed",
                channel=channel,
                error=str(e)
            )

    async def unsubscribe_channel(self, channel: str):
        """
        Unsubscribe from a Redis channel

        Args:
            channel: Redis channel name to unsubscribe from
        """
        try:
            if not self.pubsub:
                return

            await self.pubsub.unsubscribe(channel)

            # Remove handler and channel
            if channel in self.message_handlers:
                del self.message_handlers[channel]
            self.subscribed_channels.discard(channel)

            # Update metrics
            PUBSUB_ACTIVE_SUBSCRIPTIONS.set(len(self.subscribed_channels))

            logger.info(
                "redis_channel_unsubscribed",
                channel=channel,
                total_subscriptions=len(self.subscribed_channels)
            )

        except Exception as e:
            logger.error(
                "redis_unsubscribe_failed",
                channel=channel,
                error=str(e)
            )

    async def start_listener(self):
        """Start listening for Redis Pub/Sub messages"""
        if self._running:
            logger.warning("redis_listener_already_running")
            return

        self._running = True
        self._listener_task = asyncio.create_task(self._listen())

        logger.info("redis_pubsub_listener_started")

    async def _listen(self):
        """Internal method to listen for Redis messages"""
        try:
            if not self.pubsub:
                logger.error("pubsub_not_initialized_for_listener")
                return

            while self._running:
                try:
                    # Get message with timeout
                    message = await self.pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0
                    )

                    if message and message["type"] == "message":
                        channel = message["channel"]
                        data = message["data"]

                        # Deserialize message
                        try:
                            message_dict = json.loads(data)

                            # Get channel type for metrics
                            if channel.startswith("empire:websocket:document:"):
                                channel_type = "document"
                            elif channel.startswith("empire:websocket:query:"):
                                channel_type = "query"
                            else:
                                channel_type = "general"

                            # Update metrics
                            PUBSUB_MESSAGES_RECEIVED.labels(channel_type=channel_type).inc()

                            # Call handler if registered
                            if channel in self.message_handlers:
                                handler = self.message_handlers[channel]
                                await handler(message_dict)

                            logger.debug(
                                "redis_message_received",
                                channel=channel,
                                channel_type=channel_type,
                                message_type=message_dict.get("type")
                            )

                        except json.JSONDecodeError as e:
                            logger.error(
                                "redis_message_json_decode_error",
                                channel=channel,
                                error=str(e)
                            )

                except asyncio.TimeoutError:
                    # Normal timeout, continue listening
                    continue

                except Exception as e:
                    logger.error(
                        "redis_listener_error",
                        error=str(e)
                    )
                    # Brief pause before continuing
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("redis_listener_cancelled")
        except Exception as e:
            logger.error(
                "redis_listener_fatal_error",
                error=str(e)
            )


# Global singleton instance
_redis_pubsub_service = None


async def get_redis_pubsub_service() -> RedisPubSubService:
    """
    Get singleton instance of RedisPubSubService

    Returns:
        RedisPubSubService instance
    """
    global _redis_pubsub_service

    if _redis_pubsub_service is None:
        _redis_pubsub_service = RedisPubSubService()
        await _redis_pubsub_service.connect()

    return _redis_pubsub_service
