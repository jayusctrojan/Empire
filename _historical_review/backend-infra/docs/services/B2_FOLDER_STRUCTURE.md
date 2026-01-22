# Backblaze B2 Folder Structure - Empire v7.2

## Overview

Empire uses a **structured folder hierarchy** in Backblaze B2 to manage document workflows and organize processed content by department. The system uses AI-powered auto-classification (Claude Haiku) to determine the correct department and subdepartment for each uploaded course or document.

---

## Complete Folder Structure

```
JB-Course-KB/
│
├── pending/                          # Documents awaiting processing
│   ├── general/                      # General documents (default)
│   ├── courses/                      # Course materials dropped here
│   └── urgent/                       # Priority processing queue
│
├── processing/                       # Currently being processed
│   └── [temporary files]
│
├── processed/                        # Successfully processed documents
│   ├── general/                      # General documents
│   ├── courses/                      # Processed course materials (organized below)
│   │   │
│   │   ├── it-engineering/                    # 1. IT & Engineering
│   │   │   ├── software-development/
│   │   │   ├── devops-infrastructure/
│   │   │   ├── data-engineering/
│   │   │   ├── cybersecurity/
│   │   │   ├── cloud-architecture/
│   │   │   └── qa-testing/
│   │   │
│   │   ├── sales-marketing/                   # 2. Sales & Marketing
│   │   │   ├── sales-training/
│   │   │   ├── sales-operations/
│   │   │   ├── marketing-strategy/
│   │   │   ├── digital-marketing/
│   │   │   ├── content-marketing/
│   │   │   ├── product-strategy/
│   │   │   ├── product-management/
│   │   │   ├── r-and-d/                      # Research & Development, Innovation
│   │   │   ├── customer-success/
│   │   │   └── brand-positioning/
│   │   │
│   │   ├── customer-support/                  # 3. Customer Support & Success
│   │   │   ├── technical-support/
│   │   │   ├── customer-success-management/
│   │   │   ├── help-desk-operations/
│   │   │   ├── sla-management/
│   │   │   ├── customer-communication/
│   │   │   └── support-tools-training/
│   │   │
│   │   ├── operations-hr-supply/              # 4. Operations, HR & Supply Chain
│   │   │   ├── hr-policies/
│   │   │   ├── talent-development/
│   │   │   ├── recruitment-onboarding/
│   │   │   ├── operations-management/
│   │   │   ├── supply-chain-logistics/
│   │   │   ├── procurement-vendor-mgmt/
│   │   │   ├── inventory-management/
│   │   │   └── legal-compliance/             # Legal & Compliance subdepartment
│   │   │
│   │   ├── finance-accounting/                # 5. Finance & Accounting
│   │   │   ├── financial-planning/
│   │   │   ├── accounting-standards/
│   │   │   ├── budgeting-forecasting/
│   │   │   ├── tax-compliance/
│   │   │   ├── audit-controls/
│   │   │   └── risk-management/
│   │   │
│   │   ├── project-management/                # 6. Project Management
│   │   │   ├── agile-scrum/
│   │   │   ├── waterfall-traditional/
│   │   │   ├── pmp-certification/
│   │   │   ├── tools-software/               # Jira, Asana, MS Project, etc.
│   │   │   └── stakeholder-management/
│   │   │
│   │   ├── real-estate/                       # 7. Real Estate
│   │   │   ├── property-management/
│   │   │   ├── commercial-real-estate/
│   │   │   ├── residential-real-estate/
│   │   │   ├── real-estate-investment/
│   │   │   ├── property-development/
│   │   │   ├── leasing-contracts/
│   │   │   └── real-estate-law/
│   │   │
│   │   ├── private-equity-ma/                 # 8. Private Equity & M&A
│   │   │   ├── mergers-acquisitions/
│   │   │   ├── due-diligence/
│   │   │   ├── deal-structuring/
│   │   │   ├── valuation-modeling/
│   │   │   ├── private-equity-fundamentals/
│   │   │   ├── portfolio-management/
│   │   │   └── exit-strategies/
│   │   │
│   │   ├── consulting/                        # 9. Consulting
│   │   │   ├── management-consulting/
│   │   │   ├── strategy-consulting/
│   │   │   ├── consulting-frameworks/        # BCG Matrix, Porter's Five Forces, etc.
│   │   │   ├── client-engagement/
│   │   │   ├── consulting-skills/
│   │   │   └── industry-expertise/
│   │   │
│   │   └── personal-continuing-ed/            # 10. Personal Continuing Education
│   │       ├── psychology/
│   │       ├── nlp-coaching/                  # NLP, life coaching (virtualcoach.com, etc.)
│   │       ├── personal-leadership/
│   │       ├── mindfulness-wellness/
│   │       └── self-improvement/
│   │
│   └── youtube-content/                       # YouTube transcripts
│       ├── by-department/
│       └── by-channel/
│
├── failed/                                    # Failed processing attempts
│   ├── parse-errors/
│   ├── ocr-failures/
│   └── invalid-format/
│
└── archive/                                   # Archived/deprecated content
    └── [timestamped backups]
```

