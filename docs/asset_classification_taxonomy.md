# Empire Asset Classification Taxonomy

**Research compiled by Ava**
**Date:** January 2025

---

## Overview

This document defines the official taxonomy for classifying assets in the Empire AI Studio. It provides clear distinctions between asset types, decision logic for AGENT-002 (Asset Classifier), and tiebreaker rules for edge cases.

---

## Asset Type Definitions

### 1. SKILL

**Definition:** A modular directory of expertise containing structured files (SKILL.md + scripts/examples) that Claude can auto-trigger based on context.

**Characteristics:**
- **Structure:** Directory with multiple files (SKILL.md, examples/, scripts/)
- **Trigger:** Claude auto-invokes based on detected context/intent
- **Complexity:** Can contain logic, scripts, multiple examples
- **Use Case:** Reusable expertise that applies across conversations

**Example:** Project Charter Skill
```
skills/project-charter/
├── SKILL.md          # Skill definition and instructions
├── template.md       # Charter template with {{variables}}
├── examples/
│   └── completed-charter.md
└── scripts/
    └── generate.py   # Optional automation
```

**When to classify as SKILL:**
- Requires a folder structure
- Contains reusable templates + examples
- Claude should auto-detect when to use it
- Involves multi-file coordination

---

### 2. SLASH COMMAND

**Definition:** A single-file, user-invoked shortcut (.md) that the user explicitly types to trigger.

**Characteristics:**
- **Structure:** Single markdown file
- **Trigger:** User types `/command-name` explicitly
- **Complexity:** Simple, focused action
- **Use Case:** Quick actions, macros, shortcuts

**Example:** `/summarize` command
```markdown
# /summarize

Summarize the following content in 3 bullet points:

{{content}}
```

**When to classify as SLASH COMMAND:**
- Single file (no directory needed)
- User must explicitly invoke
- Performs one focused action
- Acts as a shortcut/macro

---

### 3. GENERATIVE BLUEPRINT

**Definition:** A proven, precision instruction set (prompt library) that reliably produces flawless structured output. Curated in collaboration with Claude.

**Characteristics:**
- **Structure:** Battle-tested instructions stored as reusable recipes
- **Trigger:** User needs reliable, consistent output for a specific structure
- **Complexity:** Precision prompting to ensure flawless, repeatable results
- **Use Case:** Building external tools, databases, schemas, UI components, documents
- **Routes to:** AGENT-005 (Blueprint Librarian)

**Distinguishing Factor:** Precision Output Focus. These are **proven instructions** that have been refined to consistently produce flawless results. It's the **recipe library** that ensures perfect structural assets every time.

**Examples:**
- "Construct an Airtable base with 6 tables, these 12 linked fields, and this specific automation logic."
- "Generate a clean Tailwind CSS landing page with a 3-column pricing grid and a sticky nav."
- "Create a PostgreSQL schema for a multi-tenant SaaS with RLS policies enabled."
- "Generate a complete project charter with executive summary, objectives, and milestones."
- "Create a business plan with market analysis and financial projections."

**When to classify as GENERATIVE BLUEPRINT:**
- Needs proven, reliable instructions that produce consistent output
- Creates a tool/structure as output (not performs an action)
- Builds something in an external platform (Airtable, SQL, Tailwind, etc.)
- Requires precision prompting to avoid hallucinated fields/syntax
- The output should be flawless and repeatable

---

### 4. WORKFLOW

**Definition:** Multi-step orchestration with external API calls, state management, and conditional branching.

**Characteristics:**
- **Structure:** State machine or pipeline definition
- **Trigger:** Event-driven or scheduled
- **Complexity:** External integrations, state tracking, error handling
- **Use Case:** Business process automation

**Example:** Lead Qualification Workflow
```yaml
name: lead-qualification
steps:
  - fetch_lead_data:
      api: salesforce
  - score_lead:
      model: claude
      prompt: "Score this lead..."
  - route_lead:
      condition: score > 80
      then: assign_to_sales
      else: add_to_nurture
```

