from __future__ import annotations

from pydantic import BaseModel, Field


class IncidentCollectionResult(BaseModel):
    collected_count: int = 0
    notified_count: int = 0
    duplicate_skipped_count: int = 0
    pending_approval_count: int = 0
    skipped_count: int = 0
    observed_keys: list[str] = Field(default_factory=list)


class DetectionCollectionResult(BaseModel):
    collected_count: int = 0
    notified_count: int = 0
    duplicate_skipped_count: int = 0
    pending_approval_count: int = 0
    skipped_count: int = 0
    observed_keys: list[str] = Field(default_factory=list)
