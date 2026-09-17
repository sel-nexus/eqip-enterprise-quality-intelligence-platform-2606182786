"""Expose governed portfolio HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.certification.repository import CertificationRepository
from app.certification.schemas import DemandTransitionCommand, DemandTransitionResponse
from app.certification.service import CertificationService
from app.core.database import get_database
from app.platform.audit import AuditService
from app.platform.context import IdentityContext, validate_resource_identifier
from app.portfolio.repository import ApplicationRepository
from app.portfolio.schemas import ApplicationCreate, ApplicationListData, ApplicationListResponse, CreateApplicationResponse
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


@router.post("/applications", response_model=CreateApplicationResponse, status_code=201, summary="Create a governed application")
async def create_application(command: ApplicationCreate, context: IdentityContext, service: ServiceDependency) -> CreateApplicationResponse:
    """Persist an actor-owned, version-one application."""
    return CreateApplicationResponse(data=await service.create(command, context), correlation_id=context.correlation_id)


@router.get("/applications", response_model=ApplicationListResponse, status_code=200, summary="List governed applications")
async def list_applications(
    context: IdentityContext,
    service: ServiceDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApplicationListResponse:
    """Return a bounded newest-first page within the current actor scope."""
    items, total = await service.list(context, limit, offset)
    return ApplicationListResponse(data=ApplicationListData(items=items, total=total), correlation_id=context.correlation_id)


@router.post("/demands/{demand_id}/transitions", response_model=DemandTransitionResponse, status_code=200, summary="Transition a governed demand")
async def transition_demand(
    demand_id: str,
    command: DemandTransitionCommand,
    context: IdentityContext,
    service: CertificationServiceDependency,
) -> DemandTransitionResponse:
    """Move an owned persisted demand through one allowed workflow state."""
    safe_demand_id = validate_resource_identifier(demand_id)
    return DemandTransitionResponse(data=await service.transition_demand(safe_demand_id, command, context), correlation_id=context.correlation_id)
