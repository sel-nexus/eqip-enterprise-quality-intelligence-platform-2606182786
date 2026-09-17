"""Expose demand-transition and release-readiness certification HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from app.certification.repository import CertificationRepository
from app.certification.schemas import ReadinessRequest, ReadinessResponse
from app.certification.service import CertificationService
from app.core.database import get_database
from app.platform.context import IdentityContext

router = APIRouter(prefix="/api/v1", tags=["certification"])
DatabaseDependency = Annotated[AsyncDatabase, Depends(get_database)]


def get_certification_service(database: DatabaseDependency) -> CertificationService:
    """Build a certification service using the lifespan-owned Mongo database.

    Args:
        database: Active MongoDB dependency.

    Returns:
        Certification service for the request.
    """
    return CertificationService(CertificationRepository(database))


ServiceDependency = Annotated[CertificationService, Depends(get_certification_service)]



@router.post(
    "/releases/{release_id}/readiness",
    response_model=ReadinessResponse,
    status_code=201,
    summary="Calculate and persist release readiness",
)
async def calculate_readiness(
    release_id: str,
    command: ReadinessRequest,
    context: IdentityContext,
    service: ServiceDependency,
) -> ReadinessResponse:
    """Calculate a weighted release recommendation and preserve its evidence.

    Args:
        release_id: Release identifier being evaluated.
        command: Gate, test, defect, automation, and version evidence.
        context: Request identity and correlation context.
        service: Certification business service.

    Returns:
        Persisted readiness snapshot envelope.
    """
    return ReadinessResponse(
        data=await service.calculate_readiness(release_id, command, context),
        correlation_id=context.correlation_id,
    )
