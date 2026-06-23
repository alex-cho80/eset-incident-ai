from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.infrastructure.embeddings.local_embedder import LocalEmbedder
from eset_incident_ai.infrastructure.persistence.vector_repository import PgVectorRepository
from eset_incident_ai.rag.chunker import TextChunker
from eset_incident_ai.rag.document_factory import IncidentDocumentFactory, KnowledgeDocument
from eset_incident_ai.rag.file_loader import document_from_file, first_heading, iter_files
from eset_incident_ai.rag.indexer import RagIndexer
from eset_incident_ai.rag.retriever import Retriever


class FakeVectorRepository:
    def __init__(self) -> None:
        self.query: str | None = None

    async def index_document(
        self,
        *,
        document: KnowledgeDocument,
        chunks: object,
        embeddings: object,
    ) -> None:
        _ = (document, chunks, embeddings)

    async def search(self, *, query: str, tenant_scope: str, limit: int) -> list[RetrievedEvidence]:
        _ = (tenant_scope, limit)
        self.query = query
        return [
            RetrievedEvidence(
                evidence_id="evidence-1",
                source_type="knowledge",
                source_id="runbook.md",
                title="Runbook",
                excerpt="Restart the worker",
                relevance_score=0.9,
                occurred_at=datetime.now(UTC),
            )
        ]


@pytest.mark.asyncio
async def test_local_embedder_returns_normalized_deterministic_vectors() -> None:
    embedder = LocalEmbedder(dimensions=8)

    first = await embedder.embed(["ESET incident response"])
    second = await embedder.embed(["ESET incident response"])

    assert first == second
    assert len(first[0]) == 8
    assert any(value != 0 for value in first[0])


@pytest.mark.asyncio
async def test_local_embedder_returns_zero_vector_for_empty_text() -> None:
    assert await LocalEmbedder(dimensions=4).embed([""]) == [[0.0, 0.0, 0.0, 0.0]]


def test_text_chunker_splits_with_overlap() -> None:
    chunks = TextChunker(max_chars=5, overlap_chars=2).chunk("abcdefghij")

    assert chunks == ["abcde", "defgh", "ghij"]
    assert TextChunker().chunk("") == []


def test_text_chunker_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        TextChunker(max_chars=10, overlap_chars=10)


def test_rag_indexer_builds_chunk_records() -> None:
    document = KnowledgeDocument(
        source_type="knowledge",
        source_id="runbook.md",
        title="Runbook",
        content="abcdefghij",
        metadata={"category": "runbooks"},
    )

    chunks = RagIndexer(TextChunker(max_chars=5, overlap_chars=2)).build_chunks(document)

    assert chunks[0].source_id == "runbook.md"
    assert chunks[0].chunk_index == 0
    assert chunks[0].metadata == {"category": "runbooks"}


def test_incident_document_factory_builds_knowledge_document() -> None:
    incident = Incident(
        id="internal-1",
        external_id="incident-1",
        title="Malware detected",
        severity=Severity.HIGH,
        detected_at=None,
        summary="Endpoint detection",
        normalized_payload={},
    )

    document = IncidentDocumentFactory().from_incident(incident)

    assert document.source_type == "incident"
    assert document.source_id == "incident-1"
    assert document.metadata["severity"] == "high"


def test_ingest_helpers_build_documents_from_files(tmp_path) -> None:
    runbook = tmp_path / "runbooks" / "collector.md"
    runbook.parent.mkdir()
    runbook.write_text("# Collector Failure\nRestart the worker", encoding="utf-8")
    ignored = tmp_path / "ignored.json"
    ignored.write_text("{}", encoding="utf-8")

    assert iter_files(tmp_path) == [runbook]
    assert first_heading(runbook.read_text(encoding="utf-8")) == "Collector Failure"

    document = document_from_file(runbook, root=tmp_path)

    assert document.source_type == "knowledge"
    assert document.source_id == "runbooks/collector.md"
    assert document.title == "Collector Failure"
    assert document.metadata["category"] == "runbooks"


def test_ingest_document_uses_hash_for_long_source_id(tmp_path) -> None:
    deep = tmp_path / ("a" * 80) / ("b" * 80)
    deep.mkdir(parents=True)
    document_path = deep / "collector.md"
    document_path.write_text("Collector content", encoding="utf-8")

    document = document_from_file(document_path, root=tmp_path)

    assert len(document.source_id) == 64
    assert document.metadata["path"].endswith("collector.md")


def test_vector_repository_scores_cosine_similarity() -> None:
    repository = PgVectorRepository("postgresql+psycopg://user:pass@postgres:5432/db")

    assert repository._cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0  # noqa: SLF001
    assert repository._cosine_similarity([], [1.0]) == 0.0  # noqa: SLF001
    assert (
        repository._normalize_database_url(  # noqa: SLF001
            "postgresql+psycopg://user:pass@postgres:5432/db"
        )
        == "postgresql://user:pass@postgres:5432/db"
    )


@pytest.mark.asyncio
async def test_retriever_delegates_to_vector_repository() -> None:
    repository = FakeVectorRepository()
    result = await Retriever(repository).retrieve(
        query="collector failure",
        tenant_scope="default",
        limit=3,
    )

    assert repository.query == "collector failure"
    assert result[0].evidence_id == "evidence-1"
