"""People routes: list, get, create."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from adapters.storage.base import NotFoundError, StorageProvider
from api.dependencies import get_storage
from core.models import AuditLogEntry, Person, RelationshipType

router = APIRouter(prefix="/people", tags=["people"])


class CreatePersonRequest(BaseModel):
    """Request body for POST /people."""

    name: str = Field(..., min_length=1, max_length=200)
    company: str | None = Field(None, max_length=200)
    relationship_type: RelationshipType
    tags: set[str] = Field(default_factory=set)
    pronunciation: str | None = Field(None, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=10_000)


@router.get("")
async def list_people(
    limit: int = 100,
    offset: int = 0,
    storage: StorageProvider = Depends(get_storage),
) -> list[Person]:
    """List all people with pagination."""
    return await storage.list_people(limit=limit, offset=offset)


@router.get("/search")
async def search_people(
    name: str,
    storage: StorageProvider = Depends(get_storage),
) -> list[Person]:
    """Search people by name (case-insensitive partial match)."""
    return await storage.find_people_by_name(name)


@router.get("/{person_id}")
async def get_person(
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
) -> Person:
    """Get a person by ID with all their data."""
    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.post("", status_code=201)
async def create_person(
    body: CreatePersonRequest,
    storage: StorageProvider = Depends(get_storage),
) -> Person:
    """Create a new person."""
    person = Person(
        name=body.name,
        name_lower=body.name.lower(),
        company=body.company,
        relationship_type=body.relationship_type,
        tags=body.tags,
        pronunciation=body.pronunciation,
        nickname=body.nickname,
        notes=body.notes,
    )
    created = await storage.create_person(person)

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="create_person",
            resource_id=created.person_id,
            source="api",
        )
    )

    return created


@router.patch("/{person_id}")
async def update_person(
    person_id: str,
    body: CreatePersonRequest,
    storage: StorageProvider = Depends(get_storage),
) -> Person:
    """Update an existing person."""
    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    person.name = body.name
    person.name_lower = body.name.lower()
    person.company = body.company
    person.relationship_type = body.relationship_type
    person.tags = body.tags
    person.pronunciation = body.pronunciation
    person.nickname = body.nickname
    person.notes = body.notes

    updated = await storage.update_person(person)

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="update_person",
            resource_id=person_id,
            source="api",
        )
    )

    return updated


@router.delete("/{person_id}", status_code=204)
async def delete_person(
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
) -> None:
    """Delete a person and all their data."""
    try:
        await storage.delete_person(person_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Person not found") from e

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="delete_person",
            resource_id=person_id,
            source="api",
        )
    )
