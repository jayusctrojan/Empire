#!/usr/bin/env python3
"""
Script to create 127 GitHub issues for Empire v7.3 features.
Reads from tasks.md and creates issues with proper labels, milestones, and descriptions.

Usage:
    python3 create_github_issues.py --dry-run  # Preview without creating
    python3 create_github_issues.py             # Create all issues
"""

import subprocess
import json
import time
import argparse
from typing import Dict, List, Optional

# Repository configuration
REPO_OWNER = "jayusctrojan"
REPO_NAME = "Empire"

# Milestone mappings
MILESTONES = {
    "Phase 0 - Foundation": 1,
    "Phase 1 - Sprint 1 (P1 Features)": 2,
    "Phase 2 - Sprint 2 (P2 Features)": 3,
    "Phase 3 - Sprint 3 (P3 Features)": 4,
    "Production Deployment": 5
}

# Task definitions (from tasks.md)
TASKS = [
    # Phase 0: Foundation (18 tasks)
    {
        "id": "TASK-001",
        "title": "Create API Contracts (OpenAPI Specs)",
        "priority": "priority: p0",
        "type": "type: backend",
        "phase": "phase: 0-foundation",
        "milestone": 1,
        "estimate": "1 day",
        "description": """Create OpenAPI 3.0 specification files for all 9 features defining request/response schemas, error codes, and examples.

**Acceptance Criteria:**
- [ ] 9 YAML files created in `specs/2-empire-v73-features/contracts/`
- [ ] All endpoints documented with request/response schemas
- [ ] Error responses (400, 401, 404, 413, 429, 500) defined
- [ ] Example requests and responses included
- [ ] Validated with OpenAPI validator (no errors)

**Files to Create:**
- `specs/2-empire-v73-features/contracts/feature-1-rnd-dept.yaml`
- `specs/2-empire-v73-features/contracts/feature-2-loading-status.yaml`
- `specs/2-empire-v73-features/contracts/feature-3-url-upload.yaml`
- `specs/2-empire-v73-features/contracts/feature-4-source-attribution.yaml`
- `specs/2-empire-v73-features/contracts/feature-5-agent-chat.yaml`
- `specs/2-empire-v73-features/contracts/feature-6-course-addition.yaml`
- `specs/2-empire-v73-features/contracts/feature-7-chat-upload.yaml`
- `specs/2-empire-v73-features/contracts/feature-8-book-processing.yaml`
- `specs/2-empire-v73-features/contracts/feature-9-agent-router.yaml`

**Dependencies:** None

🤖 Generated with [GitHub Spec Kit](https://github.com/anthropics/spec-kit)
""",
        "dependencies": []
    },
    {
        "id": "TASK-002",
        "title": "Create Database Migrations",
        "priority": "priority: p0",
        "type": "type: database",
        "phase": "phase: 0-foundation",
        "milestone": 1,
        "estimate": "2 days",
        "description": """Create SQL migration files for all database schema changes across 9 features.

**Acceptance Criteria:**
- [ ] 15 migration files created in `migrations/`
- [ ] All migrations tested on local Supabase instance
- [ ] Rollback scripts included for each migration
- [ ] Migration order documented in README
- [ ] No data loss on migration (verified with test data)

**Migrations to Create:**
1. `001_add_rnd_department.sql` - Add R&D to department enum
2. `002_add_processing_status_column.sql` - Add processing_status JSONB
3. `003_add_source_metadata_column.sql` - Add source_metadata JSONB
4. `004_create_agent_router_cache_table.sql` - Agent routing cache
5. `005_create_agent_feedback_table.sql` - Agent feedback storage
6. Additional migrations for remaining features

**Dependencies:** TASK-001

🤖 Generated with [GitHub Spec Kit](https://github.com/anthropics/spec-kit)
""",
        "dependencies": ["TASK-001"]
    },
    # Add more tasks here - this is just a sample
    # For the full implementation, we would parse tasks.md or define all 127 tasks
]

