"""Exercise persisted demand and release certification endpoints against real MongoDB."""

import os
from collections.abc import AsyncIterator
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


@pytest.mark.asyncio
async def test_transition_persists_history_and_requires_current_version(client: httpx.AsyncClient) -> None:
    """Persist a valid demand transition and reject a stale write."""
    first = await client.post("/api/v1/demands/DEM-900/transitions", json={"destination": "triaged", "expected_version": 0})
    assert first.status_code == 200
    assert first.json()["data"]["state"] == "triaged"
    assert first.json()["data"]["history"][-1]["from_state"] == "submitted"
    stale = await client.post("/api/v1/demands/DEM-900/transitions", json={"destination": "in_progress", "expected_version": 0})
    assert stale.status_code == 409

    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    persisted = await mongo.get_database(settings.mongodb_db).demands.find_one({"demand_id": "DEM-900"})
    audit = await mongo.get_database(settings.mongodb_db).certification_audit.find_one({"aggregate_id": "DEM-900"})
    await mongo.close()
    assert persisted is not None and persisted["version"] == 1
    assert audit is not None and audit["action"] == "transitioned"


@pytest.mark.asyncio
async def test_transition_rejects_invalid_path_and_blank_terminal_note(client: httpx.AsyncClient) -> None:
    """Reject terminal evidence gaps and impossible state changes."""
    missing_note = await client.post("/api/v1/demands/DEM-901/transitions", json={"destination": "cancelled", "expected_version": 0, "resolution_note": "   "})
    assert missing_note.status_code == 422
    invalid_path = await client.post("/api/v1/demands/DEM-901/transitions", json={"destination": "completed", "expected_version": 0, "resolution_note": "Evidence reviewed"})
    assert invalid_path.status_code == 409


@pytest.mark.asyncio
async def test_readiness_persists_weighted_snapshot_and_blocks_unwaived_gate_failure(client: httpx.AsyncClient) -> None:
    """Store explainable readiness evidence and force a blocked recommendation."""
    response = await client.post("/api/v1/releases/REL-42/readiness", json={"expected_version": 0, "applicable_gate_count": 4, "passed_gate_count": 3, "unwaived_gate_failures": 1, "test_pass_rate": 96, "open_defect_count": 2, "critical_defect_count": 0, "automation_coverage": 80})
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["weights"] == {"gates": 0.4, "tests": 0.3, "defects": 0.15, "automation": 0.15}
    assert data["recommendation"] == "Blocked"
    assert data["score"] == 84.3

    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    snapshot = await mongo.get_database(settings.mongodb_db).readiness_snapshots.find_one({"release_id": "REL-42"})
    await mongo.close()
    assert snapshot is not None and snapshot["inputs"]["expected_version"] == 0


@pytest.mark.asyncio
async def test_readiness_rejects_more_passed_than_applicable_gates(client: httpx.AsyncClient) -> None:
    """Reject an internally inconsistent readiness submission."""
    response = await client.post("/api/v1/releases/REL-43/readiness", json={"expected_version": 0, "applicable_gate_count": 1, "passed_gate_count": 2, "unwaived_gate_failures": 0, "test_pass_rate": 100, "open_defect_count": 0, "critical_defect_count": 0, "automation_coverage": 100})
    assert response.status_code == 422
