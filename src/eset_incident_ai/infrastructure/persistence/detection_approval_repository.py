from __future__ import annotations

import json
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.types.json import Jsonb

from eset_incident_ai.application.dto.approval_dto import PendingDetectionApprovalDTO
from eset_incident_ai.security.sanitizer import Sanitizer

RAW_DETECTION_APPROVAL_FIELDS = frozenset({"userName", "device"})


class PostgresDetectionApprovalRepository:
    def __init__(self, *, database_url: str, sanitizer: Sanitizer) -> None:
        self._database_url = self._normalize_database_url(database_url)
        self._sanitizer = sanitizer

    async def save_pending(self, *, detection: dict[str, object], severity: str) -> None:
        await self._ensure_table()
        detection_id = str(detection.get("uuid") or detection.get("displayName") or "unknown")
        title = self._safe_text(detection.get("displayName") or detection_id)
        payload = self._sanitized_payload(detection)
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO pending_detection_approvals (
                        detection_id,
                        severity,
                        title,
                        status,
                        payload
                    )
                    VALUES (%s, %s, %s, 'pending', %s)
                    ON CONFLICT (detection_id) DO UPDATE
                    SET severity = EXCLUDED.severity,
                        title = EXCLUDED.title,
                        payload = EXCLUDED.payload,
                        updated_at = NOW()
                    """,
                    (detection_id, severity, title, Jsonb(payload)),
                )

    async def list_pending(self, *, limit: int) -> list[PendingDetectionApprovalDTO]:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, detection_id, severity, title, status, payload
                    FROM pending_detection_approvals
                    WHERE status = 'pending'
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cursor.fetchall()
        return [self._row_to_dto(row) for row in rows]

    async def get_pending(self, *, approval_id: int) -> PendingDetectionApprovalDTO | None:
        await self._ensure_table()
        async with await psycopg.AsyncConnection.connect(self._database_url) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, detection_id, severity, title, status, payload
                    FROM pending_detection_approvals
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
                    UPDATE pending_detection_approvals
                    SET status = %s,
                        updated_at = NOW()
                    WHERE id = %s AND status = 'pending'
                    """,
                    (status, approval_id),
                )

    def _row_to_dto(self, row: tuple[object, ...]) -> PendingDetectionApprovalDTO:
        return PendingDetectionApprovalDTO.model_validate(
            {
                "approval_id": row[0],
                "detection_id": row[1],
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
                    CREATE TABLE IF NOT EXISTS pending_detection_approvals (
                        id BIGSERIAL PRIMARY KEY,
                        detection_id VARCHAR(128) NOT NULL UNIQUE,
                        severity VARCHAR(20) NOT NULL,
                        title TEXT NOT NULL,
                        status VARCHAR(30) NOT NULL,
                        payload JSONB NOT NULL DEFAULT '{}',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

    def _sanitized_payload(self, detection: dict[str, object]) -> dict[str, object]:
        sanitized_keys = (
            "uuid",
            "displayName",
            "context",
            "severityLevel",
            "category",
            "occurTime",
            "objectName",
            "objectHashSha1",
            "objectUrl",
            "userName",
            "device",
        )
        payload: dict[str, object] = {
            key: self._payload_text(key, detection.get(key))
            for key in sanitized_keys
            if key in detection
        }
        context = detection.get("context")
        user_name = self._detection_user_name(detection, context)
        if user_name:
            payload["userName"] = self._payload_text("userName", user_name)
        device = self._detection_device(detection, context)
        if device:
            payload["device"] = self._payload_text("device", device)
        return payload

    def _payload_text(self, key: str, value: object) -> str:
        text = self._text_value(value)
        if key in RAW_DETECTION_APPROVAL_FIELDS:
            return text[:1000]
        return self._safe_text(text)

    def _safe_text(self, value: object, *, fallback: str = "N/A") -> str:
        return self._sanitizer.sanitize_text(self._text_value(value, fallback=fallback)).text[:1000]

    def _text_value(self, value: object, *, fallback: str = "N/A") -> str:
        raw_value = value or fallback
        if isinstance(raw_value, (dict, list)):
            return json.dumps(raw_value, ensure_ascii=False)
        return str(raw_value)

    def _detection_user_name(self, detection: dict[str, object], context: object) -> object:
        if detection.get("userName"):
            return detection.get("userName")
        if isinstance(context, dict):
            return context.get("userName")
        return None

    def _detection_device(self, detection: dict[str, object], context: object) -> object:
        if detection.get("device"):
            return detection.get("device")
        if not isinstance(context, dict):
            return None
        device_uuid = context.get("deviceUuid")
        if device_uuid:
            return f"uuid:{device_uuid}"
        return context.get("device")

    def _normalize_database_url(self, database_url: str) -> str:
        parts = urlsplit(database_url)
        scheme = parts.scheme.replace("+psycopg", "")
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
