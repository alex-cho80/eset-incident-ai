from __future__ import annotations

import pytest

from eset_incident_ai.api.routes.incidents import (
    CollectIncidentsRequest,
    collect_and_notify_incidents,
)
from eset_incident_ai.application.dto.collection_result import IncidentCollectionResult


class FakeCollectAndNotify:
    async def execute(self, *, limit: int, updated_after: str | None) -> IncidentCollectionResult:
        return IncidentCollectionResult(
            collected_count=limit,
            notified_count=1,
            duplicate_skipped_count=0,
            pending_approval_count=0,
            skipped_count=0,
            observed_keys=[updated_after or "none"],
        )


@pytest.mark.asyncio
async def test_collect_and_notify_route_handler() -> None:
    result = await collect_and_notify_incidents(
        request=CollectIncidentsRequest(limit=3, updated_after="2026-06-23T00:00:00Z"),
        use_case=FakeCollectAndNotify(),  # type: ignore[arg-type]
    )

    assert result.collected_count == 3
    assert result.observed_keys == ["2026-06-23T00:00:00Z"]
