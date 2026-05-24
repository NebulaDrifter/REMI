"""Brief generation route."""

from fastapi import APIRouter, Depends, HTTPException

from adapters.ai.base import AIProvider, AIProviderError
from adapters.storage.base import StorageProvider
from api.dependencies import get_ai, get_storage
from core.models import AuditLogEntry, Brief, Person
from core.prompts.retrieval import RETRIEVAL_SYSTEM_PROMPT, build_retrieval_prompt

router = APIRouter(tags=["briefs"])


def _build_person_summary(
    person: Person,
    interactions: list,
    loops: list,
) -> str:
    """Format person data into a text summary for the retrieval prompt."""
    parts = [
        f"Name: {person.name}",
        f"Relationship: {person.relationship_type.value}",
    ]
    if person.company:
        parts.append(f"Company: {person.company}")
    if person.tags:
        parts.append(f"Tags: {', '.join(sorted(person.tags))}")
    if person.notes:
        parts.append(f"Notes: {person.notes}")

    parts.append(f"\nInteractions ({len(interactions)} total):")
    for ix in interactions[:20]:
        line = f"- [{ix.date}] ({ix.interaction_type.value}) {ix.extracted_summary}"
        parts.append(line)
        if ix.facts:
            for fact in ix.facts:
                parts.append(f"  Fact ({fact.category.value}): {fact.content}")

    open_loops = [lp for lp in loops if lp.status.value == "open"]
    closed_loops = [lp for lp in loops if lp.status.value != "open"]
    parts.append(f"\nOpen loops ({len(open_loops)}):")
    for lp in open_loops:
        due = f" (due: {lp.due_date})" if lp.due_date else ""
        parts.append(f"- {lp.description}{due}")

    if closed_loops:
        parts.append(f"\nClosed loops ({len(closed_loops)}):")
        for lp in closed_loops:
            parts.append(f"- [{lp.status.value}] {lp.description}")

    return "\n".join(parts)


@router.post("/people/{person_id}/brief")
async def generate_brief(
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
    ai: AIProvider = Depends(get_ai),
) -> dict:
    """Generate a pre-meeting brief and store it."""
    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    interactions = await storage.list_interactions_for_person(person_id)
    loops = await storage.list_open_loops_for_person(person_id)

    summary = _build_person_summary(person, interactions, loops)
    user_prompt = build_retrieval_prompt(summary)

    try:
        brief_text = await ai.generate_text(
            system_prompt=RETRIEVAL_SYSTEM_PROMPT,
            user_input=user_prompt,
        )
    except AIProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    brief = Brief(person_id=person_id, brief_text=brief_text)
    await storage.create_brief(brief)

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="generate_brief",
            resource_id=brief.brief_id,
            source="api",
        )
    )

    return {
        "person_id": person_id,
        "person_name": person.name,
        "brief": brief_text,
        "brief_id": brief.brief_id,
        "generated_at": brief.generated_at,
    }


@router.get("/people/{person_id}/briefs")
async def list_briefs(
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
) -> list[Brief]:
    """List previously generated briefs for a person."""
    return await storage.list_briefs_for_person(person_id)
