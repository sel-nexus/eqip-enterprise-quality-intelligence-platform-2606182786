"""Exercise governed application service and API behavior against real MongoDB."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017")
os.environ.setdefault("MONGODB_DB", f"eqip_portfolio_test_{uuid4().hex}")
os.environ.setdefault("AUTH_MODE", "development")
os.environ.setdefault("DEVELOPMENT_USER_ID", "test-actor")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.core.config import Settings, get_settings
from app.main import app
from app.platform.audit import AuditService
from app.platform.context import RequestContext
from app.platform.errors import DomainValidationError
from app.portfolio.repository import ApplicationRepository
from app.portfolio.schemas import ApplicationCreate
from app.portfolio.service import ApplicationService


@pytest_asyncio.fixture(autouse=True)
async def clear_test_collections() -> AsyncIterator[None]:
    """Clear real test-database collections before and after each case."""
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
    """Run requests through the real app lifespan and ASGI boundary."""
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api_client:
            yield api_client


def valid_payload() -> dict[str, object]:
    """Return a representative LLD-conformant create payload."""
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


async def collection_counts() -> tuple[int, int]:
    """Return application and audit-event counts from the real test database."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    counts = (await database.applications.count_documents({}), await database.audit_events.count_documents({}))
    await mongo.close()
    return counts


@pytest.mark.asyncio
async def test_create_persists_actor_segment_scope_and_audit_event(client: httpx.AsyncClient) -> None:
    """Create an application and verify real Mongo ownership and audit state."""
    response = await client.post("/api/v1/applications", json=valid_payload(), headers={"X-Dev-User": "u-42"})

    assert response.status_code == 201
    application_id = response.json()["data"]["application_id"]
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    persisted = await database.applications.find_one({"application_id": application_id})
    audit = await database.audit_events.find_one({"entity_id": application_id})
    await mongo.close()
    assert persisted is not None and persisted["owner_actor_id"] == "u-42" and persisted["segment_id"] == "SEG-HEALTH"
    assert audit is not None and audit["action"] == "application.create" and audit["outcome"] == "success"


@pytest.mark.asyncio
async def test_listing_is_actor_scoped_and_does_not_serialize_another_actors_record(client: httpx.AsyncClient) -> None:
    """Verify actor A cannot list applications persisted by actor B."""
    assert (await client.post("/api/v1/applications", json=valid_payload(), headers={"X-Dev-User": "actor-a"})).status_code == 201
    response = await client.get("/api/v1/applications", headers={"X-Dev-User": "actor-b"})
    assert response.status_code == 200
    assert response.json()["data"] == {"items": [], "total": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("name", "   "), ("owners", []), ("expected_version", 1)])
async def test_invalid_or_boundary_application_fields_return_problem_details_without_writes(
    client: httpx.AsyncClient, field: str, value: object
) -> None:
    """Reject isolated invalid application fields before any database write."""
    payload = valid_payload()
    payload[field] = value
    response = await client.post("/api/v1/applications", json=payload)
    assert response.status_code == 422
    assert response.json()["title"] == "Validation failed"
    assert await collection_counts() == (0, 0)


@pytest.mark.asyncio
async def test_unknown_fields_and_xss_like_input_are_rejected_without_persistence(client: httpx.AsyncClient) -> None:
    """Forbid unknown JSON fields and ensure markup-like content is safely inert."""
    payload = valid_payload()
    payload["unexpected"] = "ignored-before"
    unknown = await client.post("/api/v1/applications", json=payload)
    assert unknown.status_code == 422 and await collection_counts() == (0, 0)

    xss = await client.post("/api/v1/applications", json={**valid_payload(), "segment_id": "<script>alert(1)</script>"})
    assert xss.status_code == 201
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    persisted = await mongo.get_database(settings.mongodb_db).applications.find_one({"segment_id": "<script>alert(1)</script>"})
    await mongo.close()
    assert persisted is not None and persisted["segment_id"] == "<script>alert(1)</script>"


@pytest.mark.asyncio
async def test_duplicate_unique_index_conflict_writes_no_success_audit() -> None:
    """Map a real Mongo unique-index collision to validation without an audit event."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    await database.applications.create_index("business_id", unique=True)
    await database.applications.insert_one({"business_id": "APP-DUPLICATE"})
    service = ApplicationService(ApplicationRepository(database), AuditService(database))
    command = ApplicationCreate(**valid_payload())
    context = RequestContext(actor_id="test-actor", correlation_id="duplicate")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("app.portfolio.service.uuid4", lambda: type("Identifier", (), {"hex": "duplicate"})())
        with pytest.raises(DomainValidationError):
            await service.create(command, context)
    assert await database.audit_events.count_documents({}) == 0
    assert await database.applications.count_documents({}) == 1
    await mongo.close()


@pytest.mark.asyncio
async def test_production_mode_absent_or_invalid_development_identity_returns_401_problem_details(client: httpx.AsyncClient) -> None:
    """Reject absent and invalid development headers through the protected HTTP route."""
    from app.core.config import get_settings

    production_settings = Settings(mongodb_uri="mongodb://localhost:27017", mongodb_db="test", auth_mode="production")
    app.dependency_overrides[get_settings] = lambda: production_settings
    try:
        for headers in ({}, {"X-Dev-User": "<script>"}):
            response = await client.get("/api/v1/applications", headers=headers)
            assert response.status_code == 401
            assert response.json()["detail"] == "No production authentication adapter is configured."
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_invalid_development_identity_returns_401(client: httpx.AsyncClient) -> None:
    """Reject a malformed local actor header rather than using it as a Mongo scope."""
    response = await client.get("/api/v1/applications", headers={"X-Dev-User": "$ne"})
    assert response.status_code == 401
