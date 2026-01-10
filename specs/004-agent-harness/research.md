# Research: Design Decisions for Research Projects

**Feature**: Research Projects (Agent Harness)
**Date**: 2025-01-10
**Status**: Complete

## Overview

This document captures the research and design decisions made for the Agent Harness implementation, including alternatives considered and rationale for final choices.

---

## 1. Task Orchestration Pattern

### Decision: Two-Stage Agent Harness (Initializer + Task Harness)

### Rationale
The Agent Harness pattern from AI Automators provides clear separation between planning and execution:
- **Initializer**: One-time Claude call to analyze query and create task plan
- **Task Harness**: Iterative execution of planned tasks with state management

### Alternatives Considered

| Alternative | Pros | Cons | Rejected Because |
|-------------|------|------|------------------|
| Single monolithic agent | Simpler implementation | No visibility, hard to debug, can't recover | No progress tracking, all-or-nothing execution |
| LangGraph state machine | Flexible routing | Complexity, learning curve | Overkill for linear task flow with dependencies |
| CrewAI multi-agent | Rich agent collaboration | More Claude calls, higher cost | Higher latency, less control over execution order |

### Implementation Notes
- Initializer uses Claude Sonnet 4 with JSON schema for structured task plan output
- Task Harness maintains state in PostgreSQL, enabling recovery from failures
- Clear phase transitions: `initializing → planning → planned → executing → synthesizing → complete`

---

## 2. Concurrent Execution Strategy

### Decision: Wave-based Parallelism with Celery Groups

### Rationale
Wave-based execution with Celery groups maximizes parallelism while respecting task dependencies:
- Tasks are sorted into waves using topological sort (Kahn's algorithm)
- Each wave contains tasks with no unresolved dependencies
- Waves execute in sequence, tasks within waves execute in parallel

### Performance Targets
- Simple queries (3-5 tasks): <2 minutes
- Medium queries (6-10 tasks): <5 minutes
- Complex queries (11-20 tasks): <15 minutes
- Parallelism ratio: >60% (concurrent tasks / total tasks)
- Wave transition latency: <100ms

### Alternatives Considered

| Alternative | Pros | Cons | Rejected Because |
|-------------|------|------|------------------|
| Pure sequential execution | Simple, predictable | Slow, no parallelism | Won't meet performance SLAs |
| Event-driven (each task triggers dependents) | Maximum parallelism | Complex state management, race conditions | Harder to implement quality gates |
| Custom task scheduler | Full control | Significant development effort | Celery groups provide this out of box |

### Implementation Notes
- Use `celery.group()` for parallel dispatch within waves
- Quality gates checked between waves before proceeding
- Prometheus metrics track parallelism ratio and wave timing

---

## 3. Task Types and Executors

### Decision: Six Core Task Types with Specialized Executors

### Task Type Registry

| Type | Purpose | Executor | Dependencies |
|------|---------|----------|--------------|
| `retrieval_rag` | Vector similarity search | RetrievalExecutor | None (first wave) |
| `retrieval_nlq` | Natural language DB query | RetrievalExecutor | None (first wave) |
| `retrieval_graph` | Knowledge graph traversal | RetrievalExecutor | None (first wave) |
| `synthesis` | Combine findings | SynthesisExecutor | Retrieval tasks |
| `write_report` | Generate final report | ReportExecutor | Synthesis tasks |
| `review` | Quality assurance | ReportExecutor | Write tasks |

### Rationale
- Specialized executors allow optimized handling per task type
- Clear dependency chain: Retrieval → Synthesis → Report
- Each executor can be tested and optimized independently

### Implementation Notes
- Executors are dependency-injected into TaskHarnessService
- Each executor returns standardized result format with artifacts
- Artifacts stored in `research_artifacts` table with source tracking

---

## 4. Quality Gates

### Decision: Per-Phase Quality Validation

### Quality Thresholds by Task Type

| Task Type | Minimum Score | Action on Failure |
|-----------|---------------|-------------------|
| `retrieval_rag` | 0.7 | Retry with expanded query |
| `retrieval_nlq` | 0.7 | Retry with alternate phrasing |
| `retrieval_graph` | 0.6 | Log warning, continue |
| `synthesis` | 0.8 | Retry with more context |
| `write_report` | 0.85 | Revision loop (max 2) |

### Rationale
- Quality gates ensure fast execution doesn't compromise output quality
- Different thresholds reflect task criticality (reports must be high quality)
- Retry logic attempts recovery before failing

### Alternatives Considered

| Alternative | Pros | Cons | Rejected Because |
|-------------|------|------|------------------|
| No quality gates | Faster execution | Inconsistent quality | Users expect reliable reports |
| Post-hoc validation only | Simpler | Wasted compute on bad paths | Better to catch early |
| User-configurable thresholds | Flexible | Complexity | Most users want defaults |

---

## 5. Data Retention and Sharing

### Decision: Indefinite Retention with Public Links + Revocation

### Rationale
Based on clarification session:
- **Retention**: Indefinite until user deletes (FR-016)
- **Sharing**: Public shareable links (FR-005) with revocation capability (FR-005a)
- **Concurrent Limit**: 3 active projects per user (FR-018)

### Implementation Notes
- `research_jobs` table has no automatic cleanup (user-initiated delete only)
- `shared_reports` table manages public links with `revoked_at` timestamp
- Queue system for projects beyond 3 concurrent limit

---

## 6. Real-time Progress Updates

### Decision: WebSocket with Redis Pub/Sub

### Rationale
- Empire already has WebSocket infrastructure
- Redis pub/sub provides reliable message delivery
- Client can reconnect and get current state

### Message Types

| Type | When Sent | Payload |
|------|-----------|---------|
| `project_created` | After initialization | `{job_id, status, total_tasks}` |
| `task_started` | Task begins | `{job_id, task_key, task_type}` |
| `task_completed` | Task finishes | `{job_id, task_key, result_summary}` |
| `task_failed` | Task fails | `{job_id, task_key, error}` |
| `project_complete` | All done | `{job_id, report_url}` |

---

## 7. Report Generation

### Decision: Markdown Primary with PDF Export

### Rationale
- Markdown is the native format for Claude output
- PDF conversion via existing pandoc/weasyprint tooling
- B2 storage for report files (existing CrewAI pattern)

### Report Structure
1. Executive Summary
2. Key Findings (bullet points)
3. Detailed Analysis (with citations)
4. Methodology Notes
5. Source Citations

---

## 8. Error Handling and Recovery

### Decision: Graceful Degradation with Partial Results

### Error Handling Strategy

| Scenario | Action | User Impact |
|----------|--------|-------------|
| Single task fails | Retry 2x, then continue | Note gap in report |
| Multiple tasks fail | Continue with available data | Reduced report scope |
| Critical failure | Mark project failed | Email notification |
| Network timeout | Auto-retry with backoff | Transparent recovery |

### Rationale
- Users prefer partial results over complete failure
- Clear communication about gaps in final report
- Recovery mechanisms minimize lost work

---

## Summary

All design decisions optimize for:
1. **Performance**: Wave-based parallelism meets SLA targets
2. **Quality**: Gates ensure output reliability
3. **Resilience**: Graceful degradation preserves user value
4. **Transparency**: Real-time updates build trust

**Status**: Ready for implementation via `/speckit.tasks`
