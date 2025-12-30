# GitHub Issues Creation Guide: Empire v7.3

**Source**: [tasks.md](./tasks.md) (127 tasks)
**Date**: 2025-11-24
**Purpose**: Convert task breakdown into GitHub issues with proper labels, milestones, and dependencies

---

## Overview

This guide provides the structure for creating 127 GitHub issues from the task breakdown, organized by phases and features.

**Issue Naming Convention**:
```
[TASK-XXX] Short Description (Feature N)
```

**Example**:
```
[TASK-301] Create YouTube Service (Feature 3: URL Upload)
```

---

## GitHub Labels to Create

### Priority Labels
- `priority: p0` - Foundation/critical (red)
- `priority: p1` - Sprint 1 features (orange)
- `priority: p2` - Sprint 2 features (yellow)
- `priority: p3` - Sprint 3 features (blue)

### Type Labels
- `type: backend` - Backend development
- `type: database` - Database migrations/schemas
- `type: frontend` - Frontend/Gradio UI
- `type: testing` - Unit/integration/E2E tests
- `type: devops` - DevOps/monitoring/deployment
- `type: documentation` - Documentation tasks
- `type: management` - Planning/retrospectives

### Feature Labels
- `feature: 1-rnd-dept` - R&D Department Addition
- `feature: 2-loading-status` - Loading Process Status UI
- `feature: 3-url-upload` - URL/Link Support on Upload
- `feature: 4-source-attribution` - Source Attribution in Chat UI
- `feature: 5-agent-chat` - Agent Chat & Improvement
- `feature: 6-course-addition` - Course Content Addition
- `feature: 7-chat-upload` - Chat File/Image Upload
- `feature: 8-book-processing` - Book Processing
- `feature: 9-agent-router` - Intelligent Agent Router

### Phase Labels
- `phase: 0-foundation` - Phase 0 (Foundation)
- `phase: 1-sprint1` - Phase 1 (Sprint 1 - P1 features)
- `phase: 2-sprint2` - Phase 2 (Sprint 2 - P2 features)
- `phase: 3-sprint3` - Phase 3 (Sprint 3 - P3 features)
- `phase: 4-post-impl` - Post-Implementation

### Status Labels (GitHub defaults + custom)
- `status: blocked` - Waiting on dependencies
- `status: in-progress` - Currently being worked on
- `status: needs-review` - Ready for code review
- `status: ready-for-testing` - Ready for QA
- `status: needs-feedback` - Awaiting stakeholder feedback

---

## GitHub Milestones to Create

### Milestone 1: Phase 0 - Foundation
**Due Date**: Day 5 (from project start)
**Description**: Infrastructure setup, migrations, contracts, monitoring
**Issues**: 18 (TASK-001 through TASK-018)

### Milestone 2: Phase 1 - Sprint 1 (P1 Features)
**Due Date**: Day 15 (from project start)
**Description**: Features 1, 2, 4, 9 (R&D Dept, Loading Status, Source Attribution, Agent Router)
**Issues**: 36 (TASK-101 through TASK-905 + related)

### Milestone 3: Phase 2 - Sprint 2 (P2 Features)
**Due Date**: Day 25 (from project start)
**Description**: Features 3, 7, 8 (URL Upload, Chat File Upload, Book Processing)
**Issues**: 46 (TASK-301 through TASK-807 + related)

### Milestone 4: Phase 3 - Sprint 3 (P3 Features)
**Due Date**: Day 30 (from project start)
**Description**: Features 5, 6 (Agent Chat, Course Addition)
**Issues**: 27 (TASK-501 through TASK-605 + related)

### Milestone 5: Production Deployment
**Due Date**: Day 38 (from project start)
**Description**: Testing, security audit, deployment, monitoring
**Issues**: 8 (TASK-FINAL-01 through TASK-FINAL-08)

---

## Issue Template Structure

Use this template for each issue:

```markdown
## Description

[Brief description from tasks.md]

## Task ID

TASK-XXX

## Priority

[P0/P1/P2/P3]

## Type

[Backend/Database/Frontend/Testing/DevOps/Documentation/Management]

## Time Estimate

[Hours or Days]

## Dependencies

- [ ] TASK-YYY: [Dependency description]
- [ ] TASK-ZZZ: [Dependency description]

## Acceptance Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]
...

## Files to Create/Modify

**Files to Create:**
- `path/to/new/file.py`
- `path/to/another/file.sql`

**Files to Modify:**
- `path/to/existing/file.py`
- `path/to/another/existing.js`

## Implementation Notes

[Any code examples or specific implementation guidance from tasks.md]

## Testing Notes

[Specific test cases or validation requirements]

## Related Issues

- Blocks: #XXX, #YYY
- Blocked by: #ZZZ
- Related to: #AAA

## Assignee

[Backend Lead / Frontend Developer / QA Engineer / etc.]

## Labels

- `priority: pN`
- `type: backend`
- `feature: N-feature-name`
- `phase: N-sprintN`

## Milestone

[Phase N - Description]
```