---

## Department Taxonomy & AI Classification Context

### 1. IT & Engineering (`it-engineering`)

**Core Focus:** Technology, software development, infrastructure, data systems, security

**AI Classification Keywords:**
- Programming languages (Python, Java, JavaScript, Go, Rust, etc.)
- DevOps, CI/CD, Docker, Kubernetes, infrastructure
- Data engineering, ETL, data pipelines, databases
- Cybersecurity, penetration testing, security audits
- Cloud platforms (AWS, Azure, GCP)
- QA, testing, automation

**Common Course Titles:**
- "Python for Backend Development"
- "AWS Solutions Architect"
- "Kubernetes Administration"
- "Data Engineering with Apache Spark"
- "Ethical Hacking & Penetration Testing"

**Subdepartments:**
- `software-development` - Coding, APIs, frameworks
- `devops-infrastructure` - CI/CD, containers, orchestration
- `data-engineering` - ETL, data warehousing, big data
- `cybersecurity` - Security protocols, ethical hacking
- `cloud-architecture` - Cloud platforms, serverless
- `qa-testing` - Test automation, QA processes

---

### 2. Sales & Marketing (`sales-marketing`)

**Core Focus:** Revenue generation, customer acquisition, product strategy, go-to-market, brand building, innovation

**AI Classification Keywords:**
- Sales techniques, cold calling, enterprise sales, B2B/B2C
- Marketing strategy, digital marketing, SEO, SEM, social media
- Product management, roadmaps, user stories
- R&D, innovation, emerging technologies, product research
- Customer success, retention, upselling
- Brand positioning, messaging, content marketing

**Common Course Titles:**
- "Enterprise Sales Mastery"
- "Digital Marketing Strategy"
- "Product Management Fundamentals"
- "Innovation & Design Thinking"
- "Customer Success Best Practices"
- "Content Marketing for B2B"

**Subdepartments:**
- `sales-training` - Sales techniques, closing deals
- `sales-operations` - CRM, sales process, forecasting
- `marketing-strategy` - Go-to-market, campaigns
- `digital-marketing` - SEO, SEM, social media, ads
- `content-marketing` - Blogging, video, storytelling
- `product-strategy` - Product vision, roadmaps
- `product-management` - User stories, product lifecycle
- `r-and-d` - Innovation, research, emerging tech
- `customer-success` - Retention, onboarding, upselling
- `brand-positioning` - Brand identity, messaging

---

### 3. Customer Support & Customer Success (`customer-support`)

**Core Focus:** Post-sale support, technical troubleshooting, customer satisfaction, help desk operations, SLA management

**AI Classification Keywords:**
- Technical support, help desk, troubleshooting
- Customer success management, retention strategies
- Support tickets, ticketing systems (Zendesk, Freshdesk)
- SLA (Service Level Agreements), response times
- Customer communication, empathy training
- Support tools (live chat, email support, phone support)

**Common Course Titles:**
- "Technical Support Essentials"
- "Customer Success Manager Training"
- "Zendesk Administration"
- "Effective Customer Communication"
- "Managing SLAs and Escalations"

**Subdepartments:**
- `technical-support` - Troubleshooting, technical issues
- `customer-success-management` - Retention, account management
- `help-desk-operations` - Ticketing, workflow optimization
- `sla-management` - Service agreements, metrics
- `customer-communication` - Empathy, de-escalation
- `support-tools-training` - Zendesk, Intercom, etc.

