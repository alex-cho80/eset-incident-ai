from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CollectionRunDTO(BaseModel):
    run_id: int
    status: str
    collected_count: int
    notified_count: int
    duplicate_skipped_count: int
    pending_approval_count: int
    skipped_count: int
    observed_keys: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime


class DetectionCollectionRunDTO(BaseModel):
    run_id: int
    status: str
    collected_count: int
    notified_count: int
    duplicate_skipped_count: int
    pending_approval_count: int
    skipped_count: int
    observed_keys: list[str] = Field(default_factory=list)
    error_message: str | None = None
    last_page_token: str | None = None
    created_at: datetime
