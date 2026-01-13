# Architecture Specification: Content Prep Agent (AGENT-016)

**Feature**: 007-content-prep-agent
**Date**: 2026-01-13
**Related PRD**: [prd.md](./prd.md)

---

## System Context

### Current Pipeline (Before)

```
B2 pending/ → Celery Task → Document Processor → Chunking → Embedding → Supabase
                  ↓
            Files processed in arbitrary order (alphabetical/upload time)
```

### Enhanced Pipeline (After)

```
B2 pending/ → AGENT-016 → Processing Manifest → Celery Task → Document Processor → ...
                  ↓
            Files processed in logical/chronological order with set context
```

---

## Component Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Content Prep Agent System                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   API Layer     │    │  Agent Layer    │    │  Storage Layer  │         │
│  │                 │    │                 │    │                 │         │
│  │ /content-prep/* │───▶│   AGENT-016     │───▶│  Supabase       │         │
│  │ FastAPI Routes  │    │   CrewAI Agent  │    │  content_sets   │         │
│  └────────┬────────┘    └────────┬────────┘    └─────────────────┘         │
│           │                      │                                          │
│           │                      ▼                                          │
│           │             ┌─────────────────┐    ┌─────────────────┐         │
│           │             │  Task Layer     │    │  External       │         │
│           │             │                 │    │                 │         │
│           └────────────▶│  Celery Tasks   │───▶│  B2 Storage     │         │
│                         │  content_prep_* │    │  Neo4j Graph    │         │
│                         └─────────────────┘    └─────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. API Layer (`app/routes/content_prep.py`)

```python
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.services.content_prep_agent import ContentPrepAgent
from app.models.content_sets import (
    AnalyzeRequest,
    AnalyzeResponse,
    ManifestRequest,
    ManifestResponse,
    ContentSetResponse
)

router = APIRouter(prefix="/api/content-prep", tags=["content-prep"])

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_pending_files(request: AnalyzeRequest):
    """Analyze pending files and detect content sets."""
    agent = ContentPrepAgent()
    return await agent.analyze_folder(
        b2_folder=request.b2_folder,
        detection_mode=request.detection_mode
    )

@router.post("/validate/{set_id}")
async def validate_content_set(set_id: str):
    """Validate completeness of a content set."""
    agent = ContentPrepAgent()
    return await agent.validate_completeness(set_id)

@router.post("/manifest", response_model=ManifestResponse)
async def generate_manifest(request: ManifestRequest):
    """Generate processing manifest for content set."""
    agent = ContentPrepAgent()
    return await agent.generate_manifest(
        content_set_id=request.content_set_id,
        proceed_incomplete=request.proceed_incomplete
    )

@router.get("/sets", response_model=list[ContentSetResponse])
async def list_content_sets(status: str = None):
    """List all detected content sets."""
    agent = ContentPrepAgent()
    return await agent.list_sets(status=status)

@router.get("/sets/{set_id}", response_model=ContentSetResponse)
async def get_content_set(set_id: str):
    """Get details of a specific content set."""
    agent = ContentPrepAgent()
    return await agent.get_set(set_id)

@router.get("/health")
async def health_check():
    """Service health check."""
    return {"status": "healthy", "agent": "AGENT-016"}
```

#### 2. Agent Layer (`app/services/content_prep_agent.py`)

```python
"""
AGENT-016: Content Prep Agent
Validates, orders, and prepares content for knowledge base ingestion.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

import structlog
from crewai import Agent, Task, Crew

from app.services.b2_service import B2Service
from app.services.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)

# Sequence detection patterns
SEQUENCE_PATTERNS = [
    (r"^(\d{1,3})[-_\s]", "numeric_prefix"),
    (r"[-_\s](\d{1,3})[-_\s.]", "numeric_infix"),
    (r"module[-_\s]?(\d{1,3})", "module"),
    (r"chapter[-_\s]?(\d{1,3})", "chapter"),
    (r"lesson[-_\s]?(\d{1,3})", "lesson"),
    (r"part[-_\s]?(\d{1,3})", "part"),
    (r"week[-_\s]?(\d{1,3})", "week"),
    (r"unit[-_\s]?(\d{1,3})", "unit"),
    (r"section[-_\s]?(\d{1,3})", "section"),
]

CONTENT_SET_INDICATORS = [
    "course", "tutorial", "training", "documentation",
    "manual", "series", "book", "guide", "curriculum"
]


@dataclass
class ContentFile:
    """Represents a file within a content set."""
    b2_path: str
    filename: str
    sequence_number: Optional[int] = None
    detection_pattern: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    estimated_complexity: str = "medium"
    file_type: str = ""
    size_bytes: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ContentSet:
    """Represents a group of related files."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    detection_method: str = "pattern"
    files: list[ContentFile] = field(default_factory=list)
    is_complete: bool = True
    missing_files: list[str] = field(default_factory=list)
    processing_status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)


class ContentPrepAgent:
    """
    AGENT-016: Content Preparation Specialist

    Responsibilities:
    1. Detect content sets from file naming patterns
    2. Validate completeness (gap detection)
    3. Order files chronologically/logically
    4. Generate processing manifests
    """

    def __init__(self):
        self.b2_service = B2Service()
        self.supabase = get_supabase_client()
        self.logger = logger.bind(agent="AGENT-016")

        # CrewAI agent for LLM-assisted ordering
        self.crew_agent = Agent(
            role="Content Preparation Specialist",
            goal="Validate, order, and prepare content sets for optimal knowledge base ingestion",
            backstory="""You are an expert in content organization and curriculum design.
            You understand that learning materials must be processed in logical sequence
            to maintain prerequisite relationships. You detect patterns in file naming,
            identify content sets, and ensure completeness before processing begins.""",
            llm="claude-3-5-haiku-20241022",
            verbose=True,
            allow_delegation=False
        )

    async def analyze_folder(
        self,
        b2_folder: str,
        detection_mode: str = "auto"
    ) -> dict:
        """
        Analyze files in B2 folder and detect content sets.

        Args:
            b2_folder: B2 folder path to analyze
            detection_mode: "auto", "pattern", "metadata", or "llm"

        Returns:
            Dict with content_sets and standalone_files
        """
        self.logger.info("analyzing_folder", folder=b2_folder, mode=detection_mode)

        # List files in folder
        files = await self.b2_service.list_files(b2_folder)

        if not files:
            return {"content_sets": [], "standalone_files": []}

        # Detect content sets
        content_sets = []
        standalone = []

        if detection_mode in ("auto", "pattern"):
            sets, remaining = self._detect_by_pattern(files)
            content_sets.extend(sets)
            files = remaining

        if detection_mode in ("auto", "llm") and files:
            # Use LLM for ambiguous files
            llm_sets = await self._detect_by_llm(files)
            content_sets.extend(llm_sets)
            # Remaining files after LLM detection
            grouped_files = {f.b2_path for s in llm_sets for f in s.files}
            standalone = [f for f in files if f["path"] not in grouped_files]
        else:
            standalone = files

        # Store detected sets in database
        for content_set in content_sets:
            await self._store_content_set(content_set)

        return {
            "content_sets": [self._serialize_set(s) for s in content_sets],
            "standalone_files": standalone
        }

    def _detect_by_pattern(
        self,
        files: list[dict]
    ) -> tuple[list[ContentSet], list[dict]]:
        """
        Detect content sets using naming patterns.

        Returns:
            Tuple of (detected_sets, remaining_files)
        """
        # Group files by prefix (common naming pattern)
        prefix_groups = {}

        for file_info in files:
            filename = file_info["filename"]

            # Try to extract common prefix
            prefix = self._extract_prefix(filename)
            if prefix:
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []
                prefix_groups[prefix].append(file_info)

        content_sets = []
        grouped_files = set()

        for prefix, group_files in prefix_groups.items():
            if len(group_files) >= 2:  # At least 2 files to form a set
                content_set = self._create_content_set(prefix, group_files)
                if content_set:
                    content_sets.append(content_set)
                    grouped_files.update(f["path"] for f in group_files)

        remaining = [f for f in files if f["path"] not in grouped_files]
        return content_sets, remaining

    def _extract_prefix(self, filename: str) -> Optional[str]:
        """Extract common prefix from filename for grouping."""
        # Remove extension
        name = filename.rsplit(".", 1)[0]

        # Try to find sequence pattern and extract prefix
        for pattern, _ in SEQUENCE_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                # Get everything before the sequence number
                prefix = name[:match.start()].strip("-_ ")
                if prefix and len(prefix) >= 3:
                    return prefix.lower()

        # Check for content set indicators
        for indicator in CONTENT_SET_INDICATORS:
            if indicator in name.lower():
                # Extract the indicator and surrounding context
                idx = name.lower().find(indicator)
                return name[:idx + len(indicator)].strip("-_ ").lower()

        return None

    def _create_content_set(
        self,
        prefix: str,
        files: list[dict]
    ) -> Optional[ContentSet]:
        """Create a ContentSet from grouped files."""
        content_files = []
        sequences_found = []

        for file_info in files:
            filename = file_info["filename"]
            sequence, pattern = self._extract_sequence(filename)

            content_file = ContentFile(
                b2_path=file_info["path"],
                filename=filename,
                sequence_number=sequence,
                detection_pattern=pattern,
                file_type=filename.rsplit(".", 1)[-1] if "." in filename else "",
                size_bytes=file_info.get("size", 0)
            )
            content_files.append(content_file)

            if sequence is not None:
                sequences_found.append(sequence)

        # Sort by sequence number
        content_files.sort(key=lambda f: (f.sequence_number or 999, f.filename))

        # Detect gaps
        missing = []
        if sequences_found:
            sequences_found.sort()
            expected = list(range(sequences_found[0], sequences_found[-1] + 1))
            missing = [f"#{n}" for n in expected if n not in sequences_found]

        # Calculate confidence
        confidence = len([f for f in content_files if f.sequence_number]) / len(content_files)

        content_set = ContentSet(
            name=self._generate_set_name(prefix, content_files),
            detection_method="pattern",
            files=content_files,
            is_complete=len(missing) == 0,
            missing_files=missing,
            confidence=confidence
        )

        return content_set if confidence >= 0.5 else None

    def _extract_sequence(self, filename: str) -> tuple[Optional[int], Optional[str]]:
        """Extract sequence number from filename."""
        name = filename.rsplit(".", 1)[0]

        for pattern, pattern_name in SEQUENCE_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1)), pattern_name
                except (ValueError, IndexError):
                    continue

        return None, None

    def _generate_set_name(self, prefix: str, files: list[ContentFile]) -> str:
        """Generate a human-readable name for the content set."""
        # Capitalize and clean up prefix
        name = prefix.replace("-", " ").replace("_", " ").title()

        # Add context
        file_types = set(f.file_type.upper() for f in files if f.file_type)
        if file_types:
            name += f" ({', '.join(sorted(file_types))})"

        return name

    async def _detect_by_llm(self, files: list[dict]) -> list[ContentSet]:
        """Use LLM to detect content sets from ambiguous files."""
        if not files:
            return []

        # Create task for CrewAI agent
        file_list = "\n".join([f"- {f['filename']}" for f in files[:50]])  # Limit for context

        task = Task(
            description=f"""Analyze these files and identify any content sets (groups of related files
            that should be processed together in a specific order):

            Files:
            {file_list}

            For each content set found, provide:
            1. A name for the set
            2. The files belonging to it
            3. The recommended processing order
            4. Any missing files you detect (gaps in sequence)

            If files are standalone (not part of a set), list them separately.
            """,
            expected_output="JSON with content_sets array and standalone_files array",
            agent=self.crew_agent
        )

        crew = Crew(agents=[self.crew_agent], tasks=[task], verbose=True)
        result = crew.kickoff()

        # Parse LLM response and create ContentSets
        # This would need proper JSON parsing of the LLM output
        return []  # Placeholder

    async def validate_completeness(self, set_id: str) -> dict:
        """Validate that a content set is complete."""
        content_set = await self._load_content_set(set_id)
        if not content_set:
            raise ValueError(f"Content set {set_id} not found")

        # Re-analyze for gaps
        sequences = [f.sequence_number for f in content_set.files if f.sequence_number]
        if sequences:
            sequences.sort()
            expected = list(range(sequences[0], sequences[-1] + 1))
            missing = [n for n in expected if n not in sequences]
            content_set.missing_files = [f"#{n}" for n in missing]
            content_set.is_complete = len(missing) == 0

        return {
            "set_id": set_id,
            "is_complete": content_set.is_complete,
            "missing_files": content_set.missing_files,
            "total_files": len(content_set.files)
        }

    async def generate_manifest(
        self,
        content_set_id: str,
        proceed_incomplete: bool = False
    ) -> dict:
        """Generate processing manifest for a content set."""
        content_set = await self._load_content_set(content_set_id)
        if not content_set:
            raise ValueError(f"Content set {content_set_id} not found")

        if not content_set.is_complete and not proceed_incomplete:
            raise ValueError(
                f"Content set is incomplete. Missing: {content_set.missing_files}. "
                "Set proceed_incomplete=true to process anyway."
            )

        # Build ordered file list with dependencies
        ordered_files = []
        for i, file in enumerate(content_set.files):
            dependencies = []
            if i > 0:
                # Each file depends on the previous one
                dependencies.append(content_set.files[i-1].filename)

            ordered_files.append({
                "sequence": i + 1,
                "file": file.filename,
                "b2_path": file.b2_path,
                "dependencies": dependencies,
                "complexity": file.estimated_complexity
            })

        # Estimate processing time (rough: 30s per file)
        estimated_time = len(ordered_files) * 30

        manifest = {
            "manifest_id": str(uuid4()),
            "content_set_id": content_set_id,
            "content_set_name": content_set.name,
            "ordered_files": ordered_files,
            "total_files": len(ordered_files),
            "warnings": content_set.missing_files if not content_set.is_complete else [],
            "estimated_time_seconds": estimated_time,
            "created_at": datetime.utcnow().isoformat(),
            "context": {
                "set_name": content_set.name,
                "is_sequential": True,
                "detection_method": content_set.detection_method
            }
        }

        # Store manifest
        await self._store_manifest(manifest)

        return manifest

    async def list_sets(self, status: str = None) -> list[dict]:
        """List all content sets, optionally filtered by status."""
        query = self.supabase.table("content_sets").select("*")
        if status:
            query = query.eq("processing_status", status)

        result = query.execute()
        return result.data if result.data else []

    async def get_set(self, set_id: str) -> dict:
        """Get details of a specific content set."""
        content_set = await self._load_content_set(set_id)
        if not content_set:
            raise ValueError(f"Content set {set_id} not found")
        return self._serialize_set(content_set)

    async def _store_content_set(self, content_set: ContentSet):
        """Store content set in database."""
        # Insert content set
        set_data = {
            "id": content_set.id,
            "name": content_set.name,
            "detection_method": content_set.detection_method,
            "is_complete": content_set.is_complete,
            "missing_files": content_set.missing_files,
            "file_count": len(content_set.files),
            "processing_status": content_set.processing_status,
            "metadata": {
                "confidence": content_set.confidence,
                **content_set.metadata
            }
        }
        self.supabase.table("content_sets").upsert(set_data).execute()

        # Insert files
        for file in content_set.files:
            file_data = {
                "content_set_id": content_set.id,
                "b2_path": file.b2_path,
                "filename": file.filename,
                "sequence_number": file.sequence_number,
                "dependencies": file.dependencies,
                "estimated_complexity": file.estimated_complexity,
                "file_type": file.file_type,
                "size_bytes": file.size_bytes,
                "metadata": file.metadata
            }
            self.supabase.table("content_set_files").upsert(file_data).execute()

    async def _load_content_set(self, set_id: str) -> Optional[ContentSet]:
        """Load content set from database."""
        result = self.supabase.table("content_sets").select("*").eq("id", set_id).execute()
        if not result.data:
            return None

        set_data = result.data[0]

        # Load files
        files_result = self.supabase.table("content_set_files")\
            .select("*")\
            .eq("content_set_id", set_id)\
            .order("sequence_number")\
            .execute()

        files = [
            ContentFile(
                b2_path=f["b2_path"],
                filename=f["filename"],
                sequence_number=f["sequence_number"],
                dependencies=f.get("dependencies", []),
                estimated_complexity=f.get("estimated_complexity", "medium"),
                file_type=f.get("file_type", ""),
                size_bytes=f.get("size_bytes", 0),
                metadata=f.get("metadata", {})
            )
            for f in (files_result.data or [])
        ]

        return ContentSet(
            id=set_data["id"],
            name=set_data["name"],
            detection_method=set_data["detection_method"],
            files=files,
            is_complete=set_data["is_complete"],
            missing_files=set_data.get("missing_files", []),
            processing_status=set_data["processing_status"],
            confidence=set_data.get("metadata", {}).get("confidence", 0),
            metadata=set_data.get("metadata", {})
        )

    async def _store_manifest(self, manifest: dict):
        """Store processing manifest."""
        self.supabase.table("processing_manifests").insert(manifest).execute()

    def _serialize_set(self, content_set: ContentSet) -> dict:
        """Serialize ContentSet for API response."""
        return {
            "id": content_set.id,
            "name": content_set.name,
            "detection_method": content_set.detection_method,
            "files_count": len(content_set.files),
            "files": [
                {
                    "filename": f.filename,
                    "sequence": f.sequence_number,
                    "b2_path": f.b2_path
                }
                for f in content_set.files
            ],
            "is_complete": content_set.is_complete,
            "missing_files": content_set.missing_files,
            "processing_status": content_set.processing_status,
            "confidence": content_set.confidence
        }
```

#### 3. Celery Tasks (`app/tasks/content_prep_tasks.py`)

```python
"""Celery tasks for content preparation."""

from celery import shared_task
from app.services.content_prep_agent import ContentPrepAgent
import structlog

logger = structlog.get_logger(__name__)


@shared_task(
    name="content_prep.analyze_folder",
    queue="content_prep",
    bind=True,
    max_retries=3
)
def analyze_folder_task(self, b2_folder: str, detection_mode: str = "auto"):
    """
    Async task to analyze B2 folder for content sets.
    """
    try:
        agent = ContentPrepAgent()
        import asyncio
        result = asyncio.run(agent.analyze_folder(b2_folder, detection_mode))
        return result
    except Exception as e:
        logger.error("analyze_folder_failed", error=str(e), folder=b2_folder)
        raise self.retry(exc=e, countdown=60)


@shared_task(
    name="content_prep.process_manifest",
    queue="content_prep",
    bind=True
)
def process_manifest_task(self, manifest_id: str):
    """
    Process files according to manifest order.
    Triggers source processing tasks in sequence.
    """
    from app.tasks.source_processing import process_source

    try:
        agent = ContentPrepAgent()
        # Load manifest
        manifest = agent.supabase.table("processing_manifests")\
            .select("*").eq("manifest_id", manifest_id).execute()

        if not manifest.data:
            raise ValueError(f"Manifest {manifest_id} not found")

        manifest_data = manifest.data[0]

        # Process files in order
        for file_info in manifest_data["ordered_files"]:
            logger.info(
                "processing_file",
                file=file_info["file"],
                sequence=file_info["sequence"]
            )

            # Trigger source processing with manifest context
            process_source.delay(
                b2_path=file_info["b2_path"],
                context={
                    "content_set": manifest_data["content_set_name"],
                    "sequence": file_info["sequence"],
                    "total_files": manifest_data["total_files"],
                    "is_sequential": True
                }
            )

        return {"status": "processing", "files_queued": len(manifest_data["ordered_files"])}

    except Exception as e:
        logger.error("process_manifest_failed", error=str(e), manifest_id=manifest_id)
        raise
```

#### 4. Pydantic Models (`app/models/content_sets.py`)

```python
"""Pydantic models for Content Prep Agent."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request to analyze pending files."""
    b2_folder: str = Field(..., description="B2 folder path to analyze")
    detection_mode: str = Field(
        default="auto",
        description="Detection mode: auto, pattern, metadata, llm"
    )


class ContentFileResponse(BaseModel):
    """Response model for a single file."""
    filename: str
    sequence: Optional[int]
    b2_path: str


class ContentSetResponse(BaseModel):
    """Response model for a content set."""
    id: str
    name: str
    detection_method: str
    files_count: int
    files: list[ContentFileResponse]
    is_complete: bool
    missing_files: list[str]
    processing_status: str
    confidence: float


class AnalyzeResponse(BaseModel):
    """Response from folder analysis."""
    content_sets: list[ContentSetResponse]
    standalone_files: list[dict]


class ManifestRequest(BaseModel):
    """Request to generate processing manifest."""
    content_set_id: str
    proceed_incomplete: bool = Field(
        default=False,
        description="Process even if content set is incomplete"
    )
    add_context: bool = Field(
        default=True,
        description="Include set context in processing"
    )


class OrderedFileResponse(BaseModel):
    """Response model for ordered file in manifest."""
    sequence: int
    file: str
    b2_path: str
    dependencies: list[str]
    complexity: str


class ManifestResponse(BaseModel):
    """Response model for processing manifest."""
    manifest_id: str
    content_set_id: str
    content_set_name: str
    ordered_files: list[OrderedFileResponse]
    total_files: int
    warnings: list[str]
    estimated_time_seconds: int
    created_at: datetime
    context: dict
```

---

## Database Schema

### Supabase Tables

```sql
-- Content Sets table
CREATE TABLE IF NOT EXISTS content_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    detection_method VARCHAR(50) NOT NULL DEFAULT 'pattern',
    is_complete BOOLEAN DEFAULT FALSE,
    missing_files JSONB DEFAULT '[]'::jsonb,
    file_count INTEGER NOT NULL DEFAULT 0,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Content Set Files table
CREATE TABLE IF NOT EXISTS content_set_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_set_id UUID NOT NULL REFERENCES content_sets(id) ON DELETE CASCADE,
    b2_path VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sequence_number INTEGER,
    dependencies JSONB DEFAULT '[]'::jsonb,
    estimated_complexity VARCHAR(20) DEFAULT 'medium',
    file_type VARCHAR(50),
    size_bytes BIGINT DEFAULT 0,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Processing Manifests table
CREATE TABLE IF NOT EXISTS processing_manifests (
    manifest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_set_id UUID REFERENCES content_sets(id) ON DELETE SET NULL,
    content_set_name VARCHAR(255),
    ordered_files JSONB NOT NULL,
    total_files INTEGER NOT NULL,
    warnings JSONB DEFAULT '[]'::jsonb,
    estimated_time_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    context JSONB DEFAULT '{}'::jsonb,
    processing_status VARCHAR(50) DEFAULT 'pending'
);

-- Indexes
CREATE INDEX idx_content_sets_status ON content_sets(processing_status);
CREATE INDEX idx_content_sets_created ON content_sets(created_at DESC);
CREATE INDEX idx_content_set_files_set_id ON content_set_files(content_set_id);
CREATE INDEX idx_content_set_files_sequence ON content_set_files(content_set_id, sequence_number);
CREATE INDEX idx_manifests_set_id ON processing_manifests(content_set_id);
CREATE INDEX idx_manifests_status ON processing_manifests(processing_status);

-- RLS Policies
ALTER TABLE content_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_set_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_manifests ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read/write their content sets
CREATE POLICY "Users can manage content sets"
ON content_sets FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

CREATE POLICY "Users can manage content set files"
ON content_set_files FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

CREATE POLICY "Users can manage manifests"
ON processing_manifests FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);
```

### Neo4j Schema

```cypher
// Constraints
CREATE CONSTRAINT content_set_id IF NOT EXISTS
FOR (cs:ContentSet) REQUIRE cs.id IS UNIQUE;

// Indexes
CREATE INDEX content_set_name IF NOT EXISTS
FOR (cs:ContentSet) ON (cs.name);

// Relationship types:
// (Document)-[:PART_OF {sequence: 1}]->(ContentSet)
// (Document)-[:PRECEDES]->(Document)
// (Document)-[:DEPENDS_ON]->(Document)
```

---

## Integration with Existing Pipeline

### B2 Workflow Hook

Modify `app/services/b2_workflow.py` to trigger content prep:

```python
# Add to process_pending_files function

async def process_pending_files(folder: str = "pending/"):
    """Process files from B2 pending folder."""

    # NEW: Analyze for content sets first
    from app.services.content_prep_agent import ContentPrepAgent
    agent = ContentPrepAgent()

    analysis = await agent.analyze_folder(folder)

    # Process content sets with manifest
    for content_set in analysis["content_sets"]:
        manifest = await agent.generate_manifest(
            content_set["id"],
            proceed_incomplete=True
        )
        # Queue manifest processing
        from app.tasks.content_prep_tasks import process_manifest_task
        process_manifest_task.delay(manifest["manifest_id"])

    # Process standalone files normally
    for file in analysis["standalone_files"]:
        from app.tasks.source_processing import process_source
        process_source.delay(file["path"])
```

### Source Processing Context

Modify `app/tasks/source_processing.py` to accept manifest context:

```python
@shared_task(name="process_source")
def process_source(b2_path: str, context: dict = None):
    """
    Process a source file.

    Args:
        b2_path: Path to file in B2
        context: Optional context from content prep agent
            - content_set: Name of the content set
            - sequence: Position in sequence
            - total_files: Total files in set
            - is_sequential: Whether this is sequential content
    """
    # ... existing processing logic ...

    # If sequential content, add metadata
    if context and context.get("is_sequential"):
        metadata["content_set"] = context["content_set"]
        metadata["sequence"] = context["sequence"]
        metadata["is_sequential"] = True

        # Create Neo4j relationships
        if context["sequence"] > 1:
            # Link to previous document
            create_sequence_relationship(doc_id, previous_doc_id)
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_content_prep_agent.py

import pytest
from app.services.content_prep_agent import ContentPrepAgent, ContentFile

class TestSequenceExtraction:
    def test_numeric_prefix(self):
        agent = ContentPrepAgent()
        seq, pattern = agent._extract_sequence("01-introduction.pdf")
        assert seq == 1
        assert pattern == "numeric_prefix"

    def test_module_pattern(self):
        agent = ContentPrepAgent()
        seq, pattern = agent._extract_sequence("module-05-advanced.pdf")
        assert seq == 5
        assert pattern == "module"

    def test_chapter_pattern(self):
        agent = ContentPrepAgent()
        seq, pattern = agent._extract_sequence("chapter12-conclusion.pdf")
        assert seq == 12
        assert pattern == "chapter"

    def test_no_sequence(self):
        agent = ContentPrepAgent()
        seq, pattern = agent._extract_sequence("random-document.pdf")
        assert seq is None
        assert pattern is None


class TestContentSetDetection:
    def test_detects_course_set(self):
        files = [
            {"filename": "python-course-01.pdf", "path": "pending/python-course-01.pdf"},
            {"filename": "python-course-02.pdf", "path": "pending/python-course-02.pdf"},
            {"filename": "python-course-03.pdf", "path": "pending/python-course-03.pdf"},
        ]
        agent = ContentPrepAgent()
        sets, remaining = agent._detect_by_pattern(files)

        assert len(sets) == 1
        assert sets[0].name.lower().startswith("python")
        assert len(sets[0].files) == 3
        assert sets[0].is_complete

    def test_detects_gap(self):
        files = [
            {"filename": "module-01.pdf", "path": "pending/module-01.pdf"},
            {"filename": "module-02.pdf", "path": "pending/module-02.pdf"},
            {"filename": "module-04.pdf", "path": "pending/module-04.pdf"},  # Gap!
        ]
        agent = ContentPrepAgent()
        sets, _ = agent._detect_by_pattern(files)

        assert len(sets) == 1
        assert not sets[0].is_complete
        assert "#3" in sets[0].missing_files


class TestManifestGeneration:
    @pytest.mark.asyncio
    async def test_generates_ordered_manifest(self):
        # Mock content set
        agent = ContentPrepAgent()
        # ... test manifest generation
```

---

## Deployment Checklist

- [ ] Create database tables (migration)
- [ ] Deploy `content_prep_agent.py` service
- [ ] Deploy `content_prep.py` routes
- [ ] Deploy `content_prep_tasks.py` Celery tasks
- [ ] Update B2 workflow hook
- [ ] Update source processing with context support
- [ ] Add Celery queue configuration for `content_prep`
- [ ] Update agent registry in `crewai_service.py`
- [ ] Run test suite
- [ ] Update API documentation

---

## Monitoring & Observability

### Prometheus Metrics

```python
# Add to content_prep_agent.py

from prometheus_client import Counter, Histogram, Gauge

CONTENT_SETS_DETECTED = Counter(
    "content_prep_sets_detected_total",
    "Total content sets detected",
    ["detection_method"]
)

PROCESSING_TIME = Histogram(
    "content_prep_processing_seconds",
    "Time spent analyzing content",
    ["operation"]
)

INCOMPLETE_SETS = Gauge(
    "content_prep_incomplete_sets",
    "Number of incomplete content sets pending"
)
```

### Structured Logging

All operations logged with structlog:
- `analyzing_folder`: Start of analysis
- `content_set_detected`: New set found
- `gap_detected`: Missing files found
- `manifest_generated`: Manifest created
- `processing_file`: File being processed

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-13 | Initial architecture specification |
