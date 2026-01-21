# Task ID: 138

**Title:** Implement Review Agent Revision Loop

**Status:** done

**Dependencies:** 107 ✓, 110 ✓, 137 ✓

**Priority:** medium

**Description:** Implement a revision loop for AGENT-015 Review Agent that routes content back to AGENT-014 Writing Agent when quality thresholds aren't met, with a maximum of 3 iterations and metrics tracking.

**Details:**

Create a revision loop system between the Review Agent and Writing Agent with the following components:

1. Enhance the Review Agent (AGENT-015) output schema:
   ```python
   class ReviewOutput(BaseModel):
       content_id: str
       passed: bool
       quality_score: float  # New field for quantitative assessment
       feedback: List[FeedbackItem]
       revision_count: int = 0  # Track number of revisions
   ```

2. Modify the orchestration workflow to handle revisions:
   ```python
   class WorkflowState(BaseModel):
       # Existing fields
       revision_requested: bool = False  # New flag to indicate revision needed
       current_revision: int = 0  # Track current revision number
   ```

3. Implement the revision loop logic in the workflow orchestrator:
   ```python
   async def process_review_result(review_output: ReviewOutput, workflow_state: WorkflowState):
       # Update metrics
       metrics.record_quality_score(review_output.content_id, review_output.quality_score)
       
       if not review_output.passed and workflow_state.current_revision < 3:
           # Route back to writing agent with feedback
           workflow_state.revision_requested = True
           workflow_state.current_revision += 1
           
           # Record metrics for revision request
           metrics.increment_revision_count(review_output.content_id)
           
           # Send to writing agent with feedback
           return await writing_agent.revise_content(
               content_id=review_output.content_id,
               feedback=review_output.feedback,
               revision_number=workflow_state.current_revision
           )
       elif not review_output.passed:
           # Max revisions reached, flag for human review
           workflow_state.requires_human_review = True
           metrics.record_failed_after_max_revisions(review_output.content_id)
           return workflow_state
       else:
           # Content passed review
           metrics.record_successful_content(
               content_id=review_output.content_id, 
               revision_count=workflow_state.current_revision
           )
           return workflow_state
   ```

4. Enhance the Writing Agent (AGENT-014) to handle revision requests:
   ```python
   async def revise_content(self, content_id: str, feedback: List[FeedbackItem], revision_number: int):
       # Retrieve original content
       original_content = await self.content_repository.get_content(content_id)
       
       # Format feedback for the LLM
       formatted_feedback = self.format_feedback_for_revision(feedback)
       
       # Create revision prompt with specific focus on addressing feedback
       revision_prompt = f"""
       You are revising content based on review feedback. This is revision #{revision_number}.
       
       ORIGINAL CONTENT:
       {original_content.text}
       
       REVIEW FEEDBACK:
       {formatted_feedback}
       
       Please revise the content to address all feedback points while maintaining the original purpose.
       Focus especially on improving the areas mentioned in the feedback.
       """
       
       # Get revised content from LLM
       revised_content = await self.llm_service.generate_content(revision_prompt)
       
       # Store revision history
       await self.content_repository.save_revision(
           content_id=content_id,
           revision_number=revision_number,
           original_content=original_content.text,
           revised_content=revised_content,
           feedback=feedback
       )
       
       # Update content
       await self.content_repository.update_content(content_id, revised_content)
       
       return revised_content
   ```

5. Implement metrics tracking for revisions:
   ```python
   # In app/services/metrics.py
   
   def record_quality_score(content_id: str, quality_score: float):
       # Record quality score in metrics system
       pass
       
   def increment_revision_count(content_id: str):
       # Increment revision counter for this content
       pass
       
   def record_quality_improvement(content_id: str, original_score: float, new_score: float):
       # Record delta between original and new quality scores
       pass
       
   def record_failed_after_max_revisions(content_id: str):
       # Record instances where content failed even after max revisions
       pass
       
   def record_successful_content(content_id: str, revision_count: int):
       # Record successful content with the number of revisions needed
       pass
   ```

6. Create a dashboard view for revision metrics:
   - Average quality score improvement per revision
   - Distribution of revision counts
   - Success rate after revisions
   - Content requiring max revisions

**Test Strategy:**

1. Unit tests for the revision loop logic:
   - Test that content with quality_score below threshold gets flagged for revision
   - Test that revision_count increments correctly
   - Test that max revisions (3) is enforced
   - Test that feedback is properly passed to the Writing Agent

2. Integration tests for the Review-Write cycle:
   - Test end-to-end flow with mock agents
   - Verify content is properly updated after revision
   - Test with various quality scores to ensure threshold logic works
   - Verify revision history is properly stored

3. Metrics validation:
   - Verify quality scores are recorded correctly
   - Test that revision counts are accurately tracked
   - Validate quality improvement calculations
   - Test dashboard data aggregation

4. Edge case testing:
   - Test behavior when a revision improves but still doesn't meet threshold
   - Test when Writing Agent fails during revision
   - Test concurrent revisions for different content pieces
   - Test with malformed feedback data

5. Performance testing:
   - Measure latency impact of revision loops
   - Test system under load with multiple simultaneous revision cycles
   - Verify database performance with revision history storage

6. User acceptance testing:
   - Verify that revision feedback is clear and actionable
   - Test that quality improvements are meaningful
   - Validate dashboard metrics against manual calculations
