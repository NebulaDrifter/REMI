"""SQLite storage adapter.

Local-deployment implementation of StorageProvider. Uses the schema documented
in DATA_MODEL.md "SQLite Schema" section.

Implementation: Phase 3 of BUILD_PLAN.md.
"""

# TODO (Phase 3): Implement SQLiteStorage(StorageProvider) here.
#
# Implementation notes:
# - Use aiosqlite for async SQLite access (already supported by Python 3.12)
#   OR use synchronous sqlite3 in a thread pool — discuss with Tyler before deciding
# - Auto-create schema in initialize() using CREATE TABLE IF NOT EXISTS
# - JSON-serialize tags, facts, tags_added when writing; parse on read
# - Use parameterized queries always (no string concatenation — SQLi defense)
# - Handle SQLite-specific quirks (no native bool, dates as text, etc.)
# - Make sure file permissions are correct on the .db file (0o600)
# - Add foreign key enforcement: PRAGMA foreign_keys = ON
#
# Test coverage requirements (Phase 3 done criteria):
# - create_person, get_person, find_people_by_name, list_people, update_person
# - create_interaction, list_interactions_for_person
# - create_open_loop, list_open_loops_by_status with due_before filter
# - update_open_loop status transition writes closed_at
# - write_audit_entry, list_audit_entries
# - delete_person cascades to interactions and loops
# - Concurrent access doesn't corrupt data

from adapters.storage.base import StorageProvider


class SQLiteStorage(StorageProvider):
    """SQLite implementation of StorageProvider.

    TODO: Implement in Phase 3.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        # TODO: Set up connection / pool

    async def initialize(self) -> None:
        raise NotImplementedError("Phase 3: implement SQLite schema initialization")

    async def close(self) -> None:
        raise NotImplementedError("Phase 3: implement connection cleanup")

    # All other methods raise NotImplementedError until Phase 3.
    # Listed explicitly here so the class is at least instantiable for tests.

    async def create_person(self, person):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def get_person(self, person_id):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def find_people_by_name(self, name):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def list_people(self, limit=100, offset=0):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def update_person(self, person):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def delete_person(self, person_id):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def create_interaction(self, interaction):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def get_interaction(self, person_id, interaction_id):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def list_interactions_for_person(self, person_id, limit=100):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def create_open_loop(self, loop):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def get_open_loop(self, person_id, loop_id):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def list_open_loops_for_person(self, person_id):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def list_open_loops_by_status(self, status, due_before=None, limit=100):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def update_open_loop(self, loop):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def write_audit_entry(self, entry):  # type: ignore[override]
        raise NotImplementedError("Phase 3")

    async def list_audit_entries(self, actor=None, action=None, limit=100):  # type: ignore[override]
        raise NotImplementedError("Phase 3")