---

## Bulk Issue Creation Script

Use GitHub CLI to create issues in bulk:

```bash
#!/bin/bash
# create_v73_issues.sh

# Phase 0: Foundation (18 issues)
gh issue create \
  --title "[TASK-001] Create API Contracts (OpenAPI Specs)" \
  --body-file ".github/issue-templates/TASK-001.md" \
  --label "priority: p0,type: backend,phase: 0-foundation" \
  --milestone "Phase 0 - Foundation"

gh issue create \
  --title "[TASK-002] Write Database Migration Scripts" \
  --body-file ".github/issue-templates/TASK-002.md" \
  --label "priority: p0,type: database,phase: 0-foundation" \
  --milestone "Phase 0 - Foundation"

# ... repeat for all 127 tasks
```

---

## Phase 0: Foundation Issues (18 issues)

### Infrastructure & Setup

#### Issue 1: [TASK-001] Create API Contracts (OpenAPI Specs)
**Labels**: `priority: p0`, `type: backend`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 1 day
**Assignee**: Backend Lead
**Dependencies**: None

#### Issue 2: [TASK-002] Write Database Migration Scripts
**Labels**: `priority: p0`, `type: database`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 1 day
**Assignee**: Database Lead
**Dependencies**: TASK-001

#### Issue 3: [TASK-003] Configure Feature Flags
**Labels**: `priority: p0`, `type: backend`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 2 hours
**Assignee**: Backend Lead
**Dependencies**: None

#### Issue 4: [TASK-004] Update Prometheus Alert Rules
**Labels**: `priority: p0`, `type: devops`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 3 hours
**Assignee**: DevOps Lead
**Dependencies**: TASK-001

#### Issue 5: [TASK-005] Create Grafana Dashboards
**Labels**: `priority: p0`, `type: devops`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 4 hours
**Assignee**: DevOps Lead
**Dependencies**: TASK-004

#### Issue 6: [TASK-006] Set Up Test Structure
**Labels**: `priority: p0`, `type: testing`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 3 hours
**Assignee**: QA Lead
**Dependencies**: TASK-001

#### Issue 7: [TASK-007] Install New Dependencies
**Labels**: `priority: p0`, `type: backend`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 1 hour
**Assignee**: Backend Lead
**Dependencies**: None

#### Issue 8: [TASK-008] Create Data Model Documentation
**Labels**: `priority: p0`, `type: documentation`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 4 hours
**Assignee**: Technical Writer
**Dependencies**: TASK-002

#### Issue 9: [TASK-009] Create API Documentation
**Labels**: `priority: p0`, `type: documentation`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 4 hours
**Assignee**: Technical Writer
**Dependencies**: TASK-001

#### Issue 10: [TASK-010] Create Implementation Guides
**Labels**: `priority: p0`, `type: documentation`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 4 hours
**Assignee**: Technical Writer
**Dependencies**: None

#### Issue 11: [TASK-011] Run Database Migrations on Staging
**Labels**: `priority: p0`, `type: database`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 2 hours
**Assignee**: Database Lead
**Dependencies**: TASK-002

#### Issue 12: [TASK-012] Update Environment Variables
**Labels**: `priority: p0`, `type: devops`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 1 hour
**Assignee**: DevOps Lead
**Dependencies**: TASK-003

#### Issue 13: [TASK-013] Create Integration Test Data
**Labels**: `priority: p0`, `type: testing`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 3 hours
**Assignee**: QA Lead
**Dependencies**: TASK-006

#### Issue 14: [TASK-014] Set Up CI/CD Pipeline
**Labels**: `priority: p0`, `type: devops`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 4 hours
**Assignee**: DevOps Lead
**Dependencies**: TASK-006

#### Issue 15: [TASK-015] Create Rollback Plan
**Labels**: `priority: p0`, `type: devops`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 2 hours
**Assignee**: DevOps Lead
**Dependencies**: None

#### Issue 16: [TASK-016] Performance Baseline Measurement
**Labels**: `priority: p0`, `type: testing`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 3 hours
**Assignee**: QA Lead
**Dependencies**: None

#### Issue 17: [TASK-017] Security Audit Preparation
**Labels**: `priority: p0`, `type: devops`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 2 hours
**Assignee**: Security Lead
**Dependencies**: TASK-001

