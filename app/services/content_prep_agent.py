"""
AGENT-016: Content Prep Agent

Validates, orders, and prepares content for knowledge base ingestion.
Ensures multi-file content (courses, documentation, book chapters) is
processed in correct logical/chronological order.

Feature: 007-content-prep-agent
"""

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

import structlog

# CrewAI import with graceful fallback for version compatibility
try:
    from crewai import Agent, Task, Crew
    CREWAI_AVAILABLE = True
except ImportError as e:
    # CrewAI 1.x may have different import structure or be unavailable
    Agent = None
    Task = None
    Crew = None
    CREWAI_AVAILABLE = False
    import logging
    logging.warning(f"CrewAI not available, LLM-based detection disabled: {e}")

from app.services.b2_storage import B2StorageService
from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)

# Module-level startup time for uptime tracking
_AGENT_START_TIME = time.time()
_AGENT_VERSION = "1.0.0"


# ============================================================================
# Sequence Detection Patterns
# ============================================================================

SEQUENCE_PATTERNS: list[tuple[str, str]] = [
    # Numeric prefix patterns
    (r"^(\d{1,3})[-_\s]", "numeric_prefix"),          # "01-intro.pdf"
    (r"[-_\s](\d{1,3})[-_\s.]", "numeric_infix"),     # "chapter-01-intro.pdf"
    (r"module[-_\s]?(\d{1,3})", "module"),            # "module01.pdf"
    (r"chapter[-_\s]?(\d{1,3})", "chapter"),          # "chapter1.pdf"
    (r"lesson[-_\s]?(\d{1,3})", "lesson"),            # "lesson5.pdf"
    (r"part[-_\s]?(\d{1,3})", "part"),                # "part-1.pdf"
    (r"week[-_\s]?(\d{1,3})", "week"),                # "week-01.pdf"
    (r"unit[-_\s]?(\d{1,3})", "unit"),                # "unit-1.pdf"
    (r"section[-_\s]?(\d{1,3})", "section"),          # "section-1.pdf"
    # Roman numerals (must come before alpha to avoid i=9th letter bug)
    (r"^(i{1,3}|iv|v|vi{0,3}|ix|x)[-_\s]", "roman"), # "i-intro.pdf"
    # Alpha sequence patterns (excluding roman numeral letters at start)
    (r"^([a-hjk-uwyz])[-_\s]", "alpha_prefix"),      # "a-intro.pdf" (excludes i,v,x)
]

CONTENT_SET_INDICATORS: list[str] = [
    "course", "tutorial", "training", "documentation",
    "manual", "series", "book", "guide", "curriculum",
]


# ============================================================================
# Data Classes
# ============================================================================

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


@dataclass
class ProcessingManifest:
    """Generated processing order with context."""

    manifest_id: str = field(default_factory=lambda: str(uuid4()))
    content_set_id: str = ""
    content_set_name: str = ""
    ordered_files: list[dict] = field(default_factory=list)
    total_files: int = 0
    warnings: list[str] = field(default_factory=list)
    estimated_time_seconds: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    context: dict = field(default_factory=dict)