**Note:** This is distinct from Sales & Marketing's "customer-success" subdepartment. This department focuses on **reactive support and troubleshooting**, while Sales/Marketing's customer success focuses on **proactive account growth and upselling**.

---

### 4. Operations, HR & Supply Chain (`operations-hr-supply`)

**Core Focus:** Internal operations, people management, supply chain, procurement, legal compliance, vendor management

**AI Classification Keywords:**
- HR policies, employee handbooks, benefits administration
- Talent development, training programs, performance reviews
- Recruitment, onboarding, hiring processes
- Operations management, SOPs, process optimization
- Supply chain, logistics, inventory management
- Procurement, vendor management, purchasing
- Legal compliance, contracts, employment law, corporate governance

**Common Course Titles:**
- "HR Management Fundamentals"
- "Supply Chain Optimization"
- "Employment Law for Managers"
- "Procurement Best Practices"
- "Operational Excellence"

**Subdepartments:**
- `hr-policies` - Employee handbooks, benefits
- `talent-development` - Training, career development
- `recruitment-onboarding` - Hiring, new employee integration
- `operations-management` - SOPs, process improvement
- `supply-chain-logistics` - Supply chain, distribution
- `procurement-vendor-mgmt` - Vendor selection, purchasing
- `inventory-management` - Stock control, warehousing
- `legal-compliance` - **Legal & Compliance subdepartment** - Employment law, contracts, regulatory compliance

---

### 5. Finance & Accounting (`finance-accounting`)

**Core Focus:** Financial planning, accounting standards, budgeting, tax compliance, audits, financial risk management

**AI Classification Keywords:**
- Financial planning, FP&A, financial modeling
- Accounting standards (GAAP, IFRS), bookkeeping
- Budgeting, forecasting, variance analysis
- Tax compliance, tax planning, IRS regulations
- Audits, internal controls, SOX compliance
- Risk management, financial risk assessment

**Common Course Titles:**
- "Financial Modeling in Excel"
- "GAAP Accounting Principles"
- "Corporate Tax Strategy"
- "Internal Audit Best Practices"
- "Risk Management Fundamentals"

**Subdepartments:**
- `financial-planning` - FP&A, financial modeling
- `accounting-standards` - GAAP, IFRS, bookkeeping
- `budgeting-forecasting` - Annual budgets, forecasts
- `tax-compliance` - Tax planning, IRS compliance
- `audit-controls` - Internal audits, SOX
- `risk-management` - Financial risk, hedging

---

### 6. Project Management (`project-management`)

**Core Focus:** Project execution methodologies, tools, stakeholder management, certifications (PMP, Scrum Master, etc.)

**AI Classification Keywords:**
- Agile, Scrum, Kanban, sprints, retrospectives
- Waterfall, PMBOK, Prince2, traditional PM
- PMP certification, Scrum Master, PMI
- Project management tools (Jira, Asana, MS Project, Monday.com)
- Stakeholder management, communication plans
- Risk management, scope management, time management

**Common Course Titles:**
- "Scrum Master Certification Prep"
- "PMP Exam Preparation"
- "Agile Project Management"
- "Jira for Project Managers"
- "Stakeholder Engagement Strategies"

**Subdepartments:**
- `agile-scrum` - Scrum, Kanban, Agile ceremonies
- `waterfall-traditional` - Waterfall, PMBOK, Prince2
- `pmp-certification` - PMP exam prep, PMI
- `tools-software` - Jira, Asana, MS Project, Monday.com
- `stakeholder-management` - Communication, engagement

**Note:** While PM is a standalone department for course organization, it will be incorporated as a subdepartment into each of the first 4 core business departments when designing CrewAI agent structures (future task).

---

### 7. Real Estate (`real-estate`)

**Core Focus:** Property management, commercial/residential real estate, real estate investment, development, leasing, real estate law

**AI Classification Keywords:**
- Property management, tenant relations, maintenance
- Commercial real estate (CRE), office buildings, retail
- Residential real estate, housing, apartments
- Real estate investment, REITs, property portfolios
- Property development, construction, zoning
- Leasing, lease agreements, contracts
- Real estate law, property rights, title insurance

**Common Course Titles:**
- "Commercial Real Estate Investment"
- "Property Management Essentials"
- "Real Estate Development Process"
- "Real Estate Law Fundamentals"
- "Residential Leasing Best Practices"
- "REIT Investment Strategies"