**When to classify as WORKFLOW:**
- Involves external API calls
- Has multiple steps with state
- Contains conditional branching
- Requires error handling/retries

---

### 5. AGENT

**Definition:** A role-based persona with isolated context, specific model choice, and ability to delegate to other agents.

**Characteristics:**
- **Structure:** Agent definition with role, backstory, capabilities
- **Trigger:** Delegated by orchestrator or direct invocation
- **Complexity:** Has memory, personality, delegation abilities
- **Use Case:** Specialized roles, team collaboration

**Example:** Research Agent
```yaml
name: research-agent
role: Research Analyst
backstory: "Expert at finding and synthesizing information..."
model: claude-3-sonnet
tools:
  - web_search
  - document_reader
can_delegate_to:
  - writer-agent
  - fact-checker-agent
```

**When to classify as AGENT:**
- Has a defined role/persona
- Has isolated context/memory
- Can delegate to other agents
- Makes autonomous decisions

---

## Decision Tree for AGENT-002

```
START: Analyze the asset request
         │
         ▼
    ┌─────────────────────┐
    │ Is it multi-step    │
    │ with external APIs? │
    └─────────┬───────────┘
              │
        YES ──┼── NO
              │    │
              ▼    ▼
         WORKFLOW  │
                   │
    ┌──────────────┴──────────────┐
    │ Does it have a role/persona │
    │ and can delegate to others? │
    └──────────────┬──────────────┘
                   │
             YES ──┼── NO
                   │    │
                   ▼    ▼
              AGENT     │
                        │
    ┌───────────────────┴───────────────────┐
    │ Does it contain logic, scripts, or    │
    │ go INTO a platform to perform actions?│
    └───────────────────┬───────────────────┘
                        │
                  YES ──┼── NO
                        │    │
                        ▼    ▼
                   SKILL     │
                             │
    ┌────────────────────────┴────────────────────────┐
    │ STEP 5: Is this a manual macro for repetitive   │
    │ chat, OR a generative blueprint to produce a    │
    │ flawless external structure (Code, SQL, Tables)?│
    └────────────────────────┬────────────────────────┘
                             │
     GENERATIVE BLUEPRINT ───┼─── CHAT MACRO/SHORTCUT
                             │
                             ▼
    ┌────────────────────────┴────────────────────────┐
    │  GENERATIVE BLUEPRINT          SLASH COMMAND         │
    │  → Routes to AGENT-005    → Routes to AGENT-004 │
    └─────────────────────────────────────────────────┘
```

### Tiebreaker Rule #1: Tool/Structure vs Process

**Question:** Does it create a **tool/structure** or does it **perform** a process?

| If it... | Classification |
|----------|----------------|
| Creates instructions to build a flawless 6x6 Airtable base | **GENERATIVE BLUEPRINT** |
| Goes INTO Airtable and updates records | **SKILL** |

---

## Tiebreaker Rules

When an asset could fit multiple categories, use these rules:

| Condition | Classification |
|-----------|----------------|
| Contains a folder/directory | **SKILL** |
| Single file, user-invoked shortcut | **SLASH COMMAND** |
| Creates a flawless external structure (Airtable, SQL, UI) | **GENERATIVE BLUEPRINT** |
| Goes INTO a platform to perform actions/updates | **SKILL** |
| Has role + backstory + delegation | **AGENT** |
| Has external API calls + state machine | **WORKFLOW** |
| Folder + user-invoked | **SKILL** (folder wins) |
| Single file + AI-invoked | Promote to **SKILL** |

### The Key Distinction: Blueprints vs Skills

**AGENT-005 (Prompt Template Generator)** focuses on **Precision Prompting**:
- Ensures the model doesn't hallucinate fields or syntax
- Produces flawless structural output for external platforms

**AGENT-003 (Skill Generator)** focuses on **Action/Tool Use**:
- Running scripts and making API calls
- Going INTO platforms to perform operations

---

## Examples by Department

### Project Management
| Asset | Type | Reason |
|-------|------|--------|
| Project Charter | SKILL | Folder with template + examples + instructions |
| `/status-update` | SLASH COMMAND | Single file, user types command |
| Airtable Project Tracker Builder | GENERATIVE BLUEPRINT | Creates flawless Airtable structure |