# ============================================================================
# Content Prep Agent
# ============================================================================

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
        self.b2_service = B2StorageService()
        self.supabase = get_supabase_client()
        self.logger = logger.bind(agent="AGENT-016")

        # CrewAI agent for LLM-assisted ordering (optional)
        self.crew_agent = None
        if CREWAI_AVAILABLE and Agent is not None:
            try:
                self.crew_agent = Agent(
                    role="Content Preparation Specialist",
                    goal="Validate, order, and prepare content sets for optimal knowledge base ingestion",
                    backstory="""You are an expert in content organization and curriculum design.
                    You understand that learning materials must be processed in logical sequence
                    to maintain prerequisite relationships. You detect patterns in file naming,
                    identify content sets, and ensure completeness before processing begins.""",
                    llm="claude-3-5-haiku-20241022",
                    verbose=True,
                    allow_delegation=False,
                )
            except Exception as e:
                self.logger.warning("crewai_agent_init_failed", error=str(e))
                self.crew_agent = None

    # ========================================================================
    # Public Methods
    # ========================================================================

    async def analyze_folder(
        self,
        b2_folder: str,
        detection_mode: str = "auto",
    ) -> dict:
        """
        Analyze files in B2 folder and detect content sets.

        Args:
            b2_folder: B2 folder path to analyze
            detection_mode: "auto", "pattern", "metadata", or "llm"

        Returns:
            Dict with content_sets and standalone_files
        """
        import time
        start_time = time.time()

        self.logger.info("analyzing_folder", folder=b2_folder, mode=detection_mode)

        # List files in folder
        files = await self.b2_service.list_files(b2_folder)

        if not files:
            return {"content_sets": [], "standalone_files": [], "analysis_time_ms": 0}

        # Early exit for single file (US-004: Standalone Pass-Through)
        if len(files) == 1:
            self.logger.info("single_file_passthrough", file=files[0].get("filename"))
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "content_sets": [],
                "standalone_files": files,
                "analysis_time_ms": elapsed_ms,
            }

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
            standalone = [f for f in files if f.get("path") not in grouped_files]
        else:
            standalone = files

        # Store detected sets in database
        for content_set in content_sets:
            await self._store_content_set(content_set)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "content_sets": [self._serialize_set(s) for s in content_sets],
            "standalone_files": standalone,
            "analysis_time_ms": elapsed_ms,
        }

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
            content_set.missing_files = [
                f"#{n} (between {n-1} and {n+1})" for n in missing
            ]
            content_set.is_complete = len(missing) == 0

        return {
            "set_id": set_id,
            "is_complete": content_set.is_complete,
            "missing_files": content_set.missing_files,
            "total_files": len(content_set.files),
            "gaps_detected": len(content_set.missing_files),
            "can_proceed": True,
            "requires_acknowledgment": not content_set.is_complete,
        }

    async def generate_manifest(
        self,
        content_set_id: str,
        proceed_incomplete: bool = False,
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

        # Log if proceeding with incomplete set (audit trail per US-002)
        if not content_set.is_complete and proceed_incomplete:
            self.logger.warning(
                "proceeding_with_incomplete_set",
                set_id=content_set_id,
                missing_files=content_set.missing_files,
            )

        # Build ordered file list with dependencies
        ordered_files = []
        for i, file in enumerate(content_set.files):
            dependencies = []
            if i > 0:
                # Each file depends on the previous one
                dependencies.append(content_set.files[i - 1].filename)

            ordered_files.append({
                "sequence": i + 1,
                "file": file.filename,
                "b2_path": file.b2_path,
                "dependencies": dependencies,
                "complexity": file.estimated_complexity,
            })

        # Estimate processing time (rough: 30s per file)
        estimated_time = len(ordered_files) * 30

        manifest = ProcessingManifest(
            content_set_id=content_set_id,
            content_set_name=content_set.name,
            ordered_files=ordered_files,
            total_files=len(ordered_files),
            warnings=content_set.missing_files if not content_set.is_complete else [],
            estimated_time_seconds=estimated_time,
            context={
                "set_name": content_set.name,
                "is_sequential": True,
                "detection_method": content_set.detection_method,
            },
        )

        # Store manifest
        await self._store_manifest(manifest)

        return {
            "manifest_id": manifest.manifest_id,
            "content_set_id": manifest.content_set_id,
            "content_set_name": manifest.content_set_name,
            "ordered_files": manifest.ordered_files,
            "total_files": manifest.total_files,
            "warnings": manifest.warnings,
            "estimated_time_seconds": manifest.estimated_time_seconds,
            "created_at": manifest.created_at.isoformat(),
            "context": manifest.context,
        }

    async def list_sets(self, status: Optional[str] = None) -> list[dict]:
        """List all content sets, optionally filtered by status."""
        query = self.supabase.table("content_sets").select("*")
        if status:
            query = query.eq("processing_status", status)

        result = query.order("created_at", desc=True).execute()
        return result.data if result.data else []

    async def get_set(self, set_id: str) -> dict:
        """Get details of a specific content set."""
        content_set = await self._load_content_set(set_id)
        if not content_set:
            raise ValueError(f"Content set {set_id} not found")
        return self._serialize_set(content_set)

    # ========================================================================
    # Pattern Detection Methods
    # ========================================================================

    def _detect_by_pattern(
        self,
        files: list[dict],
    ) -> tuple[list[ContentSet], list[dict]]:
        """
        Detect content sets using naming patterns.

        Returns:
            Tuple of (detected_sets, remaining_files)
        """
        # Group files by prefix (common naming pattern)
        prefix_groups: dict[str, list[dict]] = {}

        for file_info in files:
            filename = file_info.get("filename", "")
            prefix = self._extract_prefix(filename)
            if prefix:
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []
                prefix_groups[prefix].append(file_info)

        content_sets = []
        grouped_files: set[str] = set()

        for prefix, group_files in prefix_groups.items():
            if len(group_files) >= 2:  # At least 2 files to form a set
                content_set = self._create_content_set(prefix, group_files)
                if content_set:
                    content_sets.append(content_set)
                    grouped_files.update(f.get("filename", "") for f in group_files)

        remaining = [f for f in files if f.get("filename", "") not in grouped_files]
        return content_sets, remaining

    def _extract_prefix(self, filename: str) -> Optional[str]:
        """Extract common prefix from filename for grouping."""
        # Remove extension
        name = filename.rsplit(".", 1)[0] if "." in filename else filename

        # Try to find sequence pattern and extract prefix
        for pattern, _ in SEQUENCE_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                # Get everything before the sequence number
                prefix = name[: match.start()].strip("-_ ")
                if prefix and len(prefix) >= 3:
                    return prefix.lower()

        # Check for content set indicators
        for indicator in CONTENT_SET_INDICATORS:
            if indicator in name.lower():
                idx = name.lower().find(indicator)
                return name[: idx + len(indicator)].strip("-_ ").lower()

        return None

    def _extract_sequence(self, filename: str) -> tuple[Optional[int], Optional[str]]:
        """Extract sequence number from filename."""
        name = filename.rsplit(".", 1)[0] if "." in filename else filename

        for pattern, pattern_name in SEQUENCE_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                try:
                    # Handle roman numerals
                    if pattern_name == "roman":
                        roman_val = match.group(1).lower()
                        roman_map = {
                            "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
                            "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
                        }
                        return roman_map.get(roman_val), pattern_name
                    # Handle alpha sequences
                    if pattern_name == "alpha_prefix":
                        return ord(match.group(1).lower()) - ord("a") + 1, pattern_name
                    return int(match.group(1)), pattern_name
                except (ValueError, IndexError):
                    continue

        return None, None

    def _create_content_set(
        self,
        prefix: str,
        files: list[dict],
    ) -> Optional[ContentSet]:
        """Create a ContentSet from grouped files."""
        content_files = []
        sequences_found = []

        for file_info in files:
            filename = file_info.get("filename", "")
            sequence, pattern = self._extract_sequence(filename)

            content_file = ContentFile(
                b2_path=file_info.get("filename", ""),
                filename=filename,
                sequence_number=sequence,
                detection_pattern=pattern,
                file_type=filename.rsplit(".", 1)[-1] if "." in filename else "",
                size_bytes=file_info.get("size", 0),
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
        confidence = (
            len([f for f in content_files if f.sequence_number]) / len(content_files)
            if content_files
            else 0
        )

        content_set = ContentSet(
            name=self._generate_set_name(prefix, content_files),
            detection_method="pattern",
            files=content_files,
            is_complete=len(missing) == 0,
            missing_files=missing,
            confidence=confidence,
        )

        return content_set if confidence >= 0.5 else None

    def _generate_set_name(self, prefix: str, files: list[ContentFile]) -> str:
        """Generate a human-readable name for the content set."""
        name = prefix.replace("-", " ").replace("_", " ").title()

        file_types = set(f.file_type.upper() for f in files if f.file_type)
        if file_types:
            name += f" ({', '.join(sorted(file_types))})"

        return name

    # ========================================================================
    # LLM-Assisted Detection
    # ========================================================================

    async def _detect_by_llm(self, files: list[dict]) -> list[ContentSet]:
        """Use LLM to detect content sets from ambiguous files."""
        if not files:
            return []

        # Check if CrewAI is available
        if not CREWAI_AVAILABLE or self.crew_agent is None or Task is None or Crew is None:
            self.logger.info("llm_detection_skipped", reason="crewai_not_available")
            return []

        # Limit files for context
        file_list = "\n".join([f"- {f.get('filename', '')}" for f in files[:50]])

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
            agent=self.crew_agent,
        )

        try:
            crew = Crew(agents=[self.crew_agent], tasks=[task], verbose=True)
            result = crew.kickoff()
            self.logger.info("llm_detection_complete", result_length=len(str(result)))

            # Parse LLM response and create ContentSets
            return self._parse_llm_json_response(str(result), files)
        except Exception as e:
            self.logger.error("llm_detection_failed", error=str(e))
            return []

    def _parse_llm_json_response(
        self,
        result: str,
        original_files: list[dict]
    ) -> list[ContentSet]:
        """
        Parse LLM JSON response and create ContentSet objects.

        Args:
            result: Raw LLM output string
            original_files: Original file list for metadata lookup

        Returns:
            List of ContentSet objects parsed from LLM response
        """
        import json
        import re

        content_sets: list[ContentSet] = []

        try:
            # Try to extract JSON from LLM response
            # LLM might wrap JSON in markdown code blocks or extra text
            json_match = re.search(r'\{[\s\S]*\}', result)
            if not json_match:
                # Try array format
                json_match = re.search(r'\[[\s\S]*\]', result)

            if not json_match:
                self.logger.warning("no_json_in_llm_response", response_preview=result[:200])
                return []

            json_str = json_match.group()
            data = json.loads(json_str)

            # Handle both object and array formats
            if isinstance(data, list):
                sets_data = data
            else:
                sets_data = data.get("content_sets", [])

            # Create file lookup for quick access
            file_lookup = {f.get("filename", ""): f for f in original_files}

            for set_data in sets_data:
                if not isinstance(set_data, dict):
                    continue

                # Extract content set properties
                set_name = set_data.get("name", "Unnamed Set")
                set_files = set_data.get("files", [])
                missing = set_data.get("missing_files", [])

                # Build ContentFile list
                content_files: list[ContentFile] = []
                for idx, file_entry in enumerate(set_files):
                    # File entry can be string (filename) or dict
                    if isinstance(file_entry, str):
                        filename = file_entry
                        file_meta = file_lookup.get(filename, {})
                    else:
                        filename = file_entry.get("file_name", file_entry.get("filename", file_entry.get("name", "")))
                        file_meta = file_lookup.get(filename, {})

                    if filename:
                        content_files.append(ContentFile(
                            b2_path=file_meta.get("b2_path", filename),
                            filename=filename,
                            sequence_number=idx + 1,  # Use LLM-determined order
                            detection_pattern="llm",
                            file_type=file_meta.get("file_type", ""),
                            size_bytes=file_meta.get("size", 0),
                            metadata={"llm_detected": True}
                        ))

                if content_files:
                    content_set = ContentSet(
                        name=set_name,
                        detection_method="llm",
                        files=content_files,
                        is_complete=len(missing) == 0,
                        missing_files=missing if isinstance(missing, list) else [],
                        confidence=0.7,  # LLM detection has moderate confidence
                        metadata={"llm_raw_response": set_data}
                    )
                    content_sets.append(content_set)

            self.logger.info(
                "llm_json_parsed",
                content_sets_found=len(content_sets),
                total_files_assigned=sum(len(cs.files) for cs in content_sets)
            )

        except json.JSONDecodeError as e:
            self.logger.warning("llm_json_parse_error", error=str(e), response_preview=result[:200])
        except Exception as e:
            self.logger.error("llm_response_processing_error", error=str(e))

        return content_sets

    # ========================================================================
    # Confidence Calculation (US-005: Chat Clarification)
    # ========================================================================

    def _calculate_ordering_confidence(self, content_set: ContentSet) -> float:
        """
        Calculate confidence score for the ordering.

        Returns:
            Float between 0 and 1. Below 0.8 triggers chat clarification.
        """
        if not content_set.files:
            return 0.0

        # Factors affecting confidence:
        # 1. How many files have detected sequence numbers
        files_with_sequence = sum(1 for f in content_set.files if f.sequence_number)
        sequence_ratio = files_with_sequence / len(content_set.files)

        # 2. Whether sequences are contiguous
        sequences = [f.sequence_number for f in content_set.files if f.sequence_number]
        if sequences:
            sequences.sort()
            expected_count = sequences[-1] - sequences[0] + 1
            contiguity = len(sequences) / expected_count
        else:
            contiguity = 0.0

        # 3. Consistency of detection patterns
        patterns = [f.detection_pattern for f in content_set.files if f.detection_pattern]
        if patterns:
            most_common = max(set(patterns), key=patterns.count)
            pattern_consistency = patterns.count(most_common) / len(patterns)
        else:
            pattern_consistency = 0.0

        # Weighted average
        confidence = (
            sequence_ratio * 0.4 +
            contiguity * 0.3 +
            pattern_consistency * 0.3
        )

        return round(confidence, 2)

    # ========================================================================
    # Database Operations
    # ========================================================================

    async def _store_content_set(self, content_set: ContentSet) -> None:
        """Store content set in database."""
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
                **content_set.metadata,
            },
        }
        self.supabase.table("content_sets").upsert(set_data).execute()

        # Insert files
        for file in content_set.files:
            file_data = {
                "content_set_id": content_set.id,
                "b2_path": file.b2_path,
                "filename": file.filename,
                "sequence_number": file.sequence_number,
                "detection_pattern": file.detection_pattern,
                "dependencies": file.dependencies,
                "estimated_complexity": file.estimated_complexity,
                "file_type": file.file_type,
                "size_bytes": file.size_bytes,
                "metadata": file.metadata,
            }
            self.supabase.table("content_set_files").upsert(file_data).execute()

        self.logger.info("content_set_stored", set_id=content_set.id, files=len(content_set.files))

    async def _load_content_set(self, set_id: str) -> Optional[ContentSet]:
        """Load content set from database."""
        result = self.supabase.table("content_sets").select("*").eq("id", set_id).execute()
        if not result.data:
            return None

        set_data = result.data[0]

        # Load files
        files_result = (
            self.supabase.table("content_set_files")
            .select("*")
            .eq("content_set_id", set_id)
            .order("sequence_number")
            .execute()
        )

        files = [
            ContentFile(
                b2_path=f["b2_path"],
                filename=f["filename"],
                sequence_number=f.get("sequence_number"),
                detection_pattern=f.get("detection_pattern"),
                dependencies=f.get("dependencies", []),
                estimated_complexity=f.get("estimated_complexity", "medium"),
                file_type=f.get("file_type", ""),
                size_bytes=f.get("size_bytes", 0),
                metadata=f.get("metadata", {}),
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
            metadata=set_data.get("metadata", {}),
        )

    async def _store_manifest(self, manifest: ProcessingManifest) -> None:
        """Store processing manifest."""
        manifest_data = {
            "manifest_id": manifest.manifest_id,
            "content_set_id": manifest.content_set_id,
            "content_set_name": manifest.content_set_name,
            "ordered_files": manifest.ordered_files,
            "total_files": manifest.total_files,
            "warnings": manifest.warnings,
            "estimated_time_seconds": manifest.estimated_time_seconds,
            "context": manifest.context,
        }
        self.supabase.table("processing_manifests").insert(manifest_data).execute()
        self.logger.info("manifest_stored", manifest_id=manifest.manifest_id)

    # ========================================================================
    # Serialization
    # ========================================================================

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
                    "b2_path": f.b2_path,
                    "detection_pattern": f.detection_pattern,
                    "estimated_complexity": f.estimated_complexity,
                    "file_type": f.file_type,
                    "size_bytes": f.size_bytes,
                }
                for f in content_set.files
            ],
            "is_complete": content_set.is_complete,
            "missing_files": content_set.missing_files,
            "processing_status": content_set.processing_status,
            "confidence": content_set.confidence,
        }

    # ========================================================================
    # Chat-Based Ordering Clarification (US-005, Task 129)
    # ========================================================================

    async def resolve_order_with_clarification(
        self,
        content_set_id: str,
        user_id: str,
        confidence_threshold: float = 0.8,
        timeout_seconds: int = 3600,
    ) -> dict:
        """
        Resolve file ordering with user clarification if needed.

        If ordering confidence is below threshold, requests clarification
        from the user via CKO Chat.

        Args:
            content_set_id: The content set to order
            user_id: User ID for chat communication
            confidence_threshold: Confidence below which to request clarification
            timeout_seconds: How long to wait for user response

        Returns:
            dict: Ordering result with clarification status
        """
        from app.services.cko_chat import (
            get_cko_chat_service,
            get_clarification_logger,
            AgentClarificationType,
        )

        self.logger.info(
            "resolving_order_with_clarification",
            content_set_id=content_set_id,
            confidence_threshold=confidence_threshold,
        )

        # Load content set
        content_set = await self._load_content_set(content_set_id)
        if not content_set:
            raise ValueError(f"Content set {content_set_id} not found")

        # Calculate initial confidence
        initial_confidence = self._calculate_ordering_confidence(content_set)
        self.logger.info(
            "initial_ordering_confidence",
            content_set_id=content_set_id,
            confidence=initial_confidence,
        )

        # If confidence is sufficient, return current ordering
        if initial_confidence >= confidence_threshold:
            return {
                "status": "success",
                "content_set_id": content_set_id,
                "ordering_confidence": initial_confidence,
                "clarification_requested": False,
                "ordered_files": [
                    {"filename": f.filename, "sequence": f.sequence_number}
                    for f in content_set.files
                ],
            }

        # Need user clarification
        chat_service = get_cko_chat_service()
        conversation_logger = get_clarification_logger()

        # Generate clarification message
        clarification_message = self._generate_clarification_message(content_set)

        # Send clarification request
        request_id = await chat_service.send_agent_message(
            agent_id="AGENT-016",
            user_id=user_id,
            message=clarification_message,
            clarification_type=AgentClarificationType.ORDERING,
            context={
                "content_set_id": content_set_id,
                "content_set_name": content_set.name,
                "ambiguous_files": [
                    f.filename for f in content_set.files if f.sequence_number is None
                ],
            },
        )

        self.logger.info(
            "clarification_request_sent",
            request_id=request_id,
            content_set_id=content_set_id,
        )

        # Wait for user response
        user_response = await chat_service.wait_for_user_response(
            request_id=request_id,
            timeout=timeout_seconds,
        )

        # Process response
        if user_response:
            # Update ordering based on user input
            updated_files, parse_result = self._update_ordering_from_response(
                content_set.files,
                user_response,
            )
            content_set.files = updated_files

            # Recalculate confidence after update
            new_confidence = self._calculate_ordering_confidence(content_set)

            # Store updated content set
            await self._store_content_set(content_set)

            # Log the conversation
            await conversation_logger.log_conversation(
                content_set_id=content_set_id,
                agent_id="AGENT-016",
                user_id=user_id,
                question=clarification_message,
                answer=user_response,
                outcome="ordering_updated" if parse_result["files_reordered"] > 0 else "no_change",
                clarification_type=AgentClarificationType.ORDERING,
                metadata={
                    "initial_confidence": initial_confidence,
                    "final_confidence": new_confidence,
                    "files_reordered": parse_result["files_reordered"],
                    "parse_method": parse_result["method"],
                },
            )

            self.logger.info(
                "ordering_clarification_complete",
                content_set_id=content_set_id,
                initial_confidence=initial_confidence,
                new_confidence=new_confidence,
                files_reordered=parse_result["files_reordered"],
            )

            return {
                "status": "success",
                "content_set_id": content_set_id,
                "ordering_confidence": new_confidence,
                "clarification_requested": True,
                "clarification_answered": True,
                "files_reordered": parse_result["files_reordered"],
                "ordered_files": [
                    {"filename": f.filename, "sequence": f.sequence_number}
                    for f in content_set.files
                ],
            }

        else:
            # Timeout or cancelled - proceed with best-effort ordering
            await conversation_logger.log_conversation(
                content_set_id=content_set_id,
                agent_id="AGENT-016",
                user_id=user_id,
                question=clarification_message,
                answer=None,
                outcome="timeout",
                clarification_type=AgentClarificationType.ORDERING,
                metadata={"initial_confidence": initial_confidence},
            )

            self.logger.warning(
                "clarification_timeout",
                content_set_id=content_set_id,
            )

            return {
                "status": "success",
                "content_set_id": content_set_id,
                "ordering_confidence": initial_confidence,
                "clarification_requested": True,
                "clarification_answered": False,
                "clarification_timeout": True,
                "ordered_files": [
                    {"filename": f.filename, "sequence": f.sequence_number}
                    for f in content_set.files
                ],
            }

    def _generate_clarification_message(self, content_set: ContentSet) -> str:
        """
        Generate a user-friendly clarification message.

        Creates a message explaining the ordering ambiguity and
        providing clear instructions for how to respond.

        Args:
            content_set: The content set with ambiguous ordering

        Returns:
            Formatted clarification message
        """
        # Identify ambiguous files (without sequence numbers)
        ambiguous_files = [f for f in content_set.files if f.sequence_number is None]
        sequenced_files = [f for f in content_set.files if f.sequence_number is not None]

        message_parts = [
            f"I'm processing your content set **'{content_set.name}'** and need help determining the correct file order.",
            "",
        ]

        if sequenced_files:
            message_parts.append("**Files with detected sequence:**")
            for f in sorted(sequenced_files, key=lambda x: x.sequence_number or 0):
                message_parts.append(f"  {f.sequence_number}. {f.filename}")
            message_parts.append("")

        if ambiguous_files:
            message_parts.append("**Files without clear sequence indicators:**")
            # Limit to first 10 files to avoid overwhelming messages
            for f in ambiguous_files[:10]:
                message_parts.append(f"  - {f.filename}")

            if len(ambiguous_files) > 10:
                message_parts.append(f"  ...and {len(ambiguous_files) - 10} more files")

            message_parts.append("")

        message_parts.extend([
            "**How to respond:**",
            "You can help me order these files in several ways:",
            "",
            "1. **List in order:** Simply list the filenames in the desired order, one per line",
            "2. **Use numbers:** `1. intro.pdf, 2. chapter1.pdf, 3. chapter2.pdf`",
            "3. **Describe relationships:** `intro.pdf comes before chapter1.pdf`",
            "4. **Confirm order:** Reply 'looks good' to accept my current best guess",
            "",
            "What's the correct order for these files?",
        ])

        return "\n".join(message_parts)

    def _update_ordering_from_response(
        self,
        files: list[ContentFile],
        response: str,
    ) -> tuple[list[ContentFile], dict]:
        """
        Update file ordering based on user's natural language response.

        Parses various response formats:
        - Numbered lists: "1. file1.pdf, 2. file2.pdf"
        - Simple lists: "file1.pdf\nfile2.pdf\nfile3.pdf"
        - Relative ordering: "file1 before file2"
        - Confirmation: "looks good", "ok", "yes"

        Args:
            files: Current list of files
            response: User's response text

        Returns:
            Tuple of (updated files list, parse result metadata)
        """
        response_lower = response.lower().strip()

        # Check for confirmation (accept current order)
        confirmation_phrases = [
            "looks good", "look good", "ok", "okay", "yes", "correct",
            "that's right", "thats right", "confirmed", "approve", "accept"
        ]
        if any(phrase in response_lower for phrase in confirmation_phrases):
            return files, {
                "method": "confirmation",
                "files_reordered": 0,
                "message": "User confirmed existing order",
            }

        # Create filename lookup (case-insensitive)
        file_map = {f.filename.lower(): f for f in files}
        file_map_original = {f.filename: f for f in files}

        # Track reordering
        reordered_count = 0
        new_order = []
        used_files = set()

        # Try parsing numbered list (e.g., "1. file.pdf, 2. other.pdf")
        numbered_pattern = re.compile(r'(\d+)[.\)]\s*([^\n,]+)', re.MULTILINE)
        numbered_matches = numbered_pattern.findall(response)

        if numbered_matches:
            # Sort by number
            numbered_matches.sort(key=lambda x: int(x[0]))

            for _, filename in numbered_matches:
                filename_clean = filename.strip().lower()
                # Try exact match first, then partial
                matched_file = None
                if filename_clean in file_map:
                    matched_file = file_map[filename_clean]
                else:
                    # Try partial match
                    for fn, f in file_map.items():
                        if filename_clean in fn or fn in filename_clean:
                            matched_file = f
                            break

                if matched_file and matched_file.filename not in used_files:
                    new_order.append(matched_file)
                    used_files.add(matched_file.filename)

            if new_order:
                # Add remaining files at the end
                remaining = [f for f in files if f.filename not in used_files]
                new_order.extend(remaining)

                # Assign new sequence numbers
                for i, f in enumerate(new_order, 1):
                    if f.sequence_number != i:
                        reordered_count += 1
                    f.sequence_number = i

                return new_order, {
                    "method": "numbered_list",
                    "files_reordered": reordered_count,
                    "matched_files": len(used_files),
                }

        # Try parsing simple line-by-line list
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        if lines and len(lines) > 1:
            for line in lines:
                # Remove common list markers
                line_clean = re.sub(r'^[-*•]\s*', '', line).strip().lower()

                if line_clean in file_map:
                    matched_file = file_map[line_clean]
                    if matched_file.filename not in used_files:
                        new_order.append(matched_file)
                        used_files.add(matched_file.filename)
                else:
                    # Try partial match
                    for fn, f in file_map.items():
                        if line_clean in fn or fn in line_clean:
                            if f.filename not in used_files:
                                new_order.append(f)
                                used_files.add(f.filename)
                            break

            if new_order:
                remaining = [f for f in files if f.filename not in used_files]
                new_order.extend(remaining)

                for i, f in enumerate(new_order, 1):
                    if f.sequence_number != i:
                        reordered_count += 1
                    f.sequence_number = i

                return new_order, {
                    "method": "line_list",
                    "files_reordered": reordered_count,
                    "matched_files": len(used_files),
                }

        # Try parsing relative ordering ("A before B", "A comes after B")
        relative_patterns = [
            (r'([^\s,]+)\s+(?:comes?\s+)?before\s+([^\s,]+)', 'before'),
            (r'([^\s,]+)\s+(?:comes?\s+)?after\s+([^\s,]+)', 'after'),
            (r'([^\s,]+)\s+then\s+([^\s,]+)', 'before'),
        ]

        for pattern, relation in relative_patterns:
            matches = re.findall(pattern, response_lower)
            if matches:
                # Build ordering constraints
                for file_a, file_b in matches:
                    file_a_clean = file_a.strip()
                    file_b_clean = file_b.strip()

                    # Find matching files
                    match_a = None
                    match_b = None
                    for fn, f in file_map.items():
                        if file_a_clean in fn:
                            match_a = f
                        if file_b_clean in fn:
                            match_b = f

                    if match_a and match_b:
                        # Apply constraint
                        a_idx = files.index(match_a)
                        b_idx = files.index(match_b)

                        if relation == 'before' and a_idx > b_idx:
                            # Move A before B
                            files.remove(match_a)
                            files.insert(b_idx, match_a)
                            reordered_count += 1
                        elif relation == 'after' and a_idx < b_idx:
                            # Move A after B
                            files.remove(match_a)
                            files.insert(b_idx, match_a)
                            reordered_count += 1

                if reordered_count > 0:
                    # Reassign sequence numbers
                    for i, f in enumerate(files, 1):
                        f.sequence_number = i

                    return files, {
                        "method": "relative_ordering",
                        "files_reordered": reordered_count,
                        "constraints_applied": len(matches),
                    }

        # Could not parse - return original order
        self.logger.warning(
            "could_not_parse_ordering_response",
            response_preview=response[:100],
        )

        return files, {
            "method": "unparseable",
            "files_reordered": 0,
            "message": "Could not parse user response",
        }

    # ========================================================================
    # Health & Status Methods (Task 140)
    # ========================================================================

    async def get_health_status(self) -> dict:
        """
        Get comprehensive health status for AGENT-016.

        Returns:
            Dict with agent info, metrics, connectivity, and capabilities
        """
        from app.models.content_sets import (
            HealthResponse,
            AgentInfo,
            ProcessingMetrics,
            ConnectivityStatus,
        )

        # Get agent info
        agent_info = AgentInfo(
            agent_id="AGENT-016",
            name="Content Prep Agent",
            version=_AGENT_VERSION,
            uptime_seconds=int(time.time() - _AGENT_START_TIME),
            llm_available=bool(os.getenv("ANTHROPIC_API_KEY")),
        )

        # Get processing metrics
        metrics = await self._get_processing_metrics()

        # Check connectivity
        connectivity = await self._check_connectivity()

        # Determine overall status
        status = "healthy"
        if not connectivity.supabase or not connectivity.b2_storage:
            status = "unhealthy"
        elif not connectivity.neo4j:
            status = "degraded"

        # Build capabilities
        capabilities = {
            "content_set_detection": True,
            "ordering_analysis": True,
            "ordering_clarification": True,
            "manifest_generation": True,
            "llm_powered": agent_info.llm_available,
        }

        return HealthResponse(
            status=status,
            agent=agent_info,
            metrics=metrics,
            connectivity=connectivity,
            capabilities=capabilities,
        )

    async def _get_processing_metrics(self):
        """Get processing metrics from database."""
        from app.models.content_sets import ProcessingMetrics
        from datetime import timedelta

        metrics = ProcessingMetrics()

        try:
            # Get pending content sets count
            result = self.supabase.table("content_sets").select(
                "id", count="exact"
            ).eq("status", "pending").execute()
            metrics.pending_content_sets = result.count or 0

            # Get active processing count
            result = self.supabase.table("content_sets").select(
                "id", count="exact"
            ).eq("status", "processing").execute()
            metrics.active_processing_count = result.count or 0

            # Get completed in last 24 hours
            yesterday = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            result = self.supabase.table("content_sets").select(
                "id", count="exact"
            ).eq("status", "complete").gte("updated_at", yesterday).execute()
            metrics.total_processed_24h = result.count or 0

            # Get recent error count (last 24 hours)
            result = self.supabase.table("content_sets").select(
                "id", count="exact"
            ).eq("status", "failed").gte("updated_at", yesterday).execute()
            metrics.recent_error_count = result.count or 0

        except Exception as e:
            self.logger.warning(
                "failed_to_get_processing_metrics",
                error=str(e),
            )
            # Return defaults on error
            metrics.recent_error_count = -1

        return metrics

    async def _check_connectivity(self):
        """Check connectivity to external services."""
        from app.models.content_sets import ConnectivityStatus

        connectivity = ConnectivityStatus(
            supabase=True,
            neo4j=True,
            b2_storage=True,
        )

        # Check Supabase
        try:
            self.supabase.table("content_sets").select("id").limit(1).execute()
        except Exception as e:
            self.logger.warning("supabase_connectivity_check_failed", error=str(e))
            connectivity.supabase = False

        # Check Neo4j (if available)
        try:
            from app.services.neo4j_http_client import Neo4jHTTPClient
            client = Neo4jHTTPClient()
            await client.health_check()
        except Exception as e:
            self.logger.warning("neo4j_connectivity_check_failed", error=str(e))
            connectivity.neo4j = False

        # Check B2 Storage
        try:
            # Simple bucket check
            self.b2_service.bucket is not None
        except Exception as e:
            self.logger.warning("b2_connectivity_check_failed", error=str(e))
            connectivity.b2_storage = False

        return connectivity


# =============================================================================
# Module-Level Utility Functions (Task 140)
# =============================================================================


def get_agent_uptime() -> int:
    """Get agent uptime in seconds."""
    return int(time.time() - _AGENT_START_TIME)


def get_agent_version() -> str:
    """Get agent version."""
    return _AGENT_VERSION


def is_llm_available() -> bool:
    """Check if LLM is available (CrewAI + API key)."""
    return CREWAI_AVAILABLE and bool(os.getenv("ANTHROPIC_API_KEY"))
