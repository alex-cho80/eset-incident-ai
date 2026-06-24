from __future__ import annotations

from datetime import UTC, datetime

from eset_incident_ai.infrastructure.persistence.detection_approval_repository import (
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