# Simplified task list for demonstration - in production, parse from tasks.md
def get_all_tasks() -> List[Dict]:
    """
    Get all 127 tasks from tasks.md.

    For this prototype, we return a subset. In production, this would parse
    specs/2-empire-v73-features/tasks.md and extract all task definitions.
    """
    # TODO: Parse tasks.md file and extract all 127 tasks
    # For now, return the TASKS list above
    return TASKS

def create_issue(task: Dict, dry_run: bool = False) -> Optional[int]:
    """Create a GitHub issue using gh CLI."""

    # Construct issue body
    body = f"""{task['description']}

---
**Task ID:** {task['id']}
**Priority:** {task['priority'].replace('priority: ', '').upper()}
**Type:** {task['type'].replace('type: ', '').title()}
**Time Estimate:** {task['estimate']}
**Dependencies:** {', '.join(task['dependencies']) if task['dependencies'] else 'None'}
"""

    # Construct labels
    labels = [task['priority'], task['type'], task['phase']]

    # Add feature labels if applicable
    if 'feature' in task:
        labels.append(task['feature'])

    labels.append("status: ready")  # Default status

    labels_str = ','.join(labels)

    # Construct gh CLI command
    cmd = [
        'gh', 'api',
        f'repos/{REPO_OWNER}/{REPO_NAME}/issues',
        '-X', 'POST',
        '-f', f'title=[{task["id"]}] {task["title"]}',
        '-f', f'body={body}',
        '-f', f'milestone={task["milestone"]}',
        '-f', f'labels[]={labels[0]}'
    ]

    # Add remaining labels
    for label in labels[1:]:
        cmd.extend(['-f', f'labels[]={label}'])

    if dry_run:
        print(f"[DRY RUN] Would create issue: [{task['id']}] {task['title']}")
        print(f"  Labels: {labels_str}")
        print(f"  Milestone: {task['milestone']}")
        return None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issue_data = json.loads(result.stdout)
        issue_number = issue_data['number']
        print(f"✅ Created issue #{issue_number}: [{task['id']}] {task['title']}")
        return issue_number
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create issue: {task['id']}")
        print(f"   Error: {e.stderr}")
        return None

def create_all_issues(dry_run: bool = False, batch_size: int = 10):
    """Create all GitHub issues in batches."""
    tasks = get_all_tasks()
    total_tasks = len(tasks)

    print(f"\n{'='*60}")
    print(f"Creating {total_tasks} GitHub Issues for Empire v7.3")
    print(f"{'='*60}\n")

    if dry_run:
        print("⚠️  DRY RUN MODE - No issues will be created\n")

    created_issues = {}
    failed_tasks = []

    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{total_tasks}] Processing {task['id']}...")

        issue_number = create_issue(task, dry_run=dry_run)

        if issue_number:
            created_issues[task['id']] = issue_number
        else:
            failed_tasks.append(task['id'])

        # Rate limiting: sleep between batches
        if i % batch_size == 0 and not dry_run:
            print(f"\n⏸️  Pausing for rate limit (processed {i}/{total_tasks})...")
            time.sleep(5)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    print(f"✅ Successfully created: {len(created_issues)} issues")
    print(f"❌ Failed: {len(failed_tasks)} issues")

    if failed_tasks:
        print(f"\nFailed tasks: {', '.join(failed_tasks)}")

    print(f"\n🎉 GitHub Issues creation {'preview' if dry_run else 'complete'}!")

    return created_issues, failed_tasks

def main():
    parser = argparse.ArgumentParser(
        description="Create 127 GitHub issues for Empire v7.3 features"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview issues without creating them'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of issues to create before pausing (default: 10)'
    )

    args = parser.parse_args()

    create_all_issues(dry_run=args.dry_run, batch_size=args.batch_size)

if __name__ == '__main__':
    main()
