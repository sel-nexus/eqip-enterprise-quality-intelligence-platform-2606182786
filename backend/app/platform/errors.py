"""Model RFC 7807-style errors for business failures."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ProblemDetails(BaseModel):
    """Describe a machine-readable API problem."""

    type: str
    title: str
    status: int
    detail: str
    correlation_id: str
    invalid_params: list[dict[str, Any]] = Field(default_factory=list)


class DomainValidationError(Exception):
    """Signal a business validation error with field-level details.

    Args:
        detail: Human-readable failure explanation.
        invalid_params: Invalid field descriptors.
    """

    def __init__(self, detail: str, invalid_params: list[dict[str, Any]] | None = None) -> None:
        """Initialize the domain validation error."""
        super().__init__(detail)
        self.detail = detail
        self.invalid_params = invalid_params or []


async def domain_validation_handler(request: Request, exc: DomainValidationError) -> JSONResponse:
    """Return a Problem Details response for business validation failures.

    Args:
        request: Failing HTTP request.
        exc: Raised validation exception.

    Returns:
        RFC 7807-compatible 422 response.
    """
    problem = ProblemDetails(
        type="https://eqip.example/problems/validation",
        title="Validation failed",
        status=422,
        detail=exc.detail,
        correlation_id=getattr(request.state, "correlation_id", "unknown"),
        invalid_params=exc.invalid_params,
    )
    return JSONResponse(status_code=422, content=problem.model_dump())