**Subdepartments:**
- `property-management` - Tenant management, maintenance
- `commercial-real-estate` - Office, retail, industrial properties
- `residential-real-estate` - Housing, apartments, condos
- `real-estate-investment` - REITs, property portfolios
- `property-development` - Construction, zoning, permits
- `leasing-contracts` - Lease agreements, terms
- `real-estate-law` - Property law, title, contracts

**Classification Guidance for AI:**
- If content mentions **property, real estate, leasing, landlord, tenant, commercial/residential properties** → likely Real Estate
- If content mentions **investment properties, REITs, cap rates, NOI** → Real Estate Investment subdepartment
- If content mentions **development, construction, zoning** → Property Development subdepartment

---

### 8. Private Equity & M&A (`private-equity-ma`)

**Core Focus:** Mergers & acquisitions, due diligence, deal structuring, valuation, private equity fundamentals, portfolio management, exit strategies

**AI Classification Keywords:**
- Mergers, acquisitions, M&A deals, transaction advisory
- Due diligence, financial due diligence, legal DD
- Deal structuring, LBO (leveraged buyout), equity financing
- Valuation, DCF (discounted cash flow), comparable analysis
- Private equity, PE funds, venture capital
- Portfolio management, post-acquisition integration
- Exit strategies, IPO, strategic sale, secondary buyout

**Common Course Titles:**
- "Mergers & Acquisitions Fundamentals"
- "Due Diligence Best Practices"
- "Private Equity Investing"
- "LBO Modeling and Valuation"
- "Post-Merger Integration"
- "Exit Strategy Planning"

**Subdepartments:**
- `mergers-acquisitions` - M&A strategy, transaction process
- `due-diligence` - Financial, legal, operational DD
- `deal-structuring` - LBO, equity/debt financing
- `valuation-modeling` - DCF, comps, precedent transactions
- `private-equity-fundamentals` - PE funds, VC, investment thesis
- `portfolio-management` - Post-acquisition, value creation
- `exit-strategies` - IPO, strategic sale, secondary

**Classification Guidance for AI:**
- If content mentions **M&A, mergers, acquisitions, takeover, consolidation** → Mergers & Acquisitions subdepartment
- If content mentions **private equity, PE fund, LBO, buyout** → Private Equity Fundamentals
- If content mentions **due diligence, DD, financial analysis of target company** → Due Diligence subdepartment
- If content mentions **valuation, DCF, enterprise value, EBITDA multiple** → Valuation & Modeling
- If content mentions **exit, IPO, strategic buyer, secondary buyout** → Exit Strategies

---

### 9. Consulting (`consulting`)

**Core Focus:** Management consulting, strategy consulting, consulting frameworks, client engagement, consulting skills, industry expertise

