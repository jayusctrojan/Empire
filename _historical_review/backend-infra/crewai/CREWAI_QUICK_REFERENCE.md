# CrewAI Quick Reference Guide
## Empire v7.2 - Agent Knowledge Base

### 1. Asset Type Decision Matrix

| Content Type | Recommended Asset | Key Indicators |
|-------------|-------------------|----------------|
| **Claude Skill** | `.yaml` | • Complex automation with parameters<br>• Reusable logic patterns<br>• Multi-step processes<br>• Error handling required<br>• Time-saving automation |
| **Claude Command** | `.md` | • Quick one-liner actions<br>• Simple lookups or queries<br>• Frequently used shortcuts<br>• No complex logic<br>• Slash command format |
| **Agent** | `.yaml` | • Role-based analysis<br>• Multi-step intelligence<br>• Requires collaboration<br>• Complex decision-making<br>• Autonomous execution |
| **Prompt** | `.md` | • Reusable templates<br>• Standardized formats<br>• Variable placeholders<br>• Quality consistency<br>• DEFAULT when unsure |
| **Workflow** | `.json` | • Multi-system integration<br>• Sequential pipelines<br>• Scheduled automation<br>• Event-driven processes<br>• Data transformation |

### 2. Department Classification Keywords

| Department | Primary Keywords | Content Examples |
|------------|------------------|------------------|
| `it-engineering` | API, code, development, programming, software | Technical docs, API guides, coding tutorials |
| `sales-marketing` | CRM, lead, pipeline, campaign, funnel | Sales training, marketing strategies |
| `customer-support` | ticket, helpdesk, service, resolution | Support guides, FAQ docs |
| `operations-hr-supply` | HR, recruiting, supply chain, logistics | HR policies, operations manuals |
| `finance-accounting` | budget, forecast, accounting, financial | Financial reports, accounting guides |
| `project-management` | agile, scrum, gantt, milestone | PM methodologies, planning docs |
| `real-estate` | property, lease, mortgage, tenant | Real estate contracts, property guides |
| `private-equity-ma` | acquisition, merger, valuation, due diligence | M&A docs, PE strategies |
| `consulting` | strategy, analysis, recommendation | Consulting frameworks, reports |
| `personal-continuing-ed` | learning, course, education, skill | Personal development, online courses |
| `_global` | Cross-department content, general resources | Company-wide policies, general tools |

### 3. Output Directory Structure

```
processed/
├── crewai-summaries/          # PDF summaries with visuals
│   ├── it-engineering/
│   ├── sales-marketing/
│   ├── customer-support/
│   ├── operations-hr-supply/
│   ├── finance-accounting/
│   ├── project-management/
│   ├── real-estate/
│   ├── private-equity-ma/
│   ├── consulting/
│   ├── personal-continuing-ed/
│   └── _global/
│
└── crewai-suggestions/        # Generated assets
    ├── claude-skills/
    │   ├── drafts/           # Newly generated
    │   └── approved/         # Reviewed and approved
    ├── claude-commands/
    │   ├── drafts/
    │   └── approved/
    ├── agents/
    │   ├── drafts/
    │   └── approved/
    ├── prompts/
    │   ├── drafts/
    │   └── approved/
    └── workflows/
        ├── drafts/
        └── approved/
```

### 4. Filename Convention

**Format:** `{department}_{descriptive-name}.{extension}`

**Examples:**
- `sales-marketing_lead-scoring-automation.yaml` (skill)
- `it-engineering_api-test.md` (command)
- `finance-accounting_budget-analyst.yaml` (agent)
- `customer-support_ticket-response.md` (prompt)
- `operations-hr-supply_onboarding-flow.json` (workflow)

### 5. Content Analysis Priorities

#### When to Generate PDF Summary:
✅ **Always Generate For:**
- Educational/training materials
- Complex technical documentation
- Strategic frameworks and methodologies
- Implementation guides
- Materials with tables/charts/diagrams
- Course modules or learning content

❌ **Skip Summary For:**
- Simple reference documents
- Short code snippets
- Basic commands or scripts
- Single-purpose templates
- Brief announcements

### 6. Agent Roles Quick Reference

