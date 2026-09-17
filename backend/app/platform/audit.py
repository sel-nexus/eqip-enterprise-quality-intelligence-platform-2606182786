"""Persist immutable audit events for governed changes."""

from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.platform.context import RequestContext


class AuditService:
    """Append allowed governed actions to the audit collection."""

    def __init__(self, database: AsyncDatabase) -> None:
        """Store the collection-owning database.

        Args:
            database: Active Mongo database.
        """
        self._database = database

    async def append_created(
        self,
        context: RequestContext,
        entity_id: str,
        after: dict[str, Any],
    ) -> None:
        """Write an immutable successful application-create event.

        Args:
            context: Authenticated request actor and correlation id.
            entity_id: Created business identifier.
            after: Persisted document snapshot.
        """
        await self._database.audit_events.insert_one(
            {
                "actor_id": context.actor_id,
                "action": "application.create",
                "entity_type": "application",
                "entity_id": entity_id,
                "at": datetime.now(UTC),
                "ip": None,
                "before": None,
                "after": after,
                "outcome": "success",
                "correlation_id": context.correlation_id,
            }
        )
