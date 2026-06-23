from __future__ import annotations

from pydantic import BaseModel, Field


class ReadinessDTO(BaseModel):
    status: str
    checks: dict[str, str] = Field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"
