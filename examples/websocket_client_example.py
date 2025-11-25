"""
WebSocket Client Example - Task 10

Simple client to test WebSocket real-time status updates.

Usage:
    # Monitor general notifications
    python websocket_client_example.py

    # Monitor specific document
    python websocket_client_example.py --document doc_123

    # Monitor specific query
    python websocket_client_example.py --query query_456
"""

import asyncio
import websockets
import json
import argparse
from datetime import datetime
from typing import Optional


class WebSocketClient:
    """Simple WebSocket client for testing Empire WebSocket endpoints"""

    def __init__(self, base_url: str = "ws://localhost:8000"):
        self.base_url = base_url
        self.connection = None

    async def connect_notifications(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Connect to general notifications endpoint"""
        params = []
        if session_id:
            params.append(f"session_id={session_id}")
        if user_id:
            params.append(f"user_id={user_id}")

        query_string = "?" + "&".join(params) if params else ""
        uri = f"{self.base_url}/ws/notifications{query_string}"

        print(f"Connecting to: {uri}")
        async with websockets.connect(uri) as websocket:
            await self._listen(websocket, "General Notifications")

    async def connect_document(
        self,
        document_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Connect to document-specific endpoint"""
        params = []
        if session_id:
            params.append(f"session_id={session_id}")
        if user_id:
            params.append(f"user_id={user_id}")

        query_string = "?" + "&".join(params) if params else ""
        uri = f"{self.base_url}/ws/document/{document_id}{query_string}"

        print(f"Connecting to: {uri}")
        async with websockets.connect(uri) as websocket:
            # Receive subscription confirmation
            message = await websocket.recv()
            data = json.loads(message)
            print(f"\n✅ {data.get('type')}: {data.get('resource_type')} - {data.get('resource_id')}")

            await self._listen(websocket, f"Document {document_id}")

    async def connect_query(
        self,
        query_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Connect to query-specific endpoint"""
        params = []
        if session_id:
            params.append(f"session_id={session_id}")
        if user_id:
            params.append(f"user_id={user_id}")

        query_string = "?" + "&".join(params) if params else ""
        uri = f"{self.base_url}/ws/query/{query_id}{query_string}"

        print(f"Connecting to: {uri}")
        async with websockets.connect(uri) as websocket:
            # Receive subscription confirmation
            message = await websocket.recv()
            data = json.loads(message)
            print(f"\n✅ {data.get('type')}: {data.get('resource_type')} - {data.get('resource_id')}")

            await self._listen(websocket, f"Query {query_id}")

    async def _listen(self, websocket, channel_name: str):
        """Listen for messages and handle them"""
        print(f"\n📡 Listening to {channel_name}...")
        print("=" * 80)

        # Send initial ping
        await websocket.send(json.dumps({"type": "ping"}))

        # Start keepalive task
        keepalive_task = asyncio.create_task(self._send_keepalive(websocket))

        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)

                self._display_message(data)

        except websockets.exceptions.ConnectionClosed:
            print(f"\n❌ Connection closed")
        except KeyboardInterrupt:
            print(f"\n👋 Disconnecting...")
        finally:
            keepalive_task.cancel()

    async def _send_keepalive(self, websocket):
        """Send periodic ping messages"""
        try:
            while True:
                await asyncio.sleep(30)
                await websocket.send(json.dumps({"type": "ping"}))
        except asyncio.CancelledError:
            pass

    def _display_message(self, data: dict):
        """Display message in formatted output"""
        msg_type = data.get("type", "unknown")

        if msg_type == "pong":
            # Keepalive response - don't display
            return

        timestamp = datetime.fromisoformat(data.get("timestamp", "").replace("Z", "+00:00"))
        time_str = timestamp.strftime("%H:%M:%S")

        if msg_type == "task_event":
            self._display_task_event(data, time_str)
        elif msg_type == "subscription_confirmed":
            # Already handled in connection
            pass
        else:
            print(f"\n[{time_str}] {msg_type.upper()}")
            print(json.dumps(data, indent=2))

    def _display_task_event(self, data: dict, time_str: str):
        """Display task event message"""
        task_name = data.get("task_name", "unknown")
        status = data.get("status", "unknown")
        message = data.get("message", "")
        progress = data.get("progress")
        metadata = data.get("metadata", {})

        # Status emoji
        status_emoji = {
            "started": "🟡",
            "progress": "🔄",
            "success": "✅",
            "failure": "❌"
        }.get(status, "⚪")

        # Display header
        print(f"\n{status_emoji} [{time_str}] {task_name} - {status.upper()}")

        # Display message
        if message:
            print(f"   📝 {message}")

        # Display progress bar if available
        if progress is not None:
            bar_length = 40
            filled = int(bar_length * progress / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"   [{bar}] {progress}%")

        # Display metadata
        if metadata:
            print(f"   📊 Metadata:")
            for key, value in metadata.items():
                if key == "stage":
                    print(f"      • Stage: {value}")
                elif key == "error":
                    print(f"      • Error: {value}")
                elif key == "duration":
                    print(f"      • Duration: {value}s")
                elif key == "iteration":
                    max_iter = metadata.get("max_iterations", "?")
                    print(f"      • Iteration: {value}/{max_iter}")
                else:
                    print(f"      • {key}: {value}")


async def main():
    parser = argparse.ArgumentParser(description="WebSocket Client Example")
    parser.add_argument("--url", default="ws://localhost:8000", help="WebSocket server URL")
    parser.add_argument("--document", help="Document ID to monitor")
    parser.add_argument("--query", help="Query ID to monitor")
    parser.add_argument("--session", help="Session ID")
    parser.add_argument("--user", help="User ID")

    args = parser.parse_args()

    client = WebSocketClient(args.url)

    try:
        if args.document:
            await client.connect_document(
                document_id=args.document,
                session_id=args.session,
                user_id=args.user
            )
        elif args.query:
            await client.connect_query(
                query_id=args.query,
                session_id=args.session,
                user_id=args.user
            )
        else:
            await client.connect_notifications(
                session_id=args.session,
                user_id=args.user
            )

    except ConnectionRefusedError:
        print(f"❌ Connection refused. Is the server running at {args.url}?")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Empire v7.3 - WebSocket Client Example")
    print("=" * 80)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
