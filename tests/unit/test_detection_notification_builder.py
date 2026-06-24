from __future__ import annotations

from eset_incident_ai.infrastructure.discord.detection_notification_builder import (
    RAW_DETECTION_FIELDS,
    SanitizedDetectionNotificationBuilder,
)
from eset_incident_ai.security.sanitizer import Sanitizer


def test_detection_notification_builder_preserves_only_approved_raw_fields() -> None:
    builder = SanitizedDetectionNotificationBuilder(Sanitizer("test-secret"))

    payload = builder.build(
        {
            "uuid": "detection-1",
            "displayName": "Threat for bob@example.com",
            "severityLevel": "SEVERITY_LEVEL_MEDIUM",
            "context": "Observed by analyst alice@example.com",
            "objectName": "C:\\Users\\alice\\Downloads\\sample.exe",
            "objectUrl": "https://example.invalid/alice@example.com",
            "userName": "raw.user@example.com",
            "device": "C:\\Users\\raw-device\\HostA",
            "occurTime": "2026-06-24T00:00:00Z",
        }
    )

    rendered = str(payload)
    fields = payload["embeds"][0]["fields"]  # type: ignore[index]
    values_by_name = {str(field["name"]): field["value"] for field in fields}  # type: ignore[index]
    assert RAW_DETECTION_FIELDS == {"userName", "device"}
    assert values_by_name["User"] == "raw.user@example.com"
    assert values_by_name["Device"] == "C:\\Users\\raw-device\\HostA"
    assert "alice@example.com" not in rendered
    assert "bob@example.com" not in rendered
    assert "C:\\Users\\alice\\" not in rendered
    assert "Detection userName and device fields are shown as-is" in rendered
