from eset_incident_ai.infrastructure.persistence.notification_repository import (
    PostgresNotificationRepository,
)


def test_notification_repository_normalizes_database_url() -> None:
    repository = PostgresNotificationRepository("postgresql+psycopg://user:pass@postgres:5432/db")

    assert (
        repository._normalize_database_url(  # noqa: SLF001
            "postgresql+psycopg://user:pass@postgres:5432/db"
        )
        == "postgresql://user:pass@postgres:5432/db"
    )