#### Issue 18: [TASK-018] Stakeholder Review & Sign-off
**Labels**: `priority: p0`, `type: management`, `phase: 0-foundation`
**Milestone**: Phase 0 - Foundation
**Estimate**: 2 days
**Assignee**: Project Manager
**Dependencies**: TASK-001 through TASK-017

---

## Phase 1: Sprint 1 Issues (36 issues)

### Feature 1: R&D Department Addition (6 issues)

#### Issue 101: [TASK-101] Run R&D Department Migration (Feature 1)
**Labels**: `priority: p1`, `type: database`, `feature: 1-rnd-dept`, `phase: 1-sprint1`
**Milestone**: Phase 1 - Sprint 1 (P1 Features)
**Estimate**: 1 hour
**Assignee**: Database Lead
**Dependencies**: TASK-011

[Continue for all 127 tasks...]

---

## Issue Dependency Mapping

Create issue dependencies using GitHub's "Blocks" and "Blocked by" relationships:

```
TASK-001 (API Contracts)
  └─> TASK-002 (Database Migrations)
      └─> TASK-011 (Run Migrations on Staging)
          └─> TASK-101 (Run R&D Migration)
              └─> TASK-102 (Update Constants)
                  └─> TASK-103 (Update Department Service)
                      └─> TASK-104 (Update B2 Storage)
                      └─> TASK-105 (Update Neo4j Nodes)
                          └─> TASK-106 (Test R&D Classification)
```

---

## Automation Script: Create All 127 Issues

Save this as `.github/scripts/create_v73_issues.sh`:

```bash
#!/bin/bash
set -e

echo "Creating 127 GitHub issues for Empire v7.3..."

# Load issue templates directory
TEMPLATE_DIR=".github/issue-templates"

# Function to create issue with dependencies
create_issue() {
  local task_id=$1
  local title=$2
  local labels=$3
  local milestone=$4
  local assignee=$5
  local body_file="${TEMPLATE_DIR}/${task_id}.md"

  if [ ! -f "$body_file" ]; then
    echo "Warning: Template not found for $task_id"
    return
  fi

  gh issue create \
    --title "[$task_id] $title" \
    --body-file "$body_file" \
    --label "$labels" \
    --milestone "$milestone" \
    --assignee "$assignee" || echo "Failed to create issue $task_id"

  echo "Created issue: [$task_id] $title"
}

# Phase 0: Foundation
echo "Creating Phase 0 issues..."
create_issue "TASK-001" "Create API Contracts (OpenAPI Specs)" "priority: p0,type: backend,phase: 0-foundation" "Phase 0 - Foundation" "backend-lead"
create_issue "TASK-002" "Write Database Migration Scripts" "priority: p0,type: database,phase: 0-foundation" "Phase 0 - Foundation" "database-lead"
# ... continue for all Phase 0 tasks

# Phase 1: Sprint 1
echo "Creating Phase 1 issues..."
create_issue "TASK-101" "Run R&D Department Migration (Feature 1)" "priority: p1,type: database,feature: 1-rnd-dept,phase: 1-sprint1" "Phase 1 - Sprint 1" "database-lead"
# ... continue for all Phase 1 tasks

# Phase 2: Sprint 2
echo "Creating Phase 2 issues..."
create_issue "TASK-301" "Create YouTube Service (Feature 3)" "priority: p2,type: backend,feature: 3-url-upload,phase: 2-sprint2" "Phase 2 - Sprint 2" "backend-dev"
# ... continue for all Phase 2 tasks

# Phase 3: Sprint 3
echo "Creating Phase 3 issues..."
create_issue "TASK-501" "Run Agent Feedback Migration (Feature 5)" "priority: p3,type: database,feature: 5-agent-chat,phase: 3-sprint3" "Phase 3 - Sprint 3" "database-lead"
# ... continue for all Phase 3 tasks

# Post-Implementation
echo "Creating Post-Implementation issues..."
create_issue "TASK-FINAL-01" "Performance Testing" "priority: p0,type: testing,phase: 4-post-impl" "Production Deployment" "qa-lead"
# ... continue for all final tasks

echo "Successfully created all 127 issues!"
echo "Next: Review issues, assign to team members, and update dependencies"
```

Make executable:
```bash
chmod +x .github/scripts/create_v73_issues.sh
```

Run:
```bash
cd /path/to/Empire
./.github/scripts/create_v73_issues.sh
```

---

## Issue Template Files

Create 127 markdown files in `.github/issue-templates/`:

