# app/services/graph_result_formatter.py
"""
Graph Result Formatter for CKO Chat UI.

Task 109: Graph Agent - Graph Result Formatter
Feature: 005-graph-agent

Formats graph query results for display in the chat interface with
expandable sections, summaries, and visualization data.
"""

import structlog
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from app.models.graph_agent import (
    Customer360Response,
    CustomerNode,
    DocumentNode,
    TicketNode,
    OrderNode,
    InteractionNode,
    DocumentStructureResponse,
    SectionNode,
    DefinedTermNode,
    CrossReference,
    SmartRetrievalResponse,
    GraphEnhancedRAGResponse,
    GraphExpansionResult,
    ChunkNode,
    EntityNode,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# OUTPUT FORMAT TYPES
# =============================================================================

class OutputFormat(str, Enum):
    """Output format types for different UI contexts."""
    CHAT = "chat"  # Rich chat UI with expandable sections
    MARKDOWN = "markdown"  # Markdown for simple rendering
    JSON = "json"  # Raw JSON for API responses
    SUMMARY = "summary"  # Brief summary only


class SectionType(str, Enum):
    """Section types for expandable content."""
    PROFILE = "profile"
    DOCUMENTS = "documents"
    TICKETS = "tickets"
    ORDERS = "orders"
    INTERACTIONS = "interactions"
    SECTIONS = "sections"
    CROSS_REFERENCES = "cross_references"
    DEFINITIONS = "definitions"
    ENTITIES = "entities"
    CONTEXT = "context"
    GRAPH = "graph"


@dataclass
class FormattedSection:
    """A formatted section for display."""
    title: str
    type: SectionType
    content: Any
    expanded: bool = False
    count: Optional[int] = None
    icon: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "title": self.title,
            "type": self.type.value,
            "content": self.content,
            "expanded": self.expanded,
        }
        if self.count is not None:
            result["count"] = self.count
        if self.icon:
            result["icon"] = self.icon
        return result


# =============================================================================
# GRAPH RESULT FORMATTER
# =============================================================================

