from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eset_incident_ai.api.routes.incidents import latest_collection_run, list_collection_runs
from eset_incident_ai.application.dto.collection_run_dto import CollectionRunDTO
from eset_incident_ai.application.use_cases.list_collection_runs import ListCollectionRuns


class FakeCollectionRunRepository:
    async def save_success(self, result: object) -> None:
        _ = result

    async def save_failure(self, *, error_message: str) -> None:
        _ = error_message

    async def list_recent(self, *, limit: int) -> list[CollectionRunDTO]:
        return [
            CollectionRunDTO(
                run_id=limit,
                status="succeeded",
                collected_count=10,
                notified_count=1,
                duplicate_skipped_count=9,
                pending_approval_count=0,
                skipped_count=0,
                observed_keys=["uuid"],
                created_at=datetime.now(UTC),
            )
        ]

    async def latest(self) -> CollectionRunDTO | None:
        return (await self.list_recent(limit=1))[0]


@pytest.mark.asyncio
async def test_list_collection_runs_use_case() -> None:
    result = await ListCollectionRuns(FakeCollectionRunRepository()).list_recent(limit=3)

    assert result[0].run_id == 3


@pytest.mark.asyncio
async def test_collection_run_route_handlers() -> None:
    use_case = ListCollectionRuns(FakeCollectionRunRepository())

    latest = await latest_collection_run(use_case=use_case)
    recent = await list_collection_runs(use_case=use_case, limit=2)

    assert latest is not None
    assert latest.run_id == 1
    assert recent[0].run_id == 2
