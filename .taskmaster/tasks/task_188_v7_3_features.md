# Task ID: 188

**Title:** Implement Agent Feedback System

**Status:** done

**Dependencies:** None

**Priority:** medium

**Description:** Implement the agent feedback system by creating the agent_feedback table in Supabase and implementing feedback storage functionality.

**Details:**

In `app/services/classification_service.py` and `app/services/asset_management_service.py`, implement the following TODOs:

1. First, ensure the agent_feedback table is created in Supabase using the schema provided in the PRD:

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

2. Implement feedback storage in `app/services/classification_service.py`:

```python
def store_classification_feedback(self, classification_id, rating, feedback_text=None, user_id=None):
    """Store feedback for a classification result."""
    # Get the classification record
    classification = self.db.get("classifications", classification_id)
    if not classification:
        raise ValueError(f"Classification {classification_id} not found")
    
    # Create feedback record
    feedback = {
        "agent_id": "classification_agent",
        "task_id": classification.get("task_id"),
        "feedback_type": "classification",
        "input_summary": classification.get("input_text", "")[:500],  # First 500 chars
        "output_summary": json.dumps(classification.get("result", {}))[:500],
        "rating": rating,
        "feedback_text": feedback_text,
        "metadata": {
            "classification_id": classification_id,
            "categories": classification.get("result", {}).get("categories", []),
            "confidence": classification.get("result", {}).get("confidence")
        },
        "created_by": user_id
    }
    
    # Insert feedback
    feedback_id = self.db.insert("agent_feedback", feedback).get("id")
    
    # Update classification record with feedback reference
    self.db.update("classifications", classification_id, {
        "has_feedback": True,
        "feedback_id": feedback_id,
        "feedback_rating": rating
    })
    
    return {"success": True, "feedback_id": feedback_id}
```

3. Implement feedback storage in `app/services/asset_management_service.py`:

```python
def store_asset_feedback(self, asset_id, rating, feedback_text=None, user_id=None):
    """Store feedback for a generated asset."""
    # Get the asset record
    asset = self.db.get("assets", asset_id)
    if not asset:
        raise ValueError(f"Asset {asset_id} not found")
    
    # Determine agent ID based on asset type
    agent_map = {
        "image": "image_generation_agent",
        "text": "text_generation_agent",
        "code": "code_generation_agent",
        "chart": "chart_generation_agent"
    }
    
    agent_id = agent_map.get(asset.get("asset_type"), "unknown_agent")
    
    # Create feedback record
    feedback = {
        "agent_id": agent_id,
        "task_id": asset.get("task_id"),
        "feedback_type": "generation",
        "input_summary": asset.get("prompt", "")[:500],  # First 500 chars
        "output_summary": asset.get("description", "")[:500],
        "rating": rating,
        "feedback_text": feedback_text,
        "metadata": {
            "asset_id": asset_id,
            "asset_type": asset.get("asset_type"),
            "generation_params": asset.get("generation_params", {})
        },
        "created_by": user_id
    }
    
    # Insert feedback
    feedback_id = self.db.insert("agent_feedback", feedback).get("id")
    
    # Update asset record with feedback reference
    self.db.update("assets", asset_id, {
        "has_feedback": True,
        "feedback_id": feedback_id,
        "feedback_rating": rating
    })
    
    return {"success": True, "feedback_id": feedback_id}
```

4. Create a new `app/services/feedback_service.py` to centralize feedback functionality:

```python
from datetime import datetime
import json
from app.db.database import Database

class FeedbackService:
    """Service for managing agent feedback."""
    
    def __init__(self):
        self.db = Database()
    
    def store_feedback(self, agent_id, feedback_type, input_summary, output_summary, 
                      rating, feedback_text=None, task_id=None, metadata=None, user_id=None):
        """Store feedback for any agent."""
        # Validate rating
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            raise ValueError("Rating must be an integer between 1 and 5")
        
        # Create feedback record
        feedback = {
            "agent_id": agent_id,
            "task_id": task_id,
            "feedback_type": feedback_type,
            "input_summary": input_summary[:500] if input_summary else None,
            "output_summary": output_summary[:500] if output_summary else None,
            "rating": rating,
            "feedback_text": feedback_text,
            "metadata": metadata or {},
            "created_by": user_id,
            "created_at": datetime.now().isoformat()
        }
        
        # Insert feedback
        result = self.db.insert("agent_feedback", feedback)
        feedback_id = result.get("id")
        
        return {"success": True, "feedback_id": feedback_id}
    
    def get_feedback(self, feedback_id):
        """Get feedback by ID."""
        return self.db.get("agent_feedback", feedback_id)
    
    def get_agent_feedback(self, agent_id, limit=100, offset=0):
        """Get feedback for a specific agent."""
        return self.db.query(
            "agent_feedback",
            {"agent_id": agent_id},
            limit=limit,
            offset=offset,
            order_by="created_at",
            order_direction="desc"
        )
    
    def get_feedback_stats(self, agent_id=None, feedback_type=None):
        """Get feedback statistics."""
        query = {}
        if agent_id:
            query["agent_id"] = agent_id
        if feedback_type:
            query["feedback_type"] = feedback_type
        
        # Get all matching feedback
        feedback = self.db.query("agent_feedback", query)
        
        if not feedback:
            return {
                "count": 0,
                "average_rating": 0,
                "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
            }
        
        # Calculate statistics
        total_rating = sum(f.get("rating", 0) for f in feedback)
        avg_rating = total_rating / len(feedback) if feedback else 0
        
        # Calculate rating distribution
        distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for f in feedback:
            rating = f.get("rating")
            if rating and 1 <= rating <= 5:
                distribution[str(rating)] += 1
        
        return {
            "count": len(feedback),
            "average_rating": round(avg_rating, 2),
            "rating_distribution": distribution
        }
```

**Test Strategy:**

1. Unit tests:
   - Test feedback storage for classification service
   - Test feedback storage for asset management service
   - Test central feedback service methods
   - Test validation of rating values

2. Integration tests:
   - Test feedback storage with actual Supabase database
   - Test feedback retrieval and statistics calculation
   - Test feedback lifecycle with various agent types

3. Database tests:
   - Verify agent_feedback table schema
   - Test index performance for common queries
   - Test constraints (e.g., rating range check)
