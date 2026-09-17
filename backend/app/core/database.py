"""Own MongoDB lifecycle and collection indexes."""

import logging
from typing import AsyncIterator

from fastapi import FastAPI, Request
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

from app.core.config import Settings

logger = logging.getLogger(__name__)


async def create_indexes(database: AsyncDatabase) -> None:
    """Create indexes needed by governed portfolio reads and writes.

    Args:
        database: Active Mongo database.
    """
    await database.applications.create_index("business_id", unique=True)
    await database.applications.create_index([("segment_id", ASCENDING), ("name", ASCENDING)])
    await database.applications.create_index([("created.at", DESCENDING)])
    await database.audit_events.create_index([("entity_id", ASCENDING), ("at", DESCENDING)])


async def connect_database(app: FastAPI, settings: Settings) -> None:
    """Create the pooled asynchronous client inside the FastAPI lifespan.

    Args:
        app: Running FastAPI application receiving state.
        settings: Validated connection configuration.

    Raises:
        RuntimeError: If MongoDB is unavailable during startup.
    """
    client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        database = client.get_database(settings.mongodb_db)
        await create_indexes(database)
    except (OperationFailure, TimeoutError) as exc:
        await client.close()
        raise RuntimeError("MongoDB is unavailable; configure MONGODB_URI and MONGODB_DB") from exc
    app.state.mongo_client = client
    app.state.database = database


async def disconnect_database(app: FastAPI) -> None:
    """Close the lifespan-owned MongoDB client.

    Args:
        app: FastAPI application holding the pooled client.
    """
    client: AsyncMongoClient | None = getattr(app.state, "mongo_client", None)
    if client is not None:
        await client.close()


def get_database(request: Request) -> AsyncDatabase:
    """Return the active application database.

    Args:
        request: Current FastAPI request.

    Returns:
        Lifespan-created MongoDB database handle.
    """
    return request.app.state.database