### Example: TASK-001.md
```markdown
## Description

Create OpenAPI 3.0 specification files for all 9 features defining request/response schemas, error codes, and examples.

## Task ID

TASK-001

## Priority

P0 - Foundation

## Type

Backend

## Time Estimate

1 day

## Dependencies

None - This is a foundational task

## Acceptance Criteria

- [ ] 9 YAML files created in `specs/2-empire-v73-features/contracts/`
- [ ] All endpoints documented with request/response schemas
- [ ] Error responses (400, 401, 404, 413, 429, 500) defined
- [ ] Example requests and responses included
- [ ] Validated with OpenAPI validator (no errors)

## Files to Create

**Contract Files:**
- `specs/2-empire-v73-features/contracts/feature-1-rnd-dept.yaml`
- `specs/2-empire-v73-features/contracts/feature-2-loading-status.yaml`
- `specs/2-empire-v73-features/contracts/feature-3-url-upload.yaml`
- `specs/2-empire-v73-features/contracts/feature-4-source-attribution.yaml`
- `specs/2-empire-v73-features/contracts/feature-5-agent-chat.yaml`
- `specs/2-empire-v73-features/contracts/feature-6-course-addition.yaml`
- `specs/2-empire-v73-features/contracts/feature-7-chat-upload.yaml`
- `specs/2-empire-v73-features/contracts/feature-8-book-processing.yaml`
- `specs/2-empire-v73-features/contracts/feature-9-agent-router.yaml`

## Implementation Notes

Use OpenAPI 3.0 specification format. Include:
- Path parameters
- Query parameters
- Request body schemas (Pydantic models)
- Response schemas (success + errors)
- Authentication requirements
- Rate limits

Example structure:
```yaml
openapi: 3.0.0
info:
  title: Feature 1 - R&D Department
  version: 1.0.0
paths:
  /api/v1/documents/upload:
    post:
      summary: Upload document with R&D department support
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                department:
                  type: string
                  enum: [it_engineering, sales_marketing, r_and_d, ...]
      responses:
        '200':
          description: Successful upload
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentUploadResponse'
        '400':
          description: Invalid request
```

## Testing Notes

Validate all contract files using:
```bash
npx @stoplight/spectral-cli lint specs/2-empire-v73-features/contracts/*.yaml
```

## Related Issues

- Blocks: #2 (TASK-002 - Database Migrations)
- Blocks: #4 (TASK-004 - Prometheus Alerts)
- Blocks: #9 (TASK-009 - API Documentation)

## Assignee

Backend Lead

## Reference

See technical plan: `specs/2-empire-v73-features/technical-plan.md`
See task breakdown: `specs/2-empire-v73-features/tasks.md#task-001`
```

---

## Quick Start: Create First 10 Issues Manually

To get started quickly, create the first 10 Phase 0 issues manually:

1. Go to GitHub repository: https://github.com/[your-username]/Empire/issues
2. Click "New Issue"
3. Use template above for each task
4. Add appropriate labels and milestone
5. Link dependencies using "Blocks" and "Blocked by" in issue description

---

## Project Board Setup

Create a GitHub Project Board with columns:

1. **Backlog** - All tasks not yet started
2. **Ready** - Tasks with dependencies completed
3. **In Progress** - Currently being worked on
4. **In Review** - Code review in progress
5. **QA Testing** - Ready for QA
6. **Done** - Completed tasks

Add all 127 issues to the project board in "Backlog" column.

---

## Next Steps

1. **Create Labels** (30 labels)
   ```bash
   gh label create "priority: p0" --color "d73a4a" --description "Foundation/critical"
   gh label create "priority: p1" --color "ff9800" --description "Sprint 1 features"
   # ... create all 30 labels
   ```

2. **Create Milestones** (5 milestones)
   ```bash
   gh milestone create --title "Phase 0 - Foundation" --due-date "2025-12-05" --description "Infrastructure setup, migrations, contracts"
   # ... create all 5 milestones
   ```

3. **Generate Issue Templates** (127 markdown files)
   - Use tasks.md as source
   - Extract task details into issue template format
   - Save to `.github/issue-templates/TASK-XXX.md`

4. **Run Bulk Creation Script**
   ```bash
   ./.github/scripts/create_v73_issues.sh
   ```

5. **Review and Assign**
   - Review all created issues
   - Assign to team members
   - Update dependencies (add "Blocks" relationships)
   - Move to appropriate project board columns

6. **Start Sprint Planning**
   - Select Phase 0 tasks for first sprint
   - Assign to team members based on capacity
   - Set sprint start/end dates
   - Begin implementation!

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Status**: Ready for GitHub Issue Creation
**Next Action**: Create labels, milestones, and run bulk creation script
