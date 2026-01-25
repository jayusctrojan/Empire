"""
Faceted Search Service - Empire v7.3

Provides faceted filtering capabilities for search results:
- Department filtering
- File type filtering
- Date range filtering
- Entity filtering (from metadata)

Features:
- Multi-select facets
- Dynamic facet value generation from result set
- Efficient filtering with SQL
- Facet count aggregation
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class FacetType(str, Enum):
    """Types of facets available"""
    DEPARTMENT = "department"
    FILE_TYPE = "file_type"
    DATE_RANGE = "date_range"
    ENTITY = "entity"


@dataclass
class FacetValue:
    """Individual facet value with count"""
    value: str
    display_name: str
    count: int
    selected: bool = False


@dataclass
class Facet:
    """Facet configuration and values"""
    facet_type: FacetType
    display_name: str
    values: List[FacetValue] = field(default_factory=list)
    multi_select: bool = True


@dataclass
class FacetFilters:
    """Active facet filters for a search"""
    departments: List[str] = field(default_factory=list)
    file_types: List[str] = field(default_factory=list)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    entities: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Check if any filters are applied"""
        return not any([
            self.departments,
            self.file_types,
            self.date_from,
            self.date_to,
            self.entities
        ])

    def to_sql_conditions(self) -> tuple[str, dict]:
        """
        Convert filters to SQL WHERE conditions and parameters

        Returns:
            Tuple of (WHERE clause string, parameters dict)
        """
        conditions = []
        params = {}

        if self.departments:
            conditions.append("d.department = ANY(:departments)")
            params['departments'] = self.departments

        if self.file_types:
            conditions.append("d.file_type = ANY(:file_types)")
            params['file_types'] = self.file_types

        if self.date_from:
            conditions.append("d.created_at >= :date_from")
            params['date_from'] = self.date_from

        if self.date_to:
            conditions.append("d.created_at <= :date_to")
            params['date_to'] = self.date_to

        if self.entities:
            # Entities stored in metadata JSONB
            conditions.append("dc.metadata->>'entities' ?| :entities")
            params['entities'] = self.entities

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        return where_clause, params


