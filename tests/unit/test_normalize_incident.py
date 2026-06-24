from __future__ import annotations

from eset_incident_ai.application.use_cases.normalize_incident import NormalizeIncident
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.security.sanitizer import Sanitizer


def test_normalize_incident_parses_real_eset_severity_enum() -> None:
    normalizer = NormalizeIncident(Sanitizer("test-secret"))

    incident = normalizer.execute(
        {
            "uuid": "incident-1",
            "name": "Suspicious process",
            "severity": "INCIDENT_SEVERITY_LEVEL_HIGH",
        }
    )

    assert incident.severity is Severity.HIGH
