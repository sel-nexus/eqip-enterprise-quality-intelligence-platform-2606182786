"""Configure the FastAPI application and resource lifespan."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.portfolio import router as portfolio_router
from app.core.config import get_settings
from app.core.database import connect_database, disconnect_database
from app.platform.context import ensure_request_context
from app.platform.errors import DomainValidationError, ProblemDetails, domain_validation_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open and close the pooled MongoDB client around application lifetime.

    Args:
        app: FastAPI application being started.

    Yields:
        Control while the API serves requests.
    """
    await connect_database(app, get_settings())
    try:
        yield
    finally:
        await disconnect_database(app)


app = FastAPI(
    title="EQIP Governed Portfolio API",
    version="1.0.0",
    description="Governed application portfolio increment with development identity mode.",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Correlation-Id", "X-Dev-User"],
)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next: object) -> object:
    """Attach a correlation id to request and response headers.

    Args:
        request: Incoming HTTP request.
        call_next: FastAPI downstream handler.

    Returns:
        HTTP response carrying the correlation header.
    """
    correlation_id = ensure_request_context(request)
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response


@app.exception_handler(DomainValidationError)
async def handle_domain_validation(request: Request, exc: DomainValidationError) -> JSONResponse:
    """Map domain errors to RFC 7807 response documents.

    Args:
        request: Failed HTTP request.
        exc: Domain validation failure.

    Returns:
        Problem Details response.
    """
    return await domain_validation_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map Pydantic request failures to consistent Problem Details.

    Args:
        request: Failed HTTP request.
        exc: FastAPI validation error.

    Returns:
        Problem Details response with invalid parameters.
    """
    invalid_params = [
        {"name": ".".join(str(part) for part in error["loc"]), "reason": error["msg"]}
        for error in exc.errors()
    ]
    problem = ProblemDetails(
        type="https://eqip.example/problems/validation",
        title="Validation failed",
        status=422,
        detail="One or more request fields are invalid.",
        correlation_id=getattr(request.state, "correlation_id", "unknown"),
        invalid_params=invalid_params,
    )
    return JSONResponse(status_code=422, content=problem.model_dump())


@app.get("/api/health", status_code=200, summary="Report API liveness")
async def health() -> dict[str, str]:
    """Return a dependency-free process liveness result.

    Returns:
        Static liveness status.
    """
    return {"status": "ok"}


app.include_router(portfolio_router)
