# DO NOT MERGE TO MAIN WITHOUT ASKING JAY FIRST!

**CRITICAL: All PRs must go through CodeRabbit review. NEVER merge PRs to main or push directly to main without explicit approval from Jay. When asking for permission, always say "Can I merge PR #X to main?"**

---

# Empire Project

## Overview

Empire is a multi-agent AI orchestration platform with:
- FastAPI backend with Supabase PostgreSQL
- TypeScript/React desktop application
- Real-time WebSocket communication
- Agent workflow execution and lineage tracking

## Development Guidelines

- All database migrations go in `migrations/` directory
- Use idempotent SQL with `IF NOT EXISTS` / `CREATE OR REPLACE`
- Run CI/CD checks before merging
- Follow CodeRabbit review feedback

## Key Directories

- `app/` - FastAPI application code
- `app/services/` - Business logic services
- `app/api/` - API route handlers
- `migrations/` - SQL migration files
- `desktop/` - TypeScript/React desktop app
- `tests/` - Test files
