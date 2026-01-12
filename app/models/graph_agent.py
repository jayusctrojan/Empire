# app/models/graph_agent.py
"""
Pydantic models for Graph Agent APIs.

Task 103: Graph Agent - Pydantic Models
Feature: 005-graph-agent

Includes models for:
- Customer 360 views
- Document Structure navigation
- Graph-Enhanced RAG
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


# =============================================================================
# BASE ENUMS
# =============================================================================


class QueryType(str, Enum):
    """Types of graph queries supported."""
    CUSTOMER_360 = "customer_360"
    DOCUMENT_STRUCTURE = "document_structure"
    GRAPH_ENHANCED_RAG = "graph_enhanced_rag"
    ENTITY_LOOKUP = "entity_lookup"


class TraversalDepth(str, Enum):
    """Graph traversal depth options."""
    SHALLOW = "shallow"  # 1 hop
    MEDIUM = "medium"    # 2 hops
    DEEP = "deep"        # 3 hops


class CustomerType(str, Enum):
    """Customer type classification."""
    ENTERPRISE = "enterprise"
    SMB = "smb"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"


class TicketStatus(str, Enum):
    """Support ticket status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Support ticket priority."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InteractionType(str, Enum):
    """Customer interaction types."""
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    CHAT = "chat"
    OTHER = "other"


