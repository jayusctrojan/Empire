# CrewAI Output Guidelines - Empire v7.2

## Filename Naming Convention

When CrewAI generates suggestions, filenames **MUST** include the department to enable automatic routing to production.

### Filename Format

```
{department}_{asset-name}.{extension}
```

**Examples:**
```
sales-marketing_proposal-generator.yaml
it-engineering_code-review-checklist.md
finance-accounting_budget-analysis-prompt.md
project-management_project-charter-skill.yaml
_global_meeting-summarizer.yaml
```

### Department Codes

Use these exact slugs in filenames:

| Department Code | Full Name |
|-----------------|-----------|
| `it-engineering` | IT & Engineering |
| `sales-marketing` | Sales & Marketing |
| `customer-support` | Customer Support & Success |
| `operations-hr-supply` | Operations, HR & Supply Chain |
| `finance-accounting` | Finance & Accounting |
| `project-management` | Project Management |
| `real-estate` | Real Estate |
| `private-equity-ma` | Private Equity & M&A |
| `consulting` | Consulting |
| `personal-continuing-ed` | Personal Continuing Education |
| `_global` | Cross-department (used by all) |

### Asset Types & Extensions

| Asset Type | Extension | Description | Example |
|------------|-----------|-------------|---------|
| **claude-skills** | `.yaml` | Claude Code skill definitions | `sales-marketing_objection-handler.yaml` |
| **claude-commands** | `.md` | Slash commands for Claude | `it-engineering_review-pr.md` |
| **agents** | `.yaml` | CrewAI agent configurations | `finance-accounting_analyst-agent.yaml` |
| **prompts** | `.md` or `.yaml` | AI prompt templates | `consulting_client-brief-prompt.md` |
| **workflows** | `.json` | n8n workflow definitions | `operations-hr-supply_onboarding-workflow.json` |

## File Structure in B2

### Suggestions Workflow

```
1. CrewAI generates suggestion
   ↓
   processed/crewai-suggestions/{asset-type}/drafts/{department}_{name}.{ext}

2. You review and approve
   ↓
   processed/crewai-suggestions/{asset-type}/approved/{department}_{name}.{ext}

3. Promotion script extracts department from filename
   ↓
   production/{department}/{asset-type}/{name}.{ext}
   (department prefix removed in production)
```

### Example Flow

```bash
# 1. CrewAI generates
processed/crewai-suggestions/claude-skills/drafts/sales-marketing_proposal-generator.yaml

# 2. Move to approved after review
processed/crewai-suggestions/claude-skills/approved/sales-marketing_proposal-generator.yaml

# 3. Run promotion script (auto-detects department from filename)
python3 scripts/promote_to_production.py

# 4. Promoted to correct department
production/sales-marketing/claude-skills/proposal-generator.yaml
```

## CrewAI Output Templates

### 1. Claude Skills (YAML)

**Filename:** `{department}_skill-name.yaml`

```yaml
# FILE: sales-marketing_objection-handler.yaml
name: sales-objection-handler
description: Handles common sales objections with proven responses
department: sales-marketing
version: 1.0.0
author: CrewAI Analysis Engine
created: 2025-01-02

parameters:
  objection_type:
    description: Type of objection (price, timing, competition, need)
    required: true

  customer_context:
    description: Customer background and situation
    required: false

prompt: |
  You are a sales expert specializing in handling objections.

  Customer objection: {{objection_type}}
  Context: {{customer_context}}

  Provide a structured response that:
  1. Acknowledges the concern
  2. Reframes the objection
  3. Provides value-based counter
  4. Asks for commitment

  Format as a conversation script.

examples:
  - input:
      objection_type: "Too expensive"
      customer_context: "Mid-size SaaS company"
    output: |
      "I understand budget is a key concern..."
```

### 2. Claude Commands (Markdown)

**Filename:** `{department}_command-name.md`

```markdown
<!-- FILE: it-engineering_review-pr.md -->
# /review-pr - Code Review Assistant

**Department:** it-engineering
**Version:** 1.0.0
**Created:** 2025-01-02

## Description
Performs comprehensive code review with engineering best practices.

## Usage
```
/review-pr <PR-URL or PR-number>
```

## Checklist
- [ ] Code follows style guide
- [ ] Tests included and passing
- [ ] Documentation updated
- [ ] No security vulnerabilities
- [ ] Performance considerations addressed
- [ ] Error handling implemented
- [ ] Logging added appropriately

## Output Format
Provides structured feedback:
1. **Summary:** High-level assessment
2. **Critical Issues:** Must-fix before merge
3. **Suggestions:** Nice-to-have improvements
4. **Praise:** What was done well

## Examples
```
/review-pr https://github.com/user/repo/pull/123
/review-pr 123
```
```

### 3. CrewAI Agents (YAML)

**Filename:** `{department}_agent-name.yaml`

```yaml
# FILE: finance-accounting_analyst-agent.yaml
name: financial-analyst-agent
department: finance-accounting
version: 1.0.0
created: 2025-01-02

role: Financial Analyst
goal: Analyze financial data and provide actionable insights

backstory: |
  You are an experienced financial analyst with expertise in
  financial modeling, ratio analysis, and forecasting. You excel
  at turning complex financial data into clear recommendations.

tools:
  - excel_analyzer
  - ratio_calculator
  - trend_analyzer
  - report_generator

capabilities:
  - Financial statement analysis
  - Ratio analysis (liquidity, profitability, efficiency)
  - Trend identification
  - Forecasting and projections
  - Risk assessment

output_format:
  - Executive summary
  - Detailed analysis
  - Key metrics dashboard
  - Recommendations
  - Risk assessment

max_iterations: 3
allow_delegation: true
verbose: true
```

