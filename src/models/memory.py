"""Pydantic models for memory units.

From technical-reference.md Section 8.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class PreferenceData(BaseModel):
    """Structured data for preference memories (semantic memory)."""

    area: str  # "dining", "travel", "fitness", "cars", "clothes", etc.
    priority: str  # "high" | "low"


class SnapshotData(BaseModel):
    """Structured data for snapshot memories (episodic memory)."""

    as_of_date: str  # "2026-02"
    income: float
    fixed_expenses: float
    discretionary: float
    investments: float
    top_categories: dict[str, float]


class MismatchData(BaseModel):
    """Mismatch details within a flag."""

    stated_priority: str  # "cars:low", "fitness:high"
    actual_spending: float


class FlagData(BaseModel):
    """Structured data for flag memories (working memory)."""

    flag_type: str  # "spending_mismatch"
    severity: str  # "high" | "medium" | "low"
    mismatch: MismatchData


class MemoryUnit(BaseModel):
    """Base memory unit — shared fields across all collections."""

    user_id: str
    subject: str
    fact: str
    embedding: list[float] = Field(default_factory=list)
    citations: list = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Preference(MemoryUnit):
    """Preference memory (semantic memory).

    Long-term user values and priorities.
    No expiration — permanent until contradicted.
    """

    structured_data: PreferenceData


class Snapshot(MemoryUnit):
    """Snapshot memory (episodic memory).

    Computed summaries of events (e.g., monthly spending).
    Uses supersedes chain for versioning.
    """

    structured_data: SnapshotData
    supersedes: Optional[str] = None  # ObjectId as string


class Flag(MemoryUnit):
    """Flag memory (working memory).

    Short-term agent-inferred insights.
    Auto-expires via MongoDB TTL index on expires_at.
    """

    structured_data: FlagData
    expires_at: datetime


class ExtractionResult(BaseModel):
    """What the extraction prompt returns from Claude."""

    collection: str  # "preferences" | "flags"
    subject: str
    fact: str
    structured_data: dict
    citations: list[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = None
