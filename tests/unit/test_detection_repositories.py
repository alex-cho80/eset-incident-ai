from __future__ import annotations

import json
from datetime import UTC, datetime

from eset_incident_ai.infrastructure.persistence.detection_approval_repository import (
    RAW_DETECTION_APPROVAL_FIELDS,
    PostgresDetectionApprovalRepository,
)
from eset_incident_ai.infrastructure.persistence.detection_collection_run_repository import (
    PostgresDetectionCollectionRunRepository,
)
from eset_incident_ai.security.sanitizer import Sanitizer


def test_detection_approval_repository_maps_detection_id_and_preserves_raw_policy() -> None:
    repository = PostgresDetectionApprovalRepository(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        sanitizer=Sanitizer("test-secret"),
    )

    payload = repository._sanitized_payload(  # noqa: SLF001
        {
            "uuid": "detection-1",
            "displayName": "alice@example.com",
            "context": "contact bob@example.com",
            "objectName": "C:\\Users\\alice\\Downloads\\a.exe",
            "userName": "raw.user@example.com",
            "device": "C:\\Users\\raw-device\\HostA",
            "ignored": "raw",
        }
    )
    approval = repository._row_to_dto(  # noqa: SLF001
        (1, "detection-1", "high", "Detection", "pending", payload)
    )

    assert approval.detection_id == "detection-1"
    assert "ignored" not in payload
    assert "alice@example.com" not in str(payload)
    assert "bob@example.com" not in str(payload)
    assert payload["userName"] == "raw.user@example.com"
    assert payload["device"] == "C:\\Users\\raw-device\\HostA"


def test_detection_approval_repository_reads_nested_context_fallbacks() -> None:
    repository = PostgresDetectionApprovalRepository(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        sanitizer=Sanitizer("test-secret"),
    )

    payload = repository._sanitized_payload(  # noqa: SLF001
        {
            "uuid": "detection-1",
            "displayName": "Threat for alice@example.com",
            "context": {
                "userName": "nt authority\\local service",
                "deviceUuid": "cf48940b-bbc9-41bb-88a7-d4510c5cf214",
                "message": "탐지됨",
            },
        }
    )

    assert RAW_DETECTION_APPROVAL_FIELDS == {"userName", "device"}
    assert payload["userName"] == "nt authority\\local service"
    assert payload["device"] == "uuid:cf48940b-bbc9-41bb-88a7-d4510c5cf214"
    assert "alice@example.com" not in str(payload)


def test_detection_approval_repository_serializes_context_as_json() -> None:
    repository = PostgresDetectionApprovalRepository(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        sanitizer=Sanitizer("test-secret"),
    )

    payload = repository._sanitized_payload(  # noqa: SLF001
        {
            "uuid": "detection-1",
            "context": {"message": "탐지됨", "items": ["one", "two"]},
        }
    )

    context = payload["context"]
    assert isinstance(context, str)
    assert json.loads(context) == {"message": "탐지됨", "items": ["one", "two"]}
    assert "'message':" not in context


def test_detection_collection_run_repository_maps_last_page_token() -> None:
    repository = PostgresDetectionCollectionRunRepository(
        "postgresql+psycopg://user:pass@postgres:5432/db"
    )

    dto = repository._row_to_dto(  # noqa: SLF001
        (
            1,
            "succeeded",
            10,
            2,
            1,
            3,
            4,
            ["uuid"],
            None,
            "page-2",
            datetime.now(UTC),
        )
    )

    assert dto.run_id == 1
    assert dto.last_page_token == "page-2"  # noqa: S105
    assert dto.pending_approval_count == 3
