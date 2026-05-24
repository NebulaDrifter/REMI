"""Frontend routes: serve HTML templates."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from adapters.ai.base import AIProvider, AIProviderError
from adapters.storage.base import StorageProvider
from api.dependencies import get_ai, get_storage
from core.prompts.retrieval import RETRIEVAL_SYSTEM_PROMPT, build_retrieval_prompt

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["frontend"])


@router.get("/", response_class=HTMLResponse)
async def capture_page(request: Request):
    """Capture screen — primary daily-use page."""
    return templates.TemplateResponse(request, "capture.html", {"active": "capture"})


@router.get("/app/people", response_class=HTMLResponse)
async def people_list_page(
    request: Request,
    storage: StorageProvider = Depends(get_storage),
):
    """People list screen."""
    people = await storage.list_people()
    return templates.TemplateResponse(
        request, "people_list.html", {"active": "people", "people": people}
    )


@router.get("/api/people/search-html", response_class=HTMLResponse)
async def people_search_html(
    request: Request,
    name: str = "",
    storage: StorageProvider = Depends(get_storage),
):
    """HTMX endpoint: return people search results as HTML fragment."""
    if name.strip():
        people = await storage.find_people_by_name(name)
    else:
        people = await storage.list_people()
    return templates.TemplateResponse(
        request, "people_search_results.html", {"people": people}
    )


@router.get("/app/people/{person_id}", response_class=HTMLResponse)
async def person_detail_page(
    request: Request,
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
):
    """Person detail screen."""
    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    interactions = await storage.list_interactions_for_person(person_id)
    loops = await storage.list_open_loops_for_person(person_id)
    open_loops = [lp for lp in loops if lp.status.value == "open"]

    return templates.TemplateResponse(
        request,
        "person_detail.html",
        {
            "active": "people",
            "person": person,
            "interactions": interactions,
            "open_loops": open_loops,
        },
    )


@router.get("/app/people/{person_id}/brief", response_class=HTMLResponse)
async def brief_page(
    request: Request,
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
    ai: AIProvider = Depends(get_ai),
):
    """Brief generation screen."""
    from api.routes.briefs import _build_person_summary

    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    interactions = await storage.list_interactions_for_person(person_id)
    loops = await storage.list_open_loops_for_person(person_id)
    summary = _build_person_summary(person, interactions, loops)
    user_prompt = build_retrieval_prompt(summary)

    try:
        brief = await ai.generate_text(
            system_prompt=RETRIEVAL_SYSTEM_PROMPT,
            user_input=user_prompt,
        )
    except AIProviderError as e:
        brief = f"Error generating brief: {e}"

    return templates.TemplateResponse(
        request,
        "brief.html",
        {
            "active": "people",
            "person_id": person_id,
            "person_name": person.name,
            "brief": brief,
        },
    )


@router.get("/app/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings screen — read-only view of current config."""
    settings = request.app.state.settings
    ai_model = ""
    if hasattr(settings, "anthropic_model"):
        ai_model = settings.anthropic_model
    if settings.ai_provider.value == "ollama":
        ai_model = settings.ollama_model

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "active": "settings",
            "version": "0.1.0",
            "deployment": settings.remi_deployment,
            "storage_backend": settings.storage_backend.value,
            "ai_provider": settings.ai_provider.value,
            "ai_model": ai_model,
            "blob_backend": settings.blob_backend.value,
            "transcription": settings.transcription_provider.value,
            "audio_retention_days": settings.audio_retention_days,
        },
    )
