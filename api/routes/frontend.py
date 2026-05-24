"""Frontend routes: serve HTML templates."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from adapters.storage.base import StorageProvider
from api.dependencies import get_storage
from core.models import Person

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["frontend"])


def _initials(name: str) -> str:
    """Get up to 2 initials from a name."""
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[0].upper() if name else "?"


_AVATAR_COLORS = [
    "bg-blue-500",
    "bg-green-500",
    "bg-purple-500",
    "bg-pink-500",
    "bg-yellow-500",
    "bg-red-500",
    "bg-indigo-500",
    "bg-teal-500",
]


def _avatar_color(name: str) -> str:
    """Deterministic color from name."""
    return _AVATAR_COLORS[sum(ord(c) for c in name) % len(_AVATAR_COLORS)]


async def _enrich_people(people: list[Person], storage: StorageProvider) -> list[dict]:
    """Add initials, avatar color, and last interaction date to people."""
    result = []
    for person in people:
        interactions = await storage.list_interactions_for_person(
            person.person_id, limit=1
        )
        last_interaction = interactions[0].date[:10] if interactions else None
        result.append(
            {
                "person": person,
                "initials": _initials(person.name),
                "avatar_color": _avatar_color(person.name),
                "last_interaction": last_interaction,
            }
        )
    return result


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
    people_data = await _enrich_people(people, storage)
    return templates.TemplateResponse(
        request,
        "people_list.html",
        {"active": "people", "people_data": people_data},
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
    people_data = await _enrich_people(people, storage)
    return templates.TemplateResponse(
        request,
        "people_search_results.html",
        {"people_data": people_data},
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
            "initials": _initials(person.name),
            "avatar_color": _avatar_color(person.name),
            "interactions": interactions,
            "open_loops": open_loops,
        },
    )


@router.get("/app/people/{person_id}/brief", response_class=HTMLResponse)
async def brief_page(
    request: Request,
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
):
    """Brief screen — shows history and generate button."""
    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    briefs = await storage.list_briefs_for_person(person_id)

    return templates.TemplateResponse(
        request,
        "brief.html",
        {
            "active": "people",
            "person_id": person_id,
            "person_name": person.name,
            "briefs": briefs,
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
