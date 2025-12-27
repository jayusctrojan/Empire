// ============================================================================
// Empire AI v7.3 - Neo4j Department Nodes Schema
// ============================================================================
// This script creates Department nodes for the 12-department taxonomy
// Run this after the main schema setup
// ============================================================================

// ============================================================================
// STEP 1: CREATE CONSTRAINT FOR DEPARTMENT NODES
// ============================================================================

CREATE CONSTRAINT department_slug IF NOT EXISTS FOR (d:Department) REQUIRE d.slug IS UNIQUE;

// ============================================================================
// STEP 2: CREATE INDEX FOR FAST LOOKUPS
// ============================================================================

CREATE INDEX department_name IF NOT EXISTS FOR (d:Department) ON (d.display_name);
CREATE INDEX department_active IF NOT EXISTS FOR (d:Department) ON (d.is_active);

// ============================================================================
// STEP 3: CREATE ALL 12 DEPARTMENT NODES
// ============================================================================

// 1. IT & Engineering
MERGE (d:Department {slug: 'it-engineering'})
SET d.display_name = 'IT & Engineering',
    d.description = 'Technology, software development, infrastructure, DevOps, and technical systems',
    d.icon = 'computer',
    d.sort_order = 1,
    d.is_active = true,
    d.keywords = ['software', 'code', 'api', 'programming', 'development', 'engineering', 'backend', 'frontend', 'database', 'server', 'devops', 'cloud', 'aws', 'azure', 'docker', 'kubernetes'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 2. Sales & Marketing
MERGE (d:Department {slug: 'sales-marketing'})
SET d.display_name = 'Sales & Marketing',
    d.description = 'Sales strategies, marketing campaigns, lead generation, and customer acquisition',
    d.icon = 'trending-up',
    d.sort_order = 2,
    d.is_active = true,
    d.keywords = ['sales', 'marketing', 'lead', 'customer', 'campaign', 'crm', 'pipeline', 'revenue', 'funnel', 'conversion', 'prospect', 'advertising'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 3. Customer Support
MERGE (d:Department {slug: 'customer-support'})
SET d.display_name = 'Customer Support',
    d.description = 'Customer service, support processes, helpdesk, and customer satisfaction',
    d.icon = 'headphones',
    d.sort_order = 3,
    d.is_active = true,
    d.keywords = ['support', 'customer service', 'helpdesk', 'ticket', 'issue resolution', 'complaint', 'service desk', 'sla', 'escalation'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 4. Operations, HR & Supply Chain
MERGE (d:Department {slug: 'operations-hr-supply'})
SET d.display_name = 'Operations, HR & Supply Chain',
    d.description = 'Operations management, human resources, supply chain, and logistics',
    d.icon = 'settings',
    d.sort_order = 4,
    d.is_active = true,
    d.keywords = ['operations', 'hr', 'human resources', 'supply chain', 'logistics', 'warehouse', 'inventory', 'procurement', 'hiring', 'recruitment', 'employee'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 5. Finance & Accounting
MERGE (d:Department {slug: 'finance-accounting'})
SET d.display_name = 'Finance & Accounting',
    d.description = 'Financial management, accounting, budgeting, and auditing',
    d.icon = 'dollar-sign',
    d.sort_order = 5,
    d.is_active = true,
    d.keywords = ['finance', 'accounting', 'financial', 'budget', 'revenue', 'expense', 'profit', 'cash flow', 'audit', 'tax', 'invoice'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 6. Project Management
MERGE (d:Department {slug: 'project-management'})
SET d.display_name = 'Project Management',
    d.description = 'Project planning, execution, delivery, and stakeholder management',
    d.icon = 'clipboard',
    d.sort_order = 6,
    d.is_active = true,
    d.keywords = ['project', 'project management', 'agile', 'scrum', 'milestone', 'deliverable', 'timeline', 'sprint', 'kanban', 'gantt', 'pmo'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 7. Real Estate
MERGE (d:Department {slug: 'real-estate'})
SET d.display_name = 'Real Estate',
    d.description = 'Property management, real estate transactions, and investments',
    d.icon = 'home',
    d.sort_order = 7,
    d.is_active = true,
    d.keywords = ['real estate', 'property', 'lease', 'tenant', 'landlord', 'rental', 'mortgage', 'commercial property', 'residential'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 8. Private Equity & M&A
MERGE (d:Department {slug: 'private-equity-ma'})
SET d.display_name = 'Private Equity & M&A',
    d.description = 'Private equity investments, mergers & acquisitions, and valuations',
    d.icon = 'briefcase',
    d.sort_order = 8,
    d.is_active = true,
    d.keywords = ['private equity', 'merger', 'acquisition', 'm&a', 'valuation', 'due diligence', 'investment', 'portfolio', 'buyout', 'lbo', 'ebitda'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 9. Consulting
MERGE (d:Department {slug: 'consulting'})
SET d.display_name = 'Consulting',
    d.description = 'Business consulting, advisory services, strategy, and recommendations',
    d.icon = 'users',
    d.sort_order = 9,
    d.is_active = true,
    d.keywords = ['consulting', 'strategy', 'advisory', 'recommendation', 'assessment', 'analysis', 'framework', 'methodology'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 10. Personal & Continuing Education
MERGE (d:Department {slug: 'personal-continuing-ed'})
SET d.display_name = 'Personal & Continuing Education',
    d.description = 'Personal development, training, certification, and continuous learning',
    d.icon = 'book-open',
    d.sort_order = 10,
    d.is_active = true,
    d.keywords = ['education', 'learning', 'course', 'training', 'skill development', 'personal development', 'certification', 'professional development'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 11. Global (Cross-department)
MERGE (d:Department {slug: '_global'})
SET d.display_name = 'Global',
    d.description = 'Cross-department content applicable to all departments',
    d.icon = 'globe',
    d.sort_order = 11,
    d.is_active = true,
    d.keywords = ['general', 'universal', 'cross-functional', 'company-wide', 'organization'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// 12. Research & Development (NEW in v7.3)
MERGE (d:Department {slug: 'research-development'})
SET d.display_name = 'Research & Development',
    d.description = 'R&D, innovation, prototyping, experiments, patents, and product development',
    d.icon = 'flask',
    d.sort_order = 12,
    d.is_active = true,
    d.keywords = ['research', 'r&d', 'research and development', 'innovation', 'prototype', 'experiment', 'hypothesis', 'discovery', 'invention', 'patent', 'intellectual property', 'product development'],
    d.created_at = datetime(),
    d.updated_at = datetime();

// ============================================================================
// STEP 4: CREATE RELATIONSHIPS (Optional - for hierarchical structure)
// ============================================================================

// Create parent-child relationships if needed
// Example: MATCH (parent:Department {slug: 'it-engineering'}), (child:Department {slug: 'research-development'})
// MERGE (parent)-[:RELATED_TO {type: 'adjacent'}]->(child)

// ============================================================================
// STEP 5: VERIFICATION QUERIES
// ============================================================================

// Count all departments
// MATCH (d:Department) RETURN count(d) as total_departments;

// List all departments
// MATCH (d:Department) RETURN d.slug, d.display_name, d.sort_order ORDER BY d.sort_order;

// Find R&D department
// MATCH (d:Department {slug: 'research-development'}) RETURN d;

// ============================================================================
// END OF DEPARTMENT SCHEMA
// ============================================================================
