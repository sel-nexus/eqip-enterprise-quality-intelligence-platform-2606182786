"""Persist certification workflow documents through the lifespan-owned Mongo database."""

from datetime import datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.results import UpdateResult


class CertificationRepository:
    """Provide MongoDB access for demand transitions and readiness snapshots."""

    def __init__(self, database: AsyncDatabase) -> None:
        """Store the application-scoped Mongo database handle.

        Args:
            database: Lifespan-owned asynchronous Mongo database.
        """
        self._demands = database.get_collection("demands")
        self._readiness = database.get_collection("readiness_snapshots")
        self._audit = database.get_collection("certification_audit")

    async def ensure_indexes(self) -> None:
        """Create indexes supporting actor-scoped workflow lookups."""
        await self._demands.create_index("demand_id", unique=True)
        await self._readiness.create_index([("release_id", 1), ("owner_actor_id", 1), ("timestamp", -1)])
        await self._audit.create_index([("aggregate_id", 1), ("timestamp", -1)])

    async def find_demand(self, demand_id: str) -> dict[str, Any] | None:
        """Find one demand by its externally supplied identifier.

        Args:
            demand_id: Safe demand identifier.

        Returns:
            Persisted demand, if present.
        """
        return await self._demands.find_one({"demand_id": demand_id}, {"_id": 0})

    async def transition_demand(
        self,
        demand_id: str,
        actor_id: str,
        expected_version: int,
        source: str,
        destination: str,
        resolution_note: str | None,
        timestamp: datetime,
    ) -> UpdateResult:
        """Atomically apply an owned state transition only at the expected version.

        Args:
            demand_id: Safe demand identifier.
            actor_id: Owning actor for the mutation.
            expected_version: Optimistic-lock version.
            source: Current demand state.
            destination: Requested next demand state.
            resolution_note: Optional terminal transition evidence.
            timestamp: Transition timestamp.

        Returns:
            Mongo update result.
        """
        return await self._demands.update_one(
            {"demand_id": demand_id, "owner_actor_id": actor_id, "version": expected_version},
            {
                "$set": {
                    "state": destination,
                    "resolution_note": resolution_note,
                    "updated_at": timestamp,
                },
                "$inc": {"version": 1},
                "$push": {
                    "history": {
                        "from_state": source,
                        "to_state": destination,
                        "note": resolution_note,
                        "timestamp": timestamp,
                    }
                },
            },
        )

    async def find_latest_readiness(self, release_id: str, actor_id: str) -> dict[str, Any] | None:
        """Find the latest readiness snapshot visible to the owning actor.

        Args:
            release_id: Safe release identifier.
            actor_id: Owning actor for the read.

        Returns:
            Latest actor-scoped readiness snapshot, if present.
        """
        cursor = self._readiness.find(
            {"release_id": release_id, "owner_actor_id": actor_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(1)
        snapshots = await cursor.to_list(length=1)
        return snapshots[0] if snapshots else None

    async def find_any_readiness(self, release_id: str) -> dict[str, Any] | None:
        """Find a release snapshot regardless of ownership for authorization checks."""
        return await self._readiness.find_one({"release_id": release_id}, {"_id": 0})

    async def insert_readiness_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Persist one immutable readiness calculation."""
        await self._readiness.insert_one(snapshot)

    async def write_audit(self, event: dict[str, Any]) -> None:
        """Persist an audit event for a certification decision."""
        await self._audit.insert_one(event)
