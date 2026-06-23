from __future__ import annotations

from typing import Protocol

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.domain.entities.incident import Incident


class AnalysisGateway(Protocol):
    async def analyze(
        self, *, incident: Incident, evidence: list[RetrievedEvidence]
    ) -> IncidentAnalysisResult: ...