class GraphResultFormatter:
    """
    Formats graph query results for the CKO Chat UI.

    Creates structured responses with:
    - Natural language summaries
    - Expandable sections
    - Source links
    - Graph visualization data
    """

    def __init__(self, output_format: OutputFormat = OutputFormat.CHAT):
        """
        Initialize the formatter.

        Args:
            output_format: Default output format
        """
        self.output_format = output_format
        logger.info("GraphResultFormatter initialized", format=output_format.value)

    # =========================================================================
    # CUSTOMER 360 FORMATTING
    # =========================================================================

    def format_customer_360(
        self,
        response: Customer360Response,
        output_format: Optional[OutputFormat] = None,
    ) -> Dict[str, Any]:
        """
        Format Customer 360 response for chat UI.

        Args:
            response: Customer360Response from service
            output_format: Optional format override

        Returns:
            Formatted response dict
        """
        fmt = output_format or self.output_format

        if fmt == OutputFormat.MARKDOWN:
            return self._format_customer_360_markdown(response)
        elif fmt == OutputFormat.SUMMARY:
            return {
                "type": "customer_360",
                "summary": self._generate_customer_summary(response),
            }
        elif fmt == OutputFormat.JSON:
            return {"type": "customer_360", "data": response.model_dump()}

        # Default: CHAT format with expandable sections
        sections = []

        # Customer Profile (always expanded)
        if response.customer:
            sections.append(FormattedSection(
                title="Customer Profile",
                type=SectionType.PROFILE,
                content=self._format_customer_profile(response.customer),
                expanded=True,
                icon="user",
            ))

        # Documents
        if response.documents:
            sections.append(FormattedSection(
                title=f"Documents ({len(response.documents)})",
                type=SectionType.DOCUMENTS,
                content=self._format_document_list(response.documents),
                expanded=False,
                count=len(response.documents),
                icon="file-text",
            ))

        # Support Tickets
        if response.tickets:
            sections.append(FormattedSection(
                title=f"Support Tickets ({len(response.tickets)})",
                type=SectionType.TICKETS,
                content=self._format_ticket_list(response.tickets),
                expanded=False,
                count=len(response.tickets),
                icon="ticket",
            ))

        # Orders
        if response.orders:
            sections.append(FormattedSection(
                title=f"Orders ({len(response.orders)})",
                type=SectionType.ORDERS,
                content=self._format_order_list(response.orders),
                expanded=False,
                count=len(response.orders),
                icon="shopping-cart",
            ))

        # Interactions
        if response.interactions:
            sections.append(FormattedSection(
                title=f"Interactions ({len(response.interactions)})",
                type=SectionType.INTERACTIONS,
                content=self._format_interaction_list(response.interactions),
                expanded=False,
                count=len(response.interactions),
                icon="message-circle",
            ))

        return {
            "type": "customer_360",
            "content": {
                "summary": self._generate_customer_summary(response),
                "sections": [s.to_dict() for s in sections],
                "relationship_count": response.relationship_count,
                "generated_at": response.generated_at.isoformat(),
            },
        }

    def _generate_customer_summary(self, response: Customer360Response) -> str:
        """Generate natural language summary of customer data."""
        customer = response.customer
        parts = []

        # Customer name and type
        if customer.name:
            parts.append(f"**{customer.name}**")
            if customer.type:
                parts.append(f"({customer.type})")

        # Industry
        if customer.industry:
            parts.append(f"in the {customer.industry} industry")

        # Summary sentence
        summary = " ".join(parts) + "."

        # Stats
        stats = []
        if response.documents:
            stats.append(f"{len(response.documents)} documents")
        if response.tickets:
            stats.append(f"{len(response.tickets)} tickets")
        if response.orders:
            stats.append(f"{len(response.orders)} orders")
        if response.interactions:
            stats.append(f"{len(response.interactions)} interactions")

        if stats:
            summary += f" Related data: {', '.join(stats)}."

        return summary

    def _format_customer_profile(self, customer: CustomerNode) -> Dict[str, Any]:
        """Format customer profile data."""
        return {
            "id": customer.id,
            "name": customer.name,
            "type": customer.type.value if hasattr(customer.type, 'value') else str(customer.type),
            "industry": customer.industry,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
            "metadata": customer.metadata or {},
        }

    def _format_document_list(self, documents: List[DocumentNode]) -> List[Dict[str, Any]]:
        """Format document list with links."""
        return [
            {
                "id": doc.id,
                "title": doc.title,
                "type": doc.type,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "link": f"/documents/{doc.id}",
            }
            for doc in documents
        ]

    def _format_ticket_list(self, tickets: List[TicketNode]) -> List[Dict[str, Any]]:
        """Format ticket list."""
        return [
            {
                "id": ticket.id,
                "subject": ticket.subject,
                "status": ticket.status.value if ticket.status else None,
                "priority": ticket.priority.value if ticket.priority else None,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "link": f"/tickets/{ticket.id}",
            }
            for ticket in tickets
        ]

    def _format_order_list(self, orders: List[OrderNode]) -> List[Dict[str, Any]]:
        """Format order list."""
        return [
            {
                "id": order.id,
                "status": order.status.value if order.status else None,
                "total_amount": order.total_amount,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "link": f"/orders/{order.id}",
            }
            for order in orders
        ]

    def _format_interaction_list(
        self,
        interactions: List[InteractionNode],
    ) -> List[Dict[str, Any]]:
        """Format interaction list."""
        return [
            {
                "id": interaction.id,
                "type": interaction.type.value if interaction.type else None,
                "created_at": interaction.created_at.isoformat() if interaction.created_at else None,
                "summary": interaction.summary,
            }
            for interaction in interactions
        ]

    def _format_customer_360_markdown(
        self,
        response: Customer360Response,
    ) -> Dict[str, Any]:
        """Format Customer 360 as markdown."""
        lines = []
        customer = response.customer

        # Header
        lines.append(f"## Customer: {customer.name}")
        lines.append("")

        # Profile
        lines.append("### Profile")
        type_val = customer.type.value if hasattr(customer.type, 'value') else str(customer.type) if customer.type else 'N/A'
        lines.append(f"- **Type:** {type_val}")
        lines.append(f"- **Industry:** {customer.industry or 'N/A'}")
        lines.append("")

        # Documents
        if response.documents:
            lines.append(f"### Documents ({len(response.documents)})")
            for doc in response.documents[:5]:
                lines.append(f"- [{doc.title}](/documents/{doc.id})")
            if len(response.documents) > 5:
                lines.append(f"- *...and {len(response.documents) - 5} more*")
            lines.append("")

        # Tickets
        if response.tickets:
            lines.append(f"### Support Tickets ({len(response.tickets)})")
            for ticket in response.tickets[:3]:
                lines.append(f"- {ticket.subject} ({ticket.status.value if ticket.status else 'unknown'})")
            if len(response.tickets) > 3:
                lines.append(f"- *...and {len(response.tickets) - 3} more*")
            lines.append("")

        return {
            "type": "customer_360",
            "format": "markdown",
            "content": "\n".join(lines),
        }

    # =========================================================================
    # DOCUMENT STRUCTURE FORMATTING
    # =========================================================================

    def format_document_structure(
        self,
        response: DocumentStructureResponse,
        output_format: Optional[OutputFormat] = None,
    ) -> Dict[str, Any]:
        """
        Format Document Structure response for chat UI.

        Args:
            response: DocumentStructureResponse from service
            output_format: Optional format override

        Returns:
            Formatted response dict
        """
        fmt = output_format or self.output_format

        if fmt == OutputFormat.MARKDOWN:
            return self._format_document_structure_markdown(response)
        elif fmt == OutputFormat.SUMMARY:
            return {
                "type": "document_structure",
                "summary": self._generate_document_summary(response),
            }
        elif fmt == OutputFormat.JSON:
            return {"type": "document_structure", "data": response.model_dump()}

        # Default: CHAT format
        sections = []

        # Section hierarchy
        if response.sections:
            sections.append(FormattedSection(
                title=f"Sections ({len(response.sections)})",
                type=SectionType.SECTIONS,
                content=self._format_section_tree(response.sections),
                expanded=True,
                count=len(response.sections),
                icon="list",
            ))

        # Defined terms
        if response.definitions:
            sections.append(FormattedSection(
                title=f"Defined Terms ({len(response.definitions)})",
                type=SectionType.DEFINITIONS,
                content=self._format_definition_list(response.definitions),
                expanded=False,
                count=len(response.definitions),
                icon="book",
            ))

        # Cross-references
        if response.cross_references:
            sections.append(FormattedSection(
                title=f"Cross-References ({len(response.cross_references)})",
                type=SectionType.CROSS_REFERENCES,
                content=self._format_cross_reference_list(response.cross_references),
                expanded=False,
                count=len(response.cross_references),
                icon="link",
            ))

        return {
            "type": "document_structure",
            "content": {
                "summary": self._generate_document_summary(response),
                "document_id": response.document_id,
                "title": response.title,
                "sections": [s.to_dict() for s in sections],
            },
        }

    def _generate_document_summary(self, response: DocumentStructureResponse) -> str:
        """Generate summary for document structure."""
        parts = [f"**{response.title or 'Document'}**"]

        stats = []
        if response.sections:
            stats.append(f"{len(response.sections)} sections")
        if response.definitions:
            stats.append(f"{len(response.definitions)} defined terms")
        if response.cross_references:
            stats.append(f"{len(response.cross_references)} cross-references")

        if stats:
            parts.append(f"contains {', '.join(stats)}")

        return " ".join(parts) + "."

    def _format_section_tree(
        self,
        sections: List[SectionNode],
    ) -> List[Dict[str, Any]]:
        """Format sections as a tree structure."""
        return [
            {
                "id": section.id,
                "number": section.number,
                "title": section.title,
                "level": section.level,
                "content_preview": section.content_preview,
                "child_count": section.child_count,
                "link": f"#section-{section.number}",
            }
            for section in sections
        ]

    def _format_definition_list(
        self,
        definitions: List[DefinedTermNode],
    ) -> List[Dict[str, Any]]:
        """Format defined terms list."""
        return [
            {
                "id": defn.id,
                "term": defn.term,
                "definition": defn.definition,
                "section_id": defn.section_id,
            }
            for defn in definitions
        ]

    def _format_cross_reference_list(
        self,
        refs: List[CrossReference],
    ) -> List[Dict[str, Any]]:
        """Format cross-references list."""
        return [
            {
                "from_section": ref.from_section_number,
                "to_section": ref.to_section_number,
                "text": ref.reference_text,
                "link": f"#section-{ref.to_section_number}",
            }
            for ref in refs
        ]

    def _format_document_structure_markdown(
        self,
        response: DocumentStructureResponse,
    ) -> Dict[str, Any]:
        """Format document structure as markdown."""
        lines = []

        lines.append(f"## {response.title or 'Document Structure'}")
        lines.append("")

        # Table of contents
        if response.sections:
            lines.append("### Table of Contents")
            for section in response.sections:
                indent = "  " * (section.level - 1)
                lines.append(f"{indent}- **{section.number}** {section.title}")
            lines.append("")

        # Definitions
        if response.definitions:
            lines.append("### Defined Terms")
            for defn in response.definitions[:10]:
                lines.append(f"- **{defn.term}**: {defn.definition[:100]}...")
            lines.append("")

        return {
            "type": "document_structure",
            "format": "markdown",
            "content": "\n".join(lines),
        }

    # =========================================================================
    # SMART RETRIEVAL FORMATTING
    # =========================================================================

    def format_smart_retrieval(
        self,
        response: SmartRetrievalResponse,
        output_format: Optional[OutputFormat] = None,
    ) -> Dict[str, Any]:
        """
        Format Smart Retrieval response for chat UI.

        Args:
            response: SmartRetrievalResponse from service
            output_format: Optional format override

        Returns:
            Formatted response dict
        """
        fmt = output_format or self.output_format

        if fmt == OutputFormat.JSON:
            return {"type": "smart_retrieval", "data": response.model_dump()}

        sections = []

        # Main sections (always expanded)
        if response.sections:
            sections.append(FormattedSection(
                title="Retrieved Sections",
                type=SectionType.SECTIONS,
                content=self._format_retrieved_sections(response.sections),
                expanded=True,
                count=len(response.sections),
                icon="file-text",
            ))

        # Cross-referenced sections
        if response.cross_referenced_sections:
            sections.append(FormattedSection(
                title="Related References",
                type=SectionType.CROSS_REFERENCES,
                content=self._format_retrieved_sections(response.cross_referenced_sections),
                expanded=False,
                count=len(response.cross_referenced_sections),
                icon="link",
            ))

        # Relevant definitions
        if response.relevant_definitions:
            sections.append(FormattedSection(
                title="Defined Terms Used",
                type=SectionType.DEFINITIONS,
                content=self._format_definition_list(response.relevant_definitions),
                expanded=False,
                count=len(response.relevant_definitions),
                icon="book",
            ))

        return {
            "type": "smart_retrieval",
            "content": {
                "summary": f"Found {len(response.sections)} relevant sections.",
                "sections": [s.to_dict() for s in sections],
            },
        }

    def _format_retrieved_sections(
        self,
        sections: List[SectionNode],
    ) -> List[Dict[str, Any]]:
        """Format retrieved sections with full content."""
        return [
            {
                "id": section.id,
                "number": section.number,
                "title": section.title,
                "content_preview": section.content_preview,
                "relevance_score": getattr(section, 'relevance_score', None),
                "link": f"#section-{section.number}",
            }
            for section in sections
        ]

    # =========================================================================
    # GRAPH-ENHANCED RAG FORMATTING
    # =========================================================================

    def format_graph_enhanced_rag(
        self,
        response: GraphEnhancedRAGResponse,
        output_format: Optional[OutputFormat] = None,
    ) -> Dict[str, Any]:
        """
        Format Graph-Enhanced RAG response for chat UI.

        Args:
            response: GraphEnhancedRAGResponse from service
            output_format: Optional format override

        Returns:
            Formatted response dict
        """
        fmt = output_format or self.output_format

        if fmt == OutputFormat.MARKDOWN:
            return self._format_rag_markdown(response)
        elif fmt == OutputFormat.SUMMARY:
            return {
                "type": "graph_enhanced_rag",
                "answer": response.answer,
            }
        elif fmt == OutputFormat.JSON:
            return {"type": "graph_enhanced_rag", "data": response.model_dump()}

        # Default: CHAT format
        sections = []

        # Context chunks
        if response.original_chunks:
            sections.append(FormattedSection(
                title=f"Source Documents ({len(response.original_chunks)})",
                type=SectionType.CONTEXT,
                content=self._format_chunk_list(response.original_chunks),
                expanded=False,
                count=len(response.original_chunks),
                icon="file-text",
            ))

        # Extracted entities
        if response.graph_context and response.graph_context.extracted_entities:
            sections.append(FormattedSection(
                title=f"Related Entities ({len(response.graph_context.extracted_entities)})",
                type=SectionType.ENTITIES,
                content=self._format_entity_list(response.graph_context.extracted_entities),
                expanded=False,
                count=len(response.graph_context.extracted_entities),
                icon="network",
            ))

        # Graph visualization data
        if response.graph_context:
            graph_data = self._generate_graph_visualization(response)
            if graph_data:
                sections.append(FormattedSection(
                    title="Knowledge Graph",
                    type=SectionType.GRAPH,
                    content=graph_data,
                    expanded=False,
                    icon="share-2",
                ))

        return {
            "type": "graph_enhanced_rag",
            "content": {
                "query": response.query,
                "answer": response.answer,
                "graph_enhanced": response.graph_enhanced,
                "latency_ms": response.latency_ms,
                "sections": [s.to_dict() for s in sections],
            },
        }

    def _format_chunk_list(self, chunks: List[ChunkNode]) -> List[Dict[str, Any]]:
        """Format chunk list for display."""
        return [
            {
                "id": chunk.id,
                "content": chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content,
                "document_id": chunk.document_id,
                "position": chunk.position,
                "link": f"/documents/{chunk.document_id}#chunk-{chunk.id}",
            }
            for chunk in chunks
        ]

    def _format_entity_list(self, entities: List[EntityNode]) -> List[Dict[str, Any]]:
        """Format entity list for display."""
        return [
            {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
                "description": entity.description,
                "confidence": entity.confidence,
                "link": f"/entities/{entity.id}",
            }
            for entity in entities
        ]

    def _generate_graph_visualization(
        self,
        response: GraphEnhancedRAGResponse,
    ) -> Optional[Dict[str, Any]]:
        """Generate graph visualization data for UI."""
        if not response.graph_context:
            return None

        nodes = []
        edges = []

        # Add entity nodes
        for entity in response.graph_context.extracted_entities:
            nodes.append({
                "id": entity.id,
                "label": entity.name,
                "type": entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
                "group": entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
            })

        # Add relationship edges
        for rel in response.graph_context.entity_relationships:
            edges.append({
                "from": rel.from_entity_id,
                "to": rel.to_entity_id,
                "label": rel.relationship_type,
            })

        if not nodes:
            return None

        return {
            "nodes": nodes,
            "edges": edges,
            "layout": "force-directed",
        }

    def _format_rag_markdown(
        self,
        response: GraphEnhancedRAGResponse,
    ) -> Dict[str, Any]:
        """Format RAG response as markdown."""
        lines = []

        # Answer
        lines.append("## Answer")
        lines.append("")
        lines.append(response.answer)
        lines.append("")

        # Sources
        if response.original_chunks:
            lines.append("### Sources")
            for i, chunk in enumerate(response.original_chunks[:5], 1):
                lines.append(f"{i}. [{chunk.document_id}](/documents/{chunk.document_id})")
            lines.append("")

        # Entities
        if response.graph_context and response.graph_context.extracted_entities:
            lines.append("### Related Entities")
            for entity in response.graph_context.extracted_entities[:5]:
                lines.append(f"- **{entity.name}** ({entity.type})")
            lines.append("")

        return {
            "type": "graph_enhanced_rag",
            "format": "markdown",
            "content": "\n".join(lines),
        }

    # =========================================================================
    # GRAPH EXPANSION FORMATTING
    # =========================================================================

    def format_graph_expansion(
        self,
        result: GraphExpansionResult,
        output_format: Optional[OutputFormat] = None,
    ) -> Dict[str, Any]:
        """
        Format Graph Expansion result for chat UI.

        Args:
            result: GraphExpansionResult from service
            output_format: Optional format override

        Returns:
            Formatted response dict
        """
        fmt = output_format or self.output_format

        if fmt == OutputFormat.JSON:
            return {"type": "graph_expansion", "data": result.model_dump()}

        sections = []

        # Expanded chunks
        if result.expanded_chunks:
            sections.append(FormattedSection(
                title=f"Expanded Results ({len(result.expanded_chunks)})",
                type=SectionType.CONTEXT,
                content=self._format_chunk_list(result.expanded_chunks),
                expanded=True,
                count=len(result.expanded_chunks),
                icon="maximize-2",
            ))

        # Extracted entities
        if result.extracted_entities:
            sections.append(FormattedSection(
                title=f"Discovered Entities ({len(result.extracted_entities)})",
                type=SectionType.ENTITIES,
                content=self._format_entity_list(result.extracted_entities),
                expanded=False,
                count=len(result.extracted_entities),
                icon="network",
            ))

        return {
            "type": "graph_expansion",
            "content": {
                "summary": f"Expanded to {len(result.expanded_chunks)} chunks with {len(result.extracted_entities)} entities.",
                "sections": [s.to_dict() for s in sections],
            },
        }


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_formatter_instance: Optional[GraphResultFormatter] = None


def get_graph_result_formatter(
    output_format: OutputFormat = OutputFormat.CHAT,
) -> GraphResultFormatter:
    """
    Get or create the GraphResultFormatter singleton.

    Args:
        output_format: Default output format

    Returns:
        GraphResultFormatter instance
    """
    global _formatter_instance

    if _formatter_instance is None:
        _formatter_instance = GraphResultFormatter(output_format=output_format)

    return _formatter_instance


def reset_graph_result_formatter() -> None:
    """Reset the formatter singleton (useful for testing)."""
    global _formatter_instance
    _formatter_instance = None
