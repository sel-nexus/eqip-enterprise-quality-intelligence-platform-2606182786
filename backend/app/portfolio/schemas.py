"""Define Pydantic contracts for governed portfolio applications."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Criticality = Literal["low", "medium", "high", "critical"]
Tier = Literal["tier-1", "tier-2", "tier-3"]
Health = Literal["green", "amber", "red"]


class ApplicationCreate(BaseModel):
    """Validate the command used to create a governed application."""

    name: str = Field(min_length=1, max_length=160)
    segment_id: str = Field(min_length=1, max_length=80)
    product: str = Field(min_length=1, max_length=120)
    criticality: Criticality
    tier: Tier
    owners: list[str] = Field(min_length=1, max_length=25)
    technology: list[str] = Field(min_length=1, max_length=30)
    health: Health
    expected_version: int = Field(ge=0, le=0)

    @field_validator("name", "segment_id", "product")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Normalize text and reject whitespace-only command values.

        Args:
            value: Submitted text value.

        Returns:
            Trimmed text.

        Raises:
            ValueError: If text is empty after trimming.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be empty.")
        return normalized

    @field_validator("owners", "technology")
    @classmethod
    def normalize_nonempty_list(cls, values: list[str]) -> list[str]:
        """Trim list values and reject blank entries.

        Args:
            values: Submitted string values.

        Returns:
            Normalized values.

        Raises:
            ValueError: If any submitted list item is blank.
        """
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("List values must not be empty.")
        return normalized


class ApplicationRecord(BaseModel):
    """Expose a persisted governed application without Mongo internals."""

    model_config = ConfigDict(from_attributes=True)

    application_id: str
    name: str
    segment_id: str
    product: str
    criticality: Criticality
    tier: Tier
    owners: list[str]
    technology: list[str]
    health: Health
    lifecycle: Literal["active"]
    version: int
    created_at: datetime
    updated_at: datetime


class CreateApplicationResponse(BaseModel):
    """Wrap a created application with its request correlation id."""

    data: ApplicationRecord
    correlation_id: str


class ApplicationListData(BaseModel):
    """Describe bounded application collection results."""

    items: list[ApplicationRecord]
    total: int


class ApplicationListResponse(BaseModel):
    """Wrap a bounded application collection response."""

    data: ApplicationListData
    correlation_id: str
