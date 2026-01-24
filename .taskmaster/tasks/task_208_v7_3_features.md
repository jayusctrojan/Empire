# Task ID: 208

**Title:** Implement Session Resume & Recovery UI

**Status:** pending

**Dependencies:** 206, 207

**Priority:** medium

**Description:** Create a user interface for browsing, selecting, and resuming from saved sessions and checkpoints

**Details:**

Develop a UI for session management that allows users to browse and resume previous sessions. The implementation should:

1. Show a session picker on app start
2. Display recent sessions with previews
3. Provide a checkpoint browser within sessions
4. Support session resumption from any checkpoint

```jsx
// React components for session management UI
import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';

// Session picker component shown on app start
const SessionPicker = ({ onSelectSession, onNewSession }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Fetch recent sessions on component mount
    const fetchSessions = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/session/recent');
        if (!response.ok) throw new Error('Failed to fetch sessions');
        const data = await response.json();
        setSessions(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchSessions();
  }, []);
  
  if (loading) return <div className="p-4 text-center">Loading recent sessions...</div>;
  if (error) return <div className="p-4 text-center text-red-500">Error: {error}</div>;
  
  return (
    <div className="session-picker p-4 max-w-3xl mx-auto">
      <h2 className="text-xl font-semibold mb-4">Resume Session</h2>
      
      {sessions.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-500">No recent sessions found</p>
          <button 
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            onClick={onNewSession}
          >
            Start New Session
          </button>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {sessions.map(session => (
              <SessionCard 
                key={session.session_id}
                session={session}
                onResume={() => onSelectSession(session.session_id)}
                onBrowseCheckpoints={() => onBrowseCheckpoints(session.session_id)}
              />
            ))}
          </div>
          
          <div className="mt-6 text-center">
            <button 
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              onClick={onNewSession}
            >
              Start New Session
            </button>
          </div>
        </>
      )}
    </div>
  );
};

// Individual session card component
const SessionCard = ({ session, onResume, onBrowseCheckpoints }) => {
  const { 
    session_id, 
    project_name, 
    last_message_preview, 
    updated_at, 
    checkpoint_count,
    token_count 
  } = session;
  
  return (
    <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start">
        <div className="text-2xl text-blue-500 mr-3">📁</div>
        <div className="flex-1">
          <h3 className="font-medium">{project_name || 'Untitled Project'}</h3>
          <p className="text-sm text-gray-600 mt-1 line-clamp-2">
            Last: "{last_message_preview || 'No messages'}"
          </p>
          <div className="flex items-center text-xs text-gray-500 mt-2">
            <span>🕐 {formatTimeAgo(updated_at)}</span>
            <span className="mx-2">•</span>
            <span>{checkpoint_count} checkpoints</span>
            <span className="mx-2">•</span>
            <span>{formatTokens(token_count)} tokens</span>
          </div>
        </div>
      </div>
      <div className="mt-3 flex justify-end space-x-2">
        <button 
          className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-100"
          onClick={onBrowseCheckpoints}
        >
          Browse Checkpoints
        </button>
        <button 
          className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
          onClick={onResume}
        >
          Resume Latest
        </button>
      </div>
    </div>
  );
};

// Checkpoint browser component
const CheckpointBrowser = ({ sessionId, onSelectCheckpoint, onClose }) => {
  const [checkpoints, setCheckpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Fetch checkpoints for the session
    const fetchCheckpoints = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/checkpoint/session/${sessionId}`);
        if (!response.ok) throw new Error('Failed to fetch checkpoints');
        const data = await response.json();
        setCheckpoints(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchCheckpoints();
  }, [sessionId]);
  
  if (loading) return <div className="p-4 text-center">Loading checkpoints...</div>;
  if (error) return <div className="p-4 text-center text-red-500">Error: {error}</div>;
  
  return (
    <div className="checkpoint-browser p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">Session Checkpoints</h2>
        <button 
          className="text-gray-500 hover:text-gray-700"
          onClick={onClose}
        >
          <XIcon className="h-5 w-5" />
        </button>
      </div>
      
      {checkpoints.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-500">No checkpoints found for this session</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {checkpoints.map(checkpoint => (
            <CheckpointCard 
              key={checkpoint.id}
              checkpoint={checkpoint}
              onSelect={() => onSelectCheckpoint(checkpoint.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// Individual checkpoint card component
const CheckpointCard = ({ checkpoint, onSelect }) => {
  const { 
    id, 
    label, 
    trigger, 
    token_count, 
    auto_tags,
    created_at 
  } = checkpoint;
  
  // Format trigger type for display
  const getTriggerLabel = (trigger) => {
    switch(trigger) {
      case 'auto': return 'Automatic';
      case 'manual': return 'Manual';
      case 'pre_compaction': return 'Pre-compaction';
      case 'important_context': return 'Important context';
      default: return trigger;
    }
  };
  
  return (
    <div className="border rounded p-3 hover:bg-gray-50">
      <div className="flex justify-between">
        <div>
          <h4 className="font-medium">{label}</h4>
          <div className="text-xs text-gray-500 mt-1">
            {format(new Date(created_at), 'MMM d, yyyy h:mm a')}
          </div>
        </div>
        <div className="text-right text-sm">
          <div>{formatTokens(token_count)} tokens</div>
          <div className="text-xs text-gray-500">{getTriggerLabel(trigger)}</div>
        </div>
      </div>
      
      {auto_tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {auto_tags.map(tag => (
            <span 
              key={tag} 
              className="px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded-full"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      
      <div className="mt-2 text-right">
        <button 
          className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
          onClick={onSelect}
        >
          Resume from here
        </button>
      </div>
    </div>
  );
};

// Helper functions
const formatTimeAgo = (timestamp) => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMinutes = Math.floor((now - date) / (1000 * 60));
  
  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes} minutes ago`;
  
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hours ago`;
  
  return format(date, 'MMM d, yyyy');
};

const formatTokens = (tokens) => {
  return tokens >= 1000 ? `${(tokens/1000).toFixed(1)}K` : tokens;
};

export { SessionPicker, CheckpointBrowser };
```

The UI should provide a seamless experience for resuming previous sessions and recovering from crashes. It should show relevant information about each session and checkpoint to help users make informed decisions.

**Test Strategy:**

1. Unit tests:
   - Test component rendering with different data
   - Verify formatting functions for time and tokens
   - Test empty state handling

2. Integration tests:
   - Verify session data fetching and display
   - Test checkpoint browser functionality
   - Verify session resumption flow

3. Visual regression tests:
   - Capture screenshots of session picker in different states
   - Test responsive design on different screen sizes

4. User acceptance testing:
   - Verify session picker appears on app launch
   - Test session resumption from different checkpoints
   - Confirm UI is intuitive and easy to navigate

## Subtasks

### 208.1. Create SessionPicker.tsx component

**Status:** pending  
**Dependencies:** None  

Implement the SessionPicker component that displays recent sessions on app start

**Details:**

Create the SessionPicker.tsx component in empire-desktop/src/components/ that displays a list of recent sessions with previews. The component should handle loading states, empty states, and provide options to resume a session or start a new one. Include the SessionCard subcomponent for displaying individual session information.

### 208.2. Create CheckpointBrowser.tsx component

**Status:** pending  
**Dependencies:** 208.1  

Implement the CheckpointBrowser component with timeline view for browsing checkpoints within a session

**Details:**

Create the CheckpointBrowser.tsx component in empire-desktop/src/components/ that displays checkpoints for a selected session in a timeline view. Include the CheckpointCard subcomponent for displaying individual checkpoint details. Implement sorting, filtering, and selection of checkpoints for resumption.

### 208.3. Create sessionApi.ts client

**Status:** pending  
**Dependencies:** None  

Implement the API client for session management operations

**Details:**

Create sessionApi.ts in empire-desktop/src/services/ that provides methods for fetching sessions, checkpoints, and handling session resumption. Implement proper error handling, request cancellation, and response parsing. Include TypeScript interfaces for session and checkpoint data structures.

### 208.4. Implement GET /sessions endpoint

**Status:** pending  
**Dependencies:** 208.3  

Create backend endpoint for retrieving recent sessions with pagination and filtering

**Details:**

Implement the GET /sessions endpoint that returns a list of recent sessions with pagination support. Include metadata like project name, last message preview, updated timestamp, checkpoint count, and token count. Support filtering by date range and sorting options.

### 208.5. Implement GET /sessions/picker endpoint

**Status:** pending  
**Dependencies:** 208.3, 208.4  

Create optimized endpoint for the session picker shown at app launch

**Details:**

Implement the GET /sessions/picker endpoint optimized for quick loading at app launch. This should return a limited set of the most recent sessions with minimal data needed for the picker UI. Include caching headers to improve performance on subsequent app launches.

### 208.6. Implement POST /sessions/{session_id}/resume endpoint

**Status:** pending  
**Dependencies:** 208.3  

Create endpoint for resuming a session from a specific checkpoint

**Details:**

Implement the POST /sessions/{session_id}/resume endpoint that handles session resumption from a specific checkpoint. Support optional checkpoint_id parameter to resume from a specific point. Handle session state restoration including conversation history, context, and any associated resources.

### 208.7. Implement conflict detection for sessions

**Status:** pending  
**Dependencies:** 208.6  

Add last-write-wins conflict resolution for sessions updated in multiple locations

**Details:**

Implement conflict detection and resolution for sessions that may have been updated in multiple locations. Use a timestamp-based last-write-wins strategy. Add version tracking to session objects and include conflict detection in the resume endpoint. Provide clear error messages when conflicts are detected.

### 208.8. Add session conflict notification UI

**Status:** pending  
**Dependencies:** 208.1, 208.7  

Implement UI notification for when a session has been updated elsewhere

**Details:**

Create a notification component that appears when a session conflict is detected. The notification should inform the user that the session has been updated elsewhere and provide options to either use the latest version or continue with the current version. Include visual indicators for conflicted sessions in the session picker.

### 208.9. Integrate session picker into app launch flow

**Status:** pending  
**Dependencies:** 208.1, 208.5  

Add the session picker to the application startup sequence

**Details:**

Integrate the SessionPicker component into the application startup flow. Show the session picker when the app launches, unless the user has disabled this feature. Handle the transition from session selection to either resuming a session or starting a new one. Implement persistence of the user's preference for showing the picker on startup.