| Agent | Primary Responsibility | Key Output |
|-------|------------------------|------------|
| **Main Orchestrator** | Analyze & route content | Classification & delegation |
| **Content Summarizer** | Create visual PDFs | Comprehensive summaries |
| **Skill Generator** | Build automation | YAML skill definitions |
| **Command Generator** | Quick actions | Markdown commands |
| **Agent Generator** | Role-based agents | Agent configurations |
| **Prompt Generator** | AI templates | Reusable prompts |
| **Workflow Generator** | n8n workflows | JSON workflows |
| **Department Classifier** | Categorization | Department assignment |

### 7. Quality Checklist

#### For All Assets:
- [ ] Correct department classification
- [ ] Proper filename format
- [ ] Complete documentation
- [ ] No placeholders or TODOs
- [ ] Production-ready code
- [ ] Usage examples included

#### For PDF Summaries:
- [ ] Executive summary on page 1
- [ ] Clear section headers
- [ ] Tables extracted and formatted
- [ ] Frameworks identified
- [ ] Visual elements preserved
- [ ] Implementation guides included
- [ ] Quick reference section

### 8. Processing Pipeline

```mermaid
graph TD
    A[Content Input] --> B[Main Orchestrator]
    B --> C{Department?}
    C --> D[Department Classifier]
    D --> E{Asset Types?}
    E --> F{Needs Summary?}

    F -->|Yes| G[Content Summarizer]
    G --> H[PDF with Visuals]
    H --> I[crewai-summaries/{dept}/]

    E -->|Skill| J[Skill Generator]
    E -->|Command| K[Command Generator]
    E -->|Agent| L[Agent Generator]
    E -->|Prompt| M[Prompt Generator]
    E -->|Workflow| N[Workflow Generator]

    J --> O[crewai-suggestions/*/drafts/]
    K --> O
    L --> O
    M --> O
    N --> O
```

### 9. Decision Logic Examples

#### Example 1: Sales Training Course
- **Department:** `sales-marketing`
- **Assets to Generate:**
  - Skill: Lead qualification automation
  - Agent: Sales coach agent
  - Prompt: Cold email templates
  - Summary: PDF with frameworks (BANT, MEDDIC)

#### Example 2: API Documentation
- **Department:** `it-engineering`
- **Assets to Generate:**
  - Command: Quick API test commands
  - Workflow: API integration sequence
  - Summary: PDF with endpoint tables

#### Example 3: HR Policy Document
- **Department:** `operations-hr-supply`
- **Assets to Generate:**
  - Prompt: Policy communication template
  - Workflow: Onboarding checklist
  - Summary: PDF with process flows

### 10. Integration Points

**Input Sources:**
- Web content scrapers
- Document uploads
- Video transcripts
- Course materials
- API documentation

**Output Consumers:**
- Claude Desktop (skills/commands)
- CrewAI system (agents)
- n8n workflows
- AI assistants (prompts)
- Knowledge base (PDFs)

### 11. Performance Targets

- Classification accuracy: >95%
- Asset generation time: <30 seconds
- PDF generation: <60 seconds
- Parallel processing: 10+ documents
- Local processing: 98% on Mac Studio

### 12. Error Handling

**Common Issues & Solutions:**
1. **Ambiguous Department** → Default to `_global`
2. **Unknown Asset Type** → Default to `prompt`
3. **Large Documents** → Chunk and process in stages
4. **Missing Visuals** → Note in PDF, continue processing
5. **Rate Limits** → Queue and retry with backoff

### 13. Version Control

**Asset Lifecycle:**
1. Generated → `drafts/` folder
2. Reviewed → Human validation
3. Approved → Move to `approved/`
4. Deployed → Production use
5. Updated → Version in filename

### 14. Key Rules

1. **ALWAYS** classify into a department
2. **ALWAYS** use correct filename format
3. **DEFAULT** to prompt when asset type unclear
4. **PRIORITIZE** local processing on Mac Studio
5. **INCLUDE** examples in all generated assets
6. **EXTRACT** all visual elements for PDFs
7. **PRESERVE** original content structure
8. **VALIDATE** all outputs before saving

### 15. Quick Command Reference

```bash
# Test classification
python empire_crew_config.py --classify "content"

# Generate specific asset
python empire_crew_config.py --generate skill --content "..."

# Batch process documents
python empire_crew_config.py --batch /path/to/docs/

# Generate summary only
python empire_crew_config.py --summary-only "content"
```

---

*This quick reference is designed for CrewAI agents to make fast, accurate decisions about content classification and asset generation. Keep this document updated as new patterns emerge.*