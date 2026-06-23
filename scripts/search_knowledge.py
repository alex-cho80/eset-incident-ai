from __future__ import annotations

import argparse
import asyncio

from eset_incident_ai.application.use_cases.search_knowledge import SearchKnowledge
from eset_incident_ai.infrastructure.persistence.vector_repository import PgVectorRepository
from eset_incident_ai.settings.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search indexed local knowledge.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--tenant-scope", default="default", help="Tenant scope label.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum search results.")
    return parser.parse_args()


async def run(query: str, *, tenant_scope: str, limit: int) -> None:
    settings = Settings()
    results = await SearchKnowledge(PgVectorRepository(settings.database_url)).execute(
        query=query,
        tenant_scope=tenant_scope,
        limit=limit,
    )
    for index, evidence in enumerate(results, start=1):
        print(
            f"{index}. score={evidence.relevance_score:.3f} "
            f"source={evidence.source_id} title={evidence.title}"
        )
        print(evidence.excerpt.replace("\n", " ")[:240])
    print(f"knowledge_search_ok count={len(results)}")


def main() -> int:
    args = parse_args()
    asyncio.run(run(args.query, tenant_scope=args.tenant_scope, limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
