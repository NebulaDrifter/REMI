# REMI Local Deployment Dockerfile
#
# Multi-stage build: install deps, then copy app code.
# Runs as non-root user. Binds to localhost via docker-compose port mapping.

FROM python:3.12-slim AS builder

WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml ./
COPY core/ ./core/
COPY adapters/ ./adapters/
COPY api/ ./api/
COPY config/ ./config/

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install .

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

RUN groupadd --system --gid 1000 remi && \
    useradd --system --uid 1000 --gid remi --create-home remi

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY --chown=remi:remi . /app

RUN mkdir -p /app/data /app/audio_storage && \
    chown -R remi:remi /app/data /app/audio_storage && \
    chmod 700 /app/data /app/audio_storage

USER remi

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 0.0.0.0 is INSIDE the container. docker-compose maps 127.0.0.1
# on the host to this container port, so the host stays localhost-only.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
