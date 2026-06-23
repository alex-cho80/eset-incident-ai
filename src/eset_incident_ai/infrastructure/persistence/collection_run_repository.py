from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.types.json import Jsonb

from eset_incident_ai.application.dto.collection_result import IncidentCollectionResult
from eset_incident_ai.application.dto.collection_run_dto import CollectionRunDTO


class PostgresCollectionRunRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = self._normalize_database_url(database_url)

    async def save_success(self, result: IncidentCollectionResult) -> None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO collection_runs (
                        status,
                        collected_count,
                        notified_count,
                        duplicate_skipped_count,
                        pending_approval_count,
                        skipped_count,
                        observed_keys
                    )
                    VALUES ('succeeded', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.collected_count,
                        result.notified_count,
                        result.duplicate_skipped_count,
                        result.pending_approval_count,
                        result.skipped_count,
                        Jsonb(result.observed_keys),
                    ),
                )

    async def save_failure(self, *, error_message: str) -> None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO collection_runs (
                        status,
                        collected_count,
                        notified_count,
                        duplicate_skipped_count,
                        pending_approval_count,
                        skipped_count,
                        observed_keys,
                        error_message
                    )
                    VALUES ('failed', 0, 0, 0, 0, 0, '[]', %s)
                    """,
                    (error_message[:500],),
                )

    async def list_recent(self, *, limit: int) -> list[CollectionRunDTO]:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, status, collected_count, notified_count,
                           duplicate_skipped_count, pending_approval_count,
                           skipped_count, observed_keys, error_message, created_at
                    FROM collection_runs
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cursor.fetchall()
        return [self._row_to_dto(row) for row in rows]

    async def latest(self) -> CollectionRunDTO | None:
        runs = await self.list_recent(limit=1)
        return runs[0] if runs else None

    async def _ensure_table(self) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS collection_runs (
                        id BIGSERIAL PRIMARY KEY,
                        status VARCHAR(30) NOT NULL,
                        collected_count INTEGER NOT NULL,
                        notified_count INTEGER NOT NULL,
                        duplicate_skipped_count INTEGER NOT NULL,
                        pending_approval_count INTEGER NOT NULL,
                        skipped_count INTEGER NOT NULL,
                        observed_keys JSONB NOT NULL DEFAULT '[]',
                        error_message TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                await cursor.execute(
                    """
                    ALTER TABLE collection_runs
                    ADD COLUMN IF NOT EXISTS error_message TEXT
                    """
                )

    def _row_to_dto(self, row: tuple[object, ...]) -> CollectionRunDTO:
        return CollectionRunDTO.model_validate(
            {
                "run_id": row[0],
                "status": row[1],
                "collected_count": row[2],
                "notified_count": row[3],
                "duplicate_skipped_count": row[4],
                "pending_approval_count": row[5],
                "skipped_count": row[6],
                "observed_keys": row[7],
                "error_message": row[8],
                "created_at": row[9],
            }
        )

    def _normalize_database_url(self, database_url: str) -> str:
        parts = urlsplit(database_url)
        scheme = parts.scheme.replace("+psycopg", "")
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
