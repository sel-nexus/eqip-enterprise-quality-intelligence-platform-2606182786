"""Read and write governed applications through real MongoDB collections."""

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase


class ApplicationRepository:
    """Encapsulate bounded MongoDB application persistence."""

    def __init__(self, database: AsyncDatabase) -> None:
        """Store the database backing application documents.

        Args:
            database: Active MongoDB database.
        """
        self._collection = database.applications

    async def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        """Persist and return a governed application document.

        Args:
            document: Fully validated application document.

        Returns:
            Persisted application document.
        """
        result = await self._collection.insert_one(document)
        created = await self._collection.find_one({"_id": result.inserted_id})
        if created is None:
            raise RuntimeError("Application insert did not return a persisted document.")
        return created

    async def list_for_actor(self, actor_id: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        """Read a bounded, newest-first page visible to one owning actor.

        Args:
            actor_id: Authenticated actor permitted to read the records.
            limit: Maximum number of documents to return.
            offset: Number of documents to skip.

        Returns:
            Actor-scoped application documents and complete matching count.
        """
        scope = {"owner_actor_id": actor_id}
        cursor = self._collection.find(scope, {"_id": 0}).sort("created.at", -1).skip(offset).limit(limit)
        return await cursor.to_list(length=limit), await self._collection.count_documents(scope)
