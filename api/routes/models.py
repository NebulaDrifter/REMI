"""Local model management routes (Ollama).

List, pull, delete, and hot-swap the active local model from the web UI.

Scope: these endpoints only work when ``AI_PROVIDER=ollama``. When another
provider is active they return 409 — managing local models would be a no-op.

Hot-swap: setting the active model rebuilds the inference adapter live and
swaps it on ``app.state.ai``. No restart. The choice is persisted to the
``app_config`` store so it survives the next startup.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from adapters.ai.base import AIProviderError
from adapters.ai.ollama import OllamaAI
from adapters.ai.ollama_manager import (
    SUGGESTED_MODELS,
    OllamaManager,
    OllamaModel,
    PullProgress,
)
from adapters.storage.base import StorageProvider
from api.dependencies import get_storage
from core.models import AuditLogEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])

# Key under which the active local model is persisted in app_config.
ACTIVE_MODEL_KEY = "ollama_active_model"

# Allowed characters in a model reference. Covers Ollama names (llama3.1:8b)
# and Hugging Face GGUF refs (hf.co/user/repo:quant). Keeps arbitrary input
# out of the pull/delete calls.
_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,200}$"


class ModelName(BaseModel):
    """A validated model reference."""

    name: str = Field(..., pattern=_NAME_PATTERN)


class ModelsResponse(BaseModel):
    """Current model state for the Settings panel."""

    active: str
    installed: list[OllamaModel]
    suggested: list[str]


def get_manager(request: Request) -> OllamaManager:
    """Return the Ollama manager, or 409 if Ollama isn't the active provider."""
    manager = getattr(request.app.state, "ollama_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=409,
            detail="Local model management requires AI_PROVIDER=ollama.",
        )
    return manager


def _pull_jobs(request: Request) -> dict[str, PullProgress]:
    """In-memory registry of active/finished pulls, keyed by model name."""
    jobs = getattr(request.app.state, "pull_jobs", None)
    if jobs is None:
        jobs = {}
        request.app.state.pull_jobs = jobs
    return jobs


@router.get("")
async def list_models(
    request: Request,
    manager: OllamaManager = Depends(get_manager),
) -> ModelsResponse:
    """List installed models, the active one, and suggested starters."""
    installed = await manager.list_models()
    active = getattr(request.app.state.ai, "model", "")
    return ModelsResponse(
        active=active, installed=installed, suggested=SUGGESTED_MODELS
    )


async def _run_pull(
    manager: OllamaManager, name: str, jobs: dict[str, PullProgress]
) -> None:
    """Consume a streaming pull, recording the latest progress in ``jobs``."""
    try:
        async for progress in manager.pull_model(name):
            jobs[name] = progress
    except AIProviderError as e:
        jobs[name] = PullProgress(status="error", error=str(e), done=True)
    except Exception as e:  # noqa: BLE001 — surface any failure to the poller
        logger.exception("Unexpected error pulling model %s", name)
        jobs[name] = PullProgress(status="error", error=str(e), done=True)


@router.post("/pull", status_code=202)
async def pull_model(
    request: Request,
    body: ModelName,
    manager: OllamaManager = Depends(get_manager),
    storage: StorageProvider = Depends(get_storage),
) -> dict[str, str]:
    """Start pulling a model in the background. Poll /pull/status for progress."""
    jobs = _pull_jobs(request)
    existing = jobs.get(body.name)
    if existing and not existing.done:
        raise HTTPException(status_code=409, detail="This model is already pulling.")

    jobs[body.name] = PullProgress(status="starting")
    asyncio.create_task(_run_pull(manager, body.name, jobs))  # noqa: RUF006

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="pull_model",
            resource_id=body.name,
            source="api",
        )
    )
    return {"status": "started", "name": body.name}


@router.get("/pull/status")
async def pull_status(
    request: Request,
    name: str,
) -> PullProgress:
    """Return the latest progress for an in-flight or finished pull."""
    jobs = _pull_jobs(request)
    progress = jobs.get(name)
    if progress is None:
        raise HTTPException(status_code=404, detail="No pull found for that model.")
    return progress


@router.post("/active")
async def set_active_model(
    request: Request,
    body: ModelName,
    manager: OllamaManager = Depends(get_manager),
    storage: StorageProvider = Depends(get_storage),
) -> dict[str, str]:
    """Hot-swap the active local model. Rebuilds the inference adapter live."""
    installed = {m.name for m in await manager.list_models()}
    if body.name not in installed:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{body.name}' is not installed. Pull it first.",
        )

    old_ai = request.app.state.ai
    request.app.state.ai = OllamaAI(base_url=manager.base_url, model=body.name)

    # Close the old client now that nothing new will use it. Single-user app,
    # so no in-flight request races this swap.
    if isinstance(old_ai, OllamaAI):
        try:
            await old_ai.aclose()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            logger.warning("Failed to close previous Ollama client", exc_info=True)

    await storage.set_app_config(ACTIVE_MODEL_KEY, body.name)
    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="set_active_model",
            resource_id=body.name,
            source="api",
        )
    )
    logger.info("Hot-swapped active model to %s", body.name)
    return {"status": "active", "name": body.name}


@router.delete("/{name:path}")
async def delete_model(
    request: Request,
    name: str,
    manager: OllamaManager = Depends(get_manager),
    storage: StorageProvider = Depends(get_storage),
) -> dict[str, str]:
    """Delete an installed model. Refuses to delete the active model."""
    active = getattr(request.app.state.ai, "model", "")
    if name == active:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete the active model. Switch to another first.",
        )

    try:
        await manager.delete_model(name)
    except AIProviderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="delete_model",
            resource_id=name,
            source="api",
        )
    )
    return {"status": "deleted", "name": name}
