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
        """Create indexes supporting demand and readiness workflow lookups."""
        await self._demands.create_index("demand_id", unique=True)
        await self._readiness.create_index([("release_id", 1), ("timestamp", -1)])
        await self._audit.create_index([("aggregate_id", 1), ("timestamp", -1)])

    async def find_demand(self, demand_id: str) -> dict[str, Any] | None:
        """Find one demand by its externally supplied identifier."""
        return await self._demands.find_one({"demand_id": demand_id}, {"_id": 0})

    async def create_demand_if_missing(self, demand_id: str, timestamp: datetime) -> dict[str, Any]:
        """Seed an on-demand submitted demand without replacing existing state."""
        await self._demands.update_one(
            {"demand_id": demand_id},
            {
                "$setOnInsert": {
                    "demand_id": demand_id,
                    "state": "submitted",
                    "version": 0,
                    "resolution_note": None,
                    "history": [
                        {
                            "from_state": None,
                            "to_state": "submitted",
                            "note": "On-demand demand seed",
                            "timestamp": timestamp,
                        }
                    ],
                    "updated_at": timestamp,
                }
            },
            upsert=True,
        )
        demand = await self.find_demand(demand_id)
        if demand is None:
            raise RuntimeError("Demand was not available after on-demand seed.")
        return demand

    async def transition_demand(
        self,
        demand_id: str,
        expected_version: int,
        source: str,
        destination: str,
        resolution_note: str | None,
        timestamp: datetime,
    ) -> UpdateResult:
        """Atomically apply a state transition only at the expected version."""
        return await self._demands.update_one(
            {"demand_id": demand_id, "version": expected_version},
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

    async def find_latest_readiness(self, release_id: str) -> dict[str, Any] | None:
        """Find the most recently persisted readiness snapshot for a release."""
        cursor = self._readiness.find({"release_id": release_id}, {"_id": 0}).sort("timestamp", -1).limit(1)
        snapshots = await cursor.to_list(length=1)
        return snapshots[0] if snapshots else None

    async def insert_readiness_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Persist one immutable readiness calculation."""
        await self._readiness.insert_one(snapshot)

    async def write_audit(self, event: dict[str, Any]) -> None:
        """Persist an audit event for a certification decision."""
        await self._audit.insert_one(event)
