# Build Plan

> **Summary**
> - Eight phases for v1.0 (local deployment), in dependency order
> - Each phase has an explicit "done" definition — don't move on until met
> - v1.1 (AWS cloud) phases listed at the end
> - When in doubt, finish a phase fully before starting the next

---

## How to Use This Plan

Each phase is a Claude Code session worth of work. Work top to bottom. The "done" criteria are the gate — if any item isn't met, stay in the phase.

Phases 1-3 are scaffolding. Phases 4-7 are implementation. Phase 8 is integration and polish.

---

## Phase 1 — Scaffolding (Mostly Done in Starter)

**Goal:** Empty project structure, docs, abstract interfaces in place.

**Tasks:**
- ✅ Folder structure created (already in starter)
- ✅ Documentation files created (already in starter)
- ✅ Abstract interfaces written (already in starter)
- ✅ Pydantic models for People, Interaction, OpenLoop (already in starter)
- Set up `pyproject.toml` with all dependencies
- Initialize git repo
- Verify `.gitignore` blocks `.env`, `__pycache__`, `*.db`, etc.

**Done when:**
- `pip install -e .` succeeds
- `python -c "from core.models import Person"` works
- `git status` shows no `.env` or build artifacts

## Phase 2 — Configuration Layer

**Goal:** `config/settings.py` reads `.env` and instantiates the right adapters based on env vars.

**Tasks:**
- Implement `Settings` class using `pydantic-settings`
- Define env var schema (storage backend, AI provider, blob backend, etc.)
- Write factory functions that build adapters from settings
- Default values match local Docker deployment

**Done when:**
- `Settings()` loads cleanly from `.env`
- Bad env vars produce clear validation errors
- Factory can return either SQLite or DynamoDB storage based on config (DynamoDB raises NotImplementedError, that's fine)

## Phase 3 — SQLite Storage Adapter

**Goal:** Fully functional SQLite implementation of `StorageProvider`.

**Tasks:**
- Implement all methods from `adapters/storage/base.py`
- Use SQL schema from `DATA_MODEL.md`
- Handle JSON fields (tags, facts, tags_added) via JSON serialization
- Auto-create schema on first run
- Connection pooling appropriate for FastAPI's async model

**Done when:**
- Unit tests pass for: create person, get person, find by name, update person, create interaction, list interactions, create loop, update loop status
- A test script can create Jerry, log an interaction, log a loop, query everything back

## Phase 4 — Filesystem Blob Adapter

**Goal:** Local filesystem implementation of `BlobProvider` for audio file storage.

**Tasks:**
- Implement all methods from `adapters/blob/base.py`
- Default storage path configurable via env var
- Enforce file size limits
- Generate safe filenames (no traversal attacks)

**Done when:**
- Upload, retrieve, delete audio files work
- Path traversal attempts return clean errors
- Cleanup task can delete files older than N days

## Phase 5 — AI Adapters (Two!)

**Goal:** Anthropic and Ollama both implement `AIProvider` interface, fully working.

**Critical:** Build both at once. The interface only proves itself with two implementations.

**Tasks:**
- Implement `adapters/ai/anthropic_api.py` using official `anthropic` SDK
  - Use tool-use for reliable structured JSON output
  - Configurable model (default: claude-sonnet-4-5)
- Implement `adapters/ai/ollama.py` using HTTP calls (no SDK needed)
  - Use JSON mode where available
  - Robust JSON parsing with one retry on malformed output
  - Configurable model and base URL
- Both adapters implement:
  - `extract_structured(system_prompt, user_input, response_model) -> response_model`
  - `generate_text(system_prompt, user_input, max_tokens) -> str`
- Provider-agnostic prompts in `core/prompts/`

**Done when:**
- Same extraction prompt, same input, produces valid structured output from both providers
- Swap providers by changing one env var
- Neither adapter leaks provider-specific concepts to the core

## Phase 6 — Whisper Transcription Adapter

**Goal:** OpenAI Whisper API integration for voice memo transcription.

**Tasks:**
- Implement `adapters/transcription/whisper_api.py`
- Accept audio file path or bytes
- Return plain transcript text
- Handle API errors gracefully (retry on transient, fail loud on auth)

**Done when:**
- A test audio file produces a transcript
- Long files (over Whisper's limit) get rejected with a clear error
- API key issues produce clear error messages

## Phase 7 — FastAPI Application

**Goal:** Working HTTP API with all endpoints.

**Endpoints (v1.0):**
- `POST /interactions/text` — submit text, get extraction result
- `POST /interactions/audio` — submit audio (multipart), get extraction result
- `GET /people` — list people
- `GET /people/{id}` — get one person with all interactions and open loops
- `GET /people/{id}/brief` — generate pre-meeting brief
- `POST /people` — create a person (after disambiguation)
- `POST /people/{id}/loops` — manually create a loop
- `PATCH /loops/{id}` — update loop status

**Tasks:**
- FastAPI app with route modules per resource
- Pydantic request/response models for every endpoint
- Dependency injection for adapters (from settings)
- CORS configured for local frontend
- OpenAPI docs auto-generated at `/docs`
- Audit log written for every state-changing endpoint

**Done when:**
- `uvicorn api.main:app` serves a working API
- All endpoints can be exercised via `/docs`
- Errors return clean Pydantic validation messages, not stack traces

## Phase 8 — Frontend

**Goal:** Five-screen browser UI working against local API.

**Screens:**
1. **Capture** — text input + audio recorder, submits to API, shows extraction result for confirmation before save
2. **People list** — searchable list, click to drill in
3. **Person detail** — interactions timeline, open loops, tags
4. **Brief generator** — pick a person, get a brief, copy to clipboard
5. **Settings** — view (not edit) current provider config, show app version

**Tasks:**
- HTMX + Tailwind, served from FastAPI static files
- Person resolution flow: "Jerry doesn't exist — add him?" inline confirmation
- Voice memo recorder using browser MediaRecorder API
- Mobile-responsive (one-column layouts)
- No build pipeline — just CSS + minimal JS

**Done when:**
- Full Jerry walkthrough works in browser end-to-end
- Mobile Safari and desktop Firefox both work
- No console errors

## Phase 9 — Polish & Local Security Controls

**Goal:** Production-ready for local self-hosting.

**Tasks:**
- Docker Compose stack — FastAPI + optional Ollama container
- `127.0.0.1` binding in default config
- Pre-commit hooks: `gitleaks`, `detect-secrets`, `ruff`, `black`
- CI workflow on GitHub Actions: lint, test, pip-audit
- README polished with screenshots and accurate setup instructions
- SECURITY.md final review

**Done when:**
- Fresh clone + `docker compose up` produces a working app
- All pre-commit hooks pass
- CI passes on a fresh PR
- README walks a new user through setup successfully

---

## v1.1 — AWS Cloud (Later)

Listed for visibility. Do not implement in v1.0.

| Phase | Goal |
|---|---|
| **10** | Terraform modules: DynamoDB, S3, IAM, Secrets Manager, KMS |
| **11** | DynamoDB storage adapter implementation |
| **12** | S3 blob adapter implementation |
| **13** | Mangum wrapper + Lambda packaging |
| **14** | API Gateway + CloudFront + WAF Terraform |
| **15** | CloudWatch alarms, GuardDuty enablement |
| **16** | Frontend deploy to S3 + CloudFront |
| **17** | Migration scripts (local → cloud, if needed) |

---

## Anti-Patterns to Avoid

When tempted to do these, don't:

- **Skipping the second AI adapter.** Building only Anthropic in v1 = guaranteed leaky abstraction. Build both.
- **Skipping tests on storage.** Storage bugs are the worst kind to discover later. Test the SQLite adapter thoroughly.
- **Adding a frontend framework.** HTMX is enough. Resist React.
- **Implementing cloud adapters in v1.0.** They have `NotImplementedError` for a reason. Stay focused.
- **Adding "just one more" feature before v1.0 ships.** Get the loop working end-to-end first. Embeddings, person-to-person links, confidence scores — all v2.
