from __future__ import annotations

import json
import re

from pydantic import ValidationError

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult


class StructuredOutputError(RuntimeError):
    pass


# Models sometimes wrap JSON output in a markdown code fence despite being instructed
# not to; strip a single leading/trailing fence (with an optional "json" language tag)
# before parsing so that quirk doesn't surface as a validation failure.
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL | re.IGNORECASE)


def parse_incident_analysis(raw_json: str) -> IncidentAnalysisResult:
    try:
        payload = json.loads(_strip_code_fence(raw_json))
        return IncidentAnalysisResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise StructuredOutputError("LLM output did not match IncidentAnalysisResult") from exc


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped
