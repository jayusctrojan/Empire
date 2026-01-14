# Data Model: Graph Agent for CKO Chat

**Date**: 2025-01-11
**Source**: spec.md, architecture_graph_agent.md

---

## Entity Definitions

### 1. Customer

Represents an organization or individual with a business relationship.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| name | String | Yes | Customer name |
| type | Enum | Yes | enterprise, smb, individual |
| industry | String | No | Industry classification |
| status | Enum | Yes | active, inactive, prospect |
| metadata | JSON | No | Additional customer data |
| created_at | DateTime | Yes | Record creation time |
| updated_at | DateTime | Yes | Last modification time |

**Relationships**:
- `HAS_DOCUMENT` → Document (1:N)
- `HAS_TICKET` → Ticket (1:N)
- `PLACED_ORDER` → Order (1:N)
- `HAD_INTERACTION` → Interaction (1:N)
- `USES_PRODUCT` → Product (M:N)

---

### 2. Document

Represents a stored document with optional extracted structure.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| title | String | Yes | Document title |
| type | String | Yes | contract, policy, regulation, report |
| content | Text | No | Full document content |
| summary | Text | No | AI-generated summary |
| upload_date | DateTime | Yes | When uploaded |
| structure_extracted | Boolean | No | Whether structure has been extracted |
| metadata | JSON | No | Additional document data |

**Relationships**:
- `HAS_SECTION` → Section (1:N)
- `MENTIONS` ↔ Entity (M:N)
- `RELATED_TO` ↔ Document (M:N)

---

### 3. Section

Represents a structural unit within a document (hierarchy-aware).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| document_id | UUID | Yes | Parent document |
| number | String | Yes | Section number (e.g., "1.2.3") |
| title | String | Yes | Section title |
| level | Integer | Yes | Depth in hierarchy (1 = top) |
| content | Text | Yes | Section content |
| start_position | Integer | No | Character offset in source |
| metadata | JSON | No | Additional section data |

**Relationships**:
- `HAS_SUBSECTION` → Section (self-referencing, 1:N)
- `REFERENCES` → Section (M:N, cross-references)
- `DEFINED_IN` ← DefinedTerm (1:N)

---

### 4. Ticket

Represents a support or service ticket.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| customer_id | UUID | Yes | Associated customer |
| title | String | Yes | Ticket title/subject |
| description | Text | No | Ticket description |
| status | Enum | Yes | open, in_progress, resolved, closed |
| priority | Enum | Yes | low, medium, high, critical |
| created_date | DateTime | Yes | When ticket was created |
| resolved_date | DateTime | No | When ticket was resolved |
| metadata | JSON | No | Additional ticket data |

**Relationships**:
- `RELATED_TO` ↔ Document (M:N)
- `INVOLVES_PRODUCT` → Product (M:N)

---

### 5. Order

Represents a purchase transaction.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| customer_id | UUID | Yes | Associated customer |
| order_number | String | Yes | External order number |
| amount | Decimal | Yes | Total order amount |
| currency | String | Yes | Currency code (USD, EUR, etc.) |
| status | Enum | Yes | pending, confirmed, shipped, delivered, cancelled |
| order_date | DateTime | Yes | When order was placed |
| metadata | JSON | No | Additional order data |

**Relationships**:
- `CONTAINS_PRODUCT` → Product (M:N with quantity)

---

### 6. Interaction

Represents a customer touchpoint (email, call, meeting).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| customer_id | UUID | Yes | Associated customer |
| type | Enum | Yes | email, call, meeting, chat |
| summary | Text | Yes | Interaction summary |
| date | DateTime | Yes | When interaction occurred |
| duration_minutes | Integer | No | Duration for calls/meetings |
| sentiment | Enum | No | positive, neutral, negative |
| metadata | JSON | No | Additional interaction data |

---

### 7. Product

