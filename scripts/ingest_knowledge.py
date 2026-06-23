from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from eset_incident_ai.infrastructure.embeddings.local_embedder import LocalEmbedder
from eset_incident_ai.infrastructure.persistence.vector_repository import PgVectorRepository
from eset_incident_ai.rag.chunker import TextChunker
from eset_incident_ai.rag.file_loader import document_from_file, iter_files
from eset_incident_ai.rag.indexer import RagIndexer
from eset_incident_ai.settings.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest local knowledge files into retrieval storage."
    )
    parser.add_argument(
        "--root",
        default="knowledge",
        help="Knowledge directory containing markdown or text files.",
    )
    parser.add_argument("--max-chars", type=int, default=1200, help="Maximum chunk size.")
    parser.add_argument("--overlap-chars", type=int, default=150, help="Chunk overlap size.")
    return parser.parse_args()


async def ingest(root: Path, *, max_chars: int, overlap_chars: int) -> int:
    settings = Settings()
    embedder = LocalEmbedder()
    repository = PgVectorRepository(settings.database_url, embedder=embedder)
    indexer = RagIndexer(TextChunker(max_chars=max_chars, overlap_chars=overlap_chars))

    indexed_count = 0
    for path in iter_files(root):
        document = document_from_file(path, root=root)
        chunks = indexer.build_chunks(document)
        if not chunks:
            continue
        embeddings = await embedder.embed([chunk.content for chunk in chunks])
        await repository.index_document(
            document=document,
            chunks=chunks,
            embeddings=embeddings,
        )
        indexed_count += 1
        print(f"indexed path={path.relative_to(root).as_posix()} chunks={len(chunks)}")
    return indexed_count


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    if not root.exists():
        print(f"knowledge_root_missing path={root}")
        return 1

    indexed_count = asyncio.run(
        ingest(root, max_chars=args.max_chars, overlap_chars=args.overlap_chars)
    )
    print(f"knowledge_ingest_ok documents={indexed_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
