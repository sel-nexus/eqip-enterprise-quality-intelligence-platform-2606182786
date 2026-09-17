"""Verify cross-feature workflow consistency using real MongoDB."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient

os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:27017")
os.environ.setdefault("MONGODB_DB", f"eqip_readiness_integration_{uuid4().hex}")
os.environ.setdefault("AUTH_MODE", "development")
os.environ.setdefault("DEVELOPMENT_USER_ID", "integration-actor")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.core.config import get_settings
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def reset_workflow_data() -> AsyncIterator[None]:
    """Clean all collections traversed by each cross-feature journey."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    for name in ("applications", "audit_events", "demands", "readiness_snapshots", "certification_audit"):
        await database.get_collection(name).delete_many({})
    try:
        yield
    finally:
        await mongo.drop_database(settings.mongodb_db)
        await mongo.close()


@pytest.mark.asyncio
async def test_portfolio_to_owned_demand_to_readiness_journey_persists_all_records() -> None:
    """Chain an actor's portfolio registration, demand, and readiness snapshot."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    await database.demands.insert_one({"demand_id": "DEM-INTEGRATION", "owner_actor_id": "integration-actor", "state": "submitted", "version": 0, "resolution_note": None, "history": [], "updated_at": datetime.now(UTC)})
    await mongo.close()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            actor_headers = {"X-Dev-User": "integration-actor"}
            application = await client.post("/api/v1/applications", json={"name": "Readiness Portal", "segment_id": "SEG-QUALITY", "product": "Release", "criticality": "high", "tier": "tier-1", "owners": ["integration-actor"], "technology": ["React"], "health": "green", "expected_version": 0}, headers=actor_headers)
            triaged = await client.post("/api/v1/demands/DEM-INTEGRATION/transitions", json={"destination": "triaged", "expected_version": 0}, headers=actor_headers)
            readiness = await client.post("/api/v1/releases/REL-INTEGRATION/readiness", json={"expected_version": 0, "applicable_gate_count": 2, "passed_gate_count": 2, "unwaived_gate_failures": 0, "test_pass_rate": 100, "open_defect_count": 0, "critical_defect_count": 0, "automation_coverage": 100}, headers=actor_headers)
    assert application.status_code == 201 and triaged.status_code == 200
    assert readiness.status_code == 200 and readiness.json()["data"]["recommendation"] == "Ready"


@pytest.mark.asyncio
async def test_cross_scope_failure_keeps_all_collections_and_audits_consistent() -> None:
    """Verify a denied cross-scope mutation creates no partial state or audit event."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    timestamp = datetime.now(UTC)
    await database.demands.insert_one({"demand_id": "DEM-FOREIGN", "owner_actor_id": "actor-a", "state": "submitted", "version": 0, "resolution_note": None, "history": [], "updated_at": timestamp})
    await mongo.close()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/demands/DEM-FOREIGN/transitions", json={"destination": "triaged", "expected_version": 0}, headers={"X-Dev-User": "actor-b"})
    assert response.status_code == 403
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    demand = await database.demands.find_one({"demand_id": "DEM-FOREIGN"})
    assert demand is not None and demand["state"] == "submitted" and demand["version"] == 0
    assert await database.applications.count_documents({}) == 0
    assert await database.audit_events.count_documents({}) == 0
    assert await database.readiness_snapshots.count_documents({}) == 0
    assert await database.certification_audit.count_documents({}) == 0
    await mongo.close()


@pytest.mark.asyncio
async def test_failed_cross_scope_demand_transition_does_not_block_readiness_or_leave_orphans() -> None:
    """Reject an upstream demand mutation, then persist an independent readiness result cleanly."""
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    timestamp = datetime.now(UTC)
    await database.demands.insert_one(
        {
            "demand_id": "DEM-RECOVERY-FOREIGN",
            "owner_actor_id": "demand-owner",
            "state": "submitted",
            "version": 0,
            "resolution_note": None,
            "history": [],
            "updated_at": timestamp,
        }
    )
    await mongo.close()

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            denied_transition = await client.post(
                "/api/v1/demands/DEM-RECOVERY-FOREIGN/transitions",
                json={"destination": "triaged", "expected_version": 0},
                headers={"X-Dev-User": "other-actor"},
            )
            readiness = await client.post(
                "/api/v1/releases/REL-RECOVERY/readiness",
                json={
                    "expected_version": 0,
                    "applicable_gate_count": 2,
                    "passed_gate_count": 2,
                    "unwaived_gate_failures": 0,
                    "test_pass_rate": 100,
                    "open_defect_count": 0,
                    "critical_defect_count": 0,
                    "automation_coverage": 100,
                },
                headers={"X-Dev-User": "readiness-owner"},
            )

    assert denied_transition.status_code == 403
    assert readiness.status_code == 200
    assert readiness.json()["data"]["recommendation"] == "Ready"
    assert readiness.json()["data"]["version"] == 1

    mongo = AsyncMongoClient(settings.mongodb_uri)
    database = mongo.get_database(settings.mongodb_db)
    demand = await database.demands.find_one({"demand_id": "DEM-RECOVERY-FOREIGN"})
    snapshot = await database.readiness_snapshots.find_one({"release_id": "REL-RECOVERY"})
    readiness_audit = await database.certification_audit.find_one(
        {"aggregate_type": "release", "aggregate_id": "REL-RECOVERY"}
    )
    assert demand is not None
    assert demand["owner_actor_id"] == "demand-owner"
    assert demand["state"] == "submitted"
    assert demand["version"] == 0
    assert demand["history"] == []
    assert snapshot is not None
    assert snapshot["owner_actor_id"] == "readiness-owner"
    assert snapshot["version"] == 1
    assert snapshot["recommendation"] == "Ready"
    assert readiness_audit is not None
    assert readiness_audit["action"] == "readiness_calculated"
    assert readiness_audit["actor"] == "readiness-owner"
    assert await database.demands.count_documents({}) == 1
    assert await database.readiness_snapshots.count_documents({}) == 1
    assert await database.certification_audit.count_documents({"aggregate_type": "demand"}) == 0
    assert await database.certification_audit.count_documents({"aggregate_type": "release"}) == 1
    assert await database.applications.count_documents({}) == 0
    assert await database.audit_events.count_documents({}) == 0
    await mongo.close()
