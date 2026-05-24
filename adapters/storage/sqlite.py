"""SQLite storage adapter.

Local-deployment implementation of StorageProvider. Uses the schema documented
in DATA_MODEL.md "SQLite Schema" section.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from adapters.storage.base import AlreadyExistsError, NotFoundError, StorageProvider
from core.models import (
    AuditLogEntry,
    Brief,
    Fact,
    FactCategory,
    Interaction,
    InteractionType,
    LoopStatus,
    OpenLoop,
    Person,
    RelationshipType,
    Reminder,
    ReminderRecurrence,
    ReminderStatus,
    UpcomingReminder,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    person_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_lower TEXT NOT NULL,
    company TEXT,
    relationship_type TEXT NOT NULL,
    tags TEXT,
    pronunciation TEXT,
    nickname TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_people_name_lower ON people(name_lower);

CREATE TABLE IF NOT EXISTS interactions (
    person_id TEXT NOT NULL,
    interaction_id TEXT NOT NULL,
    date TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    raw_input TEXT NOT NULL,
    raw_transcript TEXT,
    audio_blob_key TEXT,
    extracted_summary TEXT NOT NULL,
    facts TEXT,
    tags_added TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (person_id, interaction_id),
    FOREIGN KEY (person_id) REFERENCES people(person_id)
);

CREATE TABLE IF NOT EXISTS open_loops (
    person_id TEXT NOT NULL,
    loop_id TEXT NOT NULL,
    description TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL,
    source_interaction_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at TEXT,
    PRIMARY KEY (person_id, loop_id),
    FOREIGN KEY (person_id) REFERENCES people(person_id)
);
CREATE INDEX IF NOT EXISTS idx_loops_status_due ON open_loops(status, due_date);

CREATE TABLE IF NOT EXISTS briefs (
    person_id TEXT NOT NULL,
    brief_id TEXT NOT NULL,
    brief_text TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (person_id, brief_id),
    FOREIGN KEY (person_id) REFERENCES people(person_id)
);

CREATE TABLE IF NOT EXISTS reminders (
    person_id TEXT NOT NULL,
    reminder_id TEXT NOT NULL,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    recurrence TEXT NOT NULL,
    status TEXT NOT NULL,
    source_interaction_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (person_id, reminder_id),
    FOREIGN KEY (person_id) REFERENCES people(person_id)
);
CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(date);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _tags_to_json(tags: set[str]) -> str:
    return json.dumps(sorted(tags))


def _json_to_tags(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return set(json.loads(raw))


def _facts_to_json(facts: list[Fact]) -> str:
    return json.dumps(
        [{"category": f.category.value, "content": f.content} for f in facts]
    )


def _json_to_facts(raw: str | None) -> list[Fact]:
    if not raw:
        return []
    return [
        Fact(category=FactCategory(f["category"]), content=f["content"])
        for f in json.loads(raw)
    ]


def _json_to_str_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return json.loads(raw)


def _row_to_person(row: aiosqlite.Row) -> Person:
    return Person(
        person_id=row["person_id"],
        name=row["name"],
        name_lower=row["name_lower"],
        company=row["company"],
        relationship_type=RelationshipType(row["relationship_type"]),
        tags=_json_to_tags(row["tags"]),
        pronunciation=row["pronunciation"],
        nickname=row["nickname"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_interaction(row: aiosqlite.Row) -> Interaction:
    return Interaction(
        person_id=row["person_id"],
        interaction_id=row["interaction_id"],
        date=row["date"],
        interaction_type=InteractionType(row["interaction_type"]),
        raw_input=row["raw_input"],
        raw_transcript=row["raw_transcript"],
        audio_blob_key=row["audio_blob_key"],
        extracted_summary=row["extracted_summary"],
        facts=_json_to_facts(row["facts"]),
        tags_added=_json_to_str_list(row["tags_added"]),
        created_at=row["created_at"],
    )


def _row_to_open_loop(row: aiosqlite.Row) -> OpenLoop:
    return OpenLoop(
        person_id=row["person_id"],
        loop_id=row["loop_id"],
        description=row["description"],
        due_date=row["due_date"],
        status=LoopStatus(row["status"]),
        source_interaction_id=row["source_interaction_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        closed_at=row["closed_at"],
    )


def _row_to_reminder(row: aiosqlite.Row) -> Reminder:
    return Reminder(
        person_id=row["person_id"],
        reminder_id=row["reminder_id"],
        title=row["title"],
        date=row["date"],
        recurrence=ReminderRecurrence(row["recurrence"]),
        status=ReminderStatus(row["status"]),
        source_interaction_id=row["source_interaction_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_audit_entry(row: aiosqlite.Row) -> AuditLogEntry:
    return AuditLogEntry(
        audit_id=row["audit_id"],
        actor=row["actor"],
        action=row["action"],
        resource_id=row["resource_id"],
        timestamp=row["timestamp"],
        source=row["source"],
    )


class SQLiteStorage(StorageProvider):
    """SQLite implementation of StorageProvider."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        return self._db

    async def initialize(self) -> None:
        """Create tables and enable foreign keys."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.execute("PRAGMA journal_mode = WAL")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    # ----- People -----

    async def create_person(self, person: Person) -> Person:
        db = await self._get_db()
        try:
            await db.execute(
                """INSERT INTO people
                   (person_id, name, name_lower, company, relationship_type,
                    tags, pronunciation, nickname, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    person.person_id,
                    person.name,
                    person.name_lower,
                    person.company,
                    person.relationship_type.value,
                    _tags_to_json(person.tags),
                    person.pronunciation,
                    person.nickname,
                    person.notes,
                    person.created_at,
                    person.updated_at,
                ),
            )
            await db.commit()
        except aiosqlite.IntegrityError as e:
            raise AlreadyExistsError(f"Person {person.person_id} already exists") from e
        return person

    async def get_person(self, person_id: str) -> Person | None:
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM people WHERE person_id = ?", (person_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_person(row) if row else None

    async def find_people_by_name(self, name: str) -> list[Person]:
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM people WHERE name_lower LIKE ?",
            (f"%{name.lower()}%",),
        ) as cursor:
            return [_row_to_person(row) async for row in cursor]

    async def list_people(self, limit: int = 100, offset: int = 0) -> list[Person]:
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM people ORDER BY name_lower LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cursor:
            return [_row_to_person(row) async for row in cursor]

    async def update_person(self, person: Person) -> Person:
        db = await self._get_db()
        person.updated_at = _now()
        result = await db.execute(
            """UPDATE people SET
               name = ?, name_lower = ?, company = ?, relationship_type = ?,
               tags = ?, pronunciation = ?, nickname = ?, notes = ?, updated_at = ?
               WHERE person_id = ?""",
            (
                person.name,
                person.name_lower,
                person.company,
                person.relationship_type.value,
                _tags_to_json(person.tags),
                person.pronunciation,
                person.nickname,
                person.notes,
                person.updated_at,
                person.person_id,
            ),
        )
        if result.rowcount == 0:
            raise NotFoundError(f"Person {person.person_id} not found")
        await db.commit()
        return person

    async def delete_person(self, person_id: str) -> None:
        db = await self._get_db()
        existing = await self.get_person(person_id)
        if not existing:
            raise NotFoundError(f"Person {person_id} not found")
        await db.execute("DELETE FROM reminders WHERE person_id = ?", (person_id,))
        await db.execute("DELETE FROM open_loops WHERE person_id = ?", (person_id,))
        await db.execute("DELETE FROM interactions WHERE person_id = ?", (person_id,))
        await db.execute("DELETE FROM people WHERE person_id = ?", (person_id,))
        await db.commit()

    # ----- Interactions -----

    async def create_interaction(self, interaction: Interaction) -> Interaction:
        db = await self._get_db()
        await db.execute(
            """INSERT INTO interactions
               (person_id, interaction_id, date, interaction_type, raw_input,
                raw_transcript, audio_blob_key, extracted_summary, facts,
                tags_added, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                interaction.person_id,
                interaction.interaction_id,
                interaction.date,
                interaction.interaction_type.value,
                interaction.raw_input,
                interaction.raw_transcript,
                interaction.audio_blob_key,
                interaction.extracted_summary,
                _facts_to_json(interaction.facts),
                json.dumps(interaction.tags_added),
                interaction.created_at,
            ),
        )
        await db.commit()
        return interaction

    async def get_interaction(
        self, person_id: str, interaction_id: str
    ) -> Interaction | None:
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM interactions WHERE person_id = ? AND interaction_id = ?",
            (person_id, interaction_id),
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_interaction(row) if row else None

    async def list_interactions_for_person(
        self, person_id: str, limit: int = 100
    ) -> list[Interaction]:
        db = await self._get_db()
        async with db.execute(
            """SELECT * FROM interactions
               WHERE person_id = ?
               ORDER BY interaction_id DESC
               LIMIT ?""",
            (person_id, limit),
        ) as cursor:
            return [_row_to_interaction(row) async for row in cursor]

    # ----- Open Loops -----

    async def create_open_loop(self, loop: OpenLoop) -> OpenLoop:
        db = await self._get_db()
        await db.execute(
            """INSERT INTO open_loops
               (person_id, loop_id, description, due_date, status,
                source_interaction_id, created_at, updated_at, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                loop.person_id,
                loop.loop_id,
                loop.description,
                loop.due_date,
                loop.status.value,
                loop.source_interaction_id,
                loop.created_at,
                loop.updated_at,
                loop.closed_at,
            ),
        )
        await db.commit()
        return loop

    async def get_open_loop(self, person_id: str, loop_id: str) -> OpenLoop | None:
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM open_loops WHERE person_id = ? AND loop_id = ?",
            (person_id, loop_id),
        ) as cursor:
            row = await cursor.fetchone()
            return _row_to_open_loop(row) if row else None

    async def list_open_loops_for_person(self, person_id: str) -> list[OpenLoop]:
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM open_loops WHERE person_id = ? ORDER BY loop_id DESC",
            (person_id,),
        ) as cursor:
            return [_row_to_open_loop(row) async for row in cursor]

    async def list_open_loops_by_status(
        self,
        status: LoopStatus,
        due_before: str | None = None,
        limit: int = 100,
    ) -> list[OpenLoop]:
        db = await self._get_db()
        if due_before:
            async with db.execute(
                """SELECT * FROM open_loops
                   WHERE status = ? AND due_date IS NOT NULL AND due_date <= ?
                   ORDER BY due_date
                   LIMIT ?""",
                (status.value, due_before, limit),
            ) as cursor:
                return [_row_to_open_loop(row) async for row in cursor]
        else:
            async with db.execute(
                """SELECT * FROM open_loops
                   WHERE status = ?
                   ORDER BY loop_id DESC
                   LIMIT ?""",
                (status.value, limit),
            ) as cursor:
                return [_row_to_open_loop(row) async for row in cursor]

    async def update_open_loop(self, loop: OpenLoop) -> OpenLoop:
        db = await self._get_db()
        loop.updated_at = _now()
        if loop.status in (LoopStatus.DONE, LoopStatus.DROPPED) and not loop.closed_at:
            loop.closed_at = _now()
        result = await db.execute(
            """UPDATE open_loops SET
               description = ?, due_date = ?, status = ?,
               source_interaction_id = ?, updated_at = ?, closed_at = ?
               WHERE person_id = ? AND loop_id = ?""",
            (
                loop.description,
                loop.due_date,
                loop.status.value,
                loop.source_interaction_id,
                loop.updated_at,
                loop.closed_at,
                loop.person_id,
                loop.loop_id,
            ),
        )
        if result.rowcount == 0:
            raise NotFoundError(
                f"OpenLoop {loop.loop_id} for person {loop.person_id} not found"
            )
        await db.commit()
        return loop

    # ----- Briefs -----

    async def create_brief(self, brief: Brief) -> Brief:
        db = await self._get_db()
        await db.execute(
            """INSERT INTO briefs
               (person_id, brief_id, brief_text, generated_at)
               VALUES (?, ?, ?, ?)""",
            (
                brief.person_id,
                brief.brief_id,
                brief.brief_text,
                brief.generated_at,
            ),
        )
        await db.commit()
        return brief

    async def list_briefs_for_person(
        self, person_id: str, limit: int = 20
    ) -> list[Brief]:
        db = await self._get_db()
        async with db.execute(
            """SELECT * FROM briefs
               WHERE person_id = ?
               ORDER BY brief_id DESC
               LIMIT ?""",
            (person_id, limit),
        ) as cursor:
            return [
                Brief(
                    person_id=row["person_id"],
                    brief_id=row["brief_id"],
                    brief_text=row["brief_text"],
                    generated_at=row["generated_at"],
                )
                async for row in cursor
            ]

    # ----- Reminders -----

    async def create_reminder(self, reminder: Reminder) -> Reminder:
        db = await self._get_db()
        await db.execute(
            """INSERT INTO reminders
               (person_id, reminder_id, title, date, recurrence, status,
                source_interaction_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                reminder.person_id,
                reminder.reminder_id,
                reminder.title,
                reminder.date,
                reminder.recurrence.value,
                reminder.status.value,
                reminder.source_interaction_id,
                reminder.created_at,
                reminder.updated_at,
            ),
        )
        await db.commit()
        return reminder

    async def list_reminders_for_person(self, person_id: str) -> list[Reminder]:
        db = await self._get_db()
        async with db.execute(
            """SELECT * FROM reminders
               WHERE person_id = ?
               ORDER BY date""",
            (person_id,),
        ) as cursor:
            return [_row_to_reminder(row) async for row in cursor]

    async def list_upcoming_reminders(self, days: int = 7) -> list[UpcomingReminder]:
        db = await self._get_db()
        today = datetime.now(UTC).date()
        end_date = today + timedelta(days=days)

        today_mmdd = today.strftime("%m-%d")
        end_mmdd = end_date.strftime("%m-%d")
        today_iso = today.isoformat()
        end_iso = end_date.isoformat()

        crosses_year = end_mmdd < today_mmdd

        if crosses_year:
            annual_clause = "(r.date >= ? OR r.date <= ?)"
        else:
            annual_clause = "(r.date >= ? AND r.date <= ?)"

        query = f"""
            SELECT r.*, p.name as person_name FROM reminders r
            JOIN people p ON r.person_id = p.person_id
            WHERE r.status = 'active' AND r.recurrence = 'annual'
              AND {annual_clause}
            UNION ALL
            SELECT r.*, p.name as person_name FROM reminders r
            JOIN people p ON r.person_id = p.person_id
            WHERE r.status = 'active' AND r.recurrence = 'once'
              AND r.date >= ? AND r.date <= ?
            UNION ALL
            SELECT r.*, p.name as person_name FROM reminders r
            JOIN people p ON r.person_id = p.person_id
            WHERE r.status = 'active' AND r.recurrence = 'once'
              AND r.date < ?
            ORDER BY date
        """  # noqa: S608
        params = [today_mmdd, end_mmdd, today_iso, end_iso, today_iso]

        async with db.execute(query, params) as cursor:
            return [
                UpcomingReminder(
                    reminder=_row_to_reminder(row),
                    person_name=row["person_name"],
                )
                async for row in cursor
            ]

    async def dismiss_reminder(self, person_id: str, reminder_id: str) -> Reminder:
        db = await self._get_db()
        now = _now()
        result = await db.execute(
            """UPDATE reminders SET status = ?, updated_at = ?
               WHERE person_id = ? AND reminder_id = ?""",
            (ReminderStatus.DISMISSED.value, now, person_id, reminder_id),
        )
        if result.rowcount == 0:
            raise NotFoundError(
                f"Reminder {reminder_id} for person {person_id} not found"
            )
        await db.commit()
        reminder = await self._get_reminder(person_id, reminder_id)
        return reminder

    async def _get_reminder(self, person_id: str, reminder_id: str) -> Reminder:
        db = await self._get_db()
        async with db.execute(
            "SELECT * FROM reminders WHERE person_id = ? AND reminder_id = ?",
            (person_id, reminder_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise NotFoundError(f"Reminder {reminder_id} not found")
            return _row_to_reminder(row)

    # ----- Audit Log -----

    async def write_audit_entry(self, entry: AuditLogEntry) -> None:
        db = await self._get_db()
        await db.execute(
            """INSERT INTO audit_log
               (audit_id, actor, action, resource_id, timestamp, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                entry.audit_id,
                entry.actor,
                entry.action,
                entry.resource_id,
                entry.timestamp,
                entry.source,
            ),
        )
        await db.commit()

    async def list_audit_entries(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        db = await self._get_db()
        conditions = []
        params: list[str | int] = []

        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if action:
            conditions.append("action = ?")
            params.append(action)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        query = f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?"  # noqa: S608

        async with db.execute(query, params) as cursor:
            return [_row_to_audit_entry(row) async for row in cursor]
