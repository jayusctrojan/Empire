# Task ID: 204

**Title:** Create Inline Compaction UI with Visual Divider

**Status:** pending

**Dependencies:** 202, 203

**Priority:** medium

**Description:** Implement the UI components for displaying compaction results inline with a visual divider and collapsible summary section

**Details:**

Develop UI components that show when compaction has occurred in the conversation. The implementation should:

1. Display a visual divider showing token reduction metrics
2. Provide a collapsible section with the condensed summary
3. Allow users to expand/collapse the summary
4. Show animation during compaction process

```jsx
// React component for compaction divider
import React, { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/solid';

const CompactionDivider = ({ 
  preTokens, 
  postTokens, 
  summary,
  timestamp,
  isExpanded = false
}) => {
  const [expanded, setExpanded] = useState(isExpanded);
  const reductionPercent = ((preTokens - postTokens) / preTokens * 100).toFixed(0);
  
  // Format token counts for display
  const formatTokens = (tokens) => {
    return tokens >= 1000 ? `${(tokens/1000).toFixed(1)}K` : tokens;
  };
  
  return (
    <div className="my-4 border-t border-b border-gray-200 py-2">
      {/* Divider header with metrics */}
      <div 
        className="flex items-center cursor-pointer hover:bg-gray-50 p-2 rounded"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? 
          <ChevronDownIcon className="h-5 w-5 text-gray-500" /> : 
          <ChevronRightIcon className="h-5 w-5 text-gray-500" />
        }
        <div className="ml-2 text-sm text-gray-600">
          <span className="font-medium">Context condensed</span> ({formatTokens(preTokens)} → {formatTokens(postTokens)} tokens, {reductionPercent}% reduction)
        </div>
        <div className="ml-auto text-xs text-gray-400">
          {new Date(timestamp).toLocaleTimeString()}
        </div>
      </div>
      
      {/* Collapsible summary section */}
      {expanded && (
        <div className="mt-2 p-3 bg-gray-50 rounded text-sm border-l-4 border-blue-400">
          <div className="font-medium mb-2 text-gray-700">Condensed Summary:</div>
          <div className="whitespace-pre-wrap">{summary}</div>
        </div>
      )}
    </div>
  );
};

// Animation component for compaction in progress
const CompactionInProgress = () => {
  return (
    <div className="my-4 p-4 border border-yellow-200 bg-yellow-50 rounded-md flex items-center">
      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-yellow-700 mr-3"></div>
      <div className="text-sm text-yellow-800">
        Condensing conversation context...
      </div>
    </div>
  );
};

export { CompactionDivider, CompactionInProgress };
```

This component should be inserted into the conversation flow whenever compaction occurs. It should provide a clear visual indication that compaction has happened while allowing users to see what was condensed if needed.

**Test Strategy:**

1. Unit tests:
   - Test rendering with different token counts and summaries
   - Verify expand/collapse functionality works correctly
   - Test animation component rendering

2. Integration tests:
   - Verify divider appears after compaction completes
   - Test interaction with the chat interface
   - Verify metrics display correctly

3. Visual regression tests:
   - Capture screenshots of divider in different states
   - Ensure consistent rendering across browsers

4. User acceptance testing:
   - Verify divider is noticeable but not disruptive
   - Test expand/collapse interaction
   - Confirm summary content is readable and well-formatted

## Subtasks

### 204.1. Create CompactionDivider.tsx component

**Status:** pending  
**Dependencies:** None  

Implement the base CompactionDivider component with expand/collapse functionality

**Details:**

Create the CompactionDivider.tsx file in empire-desktop/src/components/ directory. Implement the component with props for preTokens, postTokens, summary, timestamp, and isExpanded. Include the expand/collapse toggle functionality with useState hook and appropriate styling for the divider header.

### 204.2. Implement CompactionInProgress animation component

**Status:** pending  
**Dependencies:** None  

Create the animation component that displays during the compaction process

**Details:**

Implement the CompactionInProgress component in the same file as CompactionDivider. Add the loading spinner animation and appropriate styling to indicate that compaction is in progress. Ensure the component is visually distinct from the CompactionDivider component.

### 204.3. Implement token reduction metrics display

**Status:** pending  
**Dependencies:** 204.1  

Add functionality to calculate and display token reduction metrics in the divider header

**Details:**

Enhance the CompactionDivider component to calculate and display token reduction metrics. Implement the formatTokens function to display large token counts in a readable format (e.g., 1.2K). Calculate and display the reduction percentage. Ensure the metrics are properly aligned in the UI.

### 204.4. Create collapsible summary section with styling

**Status:** pending  
**Dependencies:** 204.1  

Implement the collapsible summary section that displays the condensed content

**Details:**

Enhance the CompactionDivider component to display the condensed summary in a collapsible section. Style the summary section with appropriate background, borders, and typography. Ensure the summary text preserves whitespace and formatting. Add proper padding and margins for readability.

### 204.5. Add timestamp display and responsive design

**Status:** pending  
**Dependencies:** 204.1, 204.3  

Implement timestamp display and ensure responsive design across different screen sizes

**Details:**

Add functionality to format and display the timestamp when compaction occurred. Ensure the component layout is responsive and works well on different screen sizes. Implement proper alignment of elements in the header (chevron icon, text, timestamp) using flexbox. Test on mobile and desktop viewports.

### 204.6. Integrate compaction UI into chat message list

**Status:** pending  
**Dependencies:** 204.1, 204.2, 204.3, 204.4, 204.5  

Integrate the CompactionDivider and CompactionInProgress components into the chat message list

**Details:**

Update the chat message list component to include CompactionDivider and CompactionInProgress components at appropriate positions in the conversation flow. Add logic to determine when to show the compaction in progress animation versus the completed divider. Ensure proper spacing between messages and compaction dividers.
