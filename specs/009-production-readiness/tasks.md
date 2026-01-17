# Tasks: Production Readiness Improvements

**Input**: Design documents from `/specs/009-production-readiness/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US6)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `app/` at repository root
- **Tests**: `tests/` at repository root
- Paths follow existing Empire FastAPI structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new core modules and directory structure

- [ ] T001 Create app/core/ directory if not exists
- [ ] T002 [P] Create app/core/__init__.py with module exports
- [ ] T003 [P] Create app/core/service_timeouts.py with timeout constants (from data-model.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend existing error models before user story implementation

**⚠️ CRITICAL**: Error models must be in place before standardized responses can be used

- [ ] T004 Extend app/models/errors.py with StandardError, ErrorCode enum, ErrorResponse models (from data-model.md)
- [ ] T005 [P] Create app/middleware/rate_limit_tiers.py with RateLimitTier model and RATE_LIMIT_TIERS constants
- [ ] T006 [P] Extend app/services/circuit_breaker.py with CircuitBreakerConfig model and CIRCUIT_BREAKER_CONFIGS

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Fail-Fast Startup Validation (Priority: P1) 🎯 MVP

**Goal**: Application fails immediately at startup if critical environment variables are missing

**Independent Test**: Start app without SUPABASE_URL, verify exit code 1 with clear error message

### Tests for User Story 1

- [ ] T007 [P] [US1] Create tests/test_startup_validation.py with test fixtures
- [ ] T008 [P] [US1] Test: missing critical env var causes startup failure in tests/test_startup_validation.py
- [ ] T009 [P] [US1] Test: missing recommended env var logs warning but continues in tests/test_startup_validation.py
- [ ] T010 [P] [US1] Test: empty string env var treated as missing in tests/test_startup_validation.py
- [ ] T011 [P] [US1] Test: all env vars present logs success message in tests/test_startup_validation.py

### Implementation for User Story 1

- [ ] T012 [US1] Create app/core/startup_validation.py with CRITICAL_ENV_VARS and RECOMMENDED_ENV_VARS constants
- [ ] T013 [US1] Implement validate_environment() function in app/core/startup_validation.py
- [ ] T014 [US1] Add startup hook in app/main.py to call validate_environment() before accepting traffic
- [ ] T015 [US1] Add structlog logging for validation results in app/core/startup_validation.py

**Checkpoint**: US1 complete - app fails fast on missing critical env vars

---

## Phase 4: User Story 2 - CORS Security Enforcement (Priority: P1)

**Goal**: CORS strictly configured in production, app refuses to start if misconfigured

**Independent Test**: Start app with ENVIRONMENT=production and CORS_ORIGINS="*", verify startup failure

### Tests for User Story 2

- [ ] T016 [P] [US2] Create tests/test_cors_hardening.py with test fixtures
- [ ] T017 [P] [US2] Test: wildcard CORS in production causes startup failure
- [ ] T018 [P] [US2] Test: missing CORS_ORIGINS in production causes startup failure
- [ ] T019 [P] [US2] Test: wildcard CORS in development allowed with warning

### Implementation for User Story 2

- [ ] T020 [US2] Add validate_cors_origins() function in app/core/startup_validation.py
- [ ] T021 [US2] Update CORS configuration in app/main.py to call validate_cors_origins()
- [ ] T022 [US2] Add structlog logging for CORS validation in app/main.py

**Checkpoint**: US2 complete - CORS strictly enforced in production

---

## Phase 5: User Story 3 - Sensitive Endpoint Rate Limiting (Priority: P1)

**Goal**: Stricter rate limits on authentication and upload endpoints

**Independent Test**: Send 6 login requests in 1 minute, verify 429 on 6th request

### Tests for User Story 3

- [ ] T023 [P] [US3] Create tests/test_rate_limiting.py with Redis mock fixtures
- [ ] T024 [P] [US3] Test: login endpoint blocks after 5 requests/minute
- [ ] T025 [P] [US3] Test: registration endpoint blocks after 3 requests/minute
- [ ] T026 [P] [US3] Test: upload endpoint blocks after 10 requests/minute
- [ ] T027 [P] [US3] Test: rate limit response includes Retry-After header

### Implementation for User Story 3

- [ ] T028 [US3] Update app/middleware/rate_limit.py to support tiered rate limiting
- [ ] T029 [US3] Add rate limit decorators to app/routes/users.py login endpoint (5/min)
- [ ] T030 [US3] Add rate limit decorators to app/routes/users.py register endpoint (3/min)
- [ ] T031 [US3] Add rate limit decorators to app/routes/documents.py upload endpoint (10/min)
- [ ] T032 [US3] Add rate limit decorators to app/routes/query.py endpoints (60/min)
- [ ] T033 [US3] Add rate limit decorators to app/routes/multi_agent_orchestration.py (30/min)
- [ ] T034 [US3] Update rate limit response to return standardized ErrorResponse with Retry-After header

**Checkpoint**: US3 complete - sensitive endpoints rate limited

---

## Phase 6: User Story 4 - External Service Timeout Protection (Priority: P2)

**Goal**: All external service calls have configurable timeouts

**Independent Test**: Mock slow LlamaIndex service, verify timeout after 60s

### Tests for User Story 4

- [ ] T035 [P] [US4] Create tests/test_service_timeouts.py with httpx mock fixtures
- [ ] T036 [P] [US4] Test: LlamaIndex service times out after 60s
- [ ] T037 [P] [US4] Test: CrewAI service times out after 120s
- [ ] T038 [P] [US4] Test: Ollama service times out after 30s
- [ ] T039 [P] [US4] Test: Neo4j service times out after 15s

### Implementation for User Story 4

- [ ] T040 [US4] Add timeout configuration to app/services/llama_index_service.py using httpx.Timeout
- [ ] T041 [US4] Add timeout configuration to app/services/crewai_service.py using httpx.Timeout
- [ ] T042 [US4] Add timeout configuration to app/services/embedding_service.py using httpx.Timeout
- [ ] T043 [US4] Add timeout configuration to app/services/neo4j_service.py using httpx.Timeout
- [ ] T044 [US4] Add timeout configuration to app/services/b2_storage.py using httpx.Timeout
- [ ] T045 [US4] Add timeout error handling that returns EXTERNAL_SERVICE_ERROR response

**Checkpoint**: US4 complete - all external calls have timeouts

---

## Phase 7: User Story 5 - Circuit Breaker Protection (Priority: P2)

**Goal**: Circuit breakers on all external service calls prevent cascading failures

**Independent Test**: Fail LlamaIndex 5 times, verify 6th request fails immediately with "Circuit breaker open"

### Tests for User Story 5

- [ ] T046 [P] [US5] Create tests/test_circuit_breakers.py with mock service fixtures
- [ ] T047 [P] [US5] Test: LlamaIndex circuit opens after 5 failures
- [ ] T048 [P] [US5] Test: circuit in open state fails immediately
- [ ] T049 [P] [US5] Test: circuit transitions to half-open after recovery timeout
- [ ] T050 [P] [US5] Test: successful request in half-open closes circuit

### Implementation for User Story 5

- [ ] T051 [US5] Apply circuit breaker decorator to app/services/llama_index_service.py (5 failures, 30s recovery)
- [ ] T052 [US5] Apply circuit breaker decorator to app/services/crewai_service.py (3 failures, 60s recovery)
- [ ] T053 [US5] Apply circuit breaker decorator to app/services/embedding_service.py (5 failures, 15s recovery)
- [ ] T054 [US5] Apply circuit breaker decorator to app/services/neo4j_service.py (3 failures, 30s recovery)
- [ ] T055 [US5] Apply circuit breaker decorator to app/services/b2_storage.py (5 failures, 60s recovery)
- [ ] T056 [US5] Verify /api/system/circuit-breakers endpoint exposes all circuit breaker states

**Checkpoint**: US5 complete - all services have circuit breakers

---

## Phase 8: User Story 6 - Standardized Error Responses (Priority: P3)

**Goal**: All error responses follow consistent format with code, message, details, request_id, timestamp

**Independent Test**: Trigger various errors and verify response format consistency

### Tests for User Story 6

- [ ] T057 [P] [US6] Create tests/test_error_responses.py with endpoint fixtures
- [ ] T058 [P] [US6] Test: validation error returns VALIDATION_ERROR code with 400 status
- [ ] T059 [P] [US6] Test: external service error returns EXTERNAL_SERVICE_ERROR code with 502 status
- [ ] T060 [P] [US6] Test: all errors include request_id and timestamp
- [ ] T061 [P] [US6] Test: error logs include request_id for correlation

### Implementation for User Story 6

- [ ] T062 [US6] Update app/middleware/error_handler.py to use StandardError for all exceptions
- [ ] T063 [US6] Add request_id extraction middleware or use existing X-Request-ID header
- [ ] T064 [US6] Update exception handlers to include request_id and timestamp in all error responses
- [ ] T065 [US6] Update structlog configuration to include request_id in all error logs
- [ ] T066 [US6] Add stack trace logging ONLY for 500 errors (FR-030)

**Checkpoint**: US6 complete - all errors follow standardized format

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and integration testing

- [ ] T067 [P] Run full test suite: pytest tests/test_startup_validation.py tests/test_cors_hardening.py tests/test_rate_limiting.py tests/test_service_timeouts.py tests/test_circuit_breakers.py tests/test_error_responses.py -v
- [ ] T068 [P] Run quickstart.md validation scenarios
- [ ] T069 Verify production readiness score is 100/100
- [ ] T070 Update CLAUDE.md with production readiness completion status

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1-US3 are P1 priority (Critical) - implement first
  - US4-US5 are P2 priority (High) - implement second
  - US6 is P3 priority (Medium) - implement last
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational - No dependencies on other stories
- **US2 (P1)**: Can start after Foundational - Extends US1's startup_validation.py
- **US3 (P1)**: Can start after Foundational - Uses rate_limit_tiers.py from Foundational
- **US4 (P2)**: Can start after Foundational - No dependencies on US1-3
- **US5 (P2)**: Can start after Foundational - No dependencies on US1-4
- **US6 (P3)**: Can start after Foundational - Uses StandardError from Foundational

### Parallel Opportunities

Within each phase, tasks marked [P] can run in parallel:
- All tests within a user story can run in parallel
- US1-US3 (all P1) can be worked on in parallel by different developers
- US4-US5 (all P2) can be worked on in parallel
- US6 can be started once StandardError model is ready

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: T007 "Create tests/test_startup_validation.py with test fixtures"
Task: T008 "Test: missing critical env var causes startup failure"
Task: T009 "Test: missing recommended env var logs warning"
Task: T010 "Test: empty string env var treated as missing"
Task: T011 "Test: all env vars present logs success message"
```

---

## Implementation Strategy

### MVP First (US1-US3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3-5: User Stories 1-3 (all P1 priority)
4. **STOP and VALIDATE**: Test all P1 stories independently
5. Deploy to staging for 24h monitoring

### Full Implementation

1. Complete MVP (US1-US3)
2. Add US4-US5 (P2 priority)
3. Add US6 (P3 priority)
4. Complete Phase 9: Polish
5. Deploy to production

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1: Setup | T001-T003 | Create core modules |
| Phase 2: Foundational | T004-T006 | Extend error models |
| Phase 3: US1 | T007-T015 | Startup validation |
| Phase 4: US2 | T016-T022 | CORS hardening |
| Phase 5: US3 | T023-T034 | Rate limiting |
| Phase 6: US4 | T035-T045 | Service timeouts |
| Phase 7: US5 | T046-T056 | Circuit breakers |
| Phase 8: US6 | T057-T066 | Error responses |
| Phase 9: Polish | T067-T070 | Final validation |

**Total Tasks**: 70
**P1 Tasks (Critical)**: 31 (US1-US3)
**P2 Tasks (High)**: 22 (US4-US5)
**P3 Tasks (Medium)**: 13 (US6 + Polish)
