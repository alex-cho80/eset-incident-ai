from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from eset_incident_ai.api.dependencies import (
    get_collect_and_notify_incidents,
    get_list_collection_runs,
)
from eset_incident_ai.application.dto.collection_result import IncidentCollectionResult
from eset_incident_ai.application.dto.collection_run_dto import CollectionRunDTO
from eset_incident_ai.application.use_cases.collect_and_notify_incidents import (
    CollectAndNotifyIncidents,
)
from eset_incident_ai.application.use_cases.list_collection_runs import ListCollectionRuns

router = APIRouter(prefix="/incidents", tags=["incidents"])


class CollectIncidentsRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    updated_after: str | None = None


@router.post("/collect-and-notify")
async def collect_and_notify_incidents(
    request: CollectIncidentsRequest,
    use_case: Annotated[
        CollectAndNotifyIncidents,
        Depends(get_collect_and_notify_incidents),
    ],
) -> IncidentCollectionResult:
    return await use_case.execute(limit=request.limit, updated_after=request.updated_after)


@router.get("/collection-runs/latest")
async def latest_collection_run(
    use_case: Annotated[ListCollectionRuns, Depends(get_list_collection_runs)],
) -> CollectionRunDTO | None:
    return await use_case.latest()


@router.get("/collection-runs")
async def list_collection_runs(
    use_case: Annotated[ListCollectionRuns, Depends(get_list_collection_runs)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CollectionRunDTO]:
    return await use_case.list_recent(limit=limit)


@router.get("/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, str]:
    return {"incident_id": incident_id, "status": "not_implemented"}
