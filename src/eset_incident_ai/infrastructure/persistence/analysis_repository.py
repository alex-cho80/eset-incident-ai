from __future__ import annotations

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult


class SqlAlchemyAnalysisRepository:
    async def save(self, *, incident_id: str, result: IncidentAnalysisResult) -> str:
        _ = (incident_id, result)
        raise NotImplementedError("Analysis persistence wiring is pending")
