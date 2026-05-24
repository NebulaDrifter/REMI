"""Reminder routes: create, list, dismiss."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from adapters.storage.base import NotFoundError, StorageProvider
from api.dependencies import get_storage
from core.models import (
    AuditLogEntry,
    Reminder,
    ReminderRecurrence,
    UpcomingReminder,
)

router = APIRouter(tags=["reminders"])


class CreateReminderRequest(BaseModel):
    """Request body for POST /people/{id}/reminders."""

    title: str = Field(..., min_length=1, max_length=500)
    date: str
    recurrence: ReminderRecurrence


@router.post("/people/{person_id}/reminders", status_code=201)
async def create_reminder(
    person_id: str,
    body: CreateReminderRequest,
    storage: StorageProvider = Depends(get_storage),
) -> Reminder:
    """Manually create a reminder for a person."""
    person = await storage.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    reminder = Reminder(
        person_id=person_id,
        title=body.title,
        date=body.date,
        recurrence=body.recurrence,
    )
    created = await storage.create_reminder(reminder)

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="create_reminder",
            resource_id=created.reminder_id,
            source="api",
        )
    )

    return created


@router.get("/people/{person_id}/reminders")
async def list_reminders(
    person_id: str,
    storage: StorageProvider = Depends(get_storage),
) -> list[Reminder]:
    """List all reminders for a person."""
    return await storage.list_reminders_for_person(person_id)


@router.patch("/reminders/{person_id}/{reminder_id}/dismiss")
async def dismiss_reminder(
    person_id: str,
    reminder_id: str,
    storage: StorageProvider = Depends(get_storage),
) -> Reminder:
    """Dismiss a reminder."""
    try:
        reminder = await storage.dismiss_reminder(person_id, reminder_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Reminder not found") from e

    await storage.write_audit_entry(
        AuditLogEntry(
            actor="single_user_mode",
            action="dismiss_reminder",
            resource_id=reminder_id,
            source="api",
        )
    )

    return reminder


@router.get("/api/reminders/upcoming")
async def upcoming_reminders(
    days: int = 7,
    storage: StorageProvider = Depends(get_storage),
) -> list[UpcomingReminder]:
    """List upcoming reminders across all people."""
    return await storage.list_upcoming_reminders(days=days)
