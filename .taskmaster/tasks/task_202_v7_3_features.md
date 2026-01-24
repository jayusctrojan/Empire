# Task ID: 202

**Title:** Develop Context Window Progress Bar UI Component

**Status:** pending

**Dependencies:** 201

**Priority:** high

**Description:** Create a visual progress bar component that displays real-time context window usage with color-coded status indicators

**Details:**

Implement a progress bar UI component that shows the current context window usage. The component should:

1. Display a visual progress bar with color-coded sections
2. Show numeric token counts on hover
3. Indicate reserved space for AI responses
4. Update in real-time as messages are added
5. Change colors based on usage thresholds

```jsx
// React component for context window progress bar
import React, { useState, useEffect } from 'react';
import { Tooltip } from './Tooltip';

const ContextWindowProgressBar = ({ 
  currentTokens, 
  maxTokens, 
  reservedTokens,
  status,
  onThresholdReached = () => {}
}) => {
  // Calculate percentages for display
  const usedPercent = (currentTokens / maxTokens) * 100;
  const reservedPercent = (reservedTokens / maxTokens) * 100;
  const availablePercent = 100 - usedPercent - reservedPercent;
  
  // Determine color based on status
  const getStatusColor = (status) => {
    switch(status) {
      case 'critical': return 'bg-red-500';
      case 'warning': return 'bg-yellow-500';
      case 'normal': return 'bg-green-500';
      default: return 'bg-green-500';
    }
  };
  
  // Format token counts for display
  const formatTokens = (tokens) => {
    return tokens >= 1000 ? `${(tokens/1000).toFixed(1)}K` : tokens;
  };
  
  // Tooltip content
  const tooltipContent = (
    <div className="p-2">
      <div>Used: {formatTokens(currentTokens)} tokens ({usedPercent.toFixed(1)}%)</div>
      <div>Reserved: {formatTokens(reservedTokens)} tokens ({reservedPercent.toFixed(1)}%)</div>
      <div>Available: {formatTokens(maxTokens - currentTokens - reservedTokens)} tokens ({availablePercent.toFixed(1)}%)</div>
      <div>Total capacity: {formatTokens(maxTokens)} tokens</div>
    </div>
  );
  
  // Pulse animation when approaching threshold
  const shouldPulse = status === 'warning' || status === 'critical';
  
  return (
    <Tooltip content={tooltipContent}>
      <div className="w-full h-6 rounded-md overflow-hidden border border-gray-300 flex">
        {/* Used tokens section */}
        <div 
          className={`h-full ${getStatusColor(status)} ${shouldPulse ? 'animate-pulse' : ''}`}
          style={{ width: `${usedPercent}%` }}
        />
        
        {/* Reserved tokens section */}
        <div 
          className="h-full bg-gray-400 opacity-50"
          style={{ width: `${reservedPercent}%` }}
        />
        
        {/* Available tokens section */}
        <div 
          className="h-full bg-gray-200"
          style={{ width: `${availablePercent}%` }}
        />
      </div>
      <div className="text-xs text-center mt-1">
        Context: {formatTokens(currentTokens)} / {formatTokens(maxTokens)} tokens ({usedPercent.toFixed(0)}%)
      </div>
    </Tooltip>
  );
};

export default ContextWindowProgressBar;
```

The component should be integrated into the chat interface header or footer area and remain visible at all times during the conversation. It should update smoothly as new messages are added without causing UI lag.

**Test Strategy:**

1. Unit tests:
   - Test rendering with different token counts and statuses
   - Verify color changes at different thresholds
   - Test tooltip content accuracy

2. Integration tests:
   - Verify real-time updates when messages are added
   - Test animation triggers at warning/critical thresholds
   - Verify tooltip displays correct information

3. Visual regression tests:
   - Capture screenshots at different states (normal, warning, critical)
   - Ensure consistent rendering across browsers

4. User acceptance testing:
   - Verify progress bar is easily visible but not distracting
   - Confirm color coding is intuitive
   - Test responsiveness on different screen sizes

## Subtasks

### 202.1. Create ContextProgressBar.tsx component

**Status:** pending  
**Dependencies:** None  

Implement the React component for displaying the context window usage progress bar with color-coded sections.

**Details:**

Create the ContextProgressBar.tsx component in empire-desktop/src/components/ directory. Implement the visual progress bar with color-coded sections based on usage thresholds. Include the basic structure with used, reserved, and available token sections as shown in the provided code sample.

### 202.2. Implement tooltip functionality for token details

**Status:** pending  
**Dependencies:** 202.1  

Add tooltip functionality to display detailed token information when hovering over the progress bar.

**Details:**

Enhance the ContextProgressBar component to show numeric token counts on hover using the Tooltip component. Display used tokens, reserved tokens, available tokens, and total capacity in a formatted way. Implement the formatTokens helper function to properly display token counts (e.g., '4.2K' for 4200).

### 202.3. Create useContextWindow.ts custom hook

**Status:** pending  
**Dependencies:** None  

Develop a custom React hook to manage context window state and calculations.

**Details:**

Create useContextWindow.ts hook in empire-desktop/src/hooks/ directory. The hook should manage the current token count, max tokens, reserved tokens, and calculate percentages. It should also determine the status based on thresholds (green <70%, yellow 70-85%, red >85%) and provide functions to update the token count.

### 202.4. Implement color-coded status display with animations

**Status:** pending  
**Dependencies:** 202.1, 202.3  

Add color-coded status indicators and pulse animations for warning states.

**Details:**

Enhance the ContextProgressBar component to change colors based on usage thresholds (green <70%, yellow 70-85%, red >85%). Implement the getStatusColor function to return appropriate color classes. Add pulse animation effect when the status is 'warning' or 'critical' to draw user attention to approaching limits.

### 202.5. Implement GET /context/{conversation_id} API endpoint

**Status:** pending  
**Dependencies:** None  

Create a backend API endpoint to retrieve context window information for a specific conversation.

**Details:**

Implement the GET /context/{conversation_id} endpoint in app/routes/context_management.py. The endpoint should return the current token count, max tokens allowed, reserved tokens, and status for the specified conversation. Include proper error handling for invalid conversation IDs.

### 202.6. Add WebSocket subscription for real-time updates

**Status:** pending  
**Dependencies:** 202.3, 202.5  

Implement WebSocket functionality to provide real-time context window usage updates.

**Details:**

Set up WebSocket subscription in the useContextWindow hook to receive real-time updates on context window usage. Implement the necessary backend WebSocket handler to emit events when the context window usage changes. Ensure the progress bar updates smoothly without causing UI lag.

### 202.7. Integrate progress bar into chat interface and create tests

**Status:** pending  
**Dependencies:** 202.1, 202.2, 202.3, 202.4, 202.6  

Add the context window progress bar to the chat interface and create comprehensive tests.

**Details:**

Integrate the ContextProgressBar component into the chat interface header or footer area to remain visible during conversations. Create integration test for context API in tests/integration/test_context_api.py to verify the entire feature works correctly. Ensure the component updates smoothly as new messages are added without causing UI lag.
