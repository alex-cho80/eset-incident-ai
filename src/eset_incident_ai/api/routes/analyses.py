from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from eset_incident_ai.api.dependencies import get_analyze_incident
from eset_incident_ai.application.dto.incident_dto import IncidentDTO
from eset_incident_ai.application.use_cases.analyze_incident import AnalyzeIncident
from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult

router = APIRouter(prefix="/analyses", tags=["analyses"])


class RunAnalysisRequest(BaseModel):
    incident: IncidentDTO
    tenant_scope: str = Field(default="default", min_length=1, max_length=100)


@router.post("/run")
async def run_analysis(
    request: RunAnalysisRequest,
    use_case: Annotated[AnalyzeIncident, Depends(get_analyze_incident)],
) -> IncidentAnalysisResult:
    return await use_case.execute(
        incident=request.incident.to_domain(),
        tenant_scope=request.tenant_scope,
    )


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: str) -> dict[str, str]:
    return {"analysis_id": analysis_id, "status": "not_implemented"}