### 4. Prompts (Markdown)

**Filename:** `{department}_prompt-name.md`

```markdown
<!-- FILE: consulting_client-brief-prompt.md -->
# Client Project Brief Generator

**Department:** consulting
**Type:** prompt-template
**Version:** 1.0.0

## Context
This prompt generates comprehensive client project briefs for consulting engagements.

## Input Variables
- `{{client_name}}` - Client organization name
- `{{industry}}` - Client's industry
- `{{challenge}}` - Primary business challenge
- `{{timeline}}` - Project timeline
- `{{budget}}` - Budget range

## Prompt Template

```
You are a management consultant preparing a project brief for a new engagement.

CLIENT: {{client_name}}
INDUSTRY: {{industry}}
CHALLENGE: {{challenge}}
TIMELINE: {{timeline}}
BUDGET: {{budget}}

Generate a comprehensive project brief with:

1. EXECUTIVE SUMMARY
   - Client overview
   - Core challenge
   - Proposed approach

2. SITUATION ANALYSIS
   - Current state assessment
   - Root cause analysis
   - Impact quantification

3. PROPOSED SOLUTION
   - Methodology (e.g., McKinsey 7S, Porter's Five Forces)
   - Workstreams
   - Deliverables
   - Timeline with milestones

4. TEAM STRUCTURE
   - Roles needed
   - Time allocation
   - Expertise required

5. SUCCESS METRICS
   - KPIs
   - Measurement approach
   - Expected outcomes

6. RISKS & MITIGATION
   - Key risks
   - Mitigation strategies
   - Contingency plans

Format as a professional consulting document.
```

## Example Usage

**Input:**
```
client_name: Acme Corp
industry: Retail
challenge: Declining in-store sales
timeline: 3 months
budget: $250K
```

**Output:** 15-page professional project brief
```

### 5. Workflows (JSON)

**Filename:** `{department}_workflow-name.json`

```json
{
  "name": "operations-hr-supply_employee-onboarding",
  "department": "operations-hr-supply",
  "version": "1.0.0",
  "created": "2025-01-02",
  "description": "Automated employee onboarding workflow",

  "nodes": [
    {
      "type": "webhook",
      "name": "New Hire Trigger",
      "parameters": {
        "path": "new-hire"
      }
    },
    {
      "type": "supabase",
      "name": "Create Employee Record",
      "parameters": {
        "operation": "insert",
        "table": "employees"
      }
    },
    {
      "type": "sendgrid",
      "name": "Send Welcome Email",
      "parameters": {
        "template_id": "welcome-new-hire"
      }
    },
    {
      "type": "slack",
      "name": "Notify HR Team",
      "parameters": {
        "channel": "#hr-onboarding"
      }
    }
  ],

  "connections": {
    "New Hire Trigger": ["Create Employee Record"],
    "Create Employee Record": ["Send Welcome Email", "Notify HR Team"]
  }
}
```

## Validation Rules

### Required Fields in All Files

1. **Department identifier** in filename (e.g., `sales-marketing_`)
2. **Version number** in file metadata
3. **Created date** in ISO format
4. **Description** explaining purpose

### Department Assignment Logic

CrewAI should assign department based on:

1. **Content Analysis:**
   - Keywords in course material
   - Primary topic/domain
   - Target audience

2. **Multiple Departments:**
   - If applicable to multiple departments → use `_global`
   - If uncertain → use the PRIMARY department
   - Can create variants for different departments

3. **Examples:**
   ```
   "Project Charter Creation" → project-management
   "Sales Forecasting Model" → sales-marketing
   "Meeting Notes Template" → _global (all departments)
   "Code Review Process" → it-engineering
   "M&A Due Diligence Checklist" → private-equity-ma
   ```

## Quality Standards

### All Outputs Must:

- ✅ Follow naming convention: `{department}_{name}.{ext}`
- ✅ Include version number
- ✅ Have clear description
- ✅ Be tested/validated before moving to approved/
- ✅ Include usage examples
- ✅ Specify department in metadata
- ✅ Be production-ready (no placeholders)

### File Size Limits

- Claude Skills: < 10 KB
- Claude Commands: < 5 KB
- Agents: < 20 KB
- Prompts: < 15 KB
- Workflows: < 50 KB

## Promotion Workflow

The promotion script will:

1. **Extract department** from filename prefix
2. **Validate** department code exists
3. **Remove department prefix** from production filename
4. **Place in correct folder:** `production/{department}/{asset-type}/`

**Example:**
```
Input:  sales-marketing_proposal-generator.yaml
Extract: department = "sales-marketing"
Output: production/sales-marketing/claude-skills/proposal-generator.yaml
```

## Special Cases

### Global Assets

Use `_global` prefix for cross-department assets:

```
_global_meeting-summarizer.yaml
_global_email-writer.md
_global_document-reviewer.yaml
```

These will be placed in:
```
production/_global/{asset-type}/
```

### Multi-Department Assets

If an asset applies to multiple specific departments (not global):

1. Generate separate files for each department
2. Use department-specific examples
3. Optimize for department context

```
sales-marketing_pipeline-manager.yaml
customer-support_pipeline-manager.yaml
```

---

**Last Updated:** 2025-01-02
**Empire Version:** v7.2 Enhanced
**Status:** Active - Department-based filename convention
