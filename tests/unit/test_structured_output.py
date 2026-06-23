from __future__ import annotations

import json

import pytest

from eset_incident_ai.infrastructure.llm.structured_output import (
    StructuredOutputError,
    parse_incident_analysis,
)


def _valid_payload_dict() -> dict[str, object]:
    return {
        "root_cause": {
            "executive_summary": "Suspicious RDP activity observed.",
            "direct_cause": [
                {"claim": "RDP abuse detected", "evidence_ids": ["evidence-1"], "confidence": 0.8}
            ],
            "root_causes": [],
            "attack_path": [],
            "affected_assets": [],
            "false_positive_probability": 0.2,
            "unknowns": [],
            "additional_checks": [],
        },
        "remediation": [],
        "overall_confidence": 0.75,
        "evidence_coverage": 0.9,
        "limitations": [],
    }


def test_parses_plain_json() -> None:
    result = parse_incident_analysis(json.dumps(_valid_payload_dict()))
    assert result.overall_confidence == 0.75


def test_strips_json_tagged_code_fence() -> None:
    fenced = f"```json\n{json.dumps(_valid_payload_dict())}\n```"
    result = parse_incident_analysis(fenced)
    assert result.overall_confidence == 0.75


def test_strips_untagged_code_fence() -> None:
    fenced = f"```\n{json.dumps(_valid_payload_dict())}\n```"
    result = parse_incident_analysis(fenced)
    assert result.overall_confidence == 0.75


def test_empty_string_raises_structured_output_error() -> None:
    with pytest.raises(StructuredOutputError):
        parse_incident_analysis("")
