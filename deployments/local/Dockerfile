# REMI Local Deployment Dockerfile
#
# Multi-stage build: install deps, then copy app code.
# Runs as non-root user. Binds to localhost via docker-compose port mapping.
#
# TODO (Phase 9): Refine this Dockerfile when the app is functional.

FROM python:3.12-slim AS builder

# Set up build environment
WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy dependency manifests
COPY pyproject.toml ./

# Install dependencies into a virtualenv
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -e .

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd --system --gid 1000 remi && \
    useradd --system --uid 1000 --gid remi --create-home remi

# Install only the runtime essentials
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set up app directory
WORKDIR /app
COPY --chown=remi:remi . /app

# Create data and audio dirs with correct perms
RUN mkdir -p /app/data /app/audio_storage && \
    chown -R remi:remi /app/data /app/audio_storage && \
    chmod 700 /app/data /app/audio_storage

# Switch to non-root user
USER remi

# Healthcheck (also defined in docker-compose.yml)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run with uvicorn — single worker is fine for personal use
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
# NOTE: 0.0.0.0 here is INSIDE the container. docker-compose maps 127.0.0.1
# on the host to this container port, so the host stays localhost-only.
