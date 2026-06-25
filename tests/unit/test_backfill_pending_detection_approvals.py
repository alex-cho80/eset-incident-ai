from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from eset_incident_ai.domain.enums.severity import Severity


def _load_backfill_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "backfill_pending_detection_approvals.py"
    )
    spec = importlib.util.spec_from_file_location(
        "backfill_pending_detection_approvals",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load backfill script module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_to_analysis_incident_maps_detection_payload() -> None:
    module = _load_backfill_module()

    incident = module.payload_to_analysis_incident(
        {
            "uuid": "detection-1",
            "displayName": "Endpoint threat",
            "context": {"path": "C:\\Users\\redacted\\Downloads\\sample.exe"},
            "occurTime": "2026-06-20T00:00:00Z",
            "severityLevel": "SEVERITY_LEVEL_HIGH",
        },
        Severity.HIGH,
    )

    assert incident.id == "detection-1"
    assert incident.external_id == "detection-1"
    assert incident.title == "Endpoint threat"
    assert incident.severity == Severity.HIGH
    assert incident.detected_at is None
    assert incident.summary == '{"path": "C:\\\\Users\\\\redacted\\\\Downloads\\\\sample.exe"}'
    assert incident.normalized_payload == {
        "source": "eset_detection",
        "raw_keys": ["context", "displayName", "occurTime", "severityLevel", "uuid"],
    }