**AI Classification Keywords:**
- Management consulting, McKinsey, BCG, Bain
- Strategy consulting, corporate strategy, growth strategy
- Consulting frameworks (BCG Matrix, Porter's Five Forces, Ansoff Matrix, SWOT)
- Client engagement, stakeholder interviews, presentations
- Consulting skills, problem-solving, case interviews
- Industry expertise (healthcare, financial services, technology, etc.)

**Common Course Titles:**
- "Management Consulting Fundamentals"
- "Strategy Frameworks for Consultants"
- "Client Engagement Best Practices"
- "Case Interview Preparation"
- "Consulting Skills: Problem-Solving"
- "Healthcare Consulting Essentials"

**Subdepartments:**
- `management-consulting` - Consulting fundamentals, MBB firms
- `strategy-consulting` - Corporate strategy, growth
- `consulting-frameworks` - BCG Matrix, Porter's Five Forces, SWOT
- `client-engagement` - Stakeholder management, presentations
- `consulting-skills` - Problem-solving, case interviews
- `industry-expertise` - Vertical-specific consulting (healthcare, finance, tech)

**Classification Guidance for AI:**
- If content mentions **consulting, McKinsey, BCG, Bain, strategy consulting** → likely Consulting department
- If content mentions **frameworks like BCG Matrix, Porter's Five Forces, Ansoff** → Consulting Frameworks
- If content mentions **case interview, problem-solving, consulting skills** → Consulting Skills subdepartment
- If content mentions **client engagement, stakeholder interviews, consulting presentations** → Client Engagement

**Note:** This department is for courses on **how to be a consultant** or **consulting methodologies**, not for industry-specific courses (those go to their respective departments like IT, Finance, etc.).

---

### 10. Personal Continuing Education (`personal-continuing-ed`)

**Core Focus:** Personal development, psychology, NLP, life coaching, personal leadership, mindfulness, self-improvement

**AI Classification Keywords:**
- Psychology, behavioral psychology, cognitive psychology
- NLP (Neuro-Linguistic Programming), life coaching, personal coaching
- Personal leadership, self-leadership, emotional intelligence
- Mindfulness, meditation, wellness, mental health
- Self-improvement, personal growth, habit formation

**Common Course Titles:**
- "NLP Practitioner Certification" (virtualcoach.com)
- "Behavioral Psychology 101"
- "Personal Leadership Development"
- "Mindfulness for Professionals"
- "Habit Formation & Change"

**Subdepartments:**
- `psychology` - Behavioral, cognitive, applied psychology
- `nlp-coaching` - NLP, life coaching, personal coaching
- `personal-leadership` - Self-leadership, emotional intelligence
- `mindfulness-wellness` - Meditation, mental health, wellness
- `self-improvement` - Habit formation, personal growth

**Classification Guidance for AI:**
- If content mentions **psychology, behavioral science, cognitive science** → Psychology subdepartment
- If content mentions **NLP, neuro-linguistic programming, life coach, Tony Robbins-style** → NLP & Coaching
- If content mentions **personal leadership, emotional intelligence, self-awareness** → Personal Leadership
- If content mentions **mindfulness, meditation, wellness, mental health** → Mindfulness & Wellness

**Note:** This category is for **personal development content**, not business leadership. It will eventually feed into a separate personal growth/life coach system (future project).

---

## Enhanced Supabase Schema

### file_uploads Table

```sql
CREATE TABLE file_uploads (
    file_id UUID PRIMARY KEY,
    original_filename TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    content_type TEXT,
    b2_path TEXT NOT NULL,
    upload_source TEXT CHECK (upload_source IN ('web_ui', 'mountain_duck', 'api')),

    -- Department classification
    document_type TEXT CHECK (document_type IN ('course', 'general', 'youtube', 'reference')),
    department TEXT CHECK (department IN (
        'it-engineering',
        'sales-marketing',
        'customer-support',
        'operations-hr-supply',
        'finance-accounting',
        'project-management',
        'real-estate',
        'private-equity-ma',
        'consulting',
        'personal-continuing-ed'
    )),
    subdepartment TEXT,

    -- Content metadata
    description TEXT,
    tags TEXT[],  -- Array of tags
    course_title TEXT,
    instructor TEXT,
    duration_minutes INTEGER,

    -- Processing status
    status TEXT CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,

    -- AI extraction results
    extracted_topics TEXT[],
    confidence_score FLOAT,
    language TEXT DEFAULT 'en'
);

-- Indexes
CREATE INDEX idx_file_uploads_department ON file_uploads(department);
CREATE INDEX idx_file_uploads_subdepartment ON file_uploads(subdepartment);
CREATE INDEX idx_file_uploads_document_type ON file_uploads(document_type);
CREATE INDEX idx_file_uploads_status ON file_uploads(status);
CREATE INDEX idx_file_uploads_created_at ON file_uploads(created_at DESC);
CREATE INDEX idx_file_uploads_tags ON file_uploads USING GIN(tags);
```

### courses Table

```sql
CREATE TABLE courses (
    course_id UUID PRIMARY KEY,
    file_id UUID REFERENCES file_uploads(file_id),

    -- Course metadata
    title TEXT NOT NULL,
    description TEXT,
    instructor TEXT,
    department TEXT NOT NULL CHECK (department IN (
        'it-engineering',
        'sales-marketing',
        'customer-support',
        'operations-hr-supply',
        'finance-accounting',
        'project-management',
        'real-estate',
        'private-equity-ma',
        'consulting',
        'personal-continuing-ed'
    )),
    subdepartment TEXT,

    -- Content structure
    total_modules INTEGER,
    total_lessons INTEGER,
    duration_minutes INTEGER,
    difficulty_level TEXT CHECK (difficulty_level IN ('beginner', 'intermediate', 'advanced')),

    -- Completion tracking
    completion_rate FLOAT,  -- % of employees who completed
    average_rating FLOAT,
    total_enrollments INTEGER DEFAULT 0,

    -- Tags and categorization
    tags TEXT[],
    prerequisites TEXT[],
    learning_objectives TEXT[],

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_courses_department ON courses(department);
CREATE INDEX idx_courses_subdepartment ON courses(subdepartment);
CREATE INDEX idx_courses_tags ON courses USING GIN(tags);
```

---

## Auto-Classification System

### Enhanced Department Auto-Classification with Claude

```python
import anthropic
import os
import json

async def auto_classify_course(filename: str, content_preview: str) -> dict:
    """
    Auto-classify course into department and subdepartment using Claude

    Returns:
        {
            "department": "private-equity-ma",
            "subdepartment": "mergers-acquisitions",
            "confidence": 0.92,
            "reasoning": "Content focuses on M&A deal structuring...",
            "suggested_tags": ["m&a", "deal-structure", "acquisition"]
        }
    """

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Analyze this course material and classify it into the appropriate department and subdepartment.

Filename: {filename}
Content Preview: {content_preview[:3000]}

DEPARTMENTS AND SUBDEPARTMENTS:

1. IT & Engineering (it-engineering)
   - software-development, devops-infrastructure, data-engineering, cybersecurity, cloud-architecture, qa-testing
   - Keywords: programming, DevOps, data pipelines, security, AWS/Azure, testing

2. Sales & Marketing (sales-marketing)
   - sales-training, sales-operations, marketing-strategy, digital-marketing, content-marketing, product-strategy, product-management, r-and-d, customer-success, brand-positioning
   - Keywords: sales techniques, marketing campaigns, product roadmaps, innovation, customer retention

3. Customer Support & Success (customer-support)
   - technical-support, customer-success-management, help-desk-operations, sla-management, customer-communication, support-tools-training
   - Keywords: technical support, help desk, troubleshooting, SLA, Zendesk, customer satisfaction
   - NOTE: Distinct from sales-marketing's customer-success (reactive support vs proactive growth)

4. Operations, HR & Supply Chain (operations-hr-supply)
   - hr-policies, talent-development, recruitment-onboarding, operations-management, supply-chain-logistics, procurement-vendor-mgmt, inventory-management, legal-compliance
   - Keywords: HR, employee management, supply chain, procurement, legal compliance, operations

5. Finance & Accounting (finance-accounting)
   - financial-planning, accounting-standards, budgeting-forecasting, tax-compliance, audit-controls, risk-management
   - Keywords: FP&A, GAAP, budgeting, tax, audits, financial risk

6. Project Management (project-management)
   - agile-scrum, waterfall-traditional, pmp-certification, tools-software, stakeholder-management
   - Keywords: Agile, Scrum, PMP, Jira, project execution, stakeholder engagement

7. Real Estate (real-estate)
   - property-management, commercial-real-estate, residential-real-estate, real-estate-investment, property-development, leasing-contracts, real-estate-law
   - Keywords: property, real estate, leasing, tenant, landlord, REITs, property development, zoning

8. Private Equity & M&A (private-equity-ma)
   - mergers-acquisitions, due-diligence, deal-structuring, valuation-modeling, private-equity-fundamentals, portfolio-management, exit-strategies
   - Keywords: M&A, mergers, acquisitions, private equity, LBO, due diligence, valuation, DCF, exit strategy

9. Consulting (consulting)
   - management-consulting, strategy-consulting, consulting-frameworks, client-engagement, consulting-skills, industry-expertise
   - Keywords: McKinsey, BCG, consulting, strategy frameworks, BCG Matrix, Porter's Five Forces, case interview

10. Personal Continuing Education (personal-continuing-ed)
    - psychology, nlp-coaching, personal-leadership, mindfulness-wellness, self-improvement
    - Keywords: psychology, NLP, life coaching, personal growth, mindfulness, emotional intelligence
    - NOTE: For personal development, not business leadership

CLASSIFICATION RULES:
- Use department slug format (e.g., "private-equity-ma", not "Private Equity & M&A")
- Use subdepartment slug format (e.g., "mergers-acquisitions", not "Mergers & Acquisitions")
- Provide confidence score (0.0-1.0)
- Include reasoning for classification decision
- Suggest 3-5 relevant tags

Respond in JSON format:
{{
    "department": "private-equity-ma",
    "subdepartment": "mergers-acquisitions",
    "confidence": 0.92,
    "reasoning": "Content focuses on M&A deal structuring and transaction process",
    "suggested_tags": ["m&a", "deal-structure", "acquisition", "transaction"]
}}
"""

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",  # Fast and cheap for classification
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(response.content[0].text)
    return result
```

---

## Summary

✅ **10 Departments in Empire:**
1. **IT & Engineering** - Technology, software, infrastructure, data, security
2. **Sales & Marketing** - Revenue, customer acquisition, product strategy, R&D
3. **Customer Support & Customer Success** - Technical support, help desk, customer satisfaction
4. **Operations, HR & Supply Chain** - People, processes, supply chain, **legal & compliance**
5. **Finance & Accounting** - Financial planning, accounting, tax, audits
6. **Project Management** - Agile, Scrum, PMP, project execution (standalone department)
7. **Real Estate** - Property management, CRE, real estate investment, development
8. **Private Equity & M&A** - Mergers, acquisitions, due diligence, PE fundamentals
9. **Consulting** - Management consulting, strategy, frameworks, client engagement
10. **Personal Continuing Education** - Psychology, NLP, coaching, personal growth

✅ **Key Notes:**
- **Legal & Compliance** is a subdepartment under Operations, HR & Supply Chain
- **Project Management** has its own folder but will be incorporated into CrewAI agent structures for each business department (future task)
- **Personal Continuing Education** will eventually feed into a separate personal growth/life coach system (future project)
- **AI Auto-Classification** uses Claude Haiku with detailed context to accurately place courses

✅ **Upload Methods:**
- **Web UI**: Department dropdown selection
- **Mountain Duck**: Auto-classification via Claude Haiku (30-second polling)

---

## CrewAI Suggestions & Production Structure

### CrewAI Suggestions Folder Structure

When CrewAI analyzes course content, it generates actionable suggestions stored in `processed/crewai-suggestions/`:

```
processed/crewai-suggestions/
│
├── claude-skills/                   # YAML skill definitions for Claude Code
│   ├── drafts/                     # Newly generated, needs review
│   └── approved/                   # Reviewed and ready for production
│
├── claude-commands/                 # Markdown slash commands
│   ├── drafts/
│   └── approved/
│
├── agents/                          # CrewAI agent definitions
│   ├── drafts/
│   └── approved/
│
├── prompts/                         # AI prompts and templates (NEW)
│   ├── drafts/
│   └── approved/
│
└── workflows/                       # n8n workflow definitions (NEW)
    ├── drafts/
    └── approved/
```

**Asset Types Explained:**

1. **`claude-skills/`** - YAML skill definitions that extend Claude Code capabilities
   - Example: `project-charter-generator.yaml`
   - Used for: Automating common tasks in Claude Code

2. **`claude-commands/`** - Markdown slash commands for quick actions
   - Example: `review-pr.md`, `analyze-metrics.md`
   - Used for: Custom `/commands` in Claude Desktop

3. **`agents/`** - CrewAI agent configurations for multi-agent workflows
   - Example: `sales-agent-config.yaml`, `finance-analyst.yaml`
   - Used for: Deploying specialized AI agents per department

4. **`prompts/`** - AI prompt templates and engineering patterns (NEW)
   - Example: `sales-proposal-template.md`, `code-review-prompt.yaml`
   - Used for: Consistent, high-quality AI interactions

5. **`workflows/`** - n8n workflow JSON definitions (NEW)
   - Example: `document-intake-enhanced.json`, `course-analysis.json`
   - Used for: Automating document processing pipelines

### Production Folder Structure (Department-based)

Once suggestions are approved, they're promoted to `production/` for active use:

```
production/
│
├── _global/                         # Cross-department assets
│   ├── claude-skills/
│   ├── claude-commands/
│   ├── crewai-agents/
│   ├── prompts/
│   └── workflows/
│
├── _versions/                       # Rollback backups
│   └── [timestamped backups]
│
├── it-engineering/                  # Department-specific assets
│   ├── claude-skills/
│   ├── claude-commands/
│   ├── crewai-agents/
│   ├── prompts/
│   └── workflows/
│
├── sales-marketing/
│   ├── claude-skills/
│   ├── claude-commands/
│   ├── crewai-agents/
│   ├── prompts/
│   └── workflows/
│
├── customer-support/
│   └── [same structure]
│
├── operations-hr-supply/
│   └── [same structure]
│
├── finance-accounting/
│   └── [same structure]
│
├── project-management/
│   └── [same structure]
│
├── real-estate/
│   └── [same structure]
│
├── private-equity-ma/
│   └── [same structure]
│
├── consulting/
│   └── [same structure]
│
└── personal-continuing-ed/
    └── [same structure]
```

### Promotion Workflow

```mermaid
1. CrewAI analyzes course content
   ↓
2. Generates suggestions → `drafts/`
   ↓
3. You review and test → Move to `approved/`
   ↓
4. Ready for production? → Run promotion script
   ↓
5. Asset copied to `production/{department}/`
   ↓
6. n8n workflows and Claude Code read from production
   ↓
7. Old version backed up to `production/_versions/`
```

**Example: Promoting a Project Charter Skill**

```bash
# Step 1: CrewAI generates suggestion WITH DEPARTMENT PREFIX
processed/crewai-suggestions/claude-skills/drafts/project-management_project-charter-generator.yaml

# Step 2: You review and approve
mv drafts/project-management_project-charter-generator.yaml \
   approved/project-management_project-charter-generator.yaml

# Step 3: Promote to production (auto-detects department from filename!)
python scripts/promote_to_production.py

# Interactive prompts:
#   Asset type: 1 (claude-skills)
#   File: 1 (project-management_project-charter-generator.yaml)
#   ✅ Auto-detected department: project-management
#   📝 Production filename: project-charter-generator.yaml
#   Use auto-detected department? yes

# Step 4: Now in production! (department prefix removed)
production/project-management/claude-skills/project-charter-generator.yaml

# Your workflows can now use it:
# - Claude Code loads skills from production/
# - n8n reads from production/{dept}/ folders
```

### Filename Naming Convention (IMPORTANT!)

All CrewAI-generated suggestions **MUST** follow this format:

```
{department}_{asset-name}.{extension}
```

**Examples:**
- `sales-marketing_proposal-generator.yaml`
- `it-engineering_code-review-checklist.md`
- `finance-accounting_budget-analysis-prompt.md`
- `_global_meeting-summarizer.yaml` (cross-department)

**Why?**
- Automatic department detection during promotion
- No manual department selection needed
- Clean filenames in production (prefix removed)
- Easy to see which department each draft belongs to

**Department Codes:**
```
it-engineering
sales-marketing
customer-support
operations-hr-supply
finance-accounting
project-management
real-estate
private-equity-ma
consulting
personal-continuing-ed
_global (cross-department)
```

See `CREWAI_OUTPUT_GUIDELINES.md` for complete filename standards.

### Production Asset Management

**Versioning:**
- Every production update creates a timestamped backup in `production/_versions/`
- Rollback: Copy previous version back from `_versions/`

**Global vs. Department-specific:**
- **`_global/`** - Assets used across all departments (e.g., "Meeting Summarizer")
- **`{department}/`** - Department-specific assets (e.g., "Sales Proposal Generator" in `sales-marketing/`)

**Scripts Available:**
1. **`scripts/setup_b2_production_structure.py`** - Creates all production folders
2. **`scripts/promote_to_production.py`** - Interactive promotion tool

### Integration with Workflows

**n8n Workflow Example:**

```javascript
// Load production skills for department
const department = "sales-marketing";
const assetType = "claude-skills";
const b2Path = `production/${department}/${assetType}/`;

// List all production skills
const skills = await b2.listFiles(b2Path);

// Load and execute skill
for (const skill of skills) {
  const skillContent = await b2.downloadFile(skill.fileName);
  // Use skill in your workflow
}
```

**Claude Code Integration:**

```yaml
# claude_desktop_config.json
{
  "skills": {
    "source": "b2://JB-Course-KB/production/_global/claude-skills/"
  }
}
```

---

**Last Updated**: 2025-01-02
**Empire Version**: v7.2 Enhanced
**Status**: Complete with production structure + CrewAI suggestions (5 asset types)
