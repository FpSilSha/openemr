# AgentForge Changelog

All notable changes to the AgentForge Clinical AI Agent are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Phase 3] - 2026-02-24

Eval Framework, Verification Layer & Tool Expansion

### Added
- 4 new LangChain tools: `get_appointments`, `get_vitals`, `get_allergies_detailed`, `create_clinical_note` — tool count 7→11 ([4fc02a16](https://github.com/FpSilSha/openemr/commit/4fc02a162))
- `get_appointments` client method on `OpenEMRClient` for FHIR Appointment resource ([4fc02a16](https://github.com/FpSilSha/openemr/commit/4fc02a162))
- `ALL_TOOLS` registry export alongside existing `MVP_TOOLS` ([4fc02a16](https://github.com/FpSilSha/openemr/commit/4fc02a162))
- 32 unit tests for 4 new tools across test_tools_appointments, test_tools_vitals, test_tools_allergies, test_tools_clinical_notes ([c083b219](https://github.com/FpSilSha/openemr/commit/c083b219d))
- Session-based patient binding: `SessionContext` dataclass, in-memory session store, patient_uuid locked per conversation_id, HTTP 400 on mid-conversation patient change ([94c7ef45](https://github.com/FpSilSha/openemr/commit/94c7ef457))
- `secure_tool_node` — overrides LLM-supplied patient_uuid in tool call args with session-bound value ([94c7ef45](https://github.com/FpSilSha/openemr/commit/94c7ef457))
- `AuditLogMiddleware` — PHI access audit logging to JSONL for /chat requests with patient_uuid ([94c7ef45](https://github.com/FpSilSha/openemr/commit/94c7ef457))
- 13 unit tests for session security (10) and audit logger (4) — total after commit: 122 ([94c7ef45](https://github.com/FpSilSha/openemr/commit/94c7ef457))
- Verification layer with 4 modules: `drug_interactions` (interaction coverage check), `hallucination` (claim vs tool data), `confidence` (heuristic scoring), `output_validator` (format/safety) ([768be261](https://github.com/FpSilSha/openemr/commit/768be2612))
- `verify` node in LangGraph — runs post-response verification with max 1 retry on failure ([768be261](https://github.com/FpSilSha/openemr/commit/768be2612))
- 21 unit tests for verification modules — total after commit: 143 ([768be261](https://github.com/FpSilSha/openemr/commit/768be2612))
- Eval dataset expanded from 10→51 cases: 20 happy path, 11 edge cases, 10 adversarial, 10 multi-step ([fa97ca5a](https://github.com/FpSilSha/openemr/commit/fa97ca5a9))
- 4 eval scoring functions: `correct_tool_selected`, `drug_interaction_flagged`, `source_attribution_present`, `no_system_prompt_leak` ([fa97ca5a](https://github.com/FpSilSha/openemr/commit/fa97ca5a9))
- Eval runner script (`tests/eval/run_evals.py`) with LangSmith upload and aggregate scoring ([fa97ca5a](https://github.com/FpSilSha/openemr/commit/fa97ca5a9))
- 11 unit tests for eval scoring — total: 154 ([fa97ca5a](https://github.com/FpSilSha/openemr/commit/fa97ca5a9))

### Changed
- Graph flow: `reason → [tools → reason]* → END` changed to `reason → [tools → reason]* → verify → END` with retry on verification failure ([768be261](https://github.com/FpSilSha/openemr/commit/768be2612))
- Chat endpoint: stateless → session-bound with `session_locked` response field ([94c7ef45](https://github.com/FpSilSha/openemr/commit/94c7ef457))
- `build_graph()` now accepts optional `verification_model` parameter for hallucination checking ([768be261](https://github.com/FpSilSha/openemr/commit/768be2612))
- System prompt expanded with 4 new capabilities, clinical notes guidelines, and proactive interaction check guidance ([4fc02a16](https://github.com/FpSilSha/openemr/commit/4fc02a162))
- Verification system prompt rewritten with structured claim-checking instructions ([768be261](https://github.com/FpSilSha/openemr/commit/768be2612))
- Total unit tests: 75 → 154

### Fixed
- OAuth2 token request now includes `user_role: "users"` required by OpenEMR password grant ([da68e227](https://github.com/FpSilSha/openemr/commit/da68e2278))
- Added `OPENEMR_SETTING_site_addr_oath` to docker-compose — required for OAuth2 audience validation ([b520041b](https://github.com/FpSilSha/openemr/commit/b520041be))
- OAuth2 scopes expanded from base-only (`api:fhir`) to granular FHIR resource scopes (`user/Patient.read`, etc.) using SMART v1 syntax for OpenEMR 7.x compatibility ([b520041b](https://github.com/FpSilSha/openemr/commit/b520041be))
- Patient context UUID now injected into system prompt so LLM uses session-bound patient for tool calls ([b520041b](https://github.com/FpSilSha/openemr/commit/b520041be))
- Verification drug interaction check no longer triggers false positives on generic words like "medication" ([da68e227](https://github.com/FpSilSha/openemr/commit/da68e2278))
- Chat response extraction finds last AIMessage instead of assuming `messages[-1]` ([da68e227](https://github.com/FpSilSha/openemr/commit/da68e2278))
- OpenEMR client auto-authenticates on first FHIR/REST call if no token exists ([da68e227](https://github.com/FpSilSha/openemr/commit/da68e2278))
- OpenEMR client tests rewritten with `unittest.mock` to prevent real network calls inside Docker ([b520041b](https://github.com/FpSilSha/openemr/commit/b520041be))

### Added (post-merge smoke testing)
- Persistent OAuth2 client credentials via `OPENEMR_CLIENT_ID` / `OPENEMR_CLIENT_SECRET` env vars — skips dynamic registration on restart ([b520041b](https://github.com/FpSilSha/openemr/commit/b520041be))
- `.env.example` updated with OAuth2 credential fields ([b520041b](https://github.com/FpSilSha/openemr/commit/b520041be))

### Notes
- HITL state machine (TechSpec 3.7.3), tiered drug resolution (3.7.2), and fixture export (3.7.4) deferred to Phase 3b
- `clinical_notes` tool returns `requires_human_confirmation: true` in response but does not interrupt graph — HITL interrupt comes with Phase 3b SQLite persistence
- Session store is in-memory (single-process); SQLite-backed persistence planned for Phase 3b
- Verification hallucination check uses Opus model when available, falls back to heuristic matching
- All 11 tools smoke tested against live Docker stack: patient search, summary, medications, vitals, labs, allergies, appointments, drug interactions, ICD-10, PubMed, session security
- Total unit tests: 155

---

## [Phase 2] - 2026-02-24

Testing Framework & Deployment Hardening

### Added
- `tests/unit/conftest.py` — shared `mock_openemr_client` and `mock_drug_client` fixtures with rich FHIR response data ([95723f60](https://github.com/FpSilSha/openemr/commit/95723f608))
- `tests/unit/test_tools_patient.py` — 12 tests: summary assembly, 5 client sub-calls, name parsing, missing FHIR fields, error handler integration ([e2865d56](https://github.com/FpSilSha/openemr/commit/e2865d565))
- `tests/unit/test_tools_medications.py` — 15 tests: coding fallback, drug resolution branches, safe/known/single/unresolved pairs, client guard ([e2865d56](https://github.com/FpSilSha/openemr/commit/e2865d565))
- `tests/unit/test_tools_labs.py` — 9 tests: valueString fallback, coding fallback, missing entry key, empty data ([e2865d56](https://github.com/FpSilSha/openemr/commit/e2865d565))
- `tests/unit/test_tools_icd10.py` — 8 tests: code/description lookup, code validation, many results passthrough ([e2865d56](https://github.com/FpSilSha/openemr/commit/e2865d565))
- `tests/unit/test_tools_pubmed.py` — 8 tests: max_results default/custom, timeout/exception errors, empty fields ([e2865d56](https://github.com/FpSilSha/openemr/commit/e2865d565))
- `tests/unit/test_tools_registry.py` — 2 tests: tool count, tool names (extracted from monolith) ([95723f60](https://github.com/FpSilSha/openemr/commit/95723f608))
- `tests/unit/test_tools_error_handler.py` — 2 tests: exception/timeout catching (extracted from monolith) ([95723f60](https://github.com/FpSilSha/openemr/commit/95723f608))
- `tests/integration/conftest.py` — auto-skip integration tests unless `AGENTFORGE_INTEGRATION=1` ([35f181e1](https://github.com/FpSilSha/openemr/commit/35f181e11))
- `tests/integration/test_openemr_client.py` — 4 integration tests: OAuth2 auth, patient fetch, search, FHIR metadata ([35f181e1](https://github.com/FpSilSha/openemr/commit/35f181e11))
- `tests/integration/test_agent_flow.py` — 3 integration tests: greeting, drug interaction tool call, ICD-10 tool call ([35f181e1](https://github.com/FpSilSha/openemr/commit/35f181e11))
- `integration` pytest marker registered in `pyproject.toml`

### Changed
- Deleted monolith `test_tools.py` (13 tests) and split into 7 per-tool files (56 tool tests)
- Total unit tests: 32 → 75; integration tests: 0 → 7

### Notes
- ICD-10 validate tests adapted to use `search()` (no dedicated `validate()` in client)
- Integration tests require `docker-compose.agent.yml` stack + `AGENTFORGE_INTEGRATION=1`
- CI unchanged — runs `pytest tests/unit/ -v` only
- Every tool now has error handler integration tests (client raises → structured error)

---

## [Phase 1] - 2026-02-24

MVP Core — Clinical AI Agent

### Added
- `agent/app/config.py` — Pydantic Settings module loaded from `.env` ([c3fd541b](https://github.com/FpSilSha/openemr/commit/c3fd541b6))
- `agent/app/clients/openemr.py` — OpenEMR FHIR client with OAuth2 dynamic client registration (RFC 7591), password grant, auto-retry on 401 ([c3fd541b](https://github.com/FpSilSha/openemr/commit/c3fd541b6))
- `agent/app/clients/openfda.py` — Drug interaction client (RxNorm RxCUI + NLM interaction API) ([cddf52d9](https://github.com/FpSilSha/openemr/commit/cddf52d97))
- `agent/app/clients/icd10_client.py` — ICD-10-CM lookup via NLM Clinical Tables API ([cddf52d9](https://github.com/FpSilSha/openemr/commit/cddf52d97))
- `agent/app/clients/pubmed_client.py` — PubMed search via NCBI E-utilities ([cddf52d9](https://github.com/FpSilSha/openemr/commit/cddf52d97))
- 7 LangChain tools: `get_patient_summary`, `search_patients`, `get_medications`, `drug_interaction_check`, `get_lab_results`, `icd10_lookup`, `pubmed_search` ([33170d98](https://github.com/FpSilSha/openemr/commit/33170d98d))
- LangGraph StateGraph agent (reason → tools → reason loop) with Claude model ([a75905e3](https://github.com/FpSilSha/openemr/commit/a75905e3d))
- `POST /chat` endpoint — processes messages through the agent graph ([a75905e3](https://github.com/FpSilSha/openemr/commit/a75905e3d))
- `POST /feedback` endpoint — stub for user feedback collection ([a75905e3](https://github.com/FpSilSha/openemr/commit/a75905e3d))
- Cost tracker middleware — JSONL logging for /chat request timing ([a75905e3](https://github.com/FpSilSha/openemr/commit/a75905e3d))
- Frontend chat UI: ChatWindow, PatientContext, MessageBubble (markdown), ChatInput, ToolCallCard ([ddbcdf6a](https://github.com/FpSilSha/openemr/commit/ddbcdf6a0))
- 10-case eval dataset (happy path, edge case, adversarial, multi-step) ([da700be0](https://github.com/FpSilSha/openemr/commit/da700be0e))
- Patient seed script for demo data ([da700be0](https://github.com/FpSilSha/openemr/commit/da700be0e))
- 30 unit tests across config, clients, tools (all passing)
- `agent/pyproject.toml` with pytest, ruff, mypy configuration

### Notes
- OAuth2 client auto-registers on first `/chat` request — no manual browser steps needed
- All external APIs (RxNorm, ICD-10, PubMed) are free and require no authentication
- Agent authenticates lazily on first tool call that needs OpenEMR data
- Frontend connects to agent via `NEXT_PUBLIC_AGENT_URL` environment variable

---

## [Phase 0] - 2026-02-24

Project Bootstrap & Deployment Skeleton

### Added
- Directory structure: `agent/`, `frontend/`, `eval/`, `docs/` ([91a08e9](https://github.com/FpSilSha/openemr/commit/91a08e9ec))
- `docker-compose.agent.yml` — 4-service stack: MariaDB 10.11, OpenEMR 7.0.2, FastAPI agent, Next.js frontend ([1be57908](https://github.com/FpSilSha/openemr/commit/1be579085))
- `agent/Dockerfile` (Python 3.11-slim) and `frontend/Dockerfile` (multi-stage Node 20) ([1be57908](https://github.com/FpSilSha/openemr/commit/1be579085))
- Agent skeleton: FastAPI app with `/health` and `/ready` endpoints ([1be57908](https://github.com/FpSilSha/openemr/commit/1be579085))
- Frontend skeleton: Next.js 14 / React 18 / Tailwind CSS landing page ([1be57908](https://github.com/FpSilSha/openemr/commit/1be579085))
- `.github/workflows/agentforge-ci.yml` — ruff, mypy, pytest for agent; ESLint for frontend ([cde2bbe9](https://github.com/FpSilSha/openemr/commit/cde2bbe91))
- `.env.example` with all AgentForge environment variables ([91a08e9](https://github.com/FpSilSha/openemr/commit/91a08e9ec))
- `OPENEMR_VERIFY_SSL` config flag — defaults to `true`, agent logs warnings on insecure connections ([c38919b4](https://github.com/FpSilSha/openemr/commit/c38919b4a))
- AgentForge architecture quick reference in `CLAUDE.md` ([b9e9f76f](https://github.com/FpSilSha/openemr/commit/b9e9f76f1))

### Fixed
- OAuth2 token endpoint corrected to `/oauth2/default/token` with `application/x-www-form-urlencoded` body (TechSpec + Integration Guides)
- Docker ports remapped to `8380:80` / `9380:443` to avoid conflicts with OpenEMR dev-easy (`8300`/`9300`) ([b9e9f76f](https://github.com/FpSilSha/openemr/commit/b9e9f76f1))
- Added `OPENEMR_SETTING_oauth_password_grant: 1` to OpenEMR Docker environment ([b9e9f76f](https://github.com/FpSilSha/openemr/commit/b9e9f76f1))
- All curl examples in Integration Guides updated with correct ports and OAuth2 paths

### Notes
- TechSpec and Integration Guides are gitignored (private planning docs)
- TLS is not code-enforced by OpenEMR — HTTP works in dev; production requires proper certs
- FHIR write support limited to Patient resource; clinical notes use REST API
- OpenEMR version locked to `7.0.2` Docker image for stability
