from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import psycopg


class PostgresNotificationRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = self._normalize_database_url(database_url)

    async def was_delivered(self, idempotency_key: str) -> bool:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT 1
                    FROM notification_deliveries
                    WHERE idempotency_key = %s
                    LIMIT 1
                    """,
                    (idempotency_key,),
                )
                return await cursor.fetchone() is not None

    async def mark_delivered(self, *, idempotency_key: str, destination: str) -> None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO notification_deliveries (
                        idempotency_key,
                        destination,
                        delivery_status,
                        delivered_at
                    )
                    VALUES (%s, %s, 'delivered', NOW())
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (idempotency_key, destination),
                )

    async def _ensure_table(self) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notification_deliveries (
                        id BIGSERIAL PRIMARY KEY,
                        idempotency_key VARCHAR(255) NOT NULL UNIQUE,
                        destination VARCHAR(100) NOT NULL,
                        delivery_status VARCHAR(30) NOT NULL,
                        delivered_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

    def _normalize_database_url(self, database_url: str) -> str:
        parts = urlsplit(database_url)
        scheme = parts.scheme.replace("+psycopg", "")
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
