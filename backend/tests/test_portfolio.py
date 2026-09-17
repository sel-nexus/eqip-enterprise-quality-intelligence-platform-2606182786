"""Exercise governed application service and API behavior against real MongoDB."""

import asyncio
import os
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", f"eqip_portfolio_test_{uuid4().hex}")
os.environ.setdefault("AUTH_MODE", "development")
os.environ.setdefault("DEVELOPMENT_USER_ID", "test-actor")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.core.config import get_settings
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def clear_test_collections() -> AsyncIterator[None]:
    """Clear real test-database collections before and after each case.

    Yields:
        Control to the test with an isolated MongoDB database.
    """
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri)
    database = client.get_database(settings.mongodb_db)
    await database.applications.delete_many({})
    await database.audit_events.delete_many({})
    try:
        yield
    finally:
        await database.applications.delete_many({})
        await database.audit_events.delete_many({})
        await client.close()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Run requests through the real app lifespan and ASGI boundary.

    Yields:
        HTTP client connected to FastAPI and real MongoDB.
    """
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as api_client:
            yield api_client


def valid_payload() -> dict[str, object]:
    """Return a representative LLD-conformant create payload.

    Returns:
        Valid create command fields.
    """
    return {
        "name": "Claims Portal",
        "segment_id": "SEG-HEALTH",
        "product": "Claims",
        "criticality": "high",
        "tier": "tier-1",
        "owners": ["u-42"],
        "technology": ["React", "FastAPI"],
        "health": "amber",
        "expected_version": 0,
    }


@pytest.mark.asyncio
async def test_create_application_persists_record_and_audit_event(client: httpx.AsyncClient) -> None:
    """Create an application and verify persisted governed state and audit."""
    response = await client.post("/api/v1/applications", json=valid_payload(), headers={"X-Dev-User": "u-42"})

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["application_id"].startswith("APP-")
    assert body["data"]["lifecycle"] == "active"
    assert body["data"]["version"] == 1
    assert body["correlation_id"]

    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    persisted = await database.applications.find_one({"application_id": body["data"]["application_id"]})
    audit = await database.audit_events.find_one({"entity_id": body["data"]["application_id"]})
    await mongo.close()
    assert persisted is not None
    assert persisted["created"]["by"] == "u-42"
    assert audit is not None
    assert audit["action"] == "application.create"


@pytest.mark.asyncio
async def test_invalid_application_returns_problem_details_and_persists_nothing(client: httpx.AsyncClient) -> None:
    """Reject invalid governed input before it can reach persistence."""
    payload = valid_payload()
    payload["name"] = "   "
    payload["criticality"] = "urgent"

    response = await client.post("/api/v1/applications", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["title"] == "Validation failed"
    assert body["status"] == 422
    assert body["invalid_params"]

    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    count = await mongo.get_database(settings.mongodb_db).applications.count_documents({})
    await mongo.close()
    assert count == 0


@pytest.mark.asyncio
async def test_list_is_bounded_and_requires_configured_identity(client: httpx.AsyncClient) -> None:
    """List persisted data through protected bounded portfolio API."""
    for index in range(3):
        payload = valid_payload()
        payload["name"] = f"Claims Portal {index}"
        created = await client.post("/api/v1/applications", json=payload)
        assert created.status_code == 201

    response = await client.get("/api/v1/applications?limit=2&offset=0")

    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) == 2
    assert response.json()["data"]["total"] == 3
    oversized = await client.get("/api/v1/applications?limit=201")
    assert oversized.status_code == 422


def test_production_auth_mode_rejects_development_identity() -> None:
    """Confirm the configured development identity does not claim production auth."""
    from app.platform.context import get_development_identity
    from fastapi import HTTPException
    from starlette.requests import Request
    from app.core.config import Settings

    request = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as error:
        asyncio.run(get_development_identity(request, settings=Settings(mongodb_uri="mongodb://localhost:27017", mongodb_db="test", auth_mode="production")))
    assert error.value.status_code == 401
