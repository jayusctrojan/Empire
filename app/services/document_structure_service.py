# app/services/document_structure_service.py
"""
Document Structure Service for extracting and navigating document hierarchy.

Task 105: Graph Agent - Document Structure Service
Feature: 005-graph-agent

Provides:
- Document structure extraction using LLM
- Cross-reference detection and linking
- Smart retrieval with context expansion
- Definition linking

Reference: AI Automators Graph-Based Context Expansion Blueprint
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re
import json
import uuid
import structlog

from app.services.neo4j_http_client import (
    Neo4jHTTPClient,
    get_neo4j_http_client,
    Neo4jQueryError,
    Neo4jConnectionError,
)
from app.models.graph_agent import (
    DocumentStructureRequest,
    DocumentStructureResponse,
    SmartRetrievalRequest,
    SmartRetrievalResponse,
    SectionNode,
    DefinedTermNode,
    CrossReference,
    CitationNode,
)

logger = structlog.get_logger()


class DocumentNotFoundError(Exception):
    """Raised when a document cannot be found."""
    pass


class DocumentStructureError(Exception):
    """Raised when document structure extraction fails."""
    pass


class DocumentStructureService:
    """
    Extracts and navigates document hierarchy, clause references, and cross-links.

    Provides:
    - Structure extraction from documents
    - Cross-reference detection and linking
    - Smart retrieval with context expansion
    - Definition linking

    Reference: AI Automators Graph-Based Context Expansion pattern
    """

    CACHE_TTL = 600  # 10 minutes

    def __init__(
        self,
        neo4j_client: Optional[Neo4jHTTPClient] = None,
        llm_service: Optional[Any] = None,
        cache_service: Optional[Any] = None,
    ):
        """
        Initialize Document Structure Service.

        Args:
            neo4j_client: Neo4j HTTP client instance. Uses singleton if not provided.
            llm_service: Optional LLM service for structure extraction.
            cache_service: Optional cache service for result caching.
        """
        self.neo4j = neo4j_client or get_neo4j_http_client()
        self.llm = llm_service
        self.cache = cache_service

        logger.info("DocumentStructureService initialized")

    async def extract_document_structure(
        self, request: DocumentStructureRequest
    ) -> DocumentStructureResponse:
        """
        Extract document structure and store in Neo4j.

        Args:
            request: DocumentStructureRequest with document_id and options

        Returns:
            DocumentStructureResponse with extracted structure

        Raises:
            DocumentNotFoundError: If document cannot be found
            DocumentStructureError: If extraction fails
        """
        document_id = request.document_id
        logger.info("Extracting document structure", document_id=document_id)

        try:
            # Get document content
            document_content = request.document_content
            if not document_content:
                document_content = await self._get_document_content(document_id)

            if not document_content:
                raise DocumentNotFoundError(f"Document {document_id} not found or has no content")

            # Get document title
            document_title = await self._get_document_title(document_id)

            # Extract sections
            sections = []
            if request.extract_sections:
                sections = await self._extract_sections(
                    document_content,
                    document_id,
                    max_depth=request.max_depth,
                )

            # Extract definitions
            definitions = []
            if request.extract_definitions:
                definitions = await self._extract_definitions(
                    document_content,
                    document_id,
                    sections,
                )

            # Extract cross-references
            cross_references = []
            if request.extract_cross_refs:
                cross_references = await self._extract_cross_references(
                    document_content,
                    sections,
                )

            # Extract citations
            citations = await self._extract_citations(document_content, document_id)

            # Store structure in Neo4j
            await self._store_structure_in_graph(
                document_id=document_id,
                sections=sections,
                definitions=definitions,
                cross_references=cross_references,
                citations=citations,
            )

            # Calculate structure depth
            structure_depth = max([s.level for s in sections], default=0)

            response = DocumentStructureResponse(
                document_id=document_id,
                title=document_title,
                sections=[SectionNode(**s) if isinstance(s, dict) else s for s in sections],
                definitions=[DefinedTermNode(**d) if isinstance(d, dict) else d for d in definitions],
                cross_references=[CrossReference(**c) if isinstance(c, dict) else c for c in cross_references],
                citations=[CitationNode(**c) if isinstance(c, dict) else c for c in citations],
                structure_depth=structure_depth,
            )

            logger.info(
                "Document structure extracted",
                document_id=document_id,
                section_count=len(sections),
                definition_count=len(definitions),
                cross_ref_count=len(cross_references),
            )

            return response

        except DocumentNotFoundError:
            raise
        except Neo4jConnectionError as e:
            logger.error("Neo4j connection error", error=str(e))
            raise DocumentStructureError(f"Database connection failed: {e}")
        except Exception as e:
            logger.error("Structure extraction failed", document_id=document_id, error=str(e))
            raise DocumentStructureError(f"Failed to extract structure: {e}")

    async def get_document_structure(
        self, document_id: str
    ) -> DocumentStructureResponse:
        """
        Retrieve existing document structure from Neo4j.

        Args:
            document_id: Document ID to retrieve structure for

        Returns:
            DocumentStructureResponse with document structure

        Raises:
            DocumentNotFoundError: If document structure not found
        """
        # Check cache first
        cache_key = f"doc_structure:{document_id}"
        if self.cache:
            try:
                cached = await self.cache.get(cache_key)
                if cached:
                    logger.info("Document structure cache hit", document_id=document_id)
                    return DocumentStructureResponse(**cached)
            except Exception as e:
                logger.warning("Cache lookup failed", error=str(e))

        try:
            # Get document title
            document_title = await self._get_document_title(document_id)
            if not document_title:
                raise DocumentNotFoundError(f"Document {document_id} not found")

            # Get sections
            sections = await self._get_sections_from_graph(document_id)

            # Get definitions
            definitions = await self._get_definitions_from_graph(document_id)

            # Get cross-references
            cross_references = await self._get_cross_references_from_graph(document_id)

            # Get citations
            citations = await self._get_citations_from_graph(document_id)

            structure_depth = max([s.level for s in sections], default=0)

            response = DocumentStructureResponse(
                document_id=document_id,
                title=document_title,
                sections=sections,
                definitions=definitions,
                cross_references=cross_references,
                citations=citations,
                structure_depth=structure_depth,
            )

            # Cache result
            if self.cache:
                try:
                    await self.cache.set(cache_key, response.model_dump(), ttl=self.CACHE_TTL)
                except Exception as e:
                    logger.warning("Cache set failed", error=str(e))

            return response

        except DocumentNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get structure", document_id=document_id, error=str(e))
            raise DocumentStructureError(f"Failed to retrieve structure: {e}")

    async def smart_retrieve(
        self, request: SmartRetrievalRequest
    ) -> SmartRetrievalResponse:
        """
        Perform context-aware retrieval with cross-reference following.

        Args:
            request: SmartRetrievalRequest with query and options

        Returns:
            SmartRetrievalResponse with matched sections and context
        """
        document_id = request.document_id
        query = request.query

        logger.info("Smart retrieval", document_id=document_id, query=query[:50])

        try:
            # Find matching sections using full-text search
            matching_sections = await self._search_sections(document_id, query)

            # Get parent context if requested
            parent_context = []
            if request.include_parent_context and matching_sections:
                parent_context = await self._get_parent_context(
                    document_id,
                    [s.id for s in matching_sections],
                )

            # Follow cross-references if requested
            cross_referenced_sections = []
            if request.follow_cross_refs and matching_sections:
                cross_referenced_sections = await self._follow_cross_references(
                    document_id,
                    [s.id for s in matching_sections],
                    max_depth=request.max_cross_ref_depth,
                )

            # Get relevant definitions if requested
            relevant_definitions = []
            if request.include_definitions and matching_sections:
                relevant_definitions = await self._get_relevant_definitions(
                    document_id,
                    matching_sections,
                )

            # Build breadcrumb
            breadcrumb = self._build_breadcrumb(parent_context, matching_sections)

            response = SmartRetrievalResponse(
                sections=matching_sections,
                parent_context=parent_context,
                cross_referenced_sections=cross_referenced_sections,
                relevant_definitions=relevant_definitions,
                breadcrumb=breadcrumb,
            )

            logger.info(
                "Smart retrieval complete",
                matching_count=len(matching_sections),
                cross_ref_count=len(cross_referenced_sections),
            )

            return response

        except Exception as e:
            logger.error("Smart retrieval failed", error=str(e))
            raise DocumentStructureError(f"Smart retrieval failed: {e}")

    async def get_cross_references(
        self,
        document_id: str,
        section_id: Optional[str] = None,
    ) -> List[CrossReference]:
        """
        Get cross-references for a document or specific section.

        Args:
            document_id: Document ID
            section_id: Optional section ID to filter by

        Returns:
            List of CrossReference objects
        """
        try:
            if section_id:
                query = """
                MATCH (s:Section {id: $section_id, document_id: $document_id})
                      -[r:REFERENCES_SECTION]->(target:Section)
                RETURN s.id as from_section_id,
                       s.number as from_section_number,
                       target.id as to_section_id,
                       target.number as to_section_number,
                       r.reference_text as reference_text
                """
                params = {"document_id": document_id, "section_id": section_id}
            else:
                query = """
                MATCH (s:Section {document_id: $document_id})
                      -[r:REFERENCES_SECTION]->(target:Section)
                RETURN s.id as from_section_id,
                       s.number as from_section_number,
                       target.id as to_section_id,
                       target.number as to_section_number,
                       r.reference_text as reference_text
                """
                params = {"document_id": document_id}

            results = await self.neo4j.execute_query(query, params)

            return [
                CrossReference(
                    from_section_id=r["from_section_id"],
                    from_section_number=r["from_section_number"],
                    to_section_id=r["to_section_id"],
                    to_section_number=r["to_section_number"],
                    reference_text=r.get("reference_text", ""),
                )
                for r in results
            ]

        except Exception as e:
            logger.error("Failed to get cross-references", error=str(e))
            raise DocumentStructureError(f"Failed to get cross-references: {e}")

    # =========================================================================
    # INTERNAL METHODS - Document Content
    # =========================================================================

    async def _get_document_content(self, document_id: str) -> Optional[str]:
        """Get document content from storage or graph."""
        try:
            query = """
            MATCH (d:Document {id: $document_id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            WITH d, c ORDER BY c.position
            RETURN d.content as content,
                   d.title as title,
                   COLLECT(c.content) as chunks
            """
            results = await self.neo4j.execute_query(query, {"document_id": document_id})

            if not results:
                return None

            result = results[0]

            # Return full content if available
            if result.get("content"):
                return result["content"]

            # Otherwise, concatenate chunks
            chunks = result.get("chunks", [])
            if chunks:
                return "\n\n".join(chunks)

            return None

        except Exception as e:
            logger.warning("Could not get document content", document_id=document_id, error=str(e))
            return None

    async def _get_document_title(self, document_id: str) -> str:
        """Get document title from graph."""
        try:
            query = """
            MATCH (d:Document {id: $document_id})
            RETURN d.title as title
            """
            results = await self.neo4j.execute_query(query, {"document_id": document_id})

            if results:
                return results[0].get("title", f"Document {document_id}")

            return f"Document {document_id}"

        except Exception:
            return f"Document {document_id}"

    # =========================================================================
    # INTERNAL METHODS - Structure Extraction
    # =========================================================================

    async def _extract_sections(
        self,
        content: str,
        document_id: str,
        max_depth: int = 5,
    ) -> List[SectionNode]:
        """
        Extract document sections using pattern matching and optional LLM.

        Uses regex patterns to identify common section patterns:
        - Numbered sections (1., 1.1., 1.1.1.)
        - Article/Section/Clause headers
        - Roman numerals (I., II., III.)
        """
        sections = []

        # Pattern for numbered sections (1., 1.1, 1.1.1, etc.)
        # Matches: "1. Title", "1.1 Title", "1.1.1. Title"
        section_pattern = re.compile(
            r'^(?P<number>\d+(?:\.\d+)*\.?)\s+(?P<title>[^\n]+)',
            re.MULTILINE
        )

        # Pattern for ARTICLE/SECTION/CLAUSE headers
        header_pattern = re.compile(
            r'^(?P<type>ARTICLE|SECTION|CLAUSE)\s+(?P<number>[\dIVXLCDM]+)[:\.\s]+(?P<title>[^\n]+)',
            re.MULTILINE | re.IGNORECASE
        )

        # Extract numbered sections
        for match in section_pattern.finditer(content):
            number = match.group("number").rstrip(".")
            title = match.group("title").strip()
            level = number.count(".") + 1

            if level <= max_depth:
                section_id = f"{document_id}_sec_{number.replace('.', '_')}"
                content_start = match.end()
                content_preview = content[content_start:content_start + 200].strip()

                sections.append(SectionNode(
                    id=section_id,
                    document_id=document_id,
                    title=title,
                    number=number,
                    level=level,
                    content_preview=content_preview[:200] if content_preview else None,
                    child_count=0,
                    reference_count=0,
                ))

        # Extract ARTICLE/SECTION/CLAUSE headers
        for match in header_pattern.finditer(content):
            header_type = match.group("type").upper()
            number = match.group("number")
            title = match.group("title").strip()

            # Determine level based on header type
            level_map = {"ARTICLE": 1, "SECTION": 2, "CLAUSE": 3}
            level = level_map.get(header_type, 2)

            section_id = f"{document_id}_{header_type.lower()}_{number}"
            content_start = match.end()
            content_preview = content[content_start:content_start + 200].strip()

            sections.append(SectionNode(
                id=section_id,
                document_id=document_id,
                title=title,
                number=f"{header_type} {number}",
                level=level,
                content_preview=content_preview[:200] if content_preview else None,
                child_count=0,
                reference_count=0,
            ))

        # Update child counts
        self._update_child_counts(sections)

        logger.info("Extracted sections", count=len(sections))
        return sections

    def _update_child_counts(self, sections: List[SectionNode]) -> None:
        """Update child counts for hierarchical sections."""
        # Sort by number for proper hierarchy detection
        sorted_sections = sorted(sections, key=lambda s: s.number)

        for i, section in enumerate(sorted_sections):
            child_count = 0
            prefix = section.number + "."

            for other in sorted_sections[i + 1:]:
                if other.number.startswith(prefix):
                    if other.level == section.level + 1:
                        child_count += 1
                elif not other.number.startswith(section.number):
                    break

            section.child_count = child_count

    async def _extract_definitions(
        self,
        content: str,
        document_id: str,
        sections: List[SectionNode],
    ) -> List[DefinedTermNode]:
        """
        Extract defined terms from document content.

        Looks for common definition patterns:
        - "Term" means/shall mean...
        - Term: definition
        - "Term" (or "Alternate Term")
        """
        definitions = []

        # Pattern: "Term" means/shall mean...
        def_pattern1 = re.compile(
            r'"(?P<term>[^"]+)"\s+(?:means|shall\s+mean|is\s+defined\s+as)\s+(?P<definition>[^.]+\.)',
            re.IGNORECASE
        )

        # Pattern: Term: definition
        def_pattern2 = re.compile(
            r'^(?P<term>[A-Z][A-Za-z\s]+):\s+(?P<definition>[^\n]+)',
            re.MULTILINE
        )

        for match in def_pattern1.finditer(content):
            term = match.group("term")
            definition = match.group("definition").strip()

            # Find which section contains this definition
            section_id = self._find_containing_section(match.start(), content, sections)

            definitions.append(DefinedTermNode(
                id=f"{document_id}_def_{self._normalize_term(term)}",
                document_id=document_id,
                term=term,
                definition=definition,
                section_id=section_id,
                usage_count=content.lower().count(term.lower()),
            ))

        for match in def_pattern2.finditer(content):
            term = match.group("term").strip()
            definition = match.group("definition").strip()

            # Skip very short or common terms
            if len(term) < 3 or term.lower() in ["the", "and", "for", "but", "not"]:
                continue

            section_id = self._find_containing_section(match.start(), content, sections)

            definitions.append(DefinedTermNode(
                id=f"{document_id}_def_{self._normalize_term(term)}",
                document_id=document_id,
                term=term,
                definition=definition,
                section_id=section_id,
                usage_count=content.lower().count(term.lower()),
            ))

        logger.info("Extracted definitions", count=len(definitions))
        return definitions

    def _normalize_term(self, term: str) -> str:
        """Normalize term for ID generation."""
        return re.sub(r'[^a-z0-9]+', '_', term.lower()).strip('_')

    def _find_containing_section(
        self,
        position: int,
        content: str,
        sections: List[SectionNode],
    ) -> Optional[str]:
        """Find which section contains a given position in the content."""
        # Find section headers and their positions
        section_positions = []
        for section in sections:
            pattern = re.escape(section.number) + r'\s+' + re.escape(section.title[:20])
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                section_positions.append((match.start(), section.id))

        # Sort by position
        section_positions.sort(key=lambda x: x[0])

        # Find containing section
        containing_section = None
        for pos, section_id in section_positions:
            if pos > position:
                break
            containing_section = section_id

        return containing_section

    async def _extract_cross_references(
        self,
        content: str,
        sections: List[SectionNode],
    ) -> List[CrossReference]:
        """
        Extract cross-references between sections.

        Patterns:
        - "See Section X.X"
        - "as defined in Section X"
        - "pursuant to Article X"
        - "(Section X.X)"
        """
        cross_refs = []

        # Create section number to section mapping
        section_map = {s.number: s for s in sections}

        # Pattern for cross-references
        ref_patterns = [
            re.compile(r'[Ss]ee\s+[Ss]ection\s+(?P<number>[\d.]+)', re.IGNORECASE),
            re.compile(r'as\s+(?:defined|set\s+forth)\s+in\s+[Ss]ection\s+(?P<number>[\d.]+)', re.IGNORECASE),
            re.compile(r'pursuant\s+to\s+(?:Article|Section)\s+(?P<number>[\d.]+)', re.IGNORECASE),
            re.compile(r'\([Ss]ection\s+(?P<number>[\d.]+)\)', re.IGNORECASE),
        ]

        for pattern in ref_patterns:
            for match in pattern.finditer(content):
                target_number = match.group("number").rstrip(".")
                reference_text = match.group(0)

                # Find target section
                target_section = section_map.get(target_number)
                if not target_section:
                    continue

                # Find source section
                source_section_id = self._find_containing_section(
                    match.start(), content, sections
                )
                if not source_section_id:
                    continue

                # Find source section object
                source_section = next(
                    (s for s in sections if s.id == source_section_id),
                    None
                )
                if not source_section:
                    continue

                cross_refs.append(CrossReference(
                    from_section_id=source_section.id,
                    from_section_number=source_section.number,
                    to_section_id=target_section.id,
                    to_section_number=target_section.number,
                    reference_text=reference_text,
                ))

        # Update reference counts
        for section in sections:
            section.reference_count = sum(
                1 for ref in cross_refs if ref.from_section_id == section.id
            )

        logger.info("Extracted cross-references", count=len(cross_refs))
        return cross_refs

    async def _extract_citations(
        self,
        content: str,
        document_id: str,
    ) -> List[CitationNode]:
        """
        Extract external citations (statutes, cases, regulations).

        Patterns:
        - U.S.C. citations (e.g., "42 U.S.C. § 1234")
        - CFR citations (e.g., "12 CFR Part 1026")
        - Case citations (e.g., "Smith v. Jones, 123 F.3d 456")
        """
        citations = []

        # USC pattern
        usc_pattern = re.compile(
            r'(?P<title>\d+)\s+U\.?S\.?C\.?\s+§?\s*(?P<section>\d+)',
            re.IGNORECASE
        )

        # CFR pattern
        cfr_pattern = re.compile(
            r'(?P<title>\d+)\s+C\.?F\.?R\.?\s+(?:Part\s+)?(?P<part>[\d.]+)',
            re.IGNORECASE
        )

        # Case citation pattern (simplified)
        case_pattern = re.compile(
            r'(?P<case>[A-Z][a-z]+\s+v\.\s+[A-Z][a-z]+),\s+(?P<citation>\d+\s+[A-Z][a-z.]+\s+\d+)',
            re.IGNORECASE
        )

        for match in usc_pattern.finditer(content):
            title = match.group("title")
            section = match.group("section")
            citations.append(CitationNode(
                id=f"{document_id}_cite_usc_{title}_{section}",
                document_id=document_id,
                type="statute",
                reference=f"{title} U.S.C. § {section}",
                section_id=None,
            ))

        for match in cfr_pattern.finditer(content):
            title = match.group("title")
            part = match.group("part")
            citations.append(CitationNode(
                id=f"{document_id}_cite_cfr_{title}_{part.replace('.', '_')}",
                document_id=document_id,
                type="regulation",
                reference=f"{title} CFR Part {part}",
                section_id=None,
            ))

        for match in case_pattern.finditer(content):
            case = match.group("case")
            citation = match.group("citation")
            case_id = self._normalize_term(case)
            citations.append(CitationNode(
                id=f"{document_id}_cite_case_{case_id}",
                document_id=document_id,
                type="case",
                reference=f"{case}, {citation}",
                section_id=None,
            ))

        logger.info("Extracted citations", count=len(citations))
        return citations

    # =========================================================================
    # INTERNAL METHODS - Graph Storage
    # =========================================================================

    async def _store_structure_in_graph(
        self,
        document_id: str,
        sections: List[SectionNode],
        definitions: List[DefinedTermNode],
        cross_references: List[CrossReference],
        citations: List[CitationNode],
    ) -> None:
        """Store extracted structure in Neo4j graph."""
        try:
            # Store sections
            for section in sections:
                section_dict = section.model_dump() if hasattr(section, 'model_dump') else section
                await self.neo4j.execute_query(
                    """
                    MERGE (s:Section {id: $id})
                    SET s += $props
                    WITH s
                    MATCH (d:Document {id: $document_id})
                    MERGE (d)-[:HAS_SECTION]->(s)
                    """,
                    {
                        "id": section_dict["id"],
                        "document_id": document_id,
                        "props": {
                            "document_id": section_dict.get("document_id"),
                            "title": section_dict["title"],
                            "number": section_dict["number"],
                            "level": section_dict["level"],
                            "content_preview": section_dict.get("content_preview"),
                            "child_count": section_dict.get("child_count", 0),
                            "reference_count": section_dict.get("reference_count", 0),
                        },
                    }
                )

            # Store section hierarchy (parent-child relationships)
            await self._store_section_hierarchy(sections)

            # Store definitions
            for definition in definitions:
                def_dict = definition.model_dump() if hasattr(definition, 'model_dump') else definition
                await self.neo4j.execute_query(
                    """
                    MERGE (dt:DefinedTerm {id: $id})
                    SET dt += $props
                    WITH dt
                    MATCH (d:Document {id: $document_id})
                    MERGE (d)-[:DEFINES_TERM]->(dt)
                    """,
                    {
                        "id": def_dict["id"],
                        "document_id": document_id,
                        "props": {
                            "document_id": def_dict["document_id"],
                            "term": def_dict["term"],
                            "definition": def_dict["definition"],
                            "section_id": def_dict.get("section_id"),
                            "usage_count": def_dict.get("usage_count", 0),
                        },
                    }
                )

            # Store cross-references
            for ref in cross_references:
                ref_dict = ref.model_dump() if hasattr(ref, 'model_dump') else ref
                await self.neo4j.execute_query(
                    """
                    MATCH (from:Section {id: $from_id})
                    MATCH (to:Section {id: $to_id})
                    MERGE (from)-[r:REFERENCES_SECTION]->(to)
                    SET r.reference_text = $reference_text
                    """,
                    {
                        "from_id": ref_dict["from_section_id"],
                        "to_id": ref_dict["to_section_id"],
                        "reference_text": ref_dict.get("reference_text", ""),
                    }
                )

            # Store citations
            for citation in citations:
                cite_dict = citation.model_dump() if hasattr(citation, 'model_dump') else citation
                await self.neo4j.execute_query(
                    """
                    MERGE (c:Citation {id: $id})
                    SET c += $props
                    WITH c
                    MATCH (d:Document {id: $document_id})
                    MERGE (d)-[:HAS_CITATION]->(c)
                    """,
                    {
                        "id": cite_dict["id"],
                        "document_id": document_id,
                        "props": {
                            "document_id": cite_dict["document_id"],
                            "type": cite_dict["type"],
                            "reference": cite_dict["reference"],
                            "section_id": cite_dict.get("section_id"),
                        },
                    }
                )

            logger.info("Structure stored in graph", document_id=document_id)

        except Exception as e:
            logger.error("Failed to store structure", document_id=document_id, error=str(e))
            raise

    async def _store_section_hierarchy(self, sections: List[SectionNode]) -> None:
        """Store parent-child relationships between sections."""
        sorted_sections = sorted(sections, key=lambda s: s.number)

        for section in sorted_sections:
            # Find parent section
            parts = section.number.split(".")
            if len(parts) > 1:
                parent_number = ".".join(parts[:-1])
                parent = next((s for s in sorted_sections if s.number == parent_number), None)

                if parent:
                    await self.neo4j.execute_query(
                        """
                        MATCH (parent:Section {id: $parent_id})
                        MATCH (child:Section {id: $child_id})
                        MERGE (parent)-[:HAS_SUBSECTION]->(child)
                        MERGE (child)-[:PARENT_SECTION]->(parent)
                        """,
                        {"parent_id": parent.id, "child_id": section.id}
                    )

    # =========================================================================
    # INTERNAL METHODS - Graph Retrieval
    # =========================================================================

    async def _get_sections_from_graph(self, document_id: str) -> List[SectionNode]:
        """Retrieve sections from Neo4j."""
        query = """
        MATCH (d:Document {id: $document_id})-[:HAS_SECTION]->(s:Section)
        RETURN s.id as id,
               s.document_id as document_id,
               s.title as title,
               s.number as number,
               s.level as level,
               s.content_preview as content_preview,
               s.child_count as child_count,
               s.reference_count as reference_count
        ORDER BY s.number
        """
        results = await self.neo4j.execute_query(query, {"document_id": document_id})

        return [
            SectionNode(
                id=r["id"],
                document_id=r.get("document_id"),
                title=r["title"],
                number=r["number"],
                level=r.get("level", 1),
                content_preview=r.get("content_preview"),
                child_count=r.get("child_count", 0),
                reference_count=r.get("reference_count", 0),
            )
            for r in results
        ]

    async def _get_definitions_from_graph(self, document_id: str) -> List[DefinedTermNode]:
        """Retrieve definitions from Neo4j."""
        query = """
        MATCH (d:Document {id: $document_id})-[:DEFINES_TERM]->(dt:DefinedTerm)
        RETURN dt.id as id,
               dt.document_id as document_id,
               dt.term as term,
               dt.definition as definition,
               dt.section_id as section_id,
               dt.usage_count as usage_count
        ORDER BY dt.term
        """
        results = await self.neo4j.execute_query(query, {"document_id": document_id})

        return [
            DefinedTermNode(
                id=r["id"],
                document_id=r["document_id"],
                term=r["term"],
                definition=r["definition"],
                section_id=r.get("section_id"),
                usage_count=r.get("usage_count", 0),
            )
            for r in results
        ]

    async def _get_cross_references_from_graph(
        self, document_id: str
    ) -> List[CrossReference]:
        """Retrieve cross-references from Neo4j."""
        query = """
        MATCH (s:Section {document_id: $document_id})
              -[r:REFERENCES_SECTION]->(target:Section)
        RETURN s.id as from_section_id,
               s.number as from_section_number,
               target.id as to_section_id,
               target.number as to_section_number,
               r.reference_text as reference_text
        """
        results = await self.neo4j.execute_query(query, {"document_id": document_id})

        return [
            CrossReference(
                from_section_id=r["from_section_id"],
                from_section_number=r["from_section_number"],
                to_section_id=r["to_section_id"],
                to_section_number=r["to_section_number"],
                reference_text=r.get("reference_text", ""),
            )
            for r in results
        ]

    async def _get_citations_from_graph(self, document_id: str) -> List[CitationNode]:
        """Retrieve citations from Neo4j."""
        query = """
        MATCH (d:Document {id: $document_id})-[:HAS_CITATION]->(c:Citation)
        RETURN c.id as id,
               c.document_id as document_id,
               c.type as type,
               c.reference as reference,
               c.section_id as section_id
        ORDER BY c.type, c.reference
        """
        results = await self.neo4j.execute_query(query, {"document_id": document_id})

        return [
            CitationNode(
                id=r["id"],
                document_id=r["document_id"],
                type=r["type"],
                reference=r["reference"],
                section_id=r.get("section_id"),
            )
            for r in results
        ]

    # =========================================================================
    # INTERNAL METHODS - Smart Retrieval
    # =========================================================================

    async def _search_sections(
        self, document_id: str, query: str
    ) -> List[SectionNode]:
        """Search sections using full-text search."""
        # Use full-text index if available, otherwise pattern matching
        cypher = """
        MATCH (s:Section {document_id: $document_id})
        WHERE s.title CONTAINS $query
           OR s.content_preview CONTAINS $query
        RETURN s.id as id,
               s.document_id as document_id,
               s.title as title,
               s.number as number,
               s.level as level,
               s.content_preview as content_preview,
               s.child_count as child_count,
               s.reference_count as reference_count
        LIMIT 10
        """
        results = await self.neo4j.execute_query(
            cypher,
            {"document_id": document_id, "query": query}
        )

        return [
            SectionNode(
                id=r["id"],
                document_id=r.get("document_id"),
                title=r["title"],
                number=r["number"],
                level=r.get("level", 1),
                content_preview=r.get("content_preview"),
                child_count=r.get("child_count", 0),
                reference_count=r.get("reference_count", 0),
            )
            for r in results
        ]

    async def _get_parent_context(
        self, document_id: str, section_ids: List[str]
    ) -> List[SectionNode]:
        """Get parent sections for context."""
        if not section_ids:
            return []

        query = """
        UNWIND $section_ids as section_id
        MATCH (s:Section {id: section_id})-[:PARENT_SECTION*1..3]->(parent:Section)
        RETURN DISTINCT parent.id as id,
               parent.document_id as document_id,
               parent.title as title,
               parent.number as number,
               parent.level as level,
               parent.content_preview as content_preview,
               parent.child_count as child_count,
               parent.reference_count as reference_count
        ORDER BY parent.level
        """
        results = await self.neo4j.execute_query(query, {"section_ids": section_ids})

        return [
            SectionNode(
                id=r["id"],
                document_id=r.get("document_id"),
                title=r["title"],
                number=r["number"],
                level=r.get("level", 1),
                content_preview=r.get("content_preview"),
                child_count=r.get("child_count", 0),
                reference_count=r.get("reference_count", 0),
            )
            for r in results
        ]

    async def _follow_cross_references(
        self,
        document_id: str,
        section_ids: List[str],
        max_depth: int = 2,
    ) -> List[SectionNode]:
        """Follow cross-references to find related sections."""
        if not section_ids:
            return []

        query = """
        UNWIND $section_ids as section_id
        MATCH (s:Section {id: section_id})-[:REFERENCES_SECTION*1..$max_depth]->(target:Section)
        RETURN DISTINCT target.id as id,
               target.document_id as document_id,
               target.title as title,
               target.number as number,
               target.level as level,
               target.content_preview as content_preview,
               target.child_count as child_count,
               target.reference_count as reference_count
        LIMIT 20
        """
        # Note: Can't use parameter for variable-length path, so we cap at max_depth=5
        results = await self.neo4j.execute_query(
            query.replace("$max_depth", str(min(max_depth, 5))),
            {"section_ids": section_ids}
        )

        return [
            SectionNode(
                id=r["id"],
                document_id=r.get("document_id"),
                title=r["title"],
                number=r["number"],
                level=r.get("level", 1),
                content_preview=r.get("content_preview"),
                child_count=r.get("child_count", 0),
                reference_count=r.get("reference_count", 0),
            )
            for r in results
        ]

    async def _get_relevant_definitions(
        self,
        document_id: str,
        sections: List[SectionNode],
    ) -> List[DefinedTermNode]:
        """Get definitions relevant to the given sections."""
        section_ids = [s.id for s in sections]

        if not section_ids:
            return []

        query = """
        MATCH (dt:DefinedTerm {document_id: $document_id})
        WHERE dt.section_id IN $section_ids
        RETURN dt.id as id,
               dt.document_id as document_id,
               dt.term as term,
               dt.definition as definition,
               dt.section_id as section_id,
               dt.usage_count as usage_count
        """
        results = await self.neo4j.execute_query(
            query,
            {"document_id": document_id, "section_ids": section_ids}
        )

        return [
            DefinedTermNode(
                id=r["id"],
                document_id=r["document_id"],
                term=r["term"],
                definition=r["definition"],
                section_id=r.get("section_id"),
                usage_count=r.get("usage_count", 0),
            )
            for r in results
        ]

    def _build_breadcrumb(
        self,
        parent_context: List[SectionNode],
        matching_sections: List[SectionNode],
    ) -> List[str]:
        """Build navigation breadcrumb from parent context and matching sections."""
        breadcrumb = []

        # Sort parent context by level
        sorted_parents = sorted(parent_context, key=lambda s: s.level)

        for parent in sorted_parents:
            breadcrumb.append(f"{parent.number} {parent.title}")

        # Add first matching section
        if matching_sections:
            section = matching_sections[0]
            breadcrumb.append(f"{section.number} {section.title}")

        return breadcrumb


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_document_structure_service: Optional[DocumentStructureService] = None


def get_document_structure_service() -> DocumentStructureService:
    """Get or create singleton DocumentStructureService instance."""
    global _document_structure_service
    if _document_structure_service is None:
        _document_structure_service = DocumentStructureService()
    return _document_structure_service


async def close_document_structure_service() -> None:
    """Close the singleton DocumentStructureService instance."""
    global _document_structure_service
    if _document_structure_service is not None:
        # Close Neo4j client if we own it
        _document_structure_service = None
