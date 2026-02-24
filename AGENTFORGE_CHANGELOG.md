# AgentForge Changelog

All notable changes to the AgentForge Clinical AI Agent are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
