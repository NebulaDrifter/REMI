"""DynamoDB storage adapter.

Cloud-deployment implementation of StorageProvider. Uses the schema documented
in DATA_MODEL.md "DynamoDB Schema" section.

Implementation: v1.1 (Phase 11 of BUILD_PLAN.md). DO NOT IMPLEMENT IN v1.0.

This file exists to keep the cloud path visible in the codebase. If you're
tempted to implement this in v1.0, see DECISIONS.md item 10 (Local-First).
"""

from adapters.storage.base import StorageProvider


class DynamoDBStorage(StorageProvider):
    """DynamoDB implementation of StorageProvider.

    Cloud-only. Ships in v1.1.
    """

    def __init__(self, **kwargs) -> None:
        raise NotImplementedError(
            "DynamoDB adapter ships in v1.1. See DECISIONS.md item 10."
        )

    async def initialize(self) -> None:
        raise NotImplementedError("v1.1")

    async def close(self) -> None:
        raise NotImplementedError("v1.1")

    async def create_person(self, person):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def get_person(self, person_id):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def find_people_by_name(self, name):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def list_people(self, limit=100, offset=0):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def update_person(self, person):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def delete_person(self, person_id):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def create_interaction(self, interaction):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def get_interaction(self, person_id, interaction_id):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def list_interactions_for_person(self, person_id, limit=100):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def create_open_loop(self, loop):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def get_open_loop(self, person_id, loop_id):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def list_open_loops_for_person(self, person_id):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def list_open_loops_by_status(self, status, due_before=None, limit=100):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def update_open_loop(self, loop):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def write_audit_entry(self, entry):  # type: ignore[override]
        raise NotImplementedError("v1.1")

    async def list_audit_entries(self, actor=None, action=None, limit=100):  # type: ignore[override]
        raise NotImplementedError("v1.1")
