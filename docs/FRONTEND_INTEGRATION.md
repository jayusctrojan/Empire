# Frontend Integration Guide - Real-Time Notifications

This guide explains how to integrate Empire v7.3's real-time WebSocket notifications and email alerts into your frontend application.

## Table of Contents

1. [WebSocket Connection](#websocket-connection)
2. [Message Formats](#message-formats)
3. [React Integration](#react-integration)
4. [Vue Integration](#vue-integration)
5. [Vanilla JavaScript](#vanilla-javascript)
6. [Email Preferences UI](#email-preferences-ui)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## WebSocket Connection

### Connection URL

```
ws://localhost:8082/api/v1/notifications/ws?session_id={SESSION_ID}
```

Production:
```
wss://your-domain.com/api/v1/notifications/ws?session_id={SESSION_ID}
```

### Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `session_id` | No | Unique session identifier for multi-tab support |
| `user_id` | No | User identifier for authenticated users |

### Generating Session ID

```javascript
function generateSessionId() {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}
```

---

## Message Formats

### Task Notification

```json
{
  "type": "task_notification",
  "task_id": "abc-123-def-456",
  "task_type": "document_processing",
  "status": "completed",
  "message": "Processing completed: contract.pdf",
  "metadata": {
    "filename": "contract.pdf",
    "result": {
      "status": "success",
      "file_id": "xyz-789"
    },
    "duration": 45.2
  },
  "timestamp": "2025-11-05T22:30:15.123Z"
}
```

### Progress Update

```json
{
  "type": "progress_update",
  "task_id": "abc-123",
  "progress": 75,
  "total": 100,
  "percentage": 75.0,
  "message": "Processing page 75 of 100",
  "timestamp": "2025-11-05T22:30:15.123Z"
}
```

### Connection Messages

```json
{
  "type": "pong",
  "timestamp": "2025-11-05T22:30:15.123Z"
}
```

```json
{
  "type": "stats",
  "data": {
    "total_connections": 5,
    "sessions": 3,
    "users": 2
  }
}
```

### Task Status Values

- `pending` - Task queued but not started
- `processing` - Task currently running
- `completed` - Task finished successfully
- `failed` - Task failed after all retries
- `retry` - Task being retried
- `cancelled` - Task was cancelled

---

## React Integration

### WebSocket Hook

Create `hooks/useWebSocket.js`:

```javascript
import { useState, useEffect, useCallback, useRef } from 'react';

export function useWebSocket(url) {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setMessages((prev) => [data, ...prev].slice(0, 50)); // Keep last 50
        } catch (err) {
          console.error('Error parsing message:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('Connection error');
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);

        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Reconnecting...');
          connect();
        }, 3000);
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to connect:', err);
      setError(err.message);
    }
  }, [url]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    messages,
    error,
    sendMessage,
    reconnect: connect,
  };
}
```

### Notification Component

Create `components/NotificationCenter.jsx`:

```jsx
import React, { useMemo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

export function NotificationCenter({ sessionId }) {
  const wsUrl = `ws://localhost:8082/api/v1/notifications/ws?session_id=${sessionId}`;
  const { isConnected, messages, error, sendMessage } = useWebSocket(wsUrl);

  const taskNotifications = useMemo(() => {
    return messages.filter((msg) => msg.type === 'task_notification');
  }, [messages]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return '✅';
      case 'failed': return '❌';
      case 'processing': return '⏳';
      case 'retry': return '🔄';
      default: return '📋';
    }
  };

  return (
    <div className="notification-center">
      <div className="header">
        <h2>Notifications</h2>
        <span className={`status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '● Connected' : '● Disconnected'}
        </span>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <div className="notification-list">
        {taskNotifications.length === 0 ? (
          <div className="empty-state">
            No notifications yet
          </div>
        ) : (
          taskNotifications.map((notification, index) => (
            <div
              key={`${notification.task_id}-${index}`}
              className={`notification notification-${notification.status}`}
            >
              <div className="notification-header">
                <span className="icon">{getStatusIcon(notification.status)}</span>
                <span className="task-type">{notification.task_type}</span>
                <span className="time">{new Date(notification.timestamp).toLocaleTimeString()}</span>
              </div>
              <div className="notification-message">
                {notification.message}
              </div>
              {notification.metadata?.filename && (
                <div className="notification-filename">
                  {notification.metadata.filename}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

### Usage

```jsx
import { NotificationCenter } from './components/NotificationCenter';
import { useState, useEffect } from 'react';

function App() {
  const [sessionId] = useState(() =>
    `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );

  return (
    <div className="app">
      <NotificationCenter sessionId={sessionId} />
    </div>
  );
}
```

---

## Vue Integration

### Composable

Create `composables/useWebSocket.js`:

```javascript
import { ref, onMounted, onUnmounted } from 'vue';

export function useWebSocket(url) {
  const isConnected = ref(false);
  const messages = ref([]);
  const error = ref(null);
  let ws = null;
  let reconnectTimeout = null;

  const connect = () => {
    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected');
        isConnected.value = true;
        error.value = null;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          messages.value = [data, ...messages.value].slice(0, 50);
        } catch (err) {
          console.error('Error parsing message:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        error.value = 'Connection error';
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        isConnected.value = false;

        // Reconnect after 3 seconds
        reconnectTimeout = setTimeout(() => {
          console.log('Reconnecting...');
          connect();
        }, 3000);
      };
    } catch (err) {
      console.error('Failed to connect:', err);
      error.value = err.message;
    }
  };

  const disconnect = () => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
    }
    if (ws) {
      ws.close();
      ws = null;
    }
  };

  const sendMessage = (message) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  };

  onMounted(() => {
    connect();
  });

  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    messages,
    error,
    sendMessage,
    reconnect: connect,
  };
}
```

### Component

```vue
<template>
  <div class="notification-center">
    <div class="header">
      <h2>Notifications</h2>
      <span :class="['status', isConnected ? 'connected' : 'disconnected']">
        {{ isConnected ? '● Connected' : '● Disconnected' }}
      </span>
    </div>

    <div v-if="error" class="error-banner">
      {{ error }}
    </div>

    <div class="notification-list">
      <div v-if="taskNotifications.length === 0" class="empty-state">
        No notifications yet
      </div>
      <div
        v-for="(notification, index) in taskNotifications"
        :key="`${notification.task_id}-${index}`"
        :class="['notification', `notification-${notification.status}`]"
      >
        <div class="notification-header">
          <span class="icon">{{ getStatusIcon(notification.status) }}</span>
          <span class="task-type">{{ notification.task_type }}</span>
          <span class="time">{{ formatTime(notification.timestamp) }}</span>
        </div>
        <div class="notification-message">
          {{ notification.message }}
        </div>
        <div v-if="notification.metadata?.filename" class="notification-filename">
          {{ notification.metadata.filename }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useWebSocket } from '../composables/useWebSocket';

const props = defineProps({
  sessionId: {
    type: String,
    required: true,
  },
});

const wsUrl = `ws://localhost:8082/api/v1/notifications/ws?session_id=${props.sessionId}`;
const { isConnected, messages, error, sendMessage } = useWebSocket(wsUrl);

const taskNotifications = computed(() => {
  return messages.value.filter((msg) => msg.type === 'task_notification');
});

const getStatusIcon = (status) => {
  const icons = {
    completed: '✅',
    failed: '❌',
    processing: '⏳',
    retry: '🔄',
  };
  return icons[status] || '📋';
};

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString();
};
</script>
```

---

## Vanilla JavaScript

### Simple Implementation

```javascript
class NotificationManager {
  constructor(url, options = {}) {
    this.url = url;
    this.ws = null;
    this.isConnected = false;
    this.reconnectDelay = options.reconnectDelay || 3000;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
    this.reconnectAttempts = 0;
    this.listeners = new Map();

    this.connect();
  }

  connect() {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connect', {});
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.emit('message', data);
          this.emit(data.type, data);
        } catch (err) {
          console.error('Error parsing message:', err);
        }
      };

      this.ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        this.emit('error', { error: err });
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.isConnected = false;
        this.emit('disconnect', {});

        // Attempt reconnection
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`);
          setTimeout(() => this.connect(), this.reconnectDelay);
        }
      };
    } catch (err) {
      console.error('Failed to connect:', err);
      this.emit('error', { error: err });
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach((callback) => callback(data));
    }
  }
}

// Usage
const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
const wsUrl = `ws://localhost:8082/api/v1/notifications/ws?session_id=${sessionId}`;
const notificationManager = new NotificationManager(wsUrl);

// Listen for task notifications
notificationManager.on('task_notification', (notification) => {
  console.log('Task notification:', notification);
  displayNotification(notification);
});

// Listen for progress updates
notificationManager.on('progress_update', (progress) => {
  console.log('Progress:', progress);
  updateProgressBar(progress);
});

// Listen for connection status
notificationManager.on('connect', () => {
  updateConnectionStatus('connected');
});

notificationManager.on('disconnect', () => {
  updateConnectionStatus('disconnected');
});
```

---

## Email Preferences UI

### Settings Component (React)

```jsx
import React, { useState } from 'react';

export function EmailPreferences({ userId }) {
  const [preferences, setPreferences] = useState({
    enabled: false,
    email: '',
    notifyOnComplete: true,
    notifyOnFailure: true,
    notifyOnLongRunning: true,
    longRunningThreshold: 300, // 5 minutes
  });

  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch('/api/v1/users/email-preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preferences),
      });

      if (response.ok) {
        alert('Preferences saved!');
      } else {
        alert('Failed to save preferences');
      }
    } catch (err) {
      console.error('Error saving preferences:', err);
      alert('Error saving preferences');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="email-preferences">
      <h2>Email Notification Preferences</h2>

      <label>
        <input
          type="checkbox"
          checked={preferences.enabled}
          onChange={(e) => setPreferences({ ...preferences, enabled: e.target.checked })}
        />
        Enable email notifications
      </label>

      {preferences.enabled && (
        <>
          <div className="form-group">
            <label>Email Address</label>
            <input
              type="email"
              value={preferences.email}
              onChange={(e) => setPreferences({ ...preferences, email: e.target.value })}
              placeholder="your-email@example.com"
            />
          </div>

          <div className="notification-types">
            <h3>Notification Types</h3>

            <label>
              <input
                type="checkbox"
                checked={preferences.notifyOnComplete}
                onChange={(e) => setPreferences({ ...preferences, notifyOnComplete: e.target.checked })}
              />
              Task completed
            </label>

            <label>
              <input
                type="checkbox"
                checked={preferences.notifyOnFailure}
                onChange={(e) => setPreferences({ ...preferences, notifyOnFailure: e.target.checked })}
              />
              Task failed
            </label>

            <label>
              <input
                type="checkbox"
                checked={preferences.notifyOnLongRunning}
                onChange={(e) => setPreferences({ ...preferences, notifyOnLongRunning: e.target.checked })}
              />
              Long-running task alert
            </label>
          </div>

          <div className="form-group">
            <label>Long-Running Task Threshold (minutes)</label>
            <select
              value={preferences.longRunningThreshold}
              onChange={(e) => setPreferences({ ...preferences, longRunningThreshold: parseInt(e.target.value) })}
            >
              <option value="60">1 minute</option>
              <option value="180">3 minutes</option>
              <option value="300">5 minutes</option>
              <option value="600">10 minutes</option>
              <option value="1800">30 minutes</option>
            </select>
          </div>

          <button onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save Preferences'}
          </button>
        </>
      )}
    </div>
  );
}
```

---

## Error Handling

### Connection Errors

```javascript
notificationManager.on('error', (error) => {
  console.error('WebSocket error:', error);

  // Display user-friendly message
  showErrorToast('Connection error. Retrying...');
});

notificationManager.on('disconnect', () => {
  // Update UI to show disconnected state
  updateConnectionIndicator('disconnected');
});

notificationManager.on('connect', () => {
  // Clear any error messages
  clearErrorToast();
  updateConnectionIndicator('connected');
});
```

### Message Parsing Errors

```javascript
try {
  const data = JSON.parse(event.data);
  handleMessage(data);
} catch (err) {
  console.error('Failed to parse message:', err);
  // Log to error tracking service
  logError('websocket_parse_error', { message: event.data, error: err });
}
```

---

## Best Practices

### 1. Connection Management

- ✅ **Auto-reconnect** with exponential backoff
- ✅ **Heartbeat/ping** every 30 seconds to keep connection alive
- ✅ **Graceful disconnect** on page unload
- ✅ **Connection status indicator** for users

### 2. Performance

- ✅ **Limit stored messages** to last 50-100
- ✅ **Debounce UI updates** for rapid messages
- ✅ **Use virtual scrolling** for large notification lists
- ✅ **Clean up listeners** on component unmount

### 3. User Experience

- ✅ **Show connection status** (connected/disconnected)
- ✅ **Display notifications** as toast/banner
- ✅ **Play sound** for important notifications (optional)
- ✅ **Badge count** for unread notifications
- ✅ **Actionable notifications** with buttons

### 4. Security

- ✅ **Use WSS** (secure WebSocket) in production
- ✅ **Authenticate connections** with user tokens
- ✅ **Validate message format** before processing
- ✅ **Sanitize displayed content** to prevent XSS

### 5. Testing

```javascript
// Mock WebSocket for testing
class MockWebSocket {
  constructor(url) {
    this.url = url;
    setTimeout(() => this.onopen(), 100);
  }

  send(data) {
    console.log('Mock send:', data);
  }

  close() {
    setTimeout(() => this.onclose(), 100);
  }
}

// Use in tests
global.WebSocket = MockWebSocket;
```

---

## References

- **WebSocket Test Page**: `/static/websocket_test.html`
- **API Documentation**: `/docs` (FastAPI Swagger UI)
- **Email Setup Guide**: `docs/EMAIL_SETUP.md`
- **WebSocket Endpoint**: `app/api/notifications.py`

---

## Support

For issues or questions about frontend integration:

1. Check browser console for WebSocket errors
2. Verify connection URL and parameters
3. Test with the WebSocket test page first
4. Review server logs for backend issues

## Examples Repository

Full working examples available in:
- `app/static/websocket_test.html` - Vanilla JavaScript reference implementation
- Contact development team for React/Vue starter templates
