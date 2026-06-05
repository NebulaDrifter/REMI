# Local Deployment

Default deployment target for v1.0. Single Docker Compose stack on your machine.

## Quick Start

```bash
# 1. Copy and edit env vars
cp .env.example .env
# Set ANTHROPIC_API_KEY (or use Ollama — see below)

# 2. Start
docker compose up

# 3. Open
open http://localhost:8000
```

## Configuration

All config via `.env`. See `.env.example` for the full list with comments.

**Key choices:**

| Setting | Default | Options |
|---|---|---|
| `STORAGE_BACKEND` | `sqlite` | `sqlite` (v1.0), `dynamodb` (v1.1) |
| `AI_PROVIDER` | `anthropic` | `anthropic`, `ollama` |
| `TRANSCRIPTION_PROVIDER` | `whisper_api` | `whisper_api` |
| `BLOB_BACKEND` | `filesystem` | `filesystem` |
| `REMI_HOST` | `127.0.0.1` | leave as-is unless you understand the security implications |

## Using Ollama (Local AI)

Run REMI without sending data to any external AI provider. Two ways to do it.

### Option A — Bundled container (default)

REMI ships its own Ollama container. Nothing extra to install.

1. Set in `.env`:
   ```
   AI_PROVIDER=ollama
   OLLAMA_MODEL=llama3.1:8b
   ```
   Leave `OLLAMA_BASE_URL` unset — Compose points it at the internal container.
2. Start: `docker compose up`
3. Pull a model from the Settings screen (or:
   `docker compose exec ollama ollama pull llama3.1:8b`).

Models persist in `./ollama_data`.

### Option B — Your host's existing Ollama

Already run Ollama on your machine with models downloaded? Connect to it
instead of pulling a second copy.

1. Set in `.env`:
   ```
   AI_PROVIDER=ollama
   OLLAMA_MODEL=llama3.1:8b   # a model you already have
   ```
   Leave `OLLAMA_BASE_URL` unset — the override below sets it.
2. Start with both compose files:
   ```
   docker compose -f docker-compose.yml -f docker-compose.host-ollama.yml up
   ```

This connects to `http://host.docker.internal:11434`, skips the bundled
container, and reuses your existing models. Model management from the Settings
screen then operates on your host's Ollama.

Note: smaller local models may struggle with structured output reliability.
Test the extraction flow before relying on it.

## Data Persistence

Docker Compose mounts two volumes:
- `./data/` → SQLite database file
- `./audio_storage/` → Audio file blobs

Both persist across container restarts. Back them up regularly.

## Security

See `SECURITY.md` in the project root for the full threat model. Local-specific
controls:

- App binds to `127.0.0.1` only (via docker-compose port mapping). No network exposure by default.
- `.env` file should be `chmod 600`.
- Data and audio directories are `chmod 700` inside the container.
- App runs as non-root user (uid 1000).
- Container drops all Linux capabilities and disables privilege escalation.

If you intend to expose REMI on a home network:
1. Put a reverse proxy (Caddy, Traefik) in front with TLS
2. Set `REMI_API_KEY` and enable auth
3. Lock `REMI_CORS_ORIGINS` to your frontend origin
4. Re-read SECURITY.md
