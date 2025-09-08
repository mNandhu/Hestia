# Implementation Plan: Hestia - Personal On-Demand Service Gateway

**Branch**: `001-hestia-a-personal` | **Date**: September 8, 2025 | **Spec**: `/home/mnand/Projects/Hestia/specs/001-hestia-a-personal/spec.md`
**Input**: Feature specification from `/home/mnand/Projects/Hestia/specs/001-hestia-a-personal/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, or `GEMINI.md` for Gemini CLI).
6. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Hestia provides a single, smart gateway for client applications to access personal services across multiple machines. It determines the required service from the request, auto-starts it on the appropriate machine per rules, routes the request, and shuts down idle services. The gateway exposes a stable port (8080) and a transparent reverse-proxy under `/services/{serviceId}/...` so clients can point to `http://localhost:8080/services/<alias>` without code changes. The delivery approach is containerized (Docker + docker-compose), with a Python 3.12 FastAPI application, SQLite persistence (volume-backed), and integration with Ansible Semaphore via internal Docker networking. A pluggable strategy pattern loads routing/startup logic from a `strategies/` directory, with hot-reload via bind-mounts in development.

## Technical Context
**Language/Version**: Python 3.12+  
**Primary Dependencies**: FastAPI, Uvicorn, Pydantic, SQLAlchemy, httpx  
**Storage**: SQLite (persisted via named Docker volume)  
**Testing**: pytest, pytest-asyncio; respx or httpx.MockTransport for external API mocking  
**Target Platform**: Linux via Docker and docker-compose  
**Project Type**: Single backend service (Option 1: Single project)  
**Performance Goals**: Gateway overhead target ≤ 200ms p95 for routed requests; cold-starts tolerated with request queueing; baseline cold start target: local ≤ 60s, remote/HPC ≤ 180s  
**Constraints**: Transparent client experience via stable gateway `http://localhost:8080/services/{serviceId}/...`; optional auth (API key for API, username/password for dashboard); idle shutdown configurable  
**Scale/Scope**: Single-user/operator with multiple services across 1-3 machines; dozens of services

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 2 (src, tests)
- Using framework directly? Yes (FastAPI directly)
- Single data model? Yes (SQLAlchemy models for persistent entities)
- Avoiding patterns? Yes (only Strategy plugin where required by spec)

**Architecture**:
- EVERY feature as library? Core engine packaged as library within repo
- Libraries listed: core (engine, persistence), strategies (plugins), api (FastAPI app), cli (admin/dev commands)
- CLI per library: Plan hestia CLI (e.g., hestia start/stop/status) with --format json|text
- Library docs: Quickstart and contracts provided in specs

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor: Enforced (contract/integration tests first)
- Commits: Tests before implementation
- Order: Contract→Integration→E2E→Unit
- Real dependencies: SQLite used in tests; external APIs mocked (Semaphore via respx)
- Integration tests: For gateway→strategy→db flows
- FORBIDDEN: Implementation before failing tests

**Observability**:
- Structured logging included (configurable levels); capture routing decisions, start/stop, retries, readiness, idle shutdowns, auth decisions
- Unified stream within backend; optional activity timeline
- Error context includes correlation/request IDs

**Versioning**:
- Version number assigned: 0.1.0
- BUILD increments on changes
- Breaking changes: migration notes in quickstart.md when applicable

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 1 (Single project) – backend service only

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - Readiness fallback behavior without health endpoint: resolved → per-service warm-up period
   - Request queueing behavior and limits: resolved → FIFO queue with max wait timeout (configurable)
   - API key and dashboard credential storage: resolved → config file + env overrides
   - Semaphore API usage details: resolved → internal URL via service name, use API token
   - Strategy plugin discovery/loading: resolved → load from strategies/ directory via importlib
   - Docker Compose volumes and networks: resolved → named volumes for SQLite and Semaphore; default network

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `/scripts/update-agent-context.sh [claude|gemini|copilot]` for your AI assistant
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, quickstart.md

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P] 
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation 
- Dependency order: Models before services before UI
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md (generated in this run per prompt)

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - approach described and tasks generated)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [ ] Complexity deviations documented

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*