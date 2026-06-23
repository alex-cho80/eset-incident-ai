from __future__ import annotations

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.domain.entities.incident import Incident


class AnthropicGateway:
    async def analyze(
        self, *, incident: Incident, evidence: list[RetrievedEvidence]
    ) -> IncidentAnalysisResult:
        raise NotImplementedError(
            "Anthropic gateway requires provider credentials and prompt wiring"
        )
