from __future__ import annotations

import pytest

from eset_incident_ai.domain.enums.severity import Severity


@pytest.mark.parametrize(
    ("raw_severity", "expected"),
    [
        ("INCIDENT_SEVERITY_LEVEL_LOW", Severity.LOW),
        ("INCIDENT_SEVERITY_LEVEL_MEDIUM", Severity.MEDIUM),
        ("INCIDENT_SEVERITY_LEVEL_HIGH", Severity.HIGH),
        ("INCIDENT_SEVERITY_LEVEL_CRITICAL", Severity.CRITICAL),
        ("INCIDENT_SEVERITY_LEVEL_UNSPECIFIED", Severity.LOW),
        ("SEVERITY_LEVEL_LOW", Severity.LOW),
        ("SEVERITY_LEVEL_MEDIUM", Severity.MEDIUM),
        ("SEVERITY_LEVEL_HIGH", Severity.HIGH),
        ("SEVERITY_LEVEL_CRITICAL", Severity.CRITICAL),
        ("SEVERITY_LEVEL_UNSPECIFIED", Severity.LOW),
        ("low", Severity.LOW),
        ("medium", Severity.MEDIUM),
        ("high", Severity.HIGH),
        ("critical", Severity.CRITICAL),
        ("info", Severity.LOW),
        ("informational", Severity.LOW),
        ("severity_level_garbage", Severity.LOW),
        ("unknown", Severity.LOW),
        ("", Severity.LOW),
        (None, Severity.LOW),
    ],
)
def test_severity_parse_supports_incident_detection_and_short_forms(
    raw_severity: object,
    expected: Severity,
) -> None:
    assert Severity.parse(raw_severity) is expected
