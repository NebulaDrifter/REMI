"""FastAPI application entry point.

Local: `uvicorn api.main:app --host 127.0.0.1 --port 8000`
Cloud (v1.1): wrapped by Mangum in deployments/aws/lambda_handler.py
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import (
    briefs,
    frontend,
    interactions,
    loops,
    models,
    people,
    reminders,
)
from api.routes.models import ACTIVE_MODEL_KEY
from config.settings import (
    AIProviderType,
    Settings,
    build_ai,
    build_blob,
    build_storage,
    build_transcription,
)
from core.version import VERSION

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize adapters on startup, close on shutdown."""
    settings = Settings()

    logging.basicConfig(
        level=getattr(logging, settings.remi_log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    storage = build_storage(settings)
    await storage.initialize()
    application.state.storage = storage

    blob = build_blob(settings)
    await blob.initialize()
    application.state.blob = blob

    # For local models, restore the last hot-swapped model from app_config so
    # the choice survives restarts. Static config still comes from .env.
    application.state.ollama_manager = None
    application.state.pull_jobs = {}
    if settings.ai_provider == AIProviderType.OLLAMA:
        from adapters.ai.ollama_manager import OllamaManager

        stored_model = await storage.get_app_config(ACTIVE_MODEL_KEY)
        if stored_model:
            settings.ollama_model = stored_model
        application.state.ollama_manager = OllamaManager(
            base_url=settings.ollama_base_url
        )

    application.state.ai = build_ai(settings)
    application.state.transcription = build_transcription(settings)
    application.state.settings = settings

    logger.info(
        "REMI started: storage=%s ai=%s blob=%s",
        settings.storage_backend.value,
        settings.ai_provider.value,
        settings.blob_backend.value,
    )

    yield

    if application.state.ollama_manager is not None:
        await application.state.ollama_manager.aclose()
    await storage.close()
    logger.info("REMI shut down")


app = FastAPI(
    title="REMI",
    description="Relationship Memory Intelligence",
    version=VERSION,
    lifespan=lifespan,
)


def configure_cors(application: FastAPI, settings: Settings | None = None) -> None:
    """Configure CORS middleware."""
    if settings is None:
        origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
    else:
        origins = settings.get_cors_origins()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


configure_cors(app)

app.include_router(people.router)
app.include_router(interactions.router)
app.include_router(loops.router)
app.include_router(briefs.router)
app.include_router(reminders.router)
app.include_router(models.router)
app.include_router(frontend.router)

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check for Docker and load balancer probes."""
    return {"status": "ok"}
