"""Provide request correlation, safe identifiers, and development identity."""

from dataclasses import dataclass
import re
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


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


def validate_resource_identifier(identifier: str) -> str:
    """Reject Mongo operators and markup from externally supplied resource IDs.

    Args:
        identifier: Path identifier received from the client.

    Returns:
        Validated identifier.

    Raises:
        HTTPException: If the identifier is not a safe scalar identifier.
    """
    if not IDENTIFIER_PATTERN.fullmatch(identifier) or identifier.startswith("$"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Resource identifier is invalid.")
    return identifier


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
        HTTPException: If development identity mode or actor identity is invalid.
    """
    if settings.auth_mode != "development":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No production authentication adapter is configured.",
        )
    correlation_id = ensure_request_context(request)
    actor_id = (x_dev_user or settings.development_user_id).strip()
    if not actor_id or not IDENTIFIER_PATTERN.fullmatch(actor_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Development identity is required.")
    return RequestContext(actor_id=actor_id, correlation_id=correlation_id)


IdentityContext = Annotated[RequestContext, Depends(get_development_identity)]
SafeResourceIdentifier = Annotated[str, Depends(validate_resource_identifier)]
