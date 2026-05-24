"""FastAPI application entry point.

Local: `uvicorn api.main:app --host 127.0.0.1 --port 8000`
Cloud (v1.1): wrapped by Mangum in deployments/aws/lambda_handler.py

Implementation: Phase 7 of BUILD_PLAN.md.
"""

# TODO (Phase 7): Build out the FastAPI app.
#
# Structure:
# - Load settings from config/settings.py
# - Build adapters using factories
# - Stash adapters in app.state for dependency injection
# - Mount route modules from api/routes/
# - Configure CORS using REMI_CORS_ORIGINS
# - Configure logging (structured, no PII)
# - Health check endpoint at /health (used by docker-compose healthcheck)
# - Serve frontend static files at / (Phase 8)
#
# Lifespan handler:
# - On startup: initialize() all adapters, log startup info (no secrets)
# - On shutdown: close() all adapters
#
# Security middleware:
# - Add security headers (Content-Security-Policy, X-Frame-Options, etc.)
# - Validate Content-Length against REMI_MAX_INPUT_LENGTH for text endpoints

from fastapi import FastAPI

app = FastAPI(
    title="REMI",
    description="Relationship Memory Intelligence",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check for Docker and load balancer probes."""
    return {"status": "ok"}


# TODO (Phase 7): Mount route modules
# from api.routes import people, interactions, loops, briefs
# app.include_router(interactions.router)
# app.include_router(people.router)
# app.include_router(loops.router)
# app.include_router(briefs.router)
