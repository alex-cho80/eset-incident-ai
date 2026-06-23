from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.types.json import Jsonb

from eset_incident_ai.application.dto.approval_dto import PendingApprovalDTO
from eset_incident_ai.security.sanitizer import Sanitizer


class PostgresApprovalRepository:
    def __init__(self, *, database_url: str, sanitizer: Sanitizer) -> None:
        self._database_url = self._normalize_database_url(database_url)
        self._sanitizer = sanitizer

    async def save_pending(self, *, incident: dict[str, object], severity: str) -> None:
        await self._ensure_table()
        incident_id = str(incident.get("uuid") or incident.get("displayName") or "unknown")
        title = self._safe_text(incident.get("displayName") or incident_id)
        payload = self._sanitized_payload(incident)
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO pending_approvals (
                        incident_id,
                        severity,
                        title,
                        status,
                        payload
                    )
                    VALUES (%s, %s, %s, 'pending', %s)
                    ON CONFLICT (incident_id) DO UPDATE
                    SET severity = EXCLUDED.severity,
                        title = EXCLUDED.title,
                        payload = EXCLUDED.payload,
                        updated_at = NOW()
                    """,
                    (incident_id, severity, title, Jsonb(payload)),
                )

    async def list_pending(self, *, limit: int) -> list[PendingApprovalDTO]:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, incident_id, severity, title, status, payload
                    FROM pending_approvals
                    WHERE status = 'pending'
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cursor.fetchall()
        return [self._row_to_dto(row) for row in rows]

    async def get_pending(self, *, approval_id: int) -> PendingApprovalDTO | None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, incident_id, severity, title, status, payload
                    FROM pending_approvals
                    WHERE id = %s AND status = 'pending'
                    """,
                    (approval_id,),
                )
                row = await cursor.fetchone()
        return self._row_to_dto(row) if row is not None else None

    async def mark_reviewed(self, *, approval_id: int, status: str) -> None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE pending_approvals
                    SET status = %s,
                        updated_at = NOW()
                    WHERE id = %s AND status = 'pending'
                    """,
                    (status, approval_id),
                )

    def _row_to_dto(self, row: tuple[object, ...]) -> PendingApprovalDTO:
        return PendingApprovalDTO.model_validate(
            {
                "approval_id": row[0],
                "incident_id": row[1],
                "severity": row[2],
                "title": row[3],
                "status": row[4],
                "payload": row[5],
            }
        )

    async def _ensure_table(self) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pending_approvals (
                        id BIGSERIAL PRIMARY KEY,
                        incident_id VARCHAR(128) NOT NULL UNIQUE,
                        severity VARCHAR(20) NOT NULL,
                        title TEXT NOT NULL,
                        status VARCHAR(30) NOT NULL,
                        payload JSONB NOT NULL DEFAULT '{}',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

    def _sanitized_payload(self, incident: dict[str, object]) -> dict[str, object]:
        allowed_keys = (
            "uuid",
            "displayName",
            "description",
            "severity",
            "status",
            "createTime",
            "updateTime",
        )
        return {key: self._safe_text(incident.get(key)) for key in allowed_keys if key in incident}

    def _safe_text(self, value: object, *, fallback: str = "N/A") -> str:
        return self._sanitizer.sanitize_text(str(value or fallback)).text[:1000]

    def _normalize_database_url(self, database_url: str) -> str:
        parts = urlsplit(database_url)
        scheme = parts.scheme.replace("+psycopg", "")
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
