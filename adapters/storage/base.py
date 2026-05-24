"""Abstract storage interface.

All storage backends (SQLite, DynamoDB, Postgres, etc.) implement this interface.
The core never imports a specific backend directly — only this base class.

Design notes:
- All methods are async to match FastAPI's async style
- Returns Pydantic models, not raw dicts
- Errors raise specific exceptions defined below, not adapter-specific errors
"""

from abc import ABC, abstractmethod

from core.models import (
    AuditLogEntry,
    Brief,
    Interaction,
    LoopStatus,
    OpenLoop,
    Person,
)

# ============================================================================
# Exceptions
# ============================================================================


class StorageError(Exception):
    """Base exception for all storage errors."""


class NotFoundError(StorageError):
    """Raised when a requested record doesn't exist."""


class AlreadyExistsError(StorageError):
    """Raised when trying to create a record that already exists."""


# ============================================================================
# Interface
# ============================================================================


class StorageProvider(ABC):
    """Abstract interface for REMI's data persistence layer.

    All operations are async. Implementations should be thread-safe within
    a single event loop.
    """

    # ----- Lifecycle -----

    @abstractmethod
    async def initialize(self) -> None:
        """Set up storage (create tables, verify connectivity, etc.).

        Called once at app startup. Must be idempotent — safe to call repeatedly.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (close connections, etc.). Called at app shutdown."""
        ...

    # ----- People -----

    @abstractmethod
    async def create_person(self, person: Person) -> Person:
        """Create a new person record.

        Raises:
            AlreadyExistsError: If person_id already exists.
        """
        ...

    @abstractmethod
    async def get_person(self, person_id: str) -> Person | None:
        """Fetch a person by ID. Returns None if not found."""
        ...

    @abstractmethod
    async def find_people_by_name(self, name: str) -> list[Person]:
        """Find all people whose name matches (case-insensitive).

        Used for person resolution during ingestion.
        """
        ...

    @abstractmethod
    async def list_people(self, limit: int = 100, offset: int = 0) -> list[Person]:
        """List all people. For the People List screen."""
        ...

    @abstractmethod
    async def update_person(self, person: Person) -> Person:
        """Update an existing person. Auto-updates updated_at timestamp.

        Raises:
            NotFoundError: If person doesn't exist.
        """
        ...

    @abstractmethod
    async def delete_person(self, person_id: str) -> None:
        """Delete a person and all their interactions and open loops.

        Cascades. Use with care.

        Raises:
            NotFoundError: If person doesn't exist.
        """
        ...

    # ----- Interactions -----

    @abstractmethod
    async def create_interaction(self, interaction: Interaction) -> Interaction:
        """Create a new interaction record."""
        ...

    @abstractmethod
    async def get_interaction(
        self, person_id: str, interaction_id: str
    ) -> Interaction | None:
        """Fetch a specific interaction. Returns None if not found."""
        ...

    @abstractmethod
    async def list_interactions_for_person(
        self, person_id: str, limit: int = 100
    ) -> list[Interaction]:
        """List all interactions for a person, newest first."""
        ...

    # ----- Open Loops -----

    @abstractmethod
    async def create_open_loop(self, loop: OpenLoop) -> OpenLoop:
        """Create a new open loop."""
        ...

    @abstractmethod
    async def get_open_loop(self, person_id: str, loop_id: str) -> OpenLoop | None:
        """Fetch a specific open loop. Returns None if not found."""
        ...

    @abstractmethod
    async def list_open_loops_for_person(self, person_id: str) -> list[OpenLoop]:
        """List all open loops for a person (any status)."""
        ...

    @abstractmethod
    async def list_open_loops_by_status(
        self,
        status: LoopStatus,
        due_before: str | None = None,
        limit: int = 100,
    ) -> list[OpenLoop]:
        """Cross-person loop query.

        Used for "what's open and due this week" view.

        Args:
            status: Filter by loop status
            due_before: Optional ISO8601 date — only loops due on or before this
            limit: Max results
        """
        ...

    @abstractmethod
    async def update_open_loop(self, loop: OpenLoop) -> OpenLoop:
        """Update an existing open loop. Auto-updates updated_at.

        If status changed to done or dropped, set closed_at.

        Raises:
            NotFoundError: If loop doesn't exist.
        """
        ...

    # ----- Briefs -----

    @abstractmethod
    async def create_brief(self, brief: Brief) -> Brief:
        """Store a generated brief."""
        ...

    @abstractmethod
    async def list_briefs_for_person(
        self, person_id: str, limit: int = 20
    ) -> list[Brief]:
        """List stored briefs for a person, newest first."""
        ...

    # ----- Audit Log -----

    @abstractmethod
    async def write_audit_entry(self, entry: AuditLogEntry) -> None:
        """Append an audit log entry.

        Per SECURITY.md, never log raw content here — only metadata about
        what action occurred. Callers must enforce this.
        """
        ...

    @abstractmethod
    async def list_audit_entries(
        self,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """List audit entries, optionally filtered. For incident forensics."""
        ...
