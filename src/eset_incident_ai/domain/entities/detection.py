from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Detection:
    detection_id: str
    name: str
    category: str | None
    occurred_at: datetime | None
    process_name: str | None = None
    file_hash: str | None = None
