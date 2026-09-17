"""Implement governed application creation rules."""

from datetime import UTC, datetime
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.platform.audit import AuditService
from app.platform.context import RequestContext
from app.platform.errors import DomainValidationError
from app.portfolio.repository import ApplicationRepository
from app.portfolio.schemas import ApplicationCreate, ApplicationRecord


class ApplicationService:
    """Coordinate portfolio persistence and immutable auditing."""

    def __init__(self, repository: ApplicationRepository, audit_service: AuditService) -> None:
        """Store repository dependencies.

        Args:
            repository: Real MongoDB application repository.
            audit_service: Append-only audit event writer.
        """
        self._repository = repository
        self._audit_service = audit_service

    async def create(self, command: ApplicationCreate, context: RequestContext) -> ApplicationRecord:
        """Create an active version-one governed application and audit it.

        Args:
            command: Validated application create command.
            context: Authorized request context.

        Returns:
            Persisted application response model.

        Raises:
            DomainValidationError: If a generated business id conflicts.
        """
        now = datetime.now(UTC)
        business_id = f"APP-{uuid4().hex[:12].upper()}"
        document = {
            "business_id": business_id,
            "application_id": business_id,
            "name": command.name,
            "segment_id": command.segment_id,
            "product": command.product,
            "criticality": command.criticality,
            "tier": command.tier,
            "owners": command.owners,
            "technology": command.technology,
            "health": command.health,
            "lifecycle": "active",
            "version": 1,
            "created": {"at": now, "by": context.actor_id},
            "updated": {"at": now, "by": context.actor_id},
        }
        try:
            persisted = await self._repository.insert(document)
        except DuplicateKeyError as exc:
            raise DomainValidationError("Application identifier collision; retry the command.") from exc
        await self._audit_service.append_created(context, business_id, persisted)
        return self._to_record(persisted)

    async def list(self, limit: int, offset: int) -> tuple[list[ApplicationRecord], int]:
        """Return a bounded portfolio page.

        Args:
            limit: Maximum results to return.
            offset: Results to skip.

        Returns:
            Serialized applications and total matching count.
        """
        documents, total = await self._repository.list(limit, offset)
        return [self._to_record(document) for document in documents], total

    @staticmethod
    def _to_record(document: dict[str, object]) -> ApplicationRecord:
        """Map internal Mongo document fields to a public record.

        Args:
            document: Persisted application document.

        Returns:
            Public governed application record.
        """
        created = document["created"]
        updated = document["updated"]
        if not isinstance(created, dict) or not isinstance(updated, dict):
            raise RuntimeError("Persisted application timestamps are malformed.")
        return ApplicationRecord(
            application_id=str(document["application_id"]),
            name=str(document["name"]),
            segment_id=str(document["segment_id"]),
            product=str(document["product"]),
            criticality=str(document["criticality"]),
            tier=str(document["tier"]),
            owners=[str(value) for value in document["owners"]],
            technology=[str(value) for value in document["technology"]],
            health=str(document["health"]),
            lifecycle="active",
            version=int(document["version"]),
            created_at=created["at"],
            updated_at=updated["at"],
        )
