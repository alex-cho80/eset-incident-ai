from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EsetIncidentPayload(BaseModel):
    uuid: str = Field(alias="id")
    title: str = "Untitled incident"
    severity: str = "low"
    updated_at: datetime | None = None
    raw: dict[str, object] = Field(default_factory=dict)
