# Task ID: 200

**Title:** Implement Agent Feedback System

**Status:** cancelled

**Dependencies:** 199 ✗

**Priority:** medium

**Description:** Create the agent feedback system by implementing the agent_feedback table in Supabase and adding feedback storage functionality to the classification and asset management services.

**Details:**

This task involves implementing the agent feedback system across multiple files:

1. First, create the agent_feedback table in Supabase using the provided schema:

```sql
CREATE TABLE agent_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    task_id UUID,
    feedback_type VARCHAR(50) NOT NULL, -- 'classification', 'generation', 'retrieval'
    input_summary TEXT,
    output_summary TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

CREATE INDEX idx_agent_feedback_agent ON agent_feedback(agent_id);
CREATE INDEX idx_agent_feedback_type ON agent_feedback(feedback_type);
CREATE INDEX idx_agent_feedback_created ON agent_feedback(created_at DESC);
```

2. Implement feedback storage in app/services/classification_service.py:

```python
from app.db.supabase import get_supabase_client
from app.core.tracing import traced
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ClassificationService:
    def __init__(self, db_client=None):
        self.db = db_client or get_supabase_client()
        self.agent_id = "classification_agent_v1"
    
    @traced("classify_document")
    def classify_document(self, document_text, metadata=None):
        """Classify a document based on its content"""
        # Existing classification logic...
        
        # Return classification result
        return classification_result
    
    @traced("store_feedback")
    def store_feedback(self, task_id, input_summary, output_summary, rating, feedback_text, user_id, metadata=None):
        """Store feedback for classification"""
        try:
            # Create feedback record
            feedback = {
                "agent_id": self.agent_id,
                "task_id": task_id,
                "feedback_type": "classification",
                "input_summary": input_summary,
                "output_summary": output_summary,
                "rating": rating,
                "feedback_text": feedback_text,
                "metadata": metadata or {},
                "created_by": user_id
            }
            
            # Insert into agent_feedback table
            result = self.db.table("agent_feedback").insert(feedback).execute()
            
            if not result.data:
                raise Exception("Failed to store feedback")
                
            feedback_id = result.data[0]["id"]
            logger.info(f"Stored classification feedback {feedback_id} for task {task_id}")
            
            return {"id": feedback_id}
        except Exception as e:
            logger.error(f"Failed to store classification feedback: {str(e)}")
            raise
```

3. Implement feedback storage in app/services/asset_management_service.py:

```python
from app.db.supabase import get_supabase_client
from app.core.tracing import traced
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AssetManagementService:
    def __init__(self, db_client=None):
        self.db = db_client or get_supabase_client()
        self.agent_id = "asset_management_agent_v1"
    
    @traced("generate_asset")
    def generate_asset(self, asset_type, parameters, user_id):
        """Generate an asset based on parameters"""
        # Existing asset generation logic...
        
        # Return generated asset
        return asset_result
    
    @traced("store_feedback")
    def store_feedback(self, task_id, input_summary, output_summary, rating, feedback_text, user_id, metadata=None):
        """Store feedback for asset generation"""
        try:
            # Create feedback record
            feedback = {
                "agent_id": self.agent_id,
                "task_id": task_id,
                "feedback_type": "generation",
                "input_summary": input_summary,
                "output_summary": output_summary,
                "rating": rating,
                "feedback_text": feedback_text,
                "metadata": metadata or {},
                "created_by": user_id
            }
            
            # Insert into agent_feedback table
            result = self.db.table("agent_feedback").insert(feedback).execute()
            
            if not result.data:
                raise Exception("Failed to store feedback")
                
            feedback_id = result.data[0]["id"]
            logger.info(f"Stored asset generation feedback {feedback_id} for task {task_id}")
            
            return {"id": feedback_id}
        except Exception as e:
            logger.error(f"Failed to store asset generation feedback: {str(e)}")
            raise
```

4. Create a generic FeedbackService for reuse across different agents:

```python
# app/services/feedback_service.py
from app.db.supabase import get_supabase_client
from app.core.tracing import traced
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FeedbackService:
    def __init__(self, db_client=None):
        self.db = db_client or get_supabase_client()
    
    @traced("store_feedback")
    def store_feedback(self, agent_id, feedback_type, task_id, input_summary, output_summary, 
                      rating, feedback_text, user_id, metadata=None):
        """Store feedback for any agent"""
        try:
            # Validate inputs
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5")
                
            if not agent_id or not feedback_type:
                raise ValueError("Agent ID and feedback type are required")
            
            # Create feedback record
            feedback = {
                "agent_id": agent_id,
                "task_id": task_id,
                "feedback_type": feedback_type,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "rating": rating,
                "feedback_text": feedback_text,
                "metadata": metadata or {},
                "created_by": user_id
            }
            
            # Insert into agent_feedback table
            result = self.db.table("agent_feedback").insert(feedback).execute()
            
            if not result.data:
                raise Exception("Failed to store feedback")
                
            feedback_id = result.data[0]["id"]
            logger.info(f"Stored {feedback_type} feedback {feedback_id} for agent {agent_id}")
            
            return {"id": feedback_id}
        except Exception as e:
            logger.error(f"Failed to store feedback: {str(e)}")
            raise
    
    @traced("get_agent_feedback")
    def get_agent_feedback(self, agent_id=None, feedback_type=None, limit=100, offset=0):
        """Get feedback for agents with optional filtering"""
        try:
            query = self.db.table("agent_feedback").select("*").order("created_at", desc=True)
            
            if agent_id:
                query = query.eq("agent_id", agent_id)
                
            if feedback_type:
                query = query.eq("feedback_type", feedback_type)
                
            result = query.range(offset, offset + limit - 1).execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Failed to get agent feedback: {str(e)}")
            raise
    
    @traced("get_feedback_stats")
    def get_feedback_stats(self, agent_id=None, feedback_type=None, days=30):
        """Get feedback statistics"""
        try:
            # Use SQL function to get statistics
            result = self.db.rpc(
                "get_feedback_stats",
                {
                    "p_agent_id": agent_id,
                    "p_feedback_type": feedback_type,
                    "p_days": days
                }
            ).execute()
            
            return result.data
        except Exception as e:
            logger.error(f"Failed to get feedback stats: {str(e)}")
            raise
```

