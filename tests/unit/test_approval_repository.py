from eset_incident_ai.infrastructure.persistence.approval_repository import (
    PostgresApprovalRepository,
)
from eset_incident_ai.security.sanitizer import Sanitizer


def test_approval_repository_normalizes_database_url() -> None:
    repository = PostgresApprovalRepository(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        sanitizer=Sanitizer("test-secret"),
    )

    assert (
        repository._normalize_database_url(  # noqa: SLF001
            "postgresql+psycopg://user:pass@postgres:5432/db"
        )
        == "postgresql://user:pass@postgres:5432/db"
    )


def test_approval_repository_sanitizes_payload() -> None:
    repository = PostgresApprovalRepository(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        sanitizer=Sanitizer("test-secret"),
    )

    payload = repository._sanitized_payload(  # noqa: SLF001
        {
            "uuid": "incident-1",
            "displayName": "alice@example.com",
            "description": "10.1.1.25",
            "ignored": "raw",
        }
    )

    assert "ignored" not in payload
    assert "alice@example.com" not in str(payload)
    assert "10.1.1.25" in str(payload)


def test_approval_repository_maps_row_to_dto() -> None:
    repository = PostgresApprovalRepository(
        database_url="postgresql+psycopg://user:pass@postgres:5432/db",
        sanitizer=Sanitizer("test-secret"),
    )

    approval = repository._row_to_dto(  # noqa: SLF001
        (1, "incident-1", "high", "Sanitized incident", "pending", {"uuid": "incident-1"})
    )

    assert approval.approval_id == 1
    assert approval.payload["uuid"] == "incident-1"
