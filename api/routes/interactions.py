"""Interaction routes: submit text, submit audio."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from adapters.ai.base import AIProvider, AIProviderError
from adapters.blob.base import BlobProvider
from adapters.storage.base import StorageProvider
from adapters.transcription.base import TranscriptionProvider
from api.dependencies import get_ai, get_blob, get_storage, get_transcription
from core.models import (
    AuditLogEntry,
    ExtractionResult,
    IngestResponse,
    Interaction,
    OpenLoop,
    PersonResolution,
    PersonResolutionStatus,
)
from core.prompts.extraction import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interactions", tags=["interactions"])


class TextInteractionRequest(BaseModel):
    """Request body for POST /interactions/text."""

    raw_input: str = Field(..., min_length=1, max_length=50_000)
    date: str | None = None


class ConfirmSaveRequest(BaseModel):
    """Request body for POST /interactions/confirm."""

    person_id: str
    extraction: ExtractionResult
    date: str | None = None


async def _resolve_person(name: str, storage: StorageProvider) -> PersonResolution:
    """Try to match an extracted person name to existing people."""
    candidates = await storage.find_people_by_name(name)

    if len(candidates) == 1:
        return PersonResolution(
            status=PersonResolutionStatus.MATCHED,
            matched_person=candidates[0],
        )
    elif len(candidates) > 1:
        return PersonResolution(
            status=PersonResolutionStatus.AMBIGUOUS,
            candidates=candidates,
        )
    else:
        return PersonResolution(
            status=PersonResolutionStatus.NEEDS_CLARIFICATION,
            missing=["last_name", "context"],
        )


async def _extract(raw_input: str, ai: AIProvider) -> ExtractionResult:
    """Run AI extraction on raw input."""
    user_prompt = build_extraction_prompt(raw_input)
    return await ai.extract_structured(
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_input=user_prompt,
        response_model=ExtractionResult,
    )


@router.post("/text")
async def submit_text(
    body: TextInteractionRequest,
    storage: StorageProvider = Depends(get_storage),
    ai: AIProvider = Depends(get_ai),
) -> IngestResponse:
    """Submit a text note for extraction."""
    try:
        extraction = await _extract(body.raw_input, ai)
    except AIProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    resolution = await _resolve_person(extraction.person_name, storage)

    return IngestResponse(
        extraction=extraction,
        person_resolution=resolution,
    )


@router.post("/audio")
async def submit_audio(
    file: UploadFile,
    storage: StorageProvider = Depends(get_storage),
    ai: AIProvider = Depends(get_ai),
    blob: BlobProvider = Depends(get_blob),
    transcription: TranscriptionProvider = Depends(get_transcription),
) -> IngestResponse:
    """Submit an audio file for transcription and extraction."""
    content = await file.read()
    timestamp = datetime.now(UTC).strftime("%Y/%m/%d")
    key = f"audio/{timestamp}/{file.filename}"

    await blob.write(key, content)
    local_path = await blob.get_local_path(key)
    transcript = await transcription.transcribe(local_path)

    try:
        extraction = await _extract(transcript, ai)
    except AIProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    resolution = await _resolve_person(extraction.person_name, storage)

    return IngestResponse(
        extraction=extraction,
        person_resolution=resolution,
    )


@router.post("/confirm", status_code=201)
async def confirm_save(
    body: ConfirmSaveRequest,
    storage: StorageProvider = Depends(get_storage),
) -> dict:
    """Save a confirmed extraction as an interaction + loops."""
    person = await storage.get_person(body.person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    interaction_date = body.date or datetime.now(UTC).isoformat()

    interaction = Interaction(
        person_id=body.person_id,
        date=interaction_date,
        interaction_type=body.extraction.interaction_type,
        raw_input=body.extraction.summary,
        extracted_summary=body.extraction.summary,
        facts=body.extraction.facts,
        tags_added=body.extraction.tags_added,
    )
    await storage.create_interaction(interaction)

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="create_interaction",
            resource_id=interaction.interaction_id,
            source="api",
        )
    )

    if body.extraction.tags_added:
        person.tags.update(body.extraction.tags_added)
        await storage.update_person(person)

    loop_ids = []
    for extracted_loop in body.extraction.loops:
        loop = OpenLoop(
            person_id=body.person_id,
            description=extracted_loop.description,
            due_date=extracted_loop.due_date,
            source_interaction_id=interaction.interaction_id,
        )
        await storage.create_open_loop(loop)
        loop_ids.append(loop.loop_id)

        await storage.write_audit_entry(
            AuditLogEntry(
                actor="single_user_mode",
                action="create_open_loop",
                resource_id=loop.loop_id,
                source="api",
            )
        )

    return {
        "interaction_id": interaction.interaction_id,
        "loop_ids": loop_ids,
    }


@router.get("/{person_id}")
async def list_interactions(
    person_id: str,
    limit: int = 100,
    storage: StorageProvider = Depends(get_storage),
) -> list[Interaction]:
    """List interactions for a person, newest first."""
    return await storage.list_interactions_for_person(person_id, limit=limit)
