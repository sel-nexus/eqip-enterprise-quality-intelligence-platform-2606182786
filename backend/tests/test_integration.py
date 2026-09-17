"""Verify the cross-feature portfolio and certification workflow using real MongoDB."""

import os
from collections.abc import AsyncIterator
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
    """Clean all collections the cross-feature journey traverses."""
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
async def test_portfolio_to_demand_to_readiness_journey_persists_all_workflow_records() -> None:
    """Chain application registration, demand execution, and release assessment."""
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            application = await client.post("/api/v1/applications", json={"name": "Readiness Portal", "segment_id": "SEG-QUALITY", "product": "Release", "criticality": "high", "tier": "tier-1", "owners": ["integration-actor"], "technology": ["React"], "health": "green", "expected_version": 0})
            assert application.status_code == 201
            demand_id = f"DEM-{application.json()['data']['application_id']}"
            triaged = await client.post(f"/api/v1/demands/{demand_id}/transitions", json={"destination": "triaged", "expected_version": 0})
            running = await client.post(f"/api/v1/demands/{demand_id}/transitions", json={"destination": "in_progress", "expected_version": 1})
            completed = await client.post(f"/api/v1/demands/{demand_id}/transitions", json={"destination": "completed", "expected_version": 2, "resolution_note": "Release evidence complete"})
            readiness = await client.post("/api/v1/releases/REL-INTEGRATION/readiness", json={"expected_version": 0, "applicable_gate_count": 2, "passed_gate_count": 2, "unwaived_gate_failures": 0, "test_pass_rate": 100, "open_defect_count": 0, "critical_defect_count": 0, "automation_coverage": 100})
    assert triaged.status_code == 200 and running.status_code == 200
    assert completed.json()["data"]["state"] == "completed"
    assert readiness.status_code == 201 and readiness.json()["data"]["recommendation"] == "Ready"
