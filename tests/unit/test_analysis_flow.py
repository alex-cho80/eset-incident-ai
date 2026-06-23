from __future__ import annotations

import pytest

from eset_incident_ai.api.routes.analyses import RunAnalysisRequest, run_analysis
from eset_incident_ai.application.dto.incident_dto import IncidentDTO
from eset_incident_ai.application.use_cases.analyze_incident import AnalyzeIncident
from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.infrastructure.llm.local_gateway import LocalAnalysisGateway


class FakeVectorRepository:
    async def index_document(self, *, document: object, chunks: object, embeddings: object) -> None:
        _ = (document, chunks, embeddings)

    async def search(self, *, query: str, tenant_scope: str, limit: int) -> list[RetrievedEvidence]:
        _ = (query, tenant_scope, limit)
        return [
            RetrievedEvidence(
                evidence_id="evidence-1",
                source_type="knowledge",
                source_id="runbooks/collector-failure.md",
                title="Collector Failure",
                excerpt="Check worker logs",
                relevance_score=0.8,
            )
        ]


class FakeLlmGateway:
    async def analyze(
        self, *, incident: Incident, evidence: list[RetrievedEvidence]
    ) -> IncidentAnalysisResult:
        return await LocalAnalysisGateway().analyze(incident=incident, evidence=evidence)


def incident() -> Incident:
    return Incident(
        id="incident-1",
        external_id="incident-1",
        title="Malware detected",
        severity=Severity.HIGH,
        detected_at=None,
        summary="Endpoint alert",
        normalized_payload={},
    )


@pytest.mark.asyncio
async def test_analyze_incident_uses_retrieved_evidence() -> None:
    result = await AnalyzeIncident(FakeVectorRepository(), FakeLlmGateway()).execute(
        incident=incident(),
        tenant_scope="default",
    )

    assert result.root_cause.direct_cause[0].evidence_ids == ["evidence-1"]
    assert result.requires_destructive_approval is True


@pytest.mark.asyncio
async def test_local_analysis_gateway_handles_missing_evidence() -> None:
    result = await LocalAnalysisGateway().analyze(incident=incident(), evidence=[])

    assert result.root_cause.direct_cause[0].evidence_ids == ["no-supporting-evidence"]
    assert result.evidence_coverage == 0


@pytest.mark.asyncio
async def test_run_analysis_route_handler() -> None:
    request = RunAnalysisRequest(
        incident=IncidentDTO(
            external_id="incident-1",
            title="Malware detected",
            severity=Severity.HIGH,
            summary="Endpoint alert",
        )
    )

    result = await run_analysis(
        request=request,
        use_case=AnalyzeIncident(FakeVectorRepository(), FakeLlmGateway()),
    )

    assert result.overall_confidence > 0
    assert result.root_cause.direct_cause[0].evidence_ids == ["evidence-1"]
