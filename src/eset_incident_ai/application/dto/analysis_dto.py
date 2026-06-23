from __future__ import annotations

from pydantic import BaseModel

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult


class AnalysisDTO(BaseModel):
    incident_id: str
    workflow_run_id: str
    result: IncidentAnalysisResult
