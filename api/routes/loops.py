"""Open loop routes: create, update status."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from adapters.storage.base import NotFoundError, StorageProvider
from api.dependencies import get_storage
from core.models import AuditLogEntry, LoopStatus, OpenLoop

router = APIRouter(tags=["loops"])


class CreateLoopRequest(BaseModel):
    """Request body for POST /people/{id}/loops."""

    description: str = Field(..., min_length=1, max_length=1000)
    due_date: str | None = None


class UpdateLoopRequest(BaseModel):
    """Request body for PATCH /loops/{loop_id}."""

    status: LoopStatus
    description: str | None = Field(None, max_length=1000)
    due_date: str | None = None


@router.post("/people/{person_id}/loops", status_code=201)
async def create_loop(
    person_id: str,
    body: CreateLoopRequest,
    storage: StorageProvider = Depends(get_storage),
) -> OpenLoop:
    """Manually create an open loop for a person."""
    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    loop = OpenLoop(
        person_id=person_id,
        description=body.description,
        due_date=body.due_date,
    )
    created = await storage.create_open_loop(loop)

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="create_open_loop",
            resource_id=created.loop_id,
            source="api",
        )
    )

    return created


@router.patch("/loops/{person_id}/{loop_id}")
async def update_loop(
    person_id: str,
    loop_id: str,
    body: UpdateLoopRequest,
    storage: StorageProvider = Depends(get_storage),
) -> OpenLoop:
    """Update an open loop's status or details."""
    loop = await storage.get_open_loop(person_id, loop_id)
    if not loop:
        raise HTTPException(status_code=404, detail="Loop not found")

    loop.status = body.status
    if body.description is not None:
        loop.description = body.description
    if body.due_date is not None:
        loop.due_date = body.due_date

    try:
        updated = await storage.update_open_loop(loop)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Loop not found") from e

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="update_open_loop",
            resource_id=loop_id,
            source="api",
        )
    )

    return updated


@router.get("/people/{person_id}/loops")
async def list_loops(
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
) -> list[OpenLoop]:
    """List all open loops for a person."""
    return await storage.list_open_loops_for_person(person_id)
