# Task ID: 123

**Title:** Create Content Sets Database Schema

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Create the database schema for content sets and content set files in Supabase as specified in the PRD.

**Details:**

Create the migration file `migrations/create_content_sets.sql` with the SQL schema for the content_sets and content_set_files tables. This will store metadata about detected content sets and their files.

The schema should include:
1. content_sets table with fields for id, name, detection method, completeness, etc.
2. content_set_files table with fields for file metadata and sequence information
3. Appropriate indexes for efficient querying
4. Foreign key relationships

SQL Schema:
```sql
CREATE TABLE content_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    detection_method VARCHAR(50) NOT NULL,
    is_complete BOOLEAN DEFAULT FALSE,
    missing_files JSONB DEFAULT '[]',
    file_count INTEGER NOT NULL,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE content_set_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_set_id UUID REFERENCES content_sets(id) ON DELETE CASCADE,
    b2_path VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sequence_number INTEGER,
    dependencies JSONB DEFAULT '[]',
    estimated_complexity VARCHAR(20),
    file_type VARCHAR(50),
    size_bytes BIGINT,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_content_sets_status ON content_sets(processing_status);
CREATE INDEX idx_content_set_files_set ON content_set_files(content_set_id);
CREATE INDEX idx_content_set_files_sequence ON content_set_files(content_set_id, sequence_number);

-- Index for retention policy
CREATE INDEX idx_content_sets_updated ON content_sets(updated_at);
```

Also create a Pydantic model file `app/models/content_sets.py` to define the data models for the API:

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import uuid

class ContentFileBase(BaseModel):
    b2_path: str
    filename: str
    sequence_number: Optional[int] = None
    dependencies: List[str] = Field(default_factory=list)
    estimated_complexity: str = "medium"
    file_type: str = ""
    size_bytes: int = 0
    metadata: Dict = Field(default_factory=dict)

class ContentFile(ContentFileBase):
    id: uuid.UUID
    content_set_id: uuid.UUID
    processing_status: str = "pending"
    created_at: datetime

class ContentFileCreate(ContentFileBase):
    content_set_id: uuid.UUID

class ContentSetBase(BaseModel):
    name: str
    detection_method: str
    is_complete: bool = False
    missing_files: List[str] = Field(default_factory=list)
    file_count: int
    metadata: Dict = Field(default_factory=dict)

class ContentSet(ContentSetBase):
    id: uuid.UUID
    processing_status: str = "pending"
    created_at: datetime
    updated_at: datetime

class ContentSetCreate(ContentSetBase):
    pass

class ProcessingManifest(BaseModel):
    content_set_id: uuid.UUID
    ordered_files: List[ContentFile]
    total_files: int
    estimated_processing_time: int
    warnings: List[str] = Field(default_factory=list)
    context: Dict = Field(default_factory=dict)
```

**Test Strategy:**

1. Verify SQL schema with test database
2. Test foreign key constraints
3. Test index performance with large datasets
4. Validate Pydantic models with sample data
5. Test serialization/deserialization of JSON fields
6. Ensure UUID generation works correctly