Represents a product or service offering.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| name | String | Yes | Product name |
| category | String | Yes | Product category |
| description | Text | No | Product description |
| status | Enum | Yes | active, deprecated, discontinued |
| metadata | JSON | No | Additional product data |

---

### 8. DefinedTerm

Represents a term with explicit definition in a document.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| document_id | UUID | Yes | Source document |
| term | String | Yes | The defined term |
| definition | Text | Yes | The definition text |
| section_id | UUID | No | Section where defined |

**Relationships**:
- `DEFINED_IN` → Section (1:1)
- `USED_IN` → Section (M:N, sections using this term)

---

### 9. Entity

Represents a named entity extracted from document content.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| name | String | Yes | Entity name |
| type | Enum | Yes | person, organization, location, concept, regulation |
| normalized_name | String | No | Canonical form of name |
| metadata | JSON | No | Additional entity data |

**Relationships**:
- `MENTIONED_IN` ← DocumentChunk (M:N)
- `RELATED_TO` ↔ Entity (M:N, semantic relationships)

---

## Neo4j Schema (Cypher)

### Constraints and Indexes

```cypher
// Customer
CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE;
CREATE INDEX customer_name IF NOT EXISTS FOR (c:Customer) ON (c.name);
CREATE INDEX customer_type IF NOT EXISTS FOR (c:Customer) ON (c.type);

// Document
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE INDEX document_title IF NOT EXISTS FOR (d:Document) ON (d.title);
CREATE INDEX document_type IF NOT EXISTS FOR (d:Document) ON (d.type);

// Section
CREATE CONSTRAINT section_id IF NOT EXISTS FOR (s:Section) REQUIRE s.id IS UNIQUE;
CREATE INDEX section_document IF NOT EXISTS FOR (s:Section) ON (s.document_id);
CREATE INDEX section_number IF NOT EXISTS FOR (s:Section) ON (s.number);

// Ticket
CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:Ticket) REQUIRE t.id IS UNIQUE;
CREATE INDEX ticket_customer IF NOT EXISTS FOR (t:Ticket) ON (t.customer_id);
CREATE INDEX ticket_status IF NOT EXISTS FOR (t:Ticket) ON (t.status);

// Order
CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE;
CREATE INDEX order_customer IF NOT EXISTS FOR (o:Order) ON (o.customer_id);

// Interaction
CREATE CONSTRAINT interaction_id IF NOT EXISTS FOR (i:Interaction) REQUIRE i.id IS UNIQUE;
CREATE INDEX interaction_customer IF NOT EXISTS FOR (i:Interaction) ON (i.customer_id);

// Product
CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE;

// DefinedTerm
CREATE CONSTRAINT defined_term_id IF NOT EXISTS FOR (dt:DefinedTerm) REQUIRE dt.id IS UNIQUE;
CREATE INDEX defined_term_document IF NOT EXISTS FOR (dt:DefinedTerm) ON (dt.document_id);

// Entity
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type);
```

### Relationship Indexes

```cypher
// For fast traversal
CREATE INDEX rel_has_document IF NOT EXISTS FOR ()-[r:HAS_DOCUMENT]-() ON (r.created_at);
CREATE INDEX rel_has_ticket IF NOT EXISTS FOR ()-[r:HAS_TICKET]-() ON (r.created_at);
CREATE INDEX rel_references IF NOT EXISTS FOR ()-[r:REFERENCES]-() ON (r.created_at);
```

---

## Pydantic Models

See `app/models/graph_agent.py` for full Pydantic model definitions including:
- Request/Response models for each endpoint
- CustomerNode, SectionNode, etc. for graph results
- GraphExpansionResult for RAG context

---

## State Transitions

### Ticket Status Flow
```
open → in_progress → resolved → closed
         ↑              ↓
         └──────────────┘ (reopened)
```

### Order Status Flow
```
pending → confirmed → shipped → delivered
    ↓         ↓
cancelled  cancelled
```

### Document Structure Extraction
```
uploaded → processing → extracted
              ↓
          failed (fallback to unstructured)
```
