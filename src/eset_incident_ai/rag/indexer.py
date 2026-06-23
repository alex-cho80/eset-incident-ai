from __future__ import annotations

from dataclasses import dataclass

from eset_incident_ai.rag.chunker import TextChunker
from eset_incident_ai.rag.document_factory import KnowledgeDocument


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    source_id: str
    chunk_index: int
    content: str
    metadata: dict[str, str]


class RagIndexer:
    def __init__(self, chunker: TextChunker) -> None:
        self._chunker = chunker

    def build_chunks(self, document: KnowledgeDocument) -> list[ChunkRecord]:
        return [
            ChunkRecord(
                source_id=document.source_id,
                chunk_index=index,
                content=content,
                metadata=document.metadata,
            )
            for index, content in enumerate(self._chunker.chunk(document.content))
        ]
