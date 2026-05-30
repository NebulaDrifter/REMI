# Security Model

> **Summary**
> - REMI holds high-sensitivity personal data: notes about real people, things they trusted you with.
> - Threat model documents what we defend against and what we don't.
> - Local and cloud deployments have different controls — see matrix below.
> - When in doubt, default to the more restrictive option.

---

## What We're Protecting

**The data itself:**
- Notes about real people
- Conversations they trusted you with
- Some content could be professionally damaging if leaked (gossip, salary discussions, intros not yet made)
- Some content is deeply personal (someone's family situation, health, life events)

This is **high-sensitivity personal data** even when no individual record looks like a credit card.

## Threat Actors

In rough order of likelihood:

1. **Yourself, accidentally** — committing a secret to GitHub, exposing a local port, leaving a backup unencrypted. Most common breach cause for solo devs.
2. **External attackers** — internet-wide scanners hitting any exposed endpoint.
3. **Credential theft** — AWS keys leaked via screenshots, repos, or compromised dev machines.
4. **AI provider exposure** — the provider sees every interaction body sent for extraction.
5. **Cloud provider insider threat** — theoretical; relevant for high-sensitivity deployments.
6. **Malicious contributor** — a PR that exfiltrates data, slipping past review.
7. **Local machine compromise** — root access to your laptop defeats most controls.

## What We Defend Against

- Accidental secret leakage (gitleaks, .gitignore enforcement, pre-commit hooks)
- Network attacks on exposed endpoints (TLS, WAF, rate limiting in cloud)
- Credential compromise impact (least-privilege IAM, key rotation)
- AI provider data minimization (only necessary fields sent)
- Encrypted-at-rest data (KMS in cloud, SQLCipher option locally)
- Prompt injection in user input (delimiters, structured output enforcement)
- Audit trail for incident forensics
- Supply chain attacks (dependency pinning, audit, Dependabot)

## What We Do NOT Defend Against

Be honest with users. Don't claim defenses you don't have.

- **Root compromise of the host machine.** If an attacker has root on the box running REMI, they have your data.
- **AI provider breaches.** Once data leaves for Anthropic/OpenAI/etc., it's subject to their security posture.
- **Physical access to an unencrypted disk.** Full-disk encryption is the user's responsibility.
- **Sophisticated supply chain attacks** that get past Dependabot and audit tools.
- **Phishing or social engineering** of the user.
- **State-level actors** with capability to compel cooperation from cloud providers.

## Controls Matrix

| Control area | Local deployment | Cloud deployment |
|---|---|---|
| **Network binding** | `127.0.0.1` only by default | Public via API Gateway + CloudFront |
| **Auth** | None (localhost trust boundary) | API key minimum, Cognito in v2 |
| **TLS** | HTTP localhost OK; HTTPS required if exposed | TLS 1.3 required, HSTS enabled |
| **WAF** | N/A | AWS WAF with managed rule sets |
| **Rate limiting** | N/A (single user) | API Gateway usage plans |
| **Secrets** | `.env` file, gitignored, `chmod 600` | AWS Secrets Manager, rotation enabled |
| **Encryption at rest** | OS full-disk encryption + filesystem perms; optional SQLCipher | KMS-encrypted DynamoDB + S3 |
| **KMS keys** | N/A | Customer-managed for high-sensitivity deployments |
| **Audit logging** | Local file or SQLite audit table | CloudWatch + DynamoDB audit table |
| **Input validation** | Pydantic on every endpoint | Pydantic on every endpoint |
| **Prompt injection defense** | Delimited user input + structured output | Same |
| **Audio retention** | User-configurable, default 7 days | S3 lifecycle delete after 7 days |
| **Backup** | User responsibility (documented) | DynamoDB PITR + S3 versioning |
| **Supply chain** | `pip-audit`, Dependabot | Same |
| **IAM** | N/A | Per-Lambda least-privilege roles |

## Foundational Rules — Both Deployments

These are absolutes. Never deviate.

1. **No secrets in code.** Ever. Use `.env` (local) or Secrets Manager (cloud).
2. **No secrets in env vars set in plaintext on the Lambda console.** Use Secrets Manager and fetch at cold-start.
3. **No `verify=False`** on any HTTP client. Cert verification stays on.
4. **No `*` in CORS** in production. Lock to specific origins.
5. **No `Resource: "*"`** in IAM policies. Always scope to specific ARNs.
6. **No `0.0.0.0` bind** in local default config. User must opt-in to network exposure.
7. **No logging of full request bodies.** Use structured logs with explicit allow-listed fields.
8. **No telemetry phoning home.** Open-source project, no usage tracking, period.

## Input Validation Standards

Every API endpoint:
- Validates request body via Pydantic model
- Enforces reasonable length limits (raw input ceiling: 50,000 chars)
- Rejects malformed JSON with 400, never 500

Every user-provided text fed into an AI prompt:
- Wrapped in explicit delimiters (`<user_input>...</user_input>`)
- System prompt instructs the model to treat delimited content as untrusted data
- Extraction always returns structured JSON conforming to a Pydantic model — even if the user input says "ignore that and do X," the output schema rejects it

Every brief retrieval:
- Only queries by `personId` from authenticated session
- No freeform query strings that could be manipulated
- No "include all people whose name matches…" patterns in v1

## Audit Logging

Every write operation logs to an audit table:

```
{
  actor: <user_id or "single_user_mode">,
  action: "create_person" | "update_person" | "create_interaction" | ...,
  resource_id: <id of affected record>,
  timestamp: <ISO8601>,
  source: "api" | "background_job"
}
```

**Never logged:** the actual data (names, notes, transcripts). Audit log captures *that something happened*, not what was said.

Model management actions (`pull_model`, `delete_model`, `set_active_model`) are audited the same way — the model name is operational metadata, not personal data.

## Local Model Management (Ollama)

REMI can pull, delete, and hot-swap local models from the Settings screen. New risks and the controls for them:

| Risk | Control |
|---|---|
| Pulling arbitrary models exhausts disk/RAM | Models persist to a dedicated volume the user can clear. Pulls are explicit, user-initiated actions — never automatic. UI warns that large models need more RAM. |
| Untrusted model source | Pulls go through Ollama (registry or `hf.co/...` GGUF). REMI runs the model for **inference only** — no arbitrary code execution path is added. |
| Model name injection | Names are Pydantic-validated against a strict character allowlist before reaching Ollama. |
| Ollama exposed to the network | The Ollama container publishes **no host port**. It is reachable only on the internal Docker network from REMI. |
| Deleting the in-use model | Blocked — the active model cannot be deleted until another is selected. |

**Not a secret store.** Model selection lives in the `app_config` table, which holds only non-secret runtime config. API keys for hosted providers are out of scope here and will use a separate encrypted key store.

## Vulnerability Reporting

Found a security issue? **Open a GitHub issue** on the repository.

This is a self-hosted, open-source project maintained on a best-effort basis. There is no dedicated security inbox or guaranteed response time. If a vulnerability is sensitive, describe the impact without posting a working exploit.

## Supply Chain Hygiene

- Python dependencies pinned with hashes (`pip-compile --generate-hashes`)
- Dependabot enabled on GitHub repo
- `pip-audit` runs in CI on every PR
- Docker base images pinned by digest, not tag
- No `curl | bash` instructions in any docs, ever

## Reviewing This Document

Re-read before:
- Adding a new adapter (does it handle secrets correctly?)
- Adding a new API endpoint (input validation in place?)
- Adding a new AI provider (data minimization considered?)
- Releasing a new version (controls matrix still accurate?)
- Open-sourcing the repo (threats and non-threats stated honestly?)
