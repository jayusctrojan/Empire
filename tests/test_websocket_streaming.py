"""
Test suite for WebSocket real-time streaming (Priority 4)
Tests WebSocket endpoint with Redis pub/sub integration
"""
import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

import asyncio
import websockets
import json
import requests
from uuid import uuid4
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


async def test_websocket_real_time_streaming():
    """Test WebSocket receives real-time agent interactions"""

    # Create test execution
    execution_id = uuid4()
    agent1_id = uuid4()
    agent2_id = uuid4()

    print(f"\n=== Testing WebSocket Real-Time Streaming ===")
    print(f"Execution ID: {execution_id}")
    print(f"Agent 1 ID: {agent1_id}")
    print(f"Agent 2 ID: {agent2_id}")

    # Track received messages
    received_messages = []

    try:
        # Connect to WebSocket
        ws_url = f"{WS_URL}/api/crewai/agent-interactions/ws/{execution_id}"
        print(f"\nConnecting to WebSocket: {ws_url}")

        async with websockets.connect(ws_url) as websocket:
            # Receive connection confirmation
            connection_msg = await websocket.recv()
            print(f"✓ Connected: {connection_msg}")

            # Create a task to listen for WebSocket messages
            async def listen_for_messages():
                try:
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        received_messages.append(data)
                        print(f"✓ Received via WebSocket: {data.get('interaction_type')} - {data.get('message', '')[:50]}")
                except websockets.exceptions.ConnectionClosed:
                    pass

            # Start listening in background
            listen_task = asyncio.create_task(listen_for_messages())

            # Send test interactions via REST API
            print("\n1. Sending direct message via REST API...")
            response = requests.post(
                f"{BASE_URL}/api/crewai/agent-interactions/message/send",
                headers=HEADERS,
                json={
                    "execution_id": str(execution_id),
                    "from_agent_id": str(agent1_id),
                    "to_agent_id": str(agent2_id),
                    "interaction_type": "message",
                    "message": "Hello from agent 1 to agent 2",
                    "requires_response": False
                }
            )
            assert response.status_code == 201, f"Failed to send message: {response.text}"
            print(f"  ✓ Message sent via REST")

            # Wait for WebSocket to receive it
            await asyncio.sleep(0.5)

            print("\n2. Publishing event via REST API...")
            response = requests.post(
                f"{BASE_URL}/api/crewai/agent-interactions/events/publish",
                headers=HEADERS,
                json={
                    "execution_id": str(execution_id),
                    "from_agent_id": str(agent1_id),
                    "to_agent_id": None,
                    "interaction_type": "event",
                    "message": "Task completed",
                    "event_type": "task_completed",
                    "event_data": {"task_id": "task-123", "status": "done"}
                }
            )
            assert response.status_code == 201, f"Failed to publish event: {response.text}"
            print(f"  ✓ Event published via REST")

            # Wait for WebSocket to receive it
            await asyncio.sleep(0.5)

            print("\n3. Synchronizing state via REST API...")
            response = requests.post(
                f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
                headers=HEADERS,
                json={
                    "execution_id": str(execution_id),
                    "from_agent_id": str(agent1_id),
                    "to_agent_id": None,
                    "interaction_type": "state_sync",
                    "message": "Updating shared state",
                    "state_key": "counter",
                    "state_value": {"count": 42},
                    "state_version": 1
                }
            )
            assert response.status_code == 201, f"Failed to sync state: {response.text}"
            print(f"  ✓ State synchronized via REST")

            # Wait for WebSocket to receive it
            await asyncio.sleep(0.5)

            # Cancel listening task
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass

            # Verify we received all messages via WebSocket
            print(f"\n=== Verification ===")
            print(f"Total messages received via WebSocket: {len(received_messages)}")

            # Check we got at least the 3 interactions (may be more if connection message included)
            interaction_messages = [msg for msg in received_messages if msg.get('interaction_type') in ['message', 'event', 'state_sync']]
            assert len(interaction_messages) >= 3, f"Expected at least 3 interactions, got {len(interaction_messages)}"

            # Verify message types
            message_types = [msg['interaction_type'] for msg in interaction_messages]
            assert 'message' in message_types, "Direct message not received"
            assert 'event' in message_types, "Event not received"
            assert 'state_sync' in message_types, "State sync not received"

            print(f"✓ All interaction types received via WebSocket:")
            print(f"  - Direct message: {'message' in message_types}")
            print(f"  - Event: {'event' in message_types}")
            print(f"  - State sync: {'state_sync' in message_types}")

            print("\n=== WebSocket Streaming Test PASSED! ===\n")
            return True

    except websockets.exceptions.WebSocketException as e:
        print(f"\n❌ WebSocket error: {e}")
        print("\nNote: WebSocket requires Redis to be running.")
        print("Start Redis with: docker-compose up -d redis")
        return False

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_websocket_ping_pong():
    """Test WebSocket keep-alive ping/pong"""

    execution_id = uuid4()

    print(f"\n=== Testing WebSocket Ping/Pong ===")

    try:
        ws_url = f"{WS_URL}/api/crewai/agent-interactions/ws/{execution_id}"

        async with websockets.connect(ws_url) as websocket:
            # Receive connection confirmation
            connection_msg = await websocket.recv()
            print(f"✓ Connected")

            # Send ping
            await websocket.send("ping")
            print("✓ Sent ping")

            # Wait for pong
            response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            assert response == "pong", f"Expected 'pong', got '{response}'"
            print("✓ Received pong")

            print("\n=== Ping/Pong Test PASSED! ===\n")
            return True

    except asyncio.TimeoutError:
        print("❌ Timeout waiting for pong response")
        return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("WebSocket Real-Time Streaming Test Suite")
    print("="*60)

    # Check if Redis is required
    print("\nPrerequisites:")
    print("1. FastAPI server running on http://localhost:8000")
    print("2. Redis running (for pub/sub)")
    print("\nStarting tests...\n")

    # Run tests
    loop = asyncio.get_event_loop()

    # Test 1: Real-time streaming
    result1 = loop.run_until_complete(test_websocket_real_time_streaming())

    # Test 2: Ping/pong
    result2 = loop.run_until_complete(test_websocket_ping_pong())

    # Summary
    print("\n" + "="*60)
    print("Test Results:")
    print("="*60)
    print(f"Real-time streaming: {'PASSED ✓' if result1 else 'FAILED ✗'}")
    print(f"Ping/pong keep-alive: {'PASSED ✓' if result2 else 'FAILED ✗'}")

    if result1 and result2:
        print("\n🎉 All WebSocket tests PASSED!")
    else:
        print("\n⚠️  Some tests failed. Check output above for details.")

    print("="*60 + "\n")
