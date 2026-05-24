# Architectural Decisions

> **Summary**
> - 10 locked decisions that govern REMI's design.
> - Each decision is non-negotiable without explicit revisit and update.
> - When Claude Code suggests something that contradicts these, point at this file.

These decisions were made deliberately and after weighing tradeoffs. They are the North Star for the build. If a future requirement makes one of these obsolete, the decision gets updated here first, then code follows.

---

## 1. Hexagonal Architecture (Ports and Adapters)

**Decision:** Core business logic depends only on abstract interfaces. Concrete implementations (AWS SDKs, database drivers, AI providers) live in adapter modules.

**Why:** Lets the same core run locally on SQLite or in the cloud on DynamoDB. Avoids vendor lock-in. Makes testing trivial — swap real adapters for mocks.

**Implication:** `core/` never imports `boto3`, `anthropic`, or any cloud/provider SDK. Those imports live only inside `adapters/`.

## 2. FastAPI + Mangum for the API Layer

**Decision:** Build the API as a standard FastAPI application. For AWS Lambda deployment, wrap with Mangum.

**Why:** Same codebase runs three ways — uvicorn locally, Docker container locally, Lambda in cloud. Native API Gateway handlers would force two parallel API layers.

**Tradeoff accepted:** ~200-400ms additional cold start on Lambda. Negligible at personal scale.

## 3. Both Local and AWS Deployments in v1 Architecture

**Decision:** The architecture supports both deployment targets from day one, even if implementation is phased.

**Why:** Local-only would let AWS-specific assumptions creep into the design. Cloud-only would block open-source self-hosting. Both are real use cases.

**Phasing:** v1.0 ships local Docker. v1.1 adds AWS. The architecture decisions are made together.

## 4. SQLite + DynamoDB as v1 Storage Adapters

**Decision:** Two storage adapters in v1 — SQLite for local, DynamoDB for cloud.

**Why:** Two implementations force the storage interface to be real. One implementation behind an interface is a monolith with extra steps.

**Implementation phasing:** SQLite ships in v1.0. DynamoDB ships in v1.1 (stub in place from v1.0).

## 5. Multi-Provider AI is Foundational, Not Optional

**Decision:** No AI provider lock-in. The AIProvider interface supports Anthropic, OpenAI, Bedrock, Ollama, and custom HTTP endpoints. v1 ships with Anthropic and Ollama implemented — both maximally different to prove the abstraction.

**Why:** Users may need to run REMI on a corporate-approved model, a local model for privacy, or a specific provider their company has contracts with. Locking to one provider would kill those use cases.

**Implication:** All prompts in `core/prompts/` are provider-agnostic. No Anthropic-tuned formatting, no OpenAI-specific JSON modes. The adapter handles provider-specific details.

## 6. Three-Table Data Model: People, Interactions, OpenLoops

**Decision:** Relational structure across three tables. Person is identity. Interaction is an event (facts extracted, tagged, dated). OpenLoop is a commitment.

**Why:** Facts are temporal. People change. "Loves fishing" said in 2024 may be wrong by 2026. A flat document model loses this history. The relational model preserves provenance and temporal context.

**Detail:** See `DATA_MODEL.md` for full schema.

## 7. Security by Design — All v1 Requirements

**Decision:** Security is not a v2 feature. Every v1 deployment ships with:
- Secrets management (Secrets Manager in cloud, .env with strict perms locally)
- Encryption at rest (KMS in cloud, SQLCipher option locally)
- TLS 1.3 in transit
- Authentication appropriate to deployment
- Pydantic validation on all inputs
- Audit log for all write operations
- Per-Lambda least-privilege IAM (cloud)
- Documented threat model

**Why:** Bolting security on after launch fails. Threat modeling and controls have to be foundational.

**Detail:** See `SECURITY.md` for full controls matrix.

## 8. Simple Browser-Based Frontend in v1

**Decision:** Static HTML/CSS/JS frontend. HTMX + Tailwind preferred for simplicity, vanilla JS acceptable. No build pipeline, no React.

**Why:** Same UI works locally and in cloud. Low contributor friction. Five screens (capture, list, detail, brief, settings) is not a SPA problem.

**Hosting:** Served by FastAPI locally. Served from S3 + CloudFront in cloud.

## 9. Security Controls Tailored Per Deployment

**Decision:** Local and cloud deployments have different threat models and therefore different controls.

| Control area | Local | Cloud |
|---|---|---|
| Network exposure | bind 127.0.0.1 | public internet, WAF required |
| Auth | none default (localhost) | API key + Cognito (v2) |
| Transport | HTTP localhost OK | TLS 1.3 required |
| Secrets | .env + chmod 600 | AWS Secrets Manager |
| Encryption at rest | OS disk + optional SQLCipher | KMS-encrypted DynamoDB/S3 |
| Audit | local file/SQLite table | CloudWatch + DynamoDB |

**Why:** A control that makes sense in one environment is overkill or impossible in the other. One-size-fits-all security is bad security.

## 10. Local-First Build Sequence

**Decision:** v1.0 = local Docker only. v1.1 adds AWS. Both targets remain locked architectural commitments — local-first is a sequencing decision, not a scope cut.

**Why:** Cheaper iteration. Faster feedback. Catches design flaws when fixes are cheap (schema changes in SQLite vs DynamoDB migrations). Forces the abstractions to be real.

**Risk acknowledged:** Cloud could become "someday-maybe." Mitigation: stub cloud adapters now with `NotImplementedError`. Empty Terraform folder with placeholder README. The path stays visible.

---

## When to Update This File

Update a decision only when:
1. A real-world requirement makes it obsolete (not a preference)
2. The new decision is written down here *before* code changes
3. The change is small enough to be a clear edit, or large enough to be a new numbered decision

Do not update for:
- Coding style preferences
- Library version changes
- Implementation details that don't affect architecture
