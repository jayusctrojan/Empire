#!/usr/bin/env python3
"""
Complete script to parse tasks.md and create all 127 GitHub issues.

Usage:
    python3 parse_and_create_issues.py --dry-run  # Preview without creating
    python3 parse_and_create_issues.py              # Create all issues
    python3 parse_and_create_issues.py --start=20 --end=40  # Create issues 20-40
"""

import subprocess
import json
import time
import argparse
import re
from typing import Dict, List, Optional
from pathlib import Path

# Repository configuration
REPO_OWNER = "jayusctrojan"
REPO_NAME = "Empire"
TASKS_FILE = "../tasks.md"

# Milestone mappings
MILESTONES = {
    "Phase 0": 1,
    "Phase 1": 2,
    "Phase 2": 3,
    "Phase 3": 4,
    "Post-Implementation": 5
}

# Feature mapping
FEATURE_LABELS = {
    "Feature 1": "feature: 1-rnd-dept",
    "Feature 2": "feature: 2-loading-status",
    "Feature 3": "feature: 3-url-upload",
    "Feature 4": "feature: 4-source-attribution",
    "Feature 5": "feature: 5-agent-chat",
    "Feature 6": "feature: 6-course-addition",
    "Feature 7": "feature: 7-chat-upload",
    "Feature 8": "feature: 8-book-processing",
    "Feature 9": "feature: 9-agent-router",
}


def parse_tasks_md(file_path: str) -> List[Dict]:
    """Parse tasks.md and extract all task information."""

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tasks = []
    current_phase = None
    current_milestone = None

    # Split by task headers (#### TASK-XXX:)
    task_pattern = r'####\s+(TASK-[A-Z]+-\d+|TASK-\d+):\s+(.+?)\n'
    task_sections = re.split(task_pattern, content)

    # Process task sections
    for i in range(1, len(task_sections), 3):
        if i + 2 > len(task_sections):
            break

        task_id = task_sections[i]
        task_title = task_sections[i + 1]
        task_body = task_sections[i + 2] if i + 2 < len(task_sections) else ""

        # Extract metadata from the first few lines
        lines = task_body.split('\n')
        metadata_lines = lines[:10]  # First 10 lines usually contain metadata

        # Parse priority, estimate, type, dependencies
        priority = None
        estimate = None
        task_type = None
        dependencies = []
        assignee = None

        for line in metadata_lines:
            if line.startswith('**Priority**:'):
                match = re.search(r'P(\d+)', line)
                if match:
                    priority = f"priority: p{match.group(1).lower()}"
            elif line.startswith('**Estimate**:'):
                estimate = re.search(r':\s+(.+?)\s+\|', line)
                estimate = estimate.group(1) if estimate else line.split(':')[1].strip()
            elif line.startswith('**Type**:'):
                match = re.search(r'Type\*\*:\s+(.+?)(\s+\||$)', line)
                if match:
                    type_name = match.group(1).strip().lower()
                    task_type = f"type: {type_name}"
            elif line.startswith('**Dependencies**:'):
                deps_text = line.split(':', 1)[1].strip()
                if deps_text and deps_text != 'None':
                    dependencies = [d.strip() for d in deps_text.split(',')]
            elif line.startswith('**Assignee**:'):
                assignee = line.split(':', 1)[1].strip()

        # Determine phase and milestone
        phase = None
        milestone = None
        if 'TASK-001' <= task_id <= 'TASK-018':
            phase = "phase: 0-foundation"
            milestone = 1
        elif 'TASK-101' <= task_id <= 'TASK-499':
            phase = "phase: 1-sprint1"
            milestone = 2
        elif 'TASK-301' <= task_id <= 'TASK-899':
            phase = "phase: 2-sprint2"
            milestone = 3
        elif 'TASK-501' <= task_id <= 'TASK-699':
            phase = "phase: 3-sprint3"
            milestone = 4
        elif 'TASK-FINAL' in task_id:
            phase = "phase: 4-post-impl"
            milestone = 5

        # Determine feature label from task ID or body
        feature = None
        if '101' <= task_id[5:8] <= '199':
            feature = "feature: 1-rnd-dept"
        elif '201' <= task_id[5:8] <= '299':
            feature = "feature: 2-loading-status"
        elif '301' <= task_id[5:8] <= '399':
            feature = "feature: 3-url-upload"
        elif '401' <= task_id[5:8] <= '499':
            feature = "feature: 4-source-attribution"
        elif '501' <= task_id[5:8] <= '599':
            feature = "feature: 5-agent-chat"
        elif '601' <= task_id[5:8] <= '699':
            feature = "feature: 6-course-addition"
        elif '701' <= task_id[5:8] <= '799':
            feature = "feature: 7-chat-upload"
        elif '801' <= task_id[5:8] <= '899':
            feature = "feature: 8-book-processing"
        elif '901' <= task_id[5:8] <= '999':
            feature = "feature: 9-agent-router"

        # Build the task dictionary
        task = {
            "id": task_id,
            "title": task_title.strip(),
            "priority": priority or "priority: p1",
            "type": task_type or "type: backend",
            "phase": phase or "phase: 1-sprint1",
            "milestone": milestone or 2,
            "estimate": estimate or "TBD",
            "description": task_body.strip(),
            "dependencies": dependencies,
            "assignee": assignee or "TBD",
            "feature": feature
        }

        tasks.append(task)

    return tasks