class OrderStatus(str, Enum):
    """Order/transaction status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class EntityType(str, Enum):
    """Entity types for Graph-Enhanced RAG."""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    CONCEPT = "concept"
    PRODUCT = "product"
    EVENT = "event"
    DATE = "date"
    REGULATION = "regulation"
    OTHER = "other"


# =============================================================================
# CUSTOMER 360 MODELS
# =============================================================================


class CustomerNode(BaseModel):
    """Represents a customer node in the graph."""
    id: str = Field(..., description="Unique customer identifier")
    name: str = Field(..., description="Customer name")
    type: CustomerType = Field(default=CustomerType.UNKNOWN, description="Customer type")
    industry: Optional[str] = Field(None, description="Customer industry")
    created_at: Optional[datetime] = Field(None, description="When customer was added")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional customer metadata")


class TicketNode(BaseModel):
    """Represents a support ticket node."""
    id: str = Field(..., description="Unique ticket identifier")
    customer_id: str = Field(..., description="Associated customer ID")
    subject: str = Field(..., description="Ticket subject")
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Ticket status")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Ticket priority")
    created_at: Optional[datetime] = Field(None, description="Ticket creation time")
    resolved_at: Optional[datetime] = Field(None, description="Ticket resolution time")
    description: Optional[str] = Field(None, description="Ticket description")


class OrderNode(BaseModel):
    """Represents an order/transaction node."""
    id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Associated customer ID")
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Order status")
    total_amount: Optional[float] = Field(None, description="Order total amount")
    currency: str = Field(default="USD", description="Currency code")
    created_at: Optional[datetime] = Field(None, description="Order creation time")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Order items")


class InteractionNode(BaseModel):
    """Represents a customer interaction node."""
    id: str = Field(..., description="Unique interaction identifier")
    customer_id: str = Field(..., description="Associated customer ID")
    type: InteractionType = Field(..., description="Interaction type")
    subject: Optional[str] = Field(None, description="Interaction subject")
    summary: Optional[str] = Field(None, description="Interaction summary")
    created_at: Optional[datetime] = Field(None, description="Interaction timestamp")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes")
    sentiment: Optional[str] = Field(None, description="Sentiment analysis result")


class ProductNode(BaseModel):
    """Represents a product/service node."""
    id: str = Field(..., description="Unique product identifier")
    name: str = Field(..., description="Product name")
    category: Optional[str] = Field(None, description="Product category")
    description: Optional[str] = Field(None, description="Product description")


class DocumentNode(BaseModel):
    """Represents a document associated with a customer."""
    id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    type: Optional[str] = Field(None, description="Document type (contract, agreement, etc.)")
    created_at: Optional[datetime] = Field(None, description="Document creation time")
    status: Optional[str] = Field(None, description="Document status")


class SimilarCustomer(BaseModel):
    """Represents a similar customer found via graph analysis."""
    id: str = Field(..., description="Customer ID")
    name: str = Field(..., description="Customer name")
    type: Optional[CustomerType] = Field(None, description="Customer type")
    industry: Optional[str] = Field(None, description="Customer industry")
    shared_products: int = Field(default=0, description="Number of shared products")
    same_industry: bool = Field(default=False, description="Whether in same industry")
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall similarity score")


class Customer360Request(BaseModel):
    """Request model for Customer 360 queries."""
    query: Optional[str] = Field(None, description="Natural language query about a customer")
    customer_id: Optional[str] = Field(None, description="Direct customer ID lookup")
    include_documents: bool = Field(default=True, description="Include related documents")
    include_tickets: bool = Field(default=True, description="Include support tickets")
    include_orders: bool = Field(default=True, description="Include orders/transactions")
    include_interactions: bool = Field(default=True, description="Include customer interactions")
    max_items_per_category: int = Field(default=10, ge=1, le=100, description="Max items per category")
    traversal_depth: TraversalDepth = Field(default=TraversalDepth.MEDIUM, description="Graph traversal depth")

    @model_validator(mode="after")
    def validate_query_or_customer_id(self) -> "Customer360Request":
        """Ensure at least one of query or customer_id is provided."""
        if not self.query and not self.customer_id:
            raise ValueError("Either 'query' or 'customer_id' must be provided")
        return self


class Customer360Response(BaseModel):
    """Response model for Customer 360 queries."""
    customer: CustomerNode = Field(..., description="Customer node data")
    documents: List[DocumentNode] = Field(default_factory=list, description="Related documents")
    tickets: List[TicketNode] = Field(default_factory=list, description="Support tickets")
    orders: List[OrderNode] = Field(default_factory=list, description="Orders/transactions")
    interactions: List[InteractionNode] = Field(default_factory=list, description="Customer interactions")
    products: List[ProductNode] = Field(default_factory=list, description="Products used")
    relationship_count: int = Field(default=0, description="Total relationship count")
    summary: str = Field(default="", description="Natural language summary")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Response generation time")


# =============================================================================
# DOCUMENT STRUCTURE MODELS
# =============================================================================


class SectionNode(BaseModel):
    """Represents a document section node."""
    id: str = Field(..., description="Unique section identifier")
    document_id: Optional[str] = Field(None, description="Parent document ID")
    title: str = Field(..., description="Section title")
    number: str = Field(..., description="Section number (e.g., '1.2.3')")
    level: int = Field(..., ge=1, description="Hierarchy level (1=top)")
    content_preview: Optional[str] = Field(None, description="First 200 chars of content")
    child_count: int = Field(default=0, description="Number of child sections")
    reference_count: int = Field(default=0, description="Number of cross-references from this section")


class DefinedTermNode(BaseModel):
    """Represents a defined term in a document."""
    id: str = Field(..., description="Unique term identifier")
    document_id: str = Field(..., description="Parent document ID")
    term: str = Field(..., description="The defined term")
    definition: str = Field(..., description="Term definition")
    section_id: Optional[str] = Field(None, description="Section where term is defined")
    usage_count: int = Field(default=0, description="Number of times term is used")


class CrossReference(BaseModel):
    """Represents a cross-reference between sections."""
    from_section_id: str = Field(..., description="Source section ID")
    from_section_number: str = Field(..., description="Source section number")
    to_section_id: str = Field(..., description="Target section ID")
    to_section_number: str = Field(..., description="Target section number")
    reference_text: str = Field(..., description="Reference text (e.g., 'See Section 5.2')")


class CitationNode(BaseModel):
    """Represents an external citation."""
    id: str = Field(..., description="Unique citation identifier")
    document_id: str = Field(..., description="Parent document ID")
    type: str = Field(..., description="Citation type (statute, case, regulation)")
    reference: str = Field(..., description="Citation reference text")
    section_id: Optional[str] = Field(None, description="Section containing citation")


class DocumentStructureRequest(BaseModel):
    """Request model for document structure extraction."""
    document_id: str = Field(..., description="Document ID to extract structure from")
    document_content: Optional[str] = Field(None, description="Document content (if not already stored)")
    extract_sections: bool = Field(default=True, description="Extract section hierarchy")
    extract_cross_refs: bool = Field(default=True, description="Extract cross-references")
    extract_definitions: bool = Field(default=True, description="Extract defined terms")
    max_depth: int = Field(default=5, ge=1, le=10, description="Maximum section hierarchy depth")


class DocumentStructureResponse(BaseModel):
    """Response model for document structure extraction."""
    document_id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    sections: List[SectionNode] = Field(default_factory=list, description="Section hierarchy")
    definitions: List[DefinedTermNode] = Field(default_factory=list, description="Defined terms")
    cross_references: List[CrossReference] = Field(default_factory=list, description="Cross-references")
    citations: List[CitationNode] = Field(default_factory=list, description="External citations")
    structure_depth: int = Field(default=0, description="Maximum depth of section hierarchy")
    extracted_at: datetime = Field(default_factory=datetime.utcnow, description="Extraction timestamp")


class SmartRetrievalRequest(BaseModel):
    """Request for smart retrieval with cross-reference following."""
    document_id: str = Field(..., description="Document ID to search within")
    query: str = Field(..., description="Search query")
    include_parent_context: bool = Field(default=True, description="Include parent section context")
    follow_cross_refs: bool = Field(default=True, description="Follow cross-references")
    max_cross_ref_depth: int = Field(default=2, ge=0, le=5, description="Max cross-reference depth")
    include_definitions: bool = Field(default=True, description="Include relevant defined terms")


class SmartRetrievalResponse(BaseModel):
    """Response for smart retrieval."""
    sections: List[SectionNode] = Field(default_factory=list, description="Matching sections")
    parent_context: List[SectionNode] = Field(default_factory=list, description="Parent sections for context")
    cross_referenced_sections: List[SectionNode] = Field(default_factory=list, description="Cross-referenced sections")
    relevant_definitions: List[DefinedTermNode] = Field(default_factory=list, description="Relevant defined terms")
    breadcrumb: List[str] = Field(default_factory=list, description="Navigation breadcrumb")


# =============================================================================
# GRAPH-ENHANCED RAG MODELS
# =============================================================================


class EntityNode(BaseModel):
    """Represents an entity extracted from documents."""
    id: str = Field(..., description="Unique entity identifier")
    name: str = Field(..., description="Entity name")
    type: EntityType = Field(..., description="Entity type")
    normalized_name: Optional[str] = Field(None, description="Normalized name for matching")
    description: Optional[str] = Field(None, description="Entity description")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    source_document_id: Optional[str] = Field(None, description="Source document ID")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")


class ChunkNode(BaseModel):
    """Represents a document chunk for RAG."""
    id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    content: str = Field(..., description="Chunk content")
    position: int = Field(..., ge=0, description="Position in document")
    embedding_id: Optional[str] = Field(None, description="Link to vector embedding in Supabase")
    section_id: Optional[str] = Field(None, description="Parent section ID")


class EntityRelationship(BaseModel):
    """Represents a relationship between entities."""
    from_entity_id: str = Field(..., description="Source entity ID")
    to_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: str = Field(..., description="Type of relationship")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship confidence")
    source_chunk_id: Optional[str] = Field(None, description="Chunk where relationship found")


class GraphEnhancedRAGRequest(BaseModel):
    """Request model for Graph-Enhanced RAG queries."""
    query: str = Field(..., description="User query")
    chunk_ids: Optional[List[str]] = Field(None, description="Pre-retrieved chunk IDs to expand")
    expansion_depth: TraversalDepth = Field(default=TraversalDepth.MEDIUM, description="Graph expansion depth")
    max_expanded_chunks: int = Field(default=10, ge=1, le=50, description="Max chunks after expansion")
    include_entity_context: bool = Field(default=True, description="Include entity information")
    include_relationship_paths: bool = Field(default=True, description="Include relationship traversal paths")
    rerank_by_graph_relevance: bool = Field(default=True, description="Re-rank results by graph relevance")


class GraphExpansionResult(BaseModel):
    """Result of graph-based context expansion."""
    original_chunks: List[ChunkNode] = Field(default_factory=list, description="Original retrieved chunks")
    expanded_chunks: List[ChunkNode] = Field(default_factory=list, description="Additional chunks from expansion")
    extracted_entities: List[EntityNode] = Field(default_factory=list, description="Entities from chunks")
    related_entities: List[EntityNode] = Field(default_factory=list, description="Related entities from graph")
    entity_relationships: List[EntityRelationship] = Field(default_factory=list, description="Entity relationships")
    relationship_paths: List[List[str]] = Field(default_factory=list, description="Relationship traversal paths")
    expansion_method: str = Field(default="entity_expansion", description="Method used for expansion")


class GraphEnhancedRAGResponse(BaseModel):
    """Response model for Graph-Enhanced RAG queries."""
    query: str = Field(..., description="Original query")
    answer: Optional[str] = Field(None, description="Generated answer")
    original_chunks: List[ChunkNode] = Field(default_factory=list, description="Original search results")
    graph_context: GraphExpansionResult = Field(..., description="Graph expansion results")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source citations")
    graph_enhanced: bool = Field(default=True, description="Whether graph enhancement was applied")
    latency_ms: float = Field(default=0.0, description="Query latency in milliseconds")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Response generation time")


# =============================================================================
# HEALTH AND STATUS MODELS
# =============================================================================


class GraphAgentHealth(BaseModel):
    """Health status for Graph Agent services."""
    neo4j_connected: bool = Field(..., description="Neo4j connection status")
    customer_360_available: bool = Field(default=True, description="Customer 360 service available")
    document_structure_available: bool = Field(default=True, description="Document Structure service available")
    graph_enhanced_rag_available: bool = Field(default=True, description="Graph-Enhanced RAG available")
    cache_connected: bool = Field(default=False, description="Redis cache connection status")
    last_health_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check time")
    version: str = Field(default="1.0.0", description="Graph Agent version")


class GraphQueryMetrics(BaseModel):
    """Metrics for graph query performance."""
    query_type: QueryType = Field(..., description="Type of query")
    execution_time_ms: float = Field(..., ge=0, description="Query execution time")
    nodes_traversed: int = Field(default=0, ge=0, description="Number of nodes traversed")
    relationships_followed: int = Field(default=0, ge=0, description="Number of relationships followed")
    cache_hit: bool = Field(default=False, description="Whether result was cached")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Query timestamp")


# =============================================================================
# INTENT DETECTION MODELS
# =============================================================================


class QueryIntent(BaseModel):
    """Detected intent from a user query."""
    query_type: QueryType = Field(..., description="Detected query type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    extracted_customer: Optional[str] = Field(None, description="Extracted customer name/ID")
    extracted_document: Optional[str] = Field(None, description="Extracted document reference")
    extracted_entities: List[str] = Field(default_factory=list, description="Extracted entity names")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional extracted parameters")


class IntentDetectionRequest(BaseModel):
    """Request for intent detection."""
    query: str = Field(..., min_length=1, description="User query to analyze")
    conversation_context: Optional[List[Dict[str, str]]] = Field(None, description="Previous conversation messages")
    hint_query_type: Optional[QueryType] = Field(None, description="Hint for expected query type")


class IntentDetectionResponse(BaseModel):
    """Response from intent detection."""
    intent: QueryIntent = Field(..., description="Detected intent")
    alternative_intents: List[QueryIntent] = Field(default_factory=list, description="Alternative possible intents")
    requires_clarification: bool = Field(default=False, description="Whether clarification is needed")
    clarification_question: Optional[str] = Field(None, description="Question to ask for clarification")
