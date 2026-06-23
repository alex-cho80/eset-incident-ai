from __future__ import annotations

import pytest

from eset_incident_ai.application.use_cases.check_readiness import CheckReadiness
from eset_incident_ai.infrastructure.observability import readiness
from eset_incident_ai.infrastructure.observability.readiness import ServiceReadinessProbe


class FakeReadinessProbe:
    def __init__(self, checks: dict[str, str]) -> None:
        self._checks = checks

    async def check(self) -> dict[str, str]:
        return self._checks


class FakeCursor:
    async def __aenter__(self) -> FakeCursor:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        _ = (exc_type, exc, traceback)

    async def execute(self, query: str) -> None:
        _ = query


class FakeDatabaseConnection:
    async def __aenter__(self) -> FakeDatabaseConnection:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        _ = (exc_type, exc, traceback)

    def cursor(self) -> FakeCursor:
        return FakeCursor()


class FakeRedisClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.closed = False

    async def ping(self) -> None:
        if self.fail:
            raise ConnectionError("redis unavailable")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_check_readiness_returns_ready_when_all_checks_pass() -> None:
    result = await CheckReadiness(FakeReadinessProbe({"database": "ok", "redis": "ok"})).execute()

    assert result.status == "ready"
    assert result.is_ready is True


@pytest.mark.asyncio
async def test_check_readiness_returns_not_ready_when_any_check_fails() -> None:
    result = await CheckReadiness(
        FakeReadinessProbe({"database": "ok", "redis": "failed"})
    ).execute()

    assert result.status == "not_ready"
    assert result.is_ready is False


def test_service_readiness_probe_normalizes_database_url() -> None:
    probe = ServiceReadinessProbe(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        redis_url="redis://redis:6379/0",
    )

    assert (
        probe._normalize_database_url(  # noqa: SLF001
            "postgresql+psycopg://user:pass@postgres:5432/db"
        )
        == "postgresql://user:pass@postgres:5432/db"
    )


@pytest.mark.asyncio
async def test_service_readiness_probe_checks_database_success(monkeypatch) -> None:
    async def connect(database_url: str) -> FakeDatabaseConnection:
        _ = database_url
        return FakeDatabaseConnection()

    monkeypatch.setattr(readiness.psycopg.AsyncConnection, "connect", connect)
    probe = ServiceReadinessProbe(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        redis_url="redis://redis:6379/0",
    )

    assert await probe._check_database() == "ok"  # noqa: SLF001


@pytest.mark.asyncio
async def test_service_readiness_probe_checks_database_failure(monkeypatch) -> None:
    async def connect(database_url: str) -> FakeDatabaseConnection:
        _ = database_url
        raise ConnectionError("database unavailable")

    monkeypatch.setattr(readiness.psycopg.AsyncConnection, "connect", connect)
    probe = ServiceReadinessProbe(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        redis_url="redis://redis:6379/0",
    )

    assert await probe._check_database() == "failed"  # noqa: SLF001


@pytest.mark.asyncio
async def test_service_readiness_probe_checks_redis_success(monkeypatch) -> None:
    client = FakeRedisClient()
    monkeypatch.setattr(readiness.redis, "from_url", lambda *args, **kwargs: client)
    probe = ServiceReadinessProbe(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        redis_url="redis://redis:6379/0",
    )

    assert await probe._check_redis() == "ok"  # noqa: SLF001
    assert client.closed is True


@pytest.mark.asyncio
async def test_service_readiness_probe_checks_redis_failure(monkeypatch) -> None:
    client = FakeRedisClient(fail=True)
    monkeypatch.setattr(readiness.redis, "from_url", lambda *args, **kwargs: client)
    probe = ServiceReadinessProbe(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        redis_url="redis://redis:6379/0",
    )

    assert await probe._check_redis() == "failed"  # noqa: SLF001
    assert client.closed is True


@pytest.mark.asyncio
async def test_service_readiness_probe_combines_checks(monkeypatch) -> None:
    async def check_database() -> str:
        return "ok"

    async def check_redis() -> str:
        return "failed"

    probe = ServiceReadinessProbe(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        redis_url="redis://redis:6379/0",
    )
    monkeypatch.setattr(probe, "_check_database", check_database)
    monkeypatch.setattr(probe, "_check_redis", check_redis)

    assert await probe.check() == {"database": "ok", "redis": "failed"}
