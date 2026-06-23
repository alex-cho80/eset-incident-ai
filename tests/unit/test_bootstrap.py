import pytest
from fastapi import HTTPException

from eset_incident_ai.api.routes.analyses import get_analysis
from eset_incident_ai.api.routes.health import health, ready
from eset_incident_ai.api.routes.incidents import get_incident
from eset_incident_ai.application.dto.readiness import ReadinessDTO
from eset_incident_ai.bootstrap import create_app
from eset_incident_ai.settings.config import Settings


class FakeReadinessUseCase:
    def __init__(self, result: ReadinessDTO) -> None:
        self._result = result

    async def execute(self) -> ReadinessDTO:
        return self._result


def test_create_app_registers_expected_routes() -> None:
    app = create_app(Settings(app_name="test-app"))
    paths = set(app.openapi()["paths"])

    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/v1/incidents/{incident_id}" in paths
    assert "/api/v1/incidents/collect-and-notify" in paths
    assert "/api/v1/incidents/collection-runs/latest" in paths
    assert "/api/v1/incidents/collection-runs" in paths
    assert "/api/v1/analyses/run" in paths
    assert "/api/v1/analyses/{analysis_id}" in paths
    assert "/api/v1/approvals/pending" in paths
    assert "/api/v1/approvals/{approval_id}/approve" in paths
    assert "/api/v1/approvals/{approval_id}/reject" in paths
    assert "/api/v1/knowledge/search" in paths


@pytest.mark.asyncio
async def test_route_handlers_return_placeholder_payloads() -> None:
    assert await health() == {"status": "ok"}
    assert await ready(
        use_case=FakeReadinessUseCase(
            ReadinessDTO(status="ready", checks={"database": "ok", "redis": "ok"})
        )
    ) == ReadinessDTO(status="ready", checks={"database": "ok", "redis": "ok"})
    assert await get_incident("incident-1") == {
        "incident_id": "incident-1",
        "status": "not_implemented",
    }
    assert await get_analysis("analysis-1") == {
        "analysis_id": "analysis-1",
        "status": "not_implemented",
    }


@pytest.mark.asyncio
async def test_ready_raises_503_when_dependency_fails() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await ready(
            use_case=FakeReadinessUseCase(
                ReadinessDTO(status="not_ready", checks={"database": "failed", "redis": "ok"})
            )
        )

    assert exc_info.value.status_code == 503
