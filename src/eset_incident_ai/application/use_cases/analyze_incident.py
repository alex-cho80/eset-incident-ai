from __future__ import annotations

from eset_incident_ai.application.ports.llm_gateway import LlmGateway
from eset_incident_ai.application.ports.vector_repository import VectorRepository
from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.entities.incident import Incident


class AnalyzeIncident:
    def __init__(self, vector_repository: VectorRepository, llm_gateway: LlmGateway) -> None:
        self._vector_repository = vector_repository
        self._llm_gateway = llm_gateway

    async def execute(self, *, incident: Incident, tenant_scope: str) -> IncidentAnalysisResult:
        evidence = await self._vector_repository.search(
            query=incident.title,
            tenant_scope=tenant_scope,
            limit=10,
        )
        return await self._llm_gateway.analyze(incident=incident, evidence=evidence)
