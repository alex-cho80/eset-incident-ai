from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.types.json import Jsonb

from eset_incident_ai.application.dto.collection_result import DetectionCollectionResult
from eset_incident_ai.application.dto.collection_run_dto import DetectionCollectionRunDTO


class PostgresDetectionCollectionRunRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = self._normalize_database_url(database_url)

    async def save_success(
        self,
        result: DetectionCollectionResult,
        *,
        last_page_token: str | None,
    ) -> None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO detection_collection_runs (
                        status,
                        collected_count,
                        notified_count,
                        duplicate_skipped_count,
                        pending_approval_count,
                        skipped_count,
                        observed_keys,
                        last_page_token
                    )
                    VALUES ('succeeded', %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.collected_count,
                        result.notified_count,
                        result.duplicate_skipped_count,
                        result.pending_approval_count,
                        result.skipped_count,
                        Jsonb(result.observed_keys),
                        last_page_token,
                    ),
                )

    async def save_cursor(self, *, last_page_token: str | None) -> None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO detection_collection_runs (
                        status,
                        collected_count,
                        notified_count,
                        duplicate_skipped_count,
                        pending_approval_count,
                        skipped_count,
                        observed_keys,
                        last_page_token
                    )
                    VALUES ('running', 0, 0, 0, 0, 0, '[]', %s)
                    """,
                    (last_page_token,),
                )

    async def save_failure(self, *, error_message: str) -> None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO detection_collection_runs (
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

    async def list_recent(self, *, limit: int) -> list[DetectionCollectionRunDTO]:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, status, collected_count, notified_count,
                           duplicate_skipped_count, pending_approval_count,
                           skipped_count, observed_keys, error_message,
                           last_page_token, created_at
                    FROM detection_collection_runs
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cursor.fetchall()
        return [self._row_to_dto(row) for row in rows]

    async def latest(self) -> DetectionCollectionRunDTO | None:
        runs = await self.list_recent(limit=1)
        return runs[0] if runs else None

    async def _ensure_table(self) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS detection_collection_runs (
                        id BIGSERIAL PRIMARY KEY,
                        status VARCHAR(30) NOT NULL,
                        collected_count INTEGER NOT NULL,
                        notified_count INTEGER NOT NULL,
                        duplicate_skipped_count INTEGER NOT NULL,
                        pending_approval_count INTEGER NOT NULL,
                        skipped_count INTEGER NOT NULL,
                        observed_keys JSONB NOT NULL DEFAULT '[]',
                        error_message TEXT,
                        last_page_token TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

    def _row_to_dto(self, row: tuple[object, ...]) -> DetectionCollectionRunDTO:
        return DetectionCollectionRunDTO.model_validate(
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
                "last_page_token": row[9],
                "created_at": row[10],
            }
        )

    def _normalize_database_url(self, database_url: str) -> str:
        parts = urlsplit(database_url)
        scheme = parts.scheme.replace("+psycopg", "")
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
