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

    async def list(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        """Read a bounded, newest-first page of applications.

        Args:
            limit: Maximum number of documents to return.
            offset: Number of documents to skip.

        Returns:
            Page of application documents and complete count.
        """
        cursor = self._collection.find({}, {"_id": 0}).sort("created.at", -1).skip(offset).limit(limit)
        return await cursor.to_list(length=limit), await self._collection.count_documents({})
