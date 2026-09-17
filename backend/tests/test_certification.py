"""Exercise persisted demand and release certification endpoints against real MongoDB."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient

os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017")
os.environ.setdefault("MONGODB_DB", f"eqip_certification_test_{uuid4().hex}")
os.environ.setdefault("AUTH_MODE", "development")
os.environ.setdefault("DEVELOPMENT_USER_ID", "test-actor")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.core.config import get_settings
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def clear_certification_collections() -> AsyncIterator[None]:
    """Isolate certification assertions in a real Mongo database."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    for name in ("demands", "readiness_snapshots", "certification_audit"):
        await database.get_collection(name).delete_many({})
    try:
        yield
    finally:
        for name in ("demands", "readiness_snapshots", "certification_audit"):
            await database.get_collection(name).delete_many({})
        await mongo.close()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Provide an ASGI client running the real FastAPI lifespan."""
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api_client:
            yield api_client


async def seed_demand(demand_id: str, actor_id: str, state: str = "submitted", version: int = 0) -> None:
    """Seed an explicitly owned demand document in the real Mongo database."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    timestamp = datetime.now(UTC)
    await mongo.get_database(settings.mongodb_db).demands.insert_one({
        "demand_id": demand_id, "owner_actor_id": actor_id, "state": state, "version": version,
        "resolution_note": None, "history": [], "updated_at": timestamp,
    })
    await mongo.close()


def readiness_payload(**overrides: object) -> dict[str, object]:
    """Build valid readiness input with optional branch-specific overrides."""
    return {
        "expected_version": 0, "applicable_gate_count": 4, "passed_gate_count": 4,
        "unwaived_gate_failures": 0, "test_pass_rate": 95, "open_defect_count": 1,
        "critical_defect_count": 0, "automation_coverage": 80, **overrides,
    }


@pytest.mark.asyncio
async def test_missing_and_cross_scope_demands_return_404_and_403_without_audit(client: httpx.AsyncClient) -> None:
    """Remove auto-seeding and deny mutation of another actor's persisted demand."""
    missing = await client.post("/api/v1/demands/DEM-MISSING/transitions", json={"destination": "triaged", "expected_version": 0})
    assert missing.status_code == 404
    await seed_demand("DEM-OTHER", "actor-a")
    forbidden = await client.post("/api/v1/demands/DEM-OTHER/transitions", json={"destination": "triaged", "expected_version": 0}, headers={"X-Dev-User": "actor-b"})
    assert forbidden.status_code == 403
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    assert await database.demands.find_one({"demand_id": "DEM-OTHER", "version": 0}) is not None
    assert await database.certification_audit.count_documents({}) == 0
    await mongo.close()


@pytest.mark.asyncio
async def test_transition_persists_history_and_rejects_stale_version(client: httpx.AsyncClient) -> None:
    """Persist a valid owned demand transition and reject a stale mutation."""
    await seed_demand("DEM-900", "test-actor")
    first = await client.post("/api/v1/demands/DEM-900/transitions", json={"destination": "triaged", "expected_version": 0})
    stale = await client.post("/api/v1/demands/DEM-900/transitions", json={"destination": "in_progress", "expected_version": 0})
    assert first.status_code == 200 and first.json()["data"]["version"] == 1
    assert stale.status_code == 409


@pytest.mark.asyncio
async def test_terminal_demand_requires_note_and_unsafe_ids_do_not_seed_documents(client: httpx.AsyncClient) -> None:
    """Require terminal evidence and reject Mongo-operator or XSS-shaped IDs safely."""
    await seed_demand("DEM-901", "test-actor")
    missing_note = await client.post("/api/v1/demands/DEM-901/transitions", json={"destination": "cancelled", "expected_version": 0, "resolution_note": "   "})
    operator = await client.post("/api/v1/demands/%24ne/transitions", json={"destination": "triaged", "expected_version": 0})
    markup = await client.post("/api/v1/demands/%3Cscript%3E/transitions", json={"destination": "triaged", "expected_version": 0})
    assert missing_note.status_code == 422 and operator.status_code == 422 and markup.status_code == 422
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    assert await mongo.get_database(settings.mongodb_db).demands.count_documents({}) == 1
    await mongo.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"applicable_gate_count": 1, "passed_gate_count": 2},
    {"test_pass_rate": 101},
    {"unknown": "field"},
])
async def test_readiness_invalid_fields_return_problem_details_without_persistence(client: httpx.AsyncClient, payload: dict[str, object]) -> None:
    """Reject isolated field and unknown-field defects without snapshots or audits."""
    response = await client.post("/api/v1/releases/REL-INVALID/readiness", json=readiness_payload(**payload))
    assert response.status_code == 422 and response.json()["title"] == "Validation failed"
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    assert await database.readiness_snapshots.count_documents({}) == 0
    assert await database.certification_audit.count_documents({}) == 0
    await mongo.close()


@pytest.mark.asyncio
async def test_readiness_handles_zero_gates_ready_conditional_stale_and_cross_scope(client: httpx.AsyncClient) -> None:
    """Cover zero gates, recommendation thresholds, stale version, and actor scope."""
    ready = await client.post("/api/v1/releases/REL-READY/readiness", json=readiness_payload(applicable_gate_count=0, passed_gate_count=0, test_pass_rate=100, open_defect_count=0, automation_coverage=100))
    conditional = await client.post("/api/v1/releases/REL-CONDITIONAL/readiness", json=readiness_payload(test_pass_rate=60, open_defect_count=4, automation_coverage=50))
    stale = await client.post("/api/v1/releases/REL-READY/readiness", json=readiness_payload(expected_version=0, applicable_gate_count=0, passed_gate_count=0))
    forbidden = await client.post("/api/v1/releases/REL-READY/readiness", json=readiness_payload(expected_version=1, applicable_gate_count=0, passed_gate_count=0), headers={"X-Dev-User": "actor-b"})
    assert ready.status_code == 200 and ready.json()["data"]["recommendation"] == "Ready"
    assert conditional.status_code == 200 and conditional.json()["data"]["recommendation"] == "Conditional"
    assert stale.status_code == 409 and forbidden.status_code == 403


@pytest.mark.asyncio
async def test_readiness_blocked_recommendation_persists_owned_snapshot(client: httpx.AsyncClient) -> None:
    """Force a blocked recommendation and verify its real Mongo ownership."""
    response = await client.post("/api/v1/releases/REL-42/readiness", json=readiness_payload(unwaived_gate_failures=1, passed_gate_count=3))
    assert response.status_code == 200 and response.json()["data"]["recommendation"] == "Blocked"
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    snapshot = await mongo.get_database(settings.mongodb_db).readiness_snapshots.find_one({"release_id": "REL-42"})
    await mongo.close()
    assert snapshot is not None and snapshot["owner_actor_id"] == "test-actor"
