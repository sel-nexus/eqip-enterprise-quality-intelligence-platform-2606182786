"""Expose governed portfolio HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.certification.repository import CertificationRepository
from app.certification.schemas import DemandTransitionCommand, DemandTransitionResponse
from app.certification.service import CertificationService
from app.core.database import get_database
from app.platform.audit import AuditService
from app.platform.context import IdentityContext
from app.portfolio.repository import ApplicationRepository
from app.portfolio.schemas import (
    ApplicationCreate,
    ApplicationListData,
    ApplicationListResponse,
    CreateApplicationResponse,
)
from app.portfolio.service import ApplicationService

router = APIRouter(prefix="/api/v1", tags=["portfolio"])
DatabaseDependency = Annotated[AsyncDatabase, Depends(get_database)]


def get_application_service(database: DatabaseDependency) -> ApplicationService:
    """Build the service around the lifespan-owned Mongo database.

    Args:
        database: Active database dependency.

    Returns:
        Application service for the current request.
    """
    return ApplicationService(ApplicationRepository(database), AuditService(database))


ServiceDependency = Annotated[ApplicationService, Depends(get_application_service)]


def get_certification_service(database: DatabaseDependency) -> CertificationService:
    """Build a demand certification service from the active database.

    Args:
        database: Lifespan-owned Mongo database.

    Returns:
        Certification service for this request.
    """
    return CertificationService(CertificationRepository(database))


CertificationServiceDependency = Annotated[CertificationService, Depends(get_certification_service)]


@router.post(
    "/applications",
    response_model=CreateApplicationResponse,
    status_code=201,
    summary="Create a governed application",
)
async def create_application(
    command: ApplicationCreate,
    context: IdentityContext,
    service: ServiceDependency,
) -> CreateApplicationResponse:
    """Persist an active, version-one application.

    Args:
        command: Validated application fields.
        context: Configured development identity context.
        service: Application business service.

    Returns:
        Created application envelope.
    """
    return CreateApplicationResponse(data=await service.create(command, context), correlation_id=context.correlation_id)


@router.get(
    "/applications",
    response_model=ApplicationListResponse,
    status_code=200,
    summary="List governed applications",
)
async def list_applications(
    context: IdentityContext,
    service: ServiceDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApplicationListResponse:
    """Return a bounded newest-first governed application page.

    Args:
        context: Configured development identity context.
        service: Application business service.
        limit: Bounded result count.
        offset: Zero-based pagination offset.

    Returns:
        Bounded application collection envelope.
    """
    items, total = await service.list(limit, offset)
    return ApplicationListResponse(data=ApplicationListData(items=items, total=total), correlation_id=context.correlation_id)


@router.post(
    "/demands/{demand_id}/transitions",
    response_model=DemandTransitionResponse,
    status_code=200,
    summary="Transition a governed demand",
)
async def transition_demand(
    demand_id: str,
    command: DemandTransitionCommand,
    context: IdentityContext,
    service: CertificationServiceDependency,
) -> DemandTransitionResponse:
    """Move a persisted demand through one allowed workflow state.

    Args:
        demand_id: Demand identifier to transition or seed on demand.
        command: Destination, expected version, and resolution evidence.
        context: Request identity and correlation context.
        service: Certification business service.

    Returns:
        Updated persisted demand envelope.
    """
    return DemandTransitionResponse(
        data=await service.transition_demand(demand_id, command, context),
        correlation_id=context.correlation_id,
    )
