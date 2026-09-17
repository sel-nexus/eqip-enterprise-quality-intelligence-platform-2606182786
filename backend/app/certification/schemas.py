"""Define validation and response contracts for demand certification workflows."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DemandState = Literal["submitted", "triaged", "in_progress", "completed", "cancelled"]
Recommendation = Literal["Ready", "Conditional", "Blocked"]


class DemandTransitionCommand(BaseModel):
    """Capture an optimistic-locking demand state transition request."""

    destination: DemandState
    expected_version: int = Field(ge=0)
    resolution_note: str | None = Field(default=None, max_length=2000)

    @field_validator("resolution_note")
    @classmethod
    def normalize_resolution_note(cls, value: str | None) -> str | None:
        """Trim optional notes before domain validation evaluates them."""
        return value.strip() if value is not None else None


class DemandRecord(BaseModel):
    """Return the persisted demand state and complete transition history."""

    demand_id: str
    state: DemandState
    version: int
    resolution_note: str | None = None
    history: list[dict[str, object]]
    updated_at: datetime


class DemandTransitionResponse(BaseModel):
    """Wrap a transitioned demand in the API's standard response envelope."""

    data: DemandRecord
    correlation_id: str


class ReadinessRequest(BaseModel):
    """Capture scored release-readiness evidence supplied by the operator."""

    expected_version: int = Field(ge=0)
    applicable_gate_count: int = Field(ge=0)
    passed_gate_count: int = Field(ge=0)
    unwaived_gate_failures: int = Field(ge=0)
    test_pass_rate: float = Field(ge=0, le=100)
    open_defect_count: int = Field(ge=0)
    critical_defect_count: int = Field(ge=0)
    automation_coverage: float = Field(ge=0, le=100)

    @field_validator("passed_gate_count")
    @classmethod
    def ensure_passed_gates_are_applicable(cls, value: int, info: object) -> int:
        """Reject a passed-gate count that exceeds the applicable-gate count."""
        data = getattr(info, "data", {})
        if value > data.get("applicable_gate_count", 0):
            raise ValueError("passed_gate_count cannot exceed applicable_gate_count")
        return value


class ReadinessSnapshot(BaseModel):
    """Return a persisted, explainable readiness calculation."""

    release_id: str
    version: int
    inputs: ReadinessRequest
    weights: dict[str, float]
    score: float
    recommendation: Recommendation
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Wrap a persisted readiness snapshot in the API response envelope."""

    data: ReadinessSnapshot
    correlation_id: str
