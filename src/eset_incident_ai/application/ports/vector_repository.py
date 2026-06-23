from __future__ import annotations

from typing import Protocol

from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.rag.document_factory import KnowledgeDocument
from eset_incident_ai.rag.indexer import ChunkRecord


class VectorRepository(Protocol):
    async def index_document(
        self,
        *,
        document: KnowledgeDocument,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]],
    ) -> None: ...

    async def search(
        self, *, query: str, tenant_scope: str, limit: int
    ) -> list[RetrievedEvidence]: ...
