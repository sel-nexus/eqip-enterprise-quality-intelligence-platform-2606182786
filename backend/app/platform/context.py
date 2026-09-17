"""Provide request correlation and configured development identity."""

from dataclasses import dataclass
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class RequestContext:
    """Represent an authenticated actor and request correlation id."""

    actor_id: str
    correlation_id: str


def ensure_request_context(request: Request) -> str:
    """Assign and return a request correlation identifier.

    Args:
        request: Current inbound HTTP request.

    Returns:
        Existing or newly generated correlation id.
    """
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid4()))
    request.state.correlation_id = correlation_id
    return correlation_id


async def get_development_identity(
    request: Request,
    x_dev_user: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> RequestContext:
    """Resolve the configured local identity for protected business routes.

    Args:
        request: Current HTTP request.
        x_dev_user: Optional explicit local actor header.
        settings: Application identity-mode configuration.

    Returns:
        Authenticated local request context.

    Raises:
        HTTPException: If development identity mode is not enabled.
    """
    if settings.auth_mode != "development":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No production authentication adapter is configured.",
        )
    correlation_id = ensure_request_context(request)
    actor_id = (x_dev_user or settings.development_user_id).strip()
    if not actor_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Development identity is required.")
    return RequestContext(actor_id=actor_id, correlation_id=correlation_id)


IdentityContext = Annotated[RequestContext, Depends(get_development_identity)]
