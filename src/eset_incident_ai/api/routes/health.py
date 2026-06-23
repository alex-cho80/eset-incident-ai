from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eset_incident_ai.api.dependencies import get_check_readiness
from eset_incident_ai.application.dto.readiness import ReadinessDTO
from eset_incident_ai.application.use_cases.check_readiness import CheckReadiness

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    use_case: Annotated[CheckReadiness, Depends(get_check_readiness)],
) -> ReadinessDTO:
    result = await use_case.execute()
    if not result.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.model_dump(),
        )
    return result
