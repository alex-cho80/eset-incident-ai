from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class IncidentSource(Protocol):
    def iter_incidents(
        self, *, updated_after: str | None, page_size: int
    ) -> AsyncIterator[dict[str, Any]]: ...

    async def get_incident(self, incident_uuid: str) -> dict[str, Any]: ...
