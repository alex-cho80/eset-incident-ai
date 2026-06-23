from __future__ import annotations

import asyncio
from urllib.parse import urlsplit, urlunsplit

import psycopg
import redis.asyncio as redis


class ServiceReadinessProbe:
    def __init__(self, *, database_url: str, redis_url: str, timeout_seconds: float = 2.0) -> None:
        self._database_url = self._normalize_database_url(database_url)
        self._redis_url = redis_url
        self._timeout_seconds = timeout_seconds

    async def check(self) -> dict[str, str]:
        database, cache = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
        )
        return {"database": database, "redis": cache}

    async def _check_database(self) -> str:
        try:
            connection = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(self._database_url),
                timeout=self._timeout_seconds,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT 1")
            return "ok"
        except Exception:
            return "failed"

    async def _check_redis(self) -> str:
        client = redis.from_url(
            self._redis_url,
            socket_connect_timeout=self._timeout_seconds,
            socket_timeout=self._timeout_seconds,
        )
        try:
            await client.ping()
            return "ok"
        except Exception:
            return "failed"
        finally:
            await client.aclose()

    def _normalize_database_url(self, database_url: str) -> str:
        parts = urlsplit(database_url)
        scheme = parts.scheme.replace("+psycopg", "")
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