@dataclass
class SearchResultWithFacets:
    """
    Enhanced search result with snippet, highlights, and metadata
    """
    chunk_id: str
    document_id: str
    content: str
    snippet: str
    highlighted_snippet: str
    score: float
    rank: int

    # Metadata for display
    relevance_score: float
    source_file: str
    department: Optional[str] = None
    file_type: Optional[str] = None
    created_at: Optional[datetime] = None
    b2_url: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class FacetedSearchService:
    """
    Service for faceted search and result presentation

    Features:
    - Extract facet values from result sets
    - Filter results by multiple facets
    - Generate snippets with keyword highlighting
    - Format results with metadata
    """

    def __init__(self, supabase_client=None):
        """
        Initialize faceted search service

        Args:
            supabase_client: Optional Supabase client for database queries
        """
        self.supabase = supabase_client
        logger.info("FacetedSearchService initialized")

    async def extract_facets(
        self,
        document_ids: List[str],
        selected_filters: Optional[FacetFilters] = None
    ) -> List[Facet]:
        """
        Extract available facet values from a set of documents

        Args:
            document_ids: List of document IDs in the result set
            selected_filters: Currently selected filters to mark as selected

        Returns:
            List of Facet objects with values and counts
        """
        if not document_ids:
            return []

        try:
            facets = []

            # Extract department facet
            department_facet = await self._extract_department_facet(
                document_ids,
                selected_filters.departments if selected_filters else []
            )
            if department_facet.values:
                facets.append(department_facet)

            # Extract file type facet
            file_type_facet = await self._extract_file_type_facet(
                document_ids,
                selected_filters.file_types if selected_filters else []
            )
            if file_type_facet.values:
                facets.append(file_type_facet)

            # Extract date range facet
            date_facet = await self._extract_date_facet(
                document_ids,
                selected_filters.date_from if selected_filters else None,
                selected_filters.date_to if selected_filters else None
            )
            if date_facet.values:
                facets.append(date_facet)

            # Extract entity facet (from metadata)
            entity_facet = await self._extract_entity_facet(
                document_ids,
                selected_filters.entities if selected_filters else []
            )
            if entity_facet.values:
                facets.append(entity_facet)

            logger.info(
                "Extracted facets",
                num_documents=len(document_ids),
                num_facets=len(facets)
            )

            return facets

        except Exception as e:
            logger.error("Failed to extract facets", error=str(e))
            return []

    async def _extract_department_facet(
        self,
        document_ids: List[str],
        selected: List[str]
    ) -> Facet:
        """Extract department facet with counts"""
        if not self.supabase:
            logger.warning("Supabase client not available for department facet extraction")
            return Facet(
                facet_type=FacetType.DEPARTMENT,
                display_name="Department",
                values=[],
                multi_select=True
            )

        try:
            # Query database for department counts
            response = self.supabase.rpc(
                'get_department_facets',
                {'doc_ids': document_ids}
            ).execute()

            if not response.data:
                # Fallback to direct query if function doesn't exist
                response = self.supabase.table('documents') \
                    .select('department') \
                    .in_('document_id', document_ids) \
                    .not_.is_('department', 'null') \
                    .execute()

                # Count departments manually
                dept_counts = {}
                for row in response.data:
                    dept = row['department']
                    dept_counts[dept] = dept_counts.get(dept, 0) + 1

                # Convert to FacetValues
                values = [
                    FacetValue(
                        value=dept,
                        display_name=dept.replace('_', ' ').title(),
                        count=count,
                        selected=dept in selected
                    )
                    for dept, count in sorted(
                        dept_counts.items(),
                        key=lambda x: (-x[1], x[0])
                    )
                ]
            else:
                # Use RPC function results
                values = [
                    FacetValue(
                        value=row['department'],
                        display_name=row['department'].replace('_', ' ').title(),
                        count=row['count'],
                        selected=row['department'] in selected
                    )
                    for row in response.data
                ]

            return Facet(
                facet_type=FacetType.DEPARTMENT,
                display_name="Department",
                values=values,
                multi_select=True
            )

        except Exception as e:
            logger.error("Failed to extract department facet", error=str(e))
            return Facet(
                facet_type=FacetType.DEPARTMENT,
                display_name="Department",
                values=[],
                multi_select=True
            )

    async def _extract_file_type_facet(
        self,
        document_ids: List[str],
        selected: List[str]
    ) -> Facet:
        """Extract file type facet with counts"""
        if not self.supabase:
            logger.warning("Supabase client not available for file type facet extraction")
            return Facet(
                facet_type=FacetType.FILE_TYPE,
                display_name="File Type",
                values=[],
                multi_select=True
            )

        try:
            # Query database for file type counts
            response = self.supabase.table('documents') \
                .select('file_type') \
                .in_('document_id', document_ids) \
                .not_.is_('file_type', 'null') \
                .execute()

            # Count file types manually
            type_counts = {}
            for row in response.data:
                file_type = row['file_type'].lower()
                type_counts[file_type] = type_counts.get(file_type, 0) + 1

            # Human-readable names
            type_display_names = {
                'pdf': 'PDF',
                'docx': 'Word Document',
                'doc': 'Word Document',
                'txt': 'Text File',
                'md': 'Markdown',
                'xlsx': 'Excel Spreadsheet',
                'xls': 'Excel Spreadsheet',
                'pptx': 'PowerPoint',
                'ppt': 'PowerPoint',
                'csv': 'CSV',
                'json': 'JSON',
                'xml': 'XML',
                'html': 'HTML'
            }

            # Convert to FacetValues
            values = [
                FacetValue(
                    value=file_type,
                    display_name=type_display_names.get(file_type, file_type.upper()),
                    count=count,
                    selected=file_type in selected
                )
                for file_type, count in sorted(
                    type_counts.items(),
                    key=lambda x: (-x[1], x[0])
                )
            ]

            return Facet(
                facet_type=FacetType.FILE_TYPE,
                display_name="File Type",
                values=values,
                multi_select=True
            )

        except Exception as e:
            logger.error("Failed to extract file type facet", error=str(e))
            return Facet(
                facet_type=FacetType.FILE_TYPE,
                display_name="File Type",
                values=[],
                multi_select=True
            )

    async def _extract_date_facet(
        self,
        document_ids: List[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime]
    ) -> Facet:
        """Extract date range facet"""
        if not self.supabase:
            logger.warning("Supabase client not available for date facet extraction")
            return Facet(
                facet_type=FacetType.DATE_RANGE,
                display_name="Date Range",
                values=[],
                multi_select=False
            )

        try:
            from datetime import timedelta
            now = datetime.now()

            # Define date ranges
            date_ranges = [
                ("last_7_days", "Last 7 Days", now - timedelta(days=7)),
                ("last_30_days", "Last 30 Days", now - timedelta(days=30)),
                ("last_90_days", "Last 90 Days", now - timedelta(days=90)),
                ("last_year", "Last Year", now - timedelta(days=365)),
            ]

            values = []
            for range_value, range_name, since_date in date_ranges:
                # Count documents in this date range
                response = self.supabase.table('documents') \
                    .select('id', count='exact') \
                    .in_('document_id', document_ids) \
                    .gte('created_at', since_date.isoformat()) \
                    .execute()

                count = response.count if hasattr(response, 'count') else len(response.data)

                values.append(FacetValue(
                    value=range_value,
                    display_name=range_name,
                    count=count,
                    selected=(date_from == since_date if date_from else False)
                ))

            return Facet(
                facet_type=FacetType.DATE_RANGE,
                display_name="Date Range",
                values=values,
                multi_select=False  # Single select for date ranges
            )

        except Exception as e:
            logger.error("Failed to extract date facet", error=str(e))
            return Facet(
                facet_type=FacetType.DATE_RANGE,
                display_name="Date Range",
                values=[],
                multi_select=False
            )

    async def _extract_entity_facet(
        self,
        document_ids: List[str],
        selected: List[str]
    ) -> Facet:
        """Extract entity facet from metadata"""
        if not self.supabase:
            logger.warning("Supabase client not available for entity facet extraction")
            return Facet(
                facet_type=FacetType.ENTITY,
                display_name="Entities",
                values=[],
                multi_select=True
            )

        try:
            # Extract entities from JSONB metadata in document_chunks
            response = self.supabase.table('document_chunks') \
                .select('metadata') \
                .in_('document_id', document_ids) \
                .execute()

            # Extract and count entities
            entity_counts = {}
            for row in response.data:
                metadata = row.get('metadata', {})
                if isinstance(metadata, dict):
                    entities = metadata.get('entities', [])
                    if isinstance(entities, list):
                        for entity in entities:
                            if isinstance(entity, str):
                                entity_counts[entity] = entity_counts.get(entity, 0) + 1
                            elif isinstance(entity, dict):
                                # Handle entity objects with 'name' field
                                entity_name = entity.get('name') or entity.get('text')
                                if entity_name:
                                    entity_counts[entity_name] = entity_counts.get(entity_name, 0) + 1

            # Convert to FacetValues (top 20 entities by count)
            values = [
                FacetValue(
                    value=entity,
                    display_name=entity,
                    count=count,
                    selected=entity in selected
                )
                for entity, count in sorted(
                    entity_counts.items(),
                    key=lambda x: (-x[1], x[0])
                )[:20]  # Limit to top 20 entities
            ]

            return Facet(
                facet_type=FacetType.ENTITY,
                display_name="Entities",
                values=values,
                multi_select=True
            )

        except Exception as e:
            logger.error("Failed to extract entity facet", error=str(e))
            return Facet(
                facet_type=FacetType.ENTITY,
                display_name="Entities",
                values=[],
                multi_select=True
            )

    def generate_snippet(
        self,
        content: str,
        query_keywords: List[str],
        max_length: int = 200,
        context_chars: int = 50
    ) -> str:
        """
        Generate a snippet from content around query keywords

        Args:
            content: Full content text
            query_keywords: Keywords to find in content
            max_length: Maximum snippet length
            context_chars: Characters of context on each side of keyword

        Returns:
            Snippet string with ellipsis if truncated
        """
        if not content or not query_keywords:
            # Return beginning of content if no keywords
            return content[:max_length] + ("..." if len(content) > max_length else "")

        content_lower = content.lower()

        # Find first occurrence of any keyword
        best_pos = -1
        best_keyword = None

        for keyword in query_keywords:
            pos = content_lower.find(keyword.lower())
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos
                best_keyword = keyword

        if best_pos == -1:
            # No keyword found, return beginning
            return content[:max_length] + ("..." if len(content) > max_length else "")

        # Extract snippet around keyword
        start = max(0, best_pos - context_chars)
        end = min(len(content), best_pos + len(best_keyword) + context_chars)

        snippet = content[start:end]

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    def highlight_keywords(
        self,
        text: str,
        keywords: List[str],
        highlight_tag: str = "mark"
    ) -> str:
        """
        Highlight keywords in text using HTML tags

        Args:
            text: Text to highlight
            keywords: Keywords to highlight
            highlight_tag: HTML tag to use (default: "mark")

        Returns:
            Text with keywords wrapped in highlight tags
        """
        if not keywords:
            return text

        highlighted = text

        for keyword in keywords:
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            highlighted = pattern.sub(
                f"<{highlight_tag}>\\g<0></{highlight_tag}>",
                highlighted
            )

        return highlighted

    def format_search_result(
        self,
        chunk_id: str,
        document_id: str,
        content: str,
        score: float,
        rank: int,
        query_keywords: List[str],
        document_metadata: Dict[str, Any]
    ) -> SearchResultWithFacets:
        """
        Format a search result with snippet, highlights, and metadata

        Args:
            chunk_id: Chunk ID
            document_id: Document ID
            content: Full content
            score: Relevance score
            rank: Result rank
            query_keywords: Keywords from query
            document_metadata: Document metadata from database

        Returns:
            Formatted SearchResultWithFacets object
        """
        # Generate snippet
        snippet = self.generate_snippet(content, query_keywords)

        # Highlight keywords in snippet
        highlighted_snippet = self.highlight_keywords(snippet, query_keywords)

        # Extract metadata
        department = document_metadata.get("department")
        file_type = document_metadata.get("file_type")
        created_at = document_metadata.get("created_at")
        b2_url = document_metadata.get("b2_url")
        filename = document_metadata.get("filename", "Unknown")

        return SearchResultWithFacets(
            chunk_id=chunk_id,
            document_id=document_id,
            content=content,
            snippet=snippet,
            highlighted_snippet=highlighted_snippet,
            score=score,
            rank=rank,
            relevance_score=score,
            source_file=filename,
            department=department,
            file_type=file_type,
            created_at=created_at,
            b2_url=b2_url,
            metadata=document_metadata
        )


# Singleton instance
_faceted_search_service = None


def get_faceted_search_service(supabase_client=None) -> FacetedSearchService:
    """
    Get singleton instance of FacetedSearchService

    Returns:
        FacetedSearchService instance
    """
    global _faceted_search_service
    if _faceted_search_service is None:
        _faceted_search_service = FacetedSearchService(supabase_client)
    return _faceted_search_service
