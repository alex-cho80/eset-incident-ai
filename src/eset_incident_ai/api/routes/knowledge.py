from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from eset_incident_ai.api.dependencies import get_search_knowledge
from eset_incident_ai.application.use_cases.search_knowledge import SearchKnowledge
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/search")
async def search_knowledge(
    use_case: Annotated[SearchKnowledge, Depends(get_search_knowledge)],
    query: str = Query(min_length=1, max_length=500),
    tenant_scope: str = Query(default="default", min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[RetrievedEvidence]:
    return await use_case.execute(
        query=query,
        tenant_scope=tenant_scope,
        limit=limit,
    )
