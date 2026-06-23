from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RetrievedEvidence(BaseModel):
    evidence_id: str
    source_type: str
    source_id: str
    title: str
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    occurred_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
