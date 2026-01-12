// migrations/neo4j/001_customer360_schema.cypher
//
// Task 102: Graph Agent - Customer 360 Schema
// Feature: 005-graph-agent
//
// Creates Customer 360 nodes and indexes for unified customer views.
// This migration is idempotent - safe to run multiple times.

// ============================================================================
// CUSTOMER NODE
// ============================================================================
// Represents customers/organizations in the knowledge graph

// Constraint: Customer ID must be unique
CREATE CONSTRAINT customer_id IF NOT EXISTS
FOR (c:Customer) REQUIRE c.id IS UNIQUE;

// Index: Customer name for text search queries
CREATE INDEX customer_name IF NOT EXISTS
FOR (c:Customer) ON (c.name);

// Index: Customer type (e.g., enterprise, SMB, individual)
CREATE INDEX customer_type IF NOT EXISTS
FOR (c:Customer) ON (c.type);

// Index: Customer industry for filtering
CREATE INDEX customer_industry IF NOT EXISTS
FOR (c:Customer) ON (c.industry);

// Index: Customer created_at for time-based queries
CREATE INDEX customer_created_at IF NOT EXISTS
FOR (c:Customer) ON (c.created_at);

// ============================================================================
// TICKET NODE
// ============================================================================
// Represents support tickets associated with customers

// Constraint: Ticket ID must be unique
CREATE CONSTRAINT ticket_id IF NOT EXISTS
FOR (t:Ticket) REQUIRE t.id IS UNIQUE;

// Index: Ticket customer_id for joins
CREATE INDEX ticket_customer_id IF NOT EXISTS
FOR (t:Ticket) ON (t.customer_id);

// Index: Ticket status for filtering (open, closed, pending, etc.)
CREATE INDEX ticket_status IF NOT EXISTS
FOR (t:Ticket) ON (t.status);

// Index: Ticket priority for filtering (high, medium, low)
CREATE INDEX ticket_priority IF NOT EXISTS
FOR (t:Ticket) ON (t.priority);

// Index: Ticket created_at for time-based queries
CREATE INDEX ticket_created_at IF NOT EXISTS
FOR (t:Ticket) ON (t.created_at);

// ============================================================================
// ORDER NODE
// ============================================================================
// Represents orders/transactions associated with customers

// Constraint: Order ID must be unique
CREATE CONSTRAINT order_id IF NOT EXISTS
FOR (o:Order) REQUIRE o.id IS UNIQUE;

// Index: Order customer_id for joins
CREATE INDEX order_customer_id IF NOT EXISTS
FOR (o:Order) ON (o.customer_id);

// Index: Order status for filtering
CREATE INDEX order_status IF NOT EXISTS
FOR (o:Order) ON (o.status);

// Index: Order created_at for time-based queries
CREATE INDEX order_created_at IF NOT EXISTS
FOR (o:Order) ON (o.created_at);

// ============================================================================
// INTERACTION NODE
// ============================================================================
// Represents customer interactions (calls, emails, meetings, etc.)

// Constraint: Interaction ID must be unique
CREATE CONSTRAINT interaction_id IF NOT EXISTS
FOR (i:Interaction) REQUIRE i.id IS UNIQUE;

// Index: Interaction customer_id for joins
CREATE INDEX interaction_customer_id IF NOT EXISTS
FOR (i:Interaction) ON (i.customer_id);

// Index: Interaction type (call, email, meeting, chat)
CREATE INDEX interaction_type IF NOT EXISTS
FOR (i:Interaction) ON (i.type);

// Index: Interaction created_at for time-based queries
CREATE INDEX interaction_created_at IF NOT EXISTS
FOR (i:Interaction) ON (i.created_at);

// ============================================================================
// PRODUCT NODE
// ============================================================================
// Represents products/services used by customers

// Constraint: Product ID must be unique
CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

// Index: Product name for text search
CREATE INDEX product_name IF NOT EXISTS
FOR (p:Product) ON (p.name);

// Index: Product category for filtering
CREATE INDEX product_category IF NOT EXISTS
FOR (p:Product) ON (p.category);

// ============================================================================
// RELATIONSHIP INDEXES
// ============================================================================
// Indexes on relationships for fast graph traversal

// HAS_DOCUMENT relationship (Customer->Document)
CREATE INDEX rel_has_document IF NOT EXISTS
FOR ()-[r:HAS_DOCUMENT]-() ON (r.created_at);

// HAS_TICKET relationship (Customer->Ticket)
CREATE INDEX rel_has_ticket IF NOT EXISTS
FOR ()-[r:HAS_TICKET]-() ON (r.created_at);

// PLACED_ORDER relationship (Customer->Order)
CREATE INDEX rel_placed_order IF NOT EXISTS
FOR ()-[r:PLACED_ORDER]-() ON (r.created_at);

// HAD_INTERACTION relationship (Customer->Interaction)
CREATE INDEX rel_had_interaction IF NOT EXISTS
FOR ()-[r:HAD_INTERACTION]-() ON (r.created_at);

// USES_PRODUCT relationship (Customer->Product)
CREATE INDEX rel_uses_product IF NOT EXISTS
FOR ()-[r:USES_PRODUCT]-() ON (r.since);

// ============================================================================
// VALIDATION QUERY
// ============================================================================
// Run this query to verify the schema was created correctly:
//
// CALL db.constraints()
// YIELD name, type, labelsOrTypes, properties
// WHERE name CONTAINS 'customer' OR name CONTAINS 'ticket'
//    OR name CONTAINS 'order' OR name CONTAINS 'interaction'
//    OR name CONTAINS 'product'
// RETURN name, type, labelsOrTypes, properties
// ORDER BY name;
