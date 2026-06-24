from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class DetectionPage:
    detections: list[dict[str, Any]]
    next_page_token: str | None


class DetectionSource(Protocol):
    async def get_detection_page(
        self,
        *,
        page_token: str | None = None,
        page_size: int,
    ) -> DetectionPage: ...

    def iter_detections(
        self,
        *,
        page_token: str | None = None,
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]: ...
