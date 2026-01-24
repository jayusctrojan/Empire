# Task ID: 158

**Title:** CrewAI Workflow Improvements

**Status:** done

**Dependencies:** 127 ✓, 131 ✓, 150 ✓, 156 ✓, 157 ✓

**Priority:** medium

**Description:** Enhance CrewAI workflow management with state persistence, graceful shutdown handling, task cancellation support, and comprehensive metrics and logging.

**Details:**

Implement the following workflow improvements to the CrewAI system:

1. **Workflow State Persistence**:
   - Create a `WorkflowStateManager` class that serializes and persists workflow state
   - Implement checkpointing at critical workflow stages
   - Store state in a configurable backend (file system, database, or Redis)
   - Add state recovery mechanisms for workflow resumption
   - Include versioning for backward compatibility
   - Example implementation:
   ```python
   class WorkflowStateManager:
       def __init__(self, storage_backend="file", storage_path="./workflow_states"):
           self.storage_backend = storage_backend
           self.storage_path = storage_path
           
       def save_state(self, workflow_id, state_data):
           """Serialize and save workflow state"""
           serialized_state = self._serialize_state(state_data)
           if self.storage_backend == "file":
               self._save_to_file(workflow_id, serialized_state)
           elif self.storage_backend == "redis":
               self._save_to_redis(workflow_id, serialized_state)
           # Add other backends as needed
           
       def load_state(self, workflow_id):
           """Load and deserialize workflow state"""
           # Implementation for loading state
   ```

2. **Graceful Shutdown Handling**:
   - Implement signal handlers for SIGTERM and SIGINT
   - Add workflow pause functionality to safely stop at checkpoints
   - Create cleanup procedures for resources (connections, temp files)
   - Implement state saving before shutdown
   - Add logging for shutdown events
   - Example implementation:
   ```python
   import signal
   import sys
   
   class GracefulShutdownHandler:
       def __init__(self, workflow_manager):
           self.workflow_manager = workflow_manager
           signal.signal(signal.SIGTERM, self.handle_shutdown)
           signal.signal(signal.SIGINT, self.handle_shutdown)
           
       def handle_shutdown(self, signum, frame):
           """Handle shutdown signals gracefully"""
           logger.info(f"Received signal {signum}, initiating graceful shutdown")
           self.workflow_manager.pause_workflows()
           self.workflow_manager.save_all_states()
           self.workflow_manager.cleanup_resources()
           sys.exit(0)
   ```

3. **Task Cancellation Support**:
   - Implement a cancellation token system for tasks
   - Add API endpoints for cancelling specific tasks or workflows
   - Create cleanup procedures for cancelled tasks
   - Implement notification system for cancellation events
   - Handle dependent task cancellation logic
   - Example implementation:
   ```python
   class CancellationToken:
       def __init__(self):
           self.cancelled = False
           self._callbacks = []
           
       def cancel(self):
           """Mark as cancelled and execute callbacks"""
           self.cancelled = True
           for callback in self._callbacks:
               callback()
               
       def register_callback(self, callback):
           """Register a callback to be executed on cancellation"""
           self._callbacks.append(callback)
           
       def is_cancelled(self):
           """Check if cancellation has been requested"""
           return self.cancelled
   ```

4. **Workflow Metrics and Logging**:
   - Implement structured logging with contextual information
   - Create metrics collection for workflow performance (duration, resource usage)
   - Add task-level timing and status metrics
   - Implement error rate and failure tracking
   - Create dashboard-ready metrics output (Prometheus format)
   - Example implementation:
   ```python
   class WorkflowMetricsCollector:
       def __init__(self):
           self.metrics = {}
           
       def record_task_start(self, task_id, metadata=None):
           """Record the start of a task"""
           self.metrics[task_id] = {
               "start_time": time.time(),
               "status": "running",
               "metadata": metadata or {}
           }
           
       def record_task_completion(self, task_id, success=True, error=None):
           """Record the completion of a task"""
           if task_id in self.metrics:
               self.metrics[task_id].update({
                   "end_time": time.time(),
                   "duration": time.time() - self.metrics[task_id]["start_time"],
                   "status": "completed" if success else "failed",
                   "error": error
               })
   ```

Integration points:
- Update the main CrewAI workflow controller to use these new components
- Modify the API layer to expose cancellation and metrics endpoints
- Update documentation to reflect new capabilities
- Create migration path for existing workflows

**Test Strategy:**

1. **Workflow State Persistence Testing**:
   - Unit test the `WorkflowStateManager` class with different storage backends
   - Test serialization/deserialization with various workflow states
   - Verify state recovery after simulated crashes
   - Test with corrupted state files to ensure proper error handling
   - Benchmark performance impact of state persistence
   - Test concurrent access patterns

2. **Graceful Shutdown Testing**:
   - Create test harness that sends shutdown signals to running workflows
   - Verify all resources are properly cleaned up after shutdown
   - Test shutdown during different workflow stages
   - Measure shutdown completion time under various loads
   - Verify state is correctly saved during shutdown
   - Test with multiple concurrent workflows

3. **Task Cancellation Testing**:
   - Unit test the cancellation token implementation
   - Test API endpoints for task and workflow cancellation
   - Verify dependent tasks are properly handled during cancellation
   - Test cancellation at different stages of task execution
   - Verify resource cleanup after cancellation
   - Test cancellation propagation in complex workflow graphs

4. **Metrics and Logging Testing**:
   - Verify metrics are correctly collected for all workflow events
   - Test structured logging format and content
   - Validate metrics accuracy with controlled workflow executions
   - Test integration with monitoring systems (Prometheus, Grafana)
   - Verify performance impact of metrics collection
   - Test with high-volume workflows to ensure scalability

5. **Integration Testing**:
   - End-to-end tests with all components integrated
   - Test recovery from various failure scenarios
   - Verify backward compatibility with existing workflows
   - Performance testing under production-like conditions
   - Stress testing with concurrent workflows and cancellations