### Sales
| Asset | Type | Reason |
|-------|------|--------|
| Lead Qualification | WORKFLOW | External CRM API + state machine |
| Sales Pitch Generator | SKILL | Multiple templates + tone variations |
| `/follow-up` | SLASH COMMAND | Quick email draft action |
| HubSpot Pipeline Schema | GENERATIVE BLUEPRINT | Generates precise CRM structure |

### IT
| Asset | Type | Reason |
|-------|------|--------|
| Incident Response | WORKFLOW | External ticketing + escalation logic |
| Code Review | SKILL | Checklist + examples + patterns |
| `/deploy` | SLASH COMMAND | Trigger deployment action |
| PostgreSQL Schema Generator | GENERATIVE BLUEPRINT | Creates flawless DB schema with RLS |

### Finance
| Asset | Type | Reason |
|-------|------|--------|
| Budget Forecast | SKILL | Templates + formulas + examples |
| QuickBooks Chart of Accounts | GENERATIVE BLUEPRINT | Generates precise accounting structure |
| `/invoice` | SLASH COMMAND | Quick invoice generation |

---

## Implementation Notes for AGENT-002

### Agent Routing

| Asset Type | Generator Agent | Focus |
|------------|-----------------|-------|
| SKILL | AGENT-003 | Action/Tool Use - running scripts, API calls |
| SLASH COMMAND | AGENT-004 | Chat macros and user shortcuts |
| GENERATIVE BLUEPRINT | AGENT-005 | Blueprint Librarian - proven precision instructions |
| WORKFLOW | AGENT-006 | Multi-step orchestration with state |
| AGENT | AGENT-007 | Role-based personas with delegation |

### Classification Logic

1. **Input Processing:**
   - Parse the asset request/description
   - Identify keywords: "build", "create structure", "generate schema" → GENERATIVE BLUEPRINT
   - Identify keywords: "go into", "update", "perform" → SKILL
   - Check for structural indicators (folder, single file, APIs mentioned)

2. **Decision Process:**
   - Follow decision tree in order
   - Apply Tiebreaker Rule #1: Does it CREATE a structure or PERFORM actions?
   - Apply tiebreaker rules when ambiguous
   - Log confidence score for each classification

3. **Output:**
   - Return asset type
   - Return target generator agent (AGENT-003 through AGENT-007)
   - Return recommended structure
   - Return example scaffolding
   - Return confidence score

4. **Feedback Loop:**
   - Track reclassification requests
   - Adjust keyword weights based on corrections
   - Report edge cases for taxonomy updates

---

## Changelog

| Date | Change |
|------|--------|
| 2025-01 | Initial taxonomy created from Ava's research |
| 2025-01 | Removed n8n workflow references |
| 2025-01 | Added decision tree and tiebreaker rules |
| 2025-01 | Refined GENERATIVE BLUEPRINT as "Generative Blueprint" (not fill-in-the-blank) |
| 2025-01 | Added Agent routing table (AGENT-003 through AGENT-007) |
| 2025-01 | Added Tiebreaker Rule #1: Tool/Structure vs Process |

---

## Implementation

AGENT-002 (Asset Classifier) is implemented in:
- **File:** `app/services/asset_classifier_agent.py`
- **Class:** `AssetClassifierAgent`
- **Integration:** Called by AGENT-001 (Orchestrator) in `app/services/orchestrator_agent_service.py`

```python
# Usage
from app.services.asset_classifier_agent import create_asset_classifier

classifier = create_asset_classifier(use_llm=True)
result = await classifier.classify(content, title)

print(result.classification)  # e.g., AssetType.SKILL
print(result.target_agent)    # e.g., "AGENT-003"
print(result.analysis)        # 3-sentence explanation
```

---

## References

- Empire AI Studio Architecture
- Claude Code Skill Documentation
- MCP Tool Specifications
- CrewAI Agent Patterns
- Ava's Asset Classification Research (2025-01)
