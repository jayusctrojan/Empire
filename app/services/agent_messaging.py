"""
Empire v7.3 - Agent-to-Agent Messaging Service

Provides inter-agent communication capabilities via Redis Pub/Sub.
Enables agents to exchange messages, share context, and coordinate work.

Features:
- Point-to-point messaging between agents
- Broadcast messaging to all agents in a workflow
- Message queuing with persistence
- Request-response patterns
- Message history and replay

Author: Claude Code
Date: 2025-01-24
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)


# ==============================================================================
# Prometheus Metrics
# ==============================================================================

MESSAGES_SENT = Counter(
    'empire_agent_messages_sent_total',
    'Total messages sent between agents',
    ['message_type']
)

MESSAGES_RECEIVED = Counter(
    'empire_agent_messages_received_total',
    'Total messages received by agents',
    ['message_type']
)

ACTIVE_SUBSCRIPTIONS = Gauge(
    'empire_agent_subscriptions',
    'Number of active agent subscriptions'
)


# ==============================================================================
# Data Models
# ==============================================================================

class MessageType(str, Enum):
    """Types of inter-agent messages"""
    # Standard messaging
    DIRECT = "direct"  # Point-to-point
    BROADCAST = "broadcast"  # To all agents in workflow
    MULTICAST = "multicast"  # To selected agents

    # Control messages
    REQUEST = "request"  # Request expecting response
    RESPONSE = "response"  # Response to request
    ACK = "ack"  # Acknowledgment

    # Coordination
    HANDOFF = "handoff"  # Agent handing off work
    CONTEXT = "context"  # Sharing context/state
    SIGNAL = "signal"  # Coordination signal

    # System
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class MessagePriority(str, Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DeliveryStatus(str, Enum):
    """Message delivery status"""
    PENDING = "pending"
    DELIVERED = "delivered"
    READ = "read"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """Represents a message between agents"""
    message_id: str
    from_agent: str
    to_agent: str  # Can be specific agent ID or "*" for broadcast
    message_type: MessageType
    content: Dict[str, Any]

    # Optional fields
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None  # For request-response patterns
    reply_to: Optional[str] = None  # Channel to reply to
    priority: MessagePriority = MessagePriority.NORMAL

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 300  # Time to live
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "content": self.content,
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "delivery_status": self.delivery_status.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary"""
        return cls(
            message_id=data["message_id"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            message_type=MessageType(data["message_type"]),
            content=data["content"],
            workflow_id=data.get("workflow_id"),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
            priority=MessagePriority(data.get("priority", "normal")),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            ttl_seconds=data.get("ttl_seconds", 300),
            delivery_status=DeliveryStatus(data.get("delivery_status", "pending"))
        )

    def is_expired(self) -> bool:
        """Check if message has expired"""
        expiry = self.timestamp + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expiry


@dataclass
class AgentSubscription:
    """Represents an agent's subscription to messages"""
    agent_id: str
    callback: Callable[[AgentMessage], Awaitable[None]]
    workflow_id: Optional[str] = None
    message_types: Optional[List[MessageType]] = None


# ==============================================================================
# Agent Message Bus
# ==============================================================================

class AgentMessageBus:
    """
    Message bus for inter-agent communication.

    Provides:
    - Point-to-point messaging
    - Broadcast messaging
    - Request-response patterns
    - Message persistence
    - Cross-instance messaging via Redis
    """

    REDIS_PREFIX = "empire:agent:msg:"
    REDIS_QUEUE_PREFIX = "empire:agent:queue:"

    def __init__(self):
        self._redis = None
        self._pubsub = None
        self._subscriptions: Dict[str, List[AgentSubscription]] = {}
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._message_history: List[AgentMessage] = []
        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

    async def initialize(self) -> None:
        """Initialize the message bus"""
        await self._connect_redis()
        self._running = True
        self._listener_task = asyncio.create_task(self._message_listener())
        logger.info("Agent message bus initialized")

    async def shutdown(self) -> None:
        """Shutdown the message bus"""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

        logger.info("Agent message bus shutdown")

    async def _connect_redis(self) -> None:
        """Connect to Redis"""
        import os
        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()

    async def _message_listener(self) -> None:
        """Listen for messages from Redis"""
        if not self._pubsub:
            return

        await self._pubsub.psubscribe(f"{self.REDIS_PREFIX}*")

        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break

                if message["type"] == "pmessage":
                    try:
                        data = json.loads(message["data"])
                        agent_msg = AgentMessage.from_dict(data)
                        await self._dispatch_message(agent_msg)
                    except Exception as e:
                        logger.error(f"Failed to process message: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Message listener error: {e}")

    async def _dispatch_message(self, message: AgentMessage) -> None:
        """Dispatch message to appropriate subscribers"""
        if message.is_expired():
            logger.debug("Dropping expired message", message_id=message.message_id)
            return

        # Handle response messages
        if message.message_type == MessageType.RESPONSE and message.correlation_id:
            if message.correlation_id in self._pending_requests:
                future = self._pending_requests.pop(message.correlation_id)
                future.set_result(message)
                return

        # Dispatch to subscribers
        target_agents = []

        if message.to_agent == "*":
            # Broadcast to all
            target_agents = list(self._subscriptions.keys())
        else:
            # Specific agent
            if message.to_agent in self._subscriptions:
                target_agents = [message.to_agent]

        for agent_id in target_agents:
            for subscription in self._subscriptions.get(agent_id, []):
                # Check workflow filter
                if subscription.workflow_id and message.workflow_id != subscription.workflow_id:
                    continue

                # Check message type filter
                if subscription.message_types and message.message_type not in subscription.message_types:
                    continue

                try:
                    await subscription.callback(message)
                    MESSAGES_RECEIVED.labels(
                        message_type=message.message_type.value
                    ).inc()
                except Exception as e:
                    logger.error(f"Error in message callback: {e}")

    # ==========================================================================
    # Subscription Management
    # ==========================================================================

    async def subscribe(
        self,
        agent_id: str,
        callback: Callable[[AgentMessage], Awaitable[None]],
        workflow_id: Optional[str] = None,
        message_types: Optional[List[MessageType]] = None
    ) -> str:
        """
        Subscribe an agent to receive messages.

        Args:
            agent_id: Agent identifier
            callback: Async function to call when message received
            workflow_id: Optional filter by workflow
            message_types: Optional filter by message types

        Returns:
            Subscription ID
        """
        subscription = AgentSubscription(
            agent_id=agent_id,
            callback=callback,
            workflow_id=workflow_id,
            message_types=message_types
        )

        if agent_id not in self._subscriptions:
            self._subscriptions[agent_id] = []

        self._subscriptions[agent_id].append(subscription)

        ACTIVE_SUBSCRIPTIONS.set(
            sum(len(subs) for subs in self._subscriptions.values())
        )

        logger.debug("Agent subscribed", agent_id=agent_id)

        return f"{agent_id}:{id(subscription)}"

    def unsubscribe(self, agent_id: str, subscription_id: Optional[str] = None) -> None:
        """
        Unsubscribe an agent from messages.

        Args:
            agent_id: Agent identifier
            subscription_id: Specific subscription to remove (None for all)
        """
        if agent_id not in self._subscriptions:
            return

        if subscription_id:
            # Remove specific subscription
            self._subscriptions[agent_id] = [
                s for s in self._subscriptions[agent_id]
                if f"{agent_id}:{id(s)}" != subscription_id
            ]
        else:
            # Remove all subscriptions
            del self._subscriptions[agent_id]

        ACTIVE_SUBSCRIPTIONS.set(
            sum(len(subs) for subs in self._subscriptions.values())
        )

        logger.debug("Agent unsubscribed", agent_id=agent_id)

    # ==========================================================================
    # Messaging Operations
    # ==========================================================================

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: Dict[str, Any],
        message_type: MessageType = MessageType.DIRECT,
        workflow_id: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        ttl_seconds: int = 300
    ) -> AgentMessage:
        """
        Send a message from one agent to another.

        Args:
            from_agent: Sending agent ID
            to_agent: Receiving agent ID (or "*" for broadcast)
            content: Message content
            message_type: Type of message
            workflow_id: Optional workflow context
            priority: Message priority
            ttl_seconds: Time to live

        Returns:
            The sent message
        """
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            workflow_id=workflow_id,
            priority=priority,
            ttl_seconds=ttl_seconds
        )

        await self._publish_message(message)

        MESSAGES_SENT.labels(
            message_type=message_type.value
        ).inc()

        logger.debug(
            "Message sent",
            message_id=message.message_id,
            from_agent=from_agent,
            to_agent=to_agent
        )

        return message

    async def broadcast_to_workflow(
        self,
        from_agent: str,
        workflow_id: str,
        content: Dict[str, Any],
        message_type: MessageType = MessageType.BROADCAST,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> AgentMessage:
        """
        Broadcast a message to all agents in a workflow.

        Args:
            from_agent: Sending agent ID
            workflow_id: Workflow to broadcast to
            content: Message content
            message_type: Type of message
            priority: Message priority

        Returns:
            The sent message
        """
        return await self.send_message(
            from_agent=from_agent,
            to_agent="*",
            content=content,
            message_type=message_type,
            workflow_id=workflow_id,
            priority=priority
        )

    async def send_request(
        self,
        from_agent: str,
        to_agent: str,
        content: Dict[str, Any],
        workflow_id: Optional[str] = None,
        timeout: float = 30.0
    ) -> Optional[AgentMessage]:
        """
        Send a request and wait for a response.

        Args:
            from_agent: Sending agent ID
            to_agent: Receiving agent ID
            content: Request content
            workflow_id: Optional workflow context
            timeout: Response timeout in seconds

        Returns:
            Response message or None if timeout
        """
        correlation_id = str(uuid.uuid4())

        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.REQUEST,
            content=content,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            reply_to=from_agent
        )

        # Create future for response
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[correlation_id] = future

        try:
            await self._publish_message(message)

            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.warning(
                "Request timeout",
                from_agent=from_agent,
                to_agent=to_agent,
                correlation_id=correlation_id
            )
            return None

        finally:
            self._pending_requests.pop(correlation_id, None)

    async def send_response(
        self,
        original_message: AgentMessage,
        from_agent: str,
        content: Dict[str, Any]
    ) -> AgentMessage:
        """
        Send a response to a request message.

        Args:
            original_message: The request message
            from_agent: Responding agent ID
            content: Response content

        Returns:
            The response message
        """
        response = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=original_message.reply_to or original_message.from_agent,
            message_type=MessageType.RESPONSE,
            content=content,
            workflow_id=original_message.workflow_id,
            correlation_id=original_message.correlation_id
        )

        await self._publish_message(response)

        return response

    async def send_handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
        workflow_id: Optional[str] = None
    ) -> AgentMessage:
        """
        Send a handoff message when transferring work to another agent.

        Args:
            from_agent: Agent handing off
            to_agent: Agent receiving handoff
            context: Context to transfer
            artifacts: Artifacts to transfer
            workflow_id: Workflow context

        Returns:
            The handoff message
        """
        content = {
            "context": context,
            "artifacts": artifacts,
            "handoff_reason": "task_complete"
        }

        return await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            message_type=MessageType.HANDOFF,
            workflow_id=workflow_id,
            priority=MessagePriority.HIGH
        )

    async def send_context_update(
        self,
        from_agent: str,
        workflow_id: str,
        context_updates: Dict[str, Any]
    ) -> AgentMessage:
        """
        Broadcast a context update to all agents in a workflow.

        Args:
            from_agent: Agent sending update
            workflow_id: Workflow to update
            context_updates: Context changes

        Returns:
            The context message
        """
        return await self.broadcast_to_workflow(
            from_agent=from_agent,
            workflow_id=workflow_id,
            content={"updates": context_updates},
            message_type=MessageType.CONTEXT
        )

    # ==========================================================================
    # Internal Methods
    # ==========================================================================

    async def _publish_message(self, message: AgentMessage) -> None:
        """Publish message to Redis"""
        if not self._redis:
            # Fall back to local dispatch
            await self._dispatch_message(message)
            return

        try:
            channel = f"{self.REDIS_PREFIX}{message.to_agent}"
            await self._redis.publish(channel, json.dumps(message.to_dict()))

            # Also store in queue for persistence
            if message.to_agent != "*":
                queue_key = f"{self.REDIS_QUEUE_PREFIX}{message.to_agent}"
                await self._redis.lpush(queue_key, json.dumps(message.to_dict()))
                await self._redis.expire(queue_key, message.ttl_seconds)

        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            # Fall back to local dispatch
            await self._dispatch_message(message)

    # ==========================================================================
    # Message History
    # ==========================================================================

    async def get_message_history(
        self,
        agent_id: str,
        limit: int = 100,
        workflow_id: Optional[str] = None
    ) -> List[AgentMessage]:
        """
        Get message history for an agent.

        Args:
            agent_id: Agent to get history for
            limit: Maximum messages to return
            workflow_id: Optional workflow filter

        Returns:
            List of messages
        """
        if not self._redis:
            return []

        try:
            queue_key = f"{self.REDIS_QUEUE_PREFIX}{agent_id}"
            raw_messages = await self._redis.lrange(queue_key, 0, limit - 1)

            messages = []
            for raw in raw_messages:
                message = AgentMessage.from_dict(json.loads(raw))
                if workflow_id and message.workflow_id != workflow_id:
                    continue
                if not message.is_expired():
                    messages.append(message)

            return messages

        except Exception as e:
            logger.error(f"Failed to get message history: {e}")
            return []

    async def clear_message_queue(self, agent_id: str) -> int:
        """Clear the message queue for an agent"""
        if not self._redis:
            return 0

        try:
            queue_key = f"{self.REDIS_QUEUE_PREFIX}{agent_id}"
            length = await self._redis.llen(queue_key)
            await self._redis.delete(queue_key)
            return length
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return 0


# ==============================================================================
# Service Factory
# ==============================================================================

_message_bus: Optional[AgentMessageBus] = None


async def get_agent_message_bus() -> AgentMessageBus:
    """Get or create the agent message bus singleton"""
    global _message_bus
    if _message_bus is None:
        _message_bus = AgentMessageBus()
        await _message_bus.initialize()
    return _message_bus
