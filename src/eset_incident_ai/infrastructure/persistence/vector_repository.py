from __future__ import annotations

import hashlib
import json
import math
import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.types.json import Jsonb

from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.infrastructure.embeddings.base import Embedder
from eset_incident_ai.infrastructure.embeddings.local_embedder import LocalEmbedder
from eset_incident_ai.rag.document_factory import KnowledgeDocument
from eset_incident_ai.rag.indexer import ChunkRecord


class PgVectorRepository:
    def __init__(self, database_url: str, embedder: Embedder | None = None) -> None:
        self._database_url = self._normalize_database_url(database_url)
        self._embedder = embedder or LocalEmbedder()

    async def index_document(
        self,
        *,
        document: KnowledgeDocument,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        await self._ensure_tables()
        content_hash = hashlib.sha256(document.content.encode("utf-8")).hexdigest()
        document_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{document.source_type}:{document.source_id}:{content_hash}",
        )

        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO knowledge_documents (
                        id, source_type, source_id, title, content, metadata, content_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_type, source_id, content_hash) DO UPDATE
                    SET title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata
                    RETURNING id
                    """,
                    (
                        document_id,
                        document.source_type,
                        document.source_id,
                        document.title,
                        document.content,
                        Jsonb(document.metadata),
                        content_hash,
                    ),
                )
                row = await cursor.fetchone()
                stored_document_id = row[0] if row else document_id

                await cursor.execute(
                    "DELETE FROM knowledge_chunks WHERE document_id = %s",
                    (stored_document_id,),
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    chunk_id = uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{stored_document_id}:{chunk.chunk_index}",
                    )
                    await cursor.execute(
                        """
                        INSERT INTO knowledge_chunks (
                            id, document_id, chunk_index, content, metadata, embedding
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            chunk_id,
                            stored_document_id,
                            chunk.chunk_index,
                            chunk.content,
                            Jsonb(chunk.metadata),
                            json.dumps(embedding),
                        ),
                    )

    async def search(self, *, query: str, tenant_scope: str, limit: int) -> list[RetrievedEvidence]:
        _ = tenant_scope
        await self._ensure_tables()
        query_embedding = (await self._embedder.embed([query]))[0]
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT c.id, d.source_type, d.source_id, d.title, c.content,
                           c.metadata, c.embedding
                    FROM knowledge_chunks c
                    JOIN knowledge_documents d ON d.id = c.document_id
                    WHERE c.embedding IS NOT NULL
                    """
                )
                rows = await cursor.fetchall()

        scored = []
        for row in rows:
            embedding = json.loads(str(row[6]))
            score = self._cosine_similarity(query_embedding, embedding)
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)

        return [
            RetrievedEvidence(
                evidence_id=str(row[0]),
                source_type=str(row[1]),
                source_id=str(row[2]),
                title=str(row[3]),
                excerpt=str(row[4])[:1000],
                relevance_score=max(min(score, 1.0), 0.0),
                metadata=dict(row[5] or {}),
            )
            for score, row in scored[:limit]
        ]

    async def _ensure_tables(self) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_documents (
                        id UUID PRIMARY KEY,
                        source_type VARCHAR(50) NOT NULL,
                        source_id VARCHAR(128) NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}',
                        content_hash VARCHAR(64) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (source_type, source_id, content_hash)
                    )
                    """
                )
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_chunks (
                        id UUID PRIMARY KEY,
                        document_id UUID NOT NULL REFERENCES knowledge_documents(id),
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}',
                        embedding TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (document_id, chunk_index)
                    )
                    """
                )

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return (numerator / (left_norm * right_norm) + 1.0) / 2.0

    def _normalize_database_url(self, database_url: str) -> str:
        parts = urlsplit(database_url)
        scheme = parts.scheme.replace("+psycopg", "")
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
