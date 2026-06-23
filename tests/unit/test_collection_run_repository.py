from datetime import UTC, datetime

from eset_incident_ai.infrastructure.persistence.collection_run_repository import (
    PostgresCollectionRunRepository,
)


def test_collection_run_repository_normalizes_database_url() -> None:
    repository = PostgresCollectionRunRepository("postgresql+psycopg://user:pass@postgres:5432/db")

    assert (
        repository._normalize_database_url(  # noqa: SLF001
            "postgresql+psycopg://user:pass@postgres:5432/db"
        )
        == "postgresql://user:pass@postgres:5432/db"
    )


def test_collection_run_repository_maps_row_to_dto() -> None:
    repository = PostgresCollectionRunRepository("postgresql+psycopg://user:pass@postgres:5432/db")

    dto = repository._row_to_dto(  # noqa: SLF001
        (
            1,
            "failed",
            10,
            2,
            8,
            0,
            0,
            ["uuid"],
            "TimeoutError: request timed out",
            datetime.now(UTC),
        )
    )

    assert dto.run_id == 1
    assert dto.status == "failed"
    assert dto.observed_keys == ["uuid"]
    assert dto.error_message == "TimeoutError: request timed out"
    assert dto.collected_count == 10
    assert dto.notified_count == 2
    assert dto.duplicate_skipped_count == 8
