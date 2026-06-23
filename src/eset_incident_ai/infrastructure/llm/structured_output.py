from __future__ import annotations

import json

from pydantic import ValidationError

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult


class StructuredOutputError(RuntimeError):
    pass


def parse_incident_analysis(raw_json: str) -> IncidentAnalysisResult:
    try:
        payload = json.loads(raw_json)
        return IncidentAnalysisResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise StructuredOutputError("LLM output did not match IncidentAnalysisResult") from exc
