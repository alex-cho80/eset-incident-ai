from __future__ import annotations

from typing import Any

from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.security.sanitizer import Sanitizer

RAW_DETECTION_FIELDS = frozenset({"userName", "device"})


class SanitizedDetectionNotificationBuilder:
    def __init__(self, sanitizer: Sanitizer) -> None:
        self._sanitizer = sanitizer

    def severity(self, detection: dict[str, Any]) -> Severity:
        return Severity.parse(detection.get("severityLevel"))

    def build(self, detection: dict[str, Any]) -> dict[str, Any]:
        severity = self.severity(detection)
        title = self._safe_text(
            "displayName", detection.get("displayName") or detection.get("uuid")
        )
        context = self._safe_text("context", detection.get("context"), fallback="No context")
        fields: list[dict[str, object]] = [
            {
                "name": "Category",
                "value": self._safe_text("category", detection.get("category")),
                "inline": True,
            },
            {
                "name": "Occurred",
                "value": self._safe_text("occurTime", detection.get("occurTime")),
                "inline": True,
            },
            {
                "name": "User",
                "value": self._safe_text("userName", detection.get("userName")),
                "inline": True,
            },
            {
                "name": "Device",
                "value": self._safe_text("device", detection.get("device")),
                "inline": True,
            },
            {
                "name": "Object",
                "value": self._safe_text("objectName", detection.get("objectName")),
            },
            {
                "name": "Object URL",
                "value": self._safe_text("objectUrl", detection.get("objectUrl")),
            },
            {
                "name": "SHA1",
                "value": self._safe_text("objectHashSha1", detection.get("objectHashSha1")),
            },
            {
                "name": "Notice",
                "value": (
                    "Notification: email addresses and local user paths are pseudonymized in "
                    "free-text fields; Detection userName and device fields are shown as-is by "
                    "approved policy."
                ),
            },
        ]

        return {
            "username": "ESET Incident AI",
            "embeds": [
                {
                    "title": f"[{severity.value.upper()}] {title}",
                    "description": context,
                    "fields": fields,
                    "footer": {"text": "Detection notification. Review before action."},
                }
            ],
        }

    def _safe_text(self, field_name: str, value: object, *, fallback: str = "N/A") -> str:
        text = str(value or fallback)
        if field_name in RAW_DETECTION_FIELDS:
            return text[:1000]
        return self._sanitizer.sanitize_text(text).text[:1000]