def create_issue(task: Dict, dry_run: bool = False) -> Optional[int]:
    """Create a GitHub issue using gh CLI."""

    # Construct issue body with full task description
    body = f"""{task['description']}

---
**Task ID:** {task['id']}
**Priority:** {task['priority'].replace('priority: ', '').upper()}
**Type:** {task['type'].replace('type: ', '').title()}
**Phase:** {task['phase'].replace('phase: ', '').title()}
**Time Estimate:** {task['estimate']}
**Assignee:** {task['assignee']}
**Dependencies:** {', '.join(task['dependencies']) if task['dependencies'] else 'None'}

🤖 Generated with [GitHub Spec Kit](https://github.com/anthropics/spec-kit)
"""

    # Construct labels
    labels = [task['priority'], task['type'], task['phase']]

    # Add feature label if applicable
    if task.get('feature'):
        labels.append(task['feature'])

    labels.append("status: ready")  # Default status

    if dry_run:
        print(f"[DRY RUN] Would create: [{task['id']}] {task['title']}")
        print(f"  Labels: {', '.join(labels)}")
        print(f"  Milestone: {task['milestone']}")
        return None

    # Construct gh API command
    cmd = [
        'gh', 'api',
        f'repos/{REPO_OWNER}/{REPO_NAME}/issues',
        '-X', 'POST',
        '-f', f'title=[{task["id"]}] {task["title"]}',
        '-f', f'body={body}',
        '-f', f'milestone={task["milestone"]}'
    ]

    # Add labels
    for label in labels:
        cmd.extend(['-f', f'labels[]={label}'])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issue_data = json.loads(result.stdout)
        issue_number = issue_data['number']
        print(f"✅ Created #{issue_number}: [{task['id']}] {task['title']}")
        return issue_number
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {task['id']}")
        print(f"   Error: {e.stderr}")
        return None


def create_all_issues(
    tasks: List[Dict],
    dry_run: bool = False,
    start_idx: int = 0,
    end_idx: Optional[int] = None,
    batch_size: int = 10
):
    """Create GitHub issues in batches."""

    if end_idx is None:
        end_idx = len(tasks)

    tasks_to_create = tasks[start_idx:end_idx]
    total = len(tasks_to_create)

    print(f"\n{'='*70}")
    print(f"Creating {total} GitHub Issues for Empire v7.3")
    print(f"Range: {start_idx + 1} to {end_idx} (of {len(tasks)} total)")
    print(f"{'='*70}\n")

    if dry_run:
        print("⚠️  DRY RUN MODE - No issues will be created\n")

    created_issues = {}
    failed_tasks = []

    for i, task in enumerate(tasks_to_create, start=1):
        global_idx = start_idx + i
        print(f"\n[{i}/{total}] (Global: {global_idx}/{len(tasks)}) Processing {task['id']}...")

        issue_number = create_issue(task, dry_run=dry_run)

        if issue_number:
            created_issues[task['id']] = issue_number
        elif not dry_run:
            failed_tasks.append(task['id'])

        # Rate limiting: sleep between batches
        if i % batch_size == 0 and not dry_run and i < total:
            print(f"\n⏸️  Pausing for rate limit (processed {i}/{total})...")
            time.sleep(5)

    # Print summary
    print(f"\n{'='*70}")
    print(f"Summary")
    print(f"{'='*70}")

    if dry_run:
        print(f"📋 Would create: {total} issues")
    else:
        print(f"✅ Successfully created: {len(created_issues)} issues")
        print(f"❌ Failed: {len(failed_tasks)} issues")

        if failed_tasks:
            print(f"\nFailed tasks: {', '.join(failed_tasks)}")

    print(f"\n🎉 GitHub Issues {'preview' if dry_run else 'creation'} complete!")

    return created_issues, failed_tasks


def main():
    parser = argparse.ArgumentParser(
        description="Parse tasks.md and create GitHub issues for Empire v7.3"
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
    parser.add_argument(
        '--start',
        type=int,
        default=0,
        help='Start index (0-based, default: 0)'
    )
    parser.add_argument(
        '--end',
        type=int,
        default=None,
        help='End index (exclusive, default: all)'
    )
    parser.add_argument(
        '--tasks-file',
        type=str,
        default=TASKS_FILE,
        help=f'Path to tasks.md (default: {TASKS_FILE})'
    )

    args = parser.parse_args()

    # Get script directory and construct absolute path
    script_dir = Path(__file__).parent
    tasks_file_path = script_dir / args.tasks_file

    if not tasks_file_path.exists():
        print(f"❌ Error: tasks.md not found at {tasks_file_path}")
        print(f"   Please check the path and try again.")
        return 1

    print(f"📖 Parsing {tasks_file_path}...")
    tasks = parse_tasks_md(str(tasks_file_path))

    print(f"✅ Parsed {len(tasks)} tasks successfully\n")

    if len(tasks) == 0:
        print("❌ No tasks found in tasks.md")
        return 1

    # Show task distribution
    phase_counts = {}
    for task in tasks:
        phase = task['phase']
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    print("Task Distribution:")
    for phase, count in sorted(phase_counts.items()):
        print(f"  {phase}: {count} tasks")
    print()

    create_all_issues(
        tasks,
        dry_run=args.dry_run,
        start_idx=args.start,
        end_idx=args.end,
        batch_size=args.batch_size
    )

    return 0


if __name__ == '__main__':
    exit(main())