5. Create a SQL function for feedback statistics:

```sql
CREATE OR REPLACE FUNCTION get_feedback_stats(
    p_agent_id VARCHAR DEFAULT NULL,
    p_feedback_type VARCHAR DEFAULT NULL,
    p_days INTEGER DEFAULT 30
) RETURNS TABLE (
    agent_id VARCHAR,
    feedback_type VARCHAR,
    total_count INTEGER,
    avg_rating NUMERIC(3,2),
    rating_distribution JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH feedback_filtered AS (
        SELECT *
        FROM agent_feedback
        WHERE (p_agent_id IS NULL OR agent_id = p_agent_id)
        AND (p_feedback_type IS NULL OR feedback_type = p_feedback_type)
        AND created_at >= NOW() - (p_days || ' days')::INTERVAL
    ),
    rating_counts AS (
        SELECT 
            agent_id,
            feedback_type,
            rating,
            COUNT(*) as count
        FROM feedback_filtered
        GROUP BY agent_id, feedback_type, rating
    )
    SELECT 
        f.agent_id,
        f.feedback_type,
        COUNT(*) as total_count,
        AVG(f.rating)::NUMERIC(3,2) as avg_rating,
        jsonb_object_agg(
            r.rating::TEXT, 
            r.count
        ) as rating_distribution
    FROM feedback_filtered f
    LEFT JOIN rating_counts r ON 
        f.agent_id = r.agent_id AND 
        f.feedback_type = r.feedback_type AND
        f.rating = r.rating
    GROUP BY f.agent_id, f.feedback_type;
    
END;
$$ LANGUAGE plpgsql;
```

6. Create API endpoints for feedback:

```python
# app/routes/feedback.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any
from app.core.auth import get_current_user
from app.models.user import User
from app.services.feedback_service import FeedbackService
from pydantic import BaseModel, Field

router = APIRouter()

class FeedbackRequest(BaseModel):
    agent_id: str = Field(..., description="ID of the agent receiving feedback")
    feedback_type: str = Field(..., description="Type of feedback (classification, generation, retrieval)")
    task_id: Optional[str] = Field(None, description="ID of the task if applicable")
    input_summary: str = Field(..., description="Summary of the input to the agent")
    output_summary: str = Field(..., description="Summary of the output from the agent")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5")
    feedback_text: str = Field(..., description="Detailed feedback text")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackRequest,
    current_user: User = Depends(get_current_user)
):
    """Submit feedback for an agent"""
    try:
        service = FeedbackService()
        result = service.store_feedback(
            agent_id=feedback.agent_id,
            feedback_type=feedback.feedback_type,
            task_id=feedback.task_id,
            input_summary=feedback.input_summary,
            output_summary=feedback.output_summary,
            rating=feedback.rating,
            feedback_text=feedback.feedback_text,
            user_id=current_user.id,
            metadata=feedback.metadata
        )
        
        return {
            "success": True,
            "feedback_id": result["id"],
            "message": "Feedback submitted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )

@router.get("/feedback")
async def get_feedback(
    agent_id: Optional[str] = Query(None),
    feedback_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """Get feedback with optional filtering"""
    try:
        # Only admins can view all feedback
        if not current_user.is_admin and (not agent_id or not feedback_type):
            raise HTTPException(
                status_code=403,
                detail="Non-admin users must specify both agent_id and feedback_type"
            )
        
        service = FeedbackService()
        feedback_items = service.get_agent_feedback(
            agent_id=agent_id,
            feedback_type=feedback_type,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "feedback": feedback_items,
            "count": len(feedback_items),
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get feedback: {str(e)}"
        )

@router.get("/feedback/stats")
async def get_feedback_stats(
    agent_id: Optional[str] = Query(None),
    feedback_type: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user)
):
    """Get feedback statistics"""
    try:
        service = FeedbackService()
        stats = service.get_feedback_stats(
            agent_id=agent_id,
            feedback_type=feedback_type,
            days=days
        )
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get feedback stats: {str(e)}"
        )
```

**Test Strategy:**

1. Unit tests for feedback storage in each service
   - Test FeedbackService methods
   - Test service-specific feedback methods
2. Integration tests with database
   - Test table creation and constraints
   - Test SQL function for statistics
3. API endpoint tests
   - Test feedback submission
   - Test feedback retrieval with filtering
   - Test statistics endpoint
4. Test cases:
   - Submit feedback with valid data
   - Submit feedback with invalid ratings
   - Get feedback with different filters
   - Get statistics for different time periods
5. Authorization tests:
   - Test admin vs non-admin access
   - Test user-specific feedback access
