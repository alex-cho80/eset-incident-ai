from __future__ import annotations

import pytest

from eset_incident_ai.api.routes.knowledge import search_knowledge
from eset_incident_ai.application.use_cases.search_knowledge import SearchKnowledge
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence


class FakeVectorRepository:
    async def index_document(self, *, document: object, chunks: object, embeddings: object) -> None:
        _ = (document, chunks, embeddings)

    async def search(self, *, query: str, tenant_scope: str, limit: int) -> list[RetrievedEvidence]:
        return [
            RetrievedEvidence(
                evidence_id=f"{tenant_scope}-{limit}",
                source_type="knowledge",
                source_id="runbooks/collector-failure.md",
                title=f"Result for {query}",
                excerpt="Check worker logs",
                relevance_score=0.8,
            )
        ]


@pytest.mark.asyncio
async def test_search_knowledge_use_case() -> None:
    result = await SearchKnowledge(FakeVectorRepository()).execute(
        query="collector failure",
        tenant_scope="default",
        limit=3,
    )

    assert result[0].evidence_id == "default-3"


@pytest.mark.asyncio
async def test_search_knowledge_route_handler() -> None:
    result = await search_knowledge(
        use_case=SearchKnowledge(FakeVectorRepository()),
        query="discord delivery",
        tenant_scope="tenant-a",
        limit=2,
    )

    assert result[0].title == "Result for discord delivery"
