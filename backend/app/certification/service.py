"""Apply domain rules for demand transitions and release-readiness certification."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.certification.repository import CertificationRepository
from app.certification.schemas import DemandRecord, DemandTransitionCommand, ReadinessRequest, ReadinessSnapshot
from app.platform.context import RequestContext

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"triaged", "cancelled"},
    "triaged": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}
WEIGHTS = {
    "gates": 0.40,
    "tests": 0.30,
    "defects": 0.15,
    "automation": 0.15,
}


class CertificationService:
    """Coordinate persisted demand state transitions and readiness calculations."""

    def __init__(self, repository: CertificationRepository) -> None:
        """Create the service using the workflow's MongoDB repository.

        Args:
            repository: Data-access boundary for certification collections.
        """
        self._repository = repository

    async def transition_demand(
        self, demand_id: str, command: DemandTransitionCommand, context: RequestContext
    ) -> DemandRecord:
        """Apply one valid optimistic-locking transition to an owned demand.

        Args:
            demand_id: Validated caller-supplied demand identifier.
            command: Destination state, version, and optional resolution note.
            context: Request identity and correlation context for auditing.

        Returns:
            Persisted demand after the transition.

        Raises:
            HTTPException: If the demand is missing, inaccessible, or the transition is invalid.
        """
        timestamp = datetime.now(UTC)
        demand = await self._repository.find_demand(demand_id)
        if demand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand was not found.")
        if demand.get("owner_actor_id") != context.actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demand is outside the current actor scope.")
        source = str(demand["state"])
        if command.destination not in ALLOWED_TRANSITIONS[source]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Transition from {source} to {command.destination} is not allowed.")
        if command.destination in {"completed", "cancelled"} and not command.resolution_note:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="resolution_note is required for completed or cancelled demands.")
        update = await self._repository.transition_demand(
            demand_id,
            context.actor_id,
            command.expected_version,
            source,
            command.destination,
            command.resolution_note,
            timestamp,
        )
        if update.matched_count != 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Demand version does not match the persisted version.")
        updated = await self._repository.find_demand(demand_id)
        if updated is None:
            raise RuntimeError("Demand was not available after transition.")
        await self._repository.write_audit(
            {
                "aggregate_type": "demand",
                "aggregate_id": demand_id,
                "action": "transitioned",
                "actor": context.actor_id,
                "correlation_id": context.correlation_id,
                "from_state": source,
                "to_state": command.destination,
                "timestamp": timestamp,
            }
        )
        return DemandRecord.model_validate(updated)

    async def calculate_readiness(
        self, release_id: str, command: ReadinessRequest, context: RequestContext
    ) -> ReadinessSnapshot:
        """Calculate and persist an actor-owned release-readiness snapshot.

        Args:
            release_id: Validated caller-supplied release identifier.
            command: Validated gate, test, defect, automation, and version evidence.
            context: Request identity and correlation context for auditing.

        Returns:
            Immutable persisted readiness calculation.

        Raises:
            HTTPException: If an existing release belongs to another actor or is stale.
        """
        timestamp = datetime.now(UTC)
        existing = await self._repository.find_any_readiness(release_id)
        if existing is not None and existing.get("owner_actor_id") != context.actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Release is outside the current actor scope.")
        latest = await self._repository.find_latest_readiness(release_id, context.actor_id)
        persisted_version = int(latest["version"]) if latest is not None else 0
        if command.expected_version != persisted_version:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Release version does not match the latest readiness snapshot.")
        gate_score = 100.0 if command.applicable_gate_count == 0 else (command.passed_gate_count / command.applicable_gate_count) * 100
        defect_score = max(0.0, 100.0 - (command.open_defect_count * 5.0) - (command.critical_defect_count * 25.0))
        score = round(
            gate_score * WEIGHTS["gates"]
            + command.test_pass_rate * WEIGHTS["tests"]
            + defect_score * WEIGHTS["defects"]
            + command.automation_coverage * WEIGHTS["automation"],
            2,
        )
        recommendation = "Blocked" if command.unwaived_gate_failures > 0 else "Ready" if score >= 85 else "Conditional"
        snapshot = ReadinessSnapshot(
            release_id=release_id,
            version=persisted_version + 1,
            inputs=command,
            weights=WEIGHTS,
            score=score,
            recommendation=recommendation,
            timestamp=timestamp,
        )
        document: dict[str, Any] = snapshot.model_dump()
        document["owner_actor_id"] = context.actor_id
        await self._repository.insert_readiness_snapshot(document)
        await self._repository.write_audit(
            {
                "aggregate_type": "release",
                "aggregate_id": release_id,
                "action": "readiness_calculated",
                "actor": context.actor_id,
                "correlation_id": context.correlation_id,
                "recommendation": recommendation,
                "score": score,
                "timestamp": timestamp,
            }
        )
        return snapshot
